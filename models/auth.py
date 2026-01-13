"""
Authentication Pydantic models for OTP verification
"""
from pydantic import BaseModel, EmailStr
from typing import Optional


class SendOTPRequest(BaseModel):
    """Request model for sending OTP via email"""
    email: EmailStr
    user_id: str  # Firebase UID
    name: Optional[str] = None
    role: str  # 'doctor' or 'patient'


class SendOTPResponse(BaseModel):
    """Response model for send OTP endpoint"""
    success: bool
    message: str
    expires_in_seconds: int


class VerifyOTPRequest(BaseModel):
    """Request model for verifying OTP"""
    user_id: str
    otp: str  # 6-digit code


class VerifyOTPResponse(BaseModel):
    """Response model for verify OTP endpoint"""
    success: bool
    message: str
    verified: bool


class ResendOTPRequest(BaseModel):
    """Request model for resending OTP"""
    user_id: str
    email: EmailStr


class ResendOTPResponse(BaseModel):
    """Response model for resend OTP endpoint"""
    success: bool
    message: str
    expires_in_seconds: int
    resend_count: int
