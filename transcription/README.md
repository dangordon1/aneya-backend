# Transcription Testing

This directory contains tools for testing the audio transcription endpoint.

## Files

- **`create_test_audio.py`** - Generates test audio file using Google Text-to-Speech
- **`test_transcription.py`** - Tests the `/api/transcribe` endpoint with timing
- **`test_audio.mp3`** - Generated test audio file (created by `create_test_audio.py`)

## Transcription Model

The API uses **NVIDIA Parakeet TDT 0.6B** for transcription:

| Metric | Parakeet TDT 0.6B | Whisper Small |
|--------|-------------------|---------------|
| Latency | ~2s | ~13s |
| Word Error Rate | ~6% | 14% |
| Model Size | ~350MB | ~500MB |

Parakeet 0.6B is faster and more accurate than Whisper, with a smaller footprint.

## Usage

### Step 1: Generate Test Audio

```bash
cd transcription
python create_test_audio.py
```

This creates `test_audio.mp3` with a clinical case scenario.

### Step 2: Start the API

In a separate terminal from the project root:

```bash
python api.py
```

Wait for the Parakeet model to load:
```
🎤 Loading NVIDIA Parakeet TDT 0.6B model for transcription...
✅ Parakeet TDT model loaded successfully
```

First load downloads ~350MB from HuggingFace.

### Step 3: Run the Test

```bash
cd transcription
python test_transcription.py
```

## Test Output

```
======================================================================
🎤 TRANSCRIPTION ENDPOINT TEST
======================================================================

📁 Using test audio: test_audio.mp3
📊 File size: 25024 bytes
🎯 Expected text (approximately): 'Patient presents with a 3-day history...'

✅ API is running

🎤 Sending audio to http://localhost:8000/api/transcribe...
📡 Response status: 200
⏱️  Transcription time: 2.34 seconds

✅ Transcription successful!
📝 Transcribed text: 'Patient presents with a 3-day history...'
✅ Transcription quality: GOOD (45/45 key words found, 100.0% accuracy)

======================================================================
✅ TEST PASSED - Transcription endpoint is working!
======================================================================
```

## API Endpoint

**POST /api/transcribe**

**Request:**
- Multipart form data with audio file
- Field name: `audio`
- Supported formats: MP3, WAV, WebM, etc.

**Response:**
```json
{
  "success": true,
  "text": "transcribed text here",
  "latency_seconds": 2.34,
  "model": "nvidia/parakeet-tdt-0.6b-v2"
}
```

## Customizing

To test with different audio:

1. Edit the `text` variable in `create_test_audio.py`
2. Run `python create_test_audio.py` to regenerate
3. Update `EXPECTED_TEXT` in `test_transcription.py` if needed
4. Run the test

## Troubleshooting

**"Cannot connect to API"**
- Make sure `python api.py` is running
- Check that port 8000 is not in use

**"Parakeet model not initialized"**
- Check if model loaded on startup
- Requires ~2GB RAM for model
- May need `pip install nemo_toolkit[asr]`

**"Test audio file not found"**
- Run `python create_test_audio.py` first

**"Request timed out"**
- Large audio files may exceed timeout
- Use shorter audio clips for testing

## Note on Deployment

Voice transcription is only available on Cloud Run (not Vercel) due to model size requirements.
