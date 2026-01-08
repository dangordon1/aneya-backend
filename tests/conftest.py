"""
Pytest configuration and shared fixtures for Aneya API tests.

This module provides:
- FastAPI TestClient configuration
- VCR.py configuration for HTTP recording/replay
- Mock fixtures for all external services
- Multi-language test data fixtures
- Clinical scenario fixtures
"""

import os
import sys
import json
import pytest
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

# Add the backend directory to the path
BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers and load environment."""
    # Register custom markers
    config.addinivalue_line("markers", "vcr: mark test to use VCR cassette recording")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "llm: marks tests that require LLM calls")
    config.addinivalue_line("markers", "external_service: marks tests hitting external services")

    # Load .env file
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for the test session."""
    return asyncio.get_event_loop_policy()


@pytest.fixture
def event_loop():
    """Create a new event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# VCR.PY CONFIGURATION FOR ANTHROPIC API
# ============================================================================

CASSETTES_DIR = Path(__file__).parent / "cassettes"


def filter_sensitive_request_data(request):
    """Filter sensitive data from request before recording."""
    if hasattr(request, 'headers'):
        headers = dict(request.headers)
        if 'x-api-key' in headers:
            headers['x-api-key'] = 'FILTERED'
        if 'anthropic-api-key' in headers:
            headers['anthropic-api-key'] = 'FILTERED'
        if 'authorization' in headers:
            headers['authorization'] = 'FILTERED'
        if 'xi-api-key' in headers:
            headers['xi-api-key'] = 'FILTERED'
    return request


def filter_sensitive_response_data(response):
    """Filter sensitive data from response before recording."""
    return response


@pytest.fixture(scope="module")
def vcr_config():
    """
    VCR.py configuration for Anthropic API cassette recording.

    Key settings:
    - Filter out API keys from recordings
    - Use YAML format for readability
    - Record once, replay always strategy
    """
    return {
        "cassette_library_dir": str(CASSETTES_DIR / "anthropic"),
        "record_mode": "once",
        "match_on": ["method", "scheme", "host", "port", "path"],
        "filter_headers": [
            "x-api-key",
            "anthropic-api-key",
            "authorization",
            "xi-api-key",
        ],
        "filter_post_data_parameters": [
            "api_key",
        ],
        "decode_compressed_response": True,
        "before_record_request": filter_sensitive_request_data,
        "before_record_response": filter_sensitive_response_data,
    }


@pytest.fixture
def vcr_cassette_path(request):
    """Generate cassette path based on test module and function name."""
    test_module = request.module.__name__.split('.')[-1]
    test_name = request.node.name
    return str(CASSETTES_DIR / "anthropic" / f"{test_module}" / f"{test_name}.yaml")


# ============================================================================
# FASTAPI TEST CLIENT
# ============================================================================

@pytest.fixture(scope="module")
def test_client():
    """
    FastAPI TestClient with mocked lifespan dependencies.

    Mocks external service clients to avoid actual connections:
    - Anthropic client
    - ElevenLabs client
    - GCS client
    - Firebase Admin
    """
    from fastapi.testclient import TestClient

    with patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "ELEVENLABS_API_KEY": "test-elevenlabs-key",
        "SARVAM_API_KEY": "test-sarvam-key",
        "FIREBASE_PROJECT_ID": "test-project",
        "RESEND_API_KEY": "test-resend-key",
        "GCS_BUCKET_NAME": "test-bucket",
    }):
        with patch('google.cloud.storage.Client') as mock_gcs, \
             patch('firebase_admin.initialize_app'), \
             patch('firebase_admin._apps', {'[DEFAULT]': MagicMock()}):

            mock_gcs.return_value = MagicMock()

            from api import app

            with TestClient(app) as client:
                yield client


@pytest.fixture
def async_test_client():
    """Async HTTP client for testing async endpoints."""
    with patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "ELEVENLABS_API_KEY": "test-elevenlabs-key",
    }):
        with patch('google.cloud.storage.Client'), \
             patch('firebase_admin.initialize_app'):

            from api import app

            async def get_client():
                async with httpx.AsyncClient(
                    app=app,
                    base_url="http://test"
                ) as client:
                    yield client

            return get_client


# ============================================================================
# EXTERNAL SERVICE MOCKS
# ============================================================================

@pytest.fixture
def mock_anthropic():
    """
    Mock Anthropic client for Claude API calls.

    Provides pre-configured responses for common LLM operations.
    """
    with patch('anthropic.Anthropic') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"success": true}')]
        mock_client.messages.create.return_value = mock_response

        yield mock_client


@pytest.fixture
def mock_anthropic_speaker_roles():
    """Mock for speaker role identification endpoint."""
    with patch('anthropic.Anthropic') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "speaker_0": {"role": "Doctor", "confidence": 0.95, "reasoning": "Asks diagnostic questions"},
            "speaker_1": {"role": "Patient", "confidence": 0.92, "reasoning": "Describes symptoms"}
        }))]
        mock_client.messages.create.return_value = mock_response

        yield mock_client


@pytest.fixture
def mock_anthropic_consultation_type():
    """Mock for consultation type determination endpoint."""
    with patch('anthropic.Anthropic') as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "consultation_type": "antenatal",
            "confidence": 0.9,
            "reasoning": "Patient mentions being 6 weeks pregnant"
        }))]
        mock_client.messages.create.return_value = mock_response

        yield mock_client


@pytest.fixture
def mock_elevenlabs():
    """Mock ElevenLabs client for diarization/transcription."""
    mock_client = MagicMock()

    mock_client.speech_to_text.convert.return_value = {
        "text": "Doctor: What brings you in today?\nPatient: I have a headache.",
        "words": [],
        "utterances": [
            {"speaker": "speaker_0", "text": "What brings you in today?", "start": 0.0, "end": 2.0},
            {"speaker": "speaker_1", "text": "I have a headache.", "start": 2.5, "end": 4.0},
        ]
    }

    yield mock_client


@pytest.fixture
def mock_sarvam():
    """Mock Sarvam AI client for Indian language diarization."""
    with patch('httpx.AsyncClient') as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_instance

        mock_instance.post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"job_id": "test-job-123", "status": "Pending"}
        )

        mock_instance.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "status": "Completed",
                "transcripts": [
                    {"speaker_id": "speaker_0", "text": "Namaste, kaise ho?", "start_time": 0.0, "end_time": 2.0},
                    {"speaker_id": "speaker_1", "text": "Main theek hoon", "start_time": 2.5, "end_time": 4.0}
                ]
            }
        )

        yield mock_instance


@pytest.fixture
def mock_firebase():
    """Mock Firebase Admin SDK."""
    with patch('firebase_admin.auth') as mock_auth:
        mock_auth.generate_password_reset_link.return_value = "https://test-reset-link.com"
        yield mock_auth


@pytest.fixture
def mock_gcs():
    """Mock Google Cloud Storage client."""
    with patch('google.cloud.storage.Client') as mock_client:
        mock_bucket = MagicMock()
        mock_blob = MagicMock()

        mock_blob.exists.return_value = True
        mock_blob.upload_from_string.return_value = None
        mock_blob.download_as_bytes.return_value = b"test audio content"

        mock_bucket.blob.return_value = mock_blob
        mock_client.return_value.bucket.return_value = mock_bucket

        yield mock_client.return_value


@pytest.fixture
def mock_resend():
    """Mock Resend email client."""
    with patch('resend.Emails') as mock_emails:
        mock_emails.send.return_value = {"id": "test-email-id"}
        yield mock_emails


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for database operations."""
    with patch('api.get_supabase_client') as mock_get_client:
        mock_client = MagicMock()

        mock_result = MagicMock()
        mock_result.data = [{"id": "test-id", "status": "completed"}]

        mock_client.from_.return_value.select.return_value.execute.return_value = mock_result
        mock_client.from_.return_value.insert.return_value.execute.return_value = mock_result
        mock_client.from_.return_value.update.return_value.execute.return_value = mock_result

        mock_get_client.return_value = mock_client

        yield mock_client


