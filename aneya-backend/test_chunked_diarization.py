#!/usr/bin/env python
"""
Test chunked diarization by splitting a recording into overlapping chunks
and sending them to the diarization API
"""

import subprocess
import os
import time
import json
import requests
from pathlib import Path

# Configuration
INPUT_FILE = "../consultation_recordings/recording-20251221-183930-8d1ecbb2.webm"
CHUNK_DURATION = 30  # seconds
OVERLAP_DURATION = 10  # seconds
OUTPUT_DIR = "./chunked_test_output"
API_URL = "http://localhost:8000/api/diarize"  # Use existing batch endpoint for testing

def get_audio_duration(file_path):
    """Get audio duration in seconds using ffprobe"""
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ],
            capture_output=True,
            text=True
        )

        duration_str = result.stdout.strip()
        if duration_str and duration_str != 'N/A':
            return float(duration_str)

        # Fallback: Decode audio and get duration
        print("⚠️  Duration metadata unavailable, decoding to determine length...")
        result = subprocess.run(
            [
                'ffmpeg',
                '-i', file_path,
                '-f', 'null',
                '-'
            ],
            capture_output=True,
            text=True
        )

        # Parse from stderr: "time=00:01:23.45"
        for line in result.stderr.split('\n'):
            if 'time=' in line:
                time_str = line.split('time=')[1].split()[0]
                # Parse HH:MM:SS.ms
                parts = time_str.split(':')
                if len(parts) == 3:
                    hours = float(parts[0])
                    minutes = float(parts[1])
                    seconds = float(parts[2])
                    return hours * 3600 + minutes * 60 + seconds

        raise ValueError("Could not determine audio duration")

    except Exception as e:
        print(f"❌ Error getting duration: {e}")
        return None


