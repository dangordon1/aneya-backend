#!/usr/bin/env python
"""
Show a single snapshot of the two-box UI after processing all chunks
"""

import json
import os

# ANSI color codes
TEAL = '\033[96m'
BLUE = '\033[94m'
GREEN = '\033[92m'
BOLD = '\033[1m'
RESET = '\033[0m'

# Load results
with open('./chunked_test_output/full_test_results.json') as f:
    data = json.load(f)

speaker_roles = data.get('speaker_roles', {})
merged_segments = data['merged_segments']

# Build cumulative text
cumulative_text = " ".join([seg['text'] for seg in merged_segments])

print()
print("=" * 120)
print(f"{BOLD}🎙️  RECORDING IN PROGRESS - 130s elapsed{RESET}")
print("=" * 120)
print()

# TWO COLUMNS
left_width = 58
right_width = 58

# Header
print("┌" + "─" * left_width + "┬" + "─" * right_width + "┐")
print(f"│{BOLD} 📝 Real-time Transcript{RESET}".ljust(left_width + 19) + f"│{BOLD} 👥 Speaker-Labeled Transcript{RESET}".ljust(right_width + 19) + "│")
print("│" + " " * left_width + "│" + " " * right_width + "│")
print(f"│ Live".ljust(left_width + 1) + f"│ {GREEN}{len(merged_segments)} segments{RESET}".ljust(right_width + 10) + "│")
print("├" + "─" * left_width + "┼" + "─" * right_width + "┤")

# LEFT: Raw text (wrapped)
left_lines = []
words = cumulative_text.split()
current_line = ""
for word in words[:100]:  # First 100 words
    if len(current_line) + len(word) + 1 <= left_width - 4:
        current_line += word + " "
    else:
        left_lines.append(current_line.strip())
        current_line = word + " "
if current_line:
    left_lines.append(current_line.strip())
if len(words) > 100:
    left_lines.append("...")

# RIGHT: Diarized segments
right_lines = []
for seg in merged_segments[:10]:
    role = seg.get('speaker_role', seg['speaker_id'])
    text = seg['text']

    if role == 'Doctor':
        badge = f"{TEAL}[Doctor]{RESET}"
    elif role == 'Patient':
        badge = f"{BLUE}[Patient]{RESET}"
    else:
        badge = f"[{role}]"

    # Wrap text
    words = text.split()
    current_line = f"{badge} "
    for word in words:
        if len(current_line) + len(word) + 1 <= right_width - 4:
            current_line += word + " "
        else:
            right_lines.append(current_line.strip())
            current_line = "  " + word + " "
    if current_line.strip():
        right_lines.append(current_line.strip())

    right_lines.append("")

if len(merged_segments) > 10:
    right_lines.append(f"... and {len(merged_segments) - 10} more segments")

# Print side by side
max_lines = 15
for i in range(max_lines):
    left_line = left_lines[i] if i < len(left_lines) else ""
    right_line = right_lines[i] if i < len(right_lines) else ""

    # Clean for length calc
    left_clean = left_line.replace(TEAL, '').replace(BLUE, '').replace(GREEN, '').replace(RESET, '').replace(BOLD, '')
    right_clean = right_line.replace(TEAL, '').replace(BLUE, '').replace(GREEN, '').replace(RESET, '').replace(BOLD, '')

    print("│ " + left_line + " " * (left_width - len(left_clean) - 2) +
          "│ " + right_line + " " * (right_width - len(right_clean) - 2) + "│")

print("└" + "─" * left_width + "┴" + "─" * right_width + "┘")

# Status
print()
print(f"{BOLD}Chunk Processing Status:{RESET}")
print(f"{GREEN}[✓ Chunk 1] [✓ Chunk 2] [✓ Chunk 3] [✓ Chunk 4] [✓ Chunk 5]{RESET}")
print()

print("=" * 120)
print(f"{GREEN}{BOLD}✅ ALL CHUNKS PROCESSED{RESET}")
print("=" * 120)
print()
print(f"📊 Final Statistics:")
print(f"   Duration: 130s (2m 10s)")
print(f"   Total chunks: 5")
print(f"   Total segments: {len(merged_segments)}")
print()
print(f"Speaker roles identified:")
for speaker_id, role in speaker_roles.items():
    color = TEAL if role == 'Doctor' else BLUE
    print(f"   • {color}{role}{RESET}")
print()
