#!/usr/bin/env python3
"""
Test script for speaker diarization endpoint.

Usage:
    python test_diarization.py <audio_file.webm>

Example:
    python test_diarization.py recording-2025-12-07T02-36-45-123Z.webm
"""

import sys
import requests
import json
from pathlib import Path


def test_diarization(audio_file_path: str, base_url: str = "http://localhost:8000"):
    """
    Test the /api/diarize endpoint with a local audio file.

    Args:
        audio_file_path: Path to audio file (webm, mp3, wav, etc.)
        base_url: Backend API URL
    """
    audio_path = Path(audio_file_path)

    if not audio_path.exists():
        print(f"❌ Error: File not found: {audio_file_path}")
        return

    print(f"🎤 Testing diarization with: {audio_path.name}")
    print(f"📊 File size: {audio_path.stat().st_size / 1024:.2f} KB")
    print(f"🌐 API endpoint: {base_url}/api/diarize")
    print()

    # Send request
    with open(audio_path, 'rb') as f:
        files = {'audio': (audio_path.name, f, 'audio/webm')}

        try:
            response = requests.post(
                f"{base_url}/api/diarize",
                files=files,
                timeout=120
            )

            print(f"📡 Response status: {response.status_code}")
            print()

            if response.ok:
                data = response.json()

                print("✅ Diarization successful!")
                print(f"👥 Detected speakers: {data.get('detected_speakers', [])}")
                print(f"📝 Number of segments: {len(data.get('segments', []))}")
                print(f"⏱️  Latency: {data.get('latency_seconds', 'N/A')}s")
                print()

                # Print segments
                print("Speaker Segments:")
                print("-" * 80)
                for i, seg in enumerate(data.get('segments', []), 1):
                    speaker = seg.get('speaker_id', 'unknown')
                    text = seg.get('text', '')
                    start = seg.get('start_time', 0)
                    end = seg.get('end_time', 0)

                    print(f"{i}. [{start:.2f}s - {end:.2f}s] {speaker}:")
                    print(f"   {text}")
                    print()

                # Print full transcript
                print("Full Transcript:")
                print("-" * 80)
                print(data.get('full_transcript', ''))
                print()

                # Save results to JSON
                output_file = audio_path.with_suffix('.diarization.json')
                with open(output_file, 'w') as out:
                    json.dump(data, out, indent=2)
                print(f"💾 Results saved to: {output_file}")

            else:
                print(f"❌ Request failed: {response.status_code}")
                print(f"Error: {response.text}")

        except requests.exceptions.Timeout:
            print("❌ Request timed out (>120s)")
        except requests.exceptions.ConnectionError:
            print(f"❌ Could not connect to {base_url}")
            print("   Make sure the backend server is running!")
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_diarization.py <audio_file.webm>")
        print()
        print("Example:")
        print("  python test_diarization.py recording-2025-12-07T02-36-45-123Z.webm")
        sys.exit(1)

    audio_file = sys.argv[1]
    test_diarization(audio_file)
