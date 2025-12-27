# Shared Patient Health Records Architecture

**Status**: ✅ **IMPLEMENTED** (Migration applied 2025-12-23)

## Overview

The shared health records architecture provides normalized, structured storage for patient health data that can be shared across all medical specialties (OB/GYN, Cardiology, Neurology, etc.). This replaces the previous TEXT-based storage in the `patients` table with proper relational tables.

## Architecture Goals

1. **Eliminate Data Duplication**: Single source of truth for patient health data
2. **Enable Cross-Specialty Sharing**: Vitals, medications, allergies, and conditions available to all specialties
3. **Support Temporal Tracking**: Track when medications started/stopped, when conditions were diagnosed
4. **Maintain Data Quality**: Proper data types, constraints, and validation
5. **Enable Versioning**: Historical tracking of health data changes

## Database Schema

### Core Tables

#### 1. `patient_vitals`
**Purpose**: Timestamped vital signs shared across all specialties

**Key Columns**:
- `id`: UUID primary key
- `patient_id`: Foreign key to patients table
- `recorded_at`: Timestamp when vitals were taken
- `recorded_by`: UUID of doctor/user who recorded vitals
- `appointment_id`: Optional link to appointment
- `consultation_form_id`, `consultation_form_type`: Link to specialty form
- Vitals: `systolic_bp`, `diastolic_bp`, `heart_rate`, `respiratory_rate`, `temperature_celsius`, `spo2`, `blood_glucose_mg_dl`
- Physical: `weight_kg`, `height_cm`, `bmi` (auto-calculated)
- `notes`: Additional observations
- `source_form_status`: Status of form when vitals were recorded

**Features**:
- BMI auto-calculated using PostgreSQL generated column
- Indexed on `patient_id`, `recorded_at`, `appointment_id`
- RLS policies: Patients can view own vitals, doctors can view/create/update all

#### 2. `patient_medications`
**Purpose**: Versioned medication list with temporal tracking

**Key Columns**:
- `id`: UUID primary key
- `patient_id`: Foreign key to patients table
- `medication_name`, `dosage`, `frequency`, `route`: Medication details
- `started_date`, `stopped_date`: Temporal tracking
- `status`: active | stopped | completed
- `prescribed_by`: UUID of prescribing doctor
- `prescribed_at`: Timestamp of prescription
- `appointment_id`: Optional link to appointment
- `indication`: Why medication was prescribed (e.g., "Type 2 Diabetes")
- `notes`: Additional information

**Features**:
- View `patient_active_medications`: Filters to only active medications
- Indexed on `patient_id`, `status`, `prescribed_at`
- RLS policies: Patients can view own, doctors can manage all

#### 3. `patient_allergies`
**Purpose**: Allergy list with severity tracking

**Key Columns**:
- `id`: UUID primary key
- `patient_id`: Foreign key to patients table
- `allergen`: Allergen name (e.g., "Penicillin", "Peanuts")
- `allergen_category`: medication | food | environmental | other
- `reaction`: Description of reaction
- `severity`: mild | moderate | severe | unknown
- `onset_date`: When allergy was first identified
- `status`: active | resolved | questioned
- `recorded_by`, `recorded_at`: Who/when recorded
- `notes`: Additional information

**Features**:
- View `patient_active_allergies`: Filters to only active allergies
- Indexed on `patient_id`, `status`
- RLS policies: Patients can view own, doctors can manage all

#### 4. `patient_conditions`
**Purpose**: Medical conditions/diagnoses

**Key Columns**:
- `id`: UUID primary key
- `patient_id`: Foreign key to patients table
- `condition_name`: Condition/diagnosis name
- `icd10_code`: Optional ICD-10 diagnostic code
- `diagnosed_date`: When condition was diagnosed
- `status`: active | resolved | chronic | in_remission
- `diagnosed_by`: UUID of diagnosing doctor
- `appointment_id`: Optional link to appointment
- `notes`: Additional information