# ============================================================================
# MULTI-LANGUAGE TEST DATA FIXTURES
# ============================================================================

@pytest.fixture
def english_transcript():
    """Sample English consultation transcript."""
    return """1. [0.00s - 2.50s] speaker_0:
     Good morning. What brings you in today?

  2. [3.00s - 6.00s] speaker_1:
     I've been having a persistent cough for about a week now.

  3. [6.50s - 9.00s] speaker_0:
     I see. Do you have any fever or difficulty breathing?

  4. [9.50s - 12.00s] speaker_1:
     Yes, I've had a low-grade fever for the past few days."""


@pytest.fixture
def hindi_transcript():
    """Sample Hindi consultation transcript."""
    return """1. [0.00s - 3.00s] speaker_0:
     Namaste, aapko kya problem hai?

  2. [3.50s - 7.00s] speaker_1:
     Mujhe ek hafta se khansi aa rahi hai.

  3. [7.50s - 10.00s] speaker_0:
     Kya aapko bukhar bhi hai?

  4. [10.50s - 13.00s] speaker_1:
     Haan, thoda bukhar bhi hai."""


@pytest.fixture
def kannada_transcript():
    """Sample Kannada consultation transcript."""
    return """1. [0.00s - 3.00s] speaker_0:
     Namaskara, nimma samasyenu?

  2. [3.50s - 7.00s] speaker_1:
     Nanage ondu varada indha kemmu ide.

  3. [7.50s - 10.00s] speaker_0:
     Jvara ideyaa?

  4. [10.50s - 13.00s] speaker_1:
     Haagoo, sulpu jvara ide."""


@pytest.fixture
def multilingual_transcript():
    """Sample mixed Hindi-English consultation transcript."""
    return """1. [0.00s - 3.00s] speaker_0:
     Good morning, aapko kya problem hai today?

  2. [3.50s - 7.00s] speaker_1:
     Doctor sahab, mujhe cough and cold for one week.

  3. [7.50s - 10.00s] speaker_0:
     Fever hai? Any body pain?

  4. [10.50s - 13.00s] speaker_1:
     Haan doctor, mild fever hai."""


