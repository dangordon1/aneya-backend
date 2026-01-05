#!/usr/bin/env python
"""
Aneya API - FastAPI Backend
Wraps the Clinical Decision Support Client for the React frontend
"""

# Suppress Pydantic deprecation warnings from third-party libraries (pyiceberg)
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyiceberg")

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, BackgroundTasks, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
import os
import sys
import re
import json
import httpx
import tempfile
import time
import asyncio
import uuid
import traceback
from datetime import datetime, timezone
from google.cloud import storage
from pdf_generator import generate_consultation_pdf
import firebase_admin
from firebase_admin import credentials
from functools import lru_cache
import copy

# Load environment variables from .env file
load_dotenv()

# Initialize Firebase Admin SDK (for password reset link generation)
# Uses Application Default Credentials (ADC) when running on Cloud Run
# Requires GOOGLE_CLOUD_PROJECT or explicit project ID
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "aneya-266ee")

if not firebase_admin._apps:
    try:
        # Initialize with explicit project ID
        firebase_admin.initialize_app(options={
            'projectId': FIREBASE_PROJECT_ID
        })
        print(f"✅ Firebase Admin SDK initialized (project: {FIREBASE_PROJECT_ID})")
    except Exception as e:
        print(f"⚠️  Firebase Admin SDK initialization warning: {e}")


def get_git_branch() -> str:
    """Get current git branch name"""
    # First try environment variable (for production/Cloud Run)
    branch = os.getenv("GIT_BRANCH")
    if branch:
        return branch

    # Fall back to git command (for local development)
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=str(Path(__file__).parent)
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"⚠️  Failed to get git branch: {e}")

    return "unknown"


# Add servers directory to path (servers is in the backend repo root)
sys.path.insert(0, str(Path(__file__).parent / "servers"))
from clinical_decision_support.client import ClinicalDecisionSupportClient
from clinical_decision_support import ConsultationSummary

# Global instances (reused across requests)
client: Optional[ClinicalDecisionSupportClient] = None
elevenlabs_client = None  # ElevenLabs API client for transcription
consultation_summary: Optional[ConsultationSummary] = None  # Consultation summarizer
gcs_client = None  # Google Cloud Storage client
GCS_BUCKET_NAME = "aneya-audio-recordings"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    global client, elevenlabs_client, consultation_summary, gcs_client

    # Startup
    print("🚀 Starting Aneya API...")
    print(f"🌿 Running on branch: {get_git_branch()}")

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

    # Initialize ElevenLabs client for transcription
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if elevenlabs_key:
        from elevenlabs import ElevenLabs
        elevenlabs_client = ElevenLabs(api_key=elevenlabs_key)
        print(f"✅ ElevenLabs API key loaded (ends with ...{elevenlabs_key[-4:]})")
    else:
        print("⚠️  ELEVENLABS_API_KEY not found - voice transcription and diarization will not work")

    # Initialize client but DON'T connect to servers yet
    # Servers will be connected per-request based on user's region (detected from IP)
    client = ClinicalDecisionSupportClient(anthropic_api_key=anthropic_key)
    print("✅ Client initialized (servers will be loaded based on user region)")

    # Initialize consultation summary system
    consultation_summary = ConsultationSummary(anthropic_api_key=anthropic_key)
    print("✅ Consultation summary system initialized")

    # Initialize GCS client for audio storage
    try:
        gcs_client = storage.Client()
        print(f"✅ GCS client initialized (bucket: {GCS_BUCKET_NAME})")
    except Exception as e:
        print(f"⚠️  GCS client initialization failed: {e} - audio upload will not work")

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
        "http://localhost:5175",  # Local development (alternative port)
        "http://localhost:5176",  # Local development (alternative port)
        "http://localhost:3000",
        "http://localhost:9000",  # Local development (alternative port)
        "http://localhost:9001",  # Local development (alternative port)
        "https://aneya.vercel.app",  # Production frontend
        "https://aneya.health",  # Custom domain
        "https://www.aneya.health",  # Custom domain with www
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include doctor logo API router
from doctor_logo_api import router as doctor_logo_router
app.include_router(doctor_logo_router)

# Include custom forms API router
from custom_forms_api import router as custom_forms_router
app.include_router(custom_forms_router)


class AnalysisRequest(BaseModel):
    """Request body for consultation analysis"""
    consultation: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    patient_age: Optional[str] = None
    patient_sex: Optional[str] = None
    patient_height: Optional[str] = None
    patient_weight: Optional[str] = None
    current_medications: Optional[str] = None
    current_conditions: Optional[str] = None
    allergies: Optional[str] = None
    user_ip: Optional[str] = None  # User's IP address for geolocation
    location_override: Optional[str] = None  # Optional manual country override


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str
    branch: str = "unknown"


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
        "message": "Aneya Clinical Decision Support API is running",
        "branch": get_git_branch()
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    if client is None:
        raise HTTPException(status_code=503, detail="Client not initialized")

    return {
        "status": "healthy",
        "message": "All systems operational",
        "branch": get_git_branch()
    }


@app.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """API health check endpoint (frontend compatibility)"""
    if client is None:
        raise HTTPException(status_code=503, detail="Client not initialized")

    return {
        "status": "healthy",
        "message": "All systems operational",
        "branch": get_git_branch()
    }


@app.get("/api/geolocation")
async def get_geolocation():
    """
    Get geolocation info including timezone based on the caller's IP address.
    Uses ip-api.com for geolocation lookups.

    Returns:
        Dictionary with ip, country, country_code, timezone, city, region
    """
    try:
        async with httpx.AsyncClient() as http_client:
            # Get public IP
            ip_response = await http_client.get('https://api.ipify.org?format=json', timeout=5.0)
            ip_response.raise_for_status()
            ip_address = ip_response.json()['ip']

            # Get geolocation with timezone
            geo_response = await http_client.get(
                f'http://ip-api.com/json/{ip_address}?fields=status,message,country,countryCode,city,regionName,timezone',
                timeout=5.0
            )
            geo_response.raise_for_status()
            data = geo_response.json()

            if data.get('status') == 'fail':
                raise HTTPException(status_code=400, detail=f"Geolocation failed: {data.get('message', 'Unknown error')}")

            return {
                'ip': ip_address,
                'country': data.get('country'),
                'country_code': data.get('countryCode'),
                'city': data.get('city'),
                'region': data.get('regionName'),
                'timezone': data.get('timezone')
            }
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Geolocation service unavailable: {str(e)}")


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
        if not client.diagnosis_engine.sessions:
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
            verbose=True,  # This will show ALL the Anthropic API calls and processing steps
            max_drugs=0  # Disable BNF drug lookups for faster analysis
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


@app.post("/api/analyze-stream")
async def analyze_consultation_stream(request: AnalysisRequest):
    """
    Analyze a clinical consultation with real-time progress updates via Server-Sent Events (SSE)

    This endpoint streams progress updates as the analysis proceeds:
    - Location detection
    - Guidelines being searched
    - Diagnoses identified
    - BNF drug lookups
    - Final results

    Args:
        request: AnalysisRequest with consultation text and optional patient info

    Returns:
        StreamingResponse with SSE events containing progress updates and final results
    """
    if client is None:
        raise HTTPException(status_code=503, detail="Client not initialized")

    if not request.consultation.strip():
        raise HTTPException(status_code=400, detail="Consultation text is required")

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events for progress updates using sse-starlette"""
        try:
            # Helper to send SSE event - uses dict format for sse-starlette
            def send_event(event_type: str, data: dict) -> dict:
                return {"event": event_type, "data": json.dumps(data)}

            # Normalize input - extract all patient details
            patient_id = request.patient_id if request.patient_id and request.patient_id.strip() else None
            patient_name = request.patient_name if request.patient_name and request.patient_name.strip() else None
            patient_age = request.patient_age if request.patient_age and request.patient_age.strip() else None
            patient_sex = request.patient_sex if request.patient_sex and request.patient_sex.strip() else None
            patient_height = request.patient_height if request.patient_height and request.patient_height.strip() else None
            patient_weight = request.patient_weight if request.patient_weight and request.patient_weight.strip() else None
            current_medications = request.current_medications if request.current_medications and request.current_medications.strip() else None
            current_conditions = request.current_conditions if request.current_conditions and request.current_conditions.strip() else None
            allergies = request.allergies if request.allergies and request.allergies.strip() else None

            # Send start event
            yield send_event("start", {"message": "Starting analysis..."})

            # Step 1: Geolocation
            yield send_event("progress", {"step": "geolocation", "message": "Detecting location..."})

            location_to_use = request.location_override
            detected_country = None

            if not location_to_use and request.user_ip:
                geo_data = await client.get_location_from_ip(request.user_ip)
                if geo_data and geo_data.get('country_code') != 'XX':
                    location_to_use = geo_data.get('country_code')
                    detected_country = geo_data.get('country')
                    yield send_event("location", {
                        "country": detected_country,
                        "country_code": location_to_use,
                        "ip": request.user_ip
                    })
                else:
                    yield send_event("progress", {"step": "geolocation", "message": "Using default region"})

            # Step 2: Connect to servers (will auto-reconnect if region changed)
            yield send_event("progress", {
                "step": "connecting",
                "message": f"Loading medical guidelines for {detected_country or 'default region'}..."
            })
            await client.connect_to_servers(country_code=location_to_use, verbose=True)

            # Step 3: Validate input
            yield send_event("progress", {"step": "validating", "message": "Validating clinical input..."})

            # Step 4: Run analysis
            yield send_event("progress", {"step": "analyzing", "message": "Analyzing consultation with AI..."})

            # Two-phase streaming approach:
            # Phase 1: Get diagnoses (blocking ~60s) - yields immediately when done
            # Phase 2: Stream drug lookups - yields each drug_update as it completes

            print(f"[API] Phase 1: Getting diagnoses...", flush=True)

            # Phase 1: Get diagnoses (blocking call is fine - we stream result immediately after)
            diagnosis_result = await client.get_diagnoses(
                clinical_scenario=request.consultation,
                patient_id=patient_id,
                patient_name=patient_name,
                patient_age=patient_age,
                patient_sex=patient_sex,
                patient_height=patient_height,
                patient_weight=patient_weight,
                current_medications=current_medications,
                current_conditions=current_conditions,
                allergies=allergies,
                location_override=location_to_use,
                verbose=False
            )

            # Check for validation error
            if diagnosis_result.get('error') == 'invalid_input':
                yield send_event("error", {
                    "type": "invalid_input",
                    "message": diagnosis_result.get('error_message', 'Invalid input')
                })
                return

            diagnoses = diagnosis_result.get('diagnoses', [])
            drugs_to_lookup = diagnosis_result.get('drugs_to_lookup', [])
            patient_context = diagnosis_result.get('patient_context', {})

            # Emit diagnoses event with pending drugs - this goes to client IMMEDIATELY
            drugs_pending = [d['drug_name'] for d in drugs_to_lookup]
            import time
            print(f"[API] [{time.time():.3f}] Sending diagnoses event with {len(diagnoses)} diagnoses, {len(drugs_pending)} pending drugs", flush=True)
            yield send_event("diagnoses", {
                "diagnoses": diagnoses,
                "drugs_pending": drugs_pending
            })
            await asyncio.sleep(0)  # Force event loop to flush diagnoses event

            print(f"[API] [{time.time():.3f}] Phase 2: Streaming drug lookups for {len(drugs_to_lookup)} drugs...", flush=True)

            # Phase 2: Stream drug lookups - each drug_update is yielded as it completes
            drug_results = []
            async for drug_update in client.stream_drug_lookups(drugs_to_lookup, patient_context):
                print(f"[API] [{time.time():.3f}] Streaming drug_update: {drug_update.get('drug_name')} - {drug_update.get('status')}", flush=True)
                yield send_event("drug_update", drug_update)
                await asyncio.sleep(0)  # Force event loop to flush
                drug_results.append(drug_update)

            # Build final result
            result = {
                'diagnoses': diagnoses,
                'bnf_prescribing_guidance': [],  # Populated from drug_results
                'guidelines_searched': [],  # Tool calls collected during diagnosis
                'summary': client._generate_summary(diagnoses)
            }

            # Add successful drug details to result
            for drug_result in drug_results:
                if drug_result.get('status') == 'complete' and drug_result.get('details'):
                    result['bnf_prescribing_guidance'].append(drug_result['details'])

            # Check for invalid input error
            if result and result.get('error') == 'invalid_input':
                yield send_event("error", {
                    "type": "invalid_input",
                    "message": result.get('error_message', 'Invalid input')
                })
                return

            # Send final complete result (diagnoses and BNF events already sent in real-time)
            yield send_event("complete", result)
            yield send_event("done", {"message": "Analysis complete"})

        except Exception as e:
            yield send_event("error", {"message": str(e)})

    # Use EventSourceResponse from sse-starlette for proper SSE flushing
    # ping=15 sends ping every 15 seconds to keep connection alive
    # send_timeout=0.1 ensures events are sent immediately
    return EventSourceResponse(
        event_generator(),
        ping=15,
        send_timeout=0.1,
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.get("/api/test-sse")
async def test_sse():
    """Simple SSE test endpoint - yields events with 2 second delays"""
    async def event_generator():
        import asyncio
        for i in range(5):
            yield {"event": "message", "data": json.dumps({"count": i, "message": f"Event {i}"})}
            await asyncio.sleep(2)
        yield {"event": "done", "data": json.dumps({"message": "Complete"})}

    return EventSourceResponse(
        event_generator(),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


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


@app.post("/api/translate")
async def translate_text(request: dict = Body(...)):
    """
    Translate text to English using Google Translate

    Automatically detects the source language and translates to English.
    If the text is already in English, returns it unchanged.

    Args:
        request: {"text": "text to translate"}

    Returns:
        {
            "success": true,
            "original_text": "original text",
            "translated_text": "translated text",
            "detected_language": "hi",
            "detected_language_name": "Hindi"
        }
    """
    from deep_translator import GoogleTranslator

    text = request.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        # Use Google Translate via deep-translator (no API key needed for personal use)
        translator = GoogleTranslator(source='auto', target='en')
        translated = translator.translate(text)

        # Detect source language (deep-translator auto-detects)
        # For language detection, we'll use a simple heuristic or accept it as-is
        detected_lang = 'auto'  # deep-translator doesn't return detected language directly

        return {
            "success": True,
            "original_text": text,
            "translated_text": translated,
            "detected_language": detected_lang,
            "detected_language_name": "Auto-detected"
        }

    except Exception as e:
        print(f"❌ Translation error: {str(e)}")
        # Return original text if translation fails
        return {
            "success": False,
            "original_text": text,
            "translated_text": text,  # Fallback to original
            "detected_language": "unknown",
            "detected_language_name": "Unknown",
            "error": str(e)
        }


@app.post("/api/summarize")
async def summarize_text(request: dict = Body(...)):
    """
    Summarize consultation transcript using ConsultationSummary system

    Takes a diarized consultation transcript and generates a comprehensive
    clinical summary with speaker identification, timeline extraction, and
    structured SOAP note format.

    Args:
        request: {
            "text": "diarized transcript with [timestamp] speaker_X: format",
            "original_text": "original language transcript (optional)",
            "patient_info": {  # Optional
                "patient_id": "P001",
                "patient_age": "30 years old",
                "allergies": "None"
            },
            "is_from_transcription": true,  # Default true - enables transcription error handling
            "transcription_language": "en"  # Optional - language of original speech for homophone handling
        }

    Returns:
        Comprehensive JSON summary with:
        - speakers: Doctor/patient mapping
        - metadata: Patient info, consultation duration
        - timeline: Symptom onset and progression
        - clinical_summary: Full SOAP note
        - key_concerns: Patient concerns
        - recommendations_given: Medical advice
    """
    if consultation_summary is None:
        raise HTTPException(status_code=503, detail="Consultation summary system not initialized")

    if request is None:
        raise HTTPException(status_code=400, detail="Request body is required")

    text = request.get("text", "").strip()
    original_text = request.get("original_text", "").strip()
    if not text and not original_text:
        raise HTTPException(status_code=400, detail="Text is required")

    patient_info = request.get("patient_info")
    is_from_transcription = request.get("is_from_transcription", True)  # Default True for voice consultations
    transcription_language = request.get("transcription_language")  # Language of original transcription

    try:
        # Determine which transcript to use for summarization
        # Prefer original language transcript if provided - Claude handles non-English better than translation
        transcript_for_summary = original_text if original_text else text
        has_original = bool(original_text and original_text != text)

        print(f"\n{'='*70}")
        print(f"📝 SUMMARIZING CONSULTATION")
        print(f"{'='*70}")
        print(f"Translated transcript length: {len(text)} characters")
        if has_original:
            print(f"Original transcript length: {len(original_text)} characters")
            print(f"Using ORIGINAL language transcript for summarization (Claude will output in English)")
        if patient_info:
            print(f"Patient info provided: {list(patient_info.keys())}")
        print(f"{'='*70}\n")

        # Generate comprehensive summary
        # Pass the original transcript and a flag to tell Claude to output in English
        result = await consultation_summary.summarize(
            transcript=transcript_for_summary,
            patient_info=patient_info,
            output_in_english=has_original,  # Tell Claude to output in English if input is non-English
            is_from_transcription=is_from_transcription,  # Flag for transcription error handling
            transcription_language=transcription_language  # Language of original speech
        )

        print(f"\n{'='*70}")
        print(f"✅ SUMMARY COMPLETE")
        print(f"{'='*70}")
        if 'speakers' in result:
            print(f"Speakers identified: {result['speakers']}")
        if 'timeline' in result:
            print(f"Timeline events: {len(result.get('timeline', []))}")
        if 'clinical_summary' in result:
            cc = result['clinical_summary'].get('chief_complaint', 'N/A')
            print(f"Chief complaint: {cc[:100]}...")
        print(f"{'='*70}\n")

        # Create a simple text summary for backward compatibility with frontend
        simple_summary = ""
        if 'clinical_summary' in result:
            cs = result['clinical_summary']
            simple_summary = f"{cs.get('chief_complaint', '')}\n\n{cs.get('history_present_illness', '')}"

        # Build unified consultation data format matching database columns
        # AI-specific fields are set to null/empty - populated after analyze is called
        consultation_data = {
            # Transcript data
            "consultation_text": simple_summary,  # Summary text for display
            "original_transcript": original_text if original_text else text,  # Original language transcript
            "translated_transcript": text if has_original else None,  # English translation (if different from original)
            "transcription_language": result.get('detected_language'),

            # Patient snapshot - to be filled by frontend with patient details
            "patient_snapshot": patient_info or {},

            # AI Analysis fields - NA until analyze is called
            "analysis_result": None,
            "diagnoses": [],
            "guidelines_found": [],

            # Metadata
            "consultation_duration_seconds": result.get('metadata', {}).get('consultation_duration_seconds'),
            "location_detected": result.get('metadata', {}).get('location'),
            "backend_api_version": "1.0.0",

            # Full summary data for reference
            "summary_data": {
                "speakers": result.get('speakers'),
                "metadata": result.get('metadata'),
                "timeline": result.get('timeline'),
                "clinical_summary": result.get('clinical_summary'),
                "key_concerns": result.get('key_concerns'),
                "recommendations_given": result.get('recommendations_given'),
                "follow_up": result.get('follow_up')
            }
        }

        return {
            "success": True,
            "summary": simple_summary,  # Simple text for frontend compatibility
            "consultation_data": consultation_data,  # Unified format for saving
            **result  # Full structured data for backward compatibility
        }

    except Exception as e:
        print(f"❌ Summarization error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")


@app.get("/api/get-transcription-token")
async def get_transcription_token():
    """
    Generate a temporary token for ElevenLabs speech-to-text WebSocket connection

    This endpoint provides secure client-side access to ElevenLabs by generating
    a single-use token that expires after 15 minutes.

    Returns:
        JSON with temporary token for WebSocket authentication
    """
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_key:
        raise HTTPException(
            status_code=503,
            detail="Transcription service not configured. ELEVENLABS_API_KEY is required."
        )

    try:
        print("🔑 Generating ElevenLabs temporary token...")

        # Call ElevenLabs API to generate single-use token
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe",
                headers={"xi-api-key": elevenlabs_key}
            )
            response.raise_for_status()
            data = response.json()

        print(f"✅ Token generated (expires in 15 minutes)")

        return {
            "token": data["token"],
            "model": "scribe_v2_realtime",
            "provider": "elevenlabs"
        }

    except Exception as e:
        print(f"❌ Token generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Token generation failed: {str(e)}")


@app.get("/api/get-sarvam-token")
async def get_sarvam_token():
    """
    Return the Sarvam API key for WebSocket connection (Indian languages)

    Sarvam AI is used for Indian language transcription and translation.
    The API key is passed as a query parameter to the WebSocket endpoint.

    Returns:
        JSON with API key for WebSocket authentication
    """
    sarvam_key = os.getenv("SARVAM_API_KEY")
    if not sarvam_key:
        raise HTTPException(
            status_code=503,
            detail="Sarvam transcription service not configured. SARVAM_API_KEY is required."
        )

    print("🔑 Providing Sarvam API key for Indian language transcription")

    return {
        "api_key": sarvam_key,
        "model": "saaras:v2",
        "provider": "sarvam"
    }


@app.post("/api/diarize")
async def diarize_audio(
    audio: UploadFile = File(...),
    num_speakers: Optional[int] = None,
    diarization_threshold: float = 0.22
):
    """
    Perform speaker diarization on audio using ElevenLabs Scribe v1 API

    This endpoint uses the batch Scribe v1 model which supports speaker segmentation.
    Returns word-level timestamps with speaker IDs for multi-speaker conversations.

    Args:
        audio: Audio file (webm, wav, mp3, etc.)
        num_speakers: Optional expected number of speakers (if known)
        diarization_threshold: Threshold for speaker change detection (0.1-0.4, default 0.22)

    Returns:
        {
            "success": true,
            "segments": [{"speaker_id": "speaker_1", "text": "...", "start_time": 0.0, "end_time": 1.5}],
            "detected_speakers": ["speaker_1", "speaker_2", ...],
            "full_transcript": "complete text"
        }
    """
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_key:
        raise HTTPException(
            status_code=503,
            detail="Diarization service not configured. ELEVENLABS_API_KEY is required."
        )

    try:
        print(f"🎤 Diarizing audio file: {audio.filename}")

        # Read audio content
        content = await audio.read()
        audio_size_kb = len(content) / 1024
        print(f"📊 Audio file size: {audio_size_kb:.2f} KB ({len(content)} bytes)")

        # Save to temporary file
        # Note: ElevenLabs Scribe v1 may prefer common formats like mp3, wav
        # Convert webm to mp3 if needed
        import subprocess

        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_file.write(content)
            webm_path = temp_file.name

        # Convert to mp3 format which is more universally supported
        mp3_path = webm_path.replace('.webm', '.mp3')
        try:
            # Use ffmpeg to convert webm to mp3
            result = subprocess.run(
                ['ffmpeg', '-i', webm_path, '-acodec', 'libmp3lame', '-ab', '128k', mp3_path, '-y'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                print(f"⚠️  FFmpeg conversion failed: {result.stderr}")
                print(f"   Trying with webm directly...")
                temp_path = webm_path
            else:
                print(f"✅ Converted webm to mp3 for better compatibility")
                os.unlink(webm_path)  # Remove webm file
                temp_path = mp3_path
        except FileNotFoundError:
            print("⚠️  FFmpeg not found - using webm directly (may fail)")
            temp_path = webm_path
        except Exception as e:
            print(f"⚠️  Conversion error: {e} - using webm directly")
            temp_path = webm_path

        try:
            start = time.time()

            # Call ElevenLabs Scribe v1 API with diarization
            async with httpx.AsyncClient(timeout=120.0) as http_client:
                with open(temp_path, 'rb') as audio_file:
                    # Set correct MIME type based on file format
                    mime_type = 'audio/mpeg' if temp_path.endswith('.mp3') else 'audio/webm'
                    filename = 'audio.mp3' if temp_path.endswith('.mp3') else (audio.filename or 'audio.webm')
                    # IMPORTANT: ElevenLabs expects 'file' not 'audio'
                    files = {'file': (filename, audio_file, mime_type)}

                    # Build parameters
                    params = {
                        'model_id': 'scribe_v1',
                        'diarize': 'true',
                        'diarization_threshold': str(diarization_threshold),
                        'timestamps_granularity': 'word'
                    }

                    if num_speakers:
                        params['num_speakers'] = str(num_speakers)

                    response = await http_client.post(
                        'https://api.elevenlabs.io/v1/speech-to-text',
                        headers={'xi-api-key': elevenlabs_key},
                        files=files,
                        data=params
                    )

                    # Debug: Log response status and body
                    if not response.is_success:
                        error_body = response.text
                        print(f"❌ ElevenLabs API Error ({response.status_code}): {error_body}")

                    response.raise_for_status()
                    data = response.json()

            latency = time.time() - start

            # Debug: Log raw API response
            print(f"📋 Raw API response keys: {list(data.keys())}")
            if 'words' in data and len(data['words']) > 0:
                print(f"📝 First word example: {data['words'][0]}")
                print(f"📝 Total words: {len(data['words'])}")

            # Parse response - Scribe v1 with diarization returns:
            # {
            #   "text": "full transcript",
            #   "words": [{"text": "...", "start": 0.0, "end": 0.5, "speaker": "speaker_1"}, ...]
            # }

            full_transcript = data.get('text', '')
            words = data.get('words', [])

            # Group words by speaker into segments
            segments = []
            detected_speakers = set()

            if words:
                current_speaker = words[0].get('speaker_id')
                current_text = []
                segment_start = words[0].get('start', 0.0)

                for word_data in words:
                    speaker = word_data.get('speaker_id')
                    word_text = word_data.get('text', '')

                    detected_speakers.add(speaker)

                    if speaker == current_speaker:
                        current_text.append(word_text)
                    else:
                        # Speaker changed - save current segment
                        segments.append({
                            'speaker_id': current_speaker,
                            'text': ' '.join(current_text),
                            'start_time': segment_start,
                            'end_time': word_data.get('start', 0.0)
                        })

                        # Start new segment
                        current_speaker = speaker
                        current_text = [word_text]
                        segment_start = word_data.get('start', 0.0)

                # Add final segment
                if current_text:
                    segments.append({
                        'speaker_id': current_speaker,
                        'text': ' '.join(current_text),
                        'start_time': segment_start,
                        'end_time': words[-1].get('end', 0.0)
                    })

            print(f"✅ Diarization complete in {latency:.2f}s")
            print(f"👥 Detected {len(detected_speakers)} speakers: {sorted(detected_speakers)}")
            print(f"📝 Generated {len(segments)} speaker segments")

            return {
                'success': True,
                'segments': segments,
                'detected_speakers': sorted(list(detected_speakers)),
                'full_transcript': full_transcript,
                'latency_seconds': round(latency, 2),
                'model': 'elevenlabs/scribe_v1'
            }

        finally:
            # Clean up temp file
            os.unlink(temp_path)

    except Exception as e:
        print(f"❌ Diarization error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Diarization failed: {str(e)}")


@app.post("/api/diarize-sarvam")
async def diarize_audio_sarvam(
    audio: UploadFile = File(...),
    num_speakers: int = 2
):
    """
    Perform speaker diarization on audio using Sarvam AI Batch API

    This endpoint uses Sarvam's speech-to-text-translate batch API with diarization
    for Indian language consultations. Returns diarized transcript with speaker labels
    and automatic English translation.

    Args:
        audio: Audio file (webm, wav, mp3, etc.)
        num_speakers: Expected number of speakers (default 2 for doctor-patient)

    Returns:
        {
            "success": true,
            "segments": [{"speaker_id": "speaker 1", "text": "...", "start_time": 0.0, "end_time": 1.5}],
            "detected_speakers": ["speaker 1", "speaker 2"],
            "full_transcript": "complete translated text in English"
        }
    """
    from sarvamai import SarvamAI

    sarvam_key = os.getenv("SARVAM_API_KEY")
    if not sarvam_key:
        raise HTTPException(
            status_code=503,
            detail="Sarvam diarization service not configured. SARVAM_API_KEY is required."
        )

    try:
        print(f"🎤 Sarvam diarization for: {audio.filename}")

        # Read audio content
        content = await audio.read()
        audio_size_kb = len(content) / 1024
        print(f"📊 Audio file size: {audio_size_kb:.2f} KB")

        # Save to temporary file for conversion
        import subprocess

        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_file.write(content)
            webm_path = temp_file.name

        # Convert to mp3 for Sarvam (better compatibility)
        mp3_path = webm_path.replace('.webm', '.mp3')
        try:
            result = subprocess.run(
                ['ffmpeg', '-i', webm_path, '-acodec', 'libmp3lame', '-ab', '128k', mp3_path, '-y'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                print(f"⚠️  FFmpeg conversion failed, using webm")
                temp_path = webm_path
            else:
                print(f"✅ Converted to mp3")
                os.unlink(webm_path)
                temp_path = mp3_path
        except Exception as e:
            print(f"⚠️  Conversion error: {e}")
            temp_path = webm_path

        try:
            start = time.time()

            # Initialize Sarvam client
            client = SarvamAI(api_subscription_key=sarvam_key)

            # Create batch job with diarization
            print(f"📤 Creating Sarvam batch job with diarization (speakers={num_speakers})...")
            job = client.speech_to_text_translate_job.create_job(
                model="saaras:v2.5",
                with_diarization=True,
                num_speakers=num_speakers
            )

            job_id = job.job_id
            print(f"📋 Job created: {job_id}")

            # Upload audio file
            print(f"📤 Uploading audio file: {temp_path}")
            upload_success = job.upload_files([temp_path], timeout=60.0)
            if not upload_success:
                raise Exception("Failed to upload audio file to Sarvam")
            print(f"✅ Audio file uploaded")

            # Start the job
            print(f"▶️  Starting job...")
            job.start()

            # Wait for job completion (uses SDK's built-in polling)
            print(f"⏳ Waiting for job completion...")
            job.wait_until_complete(poll_interval=3, timeout=120)

            latency = time.time() - start
            print(f"✅ Job completed after {latency:.1f}s")

            # Get results
            results = job.get_file_results()
            print(f"📥 Got results: {results}")

            # Extract diarized transcript from results
            full_transcript = ""
            diarized = []

            if results and 'successful' in results:
                for file_result in results['successful']:
                    print(f"📄 File result keys: {file_result.keys() if isinstance(file_result, dict) else type(file_result)}")
                    print(f"📄 File result: {file_result}")
                    if 'transcript' in file_result:
                        full_transcript = file_result.get('transcript', '')
                    if 'diarized_transcript' in file_result:
                        diarized = file_result.get('diarized_transcript', [])

            # Convert Sarvam format to our standard format
            segments = []
            detected_speakers = set()

            if diarized:
                for entry in diarized:
                    speaker = entry.get('speaker', 'speaker 1')
                    detected_speakers.add(speaker)
                    segments.append({
                        'speaker_id': speaker,
                        'text': entry.get('text', ''),
                        'start_time': entry.get('start', 0.0),
                        'end_time': entry.get('end', 0.0)
                    })

            print(f"✅ Sarvam diarization complete in {latency:.2f}s")
            print(f"👥 Detected {len(detected_speakers)} speakers")
            print(f"📝 Generated {len(segments)} speaker segments")

            return {
                'success': True,
                'segments': segments,
                'detected_speakers': sorted(list(detected_speakers)) or ['speaker 1', 'speaker 2'],
                'full_transcript': full_transcript,
                'latency_seconds': round(latency, 2),
                'model': 'sarvam/saaras:v2.5'
            }

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        print(f"❌ Sarvam diarization error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Sarvam diarization failed: {str(e)}")


class SpeakerRoleRequest(BaseModel):
    segments: list[dict]  # List of {speaker_id, text, start_time, end_time}
    language: Optional[str] = "en-IN"


@app.post("/api/identify-speaker-roles")
async def identify_speaker_roles(request: SpeakerRoleRequest):
    """
    Identify which speaker is the doctor vs patient using LLM analysis

    Analyzes the FULL conversation to determine speaker roles.
    Uses Claude Haiku for fast, cost-effective inference.

    Args:
        segments: ALL diarized segments from the consultation
        language: Conversation language (for context)

    Returns:
        Speaker role mapping: {"speaker_0": "Doctor", "speaker_1": "Patient"}
    """
    try:
        import anthropic

        anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Format conversation for analysis
        conversation_text = ""
        for seg in request.segments:  # Use ALL segments for better accuracy
            conversation_text += f"{seg['speaker_id']}: {seg['text']}\n"

        print(f"🔍 Identifying speaker roles from {len(request.segments)} segments (full consultation)")

        # Prompt for role identification
        prompt = f"""You are analyzing a medical consultation conversation between a doctor and a patient.
