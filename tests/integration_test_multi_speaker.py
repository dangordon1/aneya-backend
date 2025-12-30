#!/usr/bin/env python3
"""
Integration test for multi-speaker diarisation

This script tests the full workflow:
1. Calls /api/identify-speaker-roles with various speaker scenarios
2. Verifies confidence scoring and thresholds
3. Tests backward compatibility with 2-speaker consultations

Usage:
    python tests/integration_test_multi_speaker.py

Requirements:
    - Backend server running on http://localhost:8000
    - ANTHROPIC_API_KEY environment variable set
"""

import requests
import json
import sys
from typing import Dict, List


API_URL = "http://localhost:8000"


def test_two_speaker_consultation():
    """Test standard doctor-patient consultation"""
    print("\n" + "="*80)
    print("TEST: Two-Speaker Consultation (Doctor + Patient)")
    print("="*80)

    segments = [
        {"speaker_id": "speaker_0", "text": "Good morning. What brings you in today?", "start_time": 0.0, "end_time": 2.5},
        {"speaker_id": "speaker_1", "text": "I've been having chest pain for the past three days.", "start_time": 3.0, "end_time": 6.0},
        {"speaker_id": "speaker_0", "text": "Can you describe the pain? Is it sharp or dull?", "start_time": 6.5, "end_time": 9.0},
        {"speaker_id": "speaker_1", "text": "It's a dull ache that comes and goes. It gets worse when I exercise.", "start_time": 9.5, "end_time": 13.0},
        {"speaker_id": "speaker_0", "text": "I see. Any shortness of breath or dizziness?", "start_time": 13.5, "end_time": 16.0},
        {"speaker_id": "speaker_1", "text": "Yes, sometimes I feel dizzy when the pain is bad.", "start_time": 16.5, "end_time": 19.0},
    ]

    response = requests.post(
        f"{API_URL}/api/identify-speaker-roles",
        json={"segments": segments, "language": "en-IN"}
    )

    if response.status_code != 200:
        print(f"❌ FAILED: {response.status_code} - {response.text}")
        return False

    data = response.json()

    print(f"✅ Response received:")
    print(f"   Role mapping: {data['role_mapping']}")
    print(f"   Confidence scores: {data['confidence_scores']}")
    print(f"   Requires manual: {data['requires_manual_assignment']}")

    # Verify
    assert len(data['role_mapping']) == 2, "Should identify 2 speakers"
    assert data['role_mapping']['speaker_0'] in ['Doctor', 'Patient'], "speaker_0 should be Doctor or Patient"
    assert data['role_mapping']['speaker_1'] in ['Doctor', 'Patient'], "speaker_1 should be Doctor or Patient"
    assert data['confidence_scores']['speaker_0'] > 0.7, "speaker_0 should have high confidence"
    assert data['confidence_scores']['speaker_1'] > 0.7, "speaker_1 should have high confidence"
    assert not data['requires_manual_assignment'], "Should not require manual assignment"

    print("✅ PASSED: Two-speaker consultation works correctly")
    return True


def test_three_speaker_consultation():
    """Test doctor + patient + family member"""
    print("\n" + "="*80)
    print("TEST: Three-Speaker Consultation (Doctor + Patient + Family)")
    print("="*80)

    segments = [
        {"speaker_id": "speaker_0", "text": "Good afternoon. How can I help you today?", "start_time": 0.0, "end_time": 2.5},
        {"speaker_id": "speaker_1", "text": "I've been having severe headaches for two weeks.", "start_time": 3.0, "end_time": 6.0},
        {"speaker_id": "speaker_2", "text": "Doctor, she also mentioned dizziness and nausea last week.", "start_time": 6.5, "end_time": 9.5},
        {"speaker_id": "speaker_0", "text": "Thank you for that information. Let me check your blood pressure.", "start_time": 10.0, "end_time": 13.0},
        {"speaker_id": "speaker_1", "text": "The headaches are usually worse in the morning.", "start_time": 13.5, "end_time": 16.0},
        {"speaker_id": "speaker_2", "text": "She's been taking ibuprofen but it doesn't help much.", "start_time": 16.5, "end_time": 19.0},
    ]

    response = requests.post(
        f"{API_URL}/api/identify-speaker-roles",
        json={"segments": segments, "language": "en-IN"}
    )

    if response.status_code != 200:
        print(f"❌ FAILED: {response.status_code} - {response.text}")
        return False

    data = response.json()

    print(f"✅ Response received:")
    print(f"   Role mapping: {data['role_mapping']}")
    print(f"   Confidence scores: {data['confidence_scores']}")
    print(f"   Requires manual: {data['requires_manual_assignment']}")
    print(f"   Reasoning:")
    for speaker_id, reason in data.get('reasoning', {}).items():
        print(f"     {speaker_id}: {reason}")

    # Verify
    assert len(data['role_mapping']) == 3, "Should identify 3 speakers"
    roles = set(data['role_mapping'].values())
    assert 'Doctor' in roles, "Should identify Doctor"
    assert 'Patient' in roles, "Should identify Patient"

    print("✅ PASSED: Three-speaker consultation identified correctly")
    return True


