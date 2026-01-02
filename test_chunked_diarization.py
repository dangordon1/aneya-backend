#!/usr/bin/env python3
"""
Test chunked diarization by simulating real-time streaming
Reads an audio file and sends 30-second chunks with 5-second overlap
"""

import asyncio
import httpx
import subprocess
import tempfile
import os
import json
from pathlib import Path

CHUNK_DURATION = 30  # seconds
OVERLAP_DURATION = 5  # seconds
API_URL = "http://localhost:8000"

async def extract_audio_chunk(input_file: str, start_sec: float, duration: float) -> bytes:
    """Extract a chunk of audio using ffmpeg"""
    print(f"  📦 Extracting {start_sec:.1f}s - {start_sec + duration:.1f}s...")

    # Use ffmpeg to extract the chunk
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run([
            'ffmpeg',
            '-i', input_file,
            '-ss', str(start_sec),
            '-t', str(duration),
            '-c', 'copy',
            tmp_path,
            '-y'
        ], capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            print(f"  ⚠️  FFmpeg error: {result.stderr}")
            return None

        with open(tmp_path, 'rb') as f:
            data = f.read()

        print(f"  ✓ Extracted {len(data)/1024:.1f} KB")
        return data

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


async def get_audio_duration(input_file: str) -> float:
    """Get audio duration using ffmpeg (more reliable for webm)"""
    try:
        # Use ffmpeg to decode and get duration from stderr
        result = subprocess.run([
            'ffmpeg',
            '-i', input_file,
            '-f', 'null',
            '-'
        ], capture_output=True, text=True, timeout=60)

        # Parse stderr for duration: "time=00:01:23.45"
        for line in result.stderr.split('\n'):
            if 'time=' in line and 'bitrate=' in line:
                # Get the last time value (final duration)
                time_str = line.split('time=')[1].split()[0]
                # Parse HH:MM:SS.ms
                parts = time_str.split(':')
                if len(parts) == 3:
                    hours = float(parts[0])
                    minutes = float(parts[1])
                    seconds = float(parts[2])
                    duration = hours * 3600 + minutes * 60 + seconds
                    return duration

        # Fallback: estimate from file size
        file_size_mb = os.path.getsize(input_file) / (1024 * 1024)
        estimated_duration = file_size_mb * 60  # ~1MB per minute
        print(f"⚠️  Could not detect exact duration, estimating: {estimated_duration:.1f}s")
        return estimated_duration

    except Exception as e:
        print(f"❌ Error getting duration: {e}")
        return 120.0  # Default fallback


async def send_chunk_for_diarization(
    chunk_data: bytes,
    chunk_index: int,
    chunk_start: float,
    chunk_end: float,
    language: str = "en-IN"
):
    """Send a chunk to the backend for diarization"""
    print(f"\n🎬 Chunk {chunk_index}: {chunk_start:.1f}s - {chunk_end:.1f}s")

    files = {
        'audio': (f'chunk-{chunk_index}.webm', chunk_data, 'audio/webm')
    }

    data = {
        'chunk_index': str(chunk_index),
        'chunk_start': str(chunk_start),
        'chunk_end': str(chunk_end),
        'language': language
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                f"{API_URL}/api/diarize-chunk",
                files=files,
                data=data
            )

            if response.status_code == 200:
                result = response.json()
                print(f"  ✅ Success: {len(result.get('detected_speakers', []))} speakers, {len(result.get('segments', []))} segments")
                print(f"  👥 Speakers: {result.get('detected_speakers', [])}")
                print(f"  ⏱️  Latency: {result.get('latency_seconds', 0):.1f}s")

                # Show first few segments
                segments = result.get('segments', [])
                if segments:
                    print(f"  📝 Sample segments:")
                    for seg in segments[:3]:
                        print(f"     {seg['speaker_id']}: {seg['text'][:60]}...")

                return result
            else:
                print(f"  ❌ Error {response.status_code}: {response.text}")
                return None

        except Exception as e:
            print(f"  ❌ Exception: {e}")
            return None


async def test_chunked_diarization(audio_file: str):
    """
    Test chunked diarization by streaming an audio file chunk-by-chunk
    """
    print(f"🎵 Testing chunked diarization with: {audio_file}")

    # Check if file exists
    if not os.path.exists(audio_file):
        print(f"❌ File not found: {audio_file}")
        return

    # Get audio duration
    total_duration = await get_audio_duration(audio_file)
    print(f"📊 Total duration: {total_duration:.1f}s")

    # Calculate number of chunks
    num_chunks = int((total_duration - OVERLAP_DURATION) / (CHUNK_DURATION - OVERLAP_DURATION)) + 1
    print(f"📦 Will process {num_chunks} chunks")
    print(f"⚙️  Chunk duration: {CHUNK_DURATION}s, Overlap: {OVERLAP_DURATION}s\n")

    all_results = []

    # Process each chunk
    for chunk_idx in range(num_chunks):
        # Calculate chunk boundaries with overlap
        if chunk_idx == 0:
            chunk_start = 0.0
        else:
            chunk_start = chunk_idx * (CHUNK_DURATION - OVERLAP_DURATION)

        chunk_end = min(chunk_start + CHUNK_DURATION, total_duration)
        actual_duration = chunk_end - chunk_start

        # Extract chunk
        chunk_data = await extract_audio_chunk(audio_file, chunk_start, actual_duration)

        if not chunk_data:
            print(f"  ⚠️  Skipping chunk {chunk_idx} - extraction failed")
            continue

        # Send to backend
        result = await send_chunk_for_diarization(
            chunk_data,
            chunk_idx,
            chunk_start,
            chunk_end,
            language="en-IN"
        )

        if result:
            all_results.append({
                'chunk_index': chunk_idx,
                'chunk_start': chunk_start,
                'chunk_end': chunk_end,
                'result': result
            })

        # Simulate real-time processing delay
        # (In production, this happens naturally as recording continues)
        if chunk_idx < num_chunks - 1:
            print(f"  ⏸️  Waiting for next chunk...")
            await asyncio.sleep(2)

    # Summary
    print(f"\n{'='*60}")
    print(f"📊 SUMMARY")
    print(f"{'='*60}")
    print(f"Total chunks processed: {len(all_results)}/{num_chunks}")

    total_segments = sum(len(r['result'].get('segments', [])) for r in all_results)
    print(f"Total segments extracted: {total_segments}")

    # Show all unique speakers across chunks
    all_speakers = set()
    for r in all_results:
        speakers = r['result'].get('detected_speakers', [])
        all_speakers.update(speakers)

    print(f"Unique speakers detected: {sorted(all_speakers)}")

    # Show complete merged transcript
    print(f"\n📝 MERGED TRANSCRIPT:")
    print(f"{'-'*60}")

    for r in all_results:
        segments = r['result'].get('segments', [])
        chunk_idx = r['chunk_index']
        chunk_start = r['chunk_start']

        for seg in segments:
            global_start = chunk_start + seg['start_time']
            print(f"[{global_start:6.1f}s] {seg['speaker_id']:12s}: {seg['text']}")

    print(f"{'-'*60}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
    else:
        audio_file = "/Users/dgordon/aneya/consultation_recordings/recording-20251221-183930-8d1ecbb2.webm"

    asyncio.run(test_chunked_diarization(audio_file))
