# Form Table Classification Summary

**Status**: ✅ **COMPLETE**
**Date**: 2026-01-04
**Worktree**: `form-schema-review`

## Overview

This document summarizes the automated classification system that detects which tables and fields in custom medical forms reference data from previous consultations vs. data entered fresh during the current consultation.

## Purpose

When a doctor fills out a medical form (e.g., antenatal form), some tables display **historical data from previous visits** (e.g., past vital signs, previous lab results), while other tables require **new data entry for the current visit**.

The classification system:
1. Automatically identifies which tables reference previous consultations
2. Determines the data source type for each table
3. Maps table columns to external database fields
4. Enables intelligent auto-filling and data presentation in the UI

## Architecture

### Database Schema

**Migration**: `024_add_table_metadata.sql` ✅ Applied

Added `table_metadata` JSONB column to `custom_forms` table to store:
- Data source type for each table
- Whether the table references previous consultations
- Field mappings to external data sources
- Classification confidence scores

```sql
ALTER TABLE custom_forms
ADD COLUMN IF NOT EXISTS table_metadata JSONB;

CREATE INDEX idx_custom_forms_table_metadata
ON custom_forms USING GIN (table_metadata);
```

### Classification System

**Core Component**: `tools/table_classifier.py`

Uses Claude (Sonnet 4) to intelligently classify form tables based on:
- Table name and description
- Column names and field types
- Form context (specialty, patient criteria)
- Temporal indicators (date columns, sequential data)

### Data Source Types

The classifier categorizes tables into 8 types:

1. **visit_history** - Sequential visits/appointments with dates (e.g., antenatal visits tracking BP, weight over time)
   - ✅ **References previous consultations**

2. **lab_results** - Blood tests, lab investigations (CBC, glucose, hemoglobin, liver function tests)
   - May or may not reference previous consultations (depends on table structure)

3. **scan_results** - Imaging results (ultrasound scans, MRI, CT scans, X-rays)
   - May or may not reference previous consultations

4. **medication_history** - Current and past medications with dosage, frequency, start/stop dates
   - ✅ **References previous consultations**

5. **vitals_history** - Vital sign measurements (blood pressure, weight, temperature, heart rate)
   - ✅ **References previous consultations**

6. **vaccination_records** - Immunization tracking (vaccine name, date, batch number)
   - ✅ **References previous consultations**

7. **previous_consultation** - Explicitly references data from a prior form completion
   - ✅ **References previous consultations**

8. **manual_entry** - No external data source, doctor manually fills during current consultation
   - ❌ Does not reference previous consultations

### Auto-Correction Logic

The classifier includes post-processing logic to automatically set `references_previous_consultation: true` for data source types that inherently track historical data:
- `visit_history`
- `vitals_history`
- `medication_history`
- `vaccination_records`

## Classification Results

### Antenatal Form (antenatal_2)

**Total Tables**: 12
**Tables Referencing Previous Consultations**: 2

#### Tables That Reference Previous Consultations

##### 1. visit_records
- **Data Source**: `visit_history`
- **Confidence**: 0.95
- **Columns**: Date, Wt (Kg), BP, Edema Pallor, Gest Age, Fundal Height, SFH (cm), Presentation & Position, FHR Per min, Liquor, Complaints, Medication, INV, Review Date
- **Reasoning**: Tracks sequential antenatal visits with date fields and clinical measurements. The presence of 'Date' and 'Review Date' columns indicates this captures comprehensive antenatal examination findings across multiple visits over time.
- **Field Mappings**:
  ```json
  {
    "date": "visit_date",
    "weight": "weight_kg",
    "bp": "blood_pressure",
    "edema_pallor": "edema_pallor_status",
    "gest_age": "gestational_age",
    "fundal_height": "fundal_height_measurement",
    "sfh": "symphysis_fundal_height_cm",
    "presentation_position": "fetal_presentation_position",
    "fhr": "fetal_heart_rate_bpm",
    "liquor": "amniotic_fluid_status",
    "complaints": "patient_complaints",
    "medication": "prescribed_medications",
    "inv": "investigations_ordered",
    "review_date": "next_visit_date"
  }
  ```

