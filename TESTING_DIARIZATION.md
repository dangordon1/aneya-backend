# Testing Speaker Diarization

This guide explains how to test the speaker diarization feature using recordings from the frontend.

## Recording Audio for Tests

When you record in the frontend (https://aneya.vercel.app or http://localhost:5173), the audio will automatically download to your Downloads folder with a timestamped filename:

```
recording-2025-12-07T02-36-45-123Z.webm
```

These recordings can be used for:
- Backend API testing
- Debugging diarization issues
- Creating automated test suites
- Verifying speaker detection accuracy

## Testing with the Script

### 1. Record Audio
1. Open the frontend: http://localhost:5173
2. Navigate to "New Consultation"
3. Click "Start Recording" and have a conversation (multi-speaker works best)
4. Click "Stop Recording"
5. The audio file will automatically download to your Downloads folder

### 2. Run the Test Script

```bash
cd /Users/dgordon/aneya/aneya-backend

# Make sure backend is running
# (in another terminal: source .env && python -m uvicorn api:app --reload)

# Test with downloaded recording
python test_diarization.py ~/Downloads/recording-2025-12-07T02-36-45-123Z.webm
```

### 3. View Results

The script will output:
- Detected speakers
- Number of segments
- Processing latency
- Each segment with speaker ID, timestamps, and text
- Full transcript

It also saves the results to a JSON file:
```
recording-2025-12-07T02-36-45-123Z.diarization.json
```

## Example Output

```
🎤 Testing diarization with: recording-2025-12-07T02-36-45-123Z.webm
📊 File size: 853.07 KB
🌐 API endpoint: http://localhost:8000/api/diarize

📡 Response status: 200

✅ Diarization successful!
👥 Detected speakers: ['speaker_1', 'speaker_2']
📝 Number of segments: 12
⏱️  Latency: 2.34s

Speaker Segments:
--------------------------------------------------------------------------------
1. [0.00s - 2.50s] speaker_1:
   Hello, what brings you in today?

2. [2.50s - 5.80s] speaker_2:
   I've had a persistent cough for three days.

3. [5.80s - 8.20s] speaker_1:
   Let me check your vitals...

...

💾 Results saved to: recording-2025-12-07T02-36-45-123Z.diarization.json
```

## Creating Automated Tests

You can create a test suite by:

1. Collecting various recordings (1-speaker, 2-speaker, multi-speaker)
2. Organizing them in a `test_audio/` directory
3. Creating a pytest test that runs each file through the diarization endpoint
4. Asserting expected speaker counts and segment quality

Example structure:
```
aneya-backend/
├── test_audio/
│   ├── single_speaker.webm
│   ├── doctor_patient.webm
│   ├── multi_speaker_family.webm
│   └── expected_results.json
├── test_diarization.py  (manual testing)
└── tests/
    └── test_diarization_suite.py  (automated pytest)
```

## Debugging Tips

### If diarization fails with 400 error:
1. Check backend logs for the error message from ElevenLabs API
2. Verify audio format (should be webm → mp3 conversion)
3. Check MIME type is set correctly
4. Ensure ELEVENLABS_API_KEY is valid

### If no speakers detected:
1. Verify audio has actual voice content
2. Check audio isn't silent or corrupted
3. Try adjusting `diarization_threshold` (default 0.22)

### If wrong number of speakers:
1. Try setting `num_speakers` parameter explicitly
2. Adjust `diarization_threshold` (lower = more sensitive)
3. Ensure speakers have distinct voices and don't overlap too much

## Manual API Testing with cURL

You can also test with cURL:

```bash
curl -X POST http://localhost:8000/api/diarize \
  -F "audio=@recording-2025-12-07T02-36-45-123Z.webm" \
  -F "diarization_threshold=0.22" \
  | python -m json.tool
```

## Next Steps

- [ ] Collect test recordings with known speaker counts
- [ ] Create automated pytest suite
- [ ] Test edge cases (single speaker, overlapping speech, background noise)
- [ ] Benchmark latency with different audio lengths
- [ ] Test with different audio formats (webm, mp3, wav)
