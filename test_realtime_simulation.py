#!/usr/bin/env python
"""
Simulate real-time chunked diarization as the user would experience it

This test mimics the frontend's behavior:
1. Processes chunks every "30 seconds" (simulated)
2. Shows both boxes: raw transcript (left) and diarized transcript (right)
3. Identifies speaker roles after first chunk
4. Matches speakers across chunks using overlap
"""

import subprocess
import os
import time
import json
import requests
from pathlib import Path

INPUT_FILE = "../consultation_recordings/recording-20251221-183930-8d1ecbb2.webm"
CHUNK_DURATION = 30  # seconds
OVERLAP_DURATION = 5  # seconds
OUTPUT_DIR = "./realtime_sim_output"
API_URL = "http://localhost:8000"

# ANSI color codes for terminal
TEAL = '\033[96m'
BLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')

def print_box(title, content, width=80):
    """Print content in a bordered box"""
    print("┌" + "─" * (width - 2) + "┐")
    print("│ " + title.ljust(width - 4) + " │")
    print("├" + "─" * (width - 2) + "┤")
    for line in content:
        # Wrap long lines
        if len(line) > width - 4:
            words = line.split()
            current_line = ""
            for word in words:
                if len(current_line) + len(word) + 1 <= width - 4:
                    current_line += word + " "
                else:
                    print("│ " + current_line.ljust(width - 4) + " │")
                    current_line = word + " "
            if current_line:
                print("│ " + current_line.ljust(width - 4) + " │")
        else:
            print("│ " + line.ljust(width - 4) + " │")
    print("└" + "─" * (width - 2) + "┘")

