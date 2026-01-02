# Consultation Transcription & Diarization Architecture

## Overview

The production system uses a **batch processing architecture** for speaker diarization:

1. **During Recording**: Real-time transcription via ElevenLabs/Sarvam WebSocket (no speaker labels)
2. **Post-Recording**: Full audio sent for batch diarization (25-50s processing time)
3. **Speaker Identification**:
   - **Manual**: User maps speaker IDs via SpeakerMappingModal
   - **Automatic**: LLM-based identification during consultation summarization

This architecture provides reliable, high-quality speaker diarization and role identification with user control and verification.

---

## Production Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│ FRONTEND (InputScreen.tsx)                                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ RECORDING PHASE                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User clicks "Start Recording"                                          │
│         ↓                                                                │
│  MediaRecorder starts capturing audio                                   │
│  - Collects 1-second audio blobs into audioChunksRef                    │
│  - Sends to ElevenLabs/Sarvam WebSocket for real-time transcription    │
│         ↓                                                                │
│  ┌──────────────────────────────────────────┐                           │
│  │ ElevenLabs Scribe v2 Realtime WebSocket  │                           │
│  │ (or Sarvam for Indian languages)         │                           │
│  │                                           │                           │
│  │ Frontend connects directly to provider   │                           │
│  │ Token obtained from /api/get-*-token     │                           │
│  │                                           │                           │
│  │ Receives: 1-second audio blobs           │                           │
│  │ Returns: Real-time transcript chunks     │                           │
│  │ Latency: ~150-300ms per chunk            │                           │
│  └──────────────────────────────────────────┘                           │
│         ↓                                                                │
│  Display interim transcript in UI (NO speaker labels yet)               │
│                                                                          │
│  Recording duration: 0s → 130s → ...                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ POST-RECORDING PHASE (After user stops recording)                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User clicks "Stop Recording"                                           │
│         ↓                                                                │
│  1. Combine all audioChunksRef blobs into single file                   │
│         ↓                                                                │
│  2. Show "Analyzing Speakers..." spinner (user waits here!)             │
│         ↓                                                                │
│  ┌──────────────────────────────────────────┐                           │
│  │ POST /api/diarize                        │                           │
│  │ or POST /api/diarize-sarvam              │                           │
│  │                                           │                           │
│  │ Sends: Full audio file (webm)            │                           │
│  │ Language: consultationLanguage           │                           │
│  │                                           │                           │
│  │ BACKEND PROCESSING:                      │                           │
│  │ 1. Convert webm → mp3 (2-5s) ⏱️         │                           │
│  │ 2. Call ElevenLabs/Sarvam (15-30s) ⏱️   │                           │
│  │ 3. Group words by speaker (1s)           │                           │
│  │                                           │                           │
│  │ Returns:                                  │                           │
│  │ {                                         │                           │
│  │   segments: [                             │                           │
│  │     {speaker_id, text, start, end}, ...  │                           │
│  │   ],                                      │                           │
│  │   detected_speakers: ["speaker_0", ...], │                           │
│  │   full_transcript: "..."                  │                           │
│  │ }                                         │                           │
│  │                                           │                           │
│  │ Total latency: 25-50 seconds ⏱️⏱️⏱️    │                           │
│  └──────────────────────────────────────────┘                           │
│         ↓                                                                │
│  3. Speaker Identification (two methods):                               │
│     A. SpeakerMappingModal: User manually maps speaker_0 → roles        │
│        - Simple UI to select which speaker is Doctor/Patient            │
│        - User confirms mapping                                          │
│     B. Automatic LLM identification (during summarization):             │
│        - /api/identify-speaker-roles analyzes conversation patterns     │
│        - Claude Haiku identifies roles (1-2s, ~$0.001 cost)             │
│        - Fallback to heuristic method if LLM fails                      │
│         ↓                                                                │
│  4. Apply role mapping and display final transcript                     │
│                                                                          │
│  Total wait time: 25-50 seconds from stop → speaker-labeled transcript  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Speaker Identification Methods

### Method A: Manual Mapping (SpeakerMappingModal)
**Location**: `aneya-frontend/src/components/SpeakerMappingModal.tsx`

