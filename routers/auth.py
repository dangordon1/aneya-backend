"""
Authentication Router for OTP Email Verification
Handles sending, verifying, and resending OTPs for user signup
"""
import os
import random
import string
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from supabase import create_client, Client
import resend

from models.auth import (
    SendOTPRequest, SendOTPResponse,
    VerifyOTPRequest, VerifyOTPResponse,
    ResendOTPRequest, ResendOTPResponse
)
from config import RESEND_API_KEY

# Initialize router
router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Supabase client initialization
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise Exception("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# Constants
OTP_LENGTH = 6
OTP_EXPIRY_MINUTES = 10
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
MAX_RESENDS = 3
RESEND_COOLDOWN_SECONDS = 60


def generate_otp() -> str:
    """Generate a random 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=OTP_LENGTH))


def hash_otp(otp: str) -> str:
    """Hash OTP using bcrypt"""
    return bcrypt.hashpw(otp.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_otp_hash(otp: str, otp_hash: str) -> bool:
    """Verify OTP against bcrypt hash (timing-attack resistant)"""
    try:
        return bcrypt.checkpw(otp.encode('utf-8'), otp_hash.encode('utf-8'))
    except Exception:
        return False


def get_otp_email_html(otp: str, name: Optional[str], email: str) -> str:
    """Generate HTML email template for OTP"""
    greeting = f"Hi {name}," if name else "Hello,"

    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f6f5ee;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
        }}
        .card {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 40px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo {{
            max-width: 180px;
            height: auto;
            margin: 0 auto;
            display: block;
        }}
        .content {{
            margin-bottom: 30px;
        }}
        .otp-box {{
            background: #f6f5ee;
            border: 2px solid #1d9e99;
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            margin: 30px 0;
        }}
        .otp-code {{
            font-family: 'Courier New', Courier, monospace;
            font-size: 36px;
            font-weight: bold;
            color: #0c3555;
            letter-spacing: 8px;
            margin: 10px 0;
        }}
        .otp-label {{
            font-size: 14px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        .footer {{
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }}
        .warning {{
            background: #fff8e6;
            border: 1px solid #ffd666;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 14px;
            color: #8a6d3b;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <img src="https://aneya.vercel.app/aneya-logo.png" alt="Aneya" class="logo">
            </div>
            <div class="content">
                <h2 style="color: #0c3555; margin-bottom: 16px;">Verify Your Email Address</h2>
                <p>{greeting}</p>
                <p>Thank you for signing up with Aneya! To complete your registration and access your account, please verify your email address by entering the code below:</p>

                <div class="otp-box">
                    <div class="otp-label">Your Verification Code</div>
                    <div class="otp-code">{otp}</div>
                </div>

                <p style="text-align: center; color: #666; font-size: 14px;">
                    This code will expire in <strong>10 minutes</strong>
                </p>

                <div class="warning">
                    <strong>Didn't request this code?</strong> If you didn't create an account with Aneya, you can safely ignore this email.
                </div>
            </div>
            <div class="footer">
                <p style="font-size: 12px; color: #999;">
                    Aneya Healthcare Platform<br>
                    This email was sent to {email}
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_otp_email_text(otp: str, name: Optional[str], email: str) -> str:
    """Generate plain text email for OTP"""
    greeting = f"Hi {name}," if name else "Hello,"

    return f"""
Verify Your Email Address - Aneya

{greeting}

Thank you for signing up with Aneya! To complete your registration and access your account, please verify your email address by entering the code below:

YOUR VERIFICATION CODE: {otp}

This code will expire in 10 minutes.

If you didn't create an account with Aneya, you can safely ignore this email.

---
Aneya Healthcare Platform
This email was sent to {email}
"""


async def send_otp_email(email: str, otp: str, name: Optional[str] = None) -> None:
    """Send OTP via Resend email service"""
    if not RESEND_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Email service not configured. RESEND_API_KEY is required."
        )

    resend.api_key = RESEND_API_KEY

    html_content = get_otp_email_html(otp, name, email)
    text_content = get_otp_email_text(otp, name, email)

    try:
        params = {
            "from": "Aneya <noreply@aneya.health>",  # Verified custom domain
            "to": [email],
            "subject": "Verify Your Email - Aneya",
            "html": html_content,
            "text": text_content
        }

        response = resend.Emails.send(params)
        print(f"✅ OTP email sent to {email}: {response}")
    except Exception as e:
        print(f"❌ Failed to send OTP email to {email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send verification email")


@router.post("/send-otp", response_model=SendOTPResponse)
async def send_otp(request: SendOTPRequest):
    """
    Generate and send OTP verification code via email

    Creates or updates email_verifications record with:
    - 6-digit OTP (bcrypt hashed)
    - 10-minute expiration
    - Reset attempts counter
    """
    try:
        email = request.email.strip().lower()
        user_id = request.user_id.strip()

        print(f"📧 Sending OTP to {email} for user {user_id}")

        # Generate OTP
        otp = generate_otp()
        otp_hashed = hash_otp(otp)

        # Calculate expiry time
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)

        # Check if verification record exists
        existing = supabase.table('email_verifications').select('*').eq('user_id', user_id).execute()

        if existing.data and len(existing.data) > 0:
            # Update existing record
            supabase.table('email_verifications').update({
                'otp_hash': otp_hashed,
                'created_at': now.isoformat(),
                'expires_at': expires_at.isoformat(),
                'is_verified': False,
                'verified_at': None,
                'attempts': 0,
                'locked_until': None
            }).eq('user_id', user_id).execute()
            print(f"✅ Updated existing verification record for {user_id}")
        else:
            # Create new record
            supabase.table('email_verifications').insert({
                'user_id': user_id,
                'email': email,
                'otp_hash': otp_hashed,
                'expires_at': expires_at.isoformat(),
                'is_verified': False,
                'attempts': 0,
                'resend_count': 0
            }).execute()
            print(f"✅ Created verification record for {user_id}")

        # Send email
        await send_otp_email(email, otp, request.name)

        return SendOTPResponse(
            success=True,
            message="Verification code sent to your email",
            expires_in_seconds=OTP_EXPIRY_MINUTES * 60
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in send_otp: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send verification code: {str(e)}")


@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(request: VerifyOTPRequest):
    """
    Verify OTP code entered by user

    Checks:
    - OTP exists and not expired
    - Not locked out from too many attempts
    - OTP matches hash (timing-attack resistant)

    On success:
    - Marks email_verifications.is_verified = true
    - Sets user_roles.email_verified = true

    On failure:
    - Increments attempts
    - Locks if attempts >= 5
    """
    try:
        user_id = request.user_id.strip()
        otp = request.otp.strip()

        print(f"🔐 Verifying OTP for user {user_id}")

        # Get verification record
        result = supabase.table('email_verifications').select('*').eq('user_id', user_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="No verification request found")

        record = result.data[0]
        now = datetime.now(timezone.utc)

        # Check if already verified
        if record['is_verified']:
            return VerifyOTPResponse(
                success=True,
                message="Email already verified",
                verified=True
            )

        # Check if locked
        if record['locked_until']:
            locked_until = datetime.fromisoformat(record['locked_until'].replace('Z', '+00:00'))
            if now < locked_until:
                remaining = int((locked_until - now).total_seconds())
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many failed attempts. Try again in {remaining // 60} minutes"
                )

        # Check if expired
        expires_at = datetime.fromisoformat(record['expires_at'].replace('Z', '+00:00'))
        if now > expires_at:
            raise HTTPException(
                status_code=400,
                detail="Verification code has expired. Please request a new code"
            )

        # Verify OTP
        if not verify_otp_hash(otp, record['otp_hash']):
            # Increment attempts
            new_attempts = record['attempts'] + 1

            # Check if should lock
            if new_attempts >= MAX_ATTEMPTS:
                locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                supabase.table('email_verifications').update({
                    'attempts': new_attempts,
                    'locked_until': locked_until.isoformat()
                }).eq('user_id', user_id).execute()

                raise HTTPException(
                    status_code=429,
                    detail=f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes"
                )
            else:
                supabase.table('email_verifications').update({
                    'attempts': new_attempts
                }).eq('user_id', user_id).execute()

                remaining = MAX_ATTEMPTS - new_attempts
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid verification code. {remaining} attempts remaining"
                )

        # OTP verified successfully
        verified_at = now.isoformat()

        # Update email_verifications
        supabase.table('email_verifications').update({
            'is_verified': True,
            'verified_at': verified_at
        }).eq('user_id', user_id).execute()

        # Update user_roles.email_verified
        supabase.table('user_roles').update({
            'email_verified': True
        }).eq('user_id', user_id).execute()

        print(f"✅ Email verified for user {user_id}")

        return VerifyOTPResponse(
            success=True,
            message="Email verified successfully! You can now log in",
            verified=True
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in verify_otp: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")


@router.post("/resend-otp", response_model=ResendOTPResponse)
async def resend_otp(request: ResendOTPRequest):
    """
    Resend OTP verification code

    Checks:
    - Cooldown period (60 seconds since last resend)
    - Max resends limit (3)

    Generates new OTP and sends email
    """
    try:
        user_id = request.user_id.strip()
        email = request.email.strip().lower()

        print(f"🔄 Resending OTP to {email} for user {user_id}")

        # Get verification record
        result = supabase.table('email_verifications').select('*').eq('user_id', user_id).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="No verification request found")

        record = result.data[0]
        now = datetime.now(timezone.utc)

        # Check if already verified
        if record['is_verified']:
            return ResendOTPResponse(
                success=True,
                message="Email already verified",
                expires_in_seconds=0,
                resend_count=record['resend_count']
            )

        # Check resend cooldown
        if record['last_resent_at']:
            last_resent = datetime.fromisoformat(record['last_resent_at'].replace('Z', '+00:00'))
            cooldown_remaining = RESEND_COOLDOWN_SECONDS - (now - last_resent).total_seconds()
            if cooldown_remaining > 0:
                raise HTTPException(
                    status_code=429,
                    detail=f"Please wait {int(cooldown_remaining)} seconds before requesting another code"
                )

        # Check max resends
        if record['resend_count'] >= MAX_RESENDS:
            raise HTTPException(
                status_code=429,
                detail="Maximum resend limit reached. Please try again later or contact support"
            )

        # Generate new OTP
        otp = generate_otp()
        otp_hashed = hash_otp(otp)
        expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)

        # Update record
        new_resend_count = record['resend_count'] + 1
        supabase.table('email_verifications').update({
            'otp_hash': otp_hashed,
            'created_at': now.isoformat(),
            'expires_at': expires_at.isoformat(),
            'attempts': 0,
            'locked_until': None,
            'resend_count': new_resend_count,
            'last_resent_at': now.isoformat()
        }).eq('user_id', user_id).execute()

        # Send email (without name to avoid RLS issues)
        await send_otp_email(email, otp, None)

        print(f"✅ OTP resent to {email} (resend #{new_resend_count})")

        return ResendOTPResponse(
            success=True,
            message="New verification code sent to your email",
            expires_in_seconds=OTP_EXPIRY_MINUTES * 60,
            resend_count=new_resend_count
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in resend_otp: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to resend code: {str(e)}")
