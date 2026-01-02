#!/usr/bin/env python
"""
Test speaker role identification endpoint
Uses segments from the first chunk of our diarization test
"""

import json
import requests

# Load the first chunk's segments from our test results
with open('chunked_test_output/full_test_results.json') as f:
    data = json.load(f)

# Get first chunk's segments
first_chunk_segments = data['diarization_results'][0]['segments']

print("=" * 80)
print("🧪 TESTING SPEAKER ROLE IDENTIFICATION")
print("=" * 80)
print()
print(f"📊 Using {len(first_chunk_segments)} segments from first chunk")
print()

# Show first few segments
print("First 5 segments:")
for seg in first_chunk_segments[:5]:
    print(f"  {seg['speaker_id']:12s} {seg['text'][:60]}")
print()

# Call the API
API_URL = "http://localhost:8000/api/identify-speaker-roles"

payload = {
    "segments": first_chunk_segments,
    "language": "en-IN"
}

print("🔍 Calling speaker role identification API...")
print()

try:
    response = requests.post(API_URL, json=payload, timeout=30)
    response.raise_for_status()

    result = response.json()

    print("✅ API Response:")
    print(f"  Success: {result['success']}")
    print(f"  Latency: {result['latency_seconds']}s")
    print(f"  Model: {result['model']}")
    print()
    print("👥 Speaker Role Mapping:")
    for speaker_id, role in result['role_mapping'].items():
        print(f"  {speaker_id} → {role}")
    print()

    # Apply mapping to segments and show result
    print("=" * 80)
    print("TRANSCRIPT WITH ROLES")
    print("=" * 80)
    print()

    role_mapping = result['role_mapping']

    for seg in first_chunk_segments[:10]:
        role = role_mapping.get(seg['speaker_id'], seg['speaker_id'])
        print(f"{seg['start_time']:6.1f}s  {role:12s} {seg['text']}")

    if len(first_chunk_segments) > 10:
        print(f"... and {len(first_chunk_segments) - 10} more segments")

    print()
    print("✅ Test complete!")

except requests.exceptions.ConnectionError:
    print("❌ Error: Could not connect to API")
    print("   Make sure the backend is running: python api.py")
except Exception as e:
    print(f"❌ Error: {e}")
    if hasattr(e, 'response'):
        print(f"   Response: {e.response.text}")
