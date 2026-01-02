#!/usr/bin/env python3
"""
Authenticated test for form auto-fill endpoints.

Tests:
1. /api/auto-fill-consultation-form - Full consultation form creation with multi-form detection
2. /api/extract-form-fields - Real-time field extraction from diarized segments

Requires Firebase authentication token.
"""

import requests
import json
import uuid
import os
from datetime import datetime

API_URL = "http://localhost:8000"

# Firebase test credentials
# NOTE: Replace with actual test user credentials or use Firebase Admin SDK
FIREBASE_TEST_EMAIL = os.getenv("FIREBASE_TEST_EMAIL", "test@example.com")
FIREBASE_TEST_PASSWORD = os.getenv("FIREBASE_TEST_PASSWORD", "testpassword123")


def get_firebase_id_token():
    """
    Get Firebase ID token for authentication.

    Options:
    1. Use Firebase Auth REST API to sign in with email/password
    2. Use Firebase Admin SDK to create custom token
    3. Manually provide token via environment variable

    For now, we'll use environment variable approach.
    """
    token = os.getenv("FIREBASE_ID_TOKEN")

    if not token:
        print("⚠️  No FIREBASE_ID_TOKEN environment variable set")
        print("   To run authenticated tests, either:")
        print("   1. Export FIREBASE_ID_TOKEN from your browser's Firebase session")
        print("   2. Use Firebase Auth REST API to get a token")
        print()
        print("   Example (get token from Firebase Auth REST API):")
        print(f"   curl -X POST 'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=YOUR_API_KEY' \\")
        print(f"     -H 'Content-Type: application/json' \\")
        print(f"     -d '{{\"email\":\"{FIREBASE_TEST_EMAIL}\",\"password\":\"{FIREBASE_TEST_PASSWORD}\",\"returnSecureToken\":true}}'")
        print()
        return None

    return token


