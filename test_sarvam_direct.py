#!/usr/bin/env python
"""Test Sarvam API directly to see what it returns"""
import os
from sarvamai import SarvamAI
import json

# Initialize client
client = SarvamAI(api_subscription_key=os.getenv("SARVAM_API_KEY"))

# Create batch job
print("Creating Sarvam batch job...")
job = client.speech_to_text_translate_job.create_job(
    model="saaras:v2.5",
    with_diarization=True,
    num_speakers=2
)

print(f"Job ID: {job.job_id}")

# Upload audio file
audio_path = "/tmp/test_chunk_0.mp3"
print(f"Uploading {audio_path}...")
upload_success = job.upload_files([audio_path], timeout=60.0)
print(f"Upload success: {upload_success}")

# Start and wait
print("Starting job...")
job.start()

print("Waiting for completion...")
job.wait_until_complete(poll_interval=2, timeout=60)

# Get results
print("\nGetting results...")
results = job.get_file_results()

print(f"\n{'='*60}")
print("RESULTS:")
print(f"{'='*60}")
print(json.dumps(results, indent=2))

# Extract diarized_transcript
if results and 'successful' in results:
    for file_result in results['successful']:
        print(f"\n{'='*60}")
        print("FILE RESULT:")
        print(f"{'='*60}")
        print(json.dumps(file_result, indent=2))

        if 'diarized_transcript' in file_result:
            diarized = file_result['diarized_transcript']
            print(f"\n{'='*60}")
            print(f"DIARIZED TRANSCRIPT ({len(diarized)} entries):")
            print(f"{'='*60}")
            for idx, entry in enumerate(diarized):
                print(f"{idx}: {entry}")
        else:
            print("\n⚠️ NO 'diarized_transcript' key found!")
            print(f"Available keys: {list(file_result.keys())}")