##### 2. tt_immunization
- **Data Source**: `vaccination_records`
- **Confidence**: 0.95
- **Columns**: Dose, Date
- **Reasoning**: Tetanus toxoid immunization record tracking vaccine doses and dates. Table structure with dose and date columns is typical for immunization tracking systems.
- **Field Mappings**:
  ```json
  {
    "dose": "vaccine_dose_number",
    "date": "vaccination_date"
  }
  ```

#### Other Tables (Manual Entry or External Data)

##### 3. serial_labs
- **Data Source**: `lab_results`
- **Confidence**: 0.95
- **Columns**: Date, Gest Age, HB%, URE, DIPSI, ICT, TSH, Platelets
- **Note**: Tracks lab results over time, but classified as lab_results (not previous_consultation) because it stores NEW lab data entered during current visit

##### 4. ultrasound_records
- **Data Source**: `scan_results`
- **Confidence**: 0.95
- **Columns**: Dating Scan, NT Scan, Anomaly Scan, IG Scan, IG Scan, IG Scan, Any Other
- **Note**: Stores ultrasound scan findings

##### 5. booking_labs, special_investigations, screening_tests
- **Data Source**: `lab_results`
- **Confidence**: 0.85-0.95
- **Note**: Various lab test records

##### 6. doppler_study, nst, other_surveillance
- **Data Source**: `scan_results` / `lab_results`
- **Confidence**: 0.85-0.95
- **Note**: Specialized monitoring and surveillance tests

##### 7. referral_records, previous_pregnancies
- **Data Source**: `manual_entry`
- **Confidence**: 0.95
- **Note**: Data entered manually by doctor during consultation

## Integration Points

### 1. Form Creation (custom_forms_api.py)

When a doctor reviews and finalizes a new custom form, the TableClassifier automatically runs:

```python
from tools.table_classifier import TableClassifier

classifier = TableClassifier()
table_metadata = await classifier.classify_all_tables(
    form_schema=request.form_schema,
    form_metadata={
        "form_name": request.form_name,
        "specialty": request.specialty,
        "description": request.patient_criteria
    }
)

# Store metadata in database
form.table_metadata = table_metadata
```

### 2. Form Auto-Filling (Future Integration)

The `table_metadata` can be used to:
- Auto-populate tables marked as `references_previous_consultation: true` with historical data
- Use `external_data_mappings` to fetch the correct database fields
- Display read-only historical data vs. editable current data
- Show trends and comparisons with previous visits

**Example**: For `visit_records` table:
```python
if table_metadata["tables"]["visit_records"]["references_previous_consultation"]:
    # Fetch historical visit data
    mappings = table_metadata["tables"]["visit_records"]["external_data_mappings"]
    previous_visits = await fetch_patient_visits(patient_id)

    # Auto-populate table with historical data
    for visit in previous_visits:
        table_row = {
            "Date": visit[mappings["date"]],
            "Wt (Kg)": visit[mappings["weight"]],
            "BP": visit[mappings["bp"]],
            # ... etc
        }
```

### 3. UI Presentation

Frontend can use `table_metadata` to:
- Show "📅 Historical Data" indicator for tables referencing previous consultations
- Display comparison views (current vs. previous values)
- Highlight changes from last visit
- Lock certain tables to read-only if they're purely historical

## Scripts

### Classification Script

**Location**: `tools/classify_existing_forms.py`

Classifies all existing custom forms and updates their `table_metadata`:

```bash
python tools/classify_existing_forms.py
```

**Output**:
- Classification results for each table
- Summary statistics (total forms, total tables, tables referencing previous consultations)
- Detailed report of cross-consultation references

## Key Insights

### What We Learned

1. **Not all tables with dates reference previous consultations**
   - Tables like `serial_labs` track NEW data over time (entered during current visit)
   - Tables like `visit_records` display HISTORICAL data from previous visits
   - The distinction is important for UI/UX design

