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

@router.post("/upload", response_model=FormConversionStatusResponse)
async def upload_custom_form(
    form_name: str = Form(...),
    specialty: str = Form(...),
    description: Optional[str] = Form(None),
    is_public: bool = Form(False),
    files: List[UploadFile] = File(...)
):
    """
    Upload form images and convert to custom form schema.

    Args:
        form_name: Name for the form in snake_case
        specialty: Medical specialty (e.g., 'cardiology', 'neurology')
        description: Optional description of the form
        is_public: Whether to make form available to all doctors
        files: List of HEIC/JPEG/PNG image files

    Returns:
        Conversion status with form ID if successful
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
            return FormConversionStatusResponse(
                success=False,
                form_name=form_name,
                specialty=specialty,
                error=result.error
            )

        # Store in database
        from supabase import create_client, Client

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase: Client = create_client(supabase_url, supabase_key)

        # Insert into custom_forms table
        form_data = {
            "form_name": form_name,
            "specialty": specialty,
            "created_by": user_id,
            "is_public": is_public,
            "form_schema": result.schema,
            "schema_code": result.schema_code,
            "migration_sql": result.migration_sql,
            "typescript_types": result.typescript_types,
            "description": description,
            "field_count": result.metadata.get('total_fields', 0),
            "section_count": len(result.schema),
            "image_count": result.metadata.get('image_count', len(files)),
            "status": "draft"
        }

        response = supabase.table("custom_forms").insert(form_data).execute()

        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to save form to database")

        form_record = response.data[0]

        return FormConversionStatusResponse(
            success=True,
            form_id=form_record['id'],
            form_name=form_name,
            specialty=specialty,
            field_count=form_data['field_count'],
            section_count=form_data['section_count']
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error uploading custom form: {str(e)}")
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