def test_auto_fill_consultation_form(id_token):
    """Test the /api/auto-fill-consultation-form endpoint with authentication."""

    print("=" * 80)
    print("TEST 1: /api/auto-fill-consultation-form (Authenticated)")
    print("=" * 80)
    print()

    # Sample antenatal conversation with vital signs
    sample_transcript = """[0.0s] Doctor: Hello, how are you feeling today?
[3.5s] Patient: Hi doctor, I'm doing well. I'm here for my pregnancy checkup.
[8.2s] Doctor: Great! How many weeks pregnant are you?
[10.5s] Patient: I'm about 6 weeks pregnant now. My last period was on November 11th, 2024.
[14.0s] Doctor: Wonderful. Is this your first pregnancy?
[16.5s] Patient: Yes, this is my first pregnancy.
[20.0s] Doctor: Any symptoms? Nausea, vomiting?
[22.5s] Patient: I've been experiencing nausea every day, but no vomiting.
[28.0s] Doctor: Let me check your vital signs. Blood pressure is 120 over 80.
[32.0s] Patient: Okay.
[34.0s] Doctor: Heart rate is 86, and oxygen saturation is 99 percent.
[38.0s] Patient: That sounds good.
[40.0s] Doctor: Your abdomen is soft, and general inspection shows you're doing fine.
[45.0s] Patient: Thank you, doctor."""

    # Generate UUIDs for test data
    consultation_id = str(uuid.uuid4())
    appointment_id = str(uuid.uuid4())
    patient_id = str(uuid.uuid4())

    request_body = {
        "consultation_id": consultation_id,
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "original_transcript": sample_transcript,
        "consultation_text": "Patient presented for 6-week antenatal checkup. First pregnancy. LMP: 2024-11-11. Vital signs stable.",
        "patient_snapshot": {
            "name": "Test Patient",
            "age": 28
        }
    }

    print("📤 Sending POST request to /api/auto-fill-consultation-form")
    print(f"   consultation_id: {request_body['consultation_id']}")
    print(f"   appointment_id: {request_body['appointment_id']}")
    print(f"   patient_id: {request_body['patient_id']}")
    print()

    try:
        response = requests.post(
            f"{API_URL}/api/auto-fill-consultation-form",
            json=request_body,
            headers={"Authorization": f"Bearer {id_token}"},
            timeout=60
        )

        print(f"✅ Response status: {response.status_code}")
        print()

        if response.status_code == 200:
            data = response.json()

            print("📦 RESPONSE DATA:")
            print("=" * 80)
            print(f"  success: {data.get('success')}")
            print(f"  consultation_type: {data.get('consultation_type')}")
            print(f"  confidence: {data.get('confidence', 0):.2f}")
            print(f"  reasoning: {data.get('reasoning')}")
            print(f"  form_id: {data.get('form_id')}")
            print(f"  form_created: {data.get('form_created')}")
            print(f"  field_updates: {len(data.get('field_updates', {}))} fields")
            print()

            if data.get('success'):
                print("✅ TEST 1 PASSED")
                print()
                print("Summary:")
                print(f"  - Detected consultation type: {data.get('consultation_type')}")
                print(f"  - Confidence: {(data.get('confidence', 0) * 100):.0f}%")
                print(f"  - Form created: {data.get('form_created')}")
                print(f"  - Fields extracted: {len(data.get('field_updates', {}))}")

                if data.get('field_updates'):
                    print()
                    print("📝 Extracted fields:")
                    for field, value in data.get('field_updates', {}).items():
                        print(f"  - {field}: {value}")

                print()
                print("🎯 Expected behavior:")
                print("  1. Antenatal fields saved to antenatal_forms table")
                print("  2. Vital signs saved to antenatal_visits table")
                print()

                return True
            else:
                print("❌ TEST 1 FAILED")
                print(f"   Error: {data.get('error')}")
                return False

        else:
            print(f"❌ TEST 1 FAILED - HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ TEST 1 FAILED - Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_extract_form_fields(id_token):
    """Test the /api/extract-form-fields endpoint with authentication."""

    print()
    print("=" * 80)
    print("TEST 2: /api/extract-form-fields (Authenticated)")
    print("=" * 80)
    print()

    # Sample diarized segments (chunked conversation)
    diarized_segments = [
        {
            "start_time": 0.0,
            "end_time": 3.5,
            "speaker_id": "doctor",
            "speaker_role": "doctor",
            "text": "Hello, how are you feeling today?"
        },
        {
            "start_time": 3.5,
            "end_time": 8.2,
            "speaker_id": "patient",
            "speaker_role": "patient",
            "text": "Hi doctor, I'm doing well. I'm here for my pregnancy checkup."
        },
        {
            "start_time": 8.2,
            "end_time": 10.5,
            "speaker_id": "doctor",
            "speaker_role": "doctor",
            "text": "Great! How many weeks pregnant are you?"
        },
        {
            "start_time": 10.5,
            "end_time": 16.5,
            "speaker_id": "patient",
            "speaker_role": "patient",
            "text": "I'm about 6 weeks pregnant now. My last period was on November 11th, 2024."
        },
        {
            "start_time": 16.5,
            "end_time": 20.0,
            "speaker_id": "doctor",
            "speaker_role": "doctor",
            "text": "Wonderful. Is this your first pregnancy?"
        },
        {
            "start_time": 20.0,
            "end_time": 22.5,
            "speaker_id": "patient",
            "speaker_role": "patient",
            "text": "Yes, this is my first pregnancy."
        }
    ]

    request_body = {
        "diarized_segments": diarized_segments,
        "form_type": "antenatal",
        "patient_context": {
            "name": "Test Patient",
            "age": 28
        },
        "current_form_state": {},
        "chunk_index": 0
    }

    print("📤 Sending POST request to /api/extract-form-fields")
    print(f"   form_type: {request_body['form_type']}")
    print(f"   chunk_index: {request_body['chunk_index']}")
    print(f"   segments: {len(diarized_segments)} segments")
    print()

    try:
        response = requests.post(
            f"{API_URL}/api/extract-form-fields",
            json=request_body,
            headers={"Authorization": f"Bearer {id_token}"},
            timeout=30
        )

        print(f"✅ Response status: {response.status_code}")
        print()

        if response.status_code == 200:
            data = response.json()

            print("📦 RESPONSE DATA:")
            print("=" * 80)
            print(f"  field_updates: {len(data.get('field_updates', {}))} fields")
            print(f"  confidence_scores: {len(data.get('confidence_scores', {}))} scores")
            print(f"  chunk_index: {data.get('chunk_index')}")
            print()

            if data.get('field_updates'):
                print("📝 Extracted fields:")
                for field, value in data.get('field_updates', {}).items():
                    confidence = data.get('confidence_scores', {}).get(field, 0)
                    print(f"  - {field}: {value} (confidence: {confidence:.2f})")

            print()
            print("📊 Extraction metadata:")
            metadata = data.get('extraction_metadata', {})
            for key, value in metadata.items():
                print(f"  - {key}: {value}")

            print()
            print("✅ TEST 2 PASSED")
            return True

        else:
            print(f"❌ TEST 2 FAILED - HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ TEST 2 FAILED - Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print()
    print("🔐 AUTHENTICATED FORM FILLING TESTS")
    print()

    # Check if backend is running
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

    # Get Firebase ID token
    id_token = get_firebase_id_token()

    if not id_token:
        print()
        print("❌ Cannot run tests without Firebase authentication token")
        print()
        print("To get a token, you can:")
        print("1. Login to your app in a browser")
        print("2. Open browser DevTools → Application → IndexedDB → firebaseLocalStorage")
        print("3. Copy the 'stsTokenManager.accessToken' value")
        print("4. Export it: export FIREBASE_ID_TOKEN='your-token-here'")
        print()
        exit(1)

    print(f"✅ Firebase ID token obtained (length: {len(id_token)} chars)")
    print()

    # Run tests
    test1_passed = test_auto_fill_consultation_form(id_token)
    test2_passed = test_extract_form_fields(id_token)

    print()
    print("=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print(f"Test 1 (auto-fill-consultation-form): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (extract-form-fields): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print()

    if test1_passed and test2_passed:
        print("🎉 ALL TESTS PASSED")
        exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        exit(1)