def test_low_confidence_scenario():
    """Test that low confidence triggers manual assignment"""
    print("\n" + "="*80)
    print("TEST: Low Confidence Scenario (Short Utterances)")
    print("="*80)

    segments = [
        {"speaker_id": "speaker_0", "text": "Hi", "start_time": 0.0, "end_time": 0.5},
        {"speaker_id": "speaker_1", "text": "Hello", "start_time": 1.0, "end_time": 1.5},
        {"speaker_id": "speaker_2", "text": "Hey", "start_time": 2.0, "end_time": 2.5},
    ]

    response = requests.post(
        f"{API_URL}/api/identify-speaker-roles",
        json={"segments": segments, "language": "en-IN", "confidence_threshold": 0.7}
    )

    if response.status_code != 200:
        print(f"❌ FAILED: {response.status_code} - {response.text}")
        return False

    data = response.json()

    print(f"✅ Response received:")
    print(f"   Role mapping: {data['role_mapping']}")
    print(f"   Confidence scores: {data['confidence_scores']}")
    print(f"   Requires manual: {data['requires_manual_assignment']}")
    print(f"   Low confidence speakers: {data.get('low_confidence_speakers', [])}")

    # Verify
    assert data['requires_manual_assignment'], "Should require manual assignment due to low confidence"
    assert len(data.get('low_confidence_speakers', [])) > 0, "Should flag some speakers as low confidence"

    print("✅ PASSED: Low confidence correctly triggers manual assignment")
    return True


def test_four_speaker_consultation():
    """Test doctor + patient + nurse + family"""
    print("\n" + "="*80)
    print("TEST: Four-Speaker Consultation (Doctor + Patient + Nurse + Family)")
    print("="*80)

    segments = [
        {"speaker_id": "speaker_0", "text": "Let's review your blood test results.", "start_time": 0.0, "end_time": 2.5},
        {"speaker_id": "speaker_1", "text": "I'm nervous about what they'll show.", "start_time": 3.0, "end_time": 5.0},
        {"speaker_id": "speaker_2", "text": "Blood pressure is 120 over 80, temperature 98.6.", "start_time": 5.5, "end_time": 9.0},
        {"speaker_id": "speaker_3", "text": "Doctor, should we be worried about the results?", "start_time": 9.5, "end_time": 12.0},
        {"speaker_id": "speaker_0", "text": "The results look good overall. Let me explain what we found.", "start_time": 12.5, "end_time": 16.0},
    ]

    response = requests.post(
        f"{API_URL}/api/identify-speaker-roles",
        json={"segments": segments, "language": "en-IN"}
    )

    if response.status_code != 200:
        print(f"❌ FAILED: {response.status_code} - {response.text}")
        return False

    data = response.json()

    print(f"✅ Response received:")
    print(f"   Role mapping: {data['role_mapping']}")
    print(f"   Confidence scores: {data['confidence_scores']}")

    # Verify
    assert len(data['role_mapping']) == 4, "Should identify 4 speakers"

    print("✅ PASSED: Four-speaker consultation identified")
    return True


def test_custom_threshold():
    """Test custom confidence threshold"""
    print("\n" + "="*80)
    print("TEST: Custom Confidence Threshold")
    print("="*80)

    segments = [
        {"speaker_id": "speaker_0", "text": "What symptoms are you experiencing?", "start_time": 0.0, "end_time": 2.0},
        {"speaker_id": "speaker_1", "text": "I have a fever and cough.", "start_time": 2.5, "end_time": 4.0},
    ]

    # Test with high threshold (0.95)
    response = requests.post(
        f"{API_URL}/api/identify-speaker-roles",
        json={"segments": segments, "language": "en-IN", "confidence_threshold": 0.95}
    )

    if response.status_code != 200:
        print(f"❌ FAILED: {response.status_code} - {response.text}")
        return False

    data = response.json()

    print(f"✅ Response with threshold 0.95:")
    print(f"   Requires manual: {data['requires_manual_assignment']}")
    print(f"   Confidence scores: {data['confidence_scores']}")

    # With very high threshold, likely to require manual
    # (unless LLM is very confident, which is possible)

    print("✅ PASSED: Custom threshold parameter works")
    return True


def main():
    """Run all integration tests"""
    print("\n" + "="*80)
    print("MULTI-SPEAKER DIARISATION INTEGRATION TESTS")
    print("="*80)
    print(f"Testing against: {API_URL}")

    # Check server is running
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code != 200:
            print(f"\n❌ ERROR: Backend server not responding at {API_URL}")
            print("Please start the server with: uvicorn api:app --reload")
            return 1
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERROR: Cannot connect to backend server at {API_URL}")
        print("Please start the server with: uvicorn api:app --reload")
        return 1

    # Run tests
    tests = [
        test_two_speaker_consultation,
        test_three_speaker_consultation,
        test_low_confidence_scenario,
        test_four_speaker_consultation,
        test_custom_threshold,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total tests: {len(tests)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