**Features**:
- Indexed on `patient_id`, `status`
- RLS policies: Patients can view own, doctors can manage all

#### 5. `patient_lab_results`
**Purpose**: Structured lab test results

**Key Columns**:
- `id`: UUID primary key
- `patient_id`: Foreign key to patients table
- `test_date`: Date of test
- `test_type`: Type of test (e.g., "Complete Blood Count", "HbA1c")
- `ordered_by`: UUID of ordering doctor
- `appointment_id`: Optional link to appointment
- `results`: JSONB field for flexible storage of test results
- `interpretation`: Clinical interpretation of results
- `notes`: Additional notes
- `lab_name`: Name of lab that performed test

**Features**:
- JSONB storage allows flexible structure for different test types
- GIN index on `results` JSONB field for fast queries
- Indexed on `patient_id`, `test_date`, `test_type`
- RLS policies: Patients can view own, doctors can manage all

### Integration with OB/GYN Forms

The `obgyn_consultation_forms` table has been updated with reference columns:

- `vitals_record_id`: Foreign key to `patient_vitals.id`
- `lab_results_record_ids`: Array of UUIDs referencing `patient_lab_results.id`

This allows forms to reference shared health records instead of duplicating data.

## Data Migration

The migration automatically migrated existing data from the `patients` table:

```sql
-- Medications migrated from patients.current_medications to patient_medications
-- Allergies migrated from patients.allergies to patient_allergies
-- Conditions migrated from patients.current_conditions to patient_conditions
```

**Migration Statistics** (as of 2025-12-23):
- ✅ 1 medication record migrated
- ✅ 0 allergy records (patients had "None known")
- ✅ 2 condition records migrated
- ✅ 2 patients marked as `migrated_to_shared_health_record = true`

Migrated records are marked with notes like:
- `"MIGRATED FROM patients.current_medications: Elvanse 50mg, Thyroxin 75mcg"`
- `"MIGRATED FROM patients.allergies"`
- `"MIGRATED FROM patients.current_conditions"`

## API Endpoints

### Patient Vitals

```http
POST   /api/patient-vitals                       # Create vitals record
GET    /api/patient-vitals/patient/{patient_id}  # Get patient's vitals (limit=10)
GET    /api/patient-vitals/{vitals_id}           # Get specific vitals record
```

### Patient Medications

```http
POST   /api/patient-medications                      # Create medication record
GET    /api/patient-medications/patient/{patient_id} # Get patient's medications (filter by status)
PUT    /api/patient-medications/{medication_id}      # Update medication (e.g., stop date)
```

### Patient Allergies

```http
POST   /api/patient-allergies                      # Create allergy record
GET    /api/patient-allergies/patient/{patient_id} # Get patient's allergies (default: active only)
PUT    /api/patient-allergies/{allergy_id}         # Update allergy (e.g., mark resolved)
```

### Patient Conditions

```http
POST   /api/patient-conditions                      # Create condition record
GET    /api/patient-conditions/patient/{patient_id} # Get patient's conditions (filter by status)
PUT    /api/patient-conditions/{condition_id}       # Update condition (e.g., mark resolved)
```

### Patient Lab Results

```http
POST   /api/patient-lab-results                      # Create lab result record
GET    /api/patient-lab-results/patient/{patient_id} # Get patient's lab results (filter by test_type, limit=20)
GET    /api/patient-lab-results/{result_id}          # Get specific lab result
```

### Unified Health Summary

```http
GET    /api/patient-health-summary/{patient_id}     # Get comprehensive health summary
```

Returns:
```json
{
  "patient_id": "uuid",
  "latest_vitals": { ... },
  "active_medications": [ ... ],
  "active_allergies": [ ... ],
  "active_conditions": [ ... ],
  "recent_lab_results": [ ... ]
}
```

## Security (RLS Policies)