def get_audio_duration(file_path):
    """Get audio duration using ffmpeg"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-i', file_path, '-f', 'null', '-'],
            capture_output=True,
            text=True,
            timeout=60
        )
        for line in result.stderr.split('\n'):
            if 'time=' in line and 'bitrate=' in line:
                time_str = line.split('time=')[1].split()[0]
                parts = time_str.split(':')
                if len(parts) == 3:
                    hours = float(parts[0])
                    minutes = float(parts[1])
                    seconds = float(parts[2])
                    return hours * 3600 + minutes * 60 + seconds
        return 120
    except Exception as e:
        print(f"⚠️  Duration detection failed: {e}")
        return 120

def create_chunk(input_file, output_file, start_time, duration):
    """Extract audio chunk using ffmpeg"""
    result = subprocess.run(
        ['ffmpeg', '-i', input_file, '-ss', str(start_time), '-t', str(duration),
         '-c', 'copy', '-y', output_file],
        capture_output=True,
        text=True
    )
    return result.returncode == 0

def diarize_chunk(chunk_file, chunk_index, chunk_start, chunk_end, language='en-IN'):
    """Call /api/diarize-chunk endpoint"""
    with open(chunk_file, 'rb') as f:
        files = {'audio': (os.path.basename(chunk_file), f, 'audio/webm')}
        data = {
            'chunk_index': chunk_index,
            'chunk_start': chunk_start,
            'chunk_end': chunk_end,
            'language': language
        }

        response = requests.post(
            f'{API_URL}/api/diarize-chunk',
            files=files,
            data=data,
            timeout=60
        )
        response.raise_for_status()
        return response.json()

def identify_speaker_roles(segments, language='en-IN'):
    """Call /api/identify-speaker-roles endpoint"""
    response = requests.post(
        f'{API_URL}/api/identify-speaker-roles',
        json={'segments': segments, 'language': language},
        timeout=30
    )
    response.raise_for_status()
    return response.json()

def match_speakers(prev_end_stats, curr_start_stats):
    """Match speakers using overlap statistics"""
    if not prev_end_stats or not curr_start_stats:
        return {}

    # Sort by duration
    sorted_prev = sorted(prev_end_stats.items(), key=lambda x: x[1]['duration'], reverse=True)
    sorted_curr = sorted(curr_start_stats.items(), key=lambda x: x[1]['duration'], reverse=True)

    mapping = {}
    for i in range(min(len(sorted_prev), len(sorted_curr))):
        prev_id = sorted_prev[i][0]
        curr_id = sorted_curr[i][0]
        mapping[curr_id] = prev_id

    return mapping

def simulate_realtime():
    """Simulate the real-time recording and diarization experience"""

    print("=" * 80)
    print(f"{BOLD}🎙️  SIMULATING REAL-TIME CHUNKED DIARIZATION{RESET}")
    print("=" * 80)
    print()

    # Check if backend is running
    try:
        response = requests.get(f'{API_URL}/health', timeout=5)
        if response.status_code != 200:
            print(f"{YELLOW}⚠️  Backend health check failed{RESET}")
            return
    except:
        print(f"{YELLOW}❌ Backend not running at {API_URL}{RESET}")
        print(f"{YELLOW}   Start it with: python api.py{RESET}")
        return

    print(f"✅ Backend is running")
    print()

    # Get duration
    total_duration = get_audio_duration(INPUT_FILE)
    print(f"📁 Input: {INPUT_FILE}")
    print(f"⏱️  Duration: {total_duration:.1f}s ({int(total_duration//60)}m {int(total_duration%60)}s)")
    print()

    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # State (simulating frontend state)
    all_diarized_segments = []
    speaker_roles = {}
    chunk_results = []

    # Calculate number of chunks
    num_chunks = int(total_duration / CHUNK_DURATION) + 1

    print(f"📦 Will process {num_chunks} chunks")
    print()
    print("Press Enter to simulate each 30-second interval...")
    input()

    # Process each chunk
    for chunk_idx in range(num_chunks):
        chunk_start = max(0, chunk_idx * CHUNK_DURATION - OVERLAP_DURATION) if chunk_idx > 0 else 0
        chunk_end = min((chunk_idx + 1) * CHUNK_DURATION, total_duration)

        if chunk_end <= chunk_start:
            break

        # Clear screen for real-time effect
        clear_screen()

        print("=" * 80)
        print(f"{BOLD}🎙️  RECORDING IN PROGRESS - {int(chunk_end)}s elapsed{RESET}")
        print("=" * 80)
        print()

        # Extract chunk
        chunk_file = os.path.join(OUTPUT_DIR, f'chunk-{chunk_idx:02d}.webm')
        print(f"⏱️  Time: {chunk_end}s - Processing chunk {chunk_idx}...")

        if not create_chunk(INPUT_FILE, chunk_file, chunk_start, chunk_end - chunk_start):
            print(f"❌ Failed to create chunk {chunk_idx}")
            continue

        print(f"✓ Chunk extracted: {chunk_start:.1f}s - {chunk_end:.1f}s")

        # Diarize chunk
        print(f"🔍 Diarizing chunk {chunk_idx}...")
        start_time = time.time()

        try:
            result = diarize_chunk(chunk_file, chunk_idx, chunk_start, chunk_end)
            latency = time.time() - start_time

            print(f"✅ Diarized in {latency:.1f}s")
            print(f"   Speakers: {result['detected_speakers']}")
            print(f"   Segments: {len(result['segments'])}")

            chunk_results.append(result)

            # First chunk: identify speaker roles
            if chunk_idx == 0:
                print()
                print(f"{TEAL}🔍 Identifying speaker roles...{RESET}")
                role_result = identify_speaker_roles(result['segments'])

                if role_result['success']:
                    speaker_roles = role_result['role_mapping']
                    print(f"{GREEN}✅ Roles identified:{RESET}")
                    for speaker_id, role in speaker_roles.items():
                        print(f"   {speaker_id} → {role}")
            else:
                # Match speakers with previous chunk
                prev_result = chunk_results[chunk_idx - 1]
                mapping = match_speakers(
                    prev_result.get('end_overlap_stats', {}),
                    result.get('start_overlap_stats', {})
                )

                if mapping:
                    print(f"{TEAL}🔀 Speaker matching:{RESET}")
                    for curr_id, prev_id in mapping.items():
                        print(f"   Chunk {chunk_idx}.{curr_id} → Chunk {chunk_idx-1}.{prev_id}")

                    # Remap speaker IDs in segments
                    for seg in result['segments']:
                        if seg['speaker_id'] in mapping:
                            seg['speaker_id'] = mapping[seg['speaker_id']]

            # Apply speaker roles to segments
            for seg in result['segments']:
                seg['speaker_role'] = speaker_roles.get(seg['speaker_id'], seg['speaker_id'])

            # Add to global segments
            all_diarized_segments.extend(result['segments'])
            all_diarized_segments.sort(key=lambda x: x['start_time'])

        except Exception as e:
            print(f"❌ Error: {e}")
            continue

        print()
        print("=" * 80)

        # Display TWO BOXES
        left_box_content = []
        right_box_content = []

        # LEFT BOX: Raw transcript (simulated - we'll use the diarized text without labels)
        left_box_content.append("[This would show real-time transcript]")
        left_box_content.append("")
        for seg in all_diarized_segments[:5]:  # Show first 5
            left_box_content.append(seg['text'])
        if len(all_diarized_segments) > 5:
            left_box_content.append(f"... and {len(all_diarized_segments) - 5} more segments")

        # RIGHT BOX: Diarized transcript with speaker labels
        if not all_diarized_segments:
            right_box_content.append("Waiting for first chunk...")
        else:
            for seg in all_diarized_segments[:10]:  # Show first 10
                role = seg.get('speaker_role', seg['speaker_id'])
                color = TEAL if role == 'Doctor' else BLUE if role == 'Patient' else RESET
                right_box_content.append(f"{color}{role}:{RESET} {seg['text'][:60]}")
            if len(all_diarized_segments) > 10:
                right_box_content.append(f"... and {len(all_diarized_segments) - 10} more segments")

        # Print boxes side by side (simplified for terminal)
        print()
        print_box(f"{BOLD}📝 Real-time Transcript{RESET}", left_box_content, 80)
        print()
        print_box(f"{BOLD}👥 Speaker-Labeled Transcript ({len(all_diarized_segments)} segments){RESET}", right_box_content, 80)

        print()
        if chunk_idx < num_chunks - 1:
            print(f"{YELLOW}⏳ Press Enter to continue to next chunk...{RESET}")
            input()

    # Final summary
    print()
    print("=" * 80)
    print(f"{GREEN}{BOLD}✅ SIMULATION COMPLETE{RESET}")
    print("=" * 80)
    print()
    print(f"Total chunks processed: {len(chunk_results)}")
    print(f"Total segments: {len(all_diarized_segments)}")
    print(f"Speaker roles: {speaker_roles}")
    print()

    # Save final transcript
    output_file = os.path.join(OUTPUT_DIR, 'final_transcript.txt')
    with open(output_file, 'w') as f:
        for seg in all_diarized_segments:
            role = seg.get('speaker_role', seg['speaker_id'])
            f.write(f"{seg['start_time']:6.1f}s  {role:12s} {seg['text']}\n")

    print(f"💾 Final transcript saved to: {output_file}")

if __name__ == '__main__':
    simulate_realtime()
