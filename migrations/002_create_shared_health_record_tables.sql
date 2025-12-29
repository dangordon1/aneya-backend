-- Migration: Create Shared Patient Health Record Tables
-- Description: Creates normalized tables for patient health data shared across all specialties
-- Created: 2025-12-23
-- Purpose: Eliminate data duplication and enable shared health records across OB/GYN, Cardiology, etc.

-- ==============================================================================
-- 1. PATIENT VITALS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS patient_vitals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,

  -- Context: Who, when, where
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  recorded_by UUID REFERENCES auth.users(id),
  appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
  consultation_form_id UUID NULL,
  consultation_form_type TEXT NULL CHECK (consultation_form_type IN ('obgyn', 'cardiology', 'general', 'neurology', 'dermatology')),

  -- Vital Signs (all nullable - record what's available)
  systolic_bp INTEGER CHECK (systolic_bp > 0 AND systolic_bp < 300),
  diastolic_bp INTEGER CHECK (diastolic_bp > 0 AND diastolic_bp < 200),
  heart_rate INTEGER CHECK (heart_rate > 0 AND heart_rate < 300),
  respiratory_rate INTEGER CHECK (respiratory_rate > 0 AND respiratory_rate < 100),
  temperature_celsius NUMERIC(4,1) CHECK (temperature_celsius > 30 AND temperature_celsius < 45),
  spo2 INTEGER CHECK (spo2 >= 0 AND spo2 <= 100),
  blood_glucose_mg_dl INTEGER CHECK (blood_glucose_mg_dl > 0 AND blood_glucose_mg_dl < 1000),

  -- Physical Measurements
  weight_kg NUMERIC(5,2) CHECK (weight_kg > 0 AND weight_kg < 500),
  height_cm NUMERIC(5,2) CHECK (height_cm > 0 AND height_cm < 300),
  bmi NUMERIC(4,1) GENERATED ALWAYS AS (
    CASE WHEN height_cm > 0 THEN weight_kg / ((height_cm / 100.0) ^ 2) ELSE NULL END
  ) STORED,

  -- Metadata
  notes TEXT,
  source_form_status TEXT CHECK (source_form_status IN ('draft', 'partial', 'completed', 'final')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for patient_vitals
CREATE INDEX IF NOT EXISTS idx_patient_vitals_patient_id ON patient_vitals(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_vitals_recorded_at ON patient_vitals(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_patient_vitals_appointment_id ON patient_vitals(appointment_id) WHERE appointment_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_patient_vitals_form_reference ON patient_vitals(consultation_form_id, consultation_form_type) WHERE consultation_form_id IS NOT NULL;

-- Auto-update trigger for updated_at
CREATE OR REPLACE FUNCTION update_patient_vitals_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_patient_vitals_updated_at ON patient_vitals;
CREATE TRIGGER trigger_patient_vitals_updated_at
BEFORE UPDATE ON patient_vitals
FOR EACH ROW
EXECUTE FUNCTION update_patient_vitals_updated_at();

-- Comments
COMMENT ON TABLE patient_vitals IS 'Timestamped vital signs shared across all specialties';
COMMENT ON COLUMN patient_vitals.recorded_by IS 'Doctor/user who recorded these vitals';
COMMENT ON COLUMN patient_vitals.consultation_form_type IS 'Which specialty form recorded these vitals';
COMMENT ON COLUMN patient_vitals.source_form_status IS 'Status of form when vitals were recorded (draft/partial/completed/final)';

-- ==============================================================================
-- 2. PATIENT MEDICATIONS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS patient_medications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,

  -- Medication Details
  medication_name TEXT NOT NULL,
  dosage TEXT NOT NULL,
  frequency TEXT NOT NULL,
  route TEXT,

  -- Temporal Tracking
  started_date DATE NOT NULL DEFAULT CURRENT_DATE,
  stopped_date DATE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'stopped', 'completed')),

  -- Context
  prescribed_by UUID REFERENCES auth.users(id),
  prescribed_at TIMESTAMPTZ DEFAULT now(),
  appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,

  -- Metadata
  indication TEXT,
  notes TEXT,
  source_form_status TEXT CHECK (source_form_status IN ('draft', 'partial', 'completed', 'final')),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for patient_medications
CREATE INDEX IF NOT EXISTS idx_patient_medications_patient_id ON patient_medications(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_medications_status ON patient_medications(patient_id, status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_patient_medications_prescribed_at ON patient_medications(prescribed_at DESC);

-- View for currently active medications
CREATE OR REPLACE VIEW patient_active_medications AS
SELECT * FROM patient_medications
WHERE status = 'active' AND (stopped_date IS NULL OR stopped_date > CURRENT_DATE);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_patient_medications_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_patient_medications_updated_at ON patient_medications;
CREATE TRIGGER trigger_patient_medications_updated_at
BEFORE UPDATE ON patient_medications
FOR EACH ROW
EXECUTE FUNCTION update_patient_medications_updated_at();

-- Comments
COMMENT ON TABLE patient_medications IS 'Versioned medication list with start/stop dates, shared across specialties';
COMMENT ON COLUMN patient_medications.indication IS 'Why this medication was prescribed (e.g., "Type 2 Diabetes")';

-- ==============================================================================
-- 3. PATIENT ALLERGIES TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS patient_allergies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,

  -- Allergy Details
  allergen TEXT NOT NULL,
  allergen_category TEXT CHECK (allergen_category IN ('medication', 'food', 'environmental', 'other')),
  reaction TEXT,
  severity TEXT CHECK (severity IN ('mild', 'moderate', 'severe', 'unknown')),

  -- Temporal Tracking
  onset_date DATE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'resolved', 'questioned')),

  -- Context
  recorded_by UUID REFERENCES auth.users(id),
  recorded_at TIMESTAMPTZ DEFAULT now(),

  -- Metadata
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for patient_allergies
CREATE INDEX IF NOT EXISTS idx_patient_allergies_patient_id ON patient_allergies(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_allergies_status ON patient_allergies(patient_id, status) WHERE status = 'active';

-- View for active allergies
CREATE OR REPLACE VIEW patient_active_allergies AS
SELECT * FROM patient_allergies WHERE status = 'active';

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_patient_allergies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_patient_allergies_updated_at ON patient_allergies;
CREATE TRIGGER trigger_patient_allergies_updated_at
BEFORE UPDATE ON patient_allergies
FOR EACH ROW
EXECUTE FUNCTION update_patient_allergies_updated_at();

-- Comments
COMMENT ON TABLE patient_allergies IS 'Versioned allergy list with severity tracking, shared across specialties';

-- ==============================================================================
-- 4. PATIENT CONDITIONS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS patient_conditions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,

  -- Condition Details
  condition_name TEXT NOT NULL,
  icd10_code TEXT,

  -- Temporal Tracking
  diagnosed_date DATE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'resolved', 'chronic', 'in_remission')),

  -- Context
  diagnosed_by UUID REFERENCES auth.users(id),
  appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,

  -- Metadata
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for patient_conditions
CREATE INDEX IF NOT EXISTS idx_patient_conditions_patient_id ON patient_conditions(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_conditions_status ON patient_conditions(patient_id, status);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_patient_conditions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_patient_conditions_updated_at ON patient_conditions;
CREATE TRIGGER trigger_patient_conditions_updated_at
BEFORE UPDATE ON patient_conditions
FOR EACH ROW
EXECUTE FUNCTION update_patient_conditions_updated_at();

-- Comments
COMMENT ON TABLE patient_conditions IS 'Versioned medical conditions/diagnoses, shared across specialties';
COMMENT ON COLUMN patient_conditions.icd10_code IS 'Optional ICD-10 diagnostic code';

-- ==============================================================================
-- 5. PATIENT LAB RESULTS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS patient_lab_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,

  -- Context
  test_date DATE NOT NULL DEFAULT CURRENT_DATE,
  test_type TEXT NOT NULL,
  ordered_by UUID REFERENCES auth.users(id),
  appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,

  -- Results (JSONB for flexibility across different test types)
  results JSONB NOT NULL,

  -- Interpretation
  interpretation TEXT,
  notes TEXT,

  -- Metadata
  lab_name TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for patient_lab_results
CREATE INDEX IF NOT EXISTS idx_patient_lab_results_patient_id ON patient_lab_results(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_lab_results_test_date ON patient_lab_results(test_date DESC);
CREATE INDEX IF NOT EXISTS idx_patient_lab_results_test_type ON patient_lab_results(test_type);
CREATE INDEX IF NOT EXISTS idx_patient_lab_results_gin ON patient_lab_results USING GIN (results);

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_patient_lab_results_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_patient_lab_results_updated_at ON patient_lab_results;
CREATE TRIGGER trigger_patient_lab_results_updated_at
BEFORE UPDATE ON patient_lab_results
FOR EACH ROW
EXECUTE FUNCTION update_patient_lab_results_updated_at();

-- Comments
COMMENT ON TABLE patient_lab_results IS 'Structured lab results shared across specialties';
COMMENT ON COLUMN patient_lab_results.results IS 'JSONB field for flexible storage of different test types';

-- ==============================================================================
-- 6. ROW-LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================

-- Enable RLS on all tables
ALTER TABLE patient_vitals ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_medications ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_allergies ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_conditions ENABLE ROW LEVEL SECURITY;
ALTER TABLE patient_lab_results ENABLE ROW LEVEL SECURITY;

-- ===== PATIENT_VITALS RLS =====

CREATE POLICY "Patients can view own vitals"
  ON patient_vitals FOR SELECT
  TO authenticated
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

CREATE POLICY "Doctors can view patient vitals"
  ON patient_vitals FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  );

CREATE POLICY "Doctors can create vitals"
  ON patient_vitals FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  );

CREATE POLICY "Doctors can update recent vitals"
  ON patient_vitals FOR UPDATE
  TO authenticated
  USING (
    recorded_by = auth.uid() AND
    recorded_at > now() - INTERVAL '24 hours'
  );

-- ===== PATIENT_MEDICATIONS RLS =====

CREATE POLICY "Patients can view own medications"
  ON patient_medications FOR SELECT
  TO authenticated
  USING (patient_id IN (SELECT id FROM patients WHERE user_id = auth.uid()::text));

CREATE POLICY "Doctors can view patient medications"
  ON patient_medications FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  );

