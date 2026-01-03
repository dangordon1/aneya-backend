"""
Custom Forms API Endpoints

API endpoints for doctors to upload and manage custom forms.
Add these endpoints to api.py before the `if __name__ == "__main__"` block.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
import os
from datetime import datetime

from tools.form_converter.api import FormConverterAPI
from api import get_supabase_client

# Create router
router = APIRouter(prefix="/api/custom-forms", tags=["custom-forms"])


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
    schema: Dict[str, Any]  # Extracted form schema (sections + fields)
    pdf_template: Dict[str, Any]  # Extracted PDF layout
    metadata: Dict[str, Any]  # Field counts, image count, etc.
    error: Optional[str] = None


class SaveFormRequest(BaseModel):
    """Request body for saving reviewed form"""
    form_name: str
    specialty: str
    schema: Dict[str, Any]
    pdf_template: Dict[str, Any]
    description: Optional[str] = None
    is_public: bool = False


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_current_user_id() -> Optional[str]:
    """Get current authenticated user ID from token"""
    # TODO: Implement actual authentication
    # For now, return None to allow unauthenticated access for testing
    return None  # Replace with actual auth when authentication is implemented


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

        for file in files:
            content = await file.read()
            uploaded_bytes.append(content)
            filenames.append(file.filename)

            # Validate file size (max 10MB per file)
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} exceeds 10MB limit"
                )

        # Convert form
        result = converter.convert_from_uploaded_files(
            uploaded_files=uploaded_bytes,
            filenames=filenames,
            form_name=form_name,
            specialty=specialty,
            generate_migration=True,
            generate_typescript=True
        )

        if not result.success:
            return FormExtractionResponse(
                success=False,
                form_name=form_name,
                specialty=specialty,
                schema={},
                pdf_template={},
                metadata={},
                error=result.error
            )

        # CHANGED: Return extraction results for review (don't save to DB yet)
        return FormExtractionResponse(
            success=True,
            form_name=form_name,
            specialty=specialty,
            schema=result.schema,
            pdf_template=result.pdf_template,
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
async def save_custom_form(request: SaveFormRequest):
    """
    Save doctor-reviewed form schema + PDF template to database.
    Called AFTER doctor has reviewed and edited the extracted schema.

    Args:
        request: SaveFormRequest with reviewed schema and PDF template

    Returns:
        CustomFormResponse with saved form details
    """
    try:
        user_id = get_current_user_id()

        # Validate form name
        converter = FormConverterAPI()
        valid_name, name_error = converter.validate_form_name(request.form_name)
        if not valid_name:
            raise HTTPException(status_code=400, detail=f"Invalid form name: {name_error}")

        valid_specialty, specialty_error = converter.validate_specialty(request.specialty)
        if not valid_specialty:
            raise HTTPException(status_code=400, detail=f"Invalid specialty: {specialty_error}")

        # Calculate metadata from schema
        field_count = 0
        section_count = 0

        # Handle both dict (new format) and list (fallback) schema structures
        if isinstance(request.schema, dict):
            section_count = len(request.schema)
            for section_data in request.schema.values():
                if isinstance(section_data, dict) and 'fields' in section_data:
                    field_count += len(section_data.get('fields', []))
        elif isinstance(request.schema, list):
            section_count = len(request.schema)
            for section in request.schema:
                if isinstance(section, dict) and 'fields' in section:
                    field_count += len(section.get('fields', []))

        # Connect to Supabase
        from supabase import create_client, Client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Insert into custom_forms table
        form_data = {
            "form_name": request.form_name,
            "specialty": request.specialty,
            "created_by": user_id,
            "is_public": request.is_public,
            "form_schema": request.schema,
            "pdf_template": request.pdf_template,  # Save PDF template
            "description": request.description,
            "field_count": field_count,
            "section_count": section_count,
            "status": "draft"  # Starts as draft
        }

        response = supabase.table("custom_forms").insert(form_data).execute()

        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to save form to database")

        form_record = response.data[0]

        # Return saved form details
        return CustomFormResponse(
            id=form_record['id'],
            form_name=form_record['form_name'],
            specialty=form_record['specialty'],
            description=form_record.get('description'),
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


@router.get("/my-forms", response_model=List[CustomFormResponse])
async def get_my_custom_forms(
    specialty: Optional[str] = None,
    status: Optional[str] = None
):
    """
    Get all custom forms created by the current user.

    Args:
        specialty: Optional filter by specialty
        status: Optional filter by status (draft, active, archived)

    Returns:
        List of custom forms
    """
    try:
        user_id = get_current_user_id()

        # If no user authenticated, return empty list
        if not user_id:
            return []

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


@router.get("/{form_id}")
async def get_custom_form(form_id: str):
    """Get detailed information about a specific custom form"""
    try:
        user_id = get_current_user_id()

        from supabase import create_client, Client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        response = supabase.table("custom_forms").select("*").eq("id", form_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="Form not found")

        form = response.data[0]

        # Check permissions (owner or public form)
        if form['created_by'] != user_id and not form['is_public']:
            raise HTTPException(status_code=403, detail="Access denied")

        return form

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting custom form: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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
        result = supabase.table('form_schemas')\
            .select('form_type, specialty, description, schema_definition, version')\
            .eq('specialty', backend_specialty)\
            .eq('is_active', True)\
            .execute()

        if not result.data:
            return []  # Return empty list if no forms for this specialty

        # Build response with metadata about each form schema
        default_forms = []

        for form_data in result.data:
            form_schema = form_data['schema_definition']
            form_type = form_data['form_type']

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

        # Fetch doctor info for logo/clinic name
        doctor_info = None
        doctor_response = supabase.table("doctor_profiles")\
            .select("clinic_name, clinic_logo_url")\
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