After diarization completes, the user is presented with a modal to map generic speaker IDs (`speaker_0`, `speaker_1`) to roles (Doctor, Patient). This ensures accuracy and gives users control over the mapping.

### Method B: Automatic LLM Identification
**Location**: `aneya-backend/servers/clinical_decision_support/summary.py:170-200`

During consultation summarization, the system automatically identifies speaker roles using the `/api/identify-speaker-roles` endpoint:
- **Model**: Claude Haiku 3.5
- **Latency**: 1-2 seconds
- **Cost**: ~$0.001 per consultation
- **Accuracy**: Analyzes conversation patterns (questions, medical terminology, symptom descriptions)
- **Fallback**: Heuristic-based identification if LLM fails

### When Speaker Identification Happens

**Timeline of speaker identification in the current system:**

| Stage | When | Method | Details |
|-------|------|--------|---------|
| **Recording** | During (0s → end) | None | Real-time transcription has no speaker labels |
| **Diarization** | Post-recording | Batch API | Generic IDs assigned: `speaker_0`, `speaker_1` (25-50s) |
| **Manual Mapping** | After diarization | User interaction | SpeakerMappingModal allows user to map IDs to roles |
| **Summarization** | When generating summary | Automatic LLM | ConsultationSummary.summarize() identifies roles (1-2s) |

**Summary**: Speaker identification happens **POST-RECORDING**, either via manual user mapping or automatic LLM identification during summarization. The system does NOT identify speakers during the live recording.

---

## Experimental Architecture: Chunked Processing (Reference Only)

> **Note**: The following architecture is documented for reference but is NOT currently implemented in production. The batch processing approach above is the stable, production implementation.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ FRONTEND (InputScreen.tsx - EXPERIMENTAL)                               │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ RECORDING PHASE (Parallel Processing - EXPERIMENTAL)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User clicks "Start Recording"                                          │
│         ↓                                                                │
│  MediaRecorder starts capturing audio                                   │
│  - Collects 1-second blobs into audioChunksRef                          │
│  - Real-time transcription via ElevenLabs/Sarvam WebSocket             │
│         ↓                                                                │
│  Every 30 seconds during recording:                                     │
│         ↓                                                                │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ CHUNK 0 (t=30s): Extract 0-30s audio                    │            │
│  │         ↓                                                 │            │
│  │ POST /api/diarize-chunk                                  │            │
│  │ Sends: 30s audio blob, overlap metadata                 │            │
│  │         ↓                                                 │            │
│  │ BACKEND: Diarize in parallel (2-3s) ⏱️                  │            │
│  │         ↓                                                 │            │
│  │ Returns: segments + overlap_stats                        │            │
│  │         ↓                                                 │            │
│  │ Frontend receives diarized segments                      │            │
│  │         ↓                                                 │            │
│  │ TRIGGER: POST /api/identify-speaker-roles (background)   │            │
│  │         ↓                                                 │            │
│  │ BACKEND: Claude Haiku analyzes first 20 segments (1.3s)  │            │
│  │         ↓                                                 │            │
│  │ Returns: {speaker_0: "Doctor", speaker_1: "Patient"}     │            │
│  │         ↓                                                 │            │
│  │ Store role mapping in state                              │            │
│  │         ↓                                                 │            │
│  │ UI UPDATE: Show "Doctor" and "Patient" labels!           │            │
│  └─────────────────────────────────────────────────────────┘            │
│                                                                          │
│  At t=60s:                                                               │
│  ┌─────────────────────────────────────────────────────────┐            │
│  │ CHUNK 1 (t=60s): Extract 25-60s audio (5s overlap)      │            │
│  │         ↓                                                 │            │
│  │ POST /api/diarize-chunk (parallel request)               │            │
│  │         ↓                                                 │            │
│  │ BACKEND: Diarize (2-3s) ⏱️                               │            │
│  │         ↓                                                 │            │
│  │ Frontend: Match speakers using overlap (25-30s region)   │            │
│  │         ↓                                                 │            │
│  │ Remap speaker_1 → speaker_0 (based on overlap stats)     │            │
│  │         ↓                                                 │            │
│  │ Apply role mapping: speaker_0 → "Doctor"                 │            │
│  │         ↓                                                 │            │
│  │ Merge new segments into transcript                       │            │
│  │         ↓                                                 │            │
│  │ UI UPDATE: Append new Doctor/Patient segments            │            │
│  └─────────────────────────────────────────────────────────┘            │
│                                                                          │
│  ... continues every 30s until recording stops                          │
│                                                                          │
│  Recording duration: 0s → 30s → 60s → 90s → 120s → STOP                 │
│  Diarization: Chunk0  Chunk1  Chunk2  Chunk3 → ALL DONE!                │
│                 ↓       ↓       ↓       ↓                                │
│  Role ID:    Doctor/Patient (applied to all chunks)                     │
│                                                                          │
│  User sees progressive transcript with roles DURING recording!          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ POST-RECORDING PHASE (Instant!)                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  User clicks "Stop Recording"                                           │
│         ↓                                                                │
│  IF last chunk not yet processed:                                       │
│    - Extract final chunk (e.g., 115-130s)                               │
│    - POST /api/diarize-chunk                                            │
│    - Match speakers and merge                                           │
│         ↓                                                                │
│  Transcript is already complete! No waiting! ✅                          │
│         ↓                                                                │
│  User can immediately review and proceed                                │
│                                                                          │
│  Total wait time: 0-3 seconds (only final chunk if needed)              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## API Endpoints (Production)