CREATE POLICY "Doctors can manage medications"
  ON patient_medications FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  );

-- ===== PATIENT_ALLERGIES RLS =====

CREATE POLICY "Patients can view own allergies"
  ON patient_allergies FOR SELECT
  TO authenticated
  USING (patient_id IN (SELECT id FROM patients WHERE user_id = auth.uid()::text));

CREATE POLICY "Doctors can view patient allergies"
  ON patient_allergies FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  );

CREATE POLICY "Doctors can manage allergies"
  ON patient_allergies FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  );

-- ===== PATIENT_CONDITIONS RLS =====

CREATE POLICY "Patients can view own conditions"
  ON patient_conditions FOR SELECT
  TO authenticated
  USING (patient_id IN (SELECT id FROM patients WHERE user_id = auth.uid()::text));

CREATE POLICY "Doctors can view patient conditions"
  ON patient_conditions FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  );

CREATE POLICY "Doctors can manage conditions"
  ON patient_conditions FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  );

-- ===== PATIENT_LAB_RESULTS RLS =====

CREATE POLICY "Patients can view own lab results"
  ON patient_lab_results FOR SELECT
  TO authenticated
  USING (patient_id IN (SELECT id FROM patients WHERE user_id = auth.uid()::text));

CREATE POLICY "Doctors can view patient lab results"
  ON patient_lab_results FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  );

