# Testing Prescription Extraction

## Overview
This document describes how to test the prescription extraction feature added to the consultation summarization system.

## Test Setup
1. Ensure backend is deployed to Cloud Run with the latest code changes
2. Ensure frontend TypeScript types are updated
3. Database migration has been applied (prescriptions column exists in consultations table)

## Test Cases

### Test 1: Complete Prescription Extraction
**Purpose**: Verify all prescription fields are extracted when fully specified

**Sample Transcript**:
```
[0.0 - 5.2] speaker_0 (Doctor): Based on your symptoms, I'm prescribing Paracetamol 500mg tablets. Take them orally three times daily for 7 days.

[5.2 - 10.5] speaker_1 (Patient): Okay, thank you doctor.

[10.5 - 15.8] speaker_0 (Doctor): I'm also prescribing Amoxicillin 250mg capsules. Take them orally twice daily for 5 days with food.
```

**Expected Result**:
```json
{
  "prescriptions": [
    {
      "drug_name": "Paracetamol",
      "amount": "500mg",
      "method": "oral",
      "frequency": "three times daily",
      "duration": "7 days"
    },
    {
      "drug_name": "Amoxicillin",
      "amount": "250mg",
      "method": "oral",
      "frequency": "twice daily",
      "duration": "5 days"
    }
  ]
}
```

### Test 2: Partial Prescription Information
**Purpose**: Verify prescriptions with missing fields are handled gracefully

**Sample Transcript**:
```
[0.0 - 3.5] speaker_0 (Doctor): Take some Aspirin for the headache.

[3.5 - 6.0] speaker_1 (Patient): How much should I take?

[6.0 - 8.5] speaker_0 (Doctor): Just the regular dose, once daily.
```

**Expected Result**:
```json
{
  "prescriptions": [
    {
      "drug_name": "Aspirin",
      "amount": null,
      "method": "oral",
      "frequency": "once daily",
      "duration": null
    }
  ]
}
```

### Test 3: No Prescriptions
**Purpose**: Verify empty array when no medications are prescribed

**Sample Transcript**:
```
[0.0 - 5.0] speaker_0 (Doctor): Your test results look normal. Just continue with rest and drink plenty of fluids.

[5.0 - 7.5] speaker_1 (Patient): Do I need any medication?

[7.5 - 10.0] speaker_0 (Doctor): No medications needed. This should resolve on its own in a few days.
```

**Expected Result**:
```json
{
  "prescriptions": []
}
```

### Test 4: Transcription Error Correction
**Purpose**: Verify drug names are corrected when misspelled in transcript

**Sample Transcript**:
```
[0.0 - 5.0] speaker_0 (Doctor): I'm prescribing pair-a-ceta-mol 500mg, take it orally twice daily for 3 days.
```

**Expected Result**:
```json
{
  "prescriptions": [
    {
      "drug_name": "Paracetamol",
      "amount": "500mg",
      "method": "oral",
      "frequency": "twice daily",
      "duration": "3 days"
    }
  ]
}
```

### Test 5: Continue Existing Medication
**Purpose**: Verify continuation instructions are captured

**Sample Transcript**:
```
[0.0 - 4.0] speaker_0 (Doctor): Continue taking your Metformin 500mg twice daily as before.

[4.0 - 6.5] speaker_1 (Patient): For how long?

[6.5 - 8.0] speaker_0 (Doctor): Continue it indefinitely as we discussed.
```

**Expected Result**:
```json
{
  "prescriptions": [
    {
      "drug_name": "Metformin",
      "amount": "500mg",
      "method": "oral",
      "frequency": "twice daily",
      "duration": "continue"
    }
  ]
}
```

## How to Test

### Via API Endpoint
```bash
# Test via curl
curl -X POST https://aneya-backend-xao3xivzia-el.a.run.app/api/summarize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "[0.0 - 5.2] speaker_0: Based on your symptoms, I am prescribing Paracetamol 500mg tablets. Take them orally three times daily for 7 days.",
    "patient_info": {
      "patient_id": "test-patient-001",
      "patient_age": "30 years old"
    },
    "is_from_transcription": true
  }'
```

### Via Frontend
1. Record a consultation with prescription mentions
2. Complete the transcription and summarization
3. Check the consultation record in the database:
```sql
SELECT id, prescriptions
FROM consultations
WHERE id = 'YOUR_CONSULTATION_ID';
```

### Expected Database Record
```json
{
  "id": "uuid-here",
  "prescriptions": [
    {
      "drug_name": "Paracetamol",
      "amount": "500mg",
      "method": "oral",
      "frequency": "three times daily",
      "duration": "7 days"
    }
  ]
}
```

## Validation Checklist

- [ ] Prescriptions column exists in database (JSONB type, nullable)
- [ ] Complete prescriptions extract all 5 fields correctly
- [ ] Partial prescriptions use null for missing fields
- [ ] No prescriptions returns empty array `[]`
- [ ] Misspelled drug names are corrected by Claude
- [ ] Prescriptions appear in both `prescriptions` field and `summary_data.prescriptions`
- [ ] Frontend TypeScript types compile without errors
- [ ] Backward compatibility: existing consultations still load correctly

## Troubleshooting

### Prescriptions field is null instead of empty array
- Check that the backend code includes `result.get('prescriptions', [])` with default empty array
- Verify Claude is returning `"prescriptions": []` in the JSON response

### Prescriptions not being extracted
- Check Claude prompt includes prescription extraction instructions
- Verify the transcript mentions medications from the doctor (speaker_0)
- Patient's current medications should NOT be extracted (only doctor's prescriptions)

### TypeScript compilation errors
- Ensure Prescription interface is defined in database.ts
- Verify all interfaces (Consultation, SummaryData, ConsultationDataFromSummary, CreateConsultationInput) include prescriptions field

## Success Criteria

✅ Database migration applied successfully
✅ LLM extracts prescriptions from transcripts
✅ Prescriptions stored in consultations.prescriptions column
✅ TypeScript types updated and compile without errors
✅ Test consultations have prescriptions populated correctly
✅ Backward compatibility maintained for existing consultations
