"""
Doctor Logo API

Endpoints for uploading, managing, and deleting clinic logos for doctors.
Logos are stored in Google Cloud Storage and URLs are saved to the doctors table.
"""

from fastapi import APIRouter, UploadFile, File, Query, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from io import BytesIO
from PIL import Image
import os
import uuid

router = APIRouter()

# GCS configuration
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "aneya-audio-recordings")
LOGO_PATH_PREFIX = "clinic-logos"

# Image constraints
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
TARGET_WIDTH = 200
TARGET_HEIGHT = 80
ALLOWED_MIME_TYPES = ["image/png", "image/jpeg", "image/jpg"]


def verify_firebase_token_and_get_client(authorization: str):
    """
    Verify Firebase JWT token and return Supabase client with service key

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")

    Returns:
        tuple: (supabase_client, user_id from Firebase token)
    """
    from api import get_supabase_client
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

        # Get Supabase client with service key (bypasses RLS)
        supabase = get_supabase_client()

        return supabase, user_id

    except Exception as e:
        print(f"❌ Firebase token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")


class LogoUploadResponse(BaseModel):
    success: bool
    clinic_logo_url: Optional[str] = None
    message: str


class LogoDeleteResponse(BaseModel):
    success: bool
    message: str


class LogoCurrentResponse(BaseModel):
    clinic_logo_url: Optional[str] = None


def detect_file_type(file_bytes: bytes) -> str:
    """Detect file type from magic bytes"""
    if file_bytes[:2] == b'\xff\xd8':
        return 'jpeg'
    elif file_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    return 'unknown'


def validate_image_file(file: UploadFile, file_bytes: bytes) -> tuple[bool, str]:
    """
    Validate uploaded image file

    Returns:
        tuple: (is_valid, error_message)
    """
    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        return False, f"Invalid file type. Allowed: PNG, JPEG. Got: {file.content_type}"

    # Check file size
    if len(file_bytes) > MAX_FILE_SIZE:
        size_mb = len(file_bytes) / (1024 * 1024)
        return False, f"File size ({size_mb:.1f}MB) exceeds maximum allowed size (2MB)"

    # Detect actual file type from magic bytes
    detected_type = detect_file_type(file_bytes)
    if detected_type not in ['png', 'jpeg']:
        return False, f"Invalid image file. Detected type: {detected_type}"

    return True, ""


def process_logo_image(file_bytes: bytes, filename: str) -> tuple[bytes, str]:
    """
    Process logo image: resize and optimize

    Args:
        file_bytes: Raw file bytes
        filename: Original filename

    Returns:
        tuple: (processed_image_bytes, file_extension)
    """
    detected_type = detect_file_type(file_bytes)

    # Load image with PIL
    try:
        img = Image.open(BytesIO(file_bytes))

        # Convert to RGB if necessary (handles RGBA, P, etc.)
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGBA' if detected_type == 'png' else 'RGB')

        # Calculate scaling to fit within target dimensions
        img_width, img_height = img.size
        scale = min(TARGET_WIDTH / img_width, TARGET_HEIGHT / img_height)

        # Only resize if image is larger than target
        if scale < 1:
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"📐 Resized from {img_width}x{img_height} to {new_width}x{new_height}")

        # Save optimized image
        output = BytesIO()
        if detected_type == 'png':
            img.save(output, format='PNG', optimize=True, compress_level=6)
            ext = '.png'
        else:  # jpeg
            # Convert RGBA to RGB for JPEG
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            img.save(output, format='JPEG', quality=85, optimize=True)
            ext = '.jpg'

        output.seek(0)
        return output.read(), ext

    except Exception as e:
        raise ValueError(f"Failed to process image: {str(e)}")


async def upload_logo_to_supabase(supabase, doctor_id: str, image_bytes: bytes, ext: str) -> str:
    """
    Upload logo to Supabase Storage

    Args:
        supabase: Authenticated Supabase client
        doctor_id: Doctor's UUID
        image_bytes: Processed image bytes
        ext: File extension (.png or .jpg)

    Returns:
        str: Public URL of uploaded image
    """
    try:
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{doctor_id}/logo_{timestamp}_{unique_id}{ext}"

        print(f"📤 Uploading logo to Supabase Storage: {filename}")

        # Upload to Supabase Storage
        content_type = "image/png" if ext == '.png' else "image/jpeg"

        result = supabase.storage.from_('clinic-logos').upload(
            filename,
            image_bytes,
            file_options={"content-type": content_type}
        )

        # Get public URL
        public_url = supabase.storage.from_('clinic-logos').get_public_url(filename)

        print(f"✅ Logo uploaded: {public_url}")

        return public_url

    except Exception as e:
        raise Exception(f"Failed to upload to Supabase Storage: {str(e)}")


async def delete_logo_from_supabase(supabase, logo_url: str):
    """
    Delete logo from Supabase Storage

    Args:
        supabase: Authenticated Supabase client
        logo_url: Public URL of the logo to delete
    """
    try:
        # Extract filename from Supabase Storage URL
        # Format: https://{project}.supabase.co/storage/v1/object/public/clinic-logos/{path}
        if "/clinic-logos/" in logo_url:
            # Get the path after /clinic-logos/
            filename = logo_url.split("/clinic-logos/")[1]

            print(f"🗑️  Deleting logo from Supabase Storage: {filename}")

            # Delete from Supabase Storage
            result = supabase.storage.from_('clinic-logos').remove([filename])

            print(f"✅ Logo deleted: {filename}")
        else:
            print(f"⚠️  Invalid Supabase Storage URL format: {logo_url}")

    except Exception as e:
        print(f"❌ Failed to delete logo from Supabase Storage: {str(e)}")
        # Don't raise - allow DB update to proceed even if storage delete fails


