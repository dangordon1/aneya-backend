#!/usr/bin/env python
"""Test the transcription endpoint with a short example audio file."""

import os
import re
import time
from pathlib import Path

import pytest
import requests

# Configuration
API_URL = os.environ.get("API_URL", "http://localhost:8000")
TRANSCRIBE_ENDPOINT = f"{API_URL}/api/transcribe"
TEST_AUDIO_FILE = Path(__file__).parent / "test_audio.wav"
EXPECTED_TEXT = "Patient presents with a 3-day history of productive cough with green sputum, fever, 38.5 degrees Celsius, and shortness of breath.  They report feeling generally unwell with fatigue and reduced appetite.  Past medical history includes type 2 diabetes mellitus, well-controlled on metformin, and hypertension.  On remepril, no known drug allergies, non-smoker, on examination, respiratory rate 22 per minute,  oxygen saturation 94% on air, crackles herd in right lower zone on auscultation."


@pytest.fixture
def api_url():
    """Return the API URL."""
    return API_URL


@pytest.fixture
def test_audio_path():
    """Return the path to the test audio file."""
    return TEST_AUDIO_FILE


def check_api_health(api_url: str) -> bool:
    """Check if the API is running and healthy."""
    try:
        response = requests.get(f"{api_url}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


@pytest.mark.skipif(
    not os.path.exists(TEST_AUDIO_FILE),
    reason=f"Test audio file not found: {TEST_AUDIO_FILE}. Run create_test_audio.py first.",
)
class TestTranscription:
    """Tests for the transcription endpoint."""

    def test_api_health(self, api_url):
        """Test that the API health endpoint is responding."""
        response = requests.get(f"{api_url}/health", timeout=5)
        assert response.status_code == 200, f"API health check failed: {response.status_code}"

    def test_transcription_endpoint_returns_success(self, api_url, test_audio_path):
        """Test that the transcription endpoint returns a successful response."""
        if not check_api_health(api_url):
            pytest.skip(f"API not running at {api_url}")

        with open(test_audio_path, "rb") as audio_file:
            files = {"audio": (test_audio_path.name, audio_file, "audio/wav")}
            response = requests.post(f"{api_url}/api/transcribe", files=files, timeout=30)

        assert response.status_code == 200, f"Request failed with status {response.status_code}: {response.text}"

        result = response.json()
        assert result.get("success") is True, f"Transcription failed: {result}"
        assert "text" in result, "Response missing 'text' field"

    def test_transcription_quality(self, api_url, test_audio_path):
        """Test that the transcription quality meets minimum accuracy threshold."""
        if not check_api_health(api_url):
            pytest.skip(f"API not running at {api_url}")

        start_time = time.time()

        with open(test_audio_path, "rb") as audio_file:
            files = {"audio": (test_audio_path.name, audio_file, "audio/wav")}
            response = requests.post(f"{api_url}/api/transcribe", files=files, timeout=30)

        elapsed_time = time.time() - start_time

        assert response.status_code == 200
        result = response.json()
        assert result.get("success") is True

        transcribed_text = result.get("text", "")
        transcribed_lower = transcribed_text.lower().strip()

        # Check if key words are present
        key_words = re.split(r"[,\s\.\(\)\-;:\']+", EXPECTED_TEXT.lower())
        key_words = [word for word in key_words if word]
        words_found = sum(1 for word in key_words if word in transcribed_lower)

        accuracy = words_found / len(key_words) if len(key_words) > 0 else 0

        # Log transcription details for debugging
        print(f"\nTranscription time: {elapsed_time:.2f} seconds")
        print(f"Transcribed text: '{transcribed_text}'")
        print(f"Accuracy: {accuracy * 100:.1f}% ({words_found}/{len(key_words)} key words found)")

        assert accuracy >= 0.8, (
            f"Transcription quality too low: {accuracy * 100:.1f}% "
            f"(expected >= 80%, got {words_found}/{len(key_words)} key words)"
        )

    def test_transcription_timeout(self, api_url, test_audio_path):
        """Test that transcription completes within acceptable time."""
        if not check_api_health(api_url):
            pytest.skip(f"API not running at {api_url}")

        start_time = time.time()

        with open(test_audio_path, "rb") as audio_file:
            files = {"audio": (test_audio_path.name, audio_file, "audio/wav")}
            response = requests.post(f"{api_url}/api/transcribe", files=files, timeout=30)

        elapsed_time = time.time() - start_time

        assert response.status_code == 200, "Request failed"
        assert elapsed_time < 30, f"Transcription took too long: {elapsed_time:.2f}s (max 30s)"
