#!/usr/bin/env python
"""
Simple test: Create 2 chunks with overlap and test speaker matching
"""

import subprocess
import os
import time
import json
import requests

INPUT_FILE = "../consultation_recordings/recording-20251221-183930-8d1ecbb2.webm"
OUTPUT_DIR = "./chunked_test_output"
API_URL = "http://localhost:8000/api/diarize"

# Just create 2 chunks: 0-30s and 20-50s (10s overlap from 20-30s)
chunks = [
    {'index': 0, 'start': 0, 'duration': 30, 'overlap_start': 20, 'overlap_end': 30},
    {'index': 1, 'start': 20, 'duration': 30, 'overlap_start': 20, 'overlap_end': 30},
]

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 70)
print("🧪 SIMPLE CHUNKED DIARIZATION TEST (2 chunks with overlap)")
print("=" * 70)
print()

# Create chunks
for chunk in chunks:
    chunk_file = os.path.join(OUTPUT_DIR, f"chunk-{chunk['index']:02d}.webm")

    print(f"✂️  Creating chunk {chunk['index']}: {chunk['start']}s - {chunk['start']+chunk['duration']}s")

    result = subprocess.run(
        [
            'ffmpeg',
            '-ss', str(chunk['start']),
            '-i', INPUT_FILE,
            '-t', str(chunk['duration']),
            '-c', 'copy',
            '-y',
            chunk_file
        ],
        capture_output=True,
        text=True
    )

    if os.path.exists(chunk_file):
        chunk_size = os.path.getsize(chunk_file) / 1024
        print(f"   ✓ Created: {chunk_file} ({chunk_size:.1f} KB)")
        chunk['file_path'] = chunk_file
    else:
        print(f"   ❌ Failed to create chunk {chunk['index']}")
        print(f"   Error: {result.stderr[:300]}")

print()

# Diarize chunks
results = []

for chunk in chunks:
    if 'file_path' not in chunk:
        continue

    print(f"🔍 Diarizing chunk {chunk['index']}...")

    start = time.time()

    with open(chunk['file_path'], 'rb') as f:
        files = {'audio': (os.path.basename(chunk['file_path']), f, 'audio/webm')}

        try:
            response = requests.post(API_URL, files=files, timeout=120)
            response.raise_for_status()

            latency = time.time() - start
            result = response.json()

            print(f"   ✓ Completed in {latency:.2f}s")
            print(f"   📊 Detected speakers: {result.get('detected_speakers', [])}")
            print(f"   📝 Number of segments: {len(result.get('segments', []))}")

            # Show overlap region stats
            overlap_start = chunk['overlap_start']
            overlap_end = chunk['overlap_end']

            overlap_segs = [
                seg for seg in result.get('segments', [])
                if seg['start_time'] < overlap_end and seg['end_time'] > overlap_start
            ]

            speaker_stats = {}
            for seg in overlap_segs:
                speaker_id = seg['speaker_id']
                if speaker_id not in speaker_stats:
                    speaker_stats[speaker_id] = {'duration': 0, 'words': 0, 'segments': 0}

                seg_start = max(seg['start_time'], overlap_start)
                seg_end = min(seg['end_time'], overlap_end)
                duration = seg_end - seg_start

                speaker_stats[speaker_id]['duration'] += duration
                speaker_stats[speaker_id]['words'] += len(seg['text'].split())
                speaker_stats[speaker_id]['segments'] += 1

            print(f"   📍 Overlap region ({overlap_start}-{overlap_end}s):")
            for speaker_id, stats in speaker_stats.items():
                print(f"      {speaker_id}: {stats['duration']:.1f}s, {stats['words']} words, {stats['segments']} segments")

            results.append({
                'chunk_index': chunk['index'],
                'segments': result.get('segments', []),
                'detected_speakers': result.get('detected_speakers', []),
                'overlap_stats': speaker_stats,
                'latency': latency
            })

        except Exception as e:
            print(f"   ❌ Error: {e}")

print()

# Match speakers
if len(results) == 2:
    print("=" * 70)
    print("🔗 SPEAKER MATCHING")
    print("=" * 70)
    print()

    chunk0_overlap = results[0]['overlap_stats']
    chunk1_overlap = results[1]['overlap_stats']

    print("Chunk 0 speakers in overlap (20-30s):")
    for speaker, stats in chunk0_overlap.items():
        print(f"  {speaker}: {stats['duration']:.1f}s, {stats['words']} words")

    print("\nChunk 1 speakers in overlap (20-30s):")
    for speaker, stats in chunk1_overlap.items():
        print(f"  {speaker}: {stats['duration']:.1f}s, {stats['words']} words")

    # Simple matching by duration rank
    sorted_chunk0 = sorted(chunk0_overlap.items(), key=lambda x: x[1]['duration'], reverse=True)
    sorted_chunk1 = sorted(chunk1_overlap.items(), key=lambda x: x[1]['duration'], reverse=True)

    print("\n🎯 Proposed mapping (by speaking duration):")
    for i in range(min(len(sorted_chunk0), len(sorted_chunk1))):
        speaker0_id, stats0 = sorted_chunk0[i]
        speaker1_id, stats1 = sorted_chunk1[i]

        # Calculate similarity
        max_duration = max(stats0['duration'], stats1['duration'])
        duration_sim = 1 - abs(stats0['duration'] - stats1['duration']) / max_duration if max_duration > 0 else 0

        max_words = max(stats0['words'], stats1['words'])
        word_sim = 1 - abs(stats0['words'] - stats1['words']) / max_words if max_words > 0 else 0

        confidence = duration_sim * 0.7 + word_sim * 0.3

        print(f"  Chunk1:{speaker1_id} → Chunk0:{speaker0_id} (confidence: {confidence:.2%})")

print("\n✅ Test complete!")

# Save results
output_file = os.path.join(OUTPUT_DIR, 'simple_test_results.json')
with open(output_file, 'w') as f:
    json.dump({
        'chunks': chunks,
        'results': results
    }, f, indent=2)

print(f"💾 Results saved to: {output_file}")