The conversation has been transcribed with speaker diarization, identifying speakers as "speaker_0" and "speaker_1".

Your task: Determine which speaker is the DOCTOR and which is the PATIENT.

Conversation transcript:
{conversation_text}

Analysis guidelines:
- Doctors typically: ask diagnostic questions, use medical terminology, lead the consultation, give advice
- Patients typically: describe symptoms, answer questions about their health, express concerns
- Look at speech patterns, question types, and conversational dynamics

Respond with ONLY a JSON object in this exact format (no other text):
{{"speaker_0": "Doctor", "speaker_1": "Patient"}}
OR
{{"speaker_0": "Patient", "speaker_1": "Doctor"}}

Your response:"""

        # Call Claude Haiku for fast inference
        start_time = time.time()

        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            temperature=0,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        latency = time.time() - start_time

        # Parse response
        response_text = response.content[0].text.strip()

        # Extract JSON (handle markdown code blocks if present)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        role_mapping = json.loads(response_text)

        print(f"✅ Speaker roles identified in {latency:.2f}s: {role_mapping}")

        return {
            "success": True,
            "role_mapping": role_mapping,
            "latency_seconds": round(latency, 2),
            "model": "claude-haiku-4-5-20251001",
            "segments_analyzed": len(request.segments)
        }

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse LLM response: {response_text}")
        # Fallback: default mapping
        return {
            "success": False,
            "role_mapping": {"speaker_0": "Speaker 1", "speaker_1": "Speaker 2"},
            "error": "Failed to parse LLM response",
            "fallback": True
        }
    except Exception as e:
        print(f"❌ Speaker role identification error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Speaker role identification failed: {str(e)}")


class RerunTranscriptionRequest(BaseModel):
    consultation_id: str  # UUID of consultation to reprocess
    language: Optional[str] = None  # Optional language override


@app.post("/api/rerun-transcription")
async def rerun_transcription(request: RerunTranscriptionRequest):
    """
    Rerun transcription/diarization on a past consultation's audio file.

    Processes the entire audio file at once with speaker diarization and role
    identification (Doctor vs Patient), then updates the consultation record.

    Args:
        consultation_id: UUID of the consultation to reprocess
        language: Optional language code override (e.g., "en-IN", "hi-IN")

    Returns:
        {
            "success": true,
            "consultation_id": "uuid",
            "transcript": "Doctor: ... Patient: ...",
            "language": "en-IN",
            "provider": "sarvam" | "elevenlabs",
            "speaker_roles": {"speaker_0": "Doctor", "speaker_1": "Patient"},
            "segments_count": 42,
            "processing_time_seconds": 45.2
        }
    """
    import anthropic

    start_time = time.time()
    temp_audio_path = None

    try:
        # 1. Validate and fetch consultation
        print(f"🔄 Rerun transcription request for consultation {request.consultation_id}")

        supabase = get_supabase_client()

        # Fetch consultation with appointment data for language detection
        consultation_result = supabase.from_('consultations').select(
            '*'
        ).eq('id', request.consultation_id).single().execute()

        if not consultation_result.data:
            raise HTTPException(status_code=404, detail="Consultation not found")

        consultation = consultation_result.data

        if not consultation.get('audio_url'):
            raise HTTPException(status_code=400, detail="No audio file available for this consultation")

        print(f"✅ Found consultation with audio URL: {consultation['audio_url'][:50]}...")

        # 2. Download audio from GCS
        audio_url = consultation['audio_url']

        # Parse GCS URL: https://storage.googleapis.com/aneya-audio-recordings/recordings/...
        if 'aneya-audio-recordings' not in audio_url:
            raise HTTPException(status_code=400, detail="Invalid audio URL format")

        blob_path = audio_url.split('aneya-audio-recordings/')[-1]
        print(f"📥 Downloading audio from GCS: {blob_path}")

        bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_path)

        if not blob.exists():
            raise HTTPException(status_code=404, detail="Audio file not found in storage")

        audio_bytes = blob.download_as_bytes()
        print(f"✅ Downloaded {len(audio_bytes)} bytes")

        # Save to temporary file
        temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix='.webm')
        temp_audio.write(audio_bytes)
        temp_audio.close()
        temp_audio_path = temp_audio.name

        # 3. Detect language
        language = request.language or consultation.get('transcription_language') or 'en-IN'

        # Determine provider based on language
        use_sarvam = language in [
            'en-IN', 'hi-IN', 'bn-IN', 'gu-IN', 'kn-IN',
            'ml-IN', 'mr-IN', 'od-IN', 'pa-IN', 'ta-IN', 'te-IN'
        ]

        provider = "sarvam" if use_sarvam else "elevenlabs"
        print(f"🌐 Language: {language}, Provider: {provider}")

        # 4. Run diarization
        print(f"🎙️ Starting diarization with {provider}...")

        if use_sarvam:
            diarization_result = await _diarize_chunk_sarvam(
                temp_audio_path,
                language,
                num_speakers=2
            )
        else:
            diarization_result = await _diarize_chunk_elevenlabs(
                temp_audio_path,
                num_speakers=2,
                threshold=0.22
            )

        segments = diarization_result.get('segments', [])
        print(f"✅ Diarization complete: {len(segments)} segments")

        if not segments:
            raise HTTPException(status_code=500, detail="Diarization produced no segments")

        # 5. Identify speaker roles using Claude Haiku
        print(f"🔍 Identifying speaker roles...")

        anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Format conversation for analysis (use first 50 segments for efficiency)
        conversation_text = ""
        for seg in segments[:50]:
            conversation_text += f"{seg['speaker_id']}: {seg['text']}\n"

        # Prompt for role identification
        prompt = f"""You are analyzing a medical consultation conversation between a doctor and a patient.
The conversation has been transcribed with speaker diarization, identifying speakers as "speaker_0" and "speaker_1".

Your task: Determine which speaker is the DOCTOR and which is the PATIENT.

Conversation transcript:
{conversation_text}

Analysis guidelines:
- Doctors typically: ask diagnostic questions, use medical terminology, lead the consultation, give advice
- Patients typically: describe symptoms, answer questions about their health, express concerns
- Look at speech patterns, question types, and conversational dynamics

Respond with ONLY a JSON object in this exact format (no other text):
{{"speaker_0": "Doctor", "speaker_1": "Patient"}}
OR
{{"speaker_0": "Patient", "speaker_1": "Doctor"}}

