#!/usr/bin/env python
"""
Demonstrate the two-box UI using pre-processed results
Shows what the user would see during recording
"""

import json
import time
import os

# ANSI color codes
TEAL = '\033[96m'
BLUE = '\033[94m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')

def print_two_boxes(raw_text, diarized_segments, chunk_num, total_chunks, is_identifying=False):
    """Print the two-box UI as it would appear in the browser"""

    print("=" * 120)
    print(f"{BOLD}🎙️  RECORDING IN PROGRESS - {chunk_num * 30}s elapsed{RESET}")
    print("=" * 120)
    print()

    # TWO COLUMNS
    left_width = 58
    right_width = 58

    # Header row
    print("┌" + "─" * left_width + "┬" + "─" * right_width + "┐")
    print("│" + f"{BOLD} 📝 Real-time Transcript{RESET}".ljust(left_width + 10) + "│" +
          f"{BOLD} 👥 Speaker-Labeled Transcript{RESET}".ljust(right_width + 10) + "│")
    print("│" + " " * left_width + "│" + " " * right_width + "│")
    print("│" + f" {YELLOW}Live{RESET}".ljust(left_width + 10) + "│" +
          f" {GREEN}{len(diarized_segments)} segments{RESET}".ljust(right_width + 10) + "│")
    print("├" + "─" * left_width + "┼" + "─" * right_width + "┤")

    # Content area
    max_lines = 15

    # LEFT BOX: Raw text (simulated real-time transcript)
    left_lines = []
    if raw_text:
        # Wrap text to fit column
        words = raw_text.split()
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= left_width - 4:
                current_line += word + " "
            else:
                left_lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            left_lines.append(current_line.strip())
    else:
        left_lines.append("Listening...")

    # RIGHT BOX: Diarized segments
    right_lines = []

    if is_identifying:
        right_lines.append(f"{TEAL}🔍 Analyzing conversation...{RESET}")
        right_lines.append("")
        right_lines.append("Identifying doctor and patient...")
    elif not diarized_segments:
        right_lines.append("Waiting for first chunk...")
        right_lines.append("")
        right_lines.append(f"Processing will start after {YELLOW}30 seconds{RESET}")
    else:
        for seg in diarized_segments[:12]:  # Show first 12 segments
            role = seg.get('speaker_role', seg['speaker_id'])
            text = seg['text']

            # Color based on role
            if role == 'Doctor':
                color = TEAL
                badge_bg = f"{TEAL}[Doctor]{RESET}"
            elif role == 'Patient':
                color = BLUE
                badge_bg = f"{BLUE}[Patient]{RESET}"
            else:
                color = RESET
                badge_bg = f"[{role}]"

            # Wrap text
            words = text.split()
            current_line = f"{badge_bg} "
            for word in words:
                if len(current_line) + len(word) + 1 <= right_width - 4:
                    current_line += word + " "
                else:
                    right_lines.append(current_line.strip())
                    current_line = "  " + word + " "
            if current_line.strip():
                right_lines.append(current_line.strip())

            right_lines.append("")  # Spacing between segments

        if len(diarized_segments) > 12:
            right_lines.append(f"... and {len(diarized_segments) - 12} more")

    # Print both columns side by side
    for i in range(max_lines):
        left_line = left_lines[i] if i < len(left_lines) else ""
        right_line = right_lines[i] if i < len(right_lines) else ""

        # Remove ANSI codes for length calculation
        left_clean = left_line.replace(TEAL, '').replace(BLUE, '').replace(GREEN, '').replace(YELLOW, '').replace(RESET, '').replace(BOLD, '')
        right_clean = right_line.replace(TEAL, '').replace(BLUE, '').replace(GREEN, '').replace(YELLOW, '').replace(RESET, '').replace(BOLD, '')

        print("│ " + left_line + " " * (left_width - len(left_clean) - 2) +
              "│ " + right_line + " " * (right_width - len(right_clean) - 2) + "│")

    print("└" + "─" * left_width + "┴" + "─" * right_width + "┘")

    # Chunk status indicator
    print()
    print(f"{BOLD}Chunk Processing Status:{RESET}")
    status_line = ""
    for i in range(total_chunks):
        if i < chunk_num:
            status_line += f"{GREEN}[✓ Chunk {i+1}]{RESET} "
        elif i == chunk_num:
            status_line += f"{YELLOW}[⏳ Chunk {i+1}]{RESET} "
        else:
            status_line += f"[  Chunk {i+1}] "
    print(status_line)
    print()

def demo():
    """Run the demonstration"""

    # Load pre-processed results
    results_file = './chunked_test_output/full_test_results.json'

    if not os.path.exists(results_file):
        print(f"❌ Results file not found: {results_file}")
        print(f"   Run test_full_chunked.py first to generate test data")
        return

    with open(results_file) as f:
        data = json.load(f)

    chunks = data['chunks']
    results = data['diarization_results']
    speaker_roles = data.get('speaker_roles', {})
    merged_segments = data['merged_segments']

    print()
    print(f"{BOLD}{GREEN}Demonstration: Real-time Chunked Diarization UI{RESET}")
    print()
    print("This shows what the user sees during recording.")
    print("Press Enter to advance through each chunk...")
    print()
    input()

    # Simulate processing chunks
    cumulative_segments = []
    cumulative_text = ""

    for i, chunk_result in enumerate(results):
        clear_screen()

        # Get segments for this chunk
        chunk_segments = chunk_result['segments']

        # Add speaker roles
        for seg in chunk_segments:
            seg['speaker_role'] = speaker_roles.get(seg['speaker_id'], seg['speaker_id'])

        cumulative_segments.extend(chunk_segments)

        # Build raw text
        cumulative_text = " ".join([seg['text'] for seg in cumulative_segments])

        # Show identifying state for first chunk
        is_identifying = (i == 0 and len(cumulative_segments) > 0 and not speaker_roles)

        # Display
        print_two_boxes(
            cumulative_text,
            cumulative_segments,
            i + 1,
            len(results),
            is_identifying=is_identifying
        )

        # After first chunk, show speaker identification
        if i == 0 and speaker_roles:
            print()
            print(f"{GREEN}✅ Speakers identified:{RESET}")
            for speaker_id, role in speaker_roles.items():
                color = TEAL if role == 'Doctor' else BLUE
                print(f"   {speaker_id} → {color}{role}{RESET}")

        print()
        if i < len(results) - 1:
            input(f"{YELLOW}Press Enter to process next chunk...{RESET}")
        time.sleep(0.5)

    # Final state
    clear_screen()
    print_two_boxes(cumulative_text, cumulative_segments, len(results), len(results))

    print()
    print("=" * 120)
    print(f"{GREEN}{BOLD}✅ RECORDING COMPLETE{RESET}")
    print("=" * 120)
    print()
    print(f"📊 Statistics:")
    print(f"   Total duration: {int(chunks[-1]['end_time'])}s")
    print(f"   Total chunks: {len(results)}")
    print(f"   Total segments: {len(merged_segments)}")
    print(f"   Speakers detected: {len(speaker_roles)}")
    print()
    print(f"Speaker roles:")
    for speaker_id, role in speaker_roles.items():
        color = TEAL if role == 'Doctor' else BLUE
        print(f"   • {color}{role}{RESET}")
    print()

if __name__ == '__main__':
    demo()