All tables have Row-Level Security (RLS) enabled with the following policies:

### For Patients:
- **View**: Can view their own records (matched by `patient_id` → `patients.user_id` → `auth.uid()`)

### For Doctors:
- **View**: Can view all patient records (if `doctors.is_active = true`)
- **Create**: Can create records for any patient
- **Update**: Can update records (vitals: only within 24 hours of recording)
- **Manage**: Full CRUD access to medications, allergies, conditions, lab results

## Usage Examples

### Creating Vitals During Consultation

```python
# In OB/GYN consultation form handler
vitals_data = {
    "patient_id": form.patient_id,
    "appointment_id": form.appointment_id,
    "consultation_form_id": form.id,
    "consultation_form_type": "obgyn",
    "systolic_bp": 120,
    "diastolic_bp": 80,
    "heart_rate": 72,
    "temperature_celsius": 36.5,
    "weight_kg": 65.0,
    "height_cm": 165.0,
    "source_form_status": "completed"
}

# Create vitals record
vitals = await create_patient_vitals(vitals_data)

# Link to form
form.vitals_record_id = vitals.id
```

### Recording a New Medication

```python
medication_data = {
    "patient_id": patient_id,
    "medication_name": "Metformin",
    "dosage": "500mg",
    "frequency": "Twice daily with meals",
    "route": "Oral",
    "started_date": "2025-12-23",
    "status": "active",
    "appointment_id": appointment_id,
    "indication": "Type 2 Diabetes Mellitus",
    "notes": "Monitor blood glucose levels"
}

medication = await create_patient_medication(medication_data)
```

### Stopping a Medication

```python
updates = {
    "stopped_date": "2025-12-23",
    "status": "stopped",
    "notes": "Discontinued due to side effects"
}

await update_patient_medication(medication_id, updates)
```

### Recording Lab Results

```python
lab_result_data = {
    "patient_id": patient_id,
    "test_date": "2025-12-23",
    "test_type": "Complete Blood Count",
    "appointment_id": appointment_id,
    "results": {
        "WBC": {"value": 7.5, "unit": "10^9/L", "reference": "4.5-11.0"},
        "RBC": {"value": 4.8, "unit": "10^12/L", "reference": "4.5-5.5"},
        "Hemoglobin": {"value": 14.2, "unit": "g/dL", "reference": "13.5-17.5"},
        "Platelets": {"value": 250, "unit": "10^9/L", "reference": "150-400"}
    },
    "interpretation": "All values within normal range",
    "lab_name": "City Hospital Laboratory"
}

lab_result = await create_patient_lab_result(lab_result_data)
```

## Frontend Integration

### React Hook Example

```typescript
// usePatientHealthSummary.ts
export const usePatientHealthSummary = (patientId: string) => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const response = await fetch(`/api/patient-health-summary/${patientId}`);
        const data = await response.json();
        setSummary(data);
      } catch (error) {
        console.error('Error fetching health summary:', error);
      } finally {
        setLoading(false);
      }
    };

    if (patientId) {
      fetchSummary();
    }
  }, [patientId]);

  return { summary, loading };
};
```

### Component Example

```typescript
const PatientHealthDashboard = ({ patientId }) => {
  const { summary, loading } = usePatientHealthSummary(patientId);

  if (loading) return <LoadingSpinner />;

  return (
    <div>
      <VitalsCard vitals={summary.latest_vitals} />
      <MedicationsList medications={summary.active_medications} />
      <AllergiesAlert allergies={summary.active_allergies} />
      <ConditionsList conditions={summary.active_conditions} />
      <LabResultsTimeline results={summary.recent_lab_results} />
    </div>
  );
};
```

## Next Steps

### Immediate (Required for Production)

