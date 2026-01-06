# Patient Context in Form Filling

## Overview

Enhanced the form auto-fill feature to include comprehensive patient details (demographics, medications, conditions, allergies, previous consultations) in the LLM context when extracting fields from consultation transcripts.

## Implementation Date

2026-01-05

## Changes Made

### 1. New Helper Function: `fetch_patient_context()`

**Location**: `api.py:4832-4981`

Created a comprehensive patient context fetcher that retrieves:

- **Demographics**: name, age, sex, date of birth, height, weight
- **Current Medications**: active medications from `patient_medications` table
  - Includes: medication name, dosage, frequency, indication
- **Medical Conditions**: active/chronic conditions from `patient_conditions` table
  - Includes: condition name, ICD-10 code, diagnosis date, status
- **Allergies**: active allergies from `patient_allergies` table
  - Includes: allergen, category, reaction, severity
- **Previous Forms**: Last 3 completed consultation forms
  - Includes: form type, specialty, completion date

**Key Features**:
- Gracefully handles missing data
- Falls back to legacy text fields in `patients` table
- Returns empty context on error rather than failing
- Logs summary of fetched data

### 2. Updated `auto_fill_consultation_form` Endpoint

**Location**: `api.py:4727-4729`

Added patient context fetching before form field extraction:

```python
# Step 4b: Fetch comprehensive patient context
patient_context = fetch_patient_context(request.patient_id)
patient_context['patient_id'] = request.patient_id  # Keep patient_id for backward compatibility
```

This ensures patient details are available when extracting form fields.

### 3. Enhanced `extract_form_fields` LLM Prompt

**Location**: `api.py:4432-4507`

Updated the system prompt to include patient context:

**Added Patient Profile Section**:
```
Patient Profile:
Name: [name], Age: [age] years, Sex: [sex]

Current Medications:
- [medication] ([dosage])
...

Medical History:
- [condition] ([status])
...

Allergies:
- [allergen] ([severity] severity)
...
```

**New Rule Added**:
> Use patient context (demographics, medications, conditions, allergies) to validate and contextualize extracted information

## Benefits

1. **Improved Extraction Accuracy**
   - LLM can validate extracted values against patient demographics (e.g., age-appropriate ranges)
   - Better understanding of patient history for context

2. **Enhanced Safety**
   - Allergies are prominently displayed in the prompt
   - Current medications help identify potential drug interactions

3. **Better Clinical Context**
   - Medical history helps interpret symptoms
   - Previous forms provide continuity of care

4. **Backward Compatible**
   - Patient context is optional (gracefully handles missing data)
   - Existing functionality remains unchanged if context fetch fails

## Testing

Created comprehensive test suite: `test_patient_context_form_filling.py`

### Test 1: Fetch Patient Context
- ✅ Verifies data structure from Supabase
- ✅ Confirms all expected fields are present
- ✅ Tests with real patient data

### Test 2: Patient Context in Prompt
- ✅ Validates text formatting for LLM
- ✅ Ensures all critical information is included
- ✅ Confirms proper structure

**Test Results**: All tests passed ✅

## Data Sources

| Data Type | Primary Source | Fallback |
|-----------|---------------|----------|
| Demographics | `patients` table | - |
| Medications | `patient_medications` table | `patients.current_medications` (text) |
| Conditions | `patient_conditions` table | `patients.current_conditions` (text) |
| Allergies | `patient_allergies` table | `patients.allergies` (text) |
| Previous Forms | `consultation_forms` table | - |

## Example Patient Context Output

```json
{
  "demographics": {
    "name": "Juliet Bangari",
    "sex": "Female",
    "age_years": 36,
    "date_of_birth": "1989-06-06",
    "height_cm": null,
    "weight_kg": null
  },
  "medications": [
    {
      "name": "Metformin",
      "dosage": "500mg",
      "frequency": "twice daily",
      "indication": "Type 2 Diabetes"
    }
  ],
  "conditions": [
    {
      "name": "Type 2 Diabetes",
      "icd10_code": "E11",
      "diagnosed_date": "2020-03-15",
      "status": "chronic"
    }
  ],
  "allergies": [
    {
      "allergen": "Penicillin",
      "category": "medication",
      "reaction": "Rash",
      "severity": "moderate"
    }
  ],
  "previous_forms": [
    {
      "form_type": "obgyn",
      "specialty": "obstetrics_gynecology",
      "date": "2025-12-20T10:30:00Z",
      "has_data": true
    }
  ]
}
```

## Performance Considerations

- **Database Queries**: 5 additional queries per form fill
  - 1 for demographics
  - 1 for medications
  - 1 for conditions
  - 1 for allergies
  - 1 for previous forms

- **Latency Impact**: Minimal (~100-200ms)
  - Queries run sequentially in `fetch_patient_context()`
  - Could be optimized with parallel queries if needed

- **Token Usage**: Slight increase in LLM prompt size
  - ~100-300 additional tokens depending on patient history
  - Helps improve extraction quality

## Future Enhancements

1. **Caching**: Cache patient context for same patient across multiple chunks
2. **Parallel Queries**: Fetch all patient data in parallel
3. **Selective Loading**: Only load relevant context based on form type
4. **Historical Lab Results**: Include recent lab values when relevant
5. **Medication Reconciliation**: Flag discrepancies between mentioned and recorded medications

## Files Modified

- `aneya-backend/api.py` (3 sections):
  - Added `fetch_patient_context()` helper function
  - Updated `auto_fill_consultation_form` to fetch context
  - Enhanced `extract_form_fields` LLM prompt

## Files Created

- `aneya-backend/test_patient_context_form_filling.py` - Test suite
- `aneya-backend/PATIENT_CONTEXT_FORM_FILLING.md` - This documentation

## Migration Notes

No database migrations required. Uses existing tables and columns.

## Related Documentation

- `FORM_AUTOFILL_COMPLETE.md` - Original form auto-fill implementation
- `CUSTOM_FORMS_INTEGRATION.md` - Custom forms system
- `migrations/005_create_patient_demographics.sql` - Patient demographics table
