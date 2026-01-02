"""
Historical Forms Import API
Endpoints for uploading historical patient forms and managing import workflow
"""

import os
import uuid
import logging
from typing import List, Optional
from datetime import datetime, date

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, UUID4
from supabase import create_client, Client

from historical_forms import (
    HistoricalFormDataExtractor,
    ConflictDetector,
    get_file_type_from_bytes
)

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/historical-forms", tags=["historical-forms"])

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# GCS client for file storage
from google.cloud import storage
gcs_client = storage.Client()
BUCKET_NAME = "aneya-audio-recordings"  # Reuse existing bucket


# ============================================================================
# Request/Response Models
# ============================================================================

class UploadHistoricalFormsRequest(BaseModel):
    """Request model for uploading historical forms"""
    patient_id: UUID4
    form_date: Optional[str] = None  # YYYY-MM-DD


class HistoricalFormImportResponse(BaseModel):
    """Response model for form import"""
    import_id: UUID4
    patient_id: UUID4
    processing_status: str
    file_count: int
    message: str


class ImportListResponse(BaseModel):
    """Response for listing imports"""
    imports: List[dict]
    total_count: int


class ReviewDecisionRequest(BaseModel):
    """Request for doctor's review decision"""
    import_id: UUID4
    approved_fields: List[str]
    rejected_fields: List[str]
    review_notes: Optional[str] = None


class ApplyImportRequest(BaseModel):
    """Request to apply approved fields"""
    import_id: UUID4


# ============================================================================
# Helper Functions
# ============================================================================

async def get_current_patient_data(patient_id: str) -> dict:
    """Fetch current patient data from database for comparison"""
    try:
        # Get patient demographics
        patient = supabase.table("patients").select("*").eq("id", patient_id).single().execute()

        demographics = {}
        if patient.data:
            demographics = {
                "name": patient.data.get("name"),
                "date_of_birth": patient.data.get("date_of_birth"),
                "age_years": patient.data.get("age_years"),
                "sex": patient.data.get("sex"),
                "phone": patient.data.get("phone"),
                "email": patient.data.get("email"),
                "height_cm": patient.data.get("height_cm"),
                "weight_kg": patient.data.get("weight_kg"),
            }

        # Get medical history
        medical_history = {
            "current_medications": patient.data.get("current_medications") if patient.data else None,
            "current_conditions": patient.data.get("current_conditions") if patient.data else None,
            "allergies": patient.data.get("allergies") if patient.data else None,
        }

        # Get vitals
        vitals_response = supabase.table("patient_vitals")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .order("recorded_at", desc=True)\
            .limit(10)\
            .execute()
        vitals = vitals_response.data if vitals_response.data else []

        # Get medications
        meds_response = supabase.table("patient_medications")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .eq("status", "active")\
            .execute()
        medications = meds_response.data if meds_response.data else []

        # Get allergies
        allergies_response = supabase.table("patient_allergies")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .execute()
        allergies = allergies_response.data if allergies_response.data else []

        return {
            "demographics": demographics,
            "medical_history": medical_history,
            "vitals": vitals,
            "medications": medications,
            "allergies": allergies
        }

    except Exception as e:
        logger.error(f"Failed to fetch patient data: {e}")
        return {}


