# OB/GYN Forms Architecture

## Current Correct Architecture (Migration 002 - Dec 23, 2025)

The OB/GYN forms use **normalized shared health records** to eliminate data duplication across specialties.

### Data Storage Strategy

**1. Shared Patient Health Records (Normalized Tables)**

Data that is shared across ALL specialties (OB/GYN, Cardiology, etc.) is stored in normalized tables:

| Table | Purpose | Fields |
|-------|---------|--------|
| `patient_vitals` | Vital signs with timestamps | BP, HR, RR, temp, SpO2, glucose, weight, height, BMI |
| `patient_medications` | Active medication list | medication_name, dosage, frequency, started_date, stopped_date |
| `patient_allergies` | Allergy tracking | allergen, allergen_category, reaction, severity |
| `patient_conditions` | Medical diagnoses | condition_name, icd10_code, diagnosed_date, status |
| `patient_lab_results` | Lab test results | test_type, test_date, results (JSONB), interpretation |

**2. OB/GYN Forms Metadata Table**

The `obgyn_forms` table stores:
- Form metadata (patient_id, appointment_id, form_type, status)
- Foreign keys linking to shared health records:
  - `vitals_record_id` → links to patient_vitals(id)
  - `lab_results_record_ids` → array of patient_lab_results IDs
- OB/GYN-specific fields (menstrual history, pregnancy status, etc.)

**⚠️ DEPRECATED:** The `form_data` JSONB column from migration 001 should NOT be used.

### Data Flow

```
OBGynPreConsultationForm
        ↓
1. Create vitals record in patient_vitals table (via backend API)
2. Create medications in patient_medications table
3. Create allergies in patient_allergies table
4. Create OB/GYN form metadata in obgyn_forms with FKs:
   - vitals_record_id = ID from step 1
   - OB/GYN-specific fields stored directly
        ↓
Result: Shared health data accessible across all specialties
```

### Backend API Endpoints (Already Implemented)

✅ `/api/patient-vitals` - POST/GET vitals
✅ `/api/patient-medications` - POST/GET medications
✅ `/api/patient-allergies` - POST/GET allergies
✅ `/api/patient-conditions` - POST/GET conditions
✅ `/api/patient-lab-results` - POST/GET lab results
✅ `/api/patients/{id}/health-record` - GET comprehensive health record

### Frontend Implementation (NEEDS UPDATE)

❌ **Current (Broken):** Frontend writes directly to `obgyn_forms` table
❌ **Current (Broken):** Uses JSONB form_data or flattened columns
❌ **Current (Broken):** Duplicates vitals/meds/allergies data

✅ **Should be:**
1. Use `usePatientVitals` hook to write to patient_vitals
2. Use `usePatientMedications` hook (needs creation) for medications
3. Use `usePatientAllergies` hook (needs creation) for allergies
4. Store OB/GYN-specific fields in `obgyn_forms` with FK references

### Database Schema

```sql
-- Metadata and OB/GYN-specific fields
CREATE TABLE obgyn_forms (
  id UUID PRIMARY KEY,
  patient_id UUID REFERENCES patients(id),
  appointment_id UUID REFERENCES appointments(id),

  -- Foreign keys to shared health records
  vitals_record_id UUID REFERENCES patient_vitals(id),
  lab_results_record_ids UUID[],

  -- OB/GYN-specific fields
  form_type TEXT CHECK (form_type IN ('pre_consultation', 'during_consultation')),
  last_menstrual_period DATE,
  cycle_regularity TEXT,
  pregnancy_status TEXT,
  menopause_status TEXT,
  contraception_status TEXT,
  -- ... other OB/GYN-specific fields

  -- Form metadata
  status TEXT CHECK (status IN ('draft', 'partial', 'completed')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  created_by UUID REFERENCES auth.users(id),
  updated_by UUID REFERENCES auth.users(id)
);
```

### Migration Status

- ✅ Migration 001: Created obgyn_forms with JSONB (DEPRECATED)
- ✅ Migration 002: Created normalized patient health record tables
- ✅ Migration 002: Added FK columns to obgyn_forms
- ❌ **Missing:** Migration to drop form_data JSONB column
- ❌ **Missing:** Database VIEW to aggregate form data with health records

### What Needs to Be Fixed

1. **Apply migrations to Supabase**
   - Run migration 002 if not already applied
   - Verify normalized tables exist
   - Verify obgyn_forms has FK columns

2. **Update Frontend**
   - Modify OBGynPreConsultationForm to use normalized tables
   - Create hooks for medications/allergies/conditions
   - Update obgyn_forms writes to include FK references

3. **Optional: Create Database View**
   ```sql
   CREATE VIEW obgyn_form_complete AS
   SELECT
     f.*,
     v.systolic_bp, v.diastolic_bp, v.heart_rate, v.temperature_celsius,
     v.weight_kg, v.height_cm, v.bmi,
     -- Join with medications, allergies, conditions
   FROM obgyn_forms f
   LEFT JOIN patient_vitals v ON f.vitals_record_id = v.id
   ```

### Benefits of This Architecture

1. ✅ **No data duplication** - Vitals recorded once, used everywhere
2. ✅ **Cross-specialty continuity** - Cardiology can see OB/GYN-recorded vitals
3. ✅ **Temporal tracking** - All health records have timestamps
4. ✅ **Medication reconciliation** - Single source of truth for current meds
5. ✅ **Better analytics** - Query all vitals across time, not per-form

---

**Last Updated:** 2025-12-27
**Status:** Architecture defined, partial implementation, frontend needs update
