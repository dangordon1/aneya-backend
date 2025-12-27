#!/usr/bin/env python
"""
Aneya API - FastAPI Backend
Wraps the Clinical Decision Support Client for the React frontend
"""

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
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
import json
import httpx
import tempfile
import time
import asyncio
import uuid
from google.cloud import storage
import firebase_admin
from firebase_admin import credentials

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
        "https://aneya.vercel.app",  # Production frontend
        "https://aneya.health",  # Custom domain
        "https://www.aneya.health",  # Custom domain with www
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def translate_text(request: dict):
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
async def summarize_text(request: dict):
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

    Analyzes the first chunk of conversation to determine speaker roles.
    Uses Claude Haiku for fast, cost-effective inference.

    Args:
        segments: Diarized segments from the first chunk
        language: Conversation language (for context)

    Returns:
        Speaker role mapping: {"speaker_0": "Doctor", "speaker_1": "Patient"}
    """
    try:
        import anthropic

        anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Format conversation for analysis
        conversation_text = ""
        for seg in request.segments[:20]:  # Use first 20 segments (enough context)
            conversation_text += f"{seg['speaker_id']}: {seg['text']}\n"

        print(f"🔍 Identifying speaker roles from {len(request.segments)} segments")

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
            model="claude-3-5-haiku-20241022",
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
            "model": "claude-3-5-haiku-20241022"
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


@app.post("/api/diarize-chunk")
async def diarize_audio_chunk(
    audio: UploadFile = File(...),
    chunk_index: int = Form(0),
    chunk_start: float = Form(0.0),
    chunk_end: float = Form(30.0),
    num_speakers: Optional[int] = Form(None),
    diarization_threshold: float = Form(0.22),
    language: Optional[str] = Form(None)
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
            # Overlap duration is 5 seconds (configurable)
            OVERLAP_DURATION = 5.0

            # Start overlap: first 5 seconds of chunk (shared with previous chunk)
            start_overlap_stats = {}
            if chunk_index > 0:
                start_overlap_stats = _calculate_overlap_stats(
                    segments, 0.0, OVERLAP_DURATION
                )
                if start_overlap_stats:
                    print(f"  📍 Start overlap (0-{OVERLAP_DURATION}s): ", end='')
                    print(', '.join([f"{sid}={st['duration']:.1f}s" for sid, st in start_overlap_stats.items()]))

            # End overlap: last 5 seconds of chunk (shared with next chunk)
            chunk_duration = chunk_end - chunk_start
            end_overlap_start = chunk_duration - OVERLAP_DURATION
            end_overlap_stats = _calculate_overlap_stats(
                segments, end_overlap_start, chunk_duration
            )
            if end_overlap_stats:
                print(f"  📍 End overlap ({end_overlap_start:.1f}-{chunk_duration:.1f}s): ", end='')
                print(', '.join([f"{sid}={st['duration']:.1f}s" for sid, st in end_overlap_stats.items()]))

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
                'model': result_data.get('model', 'unknown')
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
        import re
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
