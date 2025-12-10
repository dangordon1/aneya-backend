#!/usr/bin/env python
"""
Aneya API - FastAPI Backend
Wraps the Clinical Decision Support Client for the React frontend
"""

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
# Load environment variables from .env file
load_dotenv()

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

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for progress updates"""
        try:
            # Helper to send SSE event
            def send_event(event_type: str, data: dict):
                return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

            # Normalize input
            patient_id = request.patient_id if request.patient_id and request.patient_id.strip() else None
            patient_age = request.patient_age if request.patient_age and request.patient_age.strip() else None
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

            # Create a queue to collect events from the progress callback
            event_queue = asyncio.Queue()

            # Progress callback to emit events in real-time
            async def progress_callback(event_type: str, data: dict):
                """Called by clinical_decision_support during analysis"""
                await event_queue.put((event_type, data))

            # Run the main analysis in background and stream events
            analysis_task = asyncio.create_task(
                client.clinical_decision_support(
                    clinical_scenario=request.consultation,
                    patient_id=patient_id,
                    patient_age=patient_age,
                    allergies=allergies,
                    location_override=location_to_use,
                    verbose=False,
                    progress_callback=progress_callback
                )
            )

            # Stream events as they come from the analysis
            result = None
            events_processed = 0

            # Helper to process a single event
            def process_event(event_type: str, data: dict):
                nonlocal events_processed
                events_processed += 1
                print(f"[API] Processing event #{events_processed}: {event_type}", flush=True)

                if event_type == "tool_call":
                    tool_name = data.get("tool_name", "")
                    if "search" in tool_name.lower() or "nice" in tool_name.lower() or "bnf" in tool_name.lower():
                        return send_event("guideline_search", {
                            "source": tool_name,
                            "query": data.get("tool_input", {})
                        })
                elif event_type == "bnf_drug":
                    return send_event("bnf_drug", data)
                elif event_type == "drug_update":
                    print(f"[API] Sending drug_update: {data.get('drug_name')} - {data.get('status')}", flush=True)
                    return send_event("drug_update", data)
                elif event_type == "diagnoses":
                    return send_event("diagnoses", data)
                return None

            while True:
                try:
                    # Check if analysis is done
                    if analysis_task.done():
                        print(f"[API] Analysis task completed, draining event queue...", flush=True)
                        result = analysis_task.result()

                        # Drain remaining events with a small delay to ensure queue is populated
                        await asyncio.sleep(0.1)

                        drain_count = 0
                        while True:
                            try:
                                # Use wait_for with short timeout instead of empty() check
                                event_type, data = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                                drain_count += 1
                                sse_event = process_event(event_type, data)
                                if sse_event:
                                    yield sse_event
                            except asyncio.TimeoutError:
                                # Queue is truly empty
                                print(f"[API] Queue drained: {drain_count} events", flush=True)
                                break
                        break

                    # Wait for next event with timeout
                    try:
                        event_type, data = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                        sse_event = process_event(event_type, data)
                        if sse_event:
                            yield sse_event
                    except asyncio.TimeoutError:
                        # No events, continue waiting for analysis
                        continue

                except Exception as e:
                    print(f"[API] Error processing event: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    break

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

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
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
            "patient_info": {  # Optional
                "patient_id": "P001",
                "patient_age": "30 years old",
                "allergies": "None"
            }
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
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    patient_info = request.get("patient_info")

    try:
        print(f"\n{'='*70}")
        print(f"📝 SUMMARIZING CONSULTATION")
        print(f"{'='*70}")
        print(f"Transcript length: {len(text)} characters")
        if patient_info:
            print(f"Patient info provided: {list(patient_info.keys())}")
        print(f"{'='*70}\n")

        # Generate comprehensive summary
        result = await consultation_summary.summarize(
            transcript=text,
            patient_info=patient_info
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
            "original_transcript": text,  # Original transcript
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
            async with httpx.AsyncClient(timeout=60.0) as http_client:
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
