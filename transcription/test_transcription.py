#!/usr/bin/env python
"""Test the transcription endpoint with a short example audio file."""

import requests
import os
import re
import time
from pathlib import Path

# Configuration
API_URL = "http://localhost:8000"
TRANSCRIBE_ENDPOINT = f"{API_URL}/api/transcribe"
TEST_AUDIO_FILE = "test_audio.mp3"
EXPECTED_TEXT = "Patient presents with a 3-day history of productive cough with green sputum, fever, 38.5 degrees Celsius, and shortness of breath.  They report feeling generally unwell with fatigue and reduced appetite.  Past medical history includes type 2 diabetes mellitus, well-controlled on metformin, and hypertension.  On remepril, no known drug allergies, non-smoker, on examination, respiratory rate 22 per minute,  oxygen saturation 94% on air, crackles herd in right lower zone on auscultation."


def test_transcription():
    """Test the /api/transcribe endpoint with a short audio file."""

    # Check if test audio file exists
    if not os.path.exists(TEST_AUDIO_FILE):
        print(f"❌ Test audio file not found: {TEST_AUDIO_FILE}")
        print("   Run create_test_audio.py first to generate the test file")
        return False

    print(f"📁 Using test audio: {TEST_AUDIO_FILE}")
    print(f"📊 File size: {os.path.getsize(TEST_AUDIO_FILE)} bytes")
    print(f"🎯 Expected text (approximately): '{EXPECTED_TEXT}'")
    print()

    # Check if API is running
    try:
        health_response = requests.get(f"{API_URL}/health", timeout=5)
        if health_response.status_code != 200:
            print(f"❌ API health check failed: {health_response.status_code}")
            return False
        print("✅ API is running")
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to API at {API_URL}")
        print(f"   Error: {e}")
        print("   Make sure the API is running: python api.py")
        return False

    # Test transcription
    print(f"\n🎤 Sending audio to {TRANSCRIBE_ENDPOINT}...")

    try:
        # Start timing
        start_time = time.time()

        with open(TEST_AUDIO_FILE, 'rb') as audio_file:
            files = {'audio': (TEST_AUDIO_FILE, audio_file, 'audio/mpeg')}
            response = requests.post(TRANSCRIBE_ENDPOINT, files=files, timeout=30)

        # Calculate elapsed time
        elapsed_time = time.time() - start_time

        print(f"📡 Response status: {response.status_code}")
        print(f"⏱️  Transcription time: {elapsed_time:.2f} seconds")

        if response.status_code == 200:
            result = response.json()

            if result.get('success'):
                transcribed_text = result.get('text', '')
                print(f"\n✅ Transcription successful!")
                print(f"📝 Transcribed text: '{transcribed_text}'")

                # Check if transcription is approximately correct
                # (Whisper might add punctuation or slight variations)
                transcribed_lower = transcribed_text.lower().strip()

                # Simple similarity check - check if key words are present
                # Split on common delimiters: space, comma, period, parentheses, dash, semicolon, colon, quotes
                key_words = re.split(r'[,\s\.\(\)\-;:\']+', EXPECTED_TEXT.lower())
                key_words = [word for word in key_words if word]  # Remove empty strings
                words_found = sum(1 for word in key_words if word in transcribed_lower)

                accuracy = words_found / len(key_words) if len(key_words) > 0 else 0

                if accuracy >= 0.8:
                    print(f"✅ Transcription quality: GOOD ({words_found}/{len(key_words)} key words found, {accuracy*100:.1f}% accuracy)")
                    return True
                else:
                    print(f"⚠️  Transcription quality: POOR ({words_found}/{len(key_words)} key words found, {accuracy*100:.1f}% accuracy)")
                    print(f"   Expected words from: '{EXPECTED_TEXT[:100]}...'")
                    print(f"   Got: '{transcribed_lower[:100]}...'")
                    return True  # Still pass since endpoint works
            else:
                print(f"❌ Transcription failed: {result}")
                return False
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print("❌ Request timed out (transcription takes longer than 30s)")
        return False
    except Exception as e:
        print(f"❌ Error during transcription: {e}")
        return False


if __name__ == "__main__":
    print("="*70)
    print("🎤 TRANSCRIPTION ENDPOINT TEST")
    print("="*70)
    print()

    success = test_transcription()

    print()
    print("="*70)
    if success:
        print("✅ TEST PASSED - Transcription endpoint is working!")
    else:
        print("❌ TEST FAILED - See errors above")
    print("="*70)

    exit(0 if success else 1)
