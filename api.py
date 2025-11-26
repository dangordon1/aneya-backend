#!/usr/bin/env python
"""
Aneya API - FastAPI Backend
Wraps the Clinical Decision Support Client for the React frontend
"""

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
import os
import sys
import json
import httpx
import tempfile
# Load environment variables from .env file
load_dotenv()

# Add servers directory to path (servers is in the backend repo root)
sys.path.insert(0, str(Path(__file__).parent / "servers"))
from clinical_decision_support_client import ClinicalDecisionSupportClient

# Global instances (reused across requests)
client: Optional[ClinicalDecisionSupportClient] = None
parakeet_model = None  # NVIDIA Parakeet TDT for transcription


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    global client, parakeet_model

    # Startup
    print("🚀 Starting Aneya API...")

    # Check for Anthropic API key - REQUIRED!
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        error_msg = """
        ❌ FATAL ERROR: ANTHROPIC_API_KEY not found!

        Aneya requires an Anthropic API key to function.

        To fix this:
        1. Create a .env file in the project root if it doesn't exist
        2. Add your API key:
           ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
        3. Restart the server

        Get your API key from: https://console.anthropic.com/
        """
        print(error_msg)
        raise RuntimeError("ANTHROPIC_API_KEY is required but not found in environment")

    print(f"✅ Anthropic API key loaded (ends with ...{anthropic_key[-4:]})")

    # Initialize client but DON'T connect to servers yet
    # Servers will be connected per-request based on user's region (detected from IP)
    client = ClinicalDecisionSupportClient(anthropic_api_key=anthropic_key)
    print("✅ Client initialized (servers will be loaded based on user region)")

    # LAZY LOADING: Parakeet TDT model will be loaded on first transcription request
    # This allows Cloud Run to start quickly and pass health checks
    print("ℹ️  Parakeet TDT model will be loaded on first transcription request (lazy loading)")

    yield

    # Shutdown
    if client:
        await client.cleanup()
        print("✅ Client cleanup complete")


