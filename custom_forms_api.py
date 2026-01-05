"""
Custom Forms API Endpoints

API endpoints for doctors to upload and manage custom forms.
Add these endpoints to api.py before the `if __name__ == "__main__"` block.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Header
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import os
from datetime import datetime
from io import BytesIO
import requests
from reportlab.lib.colors import HexColor

from tools.form_converter.api import FormConverterAPI

# Aneya brand colors for professional PDF styling
ANEYA_NAVY = HexColor('#0c3555')
ANEYA_TEAL = HexColor('#1d9e99')
ANEYA_GRAY = HexColor('#6b7280')
ANEYA_LIGHT_GRAY = HexColor('#d1d5db')

# Create router
router = APIRouter(prefix="/api/custom-forms", tags=["custom-forms"])


# Helper function to get Supabase client
def get_supabase_client():
    """Get Supabase client for database operations"""
    from supabase import create_client, Client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase configuration not available")

    return create_client(supabase_url, supabase_key)


# ============================================
# REQUEST/RESPONSE MODELS
# ============================================

class CreateCustomFormRequest(BaseModel):
    form_name: str
    specialty: str
    description: Optional[str] = None
    is_public: bool = False
    organization_id: Optional[str] = None


class CustomFormResponse(BaseModel):
    id: str
    form_name: str
    specialty: str
    description: Optional[str]
    patient_criteria: Optional[str] = None  # Optional - describes which patients this form is for
    created_by: str
    is_public: bool
    status: str
    version: int
    field_count: int
    section_count: int
    created_at: str
    updated_at: str


class FormConversionStatusResponse(BaseModel):
    success: bool
    form_id: Optional[str] = None
    form_name: str
    specialty: str
    field_count: Optional[int] = None
    section_count: Optional[int] = None
    error: Optional[str] = None


class FormExtractionResponse(BaseModel):
    """Response for initial extraction (before review)"""
    success: bool
    form_name: str
    specialty: str
    form_schema: Dict[str, Any]  # Extracted form schema (sections + fields)
    pdf_template: Dict[str, Any]  # Extracted PDF layout
    patient_criteria: str = ""  # Required - AI-extracted description of which patients this form is for
    metadata: Dict[str, Any]  # Field counts, image count, etc.
    error: Optional[str] = None


class SaveFormRequest(BaseModel):
    """Request body for saving reviewed form"""
    form_name: str
    specialty: str
    form_schema: Dict[str, Any]
    pdf_template: Dict[str, Any]
    description: Optional[str] = None
    patient_criteria: str  # Required - must specify which patients this form is for
    is_public: bool = False
    metadata: Optional[Dict[str, Any]] = None  # Includes logo_info with logo_url


# ============================================
# HELPER FUNCTIONS
# ============================================

def verify_firebase_token_and_get_user_id(authorization: str) -> str:
    """
    Verify Firebase JWT token and return user ID

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")

    Returns:
        str: User ID from Firebase token
    """
    import firebase_admin
    from firebase_admin import auth as firebase_auth

    # Extract JWT token from Authorization header
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    firebase_token = authorization.replace("Bearer ", "")

    try:
        # Verify Firebase JWT token
        decoded_token = firebase_auth.verify_id_token(firebase_token)
        user_id = decoded_token['uid']

        print(f"✅ Verified Firebase token for user: {user_id}")
        return user_id

    except Exception as e:
        print(f"❌ Firebase token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")


def get_current_user_id() -> Optional[str]:
    """
    Legacy function - kept for backward compatibility
    TODO: Remove after migrating all endpoints to use verify_firebase_token_and_get_user_id
    """
    return None


# ============================================
# ENDPOINTS
# ============================================

@router.post("/upload", response_model=FormExtractionResponse)
async def upload_custom_form(
    form_name: str = Form(...),
    specialty: str = Form(...),
    description: Optional[str] = Form(None),
    is_public: bool = Form(False),
    files: List[UploadFile] = File(...)
):
    """
    Upload form images and extract schema + PDF template for review.
    DOES NOT save to database - returns extraction results for doctor to review.

    Args:
        form_name: Name for the form in snake_case
        specialty: Medical specialty (e.g., 'cardiology', 'neurology')
        description: Optional description of the form
        is_public: Whether to make form available to all doctors
        files: List of HEIC/JPEG/PNG image files

    Returns:
        Extraction results with schema and PDF template for review
    """
    try:
        user_id = get_current_user_id()

        # Validate inputs
        if not files or len(files) == 0:
            raise HTTPException(status_code=400, detail="No files uploaded")

        if len(files) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 images allowed")

        # Validate form name and specialty
        converter = FormConverterAPI()

        valid_name, name_error = converter.validate_form_name(form_name)
        if not valid_name:
            raise HTTPException(status_code=400, detail=f"Invalid form name: {name_error}")

        valid_specialty, specialty_error = converter.validate_specialty(specialty)
        if not valid_specialty:
            raise HTTPException(status_code=400, detail=f"Invalid specialty: {specialty_error}")

        # Read uploaded files
        uploaded_bytes = []
        filenames = []

        print(f"\n📤 Upload request received:")
        print(f"   Form name: {form_name}")
        print(f"   Specialty: {specialty}")
        print(f"   File count: {len(files)}")

        for file in files:
            content = await file.read()
            uploaded_bytes.append(content)
            filenames.append(file.filename)
            print(f"   - {file.filename}: {len(content) / 1024:.1f} KB")

            # Validate file size (max 10MB per file)
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} exceeds 10MB limit"
                )

        # Convert form
        print(f"\n🔄 Starting form conversion...")
        result = converter.convert_from_uploaded_files(
            uploaded_files=uploaded_bytes,
            filenames=filenames,
            form_name=form_name,
            specialty=specialty,
            generate_migration=True,
            generate_typescript=True
        )

        if not result.success:
            print(f"❌ Conversion failed: {result.error}")
            return FormExtractionResponse(
                success=False,
                form_name=form_name,
                specialty=specialty,
                form_schema={},
                pdf_template={},
                metadata={},
                error=result.error
            )

        print(f"✅ Conversion successful!")
        print(f"   Schema sections: {len(result.schema) if isinstance(result.schema, dict) else 'N/A'}")
        print(f"   PDF template sections: {len(result.pdf_template.get('sections', [])) if result.pdf_template else 0}")

        # Extract patient_criteria from metadata
        patient_criteria = result.metadata.get('patient_criteria') if result.metadata else None
        if patient_criteria:
            print(f"   Patient criteria: {patient_criteria[:100]}...")

        # DISABLED: Logo extraction temporarily disabled - can be fixed later
        # Extract and upload logo if detected
        # logo_url = None
        # logo_info = result.metadata.get('logo_info', {}) if result.metadata else {}
        # if logo_info.get('has_logo') and logo_info.get('bounding_box'):
        #     try:
        #         # We need to save uploaded files temporarily to extract logo
        #         import tempfile
        #         from pathlib import Path
        #         from tools.form_converter.image_analyzer import ImageAnalyzer
        #         from supabase import create_client, Client
        #
        #         # Connect to Supabase
        #         supabase_url = os.getenv("SUPABASE_URL")
        #         supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        #         supabase: Client = create_client(supabase_url, supabase_key)
        #
        #         # Save first image to temp file
        #         with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filenames[0]).suffix) as tmp_file:
        #             tmp_file.write(uploaded_bytes[0])
        #             temp_path = tmp_file.name
        #
        #         # Extract and upload logo
        #         analyzer = ImageAnalyzer()
        #         facility_name = logo_info.get('facility_name', form_name)
        #         # Use form_name as pseudo user_id for now (no auth on upload endpoint)
        #         logo_url = analyzer.extract_and_upload_logo(
        #             image_path=temp_path,
        #             bounding_box=logo_info['bounding_box'],
        #             supabase_client=supabase,
        #             user_id=form_name,  # Use form_name as folder since no auth yet
        #             facility_name=facility_name
        #         )
        #
        #         # Clean up temp file
        #         Path(temp_path).unlink(missing_ok=True)
        #
        #         # Add logo URL to metadata
        #         if logo_url:
        #             logo_info['logo_url'] = logo_url
        #             if result.metadata:
        #                 result.metadata['logo_info'] = logo_info
        #
        #     except Exception as e:
        #         print(f"⚠️ Failed to extract logo: {e}")
        #         import traceback
        #         traceback.print_exc()

        print("ℹ️  Logo detection disabled - can be re-enabled later")

        # CHANGED: Return extraction results for review (don't save to DB yet)
        return FormExtractionResponse(
            success=True,
            form_name=form_name,
            specialty=specialty,
            form_schema=result.schema,
            pdf_template=result.pdf_template,
            patient_criteria=patient_criteria,
            metadata=result.metadata
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error uploading custom form: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save", response_model=CustomFormResponse)
async def save_custom_form(
    request: SaveFormRequest,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Save doctor-reviewed form schema + PDF template to database.
    Called AFTER doctor has reviewed and edited the extracted schema.

    Args:
        request: SaveFormRequest with reviewed schema and PDF template
        authorization: Firebase JWT token in Authorization header

    Returns:
        CustomFormResponse with saved form details
    """
    try:
        # Verify Firebase authentication and get user ID
        user_id = verify_firebase_token_and_get_user_id(authorization)

        # Validate form name
        converter = FormConverterAPI()
        valid_name, name_error = converter.validate_form_name(request.form_name)
        if not valid_name:
            raise HTTPException(status_code=400, detail=f"Invalid form name: {name_error}")

        valid_specialty, specialty_error = converter.validate_specialty(request.specialty)
        if not valid_specialty:
            raise HTTPException(status_code=400, detail=f"Invalid specialty: {specialty_error}")

        # ✅ VALIDATE SCHEMA IS NOT EMPTY
        if not request.form_schema:
            raise HTTPException(
                status_code=400,
                detail="form_schema is required and cannot be empty"
            )

        if not isinstance(request.form_schema, (dict, list)):
            raise HTTPException(
                status_code=400,
                detail="form_schema must be a JSON object or array"
            )

        # Calculate metadata from schema
        field_count = 0
        section_count = 0

        # Handle both dict (new format) and list (fallback) schema structures
        if isinstance(request.form_schema, dict):
            section_count = len(request.form_schema)
            for section_data in request.form_schema.values():
                if isinstance(section_data, dict) and 'fields' in section_data:
                    field_count += len(section_data.get('fields', []))
        elif isinstance(request.form_schema, list):
            section_count = len(request.form_schema)
            for section in request.form_schema:
                if isinstance(section, dict) and 'fields' in section:
                    field_count += len(section.get('fields', []))

        # ✅ VALIDATE FIELD COUNT
        if field_count == 0:
            raise HTTPException(
                status_code=400,
                detail=f"form_schema must contain at least one field (found {section_count} sections but 0 fields)"
            )

        print(f"✅ Validated schema: {section_count} sections, {field_count} fields")

        # Connect to Supabase
        from supabase import create_client, Client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # NEW: Classify tables after doctor review
        print(f"\n🔍 Classifying tables for data source detection...")
        from tools.table_classifier import TableClassifier

        classifier = TableClassifier()
        table_metadata = await classifier.classify_all_tables(
            form_schema=request.form_schema,
            form_metadata={
                "form_name": request.form_name,
                "specialty": request.specialty,
                "description": request.description or "",
                "patient_criteria": request.patient_criteria
            }
        )

        print(f"✅ Table classification complete")

        # Insert into custom_forms table
        form_data = {
            "form_name": request.form_name,
            "specialty": request.specialty,
            "created_by": user_id,
            "is_public": request.is_public,
            "form_schema": request.form_schema,
            "pdf_template": request.pdf_template,  # Save PDF template
            "description": request.description,
            "patient_criteria": request.patient_criteria,  # Save patient criteria for LLM form selector
            "field_count": field_count,
            "section_count": section_count,
            "status": "active",  # Form is ready to use after review
            "table_metadata": table_metadata  # NEW: Store table classifications
        }

        response = supabase.table("custom_forms").insert(form_data).execute()

        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to save form to database")

        form_record = response.data[0]

        # DISABLED: Logo update temporarily disabled - can be fixed later
        # Update doctor's profile with extracted logo if available
        # logo_info = request.metadata.get('logo_info', {}) if request.metadata else {}
        # logo_url = logo_info.get('logo_url')
        # clinic_name_from_logo = logo_info.get('facility_name')
        #
        # if logo_url:
        #     try:
        #         # Update doctor's clinic_logo_url
        #         update_data = {"clinic_logo_url": logo_url}
        #
        #         # Also update clinic_name if detected and not already set
        #         if clinic_name_from_logo:
        #             # Check if doctor has clinic_name set
        #             doctor_check = supabase.table("doctors")\
        #                 .select("clinic_name")\
        #                 .eq("user_id", user_id)\
        #                 .execute()
        #
        #             if doctor_check.data and not doctor_check.data[0].get('clinic_name'):
        #                 update_data["clinic_name"] = clinic_name_from_logo
        #
        #         # Update doctor profile
        #         supabase.table("doctors")\
        #             .update(update_data)\
        #             .eq("user_id", user_id)\
        #             .execute()
        #
        #         print(f"✅ Updated doctor profile with logo: {logo_url}")
        #         if 'clinic_name' in update_data:
        #             print(f"✅ Set clinic name to: {clinic_name_from_logo}")
        #
        #     except Exception as e:
        #         print(f"⚠️ Failed to update doctor profile with logo: {e}")
        #         # Don't fail the whole request if logo update fails

        print("ℹ️  Logo profile update disabled - can be re-enabled later")

        # Return saved form details
        return CustomFormResponse(
            id=form_record['id'],
            form_name=form_record['form_name'],
            specialty=form_record['specialty'],
            description=form_record.get('description'),
            patient_criteria=form_record.get('patient_criteria') or f"General {form_record['specialty']} patients",
            created_by=form_record['created_by'],
            is_public=form_record['is_public'],
            status=form_record['status'],
            version=form_record['version'],
            field_count=form_record['field_count'] or 0,
            section_count=form_record['section_count'] or 0,
            created_at=form_record['created_at'],
            updated_at=form_record['updated_at']
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error saving custom form: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class PreviewPDFRequest(BaseModel):
    """Request body for PDF preview generation"""
    form_name: str
    form_schema: Dict[str, Any]
    pdf_template: Dict[str, Any]
    clinic_logo_url: Optional[str] = None  # Optional clinic logo URL for header
    clinic_name: Optional[str] = None  # Optional clinic name for header
    primary_color: Optional[str] = None  # Primary brand color (defaults to Aneya Navy)
    accent_color: Optional[str] = None  # Accent brand color (defaults to Aneya Teal)
    text_color: Optional[str] = None  # Text color (defaults to Aneya Gray)
    light_gray_color: Optional[str] = None  # Light gray for borders (defaults to Aneya Light Gray)


# ============================================
# HELPER FUNCTIONS FOR TABLE RENDERING
# ============================================

def get_column_width_cm(col_name: str, col_types: Dict[str, str]) -> float:
    """
    Get width for a single column based on type.

    Args:
        col_name: Column name
        col_types: Mapping of column names to field types

    Returns:
        Width in cm
    """
    if col_types.get(col_name) == 'boolean':
        return 1.0
    elif col_types.get(col_name) == 'number' or 'No.' in col_name or 'Year' in col_name:
        return 1.3
    elif 'Date' in col_name:
        return 1.8
    else:
        return 2.5  # text default


def calculate_table_width_cm(column_names: List[str], row_fields: List[Dict], is_transposed: bool) -> float:
    """
    Calculate total width required for table.

    Args:
        column_names: List of column headers
        row_fields: List of field definitions
        is_transposed: Whether this is a transposed table

    Returns:
        Total width in cm
    """
    col_widths = []
    col_types = {}

    # Map column names to field types
    for field in row_fields:
        field_label = field.get('label', '')
        field_type = field.get('type', 'string')
        col_types[field_label] = field_type

    # Calculate width for each column
    for i, col_name in enumerate(column_names if not is_transposed else [''] + column_names):
        if i == 0 and is_transposed:
            # First column in transposed table (row labels)
            col_widths.append(2.2)  # cm
        else:
            col_widths.append(get_column_width_cm(col_name, col_types))

    return sum(col_widths)


def split_table_columns(column_names: List[str], row_fields: List[Dict], available_width_cm: float,
                        is_transposed: bool, include_first_col: bool = True) -> List[Dict[str, Any]]:
    """
    Split table columns into chunks that fit within available width.

    Args:
        column_names: List of column headers
        row_fields: List of field definitions
        available_width_cm: Available width in cm
        is_transposed: Whether this is a transposed table
        include_first_col: Always include first column in each chunk for alignment

    Returns:
        List of column chunks, each chunk is a dict with:
        {
            'column_names': [...],
            'row_fields': [...],
            'row_names': [...] (for transposed),
            'is_continuation': bool
        }
    """
    chunks = []

    # Map column types for width calculation
    col_types = {}
    for field in row_fields:
        col_types[field.get('label', '')] = field.get('type', 'string')

    # Get first column (for alignment)
    if is_transposed:
        first_col_width = 2.2  # cm
        first_col_name = ''
        first_col_field = None
    else:
        first_col_width = get_column_width_cm(column_names[0], col_types) if column_names else 0
        first_col_name = column_names[0] if column_names else ''
        first_col_field = row_fields[0] if row_fields else None

    # Calculate remaining columns
    remaining_cols = column_names[1:] if not is_transposed and column_names else column_names
    remaining_fields = row_fields[1:] if not is_transposed and row_fields else row_fields

    current_chunk_cols = [first_col_name] if include_first_col and first_col_name else []
    current_chunk_fields = [first_col_field] if include_first_col and first_col_field else []
    current_width = first_col_width if include_first_col else 0

    for col_name, field in zip(remaining_cols, remaining_fields):
        col_width = get_column_width_cm(col_name, col_types)

        if current_width + col_width > available_width_cm:
            # Save current chunk and start new one
            chunks.append({
                'column_names': current_chunk_cols,
                'row_fields': current_chunk_fields,
                'is_continuation': len(chunks) > 0
            })

            # Start new chunk with first column (for alignment)
            current_chunk_cols = [first_col_name] if include_first_col and first_col_name else []
            current_chunk_fields = [first_col_field] if include_first_col and first_col_field else []
            current_width = first_col_width if include_first_col else 0

        current_chunk_cols.append(col_name)
        current_chunk_fields.append(field)
        current_width += col_width

    # Add final chunk
    if current_chunk_cols:
        chunks.append({
            'column_names': current_chunk_cols,
            'row_fields': current_chunk_fields,
            'is_continuation': len(chunks) > 0
        })

    return chunks


def section_needs_landscape(section_fields: List[Dict], form_schema: Dict) -> bool:
    """
    Check if a section contains any fields that require landscape orientation.

    Prevents orphaned section headers by detecting if section content needs landscape
    before rendering the header. This ensures headers always appear on the same page
    as their content.

    Args:
        section_fields: List of field definitions from PDF template
        form_schema: Complete form schema to get field metadata

    Returns:
        True if section should start in landscape mode
    """
    for field in section_fields:
        field_name = field.get('field_name', '')

        # Find field in schema
        schema_field = None
        for schema_section in form_schema.values():
            if isinstance(schema_section, dict) and 'fields' in schema_section:
                for f in schema_section['fields']:
                    if f.get('name') == field_name:
                        schema_field = f
                        break
            if schema_field:
                break

        # Check if this is a table that needs landscape
        if schema_field and schema_field.get('type') == 'array' and schema_field.get('input_type', '').startswith('table'):
            row_fields = schema_field.get('row_fields', [])
            column_names = schema_field.get('column_names', [])
            is_transposed = schema_field.get('input_type') == 'table_transposed'

            # Calculate table width
            table_width_cm = calculate_table_width_cm(column_names, row_fields, is_transposed)
            portrait_available_cm = (21 - 4)  # A4 portrait width (21cm) - margins (4cm)

            if table_width_cm > portrait_available_cm:
                return True  # First landscape-needing field found

    return False


def render_page_header_with_logo(c, y: float, logo_url: Optional[str], clinic_name: Optional[str],
                                  width: float, height: float, show_title: bool = False,
                                  title: str = "", primary_color=None) -> float:
    """
    Render page header with optional logo and title

    Args:
        c: ReportLab canvas
        y: Current Y position
        logo_url: Optional clinic logo URL
        clinic_name: Optional clinic name
        width: Page width
        height: Page height
        show_title: Whether to show the form title
        title: Form title
        primary_color: Color for title text

    Returns:
        Updated Y position
    """
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import cm

    # Render logo or clinic name
    logo_rendered = False
    if logo_url:
        logo_rendered = render_clinic_logo(c, y, logo_url, width, height)

    if not logo_rendered and clinic_name:
        if primary_color:
            c.setFillColor(primary_color)
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(width - 2*cm, y + 0.5*cm, clinic_name)

    # Optionally show title (for first page only)
    if show_title and title:
        c.setFont("Helvetica-Bold", 14)
        if primary_color:
            c.setFillColor(primary_color)
        c.drawString(2*cm, y, title)
        y -= 0.8*cm

    return y


def render_clinic_logo(c, y: float, logo_url: str, width: float, height: float) -> bool:
    """
    Download clinic logo from URL and render in top-right corner

    Args:
        c: ReportLab canvas
        y: Current Y position
        logo_url: Public URL of the clinic logo
        width: Page width
        height: Page height

    Returns:
        bool: True if logo rendered successfully, False otherwise
    """
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.units import cm

    try:
        # Download logo with timeout
        response = requests.get(logo_url, timeout=5)
        response.raise_for_status()

        # Load image
        image_bytes = BytesIO(response.content)
        img = ImageReader(image_bytes)

        # Calculate scaling to fit within 70mm x 28mm
        img_width, img_height = img.getSize()
        max_width, max_height = 7*cm, 2.8*cm
        scale = min(max_width/img_width, max_height/img_height)

        scaled_width = img_width * scale
        scaled_height = img_height * scale

        # Position in top-right corner (works for both portrait and landscape)
        x_pos = width - 2*cm - scaled_width
        y_pos = y + 0.5*cm

        # Draw image
        c.drawImage(img, x_pos, y_pos,
                   width=scaled_width,
                   height=scaled_height,
                   preserveAspectRatio=True,
                   mask='auto')

        print(f"✅ Clinic logo rendered successfully")
        return True

    except Exception as e:
        print(f"⚠️  Failed to render clinic logo: {e}")
        return False  # Graceful fallback


@router.post("/preview-pdf")
async def preview_pdf(request: PreviewPDFRequest):
    """
    Generate a preview PDF based on the form schema and PDF template.
    Returns a sample PDF with placeholder/empty data for review.

    Args:
        request: PreviewPDFRequest with form schema and PDF template

    Returns:
        PDF file as downloadable response
    """
    from fastapi.responses import StreamingResponse
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import cm
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors

    try:
        # Create PDF buffer
        buffer = BytesIO()

        # Create canvas
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        current_page_orientation = 'portrait'  # Track page orientation

        # Get template config
        page_config = request.pdf_template.get('page_config', {})
        sections = request.pdf_template.get('sections', [])
        styling = request.pdf_template.get('styling', {})

        # Debug: Compare schema fields with PDF template fields
        print(f"\n📊 PDF Preview Debug:")
        print(f"   Schema sections: {len(request.form_schema)}")
        print(f"   PDF template sections: {len(sections)}")

        # Get all table fields from schema
        schema_tables = []
        for section_name, section_data in request.form_schema.items():
            if isinstance(section_data, dict) and 'fields' in section_data:
                for field in section_data['fields']:
                    if field.get('type') == 'array' and field.get('input_type', '').startswith('table'):
                        schema_tables.append({
                            'section': section_name,
                            'name': field.get('name'),
                            'type': field.get('input_type')
                        })

        print(f"   Tables in schema: {len(schema_tables)}")
        for table in schema_tables:
            print(f"      - {table['name']} ({table['type']}) in section '{table['section']}'")

        # Get all fields from PDF template
        template_fields = []
        for section in sections:
            section_id = section.get('id', '')
            for field in section.get('fields', []):
                field_name = field.get('field_name', '')
                template_fields.append({
                    'section': section_id,
                    'name': field_name
                })

        print(f"   Fields in PDF template: {len(template_fields)}")

        # Check which tables are missing from PDF template
        template_field_names = set(f['name'] for f in template_fields)
        missing_tables = [t for t in schema_tables if t['name'] not in template_field_names]

        if missing_tables:
            print(f"   ⚠️  TABLES MISSING FROM PDF TEMPLATE:")
            for table in missing_tables:
                print(f"      - {table['name']} ({table['type']}) from section '{table['section']}'")
        else:
            print(f"   ✅ All {len(schema_tables)} tables found in PDF template")

        # Colors - Use doctor's custom colors or fall back to Aneya brand colors
        primary_color = HexColor(request.primary_color or styling.get('primary_color', '#0c3555'))
        accent_color = HexColor(request.accent_color or styling.get('accent_color', '#1d9e99'))
        text_color = HexColor(request.text_color or '#6b7280')
        light_gray_color = HexColor(request.light_gray_color or '#d1d5db')

        # Starting Y position
        y = height - 2*cm

        # Get form title
        form_title = page_config.get('header', {}).get('title', request.form_name.replace('_', ' ').title())

        # Render header with logo and title (first page)
        y = render_page_header_with_logo(
            c, y,
            logo_url=request.clinic_logo_url,
            clinic_name=request.clinic_name,
            width=width,
            height=height,
            show_title=True,
            title=form_title,
            primary_color=primary_color
        )

        c.setFont("Helvetica", 9)
        c.setFillColor(text_color)
        c.drawString(2*cm, y, f"Preview Generated: {datetime.now().strftime('%d %B %Y at %H:%M')}")

        y -= 1*cm

        # Render sections - show ALL sections and fields
        for section in sections:
            section_title = section.get('title', section.get('id', ''))
            section_fields = section.get('fields', [])
            layout = section.get('layout', 'single_column')

            # CHANGE 1: Check if section needs landscape BEFORE rendering header
            section_requires_landscape = section_needs_landscape(section_fields, request.form_schema)

            # CHANGE 2: If section needs landscape, switch orientation first
            if section_requires_landscape and current_page_orientation == 'portrait':
                # Start new landscape page for entire section
                c.showPage()
                c.setPageSize(landscape(A4))
                current_page_orientation = 'landscape'
                width, height = landscape(A4)
                y = height - 2*cm
                # Render header with logo on new page
                y = render_page_header_with_logo(
                    c, y,
                    logo_url=request.clinic_logo_url,
                    clinic_name=request.clinic_name,
                    width=width,
                    height=height,
                    show_title=False,
                    title="",
                    primary_color=primary_color
                )
                print(f"   📐 Section '{section_title}' started in landscape (contains wide tables)")

            # CHANGE 3: Normal page break check (but respect current orientation)
            elif y < 4*cm:
                c.showPage()
                # Set page size based on current orientation
                if current_page_orientation == 'landscape':
                    c.setPageSize(landscape(A4))
                    width, height = landscape(A4)
                else:
                    c.setPageSize(A4)
                    width, height = A4
                y = height - 2*cm
                # Render header with logo on new page
                y = render_page_header_with_logo(
                    c, y,
                    logo_url=request.clinic_logo_url,
                    clinic_name=request.clinic_name,
                    width=width,
                    height=height,
                    show_title=False,
                    title="",
                    primary_color=primary_color
                )

            # Section header (now rendered on correct orientation)
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(primary_color)
            c.drawString(2*cm, y, section_title)
            y -= 0.7*cm

            # Render ALL section fields
            for field in section_fields:
                # Get field from schema to check if it's a table
                field_name = field.get('field_name', '')

                # Find field in schema to get full metadata
                schema_field = None
                for schema_section in request.form_schema.values():
                    if isinstance(schema_section, dict) and 'fields' in schema_section:
                        for f in schema_section['fields']:
                            if f.get('name') == field_name:
                                schema_field = f
                                break
                    if schema_field:
                        break

                # Check if this is a table field
                is_table = schema_field and schema_field.get('type') == 'array' and schema_field.get('input_type', '').startswith('table')

                if is_table:
                    # Render actual table structure
                    column_names = schema_field.get('column_names', [])
                    row_names = schema_field.get('row_names', [])
                    is_transposed = schema_field.get('input_type') == 'table_transposed'
                    row_fields = schema_field.get('row_fields', [])
                    field_label = field.get('label', field_name)

                    # Calculate table width to determine if landscape/splitting is needed
                    table_width_cm = calculate_table_width_cm(column_names, row_fields, is_transposed)
                    portrait_available_cm = (width - 4*cm) / cm  # A4 portrait: ~17cm available
                    landscape_available_cm = (landscape(A4)[0] - 4*cm) / cm  # A4 landscape: ~25.7cm available

                    needs_landscape = table_width_cm > portrait_available_cm
                    needs_splitting = table_width_cm > landscape_available_cm

                    # Switch to landscape if needed
                    if needs_landscape and current_page_orientation == 'portrait':
                        # Only switch if not already in landscape
                        c.showPage()
                        c.setPageSize(landscape(A4))
                        current_page_orientation = 'landscape'
                        width, height = landscape(A4)
                        y = height - 2*cm
                        print(f"   📐 Table '{field_name}' switched to landscape ({table_width_cm:.1f}cm > {portrait_available_cm:.1f}cm)")
                    elif needs_landscape:
                        # Already in landscape (section header handled it), just check if we need new page
                        if y < 6*cm:  # Need space for table
                            c.showPage()
                            c.setPageSize(landscape(A4))
                            y = height - 2*cm

                    # Check if we need table splitting
                    if needs_splitting:
                        # Split table across multiple landscape pages
                        available_width_cm = (width - 4*cm) / cm
                        column_chunks = split_table_columns(column_names, row_fields, available_width_cm, is_transposed, include_first_col=True)

                        print(f"   ✂️  Table '{field_name}' split into {len(column_chunks)} chunks ({table_width_cm:.1f}cm > {landscape_available_cm:.1f}cm)")

                        for chunk_idx, chunk in enumerate(column_chunks):
                            # New page for continuation chunks
                            if chunk_idx > 0:
                                c.showPage()
                                c.setPageSize(landscape(A4))
                                width, height = landscape(A4)
                                y = height - 2*cm

                            # Table title with continuation indicator
                            continuation_label = f"{field_label} (continued)" if chunk['is_continuation'] else field_label

                            # Calculate space needed
                            rows_to_show = min(3, len(row_names)) if row_names else 3
                            table_height = (rows_to_show + 1) * 0.6*cm  # +1 for header

                            # Check if we need a new page
                            if y < (table_height + 3*cm):
                                c.showPage()
                                c.setPageSize(landscape(A4))
                                width, height = landscape(A4)
                                y = height - 2*cm

                            # Table title
                            c.setFont("Helvetica-Bold", 9)
                            c.setFillColor(primary_color)
                            c.drawString(2.5*cm, y, f"• {continuation_label}")
                            y -= 0.6*cm

                            # Render chunk using chunk's column_names and row_fields
                            chunk_column_names = chunk['column_names']
                            chunk_row_fields = chunk['row_fields']

                            if chunk_column_names:
                                # Create paragraph style for wrapping headers
                                header_style = ParagraphStyle(
                                    'TableHeader',
                                    fontName='Helvetica-Bold',
                                    fontSize=7,
                                    leading=8,
                                    alignment=1  # Center
                                )

                                # Prepare table data for this chunk
                                if is_transposed and row_names:
                                    # Transposed table: rows are attributes, columns are entries
                                    header_paragraphs = [''] + [Paragraph(col, header_style) for col in chunk_column_names if col]
                                    table_data = [header_paragraphs]

                                    # Data rows: row name + empty cells
                                    for row_name in row_names[:8]:  # Show first 8 rows
                                        row = [row_name] + [''] * (len(chunk_column_names) - 1 if chunk_column_names[0] == '' else len(chunk_column_names))
                                        table_data.append(row)

                                else:
                                    # Regular table: columns are fields, rows are entries
                                    header_paragraphs = [Paragraph(col, header_style) for col in chunk_column_names if col]
                                    table_data = [header_paragraphs]

                                    # Add 3 empty rows
                                    for i in range(3):
                                        table_data.append([''] * len(header_paragraphs))

                                # Calculate column widths for this chunk
                                available_width = width - 4*cm
                                col_widths = []

                                # Map column names to field types for this chunk
                                col_types = {}
                                for f in chunk_row_fields:
                                    col_types[f.get('label', '')] = f.get('type', 'string')

                                # Determine width for each column
                                for i, col_name in enumerate(chunk_column_names if not is_transposed else [''] + chunk_column_names):
                                    if i == 0 and is_transposed:
                                        col_widths.append(2.2*cm)
                                    elif col_types.get(col_name) == 'boolean':
                                        col_widths.append(1.0*cm)
                                    elif col_types.get(col_name) == 'number' or 'No.' in col_name or 'Year' in col_name:
                                        col_widths.append(1.3*cm)
                                    elif 'Date' in col_name:
                                        col_widths.append(1.8*cm)
                                    else:
                                        col_widths.append(None)

                                # Calculate remaining space for text columns
                                fixed_width = sum(w for w in col_widths if w is not None)
                                text_cols = sum(1 for w in col_widths if w is None)
                                if text_cols > 0:
                                    remaining = available_width - fixed_width
                                    text_col_width = max(1.8*cm, remaining / text_cols)
                                    col_widths = [w if w is not None else text_col_width for w in col_widths]

                                # Create and style table
                                row_heights = [None] * len(table_data)
                                row_heights[0] = 0.8*cm  # Taller header row for wrapped text

                                table = Table(table_data, colWidths=col_widths, rowHeights=row_heights)
                                table.setStyle(TableStyle([
                                    # Header styling - Brand primary color with white text
                                    ('BACKGROUND', (0, 0), (-1, 0), primary_color),
                                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                                    ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                                    ('TEXTCOLOR', (0, 1), (-1, -1), text_color),
                                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                    ('GRID', (0, 0), (-1, -1), 0.5, light_gray_color),
                                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.white]),
                                    ('LEFTPADDING', (0, 0), (-1, -1), 3),
                                    ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                                    ('TOPPADDING', (0, 0), (-1, -1), 3),
                                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                                ] + ([('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                                      ('FONTSIZE', (0, 1), (0, -1), 7),
                                      ('ALIGN', (0, 1), (0, -1), 'LEFT')] if is_transposed and row_names else [])))

                                # Draw table
                                table_width, table_height_actual = table.wrap(available_width, height)
                                table.drawOn(c, 2*cm, y - table_height_actual)
                                y -= (table_height_actual + 0.5*cm)

                    else:
                        # Render table normally (fits on current page orientation)
                        # Calculate space needed
                        rows_to_show = min(3, len(row_names)) if row_names else 3
                        table_height = (rows_to_show + 1) * 0.6*cm  # +1 for header

                        # Check if we need a new page
                        if y < (table_height + 3*cm):
                            c.showPage()
                            if current_page_orientation == 'landscape':
                                c.setPageSize(landscape(A4))
                            else:
                                c.setPageSize(A4)
                            y = height - 2*cm

                        # Table title
                        c.setFont("Helvetica-Bold", 9)
                        c.setFillColor(primary_color)
                        c.drawString(2.5*cm, y, f"• {field_label}")
                        y -= 0.6*cm

                        if column_names:
                            # Create paragraph style for wrapping headers
                            header_style = ParagraphStyle(
                                'TableHeader',
                                fontName='Helvetica-Bold',
                                fontSize=7,
                                leading=8,
                                alignment=1  # Center
                            )

                            # Get row_fields to determine column types (already fetched earlier)
                            # row_fields = schema_field.get('row_fields', [])

                            # Prepare table data
                            if is_transposed and row_names:
                                # Transposed table: rows are attributes, columns are entries
                                # Show ALL columns (not limited)
                                header_paragraphs = [''] + [Paragraph(col, header_style) for col in column_names]
                                table_data = [header_paragraphs]

                                # Data rows: row name + empty cells
                                for row_name in row_names[:8]:  # Show first 8 rows
                                    row = [row_name] + [''] * len(column_names)
                                    table_data.append(row)

                            else:
                                # Regular table: columns are fields, rows are entries
                                # Show ALL columns (not limited)
                                header_paragraphs = [Paragraph(col, header_style) for col in column_names]
                                table_data = [header_paragraphs]

                                # Add 3 empty rows
                                for i in range(3):
                                    table_data.append([''] * len(column_names))

                            # Calculate column widths based on field types
                            # Less indentation for tables: 2cm left + 2cm right = width - 4cm
                            available_width = width - 4*cm
                            col_widths = []

                            # Map column names to field types
                            col_types = {}
                            for f in row_fields:
                                field_label_temp = f.get('label', '')
                                field_type_temp = f.get('type', 'string')
                                col_types[field_label_temp] = field_type_temp

                            # Determine width for each column
                            for i, col_name in enumerate(column_names if not is_transposed else [''] + column_names):
                                if i == 0 and is_transposed:
                                    # First column in transposed table (row labels)
                                    col_widths.append(2.2*cm)
                                elif col_types.get(col_name) == 'boolean':
                                    # Boolean columns: narrow
                                    col_widths.append(1.0*cm)
                                elif col_types.get(col_name) == 'number' or 'No.' in col_name or 'Year' in col_name:
                                    # Number columns: medium
                                    col_widths.append(1.3*cm)
                                elif 'Date' in col_name:
                                    # Date columns: medium
                                    col_widths.append(1.8*cm)
                                else:
                                    # Text columns: flexible (share remaining space)
                                    col_widths.append(None)  # Will calculate after

                            # Calculate remaining space for text columns
                            fixed_width = sum(w for w in col_widths if w is not None)
                            text_cols = sum(1 for w in col_widths if w is None)
                            if text_cols > 0:
                                remaining = available_width - fixed_width
                                text_col_width = max(1.8*cm, remaining / text_cols)
                                col_widths = [w if w is not None else text_col_width for w in col_widths]

                            # Check if total width exceeds available space and scale down if needed
                            total_width = sum(col_widths)
                            if total_width > available_width:
                                scale_factor = available_width / total_width
                                col_widths = [w * scale_factor for w in col_widths]
                                print(f"   ⚠️  Table '{field_name}' scaled down by {scale_factor:.2f}x to fit page")

                            # Create and style table with dynamic row heights
                            row_heights = [None] * len(table_data)
                            row_heights[0] = 0.8*cm  # Taller header row for wrapped text

                            table = Table(table_data, colWidths=col_widths, rowHeights=row_heights)
                            table.setStyle(TableStyle([
                                # Header styling - Brand primary color with white text
                                ('BACKGROUND', (0, 0), (-1, 0), primary_color),
                                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                ('FONTSIZE', (0, 0), (-1, 0), 7),
                                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),  # Center headers
                                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),   # Left-align data
                                ('TEXTCOLOR', (0, 1), (-1, -1), text_color),
                                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                ('GRID', (0, 0), (-1, -1), 0.5, light_gray_color),
                                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.white]),
                                # Padding
                                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                                ('TOPPADDING', (0, 0), (-1, -1), 3),
                                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                                # First column bold for transposed tables
                            ] + ([('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                                  ('FONTSIZE', (0, 1), (0, -1), 7),
                                  ('ALIGN', (0, 1), (0, -1), 'LEFT')] if is_transposed and row_names else [])))

                            # Draw table with less indentation (2cm left margin)
                            table_width, table_height_actual = table.wrap(available_width, height)
                            table.drawOn(c, 2*cm, y - table_height_actual)
                            y -= (table_height_actual + 0.5*cm)

                        else:
                            # Fallback if no column names
                            c.setFont("Helvetica-Oblique", 8)
                            c.setFillColor(light_gray_color)
                            c.drawString(3*cm, y, "  (Table structure not extracted)")
                            y -= 0.5*cm

                else:
                    # Regular field - render with empty value
                    if y < 2*cm:
                        c.showPage()
                        # Set page size based on current orientation
                        if current_page_orientation == 'landscape':
                            c.setPageSize(landscape(A4))
                        else:
                            c.setPageSize(A4)
                        y = height - 2*cm

                    field_label = field.get('label', field_name)
                    c.setFont("Helvetica", 9)
                    c.setFillColor(text_color)
                    c.drawString(2.5*cm, y, f"• {field_label}: _____________")
                    y -= 0.5*cm

            y -= 0.5*cm  # Space between sections

            # After section completes, if we were in landscape, return to portrait
            if current_page_orientation == 'landscape':
                c.showPage()
                c.setPageSize(A4)
                current_page_orientation = 'portrait'
                width, height = A4
                y = height - 2*cm
                print(f"   📄 Returned to portrait after section '{section_title}'")

        # Footer
        c.setFont("Helvetica", 8)
        c.setFillColor(light_gray_color)
        c.drawString(2*cm, 1.5*cm, "PDF Layout Preview - Fields shown with empty values")
        c.drawRightString(width - 2*cm, 1.5*cm, "Generated by Aneya")

        # Save PDF
        c.save()
        buffer.seek(0)

        # Return as downloadable file
        filename = f"{request.form_name}_preview.pdf"
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename={filename}"
            }
        )

    except Exception as e:
        print(f"❌ Error generating PDF preview: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF preview: {str(e)}")