Your response:"""

        response = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            temperature=0,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        response_text = response.content[0].text.strip()

        # Extract JSON (handle markdown code blocks if present)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        role_mapping = json.loads(response_text)
        print(f"✅ Speaker roles identified: {role_mapping}")

        # 6. Format transcript with speaker roles
        formatted_transcript = ""
        for seg in segments:
            speaker_role = role_mapping.get(seg['speaker_id'], seg['speaker_id'])
            formatted_transcript += f"{speaker_role}: {seg['text']}\n"

        print(f"✅ Formatted transcript: {len(formatted_transcript)} characters")

        # 7. Update database
        print(f"💾 Updating consultation record...")

        supabase.from_('consultations').update({
            'original_transcript': formatted_transcript,
            'transcription_language': language
        }).eq('id', request.consultation_id).execute()

        print(f"✅ Database updated successfully")

        processing_time = time.time() - start_time

        # 8. Return response
        return {
            "success": True,
            "consultation_id": request.consultation_id,
            "transcript": formatted_transcript,
            "language": language,
            "provider": provider,
            "speaker_roles": role_mapping,
            "segments_count": len(segments),
            "processing_time_seconds": round(processing_time, 2)
        }

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse speaker role response: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to identify speaker roles")
    except Exception as e:
        print(f"❌ Rerun transcription error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Transcription rerun failed: {str(e)}")
    finally:
        # Cleanup temporary file
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.unlink(temp_audio_path)
                print(f"🧹 Cleaned up temporary file")
            except Exception as e:
                print(f"⚠️ Failed to cleanup temp file: {e}")


@app.post("/api/diarize-chunk")
async def diarize_audio_chunk(
    audio: UploadFile = File(...),
    chunk_index: int = Form(0),
    chunk_start: float = Form(0.0),
    chunk_end: float = Form(30.0),
    num_speakers: Optional[int] = Form(None),
    diarization_threshold: float = Form(0.22),
    language: Optional[str] = Form(None),
    appointment_id: Optional[str] = Form(None),
    patient_id: Optional[str] = Form(None),
    appointment_type: Optional[str] = Form(None)
):
    """
    Diarize audio chunk with overlap metadata for speaker ID matching

    This endpoint processes 30-second audio chunks during recording, enabling
    real-time speaker-labeled transcription. Returns segments with overlap
    statistics for cross-chunk speaker matching.

    Args:
        audio: Audio chunk file (webm, 30 seconds)
        chunk_index: Chunk number (0, 1, 2, ...)
        chunk_start: Start time in full recording (seconds)
        chunk_end: End time in full recording (seconds)
        num_speakers: Optional expected number of speakers
        diarization_threshold: Speaker change detection threshold
        language: Language code (e.g., "en-IN", "hi-IN")

    Returns:
        {
            "success": true,
            "chunk_index": 0,
            "chunk_start": 0.0,
            "chunk_end": 30.0,
            "segments": [...],
            "detected_speakers": ["speaker_0", "speaker_1"],
            "start_overlap_stats": {...},
            "end_overlap_stats": {...},
            "latency_seconds": 2.3
        }
    """
    print(f"🎬 Chunk {chunk_index}: Received {audio.filename} ({chunk_start:.1f}s-{chunk_end:.1f}s)")

    # IMPORTANT: We use Sarvam for Indian languages despite the added complexity and slower processing
    # Reason: ElevenLabs performs so poorly on Indian languages (Hindi, Tamil, Telugu, etc.) that
    # it's completely unusable - transcriptions are inaccurate and speaker labels are wrong.
    # Sarvam provides high-quality transcription and diarization for Indian languages, making the
    # extra complexity (batch API, longer wait times, FFmpeg conversion) worthwhile for usability.
    #
    # Trade-off: Sarvam's batch API is slower (jobs can take 30-120s) vs ElevenLabs (5-10s),
    # but accurate transcription is more valuable than speed for Indian language consultations.
    use_sarvam = language and language in [
        'en-IN', 'hi-IN', 'bn-IN', 'gu-IN', 'kn-IN', 'ml-IN',
        'mr-IN', 'od-IN', 'pa-IN', 'ta-IN', 'te-IN'
    ]

    try:
        # Read audio content
        content = await audio.read()
        audio_size_kb = len(content) / 1024
        print(f"📦 Audio size: {audio_size_kb:.2f} KB")

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_file.write(content)
            webm_path = temp_file.name

        # Convert to MP3 for Sarvam (required for reliability with Indian languages)
        # ElevenLabs supports webm directly, but Sarvam works better with MP3
        if use_sarvam:
            mp3_path = webm_path.replace('.webm', '.mp3')
            try:
                import subprocess

                # First, diagnose the WebM file with ffprobe
                probe_result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_format', '-show_streams', webm_path],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                print(f"🔍 WebM probe results:")
                print(f"   codec info: {probe_result.stdout[:300]}")

                # Add -vn flag to ignore video streams (WebM might have video metadata)
                # Add -nostdin to prevent FFmpeg from reading stdin
                result = subprocess.run(
                    [
                        'ffmpeg',
                        '-i', webm_path,
                        '-vn',  # Ignore video streams
                        '-acodec', 'libmp3lame',
                        '-ab', '128k',
                        '-nostdin',  # Prevent FFmpeg from reading stdin
                        '-y',  # Overwrite output
                        mp3_path
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30  # Increased from 15s
                )
                if result.returncode == 0:
                    temp_path = mp3_path
                    os.unlink(webm_path)
                    print(f"✅ Converted to MP3: {mp3_path}")
                else:
                    print(f"⚠️  FFmpeg conversion failed (exit {result.returncode}), using WebM")
                    print(f"    Full stderr: {result.stderr}")  # Print FULL stderr
                    print(f"    Full stdout: {result.stdout}")  # Print FULL stdout
                    print(f"    Using WebM directly (may fail on Sarvam API)")
                    temp_path = webm_path
            except Exception as e:
                print(f"⚠️  FFmpeg error: {e}")
                print(f"    Using WebM directly")
                temp_path = webm_path
        else:
            # ElevenLabs - use webm directly (no conversion needed)
            temp_path = webm_path
            print(f"✅ Using WebM directly for ElevenLabs")

        try:
            start_time = time.time()

            if use_sarvam:
                # Call Sarvam diarization
                result_data = await _diarize_chunk_sarvam(temp_path, language, num_speakers)
            else:
                # Call ElevenLabs diarization
                result_data = await _diarize_chunk_elevenlabs(
                    temp_path, num_speakers, diarization_threshold
                )

            latency = time.time() - start_time

            segments = result_data['segments']
            detected_speakers = result_data['detected_speakers']

            print(f"  ✓ {latency:.1f}s | Speakers: {detected_speakers} | Segments: {len(segments)}")

            # Calculate overlap statistics
            # Overlap duration is 10 seconds (configurable)
            OVERLAP_DURATION = 10.0

            # Start overlap: first 10 seconds of chunk (shared with previous chunk)
            start_overlap_stats = {}
            if chunk_index > 0:
                start_overlap_stats = _calculate_overlap_stats(
                    segments, 0.0, OVERLAP_DURATION
                )
                if start_overlap_stats:
                    print(f"  📍 Start overlap (0-{OVERLAP_DURATION}s): ", end='')
                    print(', '.join([f"{sid}={st['duration']:.1f}s" for sid, st in start_overlap_stats.items()]))

            # End overlap: last 10 seconds of chunk (shared with next chunk)
            chunk_duration = chunk_end - chunk_start
            end_overlap_start = chunk_duration - OVERLAP_DURATION
            end_overlap_stats = _calculate_overlap_stats(
                segments, end_overlap_start, chunk_duration
            )
            if end_overlap_stats:
                print(f"  📍 End overlap ({end_overlap_start:.1f}-{chunk_duration:.1f}s): ", end='')
                print(', '.join([f"{sid}={st['duration']:.1f}s" for sid, st in end_overlap_stats.items()]))

            # Determine form type from appointment_type if provided
            form_type = None
            form_updates = {}
            form_confidence = {}

            if appointment_type:
                # Map appointment_type to form_type
                if appointment_type == 'obgyn_infertility' or 'infertility' in appointment_type.lower():
                    form_type = 'infertility'
                elif appointment_type == 'obgyn_antenatal' or 'antenatal' in appointment_type.lower():
                    form_type = 'antenatal'
                elif appointment_type.startswith('obgyn_'):
                    form_type = 'obgyn'

                print(f"  📋 Determined form_type: {form_type} from appointment_type: {appointment_type}")

            return {
                'success': True,
                'chunk_index': chunk_index,
                'chunk_start': chunk_start,
                'chunk_end': chunk_end,
                'segments': segments,
                'detected_speakers': detected_speakers,
                'start_overlap_stats': start_overlap_stats,
                'end_overlap_stats': end_overlap_stats,
                'latency_seconds': round(latency, 2),
                'model': result_data.get('model', 'unknown'),
                'form_type': form_type,
                'form_updates': form_updates,
                'form_confidence': form_confidence
            }

        finally:
            # Cleanup temp files
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        print(f"❌ Chunk {chunk_index} error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chunk diarization failed: {str(e)}")


@app.post("/api/process-final-chunk-async")
async def process_final_chunk_async(
    background_tasks: BackgroundTasks,
    consultation_id: str = Form(...),
    audio: UploadFile = File(...),
    chunk_index: int = Form(0),
    chunk_start: float = Form(0.0),
    chunk_end: float = Form(30.0),
    language: Optional[str] = Form(None),
    num_speakers: Optional[int] = Form(None),
    diarization_threshold: float = Form(0.22)
):
    """
    Process final audio chunk asynchronously and update consultation

    This endpoint returns immediately after queuing the background task.
    The consultation is updated via Supabase when processing completes.

    Args:
        consultation_id: UUID of the consultation to update
        audio: Audio chunk file (webm)
        chunk_index: Chunk number
        chunk_start: Start time in full recording (seconds)
        chunk_end: End time in full recording (seconds)
        language: Language code (e.g., "en-IN", "hi-IN")
        num_speakers: Expected number of speakers
        diarization_threshold: Speaker change detection threshold

    Returns:
        {
            "success": true,
            "consultation_id": "...",
            "message": "Processing in background"
        }
    """
    print(f"🚀 Starting async processing for consultation {consultation_id}")

    # Read audio content before background task (file handles can't be passed)
    audio_content = await audio.read()
    audio_filename = audio.filename or "chunk.webm"

    # Queue background processing
    background_tasks.add_task(
        _process_final_chunk_background,
        consultation_id=consultation_id,
        audio_content=audio_content,
        audio_filename=audio_filename,
        chunk_index=chunk_index,
        chunk_start=chunk_start,
        chunk_end=chunk_end,
        language=language,
        num_speakers=num_speakers,
        diarization_threshold=diarization_threshold
    )

    return {
        "success": True,
        "consultation_id": consultation_id,
        "message": "Processing in background"
    }


async def _process_final_chunk_background(
    consultation_id: str,
    audio_content: bytes,
    audio_filename: str,
    chunk_index: int,
    chunk_start: float,
    chunk_end: float,
    language: Optional[str],
    num_speakers: Optional[int],
    diarization_threshold: float
):
    """Background task to process final chunk and update consultation"""
    supabase = get_supabase_client()

    try:
        # Update status to 'processing'
        print(f"🔄 Updating consultation {consultation_id} to 'processing'")
        supabase.table('consultations').update({
            'transcription_status': 'processing',
            'transcription_started_at': 'now()'
        }).eq('id', consultation_id).execute()

        # Save audio to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as f:
            f.write(audio_content)
            temp_path = f.name

        try:
            # Determine which service to use (Sarvam for Indian languages)
            use_sarvam = language and language in [
                'en-IN', 'hi-IN', 'bn-IN', 'gu-IN', 'kn-IN', 'ml-IN',
                'mr-IN', 'od-IN', 'pa-IN', 'ta-IN', 'te-IN'
            ]

            # Convert WebM to MP3 if using Sarvam (it requires MP3)
            if use_sarvam and temp_path.endswith('.webm'):
                mp3_path = temp_path.replace('.webm', '.mp3')
                import subprocess
                subprocess.run([
                    'ffmpeg', '-i', temp_path, '-ar', '16000', '-ac', '1',
                    '-b:a', '128k', mp3_path, '-y'
                ], check=True, capture_output=True)
                os.unlink(temp_path)
                temp_path = mp3_path

            # Call diarization (reuse existing functions)
            print(f"🎬 Diarizing chunk {chunk_index} (language: {language}, service: {'Sarvam' if use_sarvam else 'ElevenLabs'})")

            if use_sarvam:
                result = await _diarize_chunk_sarvam(temp_path, language, num_speakers)
            else:
                result = await _diarize_chunk_elevenlabs(temp_path, num_speakers, diarization_threshold)

            # Format transcript as "Speaker: text" format
            segments = result.get('segments', [])
            if segments:
                segments_sorted = sorted(segments, key=lambda s: s.get('start_time', 0))
                transcript_lines = []
                for seg in segments_sorted:
                    speaker = seg.get('speaker_role') or seg.get('speaker_id', 'Unknown')
                    text = seg.get('text', '')
                    transcript_lines.append(f"{speaker}: {text}")

                formatted_transcript = '\n\n'.join(transcript_lines)

                # Update consultation with results
                print(f"✅ Updating consultation {consultation_id} with diarized transcript")
                supabase.table('consultations').update({
                    'consultation_text': formatted_transcript,
                    'transcription_status': 'completed',
                    'transcription_completed_at': 'now()'
                }).eq('id', consultation_id).execute()

                print(f"✅ Consultation {consultation_id} updated successfully")
            else:
                # No segments found - mark as failed
                print(f"⚠️  No segments found for consultation {consultation_id}")
                supabase.table('consultations').update({
                    'transcription_status': 'failed',
                    'transcription_error': 'No speaker segments detected',
                    'transcription_completed_at': 'now()'
                }).eq('id', consultation_id).execute()

        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        print(f"❌ Background processing failed for consultation {consultation_id}: {e}")
        import traceback
        traceback.print_exc()

        try:
            # Update consultation with error status
            supabase.table('consultations').update({
                'transcription_status': 'failed',
                'transcription_error': str(e),
                'transcription_completed_at': 'now()'
            }).eq('id', consultation_id).execute()
        except Exception as update_error:
            print(f"❌ Failed to update error status: {update_error}")


async def _diarize_chunk_elevenlabs(audio_path: str, num_speakers: Optional[int], threshold: float) -> dict:
    """Diarize chunk using ElevenLabs Scribe v1"""
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_key:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY not configured")

    async with httpx.AsyncClient(timeout=60.0) as http_client:
        with open(audio_path, 'rb') as audio_file:
            mime_type = 'audio/mpeg' if audio_path.endswith('.mp3') else 'audio/webm'
            filename = os.path.basename(audio_path)
            files = {'file': (filename, audio_file, mime_type)}

            params = {
                'model_id': 'scribe_v1',
                'diarize': 'true',
                'diarization_threshold': str(threshold),
                'timestamps_granularity': 'word'
            }

            if num_speakers:
                params['num_speakers'] = str(num_speakers)

            response = await http_client.post(
                'https://api.elevenlabs.io/v1/speech-to-text',
                headers={'xi-api-key': elevenlabs_key},
                files=files,
                params=params
            )

    response.raise_for_status()
    data = response.json()

    # Group words by speaker into segments
    segments = _group_words_by_speaker(data.get('words', []))
    detected_speakers = list(set(seg['speaker_id'] for seg in segments))

    return {
        'segments': segments,
        'detected_speakers': detected_speakers,
        'model': 'elevenlabs/scribe_v1'
    }


async def _diarize_chunk_sarvam(audio_path: str, language: str, num_speakers: Optional[int]) -> dict:
    """Diarize chunk using Sarvam AI"""
    from sarvamai import SarvamAI

    sarvam_key = os.getenv("SARVAM_API_KEY")
    if not sarvam_key:
        raise HTTPException(status_code=503, detail="SARVAM_API_KEY not configured")

    try:
        # Initialize Sarvam client
        client = SarvamAI(api_subscription_key=sarvam_key)

        # Create batch job with diarization (same pattern as working endpoint)
        print(f"📤 Creating Sarvam batch job with diarization...")
        job = client.speech_to_text_translate_job.create_job(
            model="saaras:v2.5",
            with_diarization=True,
            num_speakers=num_speakers or 2
        )

        job_id = job.job_id
        print(f"📋 Job created: {job_id}")

        # Upload audio file
        print(f"📤 Uploading audio file: {audio_path}")
        upload_success = job.upload_files([audio_path], timeout=60.0)
        if not upload_success:
            raise Exception("Failed to upload audio file to Sarvam")
        print(f"✅ Audio file uploaded")

        # Start the job
        print(f"▶️  Starting job...")
        job.start()

        # Wait for job completion (same as working endpoint)
        print(f"⏳ Waiting for job completion...")
        job.wait_until_complete(poll_interval=3, timeout=120)

        # Small delay to ensure Sarvam API has finalized the job
        # (prevents race condition where get_file_results returns empty)
        time.sleep(2)

        # Verify job completed successfully
        job_status = job.get_status()
        print(f"📊 Job status after wait: {job_status}")

        # Check if job_status has job_state attribute or is a string
        if hasattr(job_status, 'job_state'):
            state = job_status.job_state
            print(f"✓ Job state: {state}")
        else:
            state = str(job_status)
            print(f"✓ Job state (string): {state}")

        if state.lower() != 'completed':
            # Get more details about why it failed
            error_message = getattr(job_status, 'error_message', 'No error message')
            job_details = getattr(job_status, 'job_details', [])
            raise Exception(
                f"Job did not complete successfully. "
                f"State: {state}, Error: {error_message}, Details: {job_details}"
            )

        # Get results
        print(f"📥 Got results...")
        results = job.get_file_results()
        print(f"📊 Results: {results}")

        segments = []
        detected_speakers = set()

        # Check for failed results first
        if results and 'failed' in results and results['failed']:
            failed_files = results['failed']
            print(f"❌ {len(failed_files)} files failed processing")

            for failed_file in failed_files:
                error_msg = failed_file.get('error_message', 'Unknown error')
                file_name = failed_file.get('file_name', 'unknown')
                status = failed_file.get('status', 'Unknown')
                print(f"   Failed file: {file_name}")
                print(f"   Status: {status}")
                print(f"   Error: {error_msg}")

            # Raise exception instead of silently returning empty segments
            raise Exception(
                f"Sarvam diarization failed: {len(failed_files)} file(s) failed. "
                f"First error: {failed_files[0].get('error_message', 'Unknown')}"
            )

        # Extract diarized transcript from results
        if results and 'successful' in results:
            for file_result in results['successful']:
                print(f"📄 File result: {file_result}")

                # Check for diarized_transcript directly in file_result first
                if 'diarized_transcript' in file_result:
                    diarized = file_result.get('diarized_transcript', [])
                    print(f"✅ Found diarized_transcript directly with {len(diarized)} segments")

                    for entry in diarized:
                        speaker = entry.get('speaker', 'speaker 1')
                        detected_speakers.add(speaker)
                        segments.append({
                            'speaker_id': speaker,
                            'text': entry.get('text', ''),
                            'start_time': entry.get('start', 0.0),
                            'end_time': entry.get('end', 0.0)
                        })
                    break

                # If not in results directly, download from output_file
                elif 'output_file' in file_result:
                    output_filename = file_result.get('output_file')
                    print(f"📄 Need to download output_file: {output_filename}")

                    # Get download link
                    download_response = client.speech_to_text_translate_job.get_download_links(
                        job_id=job_id,
                        files=[output_filename]
                    )

                    if output_filename in download_response.download_urls:
                        download_url = download_response.download_urls[output_filename].file_url
                        print(f"⬇️  Downloading from: {download_url[:50]}...")

                        # Download and parse JSON
                        with httpx.Client(timeout=30.0) as http_client:
                            response = http_client.get(download_url)
                            response.raise_for_status()
                            transcript_data = response.json()

                        print(f"✅ Downloaded transcript data")

                        # Extract diarized transcript from downloaded file
                        if 'diarized_transcript' in transcript_data:
                            diarized = transcript_data.get('diarized_transcript', [])

                            # Handle both dict format (with 'entries' key) and list format
                            entries = []
                            if isinstance(diarized, dict) and 'entries' in diarized:
                                entries = diarized.get('entries', [])
                                print(f"✅ Found {len(entries)} entries in diarized dict")
                            elif isinstance(diarized, list):
                                entries = diarized
                                print(f"✅ Found {len(entries)} entries in diarized list")
                            else:
                                print(f"⚠️  Unexpected diarized type: {type(diarized)}")

                            # Convert Sarvam format to our standard format
                            for entry in entries:
                                if isinstance(entry, dict):
                                    # Handle both field naming conventions
                                    speaker = entry.get('speaker_id', entry.get('speaker', 'speaker 1'))
                                    text = entry.get('transcript', entry.get('text', ''))
                                    start = entry.get('start_time_seconds', entry.get('start', 0.0))
                                    end = entry.get('end_time_seconds', entry.get('end', 0.0))

                                    detected_speakers.add(speaker)
                                    segments.append({
                                        'speaker_id': speaker,
                                        'text': text,
                                        'start_time': start,
                                        'end_time': end
                                    })
                            break
                        else:
                            print(f"⚠️  No diarized_transcript in downloaded file")
                            print(f"    Keys: {list(transcript_data.keys())}")
        else:
            print(f"⚠️  No successful results")
            if results:
                print(f"    Keys: {list(results.keys())}")

        # Validate that we got segments
        if not segments:
            # If job succeeded but no segments, log warning and raise error
            print(f"⚠️  No segments extracted from diarization")
            print(f"   Detected speakers: {detected_speakers}")
            print(f"   This might indicate audio had no speech or very short duration")

            # For chunks, this is likely an error - raise exception
            raise Exception(
                f"Sarvam diarization returned 0 segments despite successful completion. "
                f"Detected {len(detected_speakers)} speakers but no transcript. "
                f"This may indicate the audio chunk is too short or contains no speech."
            )

        return {
            'segments': segments,
            'detected_speakers': sorted(list(detected_speakers)) or ['speaker 1', 'speaker 2'],
            'model': 'sarvam/saaras:v2.5'
        }

    except Exception as e:
        print(f"❌ Sarvam chunk diarization error: {e}")
        raise


def _group_words_by_speaker(words: list) -> list:
    """Group consecutive words by same speaker into segments"""
    if not words:
        return []

    segments = []
    current_speaker = None
    current_segment = []

    for word in words:
        speaker_id = word.get('speaker_id', 'unknown')

        if speaker_id != current_speaker:
            # Save previous segment
            if current_segment:
                segments.append({
                    'speaker_id': current_speaker,
                    'text': ' '.join(w['text'] for w in current_segment),
                    'start_time': current_segment[0]['start'],
                    'end_time': current_segment[-1]['end']
                })

            # Start new segment
            current_speaker = speaker_id
            current_segment = [word]
        else:
            current_segment.append(word)

    # Save final segment
    if current_segment:
        segments.append({
            'speaker_id': current_speaker,
            'text': ' '.join(w['text'] for w in current_segment),
            'start_time': current_segment[0]['start'],
            'end_time': current_segment[-1]['end']
        })

    return segments


def _calculate_overlap_stats(segments: list, overlap_start: float, overlap_end: float) -> dict:
    """Calculate speaker statistics in overlap region"""
    # Filter segments in overlap region
    overlap_segments = [
        seg for seg in segments
        if seg['start_time'] < overlap_end and seg['end_time'] > overlap_start
    ]

    speaker_stats = {}

    for seg in overlap_segments:
        speaker_id = seg['speaker_id']

        if speaker_id not in speaker_stats:
            speaker_stats[speaker_id] = {
                'speaker_id': speaker_id,
                'word_count': 0,
                'duration': 0.0,
                'segment_count': 0
            }

        stats = speaker_stats[speaker_id]

        # Calculate actual overlap duration
        seg_start = max(seg['start_time'], overlap_start)
        seg_end = min(seg['end_time'], overlap_end)
        duration = seg_end - seg_start

        stats['word_count'] += len(seg['text'].split())
        stats['duration'] += duration
        stats['segment_count'] += 1

    return speaker_stats


@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio using ElevenLabs Scribe v2 Realtime API

    Args:
        audio: Audio file (webm, wav, mp3, etc.)

    Returns:
        Transcribed text with ultra-low latency (~150ms) and automatic language detection
    """
    if elevenlabs_client is None:
        raise HTTPException(
            status_code=503,
            detail="Transcription service not configured. ELEVENLABS_API_KEY is required."
        )

    try:
        print(f"🎤 Transcribing audio file: {audio.filename}")

        # Read the audio content
        content = await audio.read()
        audio_size_kb = len(content) / 1024
        print(f"📊 Audio file size: {audio_size_kb:.2f} KB ({len(content)} bytes)")

        # Transcribe using ElevenLabs Scribe v2 Realtime
        start = time.time()

        # Convert bytes to BytesIO for file-like object
        from io import BytesIO
        audio_data = BytesIO(content)
        audio_data.name = audio.filename or "audio.webm"

        # Call ElevenLabs speech-to-text API
        # No language_code specified - auto-detect from 90+ languages
        response = elevenlabs_client.speech_to_text.convert(
            file=audio_data,
            model_id="scribe_v2_realtime"
        )
        latency = time.time() - start

        # Extract transcription from response
        # ElevenLabs response includes: text, language_code, and other metadata
        transcription = response.text if hasattr(response, 'text') else ""
        detected_language = response.language_code if hasattr(response, 'language_code') else None

        print(f"✅ Transcription complete in {latency:.2f}s")
        print(f"🌍 Detected language: {detected_language}")
        print(f"📝 Full transcription text: '{transcription}'")

        return {
            "success": True,
            "text": transcription.strip(),
            "detected_language": detected_language,
            "translated_text": None,  # Placeholder for future translation feature
            "latency_seconds": round(latency, 2),
            "model": "elevenlabs/scribe_v2_realtime"
        }

    except Exception as e:
        print(f"❌ Transcription error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


# ============================================================================
# AUDIO STORAGE ENDPOINTS
# ============================================================================

@app.post("/api/upload-audio")
async def upload_audio_to_gcs(
    audio: UploadFile = File(...),
    session_id: Optional[str] = None
):
    """
    Upload audio recording to Google Cloud Storage

    Args:
        audio: Audio file (webm, wav, mp3, etc.)
        session_id: Optional session ID for organizing recordings

    Returns:
        {
            "success": true,
            "gcs_uri": "gs://aneya-audio-recordings/...",
            "public_url": "https://storage.googleapis.com/...",
            "filename": "...",
            "size_bytes": 12345
        }
    """
    if gcs_client is None:
        raise HTTPException(
            status_code=503,
            detail="Audio storage service not configured. GCS client is required."
        )

    try:
        # Read audio content
        content = await audio.read()
        audio_size_kb = len(content) / 1024
        print(f"📤 Uploading audio file: {audio.filename} ({audio_size_kb:.2f} KB)")

        # Generate unique filename with timestamp and UUID
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        unique_id = str(uuid.uuid4())[:8]

        # Determine file extension from original filename or content type
        ext = ".webm"
        if audio.filename:
            ext = os.path.splitext(audio.filename)[1] or ext
        elif audio.content_type:
            ext_map = {
                "audio/webm": ".webm",
                "audio/mp3": ".mp3",
                "audio/mpeg": ".mp3",
                "audio/wav": ".wav",
                "audio/ogg": ".ogg"
            }
            ext = ext_map.get(audio.content_type, ext)

        # Build path with optional session organization
        if session_id:
            blob_path = f"sessions/{session_id}/recording-{timestamp}-{unique_id}{ext}"
        else:
            blob_path = f"recordings/recording-{timestamp}-{unique_id}{ext}"

        # Upload to GCS
        bucket = gcs_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(blob_path)

        # Set content type
        content_type = audio.content_type or "audio/webm"
        blob.upload_from_string(content, content_type=content_type)

        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{blob_path}"
        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob_path}"

        print(f"✅ Audio uploaded to GCS: {gcs_uri}")

        return {
            "success": True,
            "gcs_uri": gcs_uri,
            "public_url": public_url,
            "filename": blob_path,
            "size_bytes": len(content)
        }

    except Exception as e:
        print(f"❌ Audio upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Audio upload failed: {str(e)}")


