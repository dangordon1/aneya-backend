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
# Load environment variables from .env file
load_dotenv()

# Add servers directory to path (servers is in the backend repo root)
sys.path.insert(0, str(Path(__file__).parent / "servers"))
from clinical_decision_support_client import ClinicalDecisionSupportClient

# Global instances (reused across requests)
client: Optional[ClinicalDecisionSupportClient] = None
deepgram_client = None  # Deepgram API client for transcription


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    global client, deepgram_client

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

    # Initialize Deepgram client for transcription
    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
    if deepgram_key:
        from deepgram import DeepgramClient
        deepgram_client = DeepgramClient(api_key=deepgram_key)
        print(f"✅ Deepgram API key loaded (ends with ...{deepgram_key[-4:]})")
    else:
        print("⚠️  DEEPGRAM_API_KEY not found - transcription will not work")

    # Initialize client but DON'T connect to servers yet
    # Servers will be connected per-request based on user's region (detected from IP)
    client = ClinicalDecisionSupportClient(anthropic_api_key=anthropic_key)
    print("✅ Client initialized (servers will be loaded based on user region)")

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
            while True:
                try:
                    # Check if analysis is done
                    if analysis_task.done():
                        result = analysis_task.result()
                        # Drain any remaining events
                        while not event_queue.empty():
                            event_type, data = await event_queue.get()
                            if event_type == "tool_call":
                                # Emit guideline search event
                                tool_name = data.get("tool_name", "")
                                if "search" in tool_name.lower() or "nice" in tool_name.lower() or "bnf" in tool_name.lower():
                                    yield send_event("guideline_search", {
                                        "source": tool_name,
                                        "query": data.get("tool_input", {})
                                    })
                            elif event_type == "bnf_drug":
                                yield send_event("bnf_drug", data)
                        break

                    # Wait for next event with timeout
                    try:
                        event_type, data = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                        if event_type == "tool_call":
                            # Emit guideline search event
                            tool_name = data.get("tool_name", "")
                            if "search" in tool_name.lower() or "nice" in tool_name.lower() or "bnf" in tool_name.lower():
                                yield send_event("guideline_search", {
                                    "source": tool_name,
                                    "query": data.get("tool_input", {})
                                })
                        elif event_type == "bnf_drug":
                            yield send_event("bnf_drug", data)
                    except asyncio.TimeoutError:
                        # No events, continue waiting for analysis
                        continue

                except Exception as e:
                    print(f"Error processing event: {e}")
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


@app.post("/api/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio using Deepgram API

    Args:
        audio: Audio file (webm, wav, mp3, etc.)

    Returns:
        Transcribed text with fast cloud-based transcription (~300ms latency)
    """
    if deepgram_client is None:
        raise HTTPException(
            status_code=503,
            detail="Transcription service not configured. DEEPGRAM_API_KEY is required."
        )

    try:
        print(f"🎤 Transcribing audio file: {audio.filename}")

        # Read the audio content
        content = await audio.read()
        audio_size_kb = len(content) / 1024
        print(f"📊 Audio file size: {audio_size_kb:.2f} KB ({len(content)} bytes)")

        # Determine the mimetype
        filename = audio.filename or "audio.webm"
        if filename.endswith(".webm"):
            mimetype = "audio/webm"
        elif filename.endswith(".wav"):
            mimetype = "audio/wav"
        elif filename.endswith(".mp3"):
            mimetype = "audio/mp3"
        else:
            mimetype = "audio/webm"  # Default for browser recordings

        # Transcribe using Deepgram
        start = time.time()

        # Use the SDK v5 listen API - deepgram_client.listen.v1.media.transcribe_file()
        response = deepgram_client.listen.v1.media.transcribe_file(
            request=content,
            model="nova-2",
            language="en",
            smart_format=True,
            punctuate=True,
        )
        latency = time.time() - start

        # Extract transcription from response (SDK v5 format)
        # Structure: response.results.channels[0].alternatives[0].transcript
        transcription = ""
        if response and response.results and response.results.channels:
            channel = response.results.channels[0]
            if channel.alternatives:
                transcription = channel.alternatives[0].transcript or ""

        print(f"✅ Transcription complete in {latency:.2f}s")
        print(f"📝 Full transcription text: '{transcription}'")

        return {
            "success": True,
            "text": transcription.strip(),
            "latency_seconds": round(latency, 2),
            "model": "deepgram/nova-2"
        }

    except Exception as e:
        print(f"❌ Transcription error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
