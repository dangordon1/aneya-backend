#!/usr/bin/env python
"""Test chunked diarization by sending 30-second chunks of a recording to /api/diarize-chunk in real-time"""
import subprocess
import tempfile
import os
import time
import requests
import json

# Configuration
RECORDING_PATH = "/Users/dgordon/aneya/consultation_recordings/recording-20251221-183930-8d1ecbb2.webm"
API_URL = "http://localhost:8000"
CHUNK_DURATION = 30  # seconds
OVERLAP_DURATION = 5  # seconds
LANGUAGE = "en-IN"  # Indian English

def get_audio_duration(file_path):
    """Get duration of audio file using ffprobe"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())

def extract_chunk(input_file, start_time, duration, output_file):
    """Extract audio chunk using ffmpeg"""
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-ss', str(start_time),
        '-t', str(duration),
        '-acodec', 'copy',
        '-y',
        output_file
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return result.returncode == 0

def send_chunk_to_api(chunk_file, chunk_index, chunk_start, chunk_end):
    """Send chunk to /api/diarize-chunk endpoint"""
    print(f"\n{'='*60}")
    print(f"CHUNK {chunk_index}: {chunk_start}s - {chunk_end}s")
    print(f"{'='*60}")

    with open(chunk_file, 'rb') as f:
        files = {
            'audio': (f'chunk-{chunk_index}.webm', f, 'audio/webm')
        }
        data = {
            'chunk_index': str(chunk_index),
            'chunk_start': str(chunk_start),
            'chunk_end': str(chunk_end),
            'language': LANGUAGE
        }

        start_time = time.time()
        try:
            response = requests.post(
                f"{API_URL}/api/diarize-chunk",
                files=files,
                data=data,
                timeout=180
            )
            latency = time.time() - start_time

            if response.status_code == 200:
                result = response.json()
                print(f"✅ SUCCESS in {latency:.1f}s")
                print(f"   Speakers: {result.get('detected_speakers', [])}")
                print(f"   Segments: {len(result.get('segments', []))}")
                print(f"   Model: {result.get('model', 'unknown')}")

                # DEBUG: Show full response if segments are empty
                if len(result.get('segments', [])) == 0:
                    print(f"\n⚠️  WARNING: No segments returned!")
                    print(f"   Response keys: {list(result.keys())}")
                    import json as json_mod
                    response_str = json_mod.dumps(result, indent=2)
                    print(f"   Full response:\n{response_str[:1000]}")

                # Show first 2 segments
                segments = result.get('segments', [])[:2]
                for seg in segments:
                    text_preview = seg['text'][:60] + ('...' if len(seg['text']) > 60 else '')
                    print(f"   - {seg['speaker_id']}: {text_preview}")

                return True, latency, result
            else:
                print(f"❌ FAILED: HTTP {response.status_code}")
                print(f"   Error: {response.text[:200]}")
                return False, latency, None

        except Exception as e:
            latency = time.time() - start_time
            print(f"❌ EXCEPTION after {latency:.1f}s: {e}")
            return False, latency, None

def main():
    print(f"🎬 Testing chunked diarization with real-time simulation")
    print(f"   File: {os.path.basename(RECORDING_PATH)}")
    print(f"   Chunk duration: {CHUNK_DURATION}s")
    print(f"   Overlap: {OVERLAP_DURATION}s")
    print(f"   Testing first 2 chunks to verify speaker ID mapping")

    results = []

    with tempfile.TemporaryDirectory() as temp_dir:
        for chunk_idx in range(2):  # Test first 2 chunks only
            # Calculate chunk boundaries (with overlap)
            chunk_start = max(0, chunk_idx * CHUNK_DURATION - OVERLAP_DURATION)
            chunk_end = (chunk_idx + 1) * CHUNK_DURATION

            # Chunk 0: 0-30s, Chunk 1: 25-55s (5s overlap at 25-30s)

            # Extract chunk
            chunk_file = os.path.join(temp_dir, f'chunk-{chunk_idx}.webm')
            print(f"\n📦 Extracting chunk {chunk_idx}: {chunk_start:.1f}s - {chunk_end:.1f}s")

            if not extract_chunk(RECORDING_PATH, chunk_start, chunk_end - chunk_start, chunk_file):
                print(f"❌ Failed to extract chunk {chunk_idx}")
                continue

            file_size = os.path.getsize(chunk_file) / 1024
            print(f"   Chunk size: {file_size:.1f} KB")

            # Send to API
            success, latency, result = send_chunk_to_api(chunk_file, chunk_idx, chunk_start, chunk_end)

            results.append({
                'chunk_index': chunk_idx,
                'success': success,
                'latency': latency,
                'start': chunk_start,
                'end': chunk_end
            })

            # Small delay between chunks
            if chunk_idx < 1:  # Testing 2 chunks only
                time.sleep(0.5)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print(f"Total chunks processed: {len(results)}")
    print(f"✅ Successful: {len(successful)}")
    print(f"❌ Failed: {len(failed)}")

    if successful:
        avg_latency = sum(r['latency'] for r in successful) / len(successful)
        print(f"\n⏱️  Average latency: {avg_latency:.1f}s")
        print(f"   Min latency: {min(r['latency'] for r in successful):.1f}s")
        print(f"   Max latency: {max(r['latency'] for r in successful):.1f}s")

        if avg_latency < 10:
            print(f"   🎉 EXCELLENT! Average latency under 10s")
        elif avg_latency < 30:
            print(f"   ✅ GOOD! Average latency under 30s")
        else:
            print(f"   ⚠️  SLOW: Average latency over 30s")

    if failed:
        print(f"\n❌ Failed chunks: {[r['chunk_index'] for r in failed]}")

    # Final verdict
    print(f"\n{'='*60}")
    if len(successful) == len(results) and avg_latency < 10:
        print("✅ TEST PASSED: All chunks succeeded with good latency!")
    elif len(successful) == len(results):
        print("⚠️  TEST PARTIAL: All chunks succeeded but latency is high")
    else:
        print("❌ TEST FAILED: Some chunks failed")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