2. **Auto-correction is essential**
   - LLM sometimes misses that `visit_history` inherently references previous consultations
   - Post-processing logic ensures consistency

3. **Field mappings enable smart auto-fill**
   - Knowing that "BP" maps to "blood_pressure" enables precise data fetching
   - Column name variations are normalized through mappings

4. **Confidence scores help with edge cases**
   - Lower confidence (<0.8) indicates ambiguous classification
   - Can trigger manual review or alternative UI presentation

## Next Steps

### Immediate (for Production)

1. **Classify OB/GYN Specialty Forms**
   - Run classification on built-in specialty forms (not just custom forms)
   - Store metadata in form definition files

2. **Implement Auto-Fill in Frontend**
   - Use `table_metadata` to populate historical tables
   - Fetch data using `external_data_mappings`
   - Show read-only historical data with edit option for corrections

3. **Add UI Indicators**
   - Show "📅 Historical Data" badge on tables with `references_previous_consultation: true`
   - Display "Last Updated: [date]" for historical tables
   - Add comparison views (current vs. previous)

### Future Enhancements

1. **Incremental Classification**
   - Classify new forms automatically when created
   - Re-classify when form schema changes

2. **Confidence-Based Features**
   - High confidence (>0.9): Auto-fill enabled by default
   - Medium confidence (0.7-0.9): Show suggestion, require doctor confirmation
   - Low confidence (<0.7): Manual entry only, no auto-fill

3. **Advanced Data Sources**
   - Integrate with external lab systems
   - Pull imaging results from PACS systems
   - Sync medication lists with pharmacy databases

4. **Analytics**
   - Track which tables are most commonly auto-filled
   - Identify frequently modified historical data (indicates corrections needed)
   - Measure time saved through auto-fill

## Files Modified/Created

### New Files
- ✅ `tools/table_classifier.py` - LLM-based table classifier
- ✅ `tools/classify_existing_forms.py` - Batch classification script
- ✅ `migrations/024_add_table_metadata.sql` - Database schema change
- ✅ `FORM_TABLE_CLASSIFICATION_SUMMARY.md` - This document

### Modified Files
- ✅ `custom_forms_api.py` - Integrated classifier into form creation flow

### Database Changes
- ✅ Added `table_metadata` JSONB column to `custom_forms` table
- ✅ Created GIN index on `table_metadata` for fast JSONB queries

## Testing

### Manual Testing

```bash
# Classify all existing forms
python tools/classify_existing_forms.py

# Check classification results in database
psql> SELECT form_name, table_metadata->'tables'->'visit_records'
      FROM custom_forms
      WHERE form_name = 'antenatal_2';
```

### Expected Results

For `antenatal_2` form:
- ✅ 12 tables classified
- ✅ 2 tables marked as referencing previous consultations
- ✅ All tables have confidence scores ≥ 0.85
- ✅ Field mappings generated for all tables

## Troubleshooting

### Issue: Classification returns empty metadata

**Cause**: ANTHROPIC_API_KEY not set

**Solution**:
```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### Issue: All tables classified as "manual_entry"

**Cause**: LLM unable to parse table structure

**Solution**: Check form_schema format, ensure table fields have proper structure:
```json
{
  "name": "table_name",
  "input_type": "table",
  "column_names": [...],
  "row_fields": [...]
}
```

### Issue: Confidence scores very low (<0.5)

**Cause**: Ambiguous table structure or missing context

**Solution**: Add more descriptive table names and descriptions in form schema

## References

- **TableClassifier Code**: `tools/table_classifier.py`
- **Classification Script**: `tools/classify_existing_forms.py`
- **Migration File**: `migrations/024_add_table_metadata.sql`
- **Integration Point**: `custom_forms_api.py` (lines 393-402)
- **Shared Health Records**: `SHARED_HEALTH_RECORDS.md`

---

**Document Version**: 1.0
**Last Updated**: 2026-01-04
**Author**: Claude Sonnet 4.5
**Status**: ✅ Classification System Complete, Ready for Frontend Integration
