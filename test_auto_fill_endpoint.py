#!/usr/bin/env python3
"""
Quick test for the /api/auto-fill-consultation-form endpoint.

Tests basic endpoint functionality with minimal sample data.
"""

import requests
import json
import uuid
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

API_URL = "http://localhost:8000"

def get_real_patient_and_appointment_from_db():
    """Fetch a real patient and create/find an appointment for testing."""
    try:
        # Load Supabase credentials from environment
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            print("⚠️  SUPABASE_URL or SUPABASE_SERVICE_KEY not found in environment")
            print("   Using fake IDs (test will fail at database level)")
            return None, None, None

        supabase: Client = create_client(supabase_url, supabase_key)

        # Get first patient from database
        patient_result = supabase.table("patients").select("id, user_id").limit(1).execute()

        if not patient_result.data or len(patient_result.data) == 0:
            print("⚠️  No patients found in database")
            return None, None, None

        patient = patient_result.data[0]
        patient_id = patient['id']
        user_id = patient.get('user_id')
        print(f"✅ Found real patient in database: {patient_id}")

        # Try to find an existing appointment for this patient
        appt_result = supabase.table("appointments")\
            .select("id")\
            .eq("patient_id", patient_id)\
            .limit(1)\
            .execute()

        if appt_result.data and len(appt_result.data) > 0:
            appointment_id = appt_result.data[0]['id']
            print(f"✅ Found existing appointment: {appointment_id}")
            return patient_id, user_id, appointment_id

        # No appointment found - create a new one for testing
        print("📝 Creating test appointment...")
        from datetime import datetime, timedelta

        new_appointment = {
            'patient_id': patient_id,
            'doctor_user_id': user_id,  # Using same user_id for simplicity
            'appointment_date': (datetime.now() + timedelta(days=1)).isoformat(),
            'appointment_type': 'obgyn_antenatal',
            'status': 'scheduled',
            'specialty': 'obstetrics_gynecology'
        }

        appt_create_result = supabase.table("appointments").insert(new_appointment).execute()

        if appt_create_result.data and len(appt_create_result.data) > 0:
            appointment_id = appt_create_result.data[0]['id']
            print(f"✅ Created test appointment: {appointment_id}")
            return patient_id, user_id, appointment_id
        else:
            print("⚠️  Failed to create appointment")
            return patient_id, user_id, None

    except Exception as e:
        print(f"⚠️  Error fetching data from database: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None

def test_auto_fill_endpoint():
    """Test the auto-fill endpoint with sample antenatal conversation."""

    print("=" * 80)
    print("TESTING /api/auto-fill-consultation-form ENDPOINT")
    print("=" * 80)
    print()

    # Sample antenatal conversation transcript
    sample_transcript = """[0.0s] Doctor: Hello, how are you feeling today?
[3.5s] Patient: Hi doctor, I'm doing well. I'm here for my pregnancy checkup.
[8.2s] Doctor: Great! How many weeks pregnant are you?
[10.5s] Patient: I'm about 12 weeks pregnant now.
[14.0s] Doctor: Wonderful. Is this your first pregnancy?
[16.5s] Patient: No, this is my second pregnancy. My first child is 3 years old.
[22.0s] Doctor: That's great. Any complications so far?
[24.5s] Patient: No, everything has been smooth so far."""

    # Try to get real patient and appointment from database
    print("🔍 Fetching real patient and appointment from database...")
    real_patient_id, real_user_id, real_appointment_id = get_real_patient_and_appointment_from_db()
    print()

    # Generate UUIDs for test data
    consultation_id = str(uuid.uuid4())
    appointment_id = real_appointment_id if real_appointment_id else str(uuid.uuid4())
    patient_id = real_patient_id if real_patient_id else str(uuid.uuid4())
    user_id = real_user_id if real_user_id else str(uuid.uuid4())

    # Prepare test request
    request_body = {
        "consultation_id": consultation_id,
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "original_transcript": sample_transcript,
        "consultation_text": "Patient presented for 12-week antenatal checkup. Second pregnancy.",
        "patient_snapshot": {
            "user_id": user_id,
            "name": "Test Patient"
        }
    }

    print("📤 Sending POST request to /api/auto-fill-consultation-form")
    print(f"   consultation_id: {request_body['consultation_id']}")
    print(f"   appointment_id: {request_body['appointment_id']}")
    print(f"   patient_id: {request_body['patient_id']}")
    print()
    print("📋 Sample transcript (antenatal conversation):")
    print(sample_transcript[:200] + "...")
    print()

    try:
        response = requests.post(
            f"{API_URL}/api/auto-fill-consultation-form",
            json=request_body,
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
            print(f"  confidence: {data.get('confidence'):.2f}")
            print(f"  reasoning: {data.get('reasoning')}")
            print(f"  form_id: {data.get('form_id')}")
            print(f"  form_created: {data.get('form_created')}")
            print(f"  field_updates: {len(data.get('field_updates', {}))} fields")
            print(f"  error: {data.get('error')}")
            print()

            if data.get('success'):
                print("✅ TEST PASSED")
                print()
                print("Summary:")
                print(f"  - Detected consultation type: {data.get('consultation_type')}")
                print(f"  - Confidence: {(data.get('confidence') * 100):.0f}%")
                print(f"  - Form created: {data.get('form_created')}")
                print(f"  - Fields extracted: {len(data.get('field_updates', {}))}")

                if data.get('field_updates'):
                    print()
                    print("📝 Extracted fields:")
                    for field, value in data.get('field_updates', {}).items():
                        print(f"  - {field}: {value}")

                return True
            else:
                print("❌ TEST FAILED")
                print(f"   Error: {data.get('error')}")
                return False

        else:
            print(f"❌ TEST FAILED - HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ TEST FAILED - Could not connect to backend")
        print("   Make sure the backend is running at http://localhost:8000")
        return False

    except Exception as e:
        print(f"❌ TEST FAILED - Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
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

    # Run test
    success = test_auto_fill_endpoint()

    print()
    print("=" * 80)
    if success:
        print("✅ ENDPOINT TEST PASSED")
    else:
        print("❌ ENDPOINT TEST FAILED")
    print("=" * 80)
    print()
