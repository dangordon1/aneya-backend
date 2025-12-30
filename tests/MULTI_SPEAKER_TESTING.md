# Multi-Speaker Diarisation Testing Guide

This guide explains how to test the multi-speaker diarisation functionality.

## Overview

The multi-speaker implementation supports:
- ✅ Auto-detection of 2-5+ speakers
- ✅ LLM-based role identification (Doctor, Patient, Chaperone, Nurse, Family Member, Other Clinician, Unknown)
- ✅ Confidence scoring with threshold-based manual assignment
- ✅ Backward compatibility with existing 2-speaker consultations

## Running Tests

### 1. Backend Unit Tests

**Requirements:**
- Python 3.10+
- pytest installed (`pip install pytest`)

**Run tests:**
```bash
cd /Users/dgordon/aneya/aneya-backend
pytest tests/test_multi_speaker.py -v
```

**Test coverage:**
- ✅ 2-speaker identification (doctor + patient)
- ✅ 3-speaker identification (doctor + patient + family)
- ✅ 4-speaker identification (doctor + patient + nurse + family)
- ✅ Low confidence triggering manual assignment
- ✅ Custom confidence threshold
- ✅ Malformed LLM response fallback
- ✅ Auto-detection (no hardcoded defaults)
- ✅ Backward compatibility
- ✅ Edge cases (1 speaker, 5+ speakers, empty segments)

### 2. Frontend Unit Tests

**Requirements:**
- Node.js 18+
- Vitest installed

**Run tests:**
```bash
cd /Users/dgordon/aneya/aneya-frontend
npm test src/utils/speakerMatching.test.ts
```

**Test coverage:**
- ✅ Speaker matching across chunks (2, 3, 4+ speakers)
- ✅ New speaker joining conversation
- ✅ Speaker leaving conversation
- ✅ Speaker ID changes between chunks
- ✅ Low similarity handling
- ✅ Empty overlap regions

### 3. Integration Tests

**Requirements:**
- Backend server running on http://localhost:8000
- ANTHROPIC_API_KEY environment variable set

**Run integration tests:**
```bash
cd /Users/dgordon/aneya/aneya-backend
python tests/integration_test_multi_speaker.py
```

**What it tests:**
- ✅ Full API workflow for 2, 3, 4 speakers
- ✅ Real LLM responses (requires API key)
- ✅ Confidence scoring and thresholds
- ✅ Low confidence scenarios

**Expected output:**
```
================================================================================
MULTI-SPEAKER DIARISATION INTEGRATION TESTS
================================================================================
Testing against: http://localhost:8000

================================================================================
TEST: Two-Speaker Consultation (Doctor + Patient)
================================================================================
✅ Response received:
   Role mapping: {'speaker_0': 'Doctor', 'speaker_1': 'Patient'}
   Confidence scores: {'speaker_0': 0.95, 'speaker_1': 0.92}
   Requires manual: False
✅ PASSED: Two-speaker consultation works correctly

[... more tests ...]

================================================================================
TEST SUMMARY
================================================================================
Total tests: 5
✅ Passed: 5
❌ Failed: 0

🎉 ALL TESTS PASSED!
```

## Manual Testing

### Test Scenario 1: Standard 2-Speaker Consultation

**Setup:**
1. Start backend: `cd aneya-backend && uvicorn api:app --reload`
2. Start frontend: `cd aneya-frontend && npm run dev`
3. Navigate to consultation recording page

**Steps:**
1. Start recording
2. Speak as doctor: "Good morning. What brings you in today?"
3. Speak as patient: "I've been having chest pain."
4. Stop recording after ~30 seconds
5. Observe: Speakers should be auto-identified with high confidence
6. Verify: No SpeakerMappingModal should appear (high confidence)

**Expected:**
- ✅ 2 speakers detected automatically
- ✅ Roles assigned: Doctor, Patient
- ✅ Confidence > 0.7 for both
- ✅ Form auto-fill works from both speakers

### Test Scenario 2: 3-Speaker Consultation (Manual Assignment)

**Setup:**
Same as above

**Steps:**
1. Start recording
2. Record very short utterances (to trigger low confidence):
   - "Hi" (speaker 1)
   - "Hello" (speaker 2)
   - "Hey" (speaker 3)
3. Stop recording
4. Observe: SpeakerMappingModal should appear

**Expected:**
- ✅ Modal shows 3 speakers
- ✅ LLM suggestions displayed with low confidence badges (<70%)
- ✅ User can manually assign roles from dropdown
- ✅ Sample text shown for each speaker
- ✅ After confirmation, recording continues normally

### Test Scenario 3: 4-Speaker Consultation (Realistic)

**Setup:**
Same as above