#### 1. `/api/get-transcription-token` (GET) & `/api/get-sarvam-token` (GET)
- **Purpose:** Generate temporary tokens for client-side WebSocket connections
- **Providers:**
  - ElevenLabs Scribe v2 Realtime (English/multilingual)
  - Sarvam AI (Indian languages)
- **Returns:**
  - Token for frontend to connect directly to provider's WebSocket
  - Token expires in 15 minutes
- **Used:** Before starting recording
- **Frontend Connection:**
  - Frontend connects directly to provider's WebSocket (wss://...)
  - Sends audio stream (1-second chunks)
  - Receives real-time transcript (no speaker labels)
  - Latency: ~150-300ms per chunk

#### 2. `/api/diarize` (POST)
- **Purpose:** Batch diarization after recording completes
- **Provider:** ElevenLabs Scribe v1
- **Input:** Full audio file (webm/mp3)
- **Processing:**
  - FFmpeg conversion: 2-5s
  - API call: 15-30s
  - Grouping: 1s
- **Output:**
  ```json
  {
    "segments": [
      {"speaker_id": "speaker_0", "text": "...", "start_time": 0.3, "end_time": 2.1},
      ...
    ],
    "detected_speakers": ["speaker_0", "speaker_1"],
    "full_transcript": "..."
  }
  ```
- **Latency:** 25-50 seconds
- **Used:** Currently in production

#### 3. `/api/diarize-sarvam` (POST)
- **Purpose:** Batch diarization for Indian languages
- **Provider:** Sarvam AI
- **Languages:** 11 Indian languages (hi-IN, ta-IN, etc.)
- **Similar latency to ElevenLabs:** 20-40 seconds
- **Used:** For non-English consultations

#### 4. `/api/identify-speaker-roles` (POST)
- **Purpose:** Automatically identify which speaker is doctor vs patient
- **Provider:** Claude Haiku 3.5
- **Used by:** ConsultationSummary module during summarization
- **Input:**
  ```json
  {
    "segments": [
      {"speaker_id": "speaker_0", "text": "How are you feeling?", ...},
      {"speaker_id": "speaker_1", "text": "I have a cough", ...}
    ],
    "language": "en-IN"
  }
  ```
- **Processing:**
  - Analyzes conversation segments to detect patterns
  - Doctors: ask questions, use medical terms, lead conversation
  - Patients: describe symptoms, answer questions
- **Output:**
  ```json
  {
    "success": true,
    "role_mapping": {
      "speaker_0": "Doctor",
      "speaker_1": "Patient"
    },
    "latency_seconds": 1.3,
    "model": "claude-haiku-4-5"
  }
  ```
- **Latency:** 1-2 seconds
- **Cost:** ~$0.001 per consultation (Haiku pricing)
- **Usage:** Called automatically during consultation summarization; falls back to heuristic method on failure

