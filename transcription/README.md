# Transcription Testing

This directory contains tools for testing the audio transcription endpoint.

## Files

- **`create_test_audio.py`** - Generates test audio file using Google Text-to-Speech
- **`test_transcription.py`** - Tests the `/api/transcribe` endpoint with timing
- **`test_audio.mp3`** - Generated test audio file (created by `create_test_audio.py`)

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

Wait for the Whisper model to load (you'll see: "✅ Whisper model loaded")

### Step 3: Run the Test

```bash
cd transcription
python test_transcription.py
```

## Test Output

The test provides:
- ✅ API connectivity check
- 📁 Audio file information
- ⏱️ **Transcription timing** (how long it took)
- 📝 Full transcribed text
- ✅ Quality metrics (word accuracy percentage)
- Pass/fail status

## Example Output

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

The test targets: `POST /api/transcribe`

**Request:**
- Multipart form data with audio file
- Field name: `audio`
- Supported formats: MP3, WAV, WebM, etc.

**Response:**
```json
{
  "success": true,
  "text": "transcribed text here"
}
```

## Whisper Model

The API uses `faster-whisper` with the "small" model:
- Fast transcription (typically 2-5 seconds)
- Good accuracy for English clinical speech
- CPU-optimized with INT8 quantization

## Customizing

To test with different audio:

1. Edit the `text` variable in `create_test_audio.py`
2. Run `python create_test_audio.py` to regenerate
3. Update `EXPECTED_TEXT` in `test_transcription.py` if needed
4. Run the test

## Troubleshooting

**"Cannot connect to API"**
- Make sure `python api.py` is running
- Check that port 8000 is not in use by another process

**"Test audio file not found"**
- Run `python create_test_audio.py` first

**"Request timed out"**
- Large audio files may exceed the 30-second timeout
- Consider using a shorter audio clip for testing
