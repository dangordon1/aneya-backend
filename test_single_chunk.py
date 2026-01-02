#!/usr/bin/env python3
"""Test single chunk to see Sarvam output"""

import requests
import subprocess
import tempfile
import os

# Extract first 30 seconds
INPUT_FILE = "../consultation_recordings/recording-20251221-183930-8d1ecbb2.webm"
API_URL = "http://localhost:8000/api/diarize-chunk"

print("📦 Extracting first 30 seconds...")

with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
    tmp_path = tmp.name

subprocess.run([
    'ffmpeg', '-i', INPUT_FILE, '-ss', '0', '-t', '30',
    '-c', 'copy', tmp_path, '-y'
], capture_output=True)

print(f"✓ Chunk extracted: {os.path.getsize(tmp_path)/1024:.1f} KB")

# Save chunk for review
import shutil
saved_chunk = "test_chunk_30s.webm"
shutil.copy(tmp_path, saved_chunk)
print(f"💾 Saved chunk to: {saved_chunk}")

# Send to backend
with open(tmp_path, 'rb') as f:
    files = {'audio': ('chunk-0.webm', f, 'audio/webm')}
    data = {
        'chunk_index': '0',
        'chunk_start': '0.0',
        'chunk_end': '30.0',
        'language': 'en-IN'
    }

    print("\n📤 Sending to backend...")
    response = requests.post(API_URL, files=files, data=data, timeout=120)

print(f"\n📥 Response status: {response.status_code}")
print(f"📥 Response: {response.json()}")

os.unlink(tmp_path)