CREATE POLICY "Doctors can manage lab results"
  ON patient_lab_results FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM doctors
      WHERE user_id = auth.uid()::text AND is_active = true
    )
  );

-- ==============================================================================
-- 7. ADD REFERENCE COLUMNS TO OB/GYN CONSULTATION FORMS
-- ==============================================================================

-- Add foreign key columns to link forms to shared health records
ALTER TABLE obgyn_forms
  ADD COLUMN IF NOT EXISTS vitals_record_id UUID REFERENCES patient_vitals(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS lab_results_record_ids UUID[];

CREATE INDEX IF NOT EXISTS idx_obgyn_forms_vitals_record ON obgyn_forms(vitals_record_id) WHERE vitals_record_id IS NOT NULL;

COMMENT ON COLUMN obgyn_forms.vitals_record_id IS 'Foreign key to patient_vitals table (shared health record)';
COMMENT ON COLUMN obgyn_forms.lab_results_record_ids IS 'Array of foreign keys to patient_lab_results table';

-- ==============================================================================
-- 8. DATA MIGRATION FROM PATIENTS TABLE
-- ==============================================================================

-- Migrate current_medications from patients table to patient_medications
INSERT INTO patient_medications (patient_id, medication_name, dosage, frequency, status, notes, created_at)
SELECT
  id AS patient_id,
  'Migrated medications' AS medication_name,
  '' AS dosage,
  '' AS frequency,
  'active' AS status,
  'MIGRATED FROM patients.current_medications: ' || current_medications AS notes,
  created_at
FROM patients
WHERE current_medications IS NOT NULL
  AND current_medications != ''
  AND current_medications != 'None'
  AND NOT EXISTS (
    SELECT 1 FROM patient_medications pm
    WHERE pm.patient_id = patients.id
    AND pm.notes LIKE 'MIGRATED FROM patients.current_medications:%'
  );

-- Migrate allergies from patients table to patient_allergies
INSERT INTO patient_allergies (patient_id, allergen, allergen_category, severity, status, notes, created_at)
SELECT
  id AS patient_id,
  allergies AS allergen,
  'other' AS allergen_category,
  'unknown' AS severity,
  'active' AS status,
  'MIGRATED FROM patients.allergies' AS notes,
  created_at
FROM patients
WHERE allergies IS NOT NULL
  AND allergies != ''
  AND allergies != 'None known'
  AND allergies != 'None'
  AND NOT EXISTS (
    SELECT 1 FROM patient_allergies pa
    WHERE pa.patient_id = patients.id
    AND pa.notes = 'MIGRATED FROM patients.allergies'
  );

-- Migrate current_conditions to patient_conditions
INSERT INTO patient_conditions (patient_id, condition_name, status, notes, created_at)
SELECT
  id AS patient_id,
  current_conditions AS condition_name,
  'active' AS status,
  'MIGRATED FROM patients.current_conditions' AS notes,
  created_at
FROM patients
WHERE current_conditions IS NOT NULL
  AND current_conditions != ''
  AND current_conditions != 'None'
  AND NOT EXISTS (
    SELECT 1 FROM patient_conditions pc
    WHERE pc.patient_id = patients.id
    AND pc.notes = 'MIGRATED FROM patients.current_conditions'
  );

-- Add migration flag to patients table
ALTER TABLE patients ADD COLUMN IF NOT EXISTS migrated_to_shared_health_record BOOLEAN DEFAULT false;

UPDATE patients SET migrated_to_shared_health_record = true
WHERE id IN (SELECT DISTINCT patient_id FROM patient_medications WHERE notes LIKE 'MIGRATED%')
   OR id IN (SELECT DISTINCT patient_id FROM patient_allergies WHERE notes LIKE 'MIGRATED%')
   OR id IN (SELECT DISTINCT patient_id FROM patient_conditions WHERE notes LIKE 'MIGRATED%');

-- ==============================================================================
-- MIGRATION COMPLETE
-- ==============================================================================