def split_into_chunks(input_file, output_dir, chunk_duration, overlap_duration):
    """
    Split audio file into chunks with overlap

    Returns: List of (chunk_index, start_time, end_time, file_path)
    """
    os.makedirs(output_dir, exist_ok=True)

    # Get total duration
    total_duration = get_audio_duration(input_file)
    if not total_duration:
        print("❌ Cannot split: unknown duration")
        return []

    print(f"📁 Input file: {input_file}")
    print(f"⏱️  Total duration: {total_duration:.2f}s")
    print(f"✂️  Chunk duration: {chunk_duration}s")
    print(f"🔗 Overlap: {overlap_duration}s")
    print()

    chunks = []
    chunk_index = 0
    start_time = 0.0

    while start_time < total_duration:
        # Calculate chunk boundaries
        end_time = min(start_time + chunk_duration, total_duration)

        # Include overlap from previous chunk (except first chunk)
        chunk_start = max(0, start_time - overlap_duration if chunk_index > 0 else 0)
        chunk_end = end_time

        chunk_file = os.path.join(output_dir, f"chunk-{chunk_index:02d}.webm")

        # Extract chunk using ffmpeg
        print(f"🎬 Extracting chunk {chunk_index}: {chunk_start:.1f}s - {chunk_end:.1f}s")

        result = subprocess.run(
            [
                'ffmpeg',
                '-i', input_file,
                '-ss', str(chunk_start),
                '-t', str(chunk_end - chunk_start),
                '-c', 'copy',  # Copy codec (fast)
                '-y',
                chunk_file
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"   ⚠️  Warning: FFmpeg error: {result.stderr[:200]}")

        chunk_size = os.path.getsize(chunk_file) / 1024  # KB
        print(f"   ✓ Created: {chunk_file} ({chunk_size:.1f} KB)")

        chunks.append({
            'index': chunk_index,
            'start_time': chunk_start,
            'end_time': chunk_end,
            'overlap_start': start_time if chunk_index > 0 else chunk_start,
            'overlap_end': start_time + overlap_duration if chunk_index > 0 else chunk_start,
            'file_path': chunk_file
        })

        # Move to next chunk
        start_time += chunk_duration
        chunk_index += 1

        # Safety limit
        if chunk_index > 20:
            print("⚠️  Safety limit: Stopped at 20 chunks")
            break

    print(f"\n✅ Created {len(chunks)} chunks")
    return chunks


def diarize_chunk(chunk, api_url):
    """
    Send chunk to diarization API

    Returns: (segments, detected_speakers, latency, raw_response)
    """
    print(f"\n🔍 Diarizing chunk {chunk['index']}...")

    start = time.time()

    with open(chunk['file_path'], 'rb') as f:
        files = {'audio': (os.path.basename(chunk['file_path']), f, 'audio/webm')}

        # Use default parameters for now
        data = {}

        try:
            response = requests.post(api_url, files=files, data=data, timeout=120)
            response.raise_for_status()

            latency = time.time() - start
            result = response.json()

            print(f"   ✓ Completed in {latency:.2f}s")
            print(f"   📊 Speakers: {result.get('detected_speakers', [])}")
            print(f"   📝 Segments: {len(result.get('segments', []))}")

            return {
                'segments': result.get('segments', []),
                'detected_speakers': result.get('detected_speakers', []),
                'latency': latency,
                'full_response': result
            }

        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {
                'segments': [],
                'detected_speakers': [],
                'latency': time.time() - start,
                'error': str(e)
            }


def calculate_overlap_stats(segments, overlap_start, overlap_end):
    """Calculate speaker statistics in overlap region"""
    overlap_segs = [
        seg for seg in segments
        if seg['start_time'] < overlap_end and seg['end_time'] > overlap_start
    ]

    speaker_stats = {}

    for seg in overlap_segs:
        speaker_id = seg['speaker_id']

        if speaker_id not in speaker_stats:
            speaker_stats[speaker_id] = {
                'speaker_id': speaker_id,
                'word_count': 0,
                'total_duration': 0.0,
                'segment_count': 0,
                'sample_text': ''
            }

        stats = speaker_stats[speaker_id]

        # Calculate actual overlap duration
        seg_start = max(seg['start_time'], overlap_start)
        seg_end = min(seg['end_time'], overlap_end)
        duration = seg_end - seg_start

        stats['word_count'] += len(seg['text'].split())
        stats['total_duration'] += duration
        stats['segment_count'] += 1

        if not stats['sample_text']:
            stats['sample_text'] = seg['text'][:100]

    # Calculate averages
    for stats in speaker_stats.values():
        stats['avg_segment_length'] = (
            stats['total_duration'] / max(stats['segment_count'], 1)
        )

    return speaker_stats


def match_speakers(prev_overlap_stats, curr_overlap_stats):
    """
    Match speakers between chunks based on overlap statistics

    Returns: Map of current_speaker_id -> previous_speaker_id
    """
    # Sort by total duration (most active speaker first)
    sorted_prev = sorted(
        prev_overlap_stats.values(),
        key=lambda x: x['total_duration'],
        reverse=True
    )
    sorted_curr = sorted(
        curr_overlap_stats.values(),
        key=lambda x: x['total_duration'],
        reverse=True
    )

    mapping = {}

    for i in range(min(len(sorted_prev), len(sorted_curr))):
        prev_speaker = sorted_prev[i]
        curr_speaker = sorted_curr[i]

        # Calculate similarity
        max_duration = max(prev_speaker['total_duration'], curr_speaker['total_duration'])
        duration_sim = 1 - abs(prev_speaker['total_duration'] - curr_speaker['total_duration']) / max_duration if max_duration > 0 else 0

        max_words = max(prev_speaker['word_count'], curr_speaker['word_count'])
        word_sim = 1 - abs(prev_speaker['word_count'] - curr_speaker['word_count']) / max_words if max_words > 0 else 0

        max_avg = max(prev_speaker['avg_segment_length'], curr_speaker['avg_segment_length'])
        avg_sim = 1 - abs(prev_speaker['avg_segment_length'] - curr_speaker['avg_segment_length']) / max_avg if max_avg > 0 else 0

        similarity = duration_sim * 0.5 + word_sim * 0.3 + avg_sim * 0.2

        mapping[curr_speaker['speaker_id']] = {
            'matched_to': prev_speaker['speaker_id'],
            'confidence': similarity
        }

        print(f"   🔗 {curr_speaker['speaker_id']} → {prev_speaker['speaker_id']} (confidence: {similarity:.2%})")

    return mapping


def main():
    print("=" * 70)
    print("🧪 CHUNKED DIARIZATION TEST")
    print("=" * 70)
    print()

    # Step 1: Split recording into chunks
    chunks = split_into_chunks(INPUT_FILE, OUTPUT_DIR, CHUNK_DURATION, OVERLAP_DURATION)

    if not chunks:
        print("❌ No chunks created. Exiting.")
        return

    # Step 2: Diarize each chunk
    results = []

    for chunk in chunks:
        result = diarize_chunk(chunk, API_URL)
        result['chunk_index'] = chunk['index']
        result['chunk_start'] = chunk['start_time']
        result['chunk_end'] = chunk['end_time']
        result['overlap_start'] = chunk['overlap_start']
        result['overlap_end'] = chunk['overlap_end']
        results.append(result)

    # Step 3: Analyze overlap regions and match speakers
    print("\n" + "=" * 70)
    print("📊 SPEAKER MATCHING ANALYSIS")
    print("=" * 70)

    speaker_mappings = []

    for i in range(len(results) - 1):
        curr_result = results[i]
        next_result = results[i + 1]

        print(f"\n🔍 Matching Chunk {i} → Chunk {i+1}")
        print(f"   Overlap region: {chunks[i+1]['overlap_start']:.1f}s - {chunks[i+1]['overlap_end']:.1f}s")

        # Calculate overlap stats for both chunks
        curr_overlap_stats = calculate_overlap_stats(
            curr_result['segments'],
            chunks[i+1]['overlap_start'],
            chunks[i+1]['overlap_end']
        )

        next_overlap_stats = calculate_overlap_stats(
            next_result['segments'],
            chunks[i+1]['overlap_start'],
            chunks[i+1]['overlap_end']
        )

        print(f"   Chunk {i} speakers in overlap: {list(curr_overlap_stats.keys())}")
        print(f"   Chunk {i+1} speakers in overlap: {list(next_overlap_stats.keys())}")

        # Match speakers
        mapping = match_speakers(curr_overlap_stats, next_overlap_stats)
        speaker_mappings.append({
            'from_chunk': i,
            'to_chunk': i + 1,
            'mapping': mapping,
            'overlap_stats': {
                'chunk_' + str(i): curr_overlap_stats,
                'chunk_' + str(i + 1): next_overlap_stats
            }
        })

    # Step 4: Save results
    output_file = os.path.join(OUTPUT_DIR, 'analysis_results.json')

    with open(output_file, 'w') as f:
        json.dump({
            'chunks': chunks,
            'diarization_results': results,
            'speaker_mappings': speaker_mappings
        }, f, indent=2)

    print(f"\n💾 Results saved to: {output_file}")

    # Step 5: Summary
    print("\n" + "=" * 70)
    print("📈 SUMMARY")
    print("=" * 70)

    total_latency = sum(r['latency'] for r in results)
    avg_latency = total_latency / len(results) if results else 0

    print(f"Total chunks processed: {len(chunks)}")
    print(f"Total diarization time: {total_latency:.2f}s")
    print(f"Average per chunk: {avg_latency:.2f}s")
    print(f"Parallel potential: ~{max(r['latency'] for r in results):.2f}s (if all chunks parallel)")

    # Check matching success
    successful_matches = sum(
        1 for m in speaker_mappings
        for speaker_map in m['mapping'].values()
        if speaker_map['confidence'] > 0.7
    )
    total_matches = sum(len(m['mapping']) for m in speaker_mappings)

    print(f"\nSpeaker matching:")
    print(f"  Successful (>70% confidence): {successful_matches}/{total_matches}")
    print(f"  Success rate: {successful_matches/total_matches*100:.1f}%" if total_matches > 0 else "  N/A")

    print("\n✅ Test complete!")


if __name__ == '__main__':
    main()