@router.get("/forms/{form_id}/preview-pdf")
async def preview_saved_form_pdf(
    form_id: str,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Generate PDF preview for a saved custom form.

    Args:
        form_id: UUID of the custom form
        authorization: Firebase JWT token in Authorization header

    Returns:
        PDF file as downloadable response
    """
    from fastapi.responses import StreamingResponse
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import cm

    try:
        # Verify Firebase authentication
        user_id = verify_firebase_token_and_get_user_id(authorization)

        # Fetch form from database
        from supabase import create_client, Client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        response = supabase.table("custom_forms").select("*").eq("id", form_id).execute()

        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Form not found")

        form = response.data[0]

        # Verify user owns this form
        if form['created_by'] != user_id:
            raise HTTPException(status_code=403, detail="You don't have permission to preview this form")

        # Extract schema and pdf_template
        form_name = form['form_name']
        form_schema = form['form_schema']
        pdf_template = form['pdf_template']

        if not pdf_template:
            raise HTTPException(status_code=400, detail="This form does not have a PDF template")

        # Use the existing preview_pdf logic
        preview_request = PreviewPDFRequest(
            form_name=form_name,
            form_schema=form_schema,
            pdf_template=pdf_template
        )

        # Call the preview_pdf function
        return await preview_pdf(preview_request)

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating saved form PDF preview: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF preview: {str(e)}")


@router.get("/forms/{form_id}", response_model=CustomFormResponse)
async def get_custom_form(
    form_id: str,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Get a single custom form with full details (schema and PDF template).

    Args:
        form_id: UUID of the custom form
        authorization: Firebase JWT token in Authorization header

    Returns:
        Complete form details
    """
    try:
        # Verify Firebase authentication
        user_id = verify_firebase_token_and_get_user_id(authorization)

        # Connect to Supabase
        from supabase import create_client, Client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Fetch form
        response = supabase.table("custom_forms").select("*").eq("id", form_id).execute()

        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Form not found")

        form = response.data[0]

        # Verify user owns this form
        if form['created_by'] != user_id:
            raise HTTPException(status_code=403, detail="You don't have permission to view this form")

        return CustomFormResponse(
            id=form['id'],
            form_name=form['form_name'],
            specialty=form['specialty'],
            description=form.get('description'),
            patient_criteria=form.get('patient_criteria'),
            created_by=form['created_by'],
            is_public=form['is_public'],
            status=form['status'],
            version=form['version'],
            field_count=form['field_count'] or 0,
            section_count=form['section_count'] or 0,
            created_at=form['created_at'],
            updated_at=form['updated_at'],
            form_schema=form.get('form_schema'),
            pdf_template=form.get('pdf_template')
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting custom form: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/forms/{form_id}")
async def delete_custom_form(
    form_id: str,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Delete a custom form.

    Args:
        form_id: UUID of the custom form to delete
        authorization: Firebase JWT token in Authorization header

    Returns:
        Success message
    """
    try:
        # Verify Firebase authentication
        user_id = verify_firebase_token_and_get_user_id(authorization)

        # Connect to Supabase
        from supabase import create_client, Client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Check if form exists and user owns it
        form_response = supabase.table("custom_forms").select("*").eq("id", form_id).execute()

        if not form_response.data or len(form_response.data) == 0:
            raise HTTPException(status_code=404, detail="Form not found")

        form = form_response.data[0]

        if form['created_by'] != user_id:
            raise HTTPException(status_code=403, detail="You don't have permission to delete this form")

        # Delete the form
        supabase.table("custom_forms").delete().eq("id", form_id).execute()

        return {"success": True, "message": "Form deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting custom form: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/forms/{form_id}")
async def update_custom_form(
    form_id: str,
    request: SaveFormRequest,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Update an existing custom form's schema and PDF template.

    Args:
        form_id: UUID of the custom form to update
        request: Updated form data (schema, pdf_template, etc.)
        authorization: Firebase JWT token in Authorization header

    Returns:
        Updated form details
    """
    try:
        # Verify Firebase authentication
        user_id = verify_firebase_token_and_get_user_id(authorization)

        # Connect to Supabase
        from supabase import create_client, Client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Check if form exists and user owns it
        form_response = supabase.table("custom_forms").select("*").eq("id", form_id).execute()

        if not form_response.data or len(form_response.data) == 0:
            raise HTTPException(status_code=404, detail="Form not found")

        form = form_response.data[0]

        if form['created_by'] != user_id:
            raise HTTPException(status_code=403, detail="You don't have permission to edit this form")

        # Calculate metadata from schema
        field_count = 0
        section_count = 0

        if isinstance(request.form_schema, dict):
            section_count = len(request.form_schema)
            for section_data in request.form_schema.values():
                if isinstance(section_data, dict) and 'fields' in section_data:
                    field_count += len(section_data.get('fields', []))
        elif isinstance(request.form_schema, list):
            section_count = len(request.form_schema)
            for section in request.form_schema:
                if isinstance(section, dict) and 'fields' in section:
                    field_count += len(section.get('fields', []))

        # Update form data
        update_data = {
            "form_name": request.form_name,
            "specialty": request.specialty,
            "form_schema": request.form_schema,
            "pdf_template": request.pdf_template,
            "description": request.description,
            "patient_criteria": request.patient_criteria,
            "field_count": field_count,
            "section_count": section_count,
            "is_public": request.is_public
        }

        response = supabase.table("custom_forms").update(update_data).eq("id", form_id).execute()

        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to update form")

        updated_form = response.data[0]

        return CustomFormResponse(
            id=updated_form['id'],
            form_name=updated_form['form_name'],
            specialty=updated_form['specialty'],
            description=updated_form.get('description'),
            patient_criteria=updated_form.get('patient_criteria'),
            created_by=updated_form['created_by'],
            is_public=updated_form['is_public'],
            status=updated_form['status'],
            version=updated_form['version'],
            field_count=updated_form['field_count'] or 0,
            section_count=updated_form['section_count'] or 0,
            created_at=updated_form['created_at'],
            updated_at=updated_form['updated_at']
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating custom form: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/forms/{form_id}/share")
async def share_custom_form(
    form_id: str,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Make a custom form public so all doctors can use it.

    Args:
        form_id: UUID of the custom form to share
        authorization: Firebase JWT token in Authorization header

    Returns:
        Updated form details
    """
    try:
        # Verify Firebase authentication
        user_id = verify_firebase_token_and_get_user_id(authorization)

        # Connect to Supabase
        from supabase import create_client, Client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Check if form exists and user owns it
        form_response = supabase.table("custom_forms").select("*").eq("id", form_id).execute()

        if not form_response.data or len(form_response.data) == 0:
            raise HTTPException(status_code=404, detail="Form not found")

        form = form_response.data[0]

        if form['created_by'] != user_id:
            raise HTTPException(status_code=403, detail="You don't have permission to share this form")

        # Update is_public to true
        response = supabase.table("custom_forms").update({"is_public": True}).eq("id", form_id).execute()

        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to update form")

        updated_form = response.data[0]

        return CustomFormResponse(
            id=updated_form['id'],
            form_name=updated_form['form_name'],
            specialty=updated_form['specialty'],
            description=updated_form.get('description'),
            patient_criteria=updated_form.get('patient_criteria'),
            created_by=updated_form['created_by'],
            is_public=updated_form['is_public'],
            status=updated_form['status'],
            version=updated_form['version'],
            field_count=updated_form['field_count'] or 0,
            section_count=updated_form['section_count'] or 0,
            created_at=updated_form['created_at'],
            updated_at=updated_form['updated_at']
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error sharing custom form: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-forms", response_model=List[CustomFormResponse])
async def get_my_custom_forms(
    specialty: Optional[str] = None,
    status: Optional[str] = None,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Get all custom forms created by the current user.

    Args:
        specialty: Optional filter by specialty
        status: Optional filter by status (draft, active, archived)
        authorization: Firebase JWT token in Authorization header

    Returns:
        List of custom forms
    """
    try:
        # Verify Firebase authentication and get user ID
        user_id = verify_firebase_token_and_get_user_id(authorization)

        from supabase import create_client, Client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Build query
        query = supabase.table("custom_forms").select("*").eq("created_by", user_id)

        if specialty:
            query = query.eq("specialty", specialty)

        if status:
            query = query.eq("status", status)

        response = query.order("created_at", desc=True).execute()

        return [
            CustomFormResponse(
                id=form['id'],
                form_name=form['form_name'],
                specialty=form['specialty'],
                description=form.get('description'),
                patient_criteria=form.get('patient_criteria') or f"General {form['specialty']} patients",
                created_by=form['created_by'],
                is_public=form['is_public'],
                status=form['status'],
                version=form['version'],
                field_count=form['field_count'] or 0,
                section_count=form['section_count'] or 0,
                created_at=form['created_at'],
                updated_at=form['updated_at']
            )
            for form in response.data
        ]

    except Exception as e:
        print(f"❌ Error getting custom forms: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/public-forms", response_model=List[CustomFormResponse])
async def get_public_custom_forms(specialty: Optional[str] = None):
    """
    Get all public custom forms available to use.

    Args:
        specialty: Optional filter by specialty

    Returns:
        List of public custom forms
    """
    try:
        from supabase import create_client, Client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        query = supabase.table("custom_forms").select("*").eq("is_public", True).eq("status", "active")

        if specialty:
            query = query.eq("specialty", specialty)

        response = query.order("created_at", desc=True).execute()

        return [
            CustomFormResponse(
                id=form['id'],
                form_name=form['form_name'],
                specialty=form['specialty'],
                description=form.get('description'),
                patient_criteria=form.get('patient_criteria') or f"General {form['specialty']} patients",
                created_by=form['created_by'],
                is_public=form['is_public'],
                status=form['status'],
                version=form['version'],
                field_count=form['field_count'] or 0,
                section_count=form['section_count'] or 0,
                created_at=form['created_at'],
                updated_at=form['updated_at']
            )
            for form in response.data
        ]

    except Exception as e:
        print(f"❌ Error getting public forms: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# REMOVED: Duplicate catch-all endpoint that was conflicting with specific routes
# The proper endpoint is at line 1402: @router.get("/forms/{form_id}", ...)


@router.patch("/{form_id}/activate")
async def activate_custom_form(form_id: str):
    """Activate a custom form to make it usable"""
    try:
        user_id = get_current_user_id()

        from supabase import create_client, Client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Verify ownership
        form_response = supabase.table("custom_forms").select("*").eq("id", form_id).execute()

        if not form_response.data:
            raise HTTPException(status_code=404, detail="Form not found")

        form = form_response.data[0]

        if form['created_by'] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Update status to active
        response = supabase.table("custom_forms").update({"status": "active"}).eq("id", form_id).execute()

        return {"message": "Form activated successfully", "form_id": form_id}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error activating form: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{form_id}")
async def delete_custom_form(form_id: str):
    """Delete a draft custom form"""
    try:
        user_id = get_current_user_id()

        from supabase import create_client, Client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Verify ownership and draft status
        form_response = supabase.table("custom_forms").select("*").eq("id", form_id).execute()

        if not form_response.data:
            raise HTTPException(status_code=404, detail="Form not found")

        form = form_response.data[0]

        if form['created_by'] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        if form['status'] != 'draft':
            raise HTTPException(status_code=400, detail="Only draft forms can be deleted")

        # Delete form
        supabase.table("custom_forms").delete().eq("id", form_id).execute()

        return {"message": "Form deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting form: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/default-forms/{specialty}", response_model=List[CustomFormResponse])
async def get_default_forms_for_specialty(specialty: str):
    """
    Get all built-in/default forms for a specific medical specialty.

    Args:
        specialty: Medical specialty (e.g., 'obstetrics_gynecology', 'cardiology')

    Returns:
        List of default forms for that specialty
    """
    try:
        # Map frontend specialty names to backend specialty keys
        specialty_mapping = {
            'obstetrics_gynecology': 'obstetrics_gynecology',
            'obgyn': 'obstetrics_gynecology',
            'cardiology': 'cardiology',
            'general': 'general'
        }

        backend_specialty = specialty_mapping.get(specialty.lower(), specialty.lower())

        # Query database for form schemas by specialty
        supabase = get_supabase_client()
        result = supabase.table('custom_forms')\
            .select('form_name, specialty, description, form_schema, version')\
            .eq('specialty', backend_specialty)\
            .eq('status', 'active')\
            .execute()

        if not result.data:
            return []  # Return empty list if no forms for this specialty

        # Build response with metadata about each form schema
        default_forms = []

        for form_data in result.data:
            form_schema = form_data['form_schema']
            form_type = form_data['form_name']

            # Count fields and sections
            field_count = 0
            section_count = len(form_schema)

            for section in form_schema.values():
                if isinstance(section, dict) and 'fields' in section:
                    field_count += len(section.get('fields', {}))

            default_forms.append(CustomFormResponse(
                id=f"default-{backend_specialty}-{form_type}",  # Synthetic ID for default forms
                form_name=form_type,
                specialty=backend_specialty,
                description=form_data.get('description', f"Built-in {form_type} form"),
                created_by="system",  # System-created
                is_public=True,
                status="active",
                version=form_data.get('version', 1),
                field_count=field_count,
                section_count=section_count,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            ))

        return default_forms

    except Exception as e:
        print(f"❌ Error getting default forms: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/filled-forms/{filled_form_id}/pdf")
async def download_filled_form_pdf(filled_form_id: str):
    """
    Generate and download PDF for a filled custom form using stored pdf_template.

    Args:
        filled_form_id: ID of the filled form record

    Returns:
        StreamingResponse with PDF file
    """
    try:
        user_id = get_current_user_id()

        # Import PDF generator
        from pdf_generator import generate_custom_form_pdf

        # Connect to Supabase
        from supabase import create_client, Client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Fetch filled form
        filled_form_response = supabase.table("filled_forms")\
            .select("*, custom_forms!inner(*)")\
            .eq("id", filled_form_id)\
            .execute()

        if not filled_form_response.data:
            raise HTTPException(status_code=404, detail="Filled form not found")

        filled_form = filled_form_response.data[0]
        custom_form = filled_form['custom_forms']

        # Verify user has access (either created the form or it's public)
        if filled_form['filled_by'] != user_id and not custom_form['is_public']:
            raise HTTPException(status_code=403, detail="Access denied to this form")

        # Get pdf_template
        pdf_template = custom_form.get('pdf_template')
        if not pdf_template:
            raise HTTPException(
                status_code=400,
                detail="This form does not have a PDF template. Please contact support."
            )

        # Get form data
        form_data = filled_form['form_data']

        # Fetch patient info if available
        patient = None
        patient_id = filled_form.get('patient_id')
        if patient_id:
            patient_response = supabase.table("patients")\
                .select("*")\
                .eq("id", patient_id)\
                .execute()

            if patient_response.data:
                patient = patient_response.data[0]

        # Fetch doctor info for logo/clinic name and color scheme
        doctor_info = None
        doctor_response = supabase.table("doctors")\
            .select("clinic_name, clinic_logo_url, primary_color, accent_color, text_color, light_gray_color")\
            .eq("user_id", user_id)\
            .execute()

        if doctor_response.data:
            doctor_info = doctor_response.data[0]

        # Generate PDF
        print(f"📄 Generating PDF for filled form: {filled_form_id}")
        pdf_buffer = generate_custom_form_pdf(
            form_data=form_data,
            pdf_template=pdf_template,
            form_name=custom_form['form_name'],
            specialty=custom_form['specialty'],
            patient=patient,
            doctor_info=doctor_info
        )

        # Create filename
        form_name_safe = custom_form['form_name'].replace(' ', '_').replace('/', '_')
        patient_name = patient['name'].replace(' ', '_').replace('/', '_') if patient else 'patient'
        filename = f"{form_name_safe}_{patient_name}_{filled_form_id[:8]}.pdf"

        print(f"✅ PDF generated successfully: {filename}")

        # Return as streaming response
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


@router.post("/select-form-for-consultation")
async def select_form_for_consultation(
    specialty: str = Form(...),
    patient_context: str = Form(...),
    authorization: str = Header(..., description="Bearer token")
):
    """
    Smart form selection for consultations.

    Logic:
    - If only 1 form available for specialty → return it immediately (no LLM call)
    - If multiple forms available → call LLM with patient_criteria to decide which form to use

    Args:
        specialty: Doctor's specialty
        patient_context: Brief description of patient (age, gender, chief complaint, pregnancy status, etc.)
        authorization: Firebase JWT token

    Returns:
        Selected form details with form_id and form_name
    """
    try:
        # Verify Firebase authentication
        user_id = verify_firebase_token_and_get_user_id(authorization)

        # Connect to Supabase
        from supabase import create_client, Client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        print(f"\n🔍 Selecting form for specialty: {specialty}")
        print(f"👤 Patient context: {patient_context[:100]}...")

        # Get all forms for this specialty (user's own + public forms)
        forms_query = supabase.table("custom_forms").select("*").eq("specialty", specialty).eq("status", "active")

        # Filter: created_by = user_id OR is_public = true
        forms_response = forms_query.execute()

        # Filter in Python (Supabase doesn't support OR in eq() easily)
        available_forms = [
            form for form in forms_response.data
            if form['created_by'] == user_id or form['is_public'] == True
        ]

        print(f"📋 Found {len(available_forms)} forms for {specialty}")

        if len(available_forms) == 0:
            raise HTTPException(status_code=404, detail=f"No forms available for specialty: {specialty}")

        # If only 1 form: return it immediately (no LLM call needed)
        if len(available_forms) == 1:
            selected_form = available_forms[0]
            print(f"✅ Only 1 form available, auto-selecting: {selected_form['form_name']}")

            return {
                "form_id": selected_form['id'],
                "form_name": selected_form['form_name'],
                "description": selected_form.get('description'),
                "patient_criteria": selected_form.get('patient_criteria'),
                "selection_method": "auto",
                "reason": "Only one form available for this specialty"
            }

        # Multiple forms: use LLM to decide
        print(f"🤖 Multiple forms available ({len(available_forms)}), calling LLM to decide...")

        # Build form options for LLM
        form_options = []
        for form in available_forms:
            form_options.append({
                "form_id": form['id'],
                "form_name": form['form_name'],
                "description": form.get('description', ''),
                "patient_criteria": form.get('patient_criteria', 'Not specified')
            })

        # Call LLM to decide which form to use
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        prompt = f"""You are a medical form selector. Given a patient context and multiple form options, select the most appropriate form.

**Patient Context:**
{patient_context}

**Available Forms:**
{chr(10).join([f"{i+1}. {opt['form_name']}\n   Description: {opt['description']}\n   Patient Criteria: {opt['patient_criteria']}" for i, opt in enumerate(form_options)])}

**Instructions:**
- Analyze the patient context
- Compare it against each form's patient_criteria
- Select the form that best matches the patient's demographics, condition, and care context
- Return ONLY the form_id of the selected form (nothing else)

**Response format:**
Return just the form_id (UUID string), no additional text.
"""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        selected_form_id = response.content[0].text.strip()

        # Find the selected form
        selected_form = next((f for f in available_forms if f['id'] == selected_form_id), None)

        if not selected_form:
            # Fallback: if LLM returned invalid ID, use first form
            print(f"⚠️ LLM returned invalid form_id: {selected_form_id}, using first form as fallback")
            selected_form = available_forms[0]

        print(f"✅ LLM selected form: {selected_form['form_name']}")

        return {
            "form_id": selected_form['id'],
            "form_name": selected_form['form_name'],
            "description": selected_form.get('description'),
            "patient_criteria": selected_form.get('patient_criteria'),
            "selection_method": "llm",
            "reason": "Selected by AI based on patient context and form criteria"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error selecting form: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# ADD TO api.py
# ============================================
"""
To integrate these endpoints into api.py, add before the `if __name__ == "__main__"` block:

# Import custom forms router
from custom_forms_api import router as custom_forms_router

# Include custom forms routes
app.include_router(custom_forms_router)
"""