@pytest.fixture
def english_segments():
    """Pre-diarized English segments."""
    return [
        {"speaker_id": "speaker_0", "text": "Good morning. What brings you in today?", "start_time": 0.0, "end_time": 2.5},
        {"speaker_id": "speaker_1", "text": "I've been having a persistent cough for about a week now.", "start_time": 3.0, "end_time": 6.0},
        {"speaker_id": "speaker_0", "text": "I see. Do you have any fever or difficulty breathing?", "start_time": 6.5, "end_time": 9.0},
        {"speaker_id": "speaker_1", "text": "Yes, I've had a low-grade fever for the past few days.", "start_time": 9.5, "end_time": 12.0},
    ]


@pytest.fixture
def hindi_segments():
    """Pre-diarized Hindi segments."""
    return [
        {"speaker_id": "speaker_0", "text": "Namaste, aapko kya problem hai?", "start_time": 0.0, "end_time": 3.0},
        {"speaker_id": "speaker_1", "text": "Mujhe ek hafta se khansi aa rahi hai.", "start_time": 3.5, "end_time": 7.0},
        {"speaker_id": "speaker_0", "text": "Kya aapko bukhar bhi hai?", "start_time": 7.5, "end_time": 10.0},
        {"speaker_id": "speaker_1", "text": "Haan, thoda bukhar bhi hai.", "start_time": 10.5, "end_time": 13.0},
    ]


# ============================================================================
# CLINICAL SCENARIO FIXTURES
# ============================================================================

@pytest.fixture
def clinical_scenarios():
    """
    Clinical test scenarios for testing diagnosis and form extraction.

    Each scenario includes:
    - consultation: Full transcript text
    - patient_age: Patient age for context
    - expected_conditions: What should be identified
    - form_type: Expected consultation form type
    """
    return {
        "pregnant_flu": {
            "consultation": "6 weeks pregnant with flu symptoms including cough, cold, fever, and vomiting for 5 days",
            "patient_age": "28",
            "patient_sex": "Female",
            "expected_conditions": ["pregnancy", "viral upper respiratory infection"],
            "form_type": "antenatal",
            "language": "en-IN"
        },
        "pediatric_fever": {
            "consultation": "3-year-old with fever 39C for 2 days, cough, no rash",
            "patient_age": "3",
            "expected_conditions": ["fever", "respiratory infection"],
            "form_type": "general",
            "language": "en-IN"
        },
        "diabetes_management": {
            "consultation": "45-year-old with newly diagnosed type 2 diabetes, HbA1c 8.5%",
            "patient_age": "45",
            "expected_conditions": ["type 2 diabetes"],
            "form_type": "general",
            "language": "en-IN"
        },
        "infertility_case": {
            "consultation": "Trying to conceive for 2 years, irregular periods, no success with natural conception",
            "patient_age": "32",
            "patient_sex": "Female",
            "expected_conditions": ["infertility", "irregular menstruation"],
            "form_type": "infertility",
            "language": "en-IN"
        },
        "hindi_antenatal": {
            "consultation": "Main 6 week pregnant hoon, mujhe bahut zyada ulti aa rahi hai",
            "patient_age": "25",
            "patient_sex": "Female",
            "expected_conditions": ["pregnancy", "hyperemesis"],
            "form_type": "antenatal",
            "language": "hi-IN"
        }
    }


@pytest.fixture
def form_extraction_scenarios():
    """Test data for form field extraction."""
    return {
        "obgyn_basic": {
            "form_type": "obgyn",
            "segments": [
                {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "What's your last menstrual period?", "start_time": 0.0},
                {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "December 1st, 2024", "start_time": 2.0},
                {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "Any history of previous pregnancies?", "start_time": 4.0},
                {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "Yes, I have two children, both normal deliveries", "start_time": 6.0},
            ],
            "expected_fields": ["last_menstrual_period", "parity"]
        },
        "antenatal_vitals": {
            "form_type": "antenatal",
            "segments": [
                {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "How many weeks pregnant are you?", "start_time": 0.0},
                {"speaker_id": "speaker_1", "speaker_role": "Patient", "text": "I'm about 28 weeks now", "start_time": 2.0},
                {"speaker_id": "speaker_0", "speaker_role": "Doctor", "text": "Your blood pressure is 120/80 and weight is 65 kg", "start_time": 4.0},
            ],
            "expected_fields": ["gestational_age", "blood_pressure", "weight"]
        }
    }


# ============================================================================
# CLEANUP AND UTILITY FIXTURES
# ============================================================================

@pytest.fixture
async def cleanup_clients():
    """
    Track and cleanup MCP clients after tests.

    Usage:
        async def test_something(cleanup_clients):
            client = await get_client("GB")
            cleanup_clients.append(client)
    """
    clients = []
    yield clients

    for client in clients:
        try:
            await client.cleanup()
        except Exception:
            pass


@pytest.fixture
def temp_audio_file(tmp_path):
    """Create a temporary audio file for upload tests."""
    audio_file = tmp_path / "test_audio.webm"
    audio_file.write_bytes(b"fake audio content for testing")
    return audio_file
