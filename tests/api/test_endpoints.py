#!/usr/bin/env python3
"""
API Endpoint Tests

Tests the FastAPI endpoints for frontend-backend compatibility.
Requires the API server to be running on localhost:8000.

Usage:
    # First start the API server:
    python api.py &

    # Then run tests:
    python -m pytest tests/api/test_endpoints.py -v

Or run directly:
    python tests/api/test_endpoints.py
"""

import asyncio
import json
import sys
import requests
import sseclient
from typing import Generator

API_URL = "http://localhost:8000"


def check_api_running() -> bool:
    """Check if the API server is running."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


def test_health_endpoint():
    """Test the health check endpoint."""
    print("\n" + "-"*70)
    print("TEST: Health Endpoint")
    print("-"*70)

    response = requests.get(f"{API_URL}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Body: {response.json()}")

    assert response.status_code == 200
    return True


def test_analyze_endpoint():
    """Test the /api/analyze SSE endpoint."""
    print("\n" + "-"*70)
    print("TEST: Analyze Endpoint (SSE)")
    print("-"*70)

    payload = {
        "consultation": "30 year old with cough and fever for 3 days",
        "location": "IN"
    }

    print(f"   Consultation: {payload['consultation']}")

    response = requests.post(
        f"{API_URL}/api/analyze",
        json=payload,
        stream=True,
        headers={"Accept": "text/event-stream"}
    )

    print(f"   Status: {response.status_code}")

    if response.status_code != 200:
        print(f"   ❌ Failed: {response.text}")
        return False

    # Parse SSE events
    events = []
    client = sseclient.SSEClient(response)

    for event in client.events():
        if event.data:
            try:
                data = json.loads(event.data)
                event_type = data.get('type', 'unknown')
                events.append(event_type)
                print(f"   📤 Event: {event_type}")

                if event_type == 'complete':
                    break
            except json.JSONDecodeError:
                pass

    print(f"\n   Events received: {len(events)}")
    print(f"   Types: {' → '.join(events[:10])}")

    has_diagnoses = 'diagnoses' in events
    has_complete = 'complete' in events

    print(f"   Diagnoses event: {'✅' if has_diagnoses else '❌'}")
    print(f"   Complete event: {'✅' if has_complete else '❌'}")

    return has_diagnoses and has_complete


def test_summarize_endpoint():
    """Test the /api/summarize endpoint."""
    print("\n" + "-"*70)
    print("TEST: Summarize Endpoint")
    print("-"*70)

    transcript = """1. [0s - 5s] speaker_0: What brings you in today?
2. [5s - 15s] speaker_1: I've had a cough and fever for three days.
3. [15s - 20s] speaker_0: Any other symptoms?
4. [20s - 30s] speaker_1: Some body aches and headache."""

    payload = {"transcript": transcript}

    response = requests.post(f"{API_URL}/api/summarize", json=payload)
    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"   Success: {data.get('success')}")
        if data.get('summary'):
            print(f"   Summary length: {len(data['summary'])} chars")
        return data.get('success', False)
    else:
        print(f"   ❌ Failed: {response.text[:200]}")
        return False


def run_all_tests():
    """Run all API tests."""
    print("\n" + "="*70)
    print("🧪 API ENDPOINT TEST SUITE")
    print("="*70)
    print(f"API URL: {API_URL}")

    # Check if API is running
    if not check_api_running():
        print("\n❌ API server is not running!")
        print("   Start it with: python api.py")
        return False

    print("✅ API server is running\n")

    results = {}

    # Test 1: Health
    try:
        results['Health'] = test_health_endpoint()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['Health'] = False

    # Test 2: Analyze
    try:
        results['Analyze'] = test_analyze_endpoint()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['Analyze'] = False

    # Test 3: Summarize
    try:
        results['Summarize'] = test_summarize_endpoint()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['Summarize'] = False

    # Summary
    print("\n" + "="*70)
    print("📊 API TEST SUMMARY")
    print("="*70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*70)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