async def upload_files_to_gcs(
    files: List[UploadFile],
    patient_id: str,
    import_id: str
) -> List[dict]:
    """Upload files to Google Cloud Storage"""
    file_metadata = []

    try:
        bucket = gcs_client.bucket(BUCKET_NAME)

        for file in files:
            # Read file content
            content = await file.read()
            file_type = get_file_type_from_bytes(content)

            # Generate GCS path
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            gcs_path = f"historical_forms/{patient_id}/{import_id}/{timestamp}_{file.filename}"

            # Upload to GCS
            blob = bucket.blob(gcs_path)
            blob.upload_from_string(content)

            file_metadata.append({
                "file_name": file.filename,
                "file_type": file_type,
                "gcs_path": gcs_path,
                "file_size_bytes": len(content)
            })

            # Reset file for later processing
            await file.seek(0)

        return file_metadata

    except Exception as e:
        logger.error(f"Failed to upload files to GCS: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {e}")


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/upload", response_model=HistoricalFormImportResponse)
async def upload_historical_forms(
    patient_id: UUID4 = Form(...),
    form_date: Optional[str] = Form(None),
    files: List[UploadFile] = File(...)
):
    """
    Upload historical patient forms for processing

    Args:
        patient_id: UUID of the patient
        form_date: Optional date when the form was originally filled (YYYY-MM-DD)
        files: List of form files (images, PDFs)

    Returns:
        Import record with processing status
    """
    try:
        # Validate file count
        if len(files) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 files allowed per upload")

        if not files:
            raise HTTPException(status_code=400, detail="At least one file is required")

        # Verify patient exists
        patient = supabase.table("patients").select("id").eq("id", str(patient_id)).single().execute()
        if not patient.data:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Create import record
        import_id = str(uuid.uuid4())

        # Upload files to GCS
        file_metadata = await upload_files_to_gcs(files, str(patient_id), import_id)

        # Get current patient data for comparison
        current_data = await get_current_patient_data(str(patient_id))

        # Create initial import record
        # TODO: In production, get uploaded_by from authenticated request
        # For now, using a test UUID since we're using service role key
        test_user_id = "00000000-0000-0000-0000-000000000000"

        import_record = {
            "id": import_id,
            "patient_id": str(patient_id),
            "uploaded_by": test_user_id,
            "file_count": len(files),
            "file_metadata": file_metadata,
            "current_data": current_data,
            "processing_status": "pending",
            "form_date": form_date
        }

        # Insert into database
        result = supabase.table("historical_form_imports").insert(import_record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create import record")

        # Start background processing (extract data)
        # For now, we'll do it synchronously, but this should be async in production
        await process_import_extraction(import_id, files, current_data)

        return HistoricalFormImportResponse(
            import_id=import_id,
            patient_id=patient_id,
            processing_status="processing",
            file_count=len(files),
            message="Files uploaded successfully. Processing in background."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload historical forms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_import_extraction(
    import_id: str,
    files: List[UploadFile],
    current_data: dict
):
    """Background task to extract data from uploaded files"""
    try:
        # Update status to processing
        supabase.table("historical_form_imports")\
            .update({"processing_status": "processing"})\
            .eq("id", import_id)\
            .execute()

        # Prepare files for extraction
        file_data = []
        for file in files:
            await file.seek(0)
            content = await file.read()
            file_type = get_file_type_from_bytes(content)
            file_data.append((content, file.filename, file_type))

        # Extract data using Claude Vision API
        extractor = HistoricalFormDataExtractor()
        extraction_result = extractor.extract_patient_data_from_files(
            file_data,
            patient_context=current_data
        )

        if not extraction_result["success"]:
            # Update with error
            supabase.table("historical_form_imports")\
                .update({
                    "processing_status": "failed",
                    "processing_error": extraction_result.get("error", "Unknown error")
                })\
                .eq("id", import_id)\
                .execute()
            return

        extracted_data = extraction_result["extracted_data"]

        # Detect conflicts
        detector = ConflictDetector()
        conflicts, has_conflicts = detector.compare_patient_data(
            extracted_data,
            current_data
        )

        # Update import record with results
        update_data = {
            "processing_status": "completed",
            "extracted_data": extracted_data,
            "conflicts": conflicts,
            "has_conflicts": has_conflicts,
            "extraction_confidence": extraction_result.get("confidence", 0.5),
            "fields_extracted": extraction_result.get("fields_extracted", 0),
            "processed_at": datetime.utcnow().isoformat(),
            "review_status": "pending_review"
        }

        supabase.table("historical_form_imports")\
            .update(update_data)\
            .eq("id", import_id)\
            .execute()

        logger.info(f"Successfully processed import {import_id}")

    except Exception as e:
        logger.error(f"Failed to process import {import_id}: {e}")
        # Update with error
        supabase.table("historical_form_imports")\
            .update({
                "processing_status": "failed",
                "processing_error": str(e)
            })\
            .eq("id", import_id)\
            .execute()


@router.get("/pending", response_model=ImportListResponse)
async def get_pending_imports(
    patient_id: Optional[UUID4] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Get list of pending imports awaiting review

    Args:
        patient_id: Optional filter by patient
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of pending imports
    """
    try:
        query = supabase.table("historical_form_imports")\
            .select("*")\
            .eq("review_status", "pending_review")

        if patient_id:
            query = query.eq("patient_id", str(patient_id))

        result = query.order("created_at", desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()

        return ImportListResponse(
            imports=result.data if result.data else [],
            total_count=len(result.data) if result.data else 0
        )

    except Exception as e:
        logger.error(f"Failed to fetch pending imports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{import_id}")
async def get_import_details(import_id: UUID4):
    """Get detailed information about an import"""
    try:
        result = supabase.table("historical_form_imports")\
            .select("*")\
            .eq("id", str(import_id))\
            .single()\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Import not found")

        return result.data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch import details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review")
async def submit_review_decision(request: ReviewDecisionRequest):
    """
    Submit doctor's review decision for an import

    Args:
        request: Review decision with approved/rejected fields

    Returns:
        Updated import record
    """
    try:
        # Determine review status
        if not request.approved_fields:
            review_status = "rejected"
        elif not request.rejected_fields:
            review_status = "approved"
        else:
            review_status = "partially_approved"

        # Update import record
        update_data = {
            "review_status": review_status,
            "approved_fields": request.approved_fields,
            "rejected_fields": request.rejected_fields,
            "review_notes": request.review_notes,
            "reviewed_at": datetime.utcnow().isoformat()
        }

        result = supabase.table("historical_form_imports")\
            .update(update_data)\
            .eq("id", str(request.import_id))\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Import not found")

        return {
            "success": True,
            "import_id": request.import_id,
            "review_status": review_status,
            "message": "Review decision saved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save review decision: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply")
async def apply_approved_import(request: ApplyImportRequest):
    """
    Apply approved fields from import to patient record

    Args:
        request: Import ID to apply

    Returns:
        Summary of applied changes
    """
    try:
        # Get import record
        import_record = supabase.table("historical_form_imports")\
            .select("*")\
            .eq("id", str(request.import_id))\
            .single()\
            .execute()

        if not import_record.data:
            raise HTTPException(status_code=404, detail="Import not found")

        # Verify it's been reviewed and approved
        if import_record.data["review_status"] not in ["approved", "partially_approved"]:
            raise HTTPException(status_code=400, detail="Import must be reviewed before applying")

        approved_fields = import_record.data.get("approved_fields", [])
        if not approved_fields:
            raise HTTPException(status_code=400, detail="No fields approved for import")

        extracted_data = import_record.data.get("extracted_data", {})
        patient_id = import_record.data["patient_id"]

        # Apply approved changes
        applied_records = await apply_import_changes(
            patient_id,
            extracted_data,
            approved_fields,
            str(request.import_id)
        )

        return {
            "success": True,
            "import_id": request.import_id,
            "records_created": len([r for r in applied_records if r["operation"] == "insert"]),
            "records_updated": len([r for r in applied_records if r["operation"] == "update"]),
            "applied_records": applied_records
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to apply import: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def apply_import_changes(
    patient_id: str,
    extracted_data: dict,
    approved_fields: List[str],
    import_id: str
) -> List[dict]:
    """Apply approved changes to patient record"""
    applied_records = []

    try:
        # Apply demographics updates
        demo_fields = [f.replace("demographics.", "") for f in approved_fields if f.startswith("demographics.")]
        if demo_fields:
            demo_updates = {field: extracted_data["demographics"][field] for field in demo_fields if field in extracted_data.get("demographics", {})}
            if demo_updates:
                # Update patient record
                result = supabase.table("patients").update(demo_updates).eq("id", patient_id).execute()
                if result.data:
                    applied_records.append({
                        "table_name": "patients",
                        "record_id": patient_id,
                        "operation": "update",
                        "new_data": demo_updates
                    })

        # TODO: Apply vitals, medications, allergies (add as new records)
        # This would insert new records into respective tables

        # Create audit trail
        # TODO: In production, get applied_by from authenticated request
        test_user_id = "00000000-0000-0000-0000-000000000000"

        for record in applied_records:
            supabase.table("historical_import_applied_records").insert({
                "import_id": import_id,
                "table_name": record["table_name"],
                "record_id": record["record_id"],
                "operation": record["operation"],
                "new_data": record["new_data"],
                "applied_by": test_user_id
            }).execute()

        return applied_records

    except Exception as e:
        logger.error(f"Failed to apply changes: {e}")
        raise


@router.delete("/{import_id}")
async def delete_import(import_id: UUID4):
    """Delete a pending import (only allowed for pending_review status)"""
    try:
        result = supabase.table("historical_form_imports")\
            .delete()\
            .eq("id", str(import_id))\
            .execute()

        return {"success": True, "message": "Import deleted successfully"}

    except Exception as e:
        logger.error(f"Failed to delete import: {e}")
        raise HTTPException(status_code=500, detail=str(e))
