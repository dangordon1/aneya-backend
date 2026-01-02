#!/usr/bin/env python
"""
Quick test of /api/diarize-chunk endpoint
"""

import requests
import os

API_URL = "http://localhost:8000/api/diarize-chunk"

# Use first 30 seconds from our test recording
CHUNK_FILE = "./chunked_test_output/chunk-00.webm"

if not os.path.exists(CHUNK_FILE):
    print("❌ Test chunk file not found. Run test_full_chunked.py first.")
    exit(1)

print("=" * 80)
print("🧪 TESTING /api/diarize-chunk ENDPOINT")
print("=" * 80)
print()

# Prepare request
with open(CHUNK_FILE, 'rb') as f:
    files = {'audio': ('chunk-00.webm', f, 'audio/webm')}

    data = {
        'chunk_index': 0,
        'chunk_start': 0.0,
        'chunk_end': 30.0,
        'language': 'en-IN'
    }

    print(f"📤 Sending chunk 0 (0-30s) to {API_URL}")
    print()

    try:
        response = requests.post(API_URL, files=files, data=data, timeout=60)
        response.raise_for_status()

        result = response.json()

        print("✅ SUCCESS!")
        print()
        print(f"Chunk Index: {result['chunk_index']}")
        print(f"Time Range: {result['chunk_start']}s - {result['chunk_end']}s")
        print(f"Latency: {result['latency_seconds']}s")
        print(f"Model: {result['model']}")
        print(f"Speakers: {result['detected_speakers']}")
        print(f"Segments: {len(result['segments'])}")
        print()

        print("📍 Start Overlap Stats:")
        for speaker_id, stats in result['start_overlap_stats'].items():
            print(f"  {speaker_id}: {stats['duration']:.1f}s, {stats['word_count']} words")

        print()
        print("📍 End Overlap Stats:")
        for speaker_id, stats in result['end_overlap_stats'].items():
            print(f"  {speaker_id}: {stats['duration']:.1f}s, {stats['word_count']} words")

        print()
        print("📝 First 3 segments:")
        for seg in result['segments'][:3]:
            print(f"  {seg['start_time']:.1f}s {seg['speaker_id']:12s} {seg['text'][:50]}")

        print()
        print("✅ Endpoint test passed!")

    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to backend")
        print("   Make sure backend is running: python api.py")
    except Exception as e:
        print(f"❌ Error: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