# ============================================================================
# EMAIL INVITATION ENDPOINTS
# ============================================================================

class SendInvitationEmailRequest(BaseModel):
    """Request body for sending patient invitation emails"""
    email: str
    patient_name: Optional[str] = None
    doctor_name: str
    invitation_token: str
    invitation_url: Optional[str] = None  # Full URL to accept invitation


class PasswordResetRequest(BaseModel):
    """Request body for password reset"""
    email: str


@app.post("/api/send-invitation-email")
async def send_invitation_email(request: SendInvitationEmailRequest):
    """
    Send a patient invitation email using Resend

    Args:
        request: SendInvitationEmailRequest with email, names, and invitation token

    Returns:
        {
            "success": true,
            "message_id": "resend-message-id",
            "recipient": "email@example.com"
        }
    """
    import resend

    resend_api_key = os.getenv("RESEND_API_KEY")
    if not resend_api_key:
        raise HTTPException(
            status_code=503,
            detail="Email service not configured. RESEND_API_KEY is required."
        )

    resend.api_key = resend_api_key

    try:
        # Build the invitation URL
        base_url = request.invitation_url or f"https://aneya.vercel.app/join?token={request.invitation_token}"

        # Personalize greeting
        greeting = f"Hi {request.patient_name}," if request.patient_name else "Hello,"

        # Build HTML email
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 40px 20px; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .logo {{ font-family: Georgia, serif; font-size: 32px; color: #0c3555; font-weight: bold; }}
        .content {{ background: #f6f5ee; border-radius: 12px; padding: 30px; margin-bottom: 30px; }}
        .button {{ display: inline-block; background: #1d9e99; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: 600; margin: 20px 0; }}
        .button:hover {{ background: #178a85; }}
        .footer {{ text-align: center; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">aneya</div>
        </div>
        <div class="content">
            <p>{greeting}</p>
            <p><strong>Dr. {request.doctor_name}</strong> has invited you to connect on Aneya, a secure healthcare platform for managing your appointments and health records.</p>
            <p>Click the button below to accept this invitation and create your account:</p>
            <p style="text-align: center;">
                <a href="{base_url}" class="button">Accept Invitation</a>
            </p>
            <p style="font-size: 14px; color: #666;">This invitation link will expire in 7 days. If you didn't expect this invitation, you can safely ignore this email.</p>
        </div>
        <div class="footer">
            <p>Aneya - Clinical Decision Support</p>
            <p style="font-size: 12px;">This email was sent to {request.email}</p>
        </div>
    </div>
</body>
</html>
"""

        # Send email via Resend
        print(f"📧 Sending invitation email to {request.email}...")

        params = {
            "from": "Aneya <onboarding@resend.dev>",
            "to": [request.email],
            "subject": f"You've been invited to connect with Dr. {request.doctor_name} on Aneya",
            "html": html_content,
        }

        email_response = resend.Emails.send(params)

        print(f"✅ Invitation email sent to {request.email}")
        print(f"   Message ID: {email_response.get('id', 'N/A')}")

        return {
            "success": True,
            "message_id": email_response.get("id"),
            "recipient": request.email
        }

    except Exception as e:
        print(f"❌ Email sending error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to send invitation email: {str(e)}")


@app.post("/api/send-password-reset-email")
async def send_password_reset_email(request: PasswordResetRequest):
    """
    Send a password reset email using Resend with Firebase password reset link

    This bypasses Firebase's default email sending which has poor deliverability.
    Instead, we generate the reset link using Firebase Admin SDK and send it
    via Resend from our custom domain (aneya.health).

    Args:
        request: PasswordResetRequest with email address

    Returns:
        {
            "success": true,
            "message": "Password reset email sent"
        }
    """
    import resend
    from firebase_admin import auth as firebase_auth

    resend_api_key = os.getenv("RESEND_API_KEY")
    if not resend_api_key:
        raise HTTPException(
            status_code=503,
            detail="Email service not configured. RESEND_API_KEY is required."
        )

    resend.api_key = resend_api_key

    try:
        email = request.email.strip().lower()

        # Validate email format
        if not email or '@' not in email:
            raise HTTPException(status_code=400, detail="Invalid email address")

        print(f"🔑 Processing password reset request for: {email}")

        # Generate Firebase password reset link using Admin SDK
        # This creates a secure link that Firebase will accept
        try:
            action_code_settings = firebase_auth.ActionCodeSettings(
                url='https://aneya.vercel.app/login',  # Redirect after reset
                handle_code_in_app=False,
            )
            reset_link = firebase_auth.generate_password_reset_link(
                email,
                action_code_settings=action_code_settings
            )
            print(f"✅ Generated Firebase reset link")
        except firebase_auth.UserNotFoundError:
            # Don't reveal if email exists or not (security best practice)
            print(f"⚠️  User not found: {email} (returning success anyway)")
            return {
                "success": True,
                "message": "If an account exists with this email, a password reset link has been sent."
            }
        except Exception as firebase_error:
            print(f"❌ Firebase error generating reset link: {firebase_error}")
            raise HTTPException(status_code=500, detail=f"Failed to generate reset link: {str(firebase_error)}")

        # Build HTML email with aneya branding
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 0;
            background-color: #f6f5ee;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        .card {{
            background: white;
            border-radius: 12px;
            padding: 40px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo {{
            font-family: Georgia, serif;
            font-size: 32px;
            color: #0c3555;
            font-weight: bold;
        }}
        .content {{
            margin-bottom: 30px;
        }}
        .button {{
            display: inline-block;
            background: #1d9e99;
            color: white !important;
            padding: 14px 32px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 20px 0;
        }}
        .button:hover {{
            background: #178a85;
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
                <div class="logo">aneya</div>
                <p style="color: #666; margin-top: 8px;">Clinical Decision Support</p>
            </div>
            <div class="content">
                <h2 style="color: #0c3555; margin-bottom: 16px;">Reset Your Password</h2>
                <p>We received a request to reset the password for your Aneya account associated with <strong>{email}</strong>.</p>
                <p>Click the button below to set a new password:</p>
                <p style="text-align: center;">
                    <a href="{reset_link}" class="button">Reset Password</a>
                </p>
                <div class="warning">
                    <strong>Didn't request this?</strong> If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.
                </div>
            </div>
            <div class="footer">
                <p>This link will expire in 1 hour for security reasons.</p>
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

        # Plain text version for email clients that don't support HTML
        text_content = f"""
Reset Your Password - Aneya

We received a request to reset the password for your Aneya account ({email}).

Click the link below to set a new password:
{reset_link}

This link will expire in 1 hour for security reasons.

If you didn't request this password reset, you can safely ignore this email.

---
Aneya Healthcare Platform
"""

        # Send email via Resend
        print(f"📧 Sending password reset email to {email}...")

        params = {
            "from": "Aneya <noreply@aneya.health>",
            "to": [email],
            "subject": "Reset your Aneya password",
            "html": html_content,
            "text": text_content,
        }

        email_response = resend.Emails.send(params)

        print(f"✅ Password reset email sent to {email}")
        print(f"   Message ID: {email_response.get('id', 'N/A')}")

        return {
            "success": True,
            "message": "If an account exists with this email, a password reset link has been sent."
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Password reset email error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to send password reset email: {str(e)}")


# ============================================================================
# APPOINTMENTS ENDPOINTS
# ============================================================================

@app.patch("/api/appointments/{appointment_id}/status")
async def update_appointment_status(
    appointment_id: str,
    request: dict
):
    """
    Update appointment status (e.g., mark as completed, cancelled)

    This is a placeholder endpoint for the appointments feature.
    In production, this would update a database.
    """
    new_status = request.get("status")

    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required")

    # TODO: Implement actual database update
    # For now, just return success
    return {
        "success": True,
        "appointment_id": appointment_id,
        "status": new_status,
        "message": "Appointment status updated (placeholder)"
    }


@app.delete("/api/appointments/{appointment_id}")
async def delete_appointment(appointment_id: str):
    """
    Delete an appointment by ID.

    Args:
        appointment_id: The ID of the appointment to delete

    Returns:
        Success response with deletion confirmation
    """
    try:
        supabase = get_supabase_client()

        # Verify the appointment exists before deleting
        get_result = supabase.table("appointments").select("id").eq("id", appointment_id).execute()
        if not get_result.data:
            raise HTTPException(status_code=404, detail=f"Appointment with ID {appointment_id} not found")

        print(f"🗑️  Deleting appointment: {appointment_id}")

        # Delete the appointment
        supabase.table("appointments").delete().eq("id", appointment_id).execute()

        print(f"✅ Appointment deleted: {appointment_id}")

        return {
            "success": True,
            "message": f"Appointment {appointment_id} has been deleted",
            "appointment_id": appointment_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting appointment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete appointment: {str(e)}")


@app.get("/api/appointments/{appointment_id}/consultation-pdf")
async def download_consultation_pdf(appointment_id: str):
    """
    Generate and download a PDF of the consultation form and appointment details.

    Args:
        appointment_id: UUID of the appointment

    Returns:
        StreamingResponse with PDF file

    Raises:
        400: Invalid appointment ID format
        404: Appointment not found or no consultation form found
        500: PDF generation failed
    """
    try:
        # Validate UUID format
        try:
            uuid.UUID(appointment_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid appointment ID format")

        # Get Supabase client
        supabase = get_supabase_client()

        # Fetch appointment with patient and doctor data
        print(f"📄 Fetching appointment data for PDF generation: {appointment_id}")

        appointment_result = supabase.table("appointments")\
            .select("*, patient:patients(*), doctor:doctors(*)")\
            .eq("id", appointment_id)\
            .execute()

        if not appointment_result.data:
            raise HTTPException(status_code=404, detail="Appointment not found")

        appointment = appointment_result.data[0]
        patient = appointment['patient']

        # Extract doctor info for PDF header (logo and clinic name)
        doctor_info = None
        if appointment.get('doctor'):
            doctor_info = {
                'clinic_name': appointment['doctor'].get('clinic_name'),
                'clinic_logo_url': appointment['doctor'].get('clinic_logo_url')
            }

        # Fetch consultation form from new consultation_forms table
        form_result = supabase.table("consultation_forms")\
            .select("*")\
            .eq("appointment_id", appointment_id)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()

        if not form_result.data:
            raise HTTPException(
                status_code=404,
                detail="No consultation form found for this appointment"
            )

        form_record = form_result.data[0]
        form_data = form_record['form_data']
        form_type = form_record['form_type']
        specialty = form_record.get('specialty', 'general')
        print(f"✅ Found consultation form (type: {form_type}, specialty: {specialty})")

        # Look up the matching custom_form to get the PDF template
        custom_form_result = supabase.table("custom_forms")\
            .select("*")\
            .ilike("form_name", f"%{form_type}%")\
            .eq("specialty", specialty)\
            .eq("status", "active")\
            .limit(1)\
            .execute()

        if not custom_form_result.data:
            raise HTTPException(
                status_code=404,
                detail=f"No active custom form template found for form type '{form_type}' and specialty '{specialty}'"
            )

        custom_form = custom_form_result.data[0]
        pdf_template = custom_form.get('pdf_template')

        if not pdf_template:
            raise HTTPException(
                status_code=400,
                detail=f"Form '{custom_form['form_name']}' does not have a PDF template configured"
            )

        print(f"✅ Found custom form template: {custom_form['form_name']}")

        # Convert flat form_data (dot notation) to nested structure for PDF generator
        # PDF generator expects: {"section": {"field": "value"}}
        # But form_data has: {"section.field": "value"}
        nested_form_data = {}
        for key, value in form_data.items():
            if '.' in key:
                parts = key.split('.', 1)  # Split only on first dot
                section, field = parts[0], parts[1]

                if section not in nested_form_data:
                    nested_form_data[section] = {}

                nested_form_data[section][field] = value
            else:
                # Top-level field (no section)
                nested_form_data[key] = value

        print(f"📊 Converted {len(form_data)} flat fields to {len(nested_form_data)} sections")

        # Import PDF generator (same as used for form extraction PDF preview)
        from pdf_generator import generate_custom_form_pdf

        # Generate PDF with actual form data
        print(f"📄 Generating PDF for form type: {form_type}")
        pdf_buffer = generate_custom_form_pdf(
            form_data=nested_form_data,  # Use nested structure
            pdf_template=pdf_template,
            form_name=custom_form['form_name'],
            specialty=specialty,
            patient=patient,
            doctor_info=doctor_info,
            form_schema=custom_form.get('form_schema'),  # Pass schema for table rendering
            # Optional custom colors (None = default Aneya colors)
            # In future, could fetch from doctor preferences
            primary_color=None,
            accent_color=None,
            text_color=None,
            light_gray_color=None
        )

        # Create safe filename
        patient_name = patient['name'].replace(' ', '_').replace('/', '_')
        filename = f"consultation_{form_type}_{patient_name}_{appointment_id[:8]}.pdf"

        print(f"✅ PDF generated successfully: {filename}")

        # Return as streaming response
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
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


# ============================================================================
# SYMPTOM STRUCTURING ENDPOINT
# ============================================================================

class StructureSymptomRequest(BaseModel):
    """Request body for symptom structuring"""
    symptom_text: str
    original_transcript: Optional[str] = None
    transcription_language: Optional[str] = None
    patient_id: str


@app.post("/api/structure-symptom")
async def structure_symptom(request: StructureSymptomRequest):
    """
    Use Claude to structure free-form symptom text into structured data,
    then save to Supabase patient_symptoms table.
    """
    import anthropic
    from supabase import create_client, Client

    # Get Supabase credentials
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for backend operations

    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase configuration not available")

    # Initialize Supabase client
    supabase: Client = create_client(supabase_url, supabase_key)

    # Use Claude to structure the symptom text
    anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""Analyze the following patient symptom description and extract structured information.
Return a JSON object with these fields (use null if information is not provided):

- severity: number from 1-10 (null if not mentioned)
- duration: string describing how long they've had symptoms (null if not mentioned)
- body_location: string describing where symptoms are felt (null if not mentioned)
- time_of_day: string describing when symptoms are worst (null if not mentioned)
- triggers: string describing possible triggers (null if not mentioned)
- additional_notes: any other relevant clinical information not captured above (null if none)
- structured_summary: a concise clinical summary of the symptoms (always provide this)

Patient's symptom description:
"{request.symptom_text}"

Respond with ONLY the JSON object, no other text."""

    try:
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Parse the response
        response_text = response.content[0].text.strip()

        # Try to extract JSON from the response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            structured_data = json.loads(json_match.group())
        else:
            structured_data = json.loads(response_text)

    except Exception as e:
        print(f"Error structuring symptom with Claude: {e}")
        # Fallback: use the raw text without structuring
        structured_data = {
            "severity": None,
            "duration": None,
            "body_location": None,
            "time_of_day": None,
            "triggers": None,
            "additional_notes": None,
            "structured_summary": request.symptom_text
        }

    # Save to Supabase
    try:
        # Prepare the data for insertion
        symptom_data = {
            "patient_id": request.patient_id,
            "symptom_text": structured_data.get("structured_summary", request.symptom_text),
            "original_transcript": request.original_transcript or request.symptom_text,
            "transcription_language": request.transcription_language,
            "severity": structured_data.get("severity"),
            "duration_description": structured_data.get("duration"),
            "body_location": structured_data.get("body_location"),
            "notes": structured_data.get("additional_notes"),
            "status": "active"
        }

        result = supabase.table("patient_symptoms").insert(symptom_data).execute()

        return {
            "success": True,
            "structured_data": structured_data,
            "symptom_id": result.data[0]["id"] if result.data else None
        }

    except Exception as e:
        print(f"Error saving symptom to Supabase: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save symptom: {str(e)}")


# ============================================================================
# OB/GYN FORM ENDPOINTS
# ============================================================================

class OBGYNFormSectionRequest(BaseModel):
    """Request body for validating OB/GYN form sections"""
    section_name: str
    section_data: dict
    patient_id: Optional[str] = None


class OBGYNFormResponse(BaseModel):
    """Response model for OB/GYN form operations"""
    id: str
    patient_id: str
    appointment_id: Optional[str] = None
    form_data: dict
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class OBGYNFormCreateRequest(BaseModel):
    """Request body for creating a new OB/GYN form"""
    patient_id: str
    appointment_id: Optional[str] = None
    form_data: dict
    status: str = "draft"


class OBGYNFormUpdateRequest(BaseModel):
    """Request body for updating an OB/GYN form"""
    form_data: dict
    status: Optional[str] = None


def validate_obgyn_form_data(form_data: dict) -> tuple[bool, Optional[str]]:
    """
    Validate OB/GYN form data for required fields and data types.

    Args:
        form_data: Dictionary containing form data

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = [
        'patient_demographics',
        'obstetric_history',
        'gynecologic_history'
    ]

    for field in required_fields:
        if field not in form_data:
            return False, f"Missing required section: {field}"

    # Validate patient_demographics
    if not isinstance(form_data.get('patient_demographics'), dict):
        return False, "patient_demographics must be an object"

    # Validate obstetric_history
    if not isinstance(form_data.get('obstetric_history'), dict):
        return False, "obstetric_history must be an object"

    # Validate gynecologic_history
    if not isinstance(form_data.get('gynecologic_history'), dict):
        return False, "gynecologic_history must be an object"

    return True, None


def get_supabase_client():
    """Get Supabase client for database operations"""
    from supabase import create_client, Client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Supabase configuration not available")

    return create_client(supabase_url, supabase_key)


@app.post("/api/obgyn-forms", response_model=OBGYNFormResponse)
async def create_obgyn_form(request: OBGYNFormCreateRequest):
    """
    Create a new OB/GYN form for a patient.

    Args:
        request: OBGYNFormCreateRequest with patient_id, form_data, and optional appointment_id

    Returns:
        OBGYNFormResponse with the created form details
    """
    try:
        # Validate form data
        is_valid, error_msg = validate_obgyn_form_data(request.form_data)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Get Supabase client
        supabase = get_supabase_client()

        # Prepare form data
        form_record = {
            "patient_id": request.patient_id,
            "appointment_id": request.appointment_id,
            "form_data": request.form_data,
            "status": request.status
        }

        print(f"📋 Creating OB/GYN form for patient {request.patient_id}")

        # Insert into database
        result = supabase.table("obgyn_forms").insert(form_record).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create form")

        form = result.data[0]
        print(f"✅ OB/GYN form created with ID: {form['id']}")

        return OBGYNFormResponse(
            id=form['id'],
            patient_id=form['patient_id'],
            appointment_id=form.get('appointment_id'),
            form_data=form['form_data'],
            status=form['status'],
            created_at=form.get('created_at'),
            updated_at=form.get('updated_at')
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating OB/GYN form: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create form: {str(e)}")


@app.get("/api/obgyn-forms/{form_id}", response_model=OBGYNFormResponse)
async def get_obgyn_form(form_id: str):
    """
    Retrieve an OB/GYN form by ID.

    Args:
        form_id: The ID of the form to retrieve

    Returns:
        OBGYNFormResponse with the form details
    """
    try:
        supabase = get_supabase_client()

        print(f"📖 Retrieving OB/GYN form: {form_id}")

        result = supabase.table("obgyn_forms").select("*").eq("id", form_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Form with ID {form_id} not found")

        form = result.data[0]
        print(f"✅ Retrieved OB/GYN form: {form_id}")

        return OBGYNFormResponse(
            id=form['id'],
            patient_id=form['patient_id'],
            appointment_id=form.get('appointment_id'),
            form_data=form['form_data'],
            status=form['status'],
            created_at=form.get('created_at'),
            updated_at=form.get('updated_at')
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving form: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve form: {str(e)}")


@app.get("/api/obgyn-forms/patient/{patient_id}")
async def get_patient_obgyn_forms(patient_id: str):
    """
    Retrieve all OB/GYN forms for a specific patient.

    Args:
        patient_id: The ID of the patient

    Returns:
        List of OBGYNFormResponse objects for the patient
    """
    try:
        supabase = get_supabase_client()

        print(f"📖 Retrieving all OB/GYN forms for patient: {patient_id}")

        result = supabase.table("obgyn_forms").select("*").eq("patient_id", patient_id).order("created_at", desc=True).execute()

        forms = []
        for form in result.data:
            forms.append(OBGYNFormResponse(
                id=form['id'],
                patient_id=form['patient_id'],
                appointment_id=form.get('appointment_id'),
                form_data=form['form_data'],
                status=form['status'],
                created_at=form.get('created_at'),
                updated_at=form.get('updated_at')
            ))

        print(f"✅ Retrieved {len(forms)} OB/GYN forms for patient {patient_id}")

        return {
            "success": True,
            "patient_id": patient_id,
            "forms": forms,
            "count": len(forms)
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving patient forms: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve forms: {str(e)}")


@app.get("/api/obgyn-forms/appointment/{appointment_id}")
async def get_appointment_obgyn_form(appointment_id: str):
    """
    Retrieve the OB/GYN form associated with a specific appointment.

    Args:
        appointment_id: The ID of the appointment

    Returns:
        OBGYNFormResponse for the appointment, or 404 if not found
    """
    try:
        supabase = get_supabase_client()

        print(f"📖 Retrieving OB/GYN form for appointment: {appointment_id}")

        result = supabase.table("obgyn_forms").select("*").eq("appointment_id", appointment_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"No form found for appointment {appointment_id}")

        form = result.data[0]
        print(f"✅ Retrieved OB/GYN form for appointment {appointment_id}")

        return OBGYNFormResponse(
            id=form['id'],
            patient_id=form['patient_id'],
            appointment_id=form.get('appointment_id'),
            form_data=form['form_data'],
            status=form['status'],
            created_at=form.get('created_at'),
            updated_at=form.get('updated_at')
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving appointment form: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve form: {str(e)}")


@app.put("/api/obgyn-forms/{form_id}", response_model=OBGYNFormResponse)
async def update_obgyn_form(form_id: str, request: OBGYNFormUpdateRequest):
    """
    Update an existing OB/GYN form.

    Args:
        form_id: The ID of the form to update
        request: OBGYNFormUpdateRequest with updated form_data and optional status

    Returns:
        OBGYNFormResponse with the updated form details
    """
    try:
        supabase = get_supabase_client()

        # First, verify the form exists
        get_result = supabase.table("obgyn_forms").select("*").eq("id", form_id).execute()
        if not get_result.data:
            raise HTTPException(status_code=404, detail=f"Form with ID {form_id} not found")

        # Validate updated form data
        is_valid, error_msg = validate_obgyn_form_data(request.form_data)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Prepare update data
        update_data = {
            "form_data": request.form_data
        }

        if request.status:
            update_data["status"] = request.status

        print(f"✏️  Updating OB/GYN form: {form_id}")

        # Update the form
        result = supabase.table("obgyn_forms").update(update_data).eq("id", form_id).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update form")

        form = result.data[0]
        print(f"✅ OB/GYN form updated: {form_id}")

        return OBGYNFormResponse(
            id=form['id'],
            patient_id=form['patient_id'],
            appointment_id=form.get('appointment_id'),
            form_data=form['form_data'],
            status=form['status'],
            created_at=form.get('created_at'),
            updated_at=form.get('updated_at')
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating OB/GYN form: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to update form: {str(e)}")


@app.delete("/api/obgyn-forms/{form_id}")
async def delete_obgyn_form(form_id: str):
    """
    Delete an OB/GYN form by ID.

    Args:
        form_id: The ID of the form to delete

    Returns:
        Success response with deletion confirmation
    """
    try:
        supabase = get_supabase_client()

        # Verify the form exists before deleting
        get_result = supabase.table("obgyn_forms").select("id").eq("id", form_id).execute()
        if not get_result.data:
            raise HTTPException(status_code=404, detail=f"Form with ID {form_id} not found")

        print(f"🗑️  Deleting OB/GYN form: {form_id}")

        # Delete the form
        supabase.table("obgyn_forms").delete().eq("id", form_id).execute()

        print(f"✅ OB/GYN form deleted: {form_id}")

        return {
            "success": True,
            "message": f"Form {form_id} has been deleted",
            "form_id": form_id
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error deleting OB/GYN form: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete form: {str(e)}")


@app.post("/api/obgyn-forms/validate")
async def validate_obgyn_form_section(request: OBGYNFormSectionRequest):
    """
    Validate a specific section of an OB/GYN form.

    This endpoint validates form sections against expected data structures
    and can be called to check individual sections during form filling.

    Args:
        request: OBGYNFormSectionRequest with section_name and section_data

    Returns:
        Validation result with success status and any errors found
    """
    try:
        section_name = request.section_name.lower()
        section_data = request.section_data

        print(f"🔍 Validating OB/GYN form section: {section_name}")

        # Define validation rules for each section
        validation_rules = {
            'patient_demographics': {
                'optional_fields': ['age', 'date_of_birth', 'ethnicity', 'occupation', 'emergency_contact']
            },
            'obstetric_history': {
                'optional_fields': ['gravidity', 'parity', 'abortions', 'living_children', 'complications']
            },
            'gynecologic_history': {
                'optional_fields': ['menarche_age', 'last_menstrual_period', 'cycle_length', 'menstrual_duration', 'gynecologic_conditions']
            },
            'medical_history': {
                'optional_fields': ['conditions', 'medications', 'surgeries', 'allergies']
            },
            'physical_examination': {
                'optional_fields': ['general', 'vital_signs', 'abdominal_exam', 'pelvic_exam', 'findings']
            },
            'assessment_plan': {
                'optional_fields': ['diagnoses', 'recommendations', 'follow_up']
            }
        }

        # Check if section is recognized
        if section_name not in validation_rules and section_name not in ['patient_demographics', 'obstetric_history', 'gynecologic_history']:
            return {
                "success": False,
                "section": section_name,
                "valid": False,
                "errors": [f"Unknown section: {section_name}"]
            }

        # Validate that section_data is a dictionary
        if not isinstance(section_data, dict):
            return {
                "success": False,
                "section": section_name,
                "valid": False,
                "errors": [f"Section data must be an object/dictionary"]
            }

        errors = []

        # Validate specific sections
        if section_name == 'patient_demographics':
            # Validate demographics
            if 'age' in section_data and not isinstance(section_data['age'], (int, str)):
                errors.append("age must be a number or string")
            if 'date_of_birth' in section_data and not isinstance(section_data['date_of_birth'], str):
                errors.append("date_of_birth must be a string")

        elif section_name == 'obstetric_history':
            # Validate obstetric data
            if 'gravidity' in section_data and not isinstance(section_data['gravidity'], (int, str)):
                errors.append("gravidity must be a number or string")
            if 'parity' in section_data and not isinstance(section_data['parity'], (int, str)):
                errors.append("parity must be a number or string")

        elif section_name == 'gynecologic_history':
            # Validate gynecologic data
            if 'menarche_age' in section_data and not isinstance(section_data['menarche_age'], (int, str)):
                errors.append("menarche_age must be a number or string")
            if 'last_menstrual_period' in section_data and not isinstance(section_data['last_menstrual_period'], str):
                errors.append("last_menstrual_period must be a string (date)")

        print(f"✅ Validation complete for section: {section_name}")

        return {
            "success": True,
            "section": section_name,
            "valid": len(errors) == 0,
            "errors": errors,
            "field_count": len(section_data)
        }

    except Exception as e:
        print(f"❌ Error validating form section: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


# ============================================================================
# SHARED PATIENT HEALTH RECORDS API ENDPOINTS
# ============================================================================
# These endpoints provide access to normalized patient health data shared
# across all specialties (OB/GYN, Cardiology, etc.)
#
# Tables covered:
# - patient_vitals: Timestamped vital signs
# - patient_medications: Medication list with temporal tracking
# - patient_allergies: Allergy list with severity tracking
# - patient_conditions: Medical conditions/diagnoses
# - patient_lab_results: Lab test results
# ============================================================================


# ===== PYDANTIC MODELS =====

class PatientVitalsCreate(BaseModel):
    """Request model for creating patient vitals"""
    patient_id: str
    appointment_id: Optional[str] = None
    consultation_form_id: Optional[str] = None
    consultation_form_type: Optional[str] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    heart_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    temperature_celsius: Optional[float] = None
    spo2: Optional[int] = None
    blood_glucose_mg_dl: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    notes: Optional[str] = None
    source_form_status: Optional[str] = None


class PatientVitalsResponse(BaseModel):
    """Response model for patient vitals"""
    id: str
    patient_id: str
    recorded_at: str
    recorded_by: Optional[str] = None
    appointment_id: Optional[str] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    heart_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    temperature_celsius: Optional[float] = None
    spo2: Optional[int] = None
    blood_glucose_mg_dl: Optional[int] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    bmi: Optional[float] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class PatientMedicationCreate(BaseModel):
    """Request model for creating patient medication"""
    patient_id: str
    medication_name: str
    dosage: str
    frequency: str
    route: Optional[str] = None
    started_date: Optional[str] = None
    stopped_date: Optional[str] = None
    status: str = "active"
    appointment_id: Optional[str] = None
    indication: Optional[str] = None
    notes: Optional[str] = None


class PatientMedicationResponse(BaseModel):
    """Response model for patient medication"""
    id: str
    patient_id: str
    medication_name: str
    dosage: str
    frequency: str
    route: Optional[str] = None
    started_date: str
    stopped_date: Optional[str] = None
    status: str
    prescribed_by: Optional[str] = None
    prescribed_at: Optional[str] = None
    appointment_id: Optional[str] = None
    indication: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class PatientAllergyCreate(BaseModel):
    """Request model for creating patient allergy"""
    patient_id: str
    allergen: str
    allergen_category: Optional[str] = None
    reaction: Optional[str] = None
    severity: Optional[str] = None
    onset_date: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None


class PatientAllergyResponse(BaseModel):
    """Response model for patient allergy"""
    id: str
    patient_id: str
    allergen: str
    allergen_category: Optional[str] = None
    reaction: Optional[str] = None
    severity: Optional[str] = None
    onset_date: Optional[str] = None
    status: str
    recorded_by: Optional[str] = None
    recorded_at: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class PatientConditionCreate(BaseModel):
    """Request model for creating patient condition"""
    patient_id: str
    condition_name: str
    icd10_code: Optional[str] = None
    diagnosed_date: Optional[str] = None
    status: str = "active"
    appointment_id: Optional[str] = None
    notes: Optional[str] = None


class PatientConditionResponse(BaseModel):
    """Response model for patient condition"""
    id: str
    patient_id: str
    condition_name: str
    icd10_code: Optional[str] = None
    diagnosed_date: Optional[str] = None
    status: str
    diagnosed_by: Optional[str] = None
    appointment_id: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    updated_at: str


class PatientLabResultCreate(BaseModel):
    """Request model for creating patient lab result"""
    patient_id: str
    test_date: Optional[str] = None
    test_type: str
    appointment_id: Optional[str] = None
    results: dict
    interpretation: Optional[str] = None
    notes: Optional[str] = None
    lab_name: Optional[str] = None


class PatientLabResultResponse(BaseModel):
    """Response model for patient lab result"""
    id: str
    patient_id: str
    test_date: str
    test_type: str
    ordered_by: Optional[str] = None
    appointment_id: Optional[str] = None
    results: dict
    interpretation: Optional[str] = None
    notes: Optional[str] = None
    lab_name: Optional[str] = None
    created_at: str
    updated_at: str


# ===== PATIENT VITALS ENDPOINTS =====

@app.post("/api/patient-vitals", response_model=PatientVitalsResponse)
async def create_patient_vitals(vitals: PatientVitalsCreate):
    """Create a new patient vitals record"""
    try:
        supabase = get_supabase_client()

        # Prepare data for insertion
        vitals_data = vitals.model_dump(exclude_none=True)

        print(f"📝 Creating vitals record for patient: {vitals.patient_id}")

        result = supabase.table("patient_vitals").insert(vitals_data).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create vitals record")

        print(f"✅ Vitals record created: {result.data[0]['id']}")
        return result.data[0]

    except Exception as e:
        print(f"❌ Error creating vitals record: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create vitals record: {str(e)}")


@app.get("/api/patient-vitals/patient/{patient_id}")
async def get_patient_vitals(patient_id: str, limit: int = 10):
    """Get all vitals records for a patient (most recent first)"""
    try:
        supabase = get_supabase_client()

        result = supabase.table("patient_vitals")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .order("recorded_at", desc=True)\
            .limit(limit)\
            .execute()

        print(f"✅ Retrieved {len(result.data)} vitals records for patient {patient_id}")
        return result.data

    except Exception as e:
        print(f"❌ Error retrieving vitals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve vitals: {str(e)}")


@app.get("/api/patient-vitals/{vitals_id}", response_model=PatientVitalsResponse)
async def get_vitals_by_id(vitals_id: str):
    """Get a specific vitals record by ID"""
    try:
        supabase = get_supabase_client()

        result = supabase.table("patient_vitals")\
            .select("*")\
            .eq("id", vitals_id)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Vitals record {vitals_id} not found")

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving vitals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve vitals: {str(e)}")


# ===== PATIENT MEDICATIONS ENDPOINTS =====

@app.post("/api/patient-medications", response_model=PatientMedicationResponse)
async def create_patient_medication(medication: PatientMedicationCreate):
    """Create a new patient medication record"""
    try:
        supabase = get_supabase_client()

        medication_data = medication.model_dump(exclude_none=True)

        print(f"📝 Creating medication record for patient: {medication.patient_id}")

        result = supabase.table("patient_medications").insert(medication_data).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create medication record")

        print(f"✅ Medication record created: {result.data[0]['id']}")
        return result.data[0]

    except Exception as e:
        print(f"❌ Error creating medication record: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create medication record: {str(e)}")


@app.get("/api/patient-medications/patient/{patient_id}")
async def get_patient_medications(patient_id: str, status: Optional[str] = None):
    """Get all medications for a patient (optionally filtered by status)"""
    try:
        supabase = get_supabase_client()

        query = supabase.table("patient_medications")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .order("prescribed_at", desc=True)

        if status:
            query = query.eq("status", status)

        result = query.execute()

        print(f"✅ Retrieved {len(result.data)} medication records for patient {patient_id}")
        return result.data

    except Exception as e:
        print(f"❌ Error retrieving medications: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve medications: {str(e)}")


@app.put("/api/patient-medications/{medication_id}", response_model=PatientMedicationResponse)
async def update_patient_medication(medication_id: str, updates: dict):
    """Update a patient medication record (e.g., stop date, status)"""
    try:
        supabase = get_supabase_client()

        print(f"📝 Updating medication record: {medication_id}")

        result = supabase.table("patient_medications")\
            .update(updates)\
            .eq("id", medication_id)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Medication record {medication_id} not found")

        print(f"✅ Medication record updated: {medication_id}")
        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating medication: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update medication: {str(e)}")


# ===== PATIENT ALLERGIES ENDPOINTS =====

@app.post("/api/patient-allergies", response_model=PatientAllergyResponse)
async def create_patient_allergy(allergy: PatientAllergyCreate):
    """Create a new patient allergy record"""
    try:
        supabase = get_supabase_client()

        allergy_data = allergy.model_dump(exclude_none=True)

        print(f"📝 Creating allergy record for patient: {allergy.patient_id}")

        result = supabase.table("patient_allergies").insert(allergy_data).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create allergy record")

        print(f"✅ Allergy record created: {result.data[0]['id']}")
        return result.data[0]

    except Exception as e:
        print(f"❌ Error creating allergy record: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create allergy record: {str(e)}")


@app.get("/api/patient-allergies/patient/{patient_id}")
async def get_patient_allergies(patient_id: str, status: Optional[str] = "active"):
    """Get all allergies for a patient (default: active only)"""
    try:
        supabase = get_supabase_client()

        query = supabase.table("patient_allergies")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .order("recorded_at", desc=True)

        if status:
            query = query.eq("status", status)

        result = query.execute()

        print(f"✅ Retrieved {len(result.data)} allergy records for patient {patient_id}")
        return result.data

    except Exception as e:
        print(f"❌ Error retrieving allergies: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve allergies: {str(e)}")


@app.put("/api/patient-allergies/{allergy_id}", response_model=PatientAllergyResponse)
async def update_patient_allergy(allergy_id: str, updates: dict):
    """Update a patient allergy record (e.g., mark as resolved)"""
    try:
        supabase = get_supabase_client()

        print(f"📝 Updating allergy record: {allergy_id}")

        result = supabase.table("patient_allergies")\
            .update(updates)\
            .eq("id", allergy_id)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Allergy record {allergy_id} not found")

        print(f"✅ Allergy record updated: {allergy_id}")
        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating allergy: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update allergy: {str(e)}")


# ===== PATIENT CONDITIONS ENDPOINTS =====

@app.post("/api/patient-conditions", response_model=PatientConditionResponse)
async def create_patient_condition(condition: PatientConditionCreate):
    """Create a new patient condition record"""
    try:
        supabase = get_supabase_client()

        condition_data = condition.model_dump(exclude_none=True)

        print(f"📝 Creating condition record for patient: {condition.patient_id}")

        result = supabase.table("patient_conditions").insert(condition_data).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create condition record")

        print(f"✅ Condition record created: {result.data[0]['id']}")
        return result.data[0]

    except Exception as e:
        print(f"❌ Error creating condition record: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create condition record: {str(e)}")


@app.get("/api/patient-conditions/patient/{patient_id}")
async def get_patient_conditions(patient_id: str, status: Optional[str] = None):
    """Get all conditions for a patient (optionally filtered by status)"""
    try:
        supabase = get_supabase_client()

        query = supabase.table("patient_conditions")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .order("created_at", desc=True)

        if status:
            query = query.eq("status", status)

        result = query.execute()

        print(f"✅ Retrieved {len(result.data)} condition records for patient {patient_id}")
        return result.data

    except Exception as e:
        print(f"❌ Error retrieving conditions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve conditions: {str(e)}")


@app.put("/api/patient-conditions/{condition_id}", response_model=PatientConditionResponse)
async def update_patient_condition(condition_id: str, updates: dict):
    """Update a patient condition record (e.g., mark as resolved)"""
    try:
        supabase = get_supabase_client()

        print(f"📝 Updating condition record: {condition_id}")

        result = supabase.table("patient_conditions")\
            .update(updates)\
            .eq("id", condition_id)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Condition record {condition_id} not found")

        print(f"✅ Condition record updated: {condition_id}")
        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating condition: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update condition: {str(e)}")


# ===== PATIENT LAB RESULTS ENDPOINTS =====

@app.post("/api/patient-lab-results", response_model=PatientLabResultResponse)
async def create_patient_lab_result(lab_result: PatientLabResultCreate):
    """Create a new patient lab result record"""
    try:
        supabase = get_supabase_client()

        lab_result_data = lab_result.model_dump(exclude_none=True)

        print(f"📝 Creating lab result record for patient: {lab_result.patient_id}")

        result = supabase.table("patient_lab_results").insert(lab_result_data).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create lab result record")

        print(f"✅ Lab result record created: {result.data[0]['id']}")
        return result.data[0]

    except Exception as e:
        print(f"❌ Error creating lab result record: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create lab result record: {str(e)}")


@app.get("/api/patient-lab-results/patient/{patient_id}")
async def get_patient_lab_results(patient_id: str, test_type: Optional[str] = None, limit: int = 20):
    """Get all lab results for a patient (optionally filtered by test type)"""
    try:
        supabase = get_supabase_client()

        query = supabase.table("patient_lab_results")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .order("test_date", desc=True)\
            .limit(limit)

        if test_type:
            query = query.eq("test_type", test_type)

        result = query.execute()

        print(f"✅ Retrieved {len(result.data)} lab result records for patient {patient_id}")
        return result.data

    except Exception as e:
        print(f"❌ Error retrieving lab results: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve lab results: {str(e)}")


@app.get("/api/patient-lab-results/{result_id}", response_model=PatientLabResultResponse)
async def get_lab_result_by_id(result_id: str):
    """Get a specific lab result by ID"""
    try:
        supabase = get_supabase_client()

        result = supabase.table("patient_lab_results")\
            .select("*")\
            .eq("id", result_id)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Lab result {result_id} not found")

        return result.data[0]

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving lab result: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve lab result: {str(e)}")


# ===== UNIFIED PATIENT HEALTH SUMMARY ENDPOINT =====

@app.get("/api/patient-health-summary/{patient_id}")
async def get_patient_health_summary(patient_id: str):
    """
    Get a comprehensive health summary for a patient including:
    - Latest vitals
    - Active medications
    - Active allergies
    - Active conditions
    - Recent lab results
    """
    try:
        supabase = get_supabase_client()

        print(f"📊 Fetching health summary for patient: {patient_id}")

        # Fetch latest vitals
        vitals = supabase.table("patient_vitals")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .order("recorded_at", desc=True)\
            .limit(1)\
            .execute()

        # Fetch active medications
        medications = supabase.table("patient_medications")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .eq("status", "active")\
            .order("prescribed_at", desc=True)\
            .execute()

        # Fetch active allergies
        allergies = supabase.table("patient_allergies")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .eq("status", "active")\
            .order("recorded_at", desc=True)\
            .execute()

        # Fetch active conditions
        conditions = supabase.table("patient_conditions")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .in_("status", ["active", "chronic"])\
            .order("created_at", desc=True)\
            .execute()

        # Fetch recent lab results
        lab_results = supabase.table("patient_lab_results")\
            .select("*")\
            .eq("patient_id", patient_id)\
            .order("test_date", desc=True)\
            .limit(5)\
            .execute()

        summary = {
            "patient_id": patient_id,
            "latest_vitals": vitals.data[0] if vitals.data else None,
            "active_medications": medications.data,
            "active_allergies": allergies.data,
            "active_conditions": conditions.data,
            "recent_lab_results": lab_results.data
        }

        print(f"✅ Health summary compiled for patient {patient_id}")
        return summary

    except Exception as e:
        print(f"❌ Error fetching health summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch health summary: {str(e)}")


# ===== FORM AUTO-FILL ENDPOINTS =====

class DetermineConsultationTypeRequest(BaseModel):
    """Request model for determining consultation type from conversation"""
    diarized_segments: list
    doctor_specialty: str  # 'obgyn', 'general', etc.
    patient_context: dict


class DetermineConsultationTypeResponse(BaseModel):
    """Response model for consultation type determination"""
    consultation_type: str  # 'obgyn', 'infertility', or 'antenatal' (for OBGyn doctors only)
    confidence: float
    reasoning: str


class ExtractFormFieldsRequest(BaseModel):
    """Request model for extracting form fields from diarized segments"""
    diarized_segments: list
    form_type: str  # 'obgyn', 'infertility', 'antenatal'
    patient_context: dict
    current_form_state: dict
    chunk_index: int


class ExtractFormFieldsResponse(BaseModel):
    """Response model for extracted form fields"""
    field_updates: dict
    confidence_scores: dict
    chunk_index: int
    extraction_metadata: dict


class AutoFillConsultationFormRequest(BaseModel):
    """Request model for auto-filling consultation forms from past consultations"""
    consultation_id: str
    appointment_id: str
    patient_id: str
    original_transcript: str  # Diarized transcript
    consultation_text: str    # Summary text (fallback)
    patient_snapshot: dict    # Patient details
    force_consultation_type: Optional[str] = None  # For manual override


class AutoFillConsultationFormResponse(BaseModel):
    """Response model for auto-fill consultation form"""
    success: bool
    consultation_type: str  # antenatal|infertility|obgyn
    confidence: float
    reasoning: str
    form_id: str
    form_created: bool  # True if new form was created
    field_updates: dict  # Fields that were extracted
    error: Optional[str] = None


@app.post("/api/determine-consultation-type", response_model=DetermineConsultationTypeResponse)
async def determine_consultation_type(request: DetermineConsultationTypeRequest):
    """
    Analyze the first chunk of a consultation to determine the appropriate form type.

    This helps auto-select the correct consultation form based on the conversation content,
    especially for specialists who handle multiple types of consultations (e.g., OBGyn doctors
    seeing general gynecology, infertility, or antenatal patients).
    """
    try:
        import time
        start_time = time.time()

        print(f"🔍 Determining consultation type for {request.doctor_specialty} doctor")

        # Build conversation text
        conversation_lines = []
        for seg in request.diarized_segments:
            text = seg.get('text', '').strip()
            speaker_role = seg.get('speaker_role', seg.get('speaker_id', 'Unknown')).title()
            if text:
                conversation_lines.append(f"{speaker_role}: {text}")

        conversation_text = "\n".join(conversation_lines)

        # Build prompt for Claude
        system_prompt = """You are a medical consultation classifier for OB/GYN doctors. Analyze the conversation and determine which type of OB/GYN consultation this is.

You MUST classify as ONE of these three types ONLY:

1. **antenatal**: Pregnancy-related care
   - Indicators: "pregnant", "weeks pregnant", "fetal", "prenatal", "pregnancy test positive", "ultrasound", "antenatal", "baby", "delivery", "due date", "trimester", "expecting"
   - Examples: prenatal visits, pregnancy complications, fetal monitoring, obstetric care

2. **infertility**: Fertility issues and reproductive challenges
   - Indicators: "trying to conceive", "can't get pregnant", "difficulty conceiving", "fertility", "IVF", "IUI", "ovulation", "infertility treatment", "not conceiving", "assisted reproduction", "trying for baby"
   - Examples: difficulty getting pregnant, fertility workup, assisted reproductive technology

3. **obgyn**: General gynecology (DEFAULT if not clearly antenatal or infertility)
   - Indicators: "irregular periods", "contraception", "menstrual", "pap smear", "pelvic exam", "gynecological", "bleeding", "discharge", "pain", "fibroids", "PCOS", "birth control"
   - Examples: menstrual issues, contraception counseling, gynecological exams, routine screening

CLASSIFICATION RULES:
- If conversation mentions CURRENT PREGNANCY → MUST be "antenatal"
- If about TRYING TO GET PREGNANT or fertility problems → "infertility"
- If general gynecological issues or uncertain → "obgyn" (default)
- NEVER return any value other than: antenatal, infertility, or obgyn

Return JSON:
{
  "consultation_type": "antenatal|infertility|obgyn",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation of classification based on conversation keywords"
}"""

        user_prompt = f"""Doctor Specialty: {request.doctor_specialty}

Conversation:
{conversation_text}

Classify this consultation:"""

        # Create local Anthropic client for Claude API calls
        import anthropic
        anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Use Claude Haiku for fast classification
        message = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        response_text = message.content[0].text.strip()

        # Parse JSON response
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response_text

        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"⚠️  Failed to parse Claude response: {e}")
            print(f"Response: {response_text}")
            # Fallback to default obgyn for OBGyn doctors
            return DetermineConsultationTypeResponse(
                consultation_type='obgyn',
                confidence=0.5,
                reasoning="Failed to parse AI response, defaulting to general obgyn consultation"
            )

        consultation_type = result.get('consultation_type', 'obgyn')
        confidence = result.get('confidence', 0.0)
        reasoning = result.get('reasoning', '')

        # Validate that the type is one of the allowed three
        if consultation_type not in ['antenatal', 'infertility', 'obgyn']:
            print(f"⚠️  Invalid consultation type '{consultation_type}', defaulting to 'obgyn'")
            consultation_type = 'obgyn'
            confidence = max(0.3, confidence * 0.5)  # Reduce confidence for invalid response

        processing_time = int((time.time() - start_time) * 1000)
        print(f"✅ Consultation type: {consultation_type} (confidence: {confidence:.2f}) in {processing_time}ms")
        print(f"   Reasoning: {reasoning}")

        return DetermineConsultationTypeResponse(
            consultation_type=consultation_type,
            confidence=confidence,
            reasoning=reasoning
        )

    except Exception as e:
        print(f"❌ Error determining consultation type: {str(e)}")
        import traceback
        traceback.print_exc()
        # Fallback to default obgyn consultation type
        return DetermineConsultationTypeResponse(
            consultation_type='obgyn',
            confidence=0.3,
            reasoning=f"Error occurred, defaulting to general obgyn consultation: {str(e)}"
        )


@app.post("/api/extract-form-fields", response_model=ExtractFormFieldsResponse)
async def extract_form_fields(request: ExtractFormFieldsRequest):
    """
    Extract structured form fields from diarized conversation segments.

    This endpoint processes doctor-patient conversation segments from real-time
    diarization and extracts relevant clinical data to auto-populate form fields.
    """
    try:
        # ✨ NEW: Fetch schema from database instead of Python file
        from mcp_servers.field_validator import validate_multiple_fields, filter_by_confidence, exclude_existing_fields
        import time

        start_time = time.time()

        print(f"📋 Extracting fields for {request.form_type} form (chunk #{request.chunk_index})")

        # Validate form type
        if request.form_type not in ['obgyn', 'infertility', 'antenatal']:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid form type: {request.form_type}. Expected one of: obgyn, infertility, antenatal"
            )

        # Process ALL segments (both doctor and patient)
        # Patient responses often contain the critical medical information
        all_segments = request.diarized_segments

        if not all_segments:
            print("⚠️  No conversation segments found in chunk")
            return ExtractFormFieldsResponse(
                field_updates={},
                confidence_scores={},
                chunk_index=request.chunk_index,
                extraction_metadata={
                    "segments_analyzed": 0,
                    "conversation_segments": 0,
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }
            )

        # Build conversation text with speaker labels
        conversation_lines = []
        for seg in all_segments:
            timestamp = seg.get('start_time', 0)
            text = seg.get('text', '').strip()
            speaker_role = seg.get('speaker_role', seg.get('speaker_id', 'Unknown')).title()
            if text:
                conversation_lines.append(f"[{timestamp:.1f}s] {speaker_role}: {text}")

        conversation_text = "\n".join(conversation_lines)

        # ✨ NEW: Fetch schema from database
        schema = get_form_schema_from_db(request.form_type)
        print(f"📊 Using schema from database for {request.form_type}")

        # ✨ NEW: Flatten schema for LLM extraction
        flattened_schema, field_mapping = flatten_schema_for_extraction(schema)
        schema_hints = build_extraction_prompt_hints_from_flattened_schema(flattened_schema)

        print(f"📊 Flattened {len(flattened_schema)} fields for extraction")
        print(f"   Field mapping has {len(field_mapping)} entries")

        # Build patient context section for the prompt
        patient_context_text = ""
        if request.patient_context:
            demographics = request.patient_context.get('demographics', {})
            medications = request.patient_context.get('medications', [])
            conditions = request.patient_context.get('conditions', [])
            allergies = request.patient_context.get('allergies', [])

            # Build patient profile summary
            patient_parts = []
            if demographics.get('name'):
                patient_parts.append(f"Name: {demographics['name']}")
            if demographics.get('age_years'):
                patient_parts.append(f"Age: {demographics['age_years']} years")
            if demographics.get('sex'):
                patient_parts.append(f"Sex: {demographics['sex']}")

            if patient_parts:
                patient_context_text = f"\n\nPatient Profile:\n{', '.join(patient_parts)}"

            # Add medications if any
            if medications:
                meds_text = "\n".join([
                    f"- {med['name']}" + (f" ({med['dosage']})" if med.get('dosage') else "")
                    for med in medications[:5]  # Limit to 5 most relevant
                ])
                patient_context_text += f"\n\nCurrent Medications:\n{meds_text}"

            # Add conditions if any
            if conditions:
                conds_text = "\n".join([
                    f"- {cond['name']}" + (f" ({cond['status']})" if cond.get('status') else "")
                    for cond in conditions[:5]  # Limit to 5 most relevant
                ])
                patient_context_text += f"\n\nMedical History:\n{conds_text}"

            # Add allergies if any (critical for safety)
            if allergies:
                allergies_text = "\n".join([
                    f"- {allergy['allergen']}" + (f" ({allergy.get('severity', 'unknown')} severity)" if allergy.get('severity') else "")
                    for allergy in allergies
                ])
                patient_context_text += f"\n\nAllergies:\n{allergies_text}"

        # Build Claude prompt for extraction
        system_prompt = f"""You are a medical data extraction specialist. Your task is to extract structured clinical data from a doctor-patient consultation dialogue.

Extract information from BOTH doctor and patient statements. Patient responses often contain critical medical information (e.g., previous pregnancies, symptoms, medical history).

Extract ONLY information explicitly stated in the conversation. Do NOT infer, guess, or make assumptions.
{patient_context_text}

Form Type: {request.form_type.upper()}
Available Fields:
{schema_hints}

Rules:
1. Extract from BOTH doctor questions AND patient answers
2. Patient responses are the primary source of medical history data
3. Extract only NEW information not in current_form_state
4. Use SIMPLE field names from the Available Fields list above (e.g., "weight", "bp", "fhr" not "vital_signs.systolic_bp")
5. Convert units where needed (Fahrenheit → Celsius, text → numbers)
6. Skip extraction if confidence < 0.7
7. For blood pressure, use "bp" field with format "120/80"
8. Return JSON with field_updates and confidence_scores
9. Use patient context (demographics, medications, conditions, allergies) to validate and contextualize extracted information

Examples:
- Doctor: "Any previous pregnancies?" → Patient: "Yes, two" → Extract: "gravida": 2
- Doctor: "Blood pressure is 120 over 80" → Extract: "bp": "120/80"
- Doctor: "Weight is 61 kilos" → Extract: "weight": 61
- Doctor: "Fetal heart rate is 170" → Extract: "fhr": 170
- Patient: "I've been bleeding heavily for 3 days" → Extract relevant symptoms

Current Form State (DO NOT extract these fields):
{json.dumps(request.current_form_state, indent=2)}"""

        user_prompt = f"""Doctor-patient conversation from consultation chunk #{request.chunk_index}:

{conversation_text}

Extract all relevant clinical data as JSON:
{{
  "field_updates": {{
    "field.path": value,
    ...
  }},
  "confidence_scores": {{
    "field.path": 0.0-1.0,
    ...
  }}
}}"""

        # Create local Anthropic client for Claude API calls
        import anthropic
        anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Use Claude to extract fields
        message = anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",  # Fast, cost-effective model
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )

        # Parse Claude response
        response_text = message.content[0].text.strip()

        # Extract JSON from response (may have markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to parse the whole response as JSON
            json_str = response_text

        try:
            extraction_result = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"⚠️  Failed to parse Claude response as JSON: {e}")
            print(f"Response: {response_text[:500]}")
            return ExtractFormFieldsResponse(
                field_updates={},
                confidence_scores={},
                chunk_index=request.chunk_index,
                extraction_metadata={
                    "segments_analyzed": len(request.diarized_segments),
                    "conversation_segments": len(all_segments),
                    "processing_time_ms": int((time.time() - start_time) * 1000),
                    "error": "Failed to parse extraction result"
                }
            )

        field_updates = extraction_result.get("field_updates", {})
        confidence_scores = extraction_result.get("confidence_scores", {})

        print(f"📝 LLM extracted {len(field_updates)} fields (flat format)")
        print(f"   Raw extraction: {field_updates}")
        print(f"   Confidence scores: {confidence_scores}")

        # ✨ IMPORTANT: Filter by confidence BEFORE mapping (while field names still match)
        field_updates = filter_by_confidence(field_updates, confidence_scores, min_confidence=0.7)
        print(f"📝 After confidence filter: {len(field_updates)} fields (still flat)")
        print(f"   Remaining: {field_updates}")

        # ✨ NEW: Map flat field names back to nested structure
        field_updates = map_flat_fields_to_nested(field_updates, field_mapping)
        print(f"📝 Mapped to {len(field_updates)} nested fields")
        print(f"   After mapping: {field_updates}")

        # ✨ NEW: Apply historical consultation aggregation for fields marked with requires_previous_consultations
        patient_id = request.patient_context.get('demographics', {}).get('patient_id') or request.patient_context.get('patient_id')
        field_updates = await apply_historical_aggregation(
            field_updates=field_updates,
            schema=schema,
            patient_context=request.patient_context,
            form_type=request.form_type,
            patient_id=patient_id
        )
        print(f"📝 After historical aggregation: {len(field_updates)} fields")

        # Exclude fields already in current form state (smart version that keeps aggregated arrays)
        field_updates = exclude_existing_fields_smart(field_updates, request.current_form_state)
        print(f"📝 After smart exclude: {len(field_updates)} fields")
        print(f"   Remaining: {field_updates}")

        # Validate all extracted fields
        valid_updates, validation_errors = validate_multiple_fields(
            request.form_type,
            field_updates
        )

        if validation_errors:
            print(f"⚠️  Validation errors: {validation_errors}")

        print(f"📝 After validation: {len(valid_updates)} fields")
        print(f"   Valid updates: {valid_updates}")

        # Filter confidence scores to only validated fields
        validated_confidence = {
            k: confidence_scores.get(k, 0.0)
            for k in valid_updates.keys()
        }

        processing_time_ms = int((time.time() - start_time) * 1000)

        print(f"✅ Extracted {len(valid_updates)} fields in {processing_time_ms}ms")

        return ExtractFormFieldsResponse(
            field_updates=valid_updates,
            confidence_scores=validated_confidence,
            chunk_index=request.chunk_index,
            extraction_metadata={
                "segments_analyzed": len(request.diarized_segments),
                "conversation_segments": len(all_segments),
                "processing_time_ms": processing_time_ms,
                "validation_errors_count": len(validation_errors)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error extracting form fields: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to extract form fields: {str(e)}")


@app.post("/api/auto-fill-consultation-form", response_model=AutoFillConsultationFormResponse)
async def auto_fill_consultation_form(request: AutoFillConsultationFormRequest):
    """
    Intelligently detect consultation type, create/update form, and auto-fill fields.

    Workflow:
    1. Parse diarized transcript
    2. Call determine_consultation_type() to detect type
    3. Check if form already exists in database
    4. Create new form if missing, or get existing form
    5. Call extract_form_fields() to extract data
    6. Update form with extracted fields
    7. Return success response with form details
    """
    try:
        from datetime import datetime
        import traceback

        # Initialize Supabase client
        supabase = get_supabase_client()

        # Step 1: Parse diarized segments
        diarized_segments = parse_diarized_transcript(request.original_transcript)

        # Step 2: Determine consultation type using existing endpoint function
        type_request = DetermineConsultationTypeRequest(
            diarized_segments=diarized_segments,
            doctor_specialty='obgyn',
            patient_context={
                'patient_id': request.patient_id,
                'consultation_id': request.consultation_id
            }
        )
        type_result = await determine_consultation_type(type_request)

        consultation_type = type_result.consultation_type
        confidence = type_result.confidence
        reasoning = type_result.reasoning

        print(f"📊 Detected: {consultation_type} (confidence: {confidence:.2f})")

        # Step 3: Check if form exists in unified consultation_forms table
        # ✨ NEW: Using unified table with JSONB storage
        existing_form = supabase.table('consultation_forms').select('id, form_data').eq(
            'appointment_id', request.appointment_id
        ).eq(
            'form_type', consultation_type
        ).execute()

        form_created = False

        if existing_form.data and len(existing_form.data) > 0:
            # Form exists - update it
            form_id = existing_form.data[0]['id']
            # Get existing form_data for context
            current_form_state = existing_form.data[0].get('form_data', {})
            print(f"📝 Found existing form: {form_id}")
            print(f"   Existing fields: {list(current_form_state.keys())[:5]}...")
        else:
            # Step 4: Create new form
            print(f"➕ Creating new {consultation_type} form...")

            # Get Firebase UID from consultation.performed_by (doctor who performed the consultation)
            # After migration, created_by is TEXT type and accepts Firebase UIDs directly
            user_id = None
            try:
                consultation = supabase.table('consultations')\
                    .select('performed_by')\
                    .eq('id', request.consultation_id)\
                    .single()\
                    .execute()

                if consultation.data and consultation.data.get('performed_by'):
                    user_id = consultation.data['performed_by']
                    print(f"✅ Using consultation.performed_by as created_by: {user_id[:8]}...")
                else:
                    print(f"⚠️  Consultation has no performed_by field")
            except Exception as e:
                print(f"⚠️  Failed to fetch consultation: {e}")

            # Fallback: Try patient_snapshot.user_id
            if not user_id:
                user_id = request.patient_snapshot.get('user_id')
                if user_id:
                    print(f"✅ Using patient_snapshot.user_id as created_by: {user_id[:8]}...")

            # Final fallback: Use system default if still no user_id
            if not user_id:
                user_id = '8c55534b-3c7a-436a-bb00-70dc6722439f'
                print(f"⚠️  Using system default as created_by: {user_id[:8]}...")

            # Fetch appointment to get scheduled date for auto-fill
            initial_form_data = {}
            try:
                appointment_result = supabase.table("appointments")\
                    .select("scheduled_time")\
                    .eq("id", request.appointment_id)\
                    .single()\
                    .execute()

                if appointment_result.data and 'scheduled_time' in appointment_result.data:
                    # Extract date from scheduled_time (format: YYYY-MM-DD)
                    appointment_date = appointment_result.data['scheduled_time'][:10]

                    # Initialize form_data with visit_records containing appointment date
                    # This matches the antenatal form schema structure
                    initial_form_data = {
                        'antenatal_visits': {
                            'visit_records': [
                                {
                                    'visit_date': appointment_date
                                }
                            ]
                        }
                    }
                    print(f"📅 Auto-filled visit date: {appointment_date}")
            except Exception as e:
                print(f"⚠️  Could not fetch appointment date: {e}")
                # Continue with empty form_data if appointment fetch fails

            # ✨ NEW: Create form in unified consultation_forms table with JSONB
            new_form_data = {
                'patient_id': request.patient_id,
                'appointment_id': request.appointment_id,
                'form_type': consultation_type,
                'specialty': 'obstetrics_gynecology',  # Based on doctor_specialty
                'form_data': initial_form_data,  # Pre-populated with appointment date
                'status': 'draft',
                'created_by': user_id,
                'updated_by': user_id,
                'filled_by': user_id
            }

            new_form = supabase.table('consultation_forms').insert(new_form_data).execute()

            if new_form.data and len(new_form.data) > 0:
                form_id = new_form.data[0]['id']
                current_form_state = {}
                form_created = True
                print(f"✅ Created form in consultation_forms: {form_id}")
            else:
                raise Exception("Failed to create form")

        # Step 4b: Fetch comprehensive patient context (filtered by form_type for targeted aggregation)
        patient_context = fetch_patient_context(request.patient_id, form_type=consultation_type)
        patient_context['patient_id'] = request.patient_id  # Keep patient_id for backward compatibility
        patient_context['demographics']['patient_id'] = request.patient_id  # Also add to demographics for aggregation

        # Step 5: Extract form fields using existing endpoint function
        extraction_request = ExtractFormFieldsRequest(
            diarized_segments=diarized_segments,
            form_type=consultation_type,
            patient_context=patient_context,
            current_form_state=current_form_state,
            chunk_index=0
        )
        extraction_result = await extract_form_fields(extraction_request)

        field_updates = extraction_result.field_updates

        # Step 6: Update form with extracted fields
        if field_updates:
            print(f"🔄 Updating form with {len(field_updates)} fields...")
            print(f"   Fields to update: {list(field_updates.keys())}")

            # ✨ NEW: Deep merge extracted fields into form_data JSONB
            # Deep merge preserves nested structures and arrays (critical for aggregation)
            merged_form_data = deep_merge(current_form_state, field_updates)
            print(f"🔄 Deep merged form data:")
            print(f"   Current state had {len(current_form_state)} top-level keys")
            print(f"   Field updates have {len(field_updates)} nested paths")
            print(f"   Merged result has {len(merged_form_data)} top-level keys")

            # Update the form
            user_id = request.patient_snapshot.get('user_id')
            from datetime import timezone

            update_payload = {
                'form_data': merged_form_data,  # Store in JSONB column
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'status': 'partial'  # Mark as partially filled
            }

            if user_id:
                update_payload['updated_by'] = user_id

            try:
                supabase.table('consultation_forms').update(update_payload).eq(
                    'id', form_id
                ).execute()
                print(f"✅ Form updated successfully (JSONB storage)")
                print(f"   Total fields in form_data: {len(merged_form_data)}")
            except Exception as e:
                print(f"❌ Error updating form: {str(e)}")
                # Don't fail the entire request if update fails
                # The extraction was successful, just log the error

        # Step 6b: Update consultation with detected_consultation_type
        try:
            supabase.table('consultations').update({
                'detected_consultation_type': consultation_type
            }).eq('id', request.consultation_id).execute()
            print(f"✅ Updated consultation with detected type: {consultation_type}")
        except Exception as e:
            print(f"⚠️ Failed to update consultation detected_consultation_type: {e}")
            # Don't fail the request if this update fails

        # Step 7: Return success
        return AutoFillConsultationFormResponse(
            success=True,
            consultation_type=consultation_type,
            confidence=confidence,
            reasoning=reasoning,
            form_id=form_id,
            form_created=form_created,
            field_updates=field_updates
        )

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()

        # Return error but don't raise (don't block re-summarize)
        return AutoFillConsultationFormResponse(
            success=False,
            consultation_type='obgyn',
            confidence=0.0,
            reasoning='Error occurred during form auto-fill',
            form_id='',
            form_created=False,
            field_updates={},
            error=str(e)
        )


# =============================================================================
# HELPER FUNCTIONS FOR AUTO-FILL CONSULTATION FORM
# =============================================================================

# ✨ REMOVED: FORM_TABLE_MAP - Now using unified consultation_forms table

def get_supabase_client():
    """Initialize Supabase client with service key for backend operations."""
    from supabase import create_client, Client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(
            status_code=500,
            detail="Supabase credentials not configured"
        )

    return create_client(supabase_url, supabase_key)


def fetch_patient_context(patient_id: str, form_type: str = None) -> dict:
    """
    Fetch comprehensive patient context for form filling.

    Retrieves:
    - Demographics (age, sex, name)
    - Current medications
    - Medical conditions/history
    - Allergies
    - Previous consultation form data (WITH ACTUAL FORM DATA for aggregation)

    Args:
        patient_id: UUID of the patient
        form_type: Optional form type to filter historical forms (e.g., 'antenatal')

    Returns:
        Dictionary containing patient context with keys:
        - demographics: {age_years, sex, name, date_of_birth, patient_id}
        - medications: List of current medications
        - conditions: List of medical conditions
        - allergies: List of allergies
        - previous_forms: List of completed forms WITH ACTUAL FORM DATA
    """
    try:
        supabase = get_supabase_client()
        context = {
            'demographics': {},
            'medications': [],
            'conditions': [],
            'allergies': [],
            'previous_forms': []
        }

        # 1. Fetch basic demographics from patients table
        patient_result = supabase.table('patients').select(
            'name, sex, date_of_birth, age_years, height_cm, weight_kg, current_medications, current_conditions, allergies'
        ).eq('id', patient_id).single().execute()

        if patient_result.data:
            patient = patient_result.data

            # Calculate age from date_of_birth if available
            age_years = patient.get('age_years')
            if not age_years and patient.get('date_of_birth'):
                from datetime import datetime
                dob = datetime.fromisoformat(patient['date_of_birth'].replace('Z', '+00:00'))
                today = datetime.now()
                age_years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

            context['demographics'] = {
                'name': patient.get('name'),
                'sex': patient.get('sex'),
                'age_years': age_years,
                'date_of_birth': patient.get('date_of_birth'),
                'height_cm': float(patient['height_cm']) if patient.get('height_cm') else None,
                'weight_kg': float(patient['weight_kg']) if patient.get('weight_kg') else None
            }

            # Legacy text fields for medications/conditions/allergies
            if patient.get('current_medications'):
                context['medications_text'] = patient['current_medications']
            if patient.get('current_conditions'):
                context['conditions_text'] = patient['current_conditions']
            if patient.get('allergies'):
                context['allergies_text'] = patient['allergies']

        # 2. Fetch active medications from patient_medications table
        meds_result = supabase.table('patient_medications').select(
            'medication_name, dosage, frequency, indication, started_date'
        ).eq('patient_id', patient_id).eq('status', 'active').execute()

        if meds_result.data:
            context['medications'] = [
                {
                    'name': med['medication_name'],
                    'dosage': med.get('dosage'),
                    'frequency': med.get('frequency'),
                    'indication': med.get('indication'),
                    'started_date': med.get('started_date')
                }
                for med in meds_result.data
            ]

        # 3. Fetch active medical conditions
        conditions_result = supabase.table('patient_conditions').select(
            'condition_name, icd10_code, diagnosed_date, status'
        ).eq('patient_id', patient_id).in_('status', ['active', 'chronic']).execute()

        if conditions_result.data:
            context['conditions'] = [
                {
                    'name': cond['condition_name'],
                    'icd10_code': cond.get('icd10_code'),
                    'diagnosed_date': cond.get('diagnosed_date'),
                    'status': cond.get('status')
                }
                for cond in conditions_result.data
            ]

        # 4. Fetch active allergies
        allergies_result = supabase.table('patient_allergies').select(
            'allergen, allergen_category, reaction, severity'
        ).eq('patient_id', patient_id).eq('status', 'active').execute()

        if allergies_result.data:
            context['allergies'] = [
                {
                    'allergen': allergy['allergen'],
                    'category': allergy.get('allergen_category'),
                    'reaction': allergy.get('reaction'),
                    'severity': allergy.get('severity')
                }
                for allergy in allergies_result.data
            ]

        # 5. Fetch recent consultation forms WITH ACTUAL DATA (last 10 forms, any status)
        # Note: Include both 'partial' and 'completed' to aggregate ongoing consultations
        query = supabase.table('consultation_forms').select(
            'id, form_type, specialty, created_at, form_data, status, appointment_id'
        ).eq('patient_id', patient_id).in_('status', ['partial', 'completed'])

        # Filter by form_type if specified (for targeted historical aggregation)
        if form_type:
            query = query.eq('form_type', form_type)
            print(f"📋 Filtering previous forms by form_type: {form_type}")

        forms_result = query.order('created_at', desc=True).limit(10).execute()

        if forms_result.data:
            context['previous_forms'] = [
                {
                    'id': form['id'],
                    'form_type': form['form_type'],
                    'specialty': form.get('specialty'),
                    'created_at': form.get('created_at'),
                    'appointment_id': form.get('appointment_id'),
                    'form_data': form.get('form_data', {})  # ✅ Include actual data for aggregation!
                }
                for form in forms_result.data
            ]
            print(f"📋 Fetched {len(context['previous_forms'])} previous forms with data")

        print(f"📋 Fetched patient context: {context['demographics'].get('name')}, "
              f"{len(context.get('medications', []))} medications, "
              f"{len(context.get('conditions', []))} conditions, "
              f"{len(context.get('allergies', []))} allergies")

        return context

    except Exception as e:
        print(f"⚠️  Error fetching patient context: {e}")
        # Return empty context rather than failing
        return {
            'demographics': {},
            'medications': [],
            'conditions': [],
            'allergies': [],
            'previous_forms': []
        }


def deep_merge(dict1: dict, dict2: dict) -> dict:
    """
    Deep merge two dictionaries, recursively merging nested dicts and arrays.

    Rules:
    - Scalars in dict2 overwrite dict1
    - Arrays in dict2 extend (append to) dict1
    - Nested dicts merge recursively

    Args:
        dict1: Base dictionary (historical/existing data)
        dict2: Override dictionary (new/current data)

    Returns:
        Merged dictionary
    """
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result:
            existing = result[key]

            # Both are dicts: recurse
            if isinstance(existing, dict) and isinstance(value, dict):
                result[key] = deep_merge(existing, value)

            # Both are lists: extend
            elif isinstance(existing, list) and isinstance(value, list):
                result[key] = existing + value

            # Otherwise: override
            else:
                result[key] = value
        else:
            result[key] = value

    return result


def extract_historical_field_data(
    field_schema: dict,
    previous_forms: list,
    field_path: str
) -> list:
    """
    Extract historical data for a field marked with requires_previous_consultations.

    Args:
        field_schema: The field definition with aggregation metadata
        previous_forms: List of previous consultation form objects
        field_path: Nested path to the field (e.g., "antenatal_visits.visit_records")

    Returns:
        List of historical rows (for array fields) or list with single value (for simple fields)
    """
    if not field_schema.get('requires_previous_consultations'):
        return []

    historical_data = []

    # Apply filters
    filters = field_schema.get('historical_filters', {})
    filtered_forms = [
        form for form in previous_forms
        if all(form.get(k) == v for k, v in filters.items())
    ]

    print(f"📊 Found {len(filtered_forms)} forms matching filters {filters}")

    # Apply max_historical_records limit
    max_records = field_schema.get('max_historical_records')
    if max_records is not None:
        filtered_forms = filtered_forms[:max_records]
        print(f"📊 Limited to {max_records} most recent forms")

    # Extract data from each historical form
    for form in filtered_forms:
        form_data = form.get('form_data', {})

        # Try two approaches to find the data:
        # 1. NESTED structure: {"antenatal_visits": {"visit_records": [...]}}
        # 2. FLAT structure: {"antenatal_visits.visit_records": [...]}

        value = None

        # First try flat structure (direct key lookup)
        if field_path in form_data:
            value = form_data[field_path]
            print(f"   Found data in FLAT structure: {field_path}")
        else:
            # Try nested structure (navigate through parts)
            parts = field_path.split('.')
            value = form_data

            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break

            if value is not None:
                print(f"   Found data in NESTED structure: {field_path}")

        if value is not None:
            # For array fields, extend the list
            if field_schema.get('type') == 'array' and isinstance(value, list):
                historical_data.extend(value)
            else:
                # For simple fields, append single value
                historical_data.append(value)

    print(f"📊 Extracted {len(historical_data)} historical records for {field_path}")
    return historical_data


def aggregate_field_data(
    current_data: any,
    historical_data: list,
    aggregation_strategy: str
) -> any:
    """
    Merge current data with historical data using specified strategy.

    Args:
        current_data: Data from current consultation (new row)
        historical_data: Data from previous consultations
        aggregation_strategy: 'append' | 'replace' | 'merge'

    Returns:
        Merged data
    """
    if aggregation_strategy == 'replace':
        # Replace historical with current (rare use case)
        return current_data

    elif aggregation_strategy == 'append':
        # Append current to historical (most common for visit tracking)
        if isinstance(historical_data, list):
            # Ensure current_data is also a list
            if isinstance(current_data, list):
                return historical_data + current_data
            elif current_data is not None:
                return historical_data + [current_data]
            else:
                return historical_data
        else:
            return current_data or historical_data

    elif aggregation_strategy == 'merge':
        # Deep merge objects (useful for nested data)
        if isinstance(historical_data, dict) and isinstance(current_data, dict):
            return deep_merge(historical_data, current_data)
        else:
            return current_data or historical_data

    else:
        print(f"⚠️  Unknown aggregation_strategy: {aggregation_strategy}")
        return current_data


async def apply_historical_aggregation(
    field_updates: dict,
    schema: dict,
    patient_context: dict,
    form_type: str,
    patient_id: str = None
) -> dict:
    """
    Apply historical consultation aggregation to fields marked with
    requires_previous_consultations.

    Args:
        field_updates: Current field updates from LLM extraction {nested_path: value}
        schema: Full form schema from database
        patient_context: Patient context (may not have previous_forms yet)
        form_type: Current form type (e.g., 'antenatal')
        patient_id: Optional patient ID to fetch previous forms if not in context

    Returns:
        Enhanced field_updates with historical data aggregated
    """
    # Fetch previous forms if not already in context
    previous_forms = patient_context.get('previous_forms', [])

    if not previous_forms:
        # Try to get patient_id from context if not provided
        if not patient_id:
            patient_id = patient_context.get('demographics', {}).get('patient_id')

        if patient_id:
            print(f"📋 Fetching previous {form_type} forms for aggregation")
            enhanced_context = fetch_patient_context(patient_id, form_type=form_type)
            previous_forms = enhanced_context.get('previous_forms', [])

    if not previous_forms:
        print(f"📋 No previous forms found, skipping aggregation")
        return field_updates

    print(f"📋 Applying historical aggregation with {len(previous_forms)} previous forms")

    aggregated_updates = {}

    # Iterate through schema to find fields with requires_previous_consultations
    for section_name, section_def in schema.items():
        if not isinstance(section_def, dict):
            continue

        fields = section_def.get('fields', [])
        if not isinstance(fields, list):
            continue

        for field in fields:
            if not isinstance(field, dict):
                continue

            field_name = field.get('name')
            if not field_name:
                continue

            # Check if this field requires historical aggregation
            if not field.get('requires_previous_consultations'):
                continue

            field_path = f"{section_name}.{field_name}"
            print(f"📊 Processing aggregation for: {field_path}")

            # Extract historical data
            historical_data = extract_historical_field_data(
                field_schema=field,
                previous_forms=previous_forms,
                field_path=field_path
            )

            # Get current data (if any) from field_updates
            current_data = field_updates.get(field_path)

            # Aggregate using specified strategy
            aggregation_strategy = field.get('aggregation_strategy', 'append')
            aggregated_value = aggregate_field_data(
                current_data=current_data,
                historical_data=historical_data,
                aggregation_strategy=aggregation_strategy
            )

            # Store aggregated result
            if aggregated_value is not None:
                aggregated_updates[field_path] = aggregated_value
                print(f"✅ Aggregated {field_path}: {len(aggregated_value) if isinstance(aggregated_value, list) else 'single value'}")

    # Merge aggregated updates back into field_updates
    final_updates = {**field_updates, **aggregated_updates}

    print(f"📊 Aggregation complete: {len(aggregated_updates)} fields enhanced")
    return final_updates


def exclude_existing_fields_smart(field_updates: dict, current_form_state: dict) -> dict:
    """
    Exclude fields that already have data in current form state.

    ENHANCED: For array fields with aggregated data, DO NOT exclude
    because we want to show aggregated historical + current data.

    Args:
        field_updates: Extracted field updates {nested_path: value}
        current_form_state: Current form data from database

    Returns:
        Filtered field_updates
    """
    filtered = {}

    for field_path, new_value in field_updates.items():
        # Navigate to existing value
        parts = field_path.split('.')
        existing_value = current_form_state

        for part in parts:
            if isinstance(existing_value, dict) and part in existing_value:
                existing_value = existing_value[part]
            else:
                existing_value = None
                break

        # Include field if:
        # 1. No existing value
        # 2. New value is an array (likely aggregated historical data)
        # 3. Existing value is different from new value

        if existing_value is None:
            filtered[field_path] = new_value
        elif isinstance(new_value, list):
            # Always include arrays (aggregated data)
            filtered[field_path] = new_value
        elif existing_value != new_value:
            filtered[field_path] = new_value
        else:
            print(f"⏭️  Skipping {field_path}: already has value {existing_value}")

    return filtered


# @lru_cache(maxsize=32)  # DISABLED: Need fresh data from custom_forms table
def _get_form_schema_from_db_cached(form_type: str, full_metadata: bool = False) -> dict:
    """
    Internal cached function for fetching form schemas from database.

    DO NOT CALL DIRECTLY - use get_form_schema_from_db() instead.
    This function is cached and returns the same object instance.
    """
    try:
        supabase = get_supabase_client()

        # Query custom_forms table (unified source of truth)
        # Match by either specialty OR form_name (form_type could be either)
        print(f"🔍 Querying custom_forms for form_type: {form_type}")

        # Query ALL forms (active and draft) and filter manually
        result = supabase.table('custom_forms')\
            .select('form_schema, version, description, specialty, form_name, updated_at, status')\
            .in_('status', ['active', 'draft'])\
            .execute()

        print(f"📦 Found {len(result.data) if result.data else 0} forms total")

        # Debug: Show what forms we have
        if result.data:
            for i, form in enumerate(result.data):
                print(f"   Form {i+1}: form_name='{form.get('form_name')}', specialty='{form.get('specialty')}', status='{form.get('status')}'")

        # Filter for matching form_type (by specialty, form_name, or form_name starts with form_type)
        matching_forms = [
            form for form in (result.data or [])
            if (form.get('specialty') == form_type or
                form.get('form_name') == form_type or
                form.get('form_name', '').startswith(form_type + '_') or
                form.get('form_name', '').startswith(form_type))
        ]

        print(f"📊 Found {len(matching_forms)} forms matching form_type '{form_type}'")

        if not matching_forms:
            raise HTTPException(
                status_code=404,
                detail=f"No active forms found for form_type: {form_type}"
            )

        # Sort by updated_at DESC and take the first (most recent)
        form_data = sorted(matching_forms, key=lambda x: x.get('updated_at', ''), reverse=True)[0]
        print(f"✅ Using form: {form_data.get('form_name')} (specialty: {form_data.get('specialty')})")

        # ✅ VALIDATE SCHEMA IS NOT EMPTY
        form_schema = form_data.get('form_schema')
        if not form_schema or not isinstance(form_schema, dict):
            print(f"⚠️  WARNING: Form {form_data.get('form_name')} has invalid schema: {type(form_schema)}")
            raise HTTPException(
                status_code=500,
                detail=f"Form schema is invalid or empty for {form_type}. Please re-upload the form."
            )

        schema_keys = list(form_schema.keys()) if isinstance(form_schema, dict) else []
        if len(schema_keys) == 0:
            print(f"⚠️  WARNING: Form {form_data.get('form_name')} has empty schema")
            raise HTTPException(
                status_code=500,
                detail=f"Form schema contains no fields for {form_type}. Please re-upload the form."
            )

        print(f"📊 Schema loaded with {len(schema_keys)} sections/fields")

        if full_metadata:
            # Return all metadata for frontend
            return {
                'schema': form_data['form_schema'],
                'title': form_data.get('description', ''),
                'description': form_data.get('description', ''),
                'version': form_data.get('version', 1),
                'form_type': form_data.get('specialty', ''),
                'specialty': form_data.get('specialty', ''),
            }
        else:
            # Return only schema definition (for extraction)
            return form_data['form_schema']

    except Exception as e:
        print(f"❌ Error fetching schema for {form_type}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch schema from database: {str(e)}"
        )


def get_form_schema_from_db(form_type: str, full_metadata: bool = False) -> dict:
    """
    Fetch form schema from database with LRU caching.

    Schemas are cached in memory (max 32 entries) and automatically evicted
    when the cache is full. Returns a deep copy to prevent cache pollution.

    Single source of truth for all form schemas.

    Args:
        form_type: The form type to fetch (e.g., 'antenatal', 'obgyn')
        full_metadata: If True, returns full metadata (title, description, version)
                      If False, returns only schema_definition (default for backwards compatibility)

    Returns:
        dict: Deep copy of schema definition or full metadata depending on full_metadata flag

    Cache Info:
        - Cache size: 32 entries max
        - Cache lifetime: Until backend restart
        - Invalidation: Automatic on backend restart or manual via _get_form_schema_from_db_cached.cache_clear()
    """
    # Return deep copy to prevent callers from mutating the cached object
    return copy.deepcopy(_get_form_schema_from_db_cached(form_type, full_metadata))


def flatten_schema_for_extraction(schema: dict) -> tuple[dict, dict]:
    """
    Flatten nested schema into simple fields for LLM extraction.

    Returns:
        - flattened_schema: Dict of {simple_field_name: field_definition}
        - field_mapping: Dict of {simple_field_name: nested_field_path}
    """
    flattened_schema = {}
    field_mapping = {}

    for section_name, section_def in schema.items():
        if not isinstance(section_def, dict):
            continue

        # NEW: Database schema has fields as ARRAY
        if 'fields' in section_def and isinstance(section_def['fields'], list):
            for field in section_def['fields']:
                if not isinstance(field, dict):
                    continue

                field_name = field.get('name', '')
                if not field_name:
                    continue

                # For array/table fields, flatten the row_fields
                if field.get('type') == 'array' and field.get('row_fields'):
                    for row_field in field.get('row_fields', []):
                        if isinstance(row_field, dict):
                            row_field_name = row_field.get('name', '')
                            if row_field_name:
                                # Create simple field name (e.g., "weight" instead of "antenatal_visits.visit_records.weight")
                                simple_name = row_field_name
                                nested_path = f"{section_name}.{field_name}.{row_field_name}"

                                flattened_schema[simple_name] = row_field
                                field_mapping[simple_name] = nested_path

                                # Also add with prefix for disambiguation (e.g., "visit_weight")
                                prefixed_name = f"{field_name.replace('_records', '')}_{row_field_name}"
                                flattened_schema[prefixed_name] = row_field
                                field_mapping[prefixed_name] = nested_path
                else:
                    # Simple field - use field name directly
                    simple_name = field_name
                    nested_path = f"{section_name}.{field_name}"

                    flattened_schema[simple_name] = field
                    field_mapping[simple_name] = nested_path

    return flattened_schema, field_mapping


def build_extraction_prompt_hints_from_flattened_schema(flattened_schema: dict) -> str:
    """
    Build extraction hints from flattened schema.
    """
    hints = []

    for field_name, field_def in flattened_schema.items():
        field_label = field_def.get('label', field_name)
        field_type = field_def.get('type', 'string')
        field_hints = field_def.get('extraction_hints', [])

        hint_parts = [f"- {field_name}"]

        # Add label if different
        if field_label and field_label != field_name:
            hint_parts.append(f"({field_label})")

        # Add type
        hint_parts.append(f"[{field_type}]")

        # Add extraction hints
        if field_hints:
            hints_str = ', '.join(field_hints)
            hint_parts.append(f": {hints_str}")

        hints.append(' '.join(hint_parts))

    return '\n'.join(hints) if hints else "No fields available"


def map_flat_fields_to_nested(flat_updates: dict, field_mapping: dict) -> dict:
    """
    Convert flat field updates back to nested structure.

    Args:
        flat_updates: Dict of {simple_field_name: value}
        field_mapping: Dict of {simple_field_name: nested_field_path}

    Returns:
        Dict of {nested_path: value}
    """
    nested_updates = {}

    for field_name, value in flat_updates.items():
        # Look up the nested path
        nested_path = field_mapping.get(field_name)

        if nested_path:
            # Handle array fields (e.g., antenatal_visits.visit_records.weight)
            if '..' in nested_path or nested_path.count('.') > 1:
                # This is a nested array field - wrap in array structure
                parts = nested_path.split('.')
                if len(parts) == 3:
                    section, array_field, row_field = parts
                    # Create array with single row containing this field
                    array_path = f"{section}.{array_field}"
                    if array_path not in nested_updates:
                        nested_updates[array_path] = [{}]
                    nested_updates[array_path][0][row_field] = value
            else:
                # Simple nested field
                nested_updates[nested_path] = value
        else:
            # No mapping found - use as-is (might be a direct field)
            nested_updates[field_name] = value

    return nested_updates


def build_extraction_prompt_hints_from_schema(schema: dict) -> str:
    """
    Build extraction hints from schema definition.
    DEPRECATED: Use flatten_schema_for_extraction + build_extraction_prompt_hints_from_flattened_schema
    """
    hints = []

    for section_name, section_def in schema.items():
        if isinstance(section_def, dict):
            # NEW: Database schema has fields as ARRAY
            if 'fields' in section_def and isinstance(section_def['fields'], list):
                for field in section_def['fields']:
                    if isinstance(field, dict):
                        field_name = field.get('name', '')
                        field_hints = field.get('extraction_hints', [])
                        field_label = field.get('label', field_name)

                        if field_hints and field_name:
                            field_path = f"{section_name}.{field_name}"
                            hints_str = ', '.join(field_hints)
                            hints.append(f"- {field_path} ({field_label}): {hints_str}")

            # OLD: Python schema has fields as DICT (backwards compatibility)
            elif 'fields' in section_def and isinstance(section_def['fields'], dict):
                for field_name, field_def in section_def['fields'].items():
                    if isinstance(field_def, dict) and 'extraction_hints' in field_def:
                        field_hints = field_def['extraction_hints']
                        if field_hints:
                            field_path = f"{section_name}.{field_name}"
                            hints.append(f"- {field_path}: {', '.join(field_hints)}")

            # Top-level field with extraction hints (flat schema)
            elif 'extraction_hints' in section_def:
                field_hints = section_def['extraction_hints']
                if field_hints:
                    hints.append(f"- {section_name}: {', '.join(field_hints)}")

    return '\n'.join(hints) if hints else "No specific extraction hints available"


# ✨ REMOVED: get_default_form_data() - No longer needed with unified consultation_forms table

def parse_diarized_transcript(transcript: str) -> list:
    """
    Parse original_transcript into diarized segments format.

    Expected format:
    [0.0s] Doctor: Hello...
    [5.2s] Patient: Hi...

    Returns list of diarized segments with speaker_id, text, timestamps.
    """
    segments = []

    if not transcript:
        return segments

    lines = transcript.split('\n')

    for line in lines:
        # Pattern: [timestamp] Speaker: text
        match = re.match(r'\[(\d+\.?\d*)s\]\s*(\w+):\s*(.+)', line)
        if match:
            timestamp = float(match.group(1))
            speaker = match.group(2).lower()
            text = match.group(3).strip()

            segments.append({
                'start_time': timestamp,
                'end_time': timestamp + 1.0,
                'speaker_id': speaker,
                'speaker_role': speaker,
                'text': text
            })
        elif line.strip():
            # No timestamp - treat as doctor speaking
            segments.append({
                'start_time': 0,
                'end_time': 0,
                'speaker_id': 'doctor',
                'speaker_role': 'doctor',
                'text': line.strip()
            })

    # Fallback if no segments parsed
    if not segments and transcript:
        segments = [{
            'start_time': 0,
            'end_time': 0,
            'speaker_id': 'doctor',
            'speaker_role': 'doctor',
            'text': transcript
        }]

    return segments


# =============================================================================
# AI FEEDBACK SYSTEM FOR RLHF
# =============================================================================

class FeedbackSubmitRequest(BaseModel):
    """Request body for submitting AI feedback"""

    # Required fields
    consultation_id: str
    feedback_type: str  # 'transcription', 'summary', 'diagnosis', 'drug_recommendation'
    feedback_sentiment: str  # 'positive', 'negative'

    # Optional context fields
    component_identifier: Optional[str] = None  # e.g., 'diagnosis_0', 'drug_paracetamol'
    component_data: Optional[dict] = None  # Snapshot of content being rated

    # Diagnosis-specific
    diagnosis_text: Optional[str] = None
    is_correct_diagnosis: Optional[bool] = False

    # Drug-specific
    drug_name: Optional[str] = None
    drug_dosage: Optional[str] = None

    # User context (will be enriched server-side from JWT)
    user_id: Optional[str] = None
    user_role: Optional[str] = None

    # Additional context
    notes: Optional[str] = None
    metadata: Optional[dict] = None

    def generate_fingerprint(self) -> str:
        """Generate unique fingerprint to prevent duplicates"""
        import hashlib
        data = f"{self.consultation_id}:{self.feedback_type}:{self.component_identifier}:{self.user_id or 'anonymous'}"
        return hashlib.md5(data.encode()).hexdigest()


class FeedbackResponse(BaseModel):
    """Response after submitting feedback"""
    id: str
    success: bool
    message: str
    feedback_type: str
    feedback_sentiment: str
    created_at: str


class FeedbackStatsResponse(BaseModel):
    """Aggregated feedback statistics"""
    total_feedback_count: int
    feedback_by_type: dict
    feedback_by_sentiment: dict
    positive_percentage: float
    top_diagnoses: list
    top_drugs: list
    recent_feedback: list


@app.post("/api/feedback", response_model=FeedbackResponse)
async def submit_ai_feedback(request: FeedbackSubmitRequest):
    """
    Submit feedback on AI-generated content.

    Supports:
    - Transcription quality feedback
    - Summary quality feedback
    - Diagnosis accuracy feedback (with "correct diagnosis" marking)
    - Drug recommendation feedback

    Deduplication: Uses fingerprint to prevent duplicate submissions.
    """
    try:
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for backend operations

        if not supabase_url or not supabase_key:
            raise HTTPException(status_code=500, detail="Supabase configuration missing")

        from supabase import create_client
        supabase = create_client(supabase_url, supabase_key)

        # Validate feedback_type
        valid_types = ['transcription', 'summary', 'diagnosis', 'drug_recommendation']
        if request.feedback_type not in valid_types:
            raise HTTPException(status_code=400, detail=f"feedback_type must be one of: {valid_types}")

        # Validate feedback_sentiment
        valid_sentiments = ['positive', 'negative']
        if request.feedback_sentiment not in valid_sentiments:
            raise HTTPException(status_code=400, detail=f"feedback_sentiment must be one of: {valid_sentiments}")

        # Type-specific validation
        if request.feedback_type == 'diagnosis' and not request.diagnosis_text:
            raise HTTPException(status_code=400, detail="diagnosis_text is required for diagnosis feedback")

        if request.feedback_type == 'drug_recommendation' and not request.drug_name:
            raise HTTPException(status_code=400, detail="drug_name is required for drug recommendation feedback")

        # Set default user_role if not provided
        if not request.user_role:
            request.user_role = 'anonymous'

        # Generate fingerprint for deduplication
        fingerprint = request.generate_fingerprint()

        # Check for existing feedback with same fingerprint
        existing = supabase.table('ai_feedback').select('id').eq('fingerprint', fingerprint).execute()

        if existing.data and len(existing.data) > 0:
            # Update existing feedback instead of creating duplicate
            feedback_id = existing.data[0]['id']

            from datetime import datetime
            update_data = {
                'feedback_sentiment': request.feedback_sentiment,
                'is_correct_diagnosis': request.is_correct_diagnosis,
                'notes': request.notes,
                'metadata': request.metadata or {},
                'updated_at': datetime.utcnow().isoformat()
            }

            result = supabase.table('ai_feedback').update(update_data).eq('id', feedback_id).execute()

            return FeedbackResponse(
                id=feedback_id,
                success=True,
                message="Feedback updated successfully",
                feedback_type=request.feedback_type,
                feedback_sentiment=request.feedback_sentiment,
                created_at=datetime.utcnow().isoformat()
            )

        # Insert new feedback
        from datetime import datetime
        insert_data = {
            'consultation_id': request.consultation_id,
            'feedback_type': request.feedback_type,
            'feedback_sentiment': request.feedback_sentiment,
            'component_identifier': request.component_identifier,
            'component_data': request.component_data or {},
            'diagnosis_text': request.diagnosis_text,
            'is_correct_diagnosis': request.is_correct_diagnosis or False,
            'drug_name': request.drug_name,
            'drug_dosage': request.drug_dosage,
            'user_id': request.user_id,
            'user_role': request.user_role,
            'notes': request.notes,
            'metadata': request.metadata or {},
            'fingerprint': fingerprint
        }

        result = supabase.table('ai_feedback').insert(insert_data).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=500, detail="Failed to insert feedback")

        feedback_id = result.data[0]['id']

        print(f"✅ Feedback submitted: {feedback_id} - {request.feedback_type} ({request.feedback_sentiment})")

        return FeedbackResponse(
            id=feedback_id,
            success=True,
            message="Feedback submitted successfully",
            feedback_type=request.feedback_type,
            feedback_sentiment=request.feedback_sentiment,
            created_at=datetime.utcnow().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error submitting feedback: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


@app.get("/api/feedback/consultation/{consultation_id}")
async def get_consultation_feedback(consultation_id: str):
    """
    Retrieve all feedback for a specific consultation.
    Useful for displaying feedback history in the UI.
    """
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for backend operations

        if not supabase_url or not supabase_key:
            raise HTTPException(status_code=500, detail="Supabase configuration missing")

        from supabase import create_client
        supabase = create_client(supabase_url, supabase_key)

        result = supabase.table('ai_feedback')\
            .select('*')\
            .eq('consultation_id', consultation_id)\
            .order('created_at', desc=True)\
            .execute()

        return {
            "consultation_id": consultation_id,
            "feedback_count": len(result.data) if result.data else 0,
            "feedback": result.data if result.data else []
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error retrieving feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/feedback/stats", response_model=FeedbackStatsResponse)
async def get_feedback_stats(days: int = 30, feedback_type: Optional[str] = None):
    """
    Get aggregated feedback statistics for RLHF analysis.

    Query parameters:
    - days: Number of days to look back (default: 30)
    - feedback_type: Filter by specific type (optional)
    """
    try:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for backend operations

        if not supabase_url or not supabase_key:
            raise HTTPException(status_code=500, detail="Supabase configuration missing")

        from supabase import create_client
        from datetime import datetime, timedelta
        supabase = create_client(supabase_url, supabase_key)

        # Calculate date threshold
        date_threshold = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Build query
        query = supabase.table('ai_feedback').select('*').gte('created_at', date_threshold)

        if feedback_type:
            query = query.eq('feedback_type', feedback_type)

        result = query.execute()
        feedback_data = result.data if result.data else []

        # Aggregate statistics
        total_count = len(feedback_data)

        # Count by type
        by_type = {}
        for item in feedback_data:
            ftype = item['feedback_type']
            by_type[ftype] = by_type.get(ftype, 0) + 1

        # Count by sentiment
        by_sentiment = {}
        positive_count = 0
        for item in feedback_data:
            sent = item['feedback_sentiment']
            by_sentiment[sent] = by_sentiment.get(sent, 0) + 1
            if sent == 'positive':
                positive_count += 1

        positive_percentage = round((positive_count / total_count * 100), 2) if total_count > 0 else 0.0

        # Top diagnoses with feedback
        diagnosis_feedback = [f for f in feedback_data if f['feedback_type'] == 'diagnosis']
        diagnosis_counts = {}
        for item in diagnosis_feedback:
            diag = item.get('diagnosis_text', 'Unknown')
            if diag and diag != 'Unknown':
                if diag not in diagnosis_counts:
                    diagnosis_counts[diag] = {'positive': 0, 'negative': 0, 'correct': 0}

                if item['feedback_sentiment'] == 'positive':
                    diagnosis_counts[diag]['positive'] += 1
                else:
                    diagnosis_counts[diag]['negative'] += 1

                if item.get('is_correct_diagnosis'):
                    diagnosis_counts[diag]['correct'] += 1

        top_diagnoses = [
            {'diagnosis': diag, **counts}
            for diag, counts in sorted(
                diagnosis_counts.items(),
                key=lambda x: x[1]['positive'] + x[1]['negative'],
                reverse=True
            )[:10]
        ]

        # Top drugs with feedback
        drug_feedback = [f for f in feedback_data if f['feedback_type'] == 'drug_recommendation']
        drug_counts = {}
        for item in drug_feedback:
            drug = item.get('drug_name', 'Unknown')
            if drug and drug != 'Unknown':
                if drug not in drug_counts:
                    drug_counts[drug] = {'positive': 0, 'negative': 0}

                if item['feedback_sentiment'] == 'positive':
                    drug_counts[drug]['positive'] += 1
                else:
                    drug_counts[drug]['negative'] += 1

        top_drugs = [
            {'drug': drug, **counts}
            for drug, counts in sorted(
                drug_counts.items(),
                key=lambda x: x[1]['positive'] + x[1]['negative'],
                reverse=True
            )[:10]
        ]

        # Recent feedback (last 20)
        recent_feedback = sorted(feedback_data, key=lambda x: x['created_at'], reverse=True)[:20]

        return FeedbackStatsResponse(
            total_feedback_count=total_count,
            feedback_by_type=by_type,
            feedback_by_sentiment=by_sentiment,
            positive_percentage=positive_percentage,
            top_diagnoses=top_diagnoses,
            top_drugs=top_drugs,
            recent_feedback=[
                {
                    'id': f['id'],
                    'type': f['feedback_type'],
                    'sentiment': f['feedback_sentiment'],
                    'created_at': f['created_at']
                }
                for f in recent_feedback
            ]
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting feedback stats: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# SCHEMA ENDPOINTS
# ============================================

@app.get("/api/form-schema/{form_type}")
async def get_form_schema(form_type: str):
    """
    Get form schema from database.

    Returns the active schema definition for the specified form type.
    Frontend uses this to render forms dynamically.

    Path parameters:
    - form_type: Any form type registered in the database (e.g., 'antenatal', 'obgyn', 'infertility')

    Note: No hardcoded validation - any form type in the database is valid.
    This allows adding new form types without code changes.
    """
    try:
        print(f"📊 Fetching schema for form_type: {form_type}")

        # Fetch from database with full metadata for frontend
        schema_data = get_form_schema_from_db(form_type, full_metadata=True)

        return {
            **schema_data,
            "fetched_at": time.time()
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching schema: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/form-schemas")
async def list_form_schemas():
    """
    List all available form schemas.

    Returns metadata about all active form schemas in the system.
    """
    try:
        supabase = get_supabase_client()

        result = supabase.table('custom_forms')\
            .select('id, form_name, specialty, version, description, status, updated_at, is_public')\
            .eq('status', 'active')\
            .execute()

        return {
            "schemas": [{
                "id": s['id'],
                "form_type": s['form_name'],  # Map form_name → form_type for compatibility
                "specialty": s['specialty'],
                "version": s['version'],
                "description": s['description'],
                "is_active": s['status'] == 'active',  # Map status → is_active
                "is_public": s.get('is_public', False),
                "updated_at": s['updated_at']
            } for s in result.data],
            "count": len(result.data)
        }

    except Exception as e:
        print(f"❌ Error listing schemas: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cache-stats")
async def get_cache_stats():
    """
    Get cache statistics for monitoring schema cache performance.

    Returns hit/miss ratios and cache size information.
    """
    cache_info = _get_form_schema_from_db_cached.cache_info()
    total_requests = cache_info.hits + cache_info.misses
    hit_rate = cache_info.hits / total_requests if total_requests > 0 else 0

    return {
        "schema_cache": {
            "hits": cache_info.hits,
            "misses": cache_info.misses,
            "maxsize": cache_info.maxsize,
            "currsize": cache_info.currsize,
            "hit_rate": round(hit_rate * 100, 2),
            "hit_rate_percentage": f"{round(hit_rate * 100, 2)}%"
        }
    }


# ============================================
# CONSULTATION FORM CRUD ENDPOINTS
# ============================================

@app.get("/api/consultation-form")
async def get_consultation_form(appointment_id: str, form_type: str):
    """
    Get consultation form by appointment ID and form type.
    """
    try:
        supabase = get_supabase_client()

        result = supabase.table('consultation_forms')\
            .select('*')\
            .eq('appointment_id', appointment_id)\
            .eq('form_type', form_type)\
            .single()\
            .execute()

        if result.data:
            return {"form": result.data}
        else:
            return {"form": None}

    except Exception as e:
        # Form doesn't exist yet - not an error
        return {"form": None}


@app.post("/api/consultation-form")
async def create_consultation_form(form_data: dict):
    """
    Create a new consultation form in unified table.

    Request body:
    {
        "patient_id": "uuid",
        "appointment_id": "uuid",
        "form_type": "antenatal|obgyn|infertility|...",
        "form_data": {...},  // JSONB data
        "status": "draft|partial|completed",
        "created_by": "firebase_uid",
        "updated_by": "firebase_uid",
        "filled_by": "firebase_uid"
    }
    """
    try:
        supabase = get_supabase_client()

        result = supabase.table('consultation_forms').insert(form_data).execute()

        return {"form": result.data[0]}

    except Exception as e:
        print(f"❌ Error creating form: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/consultation-form/{form_id}")
async def update_consultation_form(form_id: str, form_data: dict):
    """
    Update an existing consultation form.

    Request body: Same as create, but only include fields to update.
    """
    try:
        supabase = get_supabase_client()

        # Add updated_at timestamp
        form_data['updated_at'] = datetime.now(timezone.utc).isoformat()

        result = supabase.table('consultation_forms')\
            .update(form_data)\
            .eq('id', form_id)\
            .execute()

        return {"form": result.data[0]}

    except Exception as e:
        print(f"❌ Error updating form: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
