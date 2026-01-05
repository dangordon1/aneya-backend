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


@router.post("/preview-pdf")
async def preview_pdf(request: PreviewPDFRequest):
    """
    Generate a preview PDF based on the form schema and PDF template.
    Shows sample/dummy data for layout review before form is activated.

    Args:
        request: PreviewPDFRequest with form schema, PDF template, and optional branding

    Returns:
        StreamingResponse with PDF file for inline display
    """
    try:
        from fastapi.responses import StreamingResponse
        from pdf_generator import generate_custom_form_pdf, generate_sample_form_data

        print(f"\n📄 Generating preview PDF for form: {request.form_name}")

        # Generate sample/dummy data based on schema
        sample_data = generate_sample_form_data(
            form_schema=request.form_schema,
            pdf_template=request.pdf_template
        )
        print(f"✅ Generated sample data for {len(sample_data)} sections")

        # Prepare doctor info for header
        doctor_info = None
        if request.clinic_name or request.clinic_logo_url:
            doctor_info = {
                'clinic_name': request.clinic_name,
                'clinic_logo_url': request.clinic_logo_url
            }
            print(f"   Clinic: {request.clinic_name or 'No name'}")
            print(f"   Logo: {'Yes' if request.clinic_logo_url else 'No'}")

        # Generate PDF using shared function with sample data and custom colors
        pdf_buffer = generate_custom_form_pdf(
            form_data=sample_data,
            pdf_template=request.pdf_template,
            form_name=request.form_name,
            specialty="preview",
            patient=None,  # No patient info for preview
            doctor_info=doctor_info,
            form_schema=request.form_schema,
            # Pass custom colors
            primary_color=request.primary_color,
            accent_color=request.accent_color,
            text_color=request.text_color,
            light_gray_color=request.light_gray_color
        )

        print(f"✅ Preview PDF generated successfully")

        # Return as inline PDF for viewing
        filename = f"{request.form_name}_preview.pdf"
        return StreamingResponse(
            pdf_buffer,
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


@router.get("/my-forms")
async def get_my_forms_library(
    specialty: Optional[str] = None,
    status: Optional[str] = None,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Get doctor's complete form library (owned + adopted forms).
    This is the list of forms available for consultation selection.

    Auto-adopts public forms in doctor's specialty on first call (idempotent).

    Args:
        specialty: Optional filter by specialty
        status: Optional filter by status (draft, active, archived)
        authorization: Firebase JWT token in Authorization header

    Returns:
        Dict with forms (owned + adopted), counts, and ownership metadata
    """
    try:
        # Verify Firebase authentication and get user ID
        user_id = verify_firebase_token_and_get_user_id(authorization)

        from supabase import create_client, Client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Get doctor's specialty for auto-adoption
        doctor_result = supabase.table("doctors").select("specialty").eq("user_id", user_id).single().execute()
        doctor_specialty = doctor_result.data.get('specialty') if doctor_result.data else None

        # Auto-adopt public forms in doctor's specialty (idempotent - won't duplicate)
        if doctor_specialty:
            try:
                result = supabase.rpc('auto_adopt_forms_for_doctor', {
                    'p_doctor_id': user_id,
                    'p_specialty': doctor_specialty
                }).execute()
                forms_added = result.data if result.data else 0
                if forms_added > 0:
                    print(f"  ✓ Auto-adopted {forms_added} forms for specialty {doctor_specialty}")
            except Exception as e:
                print(f"  ⚠️  Auto-adoption warning: {e}")
                # Continue even if auto-adoption fails

        # Build query for owned forms
        owned_query = supabase.table("custom_forms").select("*").eq("created_by", user_id)

        if specialty:
            owned_query = owned_query.eq("specialty", specialty)
        if status:
            owned_query = owned_query.eq("status", status)

        owned_forms_response = owned_query.order("created_at", desc=True).execute()
        owned_forms = owned_forms_response.data or []

        # Add ownership metadata to owned forms
        for form in owned_forms:
            form['ownership_type'] = 'owned'
            form['auto_adopted'] = False

        # Build query for adopted forms with join to custom_forms
        adopted_query = supabase.table("doctor_adopted_forms")\
            .select("form_id, adopted_at, auto_adopted, custom_forms(*)")\
            .eq("doctor_id", user_id)

        adopted_result = adopted_query.execute()

        # Flatten adopted forms and add ownership metadata
        adopted_forms = []
        for adoption in (adopted_result.data or []):
            form = adoption.get('custom_forms')
            if form:
                form['ownership_type'] = 'adopted'
                form['adopted_at'] = adoption['adopted_at']
                form['auto_adopted'] = adoption['auto_adopted']

                # Apply filters
                if specialty and form.get('specialty') != specialty:
                    continue
                if status and form.get('status') != status:
                    continue

                adopted_forms.append(form)

        # Combine and sort
        all_forms = owned_forms + adopted_forms
        all_forms.sort(key=lambda x: x.get('form_name', ''))

        return {
            "success": True,
            "forms": all_forms,
            "total": len(all_forms),
            "owned_count": len(owned_forms),
            "adopted_count": len(adopted_forms)
        }

    except Exception as e:
        print(f"❌ Error getting forms library: {str(e)}")
        import traceback
        traceback.print_exc()
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


@router.get("/forms/browse")
async def browse_forms_to_add(
    specialty: Optional[str] = None,
    search: Optional[str] = None,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Browse all public forms that can be added to "My Forms".
    Excludes forms already in the doctor's library (owned or adopted).

    Args:
        specialty: Optional filter by specialty
        search: Optional search in form name or description
        authorization: Firebase JWT token in Authorization header

    Returns:
        Dict with available forms to add
    """
    try:
        # Verify Firebase authentication and get user ID
        user_id = verify_firebase_token_and_get_user_id(authorization)

        from supabase import create_client, Client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Get all public active forms
        query = supabase.table("custom_forms")\
            .select("*")\
            .eq("is_public", True)\
            .eq("status", "active")

        if specialty:
            query = query.eq("specialty", specialty)

        all_public = query.execute()
        all_public_forms = all_public.data or []

        # Get forms already in doctor's library (owned + adopted)
        owned = supabase.table("custom_forms")\
            .select("id")\
            .eq("created_by", user_id)\
            .execute()

        adopted = supabase.table("doctor_adopted_forms")\
            .select("form_id")\
            .eq("doctor_id", user_id)\
            .execute()

        library_form_ids = set(
            [f['id'] for f in (owned.data or [])] +
            [a['form_id'] for a in (adopted.data or [])]
        )

        # Filter out forms already in library
        available_forms = [
            form for form in all_public_forms
            if form['id'] not in library_form_ids
        ]

        # Optional search filter
        if search:
            search_lower = search.lower()
            available_forms = [
                form for form in available_forms
                if search_lower in form.get('form_name', '').lower()
                or search_lower in (form.get('description') or '').lower()
            ]

        return {
            "success": True,
            "forms": available_forms,
            "total": len(available_forms)
        }

    except Exception as e:
        print(f"❌ Error browsing forms: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forms/{form_id}/adopt")
async def adopt_form_to_library(
    form_id: str,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Add a public form to the doctor's "My Forms" library.

    Args:
        form_id: UUID of the form to adopt
        authorization: Firebase JWT token in Authorization header

    Returns:
        Success message with form details
    """
    try:
        # Verify Firebase authentication and get user ID
        user_id = verify_firebase_token_and_get_user_id(authorization)

        from supabase import create_client, Client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Verify form exists and is public
        form_result = supabase.table("custom_forms")\
            .select("id, form_name, is_public, created_by, status")\
            .eq("id", form_id)\
            .single()\
            .execute()

        if not form_result.data:
            raise HTTPException(status_code=404, detail="Form not found")

        form = form_result.data

        if not form.get('is_public'):
            raise HTTPException(status_code=403, detail="Can only adopt public forms")

        if form.get('created_by') == user_id:
            raise HTTPException(status_code=400, detail="Cannot adopt your own form (it's already in your library)")

        if form.get('status') != 'active':
            raise HTTPException(status_code=400, detail="Can only adopt active forms")

        # Check if already adopted
        existing = supabase.table("doctor_adopted_forms")\
            .select("id")\
            .eq("doctor_id", user_id)\
            .eq("form_id", form_id)\
            .execute()

        if existing.data:
            return {
                "success": True,
                "message": "Form already in your library",
                "form_id": form_id,
                "form_name": form['form_name']
            }

        # Adopt the form
        supabase.table("doctor_adopted_forms").insert({
            "doctor_id": user_id,
            "form_id": form_id,
            "auto_adopted": False
        }).execute()

        print(f"✓ Doctor {user_id} adopted form '{form['form_name']}'")

        return {
            "success": True,
            "message": f"Added '{form['form_name']}' to your library",
            "form_id": form_id,
            "form_name": form['form_name']
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error adopting form: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/forms/{form_id}/remove")
async def remove_form_from_library(
    form_id: str,
    authorization: str = Header(..., description="Bearer token")
):
    """
    Remove an adopted form from the doctor's library.
    Cannot remove forms you created (use DELETE /forms/{id} instead).

    Args:
        form_id: UUID of the form to remove
        authorization: Firebase JWT token in Authorization header

    Returns:
        Success message
    """
    try:
        # Verify Firebase authentication and get user ID
        user_id = verify_firebase_token_and_get_user_id(authorization)

        from supabase import create_client, Client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Check if this is an owned form
        owned_result = supabase.table("custom_forms")\
            .select("id, form_name")\
            .eq("id", form_id)\
            .eq("created_by", user_id)\
            .execute()

        if owned_result.data:
            raise HTTPException(
                status_code=400,
                detail="Cannot remove owned forms. Use DELETE /forms/{id} to delete forms you created."
            )

        # Remove adoption record
        delete_result = supabase.table("doctor_adopted_forms")\
            .delete()\
            .eq("doctor_id", user_id)\
            .eq("form_id", form_id)\
            .execute()

        if not delete_result.data:
            raise HTTPException(
                status_code=404,
                detail="Form not found in your library"
            )

        print(f"✓ Doctor {user_id} removed form {form_id} from library")

        return {
            "success": True,
            "message": "Form removed from your library",
            "form_id": form_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error removing form from library: {str(e)}")
        import traceback
        traceback.print_exc()
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

        # Get forms in doctor's library (owned + adopted)
        # This ensures only forms in "My Forms" are considered for consultation selection

        # Get owned forms
        owned_forms_query = supabase.table("custom_forms")\
            .select("*")\
            .eq("created_by", user_id)\
            .eq("specialty", specialty)\
            .eq("status", "active")

        owned_forms_response = owned_forms_query.execute()
        owned_forms = owned_forms_response.data or []

        # Get adopted forms with join to custom_forms
        adopted_forms_query = supabase.table("doctor_adopted_forms")\
            .select("form_id, custom_forms(*)")\
            .eq("doctor_id", user_id)

        adopted_result = adopted_forms_query.execute()

        # Flatten adopted forms and filter by specialty
        adopted_forms = []
        for adoption in (adopted_result.data or []):
            form = adoption.get('custom_forms')
            if form and form.get('specialty') == specialty and form.get('status') == 'active':
                adopted_forms.append(form)

        # Combine owned + adopted forms
        available_forms = owned_forms + adopted_forms

        print(f"📋 Found {len(available_forms)} forms in library for {specialty} ({len(owned_forms)} owned, {len(adopted_forms)} adopted)")

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
