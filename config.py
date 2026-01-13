"""
Configuration Module for Aneya API
Centralizes all environment variables and API keys
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Firebase Configuration
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "aneya-266ee")

# Google Cloud Storage Configuration
GCS_BUCKET_NAME = "aneya-audio-recordings"

# CORS Origins
CORS_ORIGINS = [
    "http://localhost:5173",  # Local development
    "http://localhost:5174",  # Local development (alternative port)
    "http://localhost:5175",  # Local development (alternative port)
    "http://localhost:5176",  # Local development (alternative port)
    "http://localhost:3000",
    "https://aneya.vercel.app",  # Production frontend
    "https://aneya.health",  # Custom domain
    "https://www.aneya.health",  # Custom domain with www
]