---

## Experimental Endpoints (Not in Production)

#### `/api/diarize-chunk` (POST) - EXPERIMENTAL
- **Purpose:** Incremental diarization during recording
- **Input:**
  ```
  FormData:
    audio: 30-second audio chunk (webm)
    chunk_index: 0, 1, 2, ...
    overlap_start: timestamp where overlap begins
    overlap_end: timestamp where overlap ends
    language: "en-IN"
  ```
- **Processing:**
  - Convert chunk to mp3 (or skip if webm supported)
  - Call ElevenLabs/Sarvam diarization API
  - Calculate overlap statistics for speaker matching
- **Output:**
  ```json
  {
    "success": true,
    "chunk_index": 0,
    "segments": [...],
    "detected_speakers": ["speaker_0", "speaker_1"],
    "start_overlap_stats": {
      "speaker_0": {"duration": 2.4, "words": 15, "segments": 3},
      "speaker_1": {"duration": 2.6, "words": 18, "segments": 2}
    },
    "end_overlap_stats": {...},
    "latency_seconds": 2.3
  }
  ```
- **Latency:** 2-3 seconds per chunk
- **Parallel potential:** All chunks can process simultaneously

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         RECORDING IN PROGRESS                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Timeline:   0s─────30s─────60s─────90s────120s────130s (STOP)          │
│                      │       │       │       │       │                   │
│  Audio      ████████████████████████████████████████████                │
│  Capture:           │       │       │       │       │                   │
│                      │       │       │       │       │                   │
│  Chunk              └────┐  └────┐  └────┐  └────┐  └──────┐           │
│  Extraction:          C0      C1      C2      C3      C4                │
│                        │       │       │       │       │                 │
│                        ↓       ↓       ↓       ↓       ↓                 │
│  Diarize           [2.1s]  [2.7s]  [2.5s]  [2.9s]  [1.2s]               │
│  (parallel):          │       │       │       │       │                 │
│                        ↓       │       │       │       │                 │
│  Role ID            [1.3s]    │       │       │       │                 │
│  (Chunk 0 only):      │       │       │       │       │                 │
│                        ↓       ↓       ↓       ↓       ↓                 │
│  Speaker            Match   Match   Match   Match   Final                │
│  Matching:           ─>C0    C0─C1   C1─C2   C2─C3   merge              │
│                        │       │       │       │       │                 │
│                        ↓       ↓       ↓       ↓       ↓                 │
│  UI Display:      [Doctor]   +11    +12     +9      +3  segments        │
│                   [Patient]  segs   segs    segs    segs                │
│                        │       │       │       │       │                 │
│                   t=33.4s  t=63.4s t=93.4s t=123.9s DONE!               │
│                                                                          │
│  User Experience: "Sees speaker-labeled transcript appear progressively" │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Performance Characteristics (Production System)

| Metric | Production Implementation |
|--------|--------------------------|
| **Real-time transcription latency** | 150-300ms per 1-second chunk |
| **Diarization latency** | 25-50 seconds (post-recording batch) |
| **Speaker identification** | Manual (instant) or LLM (1-2s during summarization) |
| **User wait after recording** | 25-50 seconds for diarization + manual mapping |
| **Accuracy** | High (ElevenLabs/Sarvam diarization + user-confirmed roles) |
| **Cost per consultation** | ~$0.001 (if using LLM identification during summarization) |

---

## Experimental Performance Comparison (Reference Only)

| Metric | Production (Batch) | Experimental (Chunked) | Potential Improvement |
|--------|-------------------|------------------------|----------------------|
| **Time to first speaker labels** | 25-50s after stop | 3-4s after 30s | 8-15x faster |
| **Total processing time (2min recording)** | 25-50s sequential | 11-13s sequential | 2-4x faster |
| **User wait after stop** | 25-50s | 0-3s (final chunk) | 10-20x faster |
| **Speaker role identification** | Manual mapping or LLM | Automatic (Haiku) | Eliminates user step |
| **UI feedback during recording** | None | Progressive updates | New capability |

## Speaker Matching Algorithm

