#!/usr/bin/env python3
"""
Test frontend integration - verify /api/diarize-chunk endpoint works as expected
"""
import requests
import json

API_URL = "http://localhost:8000"

# Test chunk data from our earlier test
test_chunk_path = "test_chunk_30s.webm"

print("🧪 Testing Frontend Integration")
print(f"📍 API URL: {API_URL}")
print(f"📦 Test chunk: {test_chunk_path}")
print()

# Test /api/diarize-chunk endpoint
print("1️⃣  Testing /api/diarize-chunk endpoint...")

try:
    with open(test_chunk_path, 'rb') as f:
        files = {'audio': ('chunk-0.webm', f, 'audio/webm')}
        data = {
            'chunk_index': '0',
            'chunk_start': '0.0',
            'chunk_end': '30.0',
            'language': 'en-IN'
        }

        response = requests.post(
            f"{API_URL}/api/diarize-chunk",
            files=files,
            data=data,
            timeout=60
        )

        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Success!")
            print(f"   📊 Segments: {len(result.get('segments', []))}")
            print(f"   👥 Speakers: {result.get('detected_speakers', [])}")
            print(f"   ⏱️  Latency: {result.get('latency_seconds', 0)}s")
            print(f"   🔧 Model: {result.get('model', 'unknown')}")

            # Show overlap stats
            if result.get('end_overlap_stats'):
                print(f"   📍 End overlap stats:")
                for speaker, stats in result['end_overlap_stats'].items():
                    print(f"      {speaker}: {stats['word_count']} words, {stats['duration']:.1f}s")

            print()
            print("2️⃣  Sample segments:")
            for i, seg in enumerate(result.get('segments', [])[:3]):
                print(f"   [{seg['start_time']:.1f}s] {seg['speaker_id']}: {seg['text'][:50]}...")

        else:
            print(f"   ❌ Failed: {response.text}")

except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("3️⃣  Testing /api/identify-speaker-roles endpoint...")

# Prepare sample segments for speaker identification
sample_segments = [
    {"speaker_id": "speaker_1", "text": "Okay. Good evening. How are you?", "start_time": 0.17, "end_time": 4.69},
    {"speaker_id": "speaker_2", "text": "It hasn't come yet.", "start_time": 5.19, "end_time": 5.99},
    {"speaker_id": "speaker_1", "text": "How are you doing?", "start_time": 5.93, "end_time": 7.85},
    {"speaker_id": "speaker_2", "text": "Mostly fine.", "start_time": 8.59, "end_time": 10.09},
    {"speaker_id": "speaker_1", "text": "Yes.", "start_time": 10.27, "end_time": 10.73},
    {"speaker_id": "speaker_2", "text": "But I'm having this cough problem every day. And I'm in my first trimester, eight weeks.", "start_time": 10.71, "end_time": 18.79},
    {"speaker_id": "speaker_1", "text": "Hmm hmm hmm. So did you have fever?", "start_time": 18.77, "end_time": 22.01},
    {"speaker_id": "speaker_2", "text": "I had a fever two weeks ago, a very high fever, and the fever went away.", "start_time": 22.67, "end_time": 26.97}
]

try:
    response = requests.post(
        f"{API_URL}/api/identify-speaker-roles",
        json={'segments': sample_segments},
        timeout=30
    )

    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"   ✅ Success!")
        print(f"   🏥 Speaker roles: {result.get('speaker_roles', {})}")
        print(f"   ⏱️  Latency: {result.get('latency_seconds', 0)}s")
    else:
        print(f"   ❌ Failed: {response.text}")

except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 60)
print("✅ INTEGRATION TEST COMPLETE")
print("=" * 60)
print()
print("Frontend is ready to test at: http://localhost:5173")
print()
print("To test the full flow:")
print("1. Open http://localhost:5173 in your browser")
print("2. Click 'Start Recording'")
print("3. Speak or play audio for at least 30 seconds")
print("4. Watch the two-box UI:")
print("   - Left box: Real-time transcript (immediate)")
print("   - Right box: Speaker-labeled transcript (appears after 30s)")
print("5. After 30s, you should see 'Doctor:' and 'Patient:' labels")
print()