app = FastAPI(
    title="Aneya Clinical Decision Support API",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend
# Note: Update with your actual Vercel domain after deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Local development
        "http://localhost:5174",  # Local development (alternative port)
        "http://localhost:3000",
        "https://*.vercel.app",  # Vercel deployments
        "https://aneya.vercel.app",  # Production frontend
        "https://aneya-qy2d3acnx-daniel-gordons-projects-ec39af4d.vercel.app",  # Old production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalysisRequest(BaseModel):
    """Request body for consultation analysis"""
    consultation: str
    patient_id: Optional[str] = None
    patient_age: Optional[str] = None
    allergies: Optional[str] = None
    user_ip: Optional[str] = None  # User's IP address for geolocation
    location_override: Optional[str] = None  # Optional manual country override


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str


async def get_country_from_ip(ip_address: str) -> Optional[dict]:
    """
    Get country information from an IP address using ip-api.com.

    Args:
        ip_address: The IP address to lookup

    Returns:
        Dictionary with country and country_code, or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f'http://ip-api.com/json/{ip_address}?fields=status,message,country,countryCode'
            )
            response.raise_for_status()
            data = response.json()

            if data.get('status') == 'fail':
                print(f"⚠️  Geolocation API error: {data.get('message', 'Unknown error')}")
                return None

            return {
                'ip': ip_address,
                'country': data.get('country'),
                'country_code': data.get('countryCode')
            }
    except Exception as e:
        print(f"⚠️  Geolocation failed: {str(e)}")
        return None


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint"""
    return {
        "status": "ok",
        "message": "Aneya Clinical Decision Support API is running"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if client is None:
        raise HTTPException(status_code=503, detail="Client not initialized")

    return {
        "status": "healthy",
        "message": "All systems operational"
    }


@app.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """API health check endpoint (frontend compatibility)"""
    if client is None:
        raise HTTPException(status_code=503, detail="Client not initialized")

    return {
        "status": "healthy",
        "message": "All systems operational"
    }


@app.post("/api/analyze")
async def analyze_consultation(request: AnalysisRequest):
    """
    Analyze a clinical consultation and return recommendations

    Args:
        request: AnalysisRequest with consultation text and optional patient info

    Returns:
        Complete clinical decision support analysis
    """
    if client is None:
        raise HTTPException(status_code=503, detail="Client not initialized")

    if not request.consultation.strip():
        raise HTTPException(status_code=400, detail="Consultation text is required")

    try:
        # Normalize empty strings to None for cleaner handling
        patient_id = request.patient_id if request.patient_id and request.patient_id.strip() else None
        patient_age = request.patient_age if request.patient_age and request.patient_age.strip() else None
        allergies = request.allergies if request.allergies and request.allergies.strip() else None

        print(f"\n{'='*70}")
        print(f"📋 NEW ANALYSIS REQUEST")
        print(f"{'='*70}")
        print(f"Patient ID: {patient_id or 'Not provided (info from consultation only)'}")
        print(f"Patient Age: {patient_age or 'Not provided'}")
        print(f"Allergies: {allergies or 'Not provided'}")
        print(f"User IP: {request.user_ip or 'Not provided (will auto-detect)'}")
        print(f"Location Override: {request.location_override or 'Not provided'}")
        print(f"\n📝 FULL CONSULTATION TEXT:")
        print(f"{'-'*70}")
        print(f"{request.consultation}")
        print(f"{'-'*70}")
        print(f"Consultation length: {len(request.consultation)} characters")
        print(f"{'='*70}\n")

        # Step 1: Get geolocation FIRST (direct HTTP call, no MCP)
        location_to_use = request.location_override  # Manual override takes precedence
        detected_country = None

        if not location_to_use and request.user_ip:
            # Use client's direct geolocation method (no MCP)
            geo_data = await client.get_location_from_ip(request.user_ip)
            if geo_data and geo_data.get('country_code') != 'XX':
                location_to_use = geo_data.get('country_code')
                detected_country = geo_data.get('country')
                print(f"🌍 Detected location from IP {request.user_ip}: {detected_country} ({location_to_use})")
            else:
                print(f"⚠️  Geolocation failed. Backend will auto-detect.")
                location_to_use = None

        # Step 2: Connect to region-specific MCP servers
        # Only connect if not already connected (check if we have sessions)
        if not client.sessions:
            print(f"🔄 Connecting to region-specific MCP servers for {location_to_use or 'default'}...")
            await client.connect_to_servers(country_code=location_to_use, verbose=True)
        else:
            print(f"✅ Using existing MCP server connections")

        # Step 3: Run the clinical decision support workflow
        result = await client.clinical_decision_support(
            clinical_scenario=request.consultation,
            patient_id=patient_id,  # Use normalized value (None if empty)
            patient_age=patient_age,  # Use normalized value (None if empty)
            allergies=allergies,  # Use normalized value (None if empty)
            location_override=location_to_use,
            verbose=True  # This will show ALL the Anthropic API calls and processing steps
        )

        print(f"\n{'='*70}")
        print(f"✅ ANALYSIS COMPLETE")
        print(f"{'='*70}")
        print(f"Diagnoses found: {len(result.get('diagnoses', []))}")

        # Log each diagnosis with confidence
        for idx, diagnosis in enumerate(result.get('diagnoses', []), 1):
            print(f"  {idx}. {diagnosis.get('name', 'Unknown')} (confidence: {diagnosis.get('confidence', 'N/A')})")

        print(f"\nBNF guidance entries: {len(result.get('bnf_prescribing_guidance', []))}")

        # Log medication names
        for idx, guidance in enumerate(result.get('bnf_prescribing_guidance', []), 1):
            print(f"  {idx}. {guidance.get('medication', 'Unknown')}")

        print(f"\nGuidelines searched: {len(result.get('guidelines_searched', []))}")
        print(f"{'='*70}\n")

        return result

    except Exception as e:
        print(f"❌ Analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/examples")
async def get_examples():
    """Get example clinical scenarios for testing"""
    return {
        "examples": [
            {
                "id": "pediatric-croup",
                "name": "Pediatric Croup",
                "scenario": "3-year-old with croup, moderate stridor at rest, barking cough",
                "patient_id": "P001"
            },
            {
                "id": "post-op-sepsis",
                "name": "Post-Operative Sepsis",
                "scenario": "Post-operative sepsis, fever 38.5C, tachycardia, suspected wound infection",
                "patient_id": "P002"
            },
            {
                "id": "acute-asthma",
                "name": "Acute Asthma Exacerbation",
                "scenario": "45-year-old with severe asthma exacerbation, peak flow 40% predicted, breathless",
                "patient_id": "P003"
            },
            {
                "id": "community-pneumonia",
                "name": "Community-Acquired Pneumonia",
                "scenario": "72-year-old with CAP, CURB-65 score 2, productive cough, fever",
                "patient_id": "P004"
            }
        ]
    }


def load_parakeet_model():
    """Lazily load the Parakeet TDT model on first use."""
    global parakeet_model
    if parakeet_model is not None:
        return parakeet_model

    print("🎤 Loading NVIDIA Parakeet TDT 0.6B model for transcription...")
    print("   (First load downloads ~350MB model from HuggingFace)")
    import sys
    sys.stdout.flush()

    try:
        import nemo.collections.asr as nemo_asr
        parakeet_model = nemo_asr.models.ASRModel.from_pretrained('nvidia/parakeet-tdt-0.6b-v2')
        print("✅ Parakeet TDT model loaded successfully")
        sys.stdout.flush()
        return parakeet_model
    except Exception as e:
        print(f"❌ Failed to load Parakeet model: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        raise HTTPException(status_code=503, detail=f"Failed to load transcription model: {str(e)}")


@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio using NVIDIA Parakeet TDT 1.1B model

    Args:
        audio: Audio file (webm, wav, mp3, etc.)

    Returns:
        Transcribed text (with numbers spelled out, e.g., "thirty eight point five")
    """
    # Lazy load the model on first request
    model = load_parakeet_model()
    print(f"📝 Transcribe endpoint called - model loaded: {model is not None}")

    try:
        print(f"🎤 Transcribing audio file: {audio.filename}")

        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp_file:
            content = await audio.read()
            tmp_file.write(content)
            tmp_webm_path = tmp_file.name

        # Save a copy of the recording for debugging
        import datetime
        debug_dir = Path(__file__).parent / "debug_recordings"
        debug_dir.mkdir(exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_webm_path = debug_dir / f"recording_{timestamp}.webm"
        with open(debug_webm_path, "wb") as f:
            f.write(content)
        print(f"💾 Saved debug recording to: {debug_webm_path}")

        # Log audio file details
        audio_size_kb = len(content) / 1024
        print(f"📊 Audio file size: {audio_size_kb:.2f} KB ({len(content)} bytes)")

        # Convert WebM to WAV (16kHz mono) for reliable transcription
        # WebM chunks concatenated together don't form a valid container,
        # but ffmpeg can still decode the audio stream
        import subprocess
        tmp_wav_path = tmp_webm_path.replace('.webm', '.wav')
        try:
            result = subprocess.run([
                'ffmpeg', '-y', '-i', tmp_webm_path,
                '-ar', '16000',  # 16kHz sample rate (required by Parakeet)
                '-ac', '1',      # Mono
                '-f', 'wav',
                tmp_wav_path
            ], capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                print(f"⚠️  FFmpeg conversion failed: {result.stderr}")
                # Fall back to using webm directly
                tmp_file_path = tmp_webm_path
            else:
                tmp_file_path = tmp_wav_path
                print(f"✅ Converted to WAV: {os.path.getsize(tmp_wav_path) / 1024:.2f} KB")
                # Save a copy of the WAV for debugging
                debug_wav_path = debug_dir / f"recording_{timestamp}.wav"
                import shutil
                shutil.copy(tmp_wav_path, debug_wav_path)
                print(f"💾 Saved debug WAV to: {debug_wav_path}")
        except FileNotFoundError:
            print("⚠️  FFmpeg not found, using WebM directly")
            tmp_file_path = tmp_webm_path
        except subprocess.TimeoutExpired:
            print("⚠️  FFmpeg timeout, using WebM directly")
            tmp_file_path = tmp_webm_path

        try:
            # Transcribe using NVIDIA Parakeet TDT 1.1B
            import time
            start = time.time()
            result = model.transcribe([tmp_file_path])
            latency = time.time() - start

            # Extract text from result
            if result and len(result) > 0:
                transcription = result[0]
                # Handle different return types from different model versions
                if hasattr(transcription, 'text'):
                    # Hypothesis object (older models)
                    transcription = transcription.text
                elif isinstance(transcription, list) and len(transcription) > 0:
                    # List of strings (v2 models return list)
                    transcription = transcription[0] if isinstance(transcription[0], str) else str(transcription[0])
                elif isinstance(transcription, str):
                    # Already a string
                    pass
                else:
                    transcription = str(transcription)
            else:
                transcription = ""

            # Log full transcription for debugging
            print(f"✅ Transcription complete in {latency:.2f}s")
            print(f"📝 Full transcription text: '{transcription}'")

            return {
                "success": True,
                "text": transcription.strip(),
                "latency_seconds": round(latency, 2),
                "model": "nvidia/parakeet-tdt-0.6b-v2"
            }

        finally:
            # Clean up temporary files
            if os.path.exists(tmp_webm_path):
                os.unlink(tmp_webm_path)
            if os.path.exists(tmp_wav_path):
                os.unlink(tmp_wav_path)

    except Exception as e:
        print(f"❌ Transcription error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
