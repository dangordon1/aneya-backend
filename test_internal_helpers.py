#!/usr/bin/env python3
"""
Test the integrated form extraction by calling the local backend.

This test validates:
1. /api/diarize-chunk accepts consultation context parameters
2. Backend determines form_type from conversation
3. Backend extracts form fields and returns them in response
4. Response includes form_type, form_updates, form_confidence

PREREQUISITES:
- Backend must be running: python -m uvicorn api:app --reload
- Test audio files in ../consultation_recordings/ (optional)
"""

import requests
import json
import os
import glob

# Backend URL
API_URL = "http://localhost:8000"

def find_test_audio():
    """Find a test audio file from recordings directory."""
    recordings_dir = "/Users/dgordon/aneya/consultation_recordings"

    if os.path.exists(recordings_dir):
        # Look for WAV files
        wav_files = glob.glob(f"{recordings_dir}/*.wav")
        if wav_files:
            return wav_files[0]

        # Look for WebM files
        webm_files = glob.glob(f"{recordings_dir}/*.webm")
        if webm_files:
            return webm_files[0]

    return None


def test_diarize_with_consultation_context():
    """Test that /api/diarize-chunk accepts consultation context and returns form data."""
    print("="*80)
    print("TEST 1: DIARIZE CHUNK WITH CONSULTATION CONTEXT")
    print("="*80)
    print()

    # Find test audio
    audio_file = find_test_audio()

    if not audio_file:
        print("⚠️  No test audio found in /Users/dgordon/aneya/consultation_recordings/")
        print("   Using minimal audio for structure test only")
        # Create minimal WebM header for testing structure
        import io
        audio_data = io.BytesIO(b'\x1a\x45\xdf\xa3')
        files = {'audio': ('test-chunk.webm', audio_data, 'audio/webm')}
    else:
        print(f"📁 Using test audio: {os.path.basename(audio_file)}")
        files = {'audio': open(audio_file, 'rb')}

    # Prepare request with consultation context
    data = {
        'chunk_index': '0',
        'chunk_start': '0.0',
        'chunk_end': '60.0',
        'language': 'en-IN',  # Use English (India) to route to Sarvam instead of ElevenLabs
        # NEW: Consultation context for integrated form extraction
        'consultation_id': 'test-consult-123',
        'patient_id': 'test-patient-456',
        'doctor_specialty': 'obgyn'
    }

    print(f"📤 Sending POST to {API_URL}/api/diarize-chunk")
    print(f"   consultation_id: {data['consultation_id']}")
    print(f"   patient_id: {data['patient_id']}")
    print(f"   doctor_specialty: {data['doctor_specialty']}")
    print(f"   language: {data['language']} (routes to Sarvam API)")
    print()

    try:
        response = requests.post(
            f"{API_URL}/api/diarize-chunk",
            files=files,
            data=data,
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()

            print("✅ Response received successfully")
            print()
            print("📦 RESPONSE STRUCTURE:")
            print(f"  success: {result.get('success')}")
            print(f"  chunk_index: {result.get('chunk_index')}")
            print(f"  segments: {len(result.get('segments', []))} segments")
            print(f"  detected_speakers: {len(result.get('detected_speakers', []))} speakers")
            print()
            print("📋 FORM EXTRACTION RESULTS:")
            print(f"  form_type: {result.get('form_type')}")
            print(f"  form_updates: {len(result.get('form_updates', {}))} fields")
            print(f"  form_confidence: {len(result.get('form_confidence', {}))} scores")
            print()

            if result.get('form_updates'):
                print("📝 Extracted Fields:")
                for field, value in result.get('form_updates', {}).items():
                    conf = result.get('form_confidence', {}).get(field, 0.0)
                    print(f"  - {field}: {value} (confidence: {conf:.2f})")
                print()

            # Validate structure
            assert 'form_type' in result, "Missing 'form_type' in response"
            assert 'form_updates' in result, "Missing 'form_updates' in response"
            assert 'form_confidence' in result, "Missing 'form_confidence' in response"

            print("✅ All expected fields present in response")
            return True

        else:
            print(f"❌ Request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to backend")
        print("   Make sure the backend is running:")
        print("   cd /Users/dgordon/aneya/aneya-backend")
        print("   python -m uvicorn api:app --reload")
        return False
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if audio_file and 'files' in locals():
            files['audio'].close()


def test_consultation_type_determination():
    """Test that consultation type is determined from antenatal conversation."""
    print()
    print("="*80)
    print("TEST 2: CONSULTATION TYPE CLASSIFICATION")
    print("="*80)
    print()

    # Test the separate endpoint to verify classification logic
    test_segments = [
        {
            "speaker_id": "speaker_0",
            "speaker_role": "Patient",
            "text": "Hi doctor, I'm here for my pregnancy checkup.",
            "start_time": 0.0
        },
        {
            "speaker_id": "speaker_1",
            "speaker_role": "Doctor",
            "text": "Hello! How many weeks pregnant are you?",
            "start_time": 3.0
        },
        {
            "speaker_id": "speaker_0",
            "speaker_role": "Patient",
            "text": "I'm nine weeks pregnant, in my first trimester.",
            "start_time": 5.0
        },
        {
            "speaker_id": "speaker_1",
            "speaker_role": "Doctor",
            "text": "Congratulations! Let me check the fetal heart rate.",
            "start_time": 8.0
        }
    ]

    payload = {
        "diarized_segments": test_segments,
        "doctor_specialty": "obgyn",
        "patient_context": {
            "patient_id": "test-patient-123"
        }
    }

    print("📋 Test conversation (antenatal indicators):")
    for seg in test_segments:
        print(f"  [{seg['start_time']}s] {seg['speaker_role']}: {seg['text']}")
    print()

    print(f"📤 Sending POST to {API_URL}/api/determine-consultation-type")
    print()

    try:
        response = requests.post(
            f"{API_URL}/api/determine-consultation-type",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()

            print("✅ Response received")
            print()
            print(f"  consultation_type: {result.get('consultation_type')}")
            print(f"  confidence: {result.get('confidence'):.2f}")
            print(f"  reasoning: {result.get('reasoning')}")
            print()

            # Validate
            if result.get('consultation_type') == 'antenatal':
                print("✅ CORRECT: Classified as 'antenatal'")
                if result.get('confidence', 0) >= 0.85:
                    print(f"✅ HIGH CONFIDENCE: {result.get('confidence'):.2f}")
                    return True
                else:
                    print(f"⚠️  Lower confidence: {result.get('confidence'):.2f}")
                    return True  # Still pass if classified correctly
            else:
                print(f"❌ INCORRECT: Expected 'antenatal', got '{result.get('consultation_type')}'")
                return False

        else:
            print(f"❌ Request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to backend")
        print("   Make sure the backend is running")
        return False
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    print("\n")
    print("🧪 INTEGRATED FORM EXTRACTION TEST SUITE")
    print("=" * 80)
    print()
    print("Testing the integrated form extraction by calling the running backend:")
    print("  1. /api/diarize-chunk with consultation context")
    print("  2. /api/determine-consultation-type classification")
    print()
    print("These tests verify the backend integration is working correctly.")
    print("=" * 80)
    print("\n")

    # Check if backend is running
    print("🔍 Checking if backend is running...")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        print(f"✅ Backend is running at {API_URL}")
        print()
    except:
        print(f"❌ Backend is not running at {API_URL}")
        print()
        print("Please start the backend first:")
        print("  cd /Users/dgordon/aneya/aneya-backend")
        print("  python -m uvicorn api:app --reload")
        print()
        exit(1)

    # Run tests
    test1_passed = test_diarize_with_consultation_context()
    test2_passed = test_consultation_type_determination()

    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Test 1 (Integrated Diarization): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Consultation Type): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print()

    if test1_passed and test2_passed:
        print("✅ ALL TESTS PASSED")
        print()
        print("Integration Status:")
        print("  ✓ Backend accepts consultation context parameters")
        print("  ✓ Form extraction integrated into diarization response")
        print("  ✓ Consultation type classification working")
        print("  ✓ Response includes form_type, form_updates, form_confidence")
        print()
        print("Next Steps:")
        print("  1. Test with real antenatal consultation audio")
        print("  2. Start frontend and verify form auto-fill works")
        print("  3. Confirm no race conditions (forms receive data immediately)")
        print("  4. Validate extracted field accuracy")
    else:
        print("❌ SOME TESTS FAILED")
        print()
        print("Troubleshooting:")
        print("  - Check backend logs for detailed error messages")
        print("  - Verify Claude API key is configured")
        print("  - Ensure form_schemas and field_validator modules exist")
        print("  - Test with real audio file from consultation_recordings/")

    print()