1. **Debug RLS Policies**: API using service key should bypass RLS, investigate why queries return empty
2. **Create Frontend Components**:
   - `VitalsEntryForm.tsx` - For recording vitals
   - `MedicationManager.tsx` - For managing medications
   - `AllergyManager.tsx` - For managing allergies
   - `LabResultsViewer.tsx` - For viewing lab results

3. **Update OB/GYN Forms**:
   - Modify form submission to create `patient_vitals` records
   - Link vitals to form using `vitals_record_id`
   - Remove duplicate vital signs from form JSONB fields

4. **Data Validation**:
   - Add frontend validation for vital signs ranges
   - Validate medication dosages and frequencies
   - Validate lab result formats

### Future Enhancements

1. **Additional Specialty Forms**:
   - Cardiology consultation forms
   - Neurology consultation forms
   - Dermatology consultation forms
   - All can reference the same shared health record tables

2. **Advanced Features**:
   - Medication interaction checking
   - Allergy contraindication alerts
   - Trending vitals visualization
   - Lab result comparisons over time

3. **Integration with Clinical Decision Support**:
   - Use health summary in consultation analysis
   - Include vitals trends in recommendations
   - Alert for medication-condition interactions

4. **Audit Trail**:
   - Track who viewed/modified health records
   - Maintain complete change history
   - Support HIPAA compliance requirements

5. **Data Export**:
   - Export health summary as PDF
   - Generate medication lists for patients
   - Create lab result reports

## Migration Files

- **Migration File**: `/Users/dgordon/aneya/aneya-backend/migrations/002_create_shared_health_record_tables.sql`
- **Applied**: 2025-12-23
- **Status**: ✅ Complete

## Testing

### Database Tests

```bash
# Verify tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name LIKE 'patient_%';

# Check migrated data
SELECT COUNT(*) FROM patient_medications WHERE notes LIKE 'MIGRATED%';
SELECT COUNT(*) FROM patient_conditions WHERE notes LIKE 'MIGRATED%';

# Test vitals with BMI calculation
INSERT INTO patient_vitals (patient_id, weight_kg, height_cm)
VALUES ('patient-uuid', 70.0, 170.0)
RETURNING id, bmi;
```

### API Tests

```bash
# Health summary
curl http://localhost:8000/api/patient-health-summary/{patient_id}

# Create vitals
curl -X POST http://localhost:8000/api/patient-vitals \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "...", "systolic_bp": 120, "diastolic_bp": 80}'

# Get medications
curl http://localhost:8000/api/patient-medications/patient/{patient_id}?status=active
```

## Troubleshooting

### RLS Policy Issues

If API queries return empty despite data existing:

1. Check service key is being used (not anon key)
2. Verify `get_supabase_client()` uses `SUPABASE_SERVICE_KEY`
3. Test query directly with service key:
   ```python
   from supabase import create_client
   supabase = create_client(url, service_key)
   result = supabase.table("patient_vitals").select("*").execute()
   ```

### Migration Issues

If migration fails:

1. Check all referenced tables exist (`patients`, `appointments`, `auth.users`)
2. Verify Supabase project has UUID extension enabled
3. Check for existing data that violates constraints

### Performance Issues

If queries are slow:

1. Check indexes are created: `\d patient_vitals` in psql
2. Verify query is using indexes: `EXPLAIN ANALYZE SELECT ...`
3. Consider adding composite indexes for common query patterns

## References

- **OB/GYN Forms Documentation**: `/Users/dgordon/aneya/aneya-backend/OBGYN_FORMS_API.md`
- **Database Schema**: See Supabase Table Editor
- **API Code**: `/Users/dgordon/aneya/aneya-backend/api.py` (lines 2912-3528)
- **Migration File**: `/Users/dgordon/aneya/aneya-backend/migrations/002_create_shared_health_record_tables.sql`

---

**Document Version**: 1.0
**Last Updated**: 2025-12-23
**Author**: Claude (Sonnet 4.5)
**Status**: Architecture Implemented, Frontend Integration Pending
