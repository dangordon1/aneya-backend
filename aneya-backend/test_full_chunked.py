#!/usr/bin/env python
"""
Full chunked diarization test with 5-second overlap
Processes the entire recording file
"""

import subprocess
import os
import time
import json
import requests
from pathlib import Path

INPUT_FILE = "../consultation_recordings/recording-20251221-183930-8d1ecbb2.webm"
CHUNK_DURATION = 30  # seconds
OVERLAP_DURATION = 5  # seconds (reduced from 10)
OUTPUT_DIR = "./chunked_test_output"
API_URL = "http://localhost:8000/api/diarize"

def get_audio_duration_simple(file_path):
    """Get approximate duration by decoding with ffmpeg"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-i', file_path, '-f', 'null', '-'],
            capture_output=True,
            text=True,
            timeout=60
        )

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
                    print(f"⏱️  Detected duration: {duration:.1f}s ({int(duration//60)}m {int(duration%60)}s)")
                    return duration

        # Fallback: assume reasonable length
        print("⚠️  Could not detect exact duration, estimating from file size...")
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        # Rough estimate: ~1MB per minute for webm
        estimated_duration = file_size_mb * 60
        print(f"⏱️  Estimated duration: {estimated_duration:.1f}s ({int(estimated_duration//60)}m {int(estimated_duration%60)}s)")
        return estimated_duration

    except Exception as e:
        print(f"❌ Error getting duration: {e}")
        return 120  # Default to 2 minutes

def create_chunks(input_file, output_dir, chunk_duration, overlap_duration):
    """Create all chunks from the full recording"""
    os.makedirs(output_dir, exist_ok=True)

    total_duration = get_audio_duration_simple(input_file)

    print()
    print("=" * 80)
    print("CHUNK CREATION")
    print("=" * 80)
    print(f"📁 Input: {input_file}")
    print(f"⏱️  Duration: {total_duration:.1f}s")
    print(f"✂️  Chunk size: {chunk_duration}s")
    print(f"🔗 Overlap: {overlap_duration}s")
    print()

    chunks = []
    chunk_index = 0
    current_time = 0

    while current_time < total_duration:
        # Calculate chunk boundaries
        chunk_start = max(0, current_time - overlap_duration) if chunk_index > 0 else 0
        chunk_end = min(current_time + chunk_duration, total_duration)

        chunk_file = os.path.join(output_dir, f"chunk-{chunk_index:02d}.webm")

        print(f"Creating chunk {chunk_index}: {chunk_start:.1f}s - {chunk_end:.1f}s")

        # Extract chunk
        result = subprocess.run(
            [
                'ffmpeg',
                '-i', input_file,
                '-ss', str(chunk_start),
                '-t', str(chunk_end - chunk_start),
                '-c', 'copy',
                '-y',
                chunk_file
            ],
            capture_output=True,
            text=True
        )

        if os.path.exists(chunk_file):
            chunk_size = os.path.getsize(chunk_file) / 1024
            print(f"  ✓ {chunk_file} ({chunk_size:.1f} KB)")

            # Overlap region: the shared time between this chunk and the previous chunk
            # For chunk N (starting at chunk_start), the overlap is the first OVERLAP_DURATION seconds
            # which corresponds to the last OVERLAP_DURATION seconds of chunk N-1
            if chunk_index > 0:
                overlap_start_val = chunk_start
                overlap_end_val = chunk_start + overlap_duration
            else:
                overlap_start_val = chunk_start
                overlap_end_val = chunk_start  # No overlap for first chunk

            chunks.append({
                'index': chunk_index,
                'start_time': chunk_start,
                'end_time': chunk_end,
                'overlap_start': overlap_start_val,
                'overlap_end': overlap_end_val,
                'file_path': chunk_file
            })
        else:
            print(f"  ❌ Failed: {result.stderr[:200]}")

        # Move to next chunk
        current_time += chunk_duration
        chunk_index += 1

        # Safety limit
        if chunk_index > 50:
            print("⚠️  Safety limit: 50 chunks maximum")
            break

    print(f"\n✅ Created {len(chunks)} chunks")
    return chunks

def diarize_chunk(chunk, api_url):
    """Send chunk to diarization API"""
    print(f"\n🔍 Diarizing chunk {chunk['index']} ({chunk['start_time']:.1f}s-{chunk['end_time']:.1f}s)...")

    start = time.time()

    with open(chunk['file_path'], 'rb') as f:
        files = {'audio': (os.path.basename(chunk['file_path']), f, 'audio/webm')}

        try:
            response = requests.post(api_url, files=files, timeout=120)
            response.raise_for_status()

            latency = time.time() - start
            result = response.json()

            segments = result.get('segments', [])
            speakers = result.get('detected_speakers', [])

            print(f"  ✓ {latency:.1f}s | Speakers: {speakers} | Segments: {len(segments)}")

            # Convert segment times to absolute (add chunk start time)
            chunk_start_time = chunk['start_time']
            for seg in segments:
                seg['start_time'] += chunk_start_time
                seg['end_time'] += chunk_start_time

            # Calculate overlap stats for BOTH start and end of this chunk
            # Start overlap: first OVERLAP_DURATION seconds (shared with previous chunk)
            # End overlap: last OVERLAP_DURATION seconds (shared with next chunk)

            start_overlap_stats = {}
            end_overlap_stats = {}

            # Start overlap (for matching with previous chunk)
            if chunk['index'] > 0:
                start_overlap_start = chunk['start_time']
                start_overlap_end = chunk['start_time'] + OVERLAP_DURATION

                start_overlap_segs = [
                    seg for seg in segments
                    if seg['start_time'] < start_overlap_end and seg['end_time'] > start_overlap_start
                ]

                for seg in start_overlap_segs:
                    speaker_id = seg['speaker_id']
                    if speaker_id not in start_overlap_stats:
                        start_overlap_stats[speaker_id] = {
                            'speaker_id': speaker_id,
                            'duration': 0,
                            'words': 0,
                            'segments': 0
                        }

                    seg_start = max(seg['start_time'], start_overlap_start)
                    seg_end = min(seg['end_time'], start_overlap_end)
                    duration = seg_end - seg_start

                    start_overlap_stats[speaker_id]['duration'] += duration
                    start_overlap_stats[speaker_id]['words'] += len(seg['text'].split())
                    start_overlap_stats[speaker_id]['segments'] += 1

                if start_overlap_stats:
                    print(f"  📍 Start overlap ({start_overlap_start:.1f}-{start_overlap_end:.1f}s): ", end='')
                    print(', '.join([f"{sid}={st['duration']:.1f}s" for sid, st in start_overlap_stats.items()]))

            # End overlap (for matching with next chunk)
            end_overlap_start = chunk['end_time'] - OVERLAP_DURATION
            end_overlap_end = chunk['end_time']

            end_overlap_segs = [
                seg for seg in segments
                if seg['start_time'] < end_overlap_end and seg['end_time'] > end_overlap_start
            ]

            for seg in end_overlap_segs:
                speaker_id = seg['speaker_id']
                if speaker_id not in end_overlap_stats:
                    end_overlap_stats[speaker_id] = {
                        'speaker_id': speaker_id,
                        'duration': 0,
                        'words': 0,
                        'segments': 0
                    }

                seg_start = max(seg['start_time'], end_overlap_start)
                seg_end = min(seg['end_time'], end_overlap_end)
                duration = seg_end - seg_start

                end_overlap_stats[speaker_id]['duration'] += duration
                end_overlap_stats[speaker_id]['words'] += len(seg['text'].split())
                end_overlap_stats[speaker_id]['segments'] += 1

            if end_overlap_stats:
                print(f"  📍 End overlap ({end_overlap_start:.1f}-{end_overlap_end:.1f}s): ", end='')
                print(', '.join([f"{sid}={st['duration']:.1f}s" for sid, st in end_overlap_stats.items()]))

            return {
                'chunk_index': chunk['index'],
                'segments': segments,
                'detected_speakers': speakers,
                'start_overlap_stats': start_overlap_stats,
                'end_overlap_stats': end_overlap_stats,
                'latency': latency
            }

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return {
                'chunk_index': chunk['index'],
                'segments': [],
                'detected_speakers': [],
                'start_overlap_stats': {},
                'end_overlap_stats': {},
                'latency': time.time() - start,
                'error': str(e)
            }

def identify_speaker_roles(segments):
    """Call API to identify which speaker is doctor vs patient"""
    try:
        response = requests.post(
            'http://localhost:8000/api/identify-speaker-roles',
            json={'segments': segments, 'language': 'en-IN'},
            timeout=30
        )
        response.raise_for_status()

        result = response.json()

        if result['success']:
            print(f"  ✓ Identified in {result['latency_seconds']}s using {result['model']}")
            return result['role_mapping']
        else:
            print(f"  ⚠️  Fallback to default labels")
            return result.get('role_mapping', {})

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {}


def match_speakers(prev_stats, curr_stats):
    """Match speakers between chunks based on overlap statistics"""
    if not prev_stats or not curr_stats:
        return {}

    # Sort by duration
    sorted_prev = sorted(prev_stats.items(), key=lambda x: x[1]['duration'], reverse=True)
    sorted_curr = sorted(curr_stats.items(), key=lambda x: x[1]['duration'], reverse=True)

    mapping = {}

    for i in range(min(len(sorted_prev), len(sorted_curr))):
        prev_id, prev_data = sorted_prev[i]
        curr_id, curr_data = sorted_curr[i]

        # Calculate similarity
        max_duration = max(prev_data['duration'], curr_data['duration'])
        duration_sim = 1 - abs(prev_data['duration'] - curr_data['duration']) / max_duration if max_duration > 0 else 0

        max_words = max(prev_data['words'], curr_data['words'])
        word_sim = 1 - abs(prev_data['words'] - curr_data['words']) / max_words if max_words > 0 else 0

        confidence = duration_sim * 0.7 + word_sim * 0.3

        mapping[curr_id] = {
            'maps_to': prev_id,
            'confidence': confidence
        }

    return mapping

def main():
    print("=" * 80)
    print("🧪 FULL CHUNKED DIARIZATION TEST (5-second overlap)")
    print("=" * 80)
    print()

    # Step 1: Create all chunks
    chunks = create_chunks(INPUT_FILE, OUTPUT_DIR, CHUNK_DURATION, OVERLAP_DURATION)

    if not chunks:
        print("❌ No chunks created")
        return

    # Step 2: Diarize all chunks
    print()
    print("=" * 80)
    print("DIARIZATION")
    print("=" * 80)

    results = []
    speaker_roles = {}  # Maps speaker IDs to roles (Doctor/Patient)
    total_start = time.time()

    for chunk in chunks:
        result = diarize_chunk(chunk, API_URL)
        results.append(result)

        # After first chunk, identify speaker roles
        if chunk['index'] == 0 and result['segments']:
            print()
            print("🔍 Identifying speaker roles...")
            speaker_roles = identify_speaker_roles(result['segments'])
            if speaker_roles:
                print(f"✅ Roles: {speaker_roles}")

    total_time = time.time() - total_start

    # Step 3: Match speakers across chunks
    print()
    print("=" * 80)
    print("SPEAKER MATCHING")
    print("=" * 80)
    print()

    speaker_mappings = []
    global_speaker_map = {}  # Maps all chunk speaker IDs to canonical (Chunk 0) IDs

    # Initialize with Chunk 0 speakers
    if results[0]['detected_speakers']:
        for speaker_id in results[0]['detected_speakers']:
            global_speaker_map[f"0_{speaker_id}"] = speaker_id

    for i in range(len(results) - 1):
        prev_result = results[i]
        curr_result = results[i + 1]

        print(f"Chunk {i} → Chunk {i+1}:")

        # Match using the SHARED audio region:
        # - Previous chunk's END overlap (last 5 seconds)
        # - Current chunk's START overlap (first 5 seconds)
        # These are the SAME audio, so speakers should match
        mapping = match_speakers(
            prev_result['end_overlap_stats'],
            curr_result['start_overlap_stats']
        )

        if mapping:
            for curr_id, match_info in mapping.items():
                prev_id = match_info['maps_to']
                confidence = match_info['confidence']

                # Get canonical ID from previous chunk
                prev_key = f"{i}_{prev_id}"
                canonical_id = global_speaker_map.get(prev_key, prev_id)

                # Map current chunk's speaker to canonical
                curr_key = f"{i+1}_{curr_id}"
                global_speaker_map[curr_key] = canonical_id

                status = "✓" if confidence > 0.7 else "⚠️"
                print(f"  {status} {curr_id} → {canonical_id} ({confidence:.1%})")

            speaker_mappings.append({
                'from_chunk': i,
                'to_chunk': i + 1,
                'mapping': mapping
            })
        else:
            print(f"  ⚠️  No overlap data to match")

    # Step 4: Build merged transcript
    print()
    print("=" * 80)
    print("MERGED TRANSCRIPT")
    print("=" * 80)
    print()

    all_segments = []

    for result in results:
        chunk_idx = result['chunk_index']

        for seg in result['segments']:
            # Remap speaker ID to canonical
            orig_speaker = seg['speaker_id']
            chunk_speaker_key = f"{chunk_idx}_{orig_speaker}"
            canonical_speaker = global_speaker_map.get(chunk_speaker_key, orig_speaker)

            # Get speaker role (Doctor/Patient) if available
            speaker_role = speaker_roles.get(canonical_speaker, canonical_speaker)

            all_segments.append({
                'speaker_id': canonical_speaker,
                'speaker_role': speaker_role,
                'text': seg['text'],
                'start_time': seg['start_time'],
                'end_time': seg['end_time'],
                'chunk_index': chunk_idx
            })

    # Sort by time
    all_segments.sort(key=lambda x: x['start_time'])

    # Print transcript (with roles if available)
    for i, seg in enumerate(all_segments[:20]):  # First 20 segments
        speaker_label = seg.get('speaker_role', seg['speaker_id'])
        print(f"{seg['start_time']:6.1f}s  {speaker_label:12s} {seg['text'][:60]}")

    if len(all_segments) > 20:
        print(f"... and {len(all_segments) - 20} more segments")

    # Step 5: Statistics
    print()
    print("=" * 80)
    print("STATISTICS")
    print("=" * 80)
    print()

    successful_chunks = len([r for r in results if 'error' not in r])
    failed_chunks = len([r for r in results if 'error' in r])

    avg_latency = sum(r['latency'] for r in results) / len(results) if results else 0
    max_latency = max(r['latency'] for r in results) if results else 0

    print(f"Total chunks: {len(chunks)}")
    print(f"Successful: {successful_chunks}")
    print(f"Failed: {failed_chunks}")
    print()
    print(f"Total diarization time: {total_time:.1f}s ({total_time/60:.1f}m)")
    print(f"Average per chunk: {avg_latency:.1f}s")
    print(f"Max chunk time: {max_latency:.1f}s")
    print(f"Parallel potential: ~{max_latency:.1f}s (if all parallel)")
    print()
    print(f"Total segments: {len(all_segments)}")

    # Detect unique speakers
    unique_speakers = set(seg['speaker_id'] for seg in all_segments)
    print(f"Unique speakers: {sorted(unique_speakers)}")

    # Matching success rate
    if speaker_mappings:
        total_matches = sum(len(m['mapping']) for m in speaker_mappings)
        confident_matches = sum(
            1 for m in speaker_mappings
            for match in m['mapping'].values()
            if match['confidence'] > 0.7
        )
        print(f"\nSpeaker matching:")
        print(f"  Total matches: {total_matches}")
        print(f"  Confident (>70%): {confident_matches} ({confident_matches/total_matches*100:.1f}%)" if total_matches > 0 else "  N/A")

    # Step 6: Save results
    output_file = os.path.join(OUTPUT_DIR, 'full_test_results.json')

    with open(output_file, 'w') as f:
        json.dump({
            'config': {
                'chunk_duration': CHUNK_DURATION,
                'overlap_duration': OVERLAP_DURATION,
                'input_file': INPUT_FILE
            },
            'chunks': chunks,
            'diarization_results': results,
            'speaker_mappings': speaker_mappings,
            'global_speaker_map': global_speaker_map,
            'speaker_roles': speaker_roles,
            'merged_segments': all_segments
        }, f, indent=2)

    print(f"\n💾 Results saved to: {output_file}")

    # Save transcript (with roles)
    transcript_file = os.path.join(OUTPUT_DIR, 'merged_transcript.txt')
    with open(transcript_file, 'w') as f:
        for seg in all_segments:
            speaker_label = seg.get('speaker_role', seg['speaker_id'])
            f.write(f"{seg['start_time']:6.1f}s  {speaker_label:12s} {seg['text']}\n")

    print(f"📝 Transcript saved to: {transcript_file}")

    print("\n✅ Test complete!")

if __name__ == '__main__':
    main()