@router.post("/api/doctor-logo/upload", response_model=LogoUploadResponse)
async def upload_clinic_logo(
    file: UploadFile = File(...),
    doctor_id: str = Query(..., description="Doctor's UUID"),
    authorization: str = Header(..., description="Bearer token")
):
    """
    Upload and process clinic logo for a doctor

    - Validates file type (PNG, JPEG) and size (max 2MB)
    - Resizes to fit within 200x80px
    - Uploads to Supabase Storage
    - Updates doctor record in Supabase
    - Deletes old logo if exists
    - Requires JWT authentication
    """
    try:
        # Read file
        file_bytes = await file.read()

        # Validate
        is_valid, error_msg = validate_image_file(file, file_bytes)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Verify Firebase token and get Supabase client
        supabase, user_id = verify_firebase_token_and_get_client(authorization)

        # Check if doctor exists and verify ownership
        doctor_result = supabase.table("doctors").select("clinic_logo_url, user_id").eq("id", doctor_id).execute()

        if not doctor_result.data:
            raise HTTPException(status_code=404, detail="Doctor not found")

        doctor_data = doctor_result.data[0]

        # Verify that the authenticated user owns this doctor record
        if doctor_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized: You can only upload logos for your own account")

        old_logo_url = doctor_data.get('clinic_logo_url')

        # Process image
        print(f"🖼️  Processing logo for doctor {doctor_id}")
        processed_bytes, ext = process_logo_image(file_bytes, file.filename or "logo")

        # Upload to Supabase Storage
        public_url = await upload_logo_to_supabase(supabase, doctor_id, processed_bytes, ext)

        # Update doctor record
        update_result = supabase.table("doctors").update({
            "clinic_logo_url": public_url,
            "updated_at": datetime.now().isoformat()
        }).eq("id", doctor_id).execute()

        if not update_result.data:
            raise HTTPException(status_code=500, detail="Failed to update doctor record")

        # Delete old logo from Supabase Storage (if exists)
        if old_logo_url:
            await delete_logo_from_supabase(supabase, old_logo_url)

        return LogoUploadResponse(
            success=True,
            clinic_logo_url=public_url,
            message="Logo uploaded successfully"
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Logo upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to upload logo: {str(e)}")


@router.delete("/api/doctor-logo/delete", response_model=LogoDeleteResponse)
async def delete_clinic_logo(
    doctor_id: str = Query(..., description="Doctor's UUID"),
    authorization: str = Header(..., description="Bearer token")
):
    """
    Delete clinic logo for a doctor

    - Deletes logo from Supabase Storage
    - Sets clinic_logo_url to NULL in Supabase
    - Requires JWT authentication
    """
    try:
        # Verify Firebase token and get Supabase client
        supabase, user_id = verify_firebase_token_and_get_client(authorization)

        # Get doctor and verify ownership
        doctor_result = supabase.table("doctors").select("clinic_logo_url, user_id").eq("id", doctor_id).execute()

        if not doctor_result.data:
            raise HTTPException(status_code=404, detail="Doctor not found")

        doctor_data = doctor_result.data[0]

        # Verify that the authenticated user owns this doctor record
        if doctor_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized: You can only delete logos for your own account")

        logo_url = doctor_data.get('clinic_logo_url')

        if not logo_url:
            return LogoDeleteResponse(
                success=True,
                message="No logo to delete"
            )

        # Delete from Supabase Storage
        await delete_logo_from_supabase(supabase, logo_url)

        # Update doctor record
        update_result = supabase.table("doctors").update({
            "clinic_logo_url": None,
            "updated_at": datetime.now().isoformat()
        }).eq("id", doctor_id).execute()

        if not update_result.data:
            raise HTTPException(status_code=500, detail="Failed to update doctor record")

        return LogoDeleteResponse(
            success=True,
            message="Logo deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Logo delete error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete logo: {str(e)}")


@router.get("/api/doctor-logo/current", response_model=LogoCurrentResponse)
async def get_current_logo(
    doctor_id: str = Query(..., description="Doctor's UUID"),
    authorization: str = Header(..., description="Bearer token")
):
    """
    Get current clinic logo URL for a doctor
    Requires JWT authentication
    """
    try:
        # Verify Firebase token and get Supabase client
        supabase, user_id = verify_firebase_token_and_get_client(authorization)

        # Get doctor and verify ownership
        doctor_result = supabase.table("doctors").select("clinic_logo_url, user_id").eq("id", doctor_id).execute()

        if not doctor_result.data:
            raise HTTPException(status_code=404, detail="Doctor not found")

        doctor_data = doctor_result.data[0]

        # Verify that the authenticated user owns this doctor record
        if doctor_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized: You can only access logos for your own account")

        logo_url = doctor_data.get('clinic_logo_url')

        return LogoCurrentResponse(clinic_logo_url=logo_url)

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get logo error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get logo: {str(e)}")