```
┌─────────────────────────────────────────────────────────────────────────┐
│ OVERLAP-BASED SPEAKER MATCHING                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Chunk 0 (0-30s)           Chunk 1 (25-60s)                             │
│  ─────────────────────     ─────────────────────                        │
│  │                   │     │                   │                         │
│  │   speaker_0       │     │   speaker_1       │                         │
│  │   speaker_1       │     │   speaker_0       │                         │
│  │                   │     │                   │                         │
│  └─────────────────┬─┘     └┬──────────────────┘                        │
│                    │         │                                           │
│        OVERLAP     │═════════│  (25-30s shared audio)                    │
│        REGION:     │         │                                           │
│                    │         │                                           │
│  Chunk 0 stats:    │         │  Chunk 1 stats:                           │
│    speaker_0: 2.5s │         │    speaker_1: 2.6s  ← MATCH! (similar)   │
│    speaker_1: 2.4s │         │    speaker_0: 2.4s  ← MATCH! (similar)   │
│                    │         │                                           │
│  Conclusion:       │         │                                           │
│    Chunk1.speaker_1 → maps to → Chunk0.speaker_0                        │
│    Chunk1.speaker_0 → maps to → Chunk0.speaker_1                        │
│                    │         │                                           │
│  Apply mapping:    │         │                                           │
│    All Chunk 1 segments get speaker IDs remapped to match Chunk 0       │
│                    │         │                                           │
│  Similarity Score Calculation:                                           │
│    - Duration similarity: 50% weight                                     │
│    - Word count similarity: 30% weight                                   │
│    - Avg segment length: 20% weight                                      │
│    - Threshold: 70% confidence to accept match                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Frontend State Management (New)

```typescript
// New state variables for chunked processing
const [chunkStatuses, setChunkStatuses] = useState<ChunkStatus[]>([]);
const [mergedSegments, setMergedSegments] = useState<DiarizedSegment[]>([]);
const [speakerIdMap, setSpeakerIdMap] = useState<Map<string, string>>(new Map());
const [speakerRoles, setSpeakerRoles] = useState<{[key: string]: string}>({});

interface ChunkStatus {
  index: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  startTime: number;
  endTime: number;
  segments?: DiarizedSegment[];
  speakers?: string[];
  error?: string;
}

// Every 30 seconds during recording
useEffect(() => {
  if (isRecording && recordingTime > 0 && recordingTime % 30 === 0) {
    processNextChunk();
  }
}, [isRecording, recordingTime]);
```

## Error Handling & Fallbacks

1. **Chunk processing failure:**
   - Retry failed chunk once
   - If still fails, fall back to batch processing entire recording

2. **Speaker role identification failure:**
   - Fall back to generic labels: "Speaker 1", "Speaker 2"
   - User can manually correct via SpeakerMappingModal

3. **Speaker matching low confidence (<70%):**
   - Still apply mapping but log warning
   - Consider increasing overlap duration to 10s for better accuracy

## Production Implementation Status

✅ **Production Components (Fully Implemented):**
- `/api/get-transcription-token` - Real-time transcription token generation
- `/api/get-sarvam-token` - Sarvam API token generation
- `/api/diarize` - Post-recording batch diarization (ElevenLabs)
- `/api/diarize-sarvam` - Post-recording batch diarization (Sarvam for Indian languages)
- `/api/identify-speaker-roles` - LLM-based speaker role identification (used during summarization)
- `SpeakerMappingModal` - Manual speaker role mapping UI
- `ConsultationSummary` - Automatic speaker identification during summarization with heuristic fallback

---

## Experimental Components Status (Reference Only)

✅ **Completed (Experimental):**
- `/api/identify-speaker-roles` endpoint with full context analysis
- Speaker role identification test scripts
- Overlap-based speaker matching algorithm documentation
- Test validation with chunked audio processing

🚧 **Not Implemented (Experimental):**
- `/api/diarize-chunk` endpoint for incremental diarization
- Frontend chunk extraction logic for live recording
- Frontend speaker matching logic between chunks
- Progressive UI updates during recording
- Live integration with SpeakerMappingModal

**Note**: These experimental features are documented for reference but are not planned for immediate production deployment. The current batch processing approach provides reliable, high-quality diarization and speaker identification.