**Steps:**
1. Start recording
2. Record realistic consultation:
   - Doctor: "Let's review your test results."
   - Patient: "I'm worried about what they show."
   - Nurse: "Blood pressure is 120 over 80."
   - Family: "Doctor, should we be concerned?"
3. Continue for multiple chunks
4. Stop recording

**Expected:**
- ✅ 4 speakers detected
- ✅ Roles: Doctor, Patient, Nurse, Family Member
- ✅ All confidence > 0.7 (no modal)
- ✅ Form extracts medical info from all speakers
- ✅ Speaker IDs consistent across chunks

## Backward Compatibility Testing

### Verify Existing 2-Speaker Consultations Work

**Test:**
1. Load an existing consultation with 2 speakers
2. Verify transcript displays correctly
3. Verify form data extracted correctly
4. Re-run transcription if available

**Expected:**
- ✅ No regression in 2-speaker behavior
- ✅ Same confidence thresholds
- ✅ Same role assignments (Doctor, Patient)

## Database Migration Testing

### Verify Migration Applied Correctly

**Test:**
```bash
cd /Users/dgordon/aneya/aneya-backend
psql -h <host> -U <user> -d <database> -f migrations/017_add_speaker_role_confidence.sql
```

**Verify columns exist:**
```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'consultations'
  AND column_name IN ('speaker_role_mapping', 'speaker_confidence_scores', 'speaker_identification_method');
```

**Expected:**
```
       column_name           | data_type
-----------------------------+-----------
 speaker_role_mapping        | jsonb
 speaker_confidence_scores   | jsonb
 speaker_identification_method| text
```

## Performance Testing

### Measure Speaker Identification Latency

**Test:**
```bash
# Run integration test and check latency
python tests/integration_test_multi_speaker.py
```

**Success Criteria:**
- ✅ Speaker identification < 3s (95th percentile)
- ✅ No increase in chunk diarization latency
- ✅ Modal loads < 500ms

## Troubleshooting

### Issue: Tests fail with "ANTHROPIC_API_KEY not set"

**Solution:**
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### Issue: Integration tests fail with "Connection refused"

**Solution:**
```bash
# Start backend server
cd /Users/dgordon/aneya/aneya-backend
uvicorn api:app --reload
```

### Issue: Frontend tests fail with "Module not found"

**Solution:**
```bash
cd /Users/dgordon/aneya/aneya-frontend
npm install
```

### Issue: SpeakerMappingModal doesn't show

**Possible causes:**
1. All speakers have confidence > 0.7 (working as intended)
2. Check browser console for errors
3. Verify state variables in React DevTools

## Test Data

### Sample Segments for Testing

**2-Speaker (High Confidence):**
```json
[
  {"speaker_id": "speaker_0", "text": "Good morning. What brings you in today?", "start_time": 0.0, "end_time": 2.5},
  {"speaker_id": "speaker_1", "text": "I've been having chest pain for three days.", "start_time": 3.0, "end_time": 5.5}
]
```

**3-Speaker (Mixed Confidence):**
```json
[
  {"speaker_id": "speaker_0", "text": "Good afternoon.", "start_time": 0.0, "end_time": 1.5},
  {"speaker_id": "speaker_1", "text": "I have headaches.", "start_time": 2.0, "end_time": 3.5},
  {"speaker_id": "speaker_2", "text": "Doctor, she mentioned dizziness too.", "start_time": 4.0, "end_time": 6.5}
]
```

**Low Confidence (Triggers Modal):**
```json
[
  {"speaker_id": "speaker_0", "text": "Hi", "start_time": 0.0, "end_time": 0.5},
  {"speaker_id": "speaker_1", "text": "Hello", "start_time": 1.0, "end_time": 1.5},
  {"speaker_id": "speaker_2", "text": "Hey", "start_time": 2.0, "end_time": 2.5}
]
```

## Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Auto-detect 2-5+ speakers | ✅ Yes | ✅ Pass |
| LLM accuracy (2-speaker) | >85% | ⏳ Test |
| LLM accuracy (3-speaker) | >70% | ⏳ Test |
| Modal trigger rate | <20% | ⏳ Monitor |
| User confirmation time | <30s | ⏳ Monitor |
| Backward compatibility | 100% | ✅ Pass |

## Next Steps

1. ✅ Run unit tests: `pytest tests/test_multi_speaker.py -v`
2. ✅ Run frontend tests: `npm test src/utils/speakerMatching.test.ts`
3. ⏳ Run integration tests: `python tests/integration_test_multi_speaker.py`
4. ⏳ Manual testing with real audio
5. ⏳ Deploy to staging
6. ⏳ Monitor metrics in production
