-- Migration: Create Antenatal (ANC) Forms Tables
-- This migration creates two tables:
-- 1. antenatal_forms: Master ANC card (one per pregnancy)
-- 2. antenatal_visits: Visit tracking (multiple per pregnancy)

-- Table 1: antenatal_forms (Master ANC Card - One per Pregnancy)
CREATE TABLE IF NOT EXISTS antenatal_forms (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,

  -- Form metadata
  form_type TEXT NOT NULL CHECK (form_type IN ('pre_consultation', 'during_consultation')),
  status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'partial', 'completed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES auth.users(id),
  updated_by UUID NOT NULL REFERENCES auth.users(id),
  filled_by UUID REFERENCES auth.users(id), -- Doctor if filled by doctor, null if patient

  -- Current Pregnancy Information
  lmp DATE, -- Last Menstrual Period
  edd DATE, -- Expected Date of Delivery (calculated from LMP)
  scan_edd DATE, -- Expected Date of Delivery (from ultrasound scan)
  clinical_edd DATE, -- Expected Date of Delivery (from clinical examination)
  gestational_age_weeks INTEGER,
  gravida INTEGER, -- Total pregnancies
  para INTEGER, -- Deliveries
  live INTEGER, -- Living children
  abortions INTEGER,

  -- Marriage & Social History
  marriage_date DATE, -- Date of marriage
  cohabitation_period_months INTEGER, -- Period of cohabitation in months
  consanguinity TEXT CHECK (consanguinity IN ('consanguineous', 'non_consanguineous')), -- Consanguineous marriage status

  -- Partner Details
  partner_name TEXT,
  partner_blood_group TEXT,
  partner_medical_history JSONB, -- {diabetes: bool, hypertension: bool, etc.}

  -- Detailed Obstetric History (Dynamic table - array of previous pregnancies)
  previous_pregnancies JSONB, -- Array of {pregnancy_num, mode_of_conception, mode_of_delivery, sex, age, alive, abortion, birth_weight_kg, year, breastfeeding_months, anomalies}

  -- Risk Factors (Checkboxes)
  risk_factors JSONB, -- {previous_lscs, previous_pph, pih, gdm, previous_stillbirth, previous_preterm, anemia, heart_disease, thyroid, other_conditions}

  -- Medical/Surgical/Family History
  medical_history JSONB, -- {diabetes, hypertension, asthma, tb, etc.}
  surgical_history TEXT,
  family_history JSONB, -- {diabetes, hypertension, twins, congenital_anomalies}

  -- Gynecological History
  menstrual_history JSONB,
  contraception_history TEXT,

  -- Immunization
  immunization_status JSONB, -- {tt1_date, tt2_date, ttbooster_date, other_vaccines}

  -- Current Pregnancy Symptoms
  current_symptoms TEXT,
  complaints TEXT,

  -- USG Scans (JSONB array with predefined types)
  usg_scans JSONB, -- Array of {scan_type, date, ga_weeks, findings, crl, nt_thickness, efw, afi, position, anomalies}
  -- scan_type: 'dating', 'nt_scan', 'anomaly', 'growth1', 'growth2', 'growth3', 'other'

  -- Antepartum Fetal Surveillance
  doppler_studies JSONB, -- Array of {date, umbilical_artery, mca, uterine_artery, findings}
  nst_tests JSONB, -- Array of {date, result, notes}
  other_surveillance JSONB, -- {bpp, ctg, etc.}

  -- Laboratory Investigations (Trimester-wise)
  lab_investigations JSONB, -- {first_trimester: {hb, blood_group, rh, vdrl, hiv, hbsag, blood_sugar}, second_trimester: {...}, third_trimester: {...}}

  -- Birth Plan (Available from 28+ weeks)
  birth_plan JSONB, -- {mode_of_delivery, ga_at_delivery, iol_plan, epidural, support_person, episiotomy, breastfeeding_plan}

  -- Plan of Management
  plan_mother TEXT,
  plan_fetus TEXT,

  -- Hospitalization & Follow-up
  admission_date DATE,
  followup_plan TEXT,
  postpartum_visits TEXT,

  -- Referrals (Dynamic table)
  referrals JSONB -- Array of {date, referred_to, reason, outcome}
);

-- Create indexes for antenatal_forms
CREATE INDEX IF NOT EXISTS idx_antenatal_forms_patient ON antenatal_forms(patient_id);
CREATE INDEX IF NOT EXISTS idx_antenatal_forms_appointment ON antenatal_forms(appointment_id);
CREATE INDEX IF NOT EXISTS idx_antenatal_forms_created_at ON antenatal_forms(created_at);
CREATE INDEX IF NOT EXISTS idx_antenatal_forms_status ON antenatal_forms(status);

-- Table 2: antenatal_visits (Visit Tracking - Multiple per Pregnancy)
CREATE TABLE IF NOT EXISTS antenatal_visits (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  antenatal_form_id UUID NOT NULL REFERENCES antenatal_forms(id) ON DELETE CASCADE,
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,

  -- Visit Metadata
  visit_number INTEGER NOT NULL, -- 1, 2, 3, ... 12
  visit_date DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES auth.users(id),

  -- Visit Data
  gestational_age_weeks INTEGER,
  weight_kg NUMERIC(5,2),
  blood_pressure_systolic INTEGER,
  blood_pressure_diastolic INTEGER,
  fundal_height_cm NUMERIC(4,1),
  presentation TEXT CHECK (presentation IN ('cephalic', 'breech', 'transverse')),
  fetal_heart_rate INTEGER, -- FHR
  urine_albumin TEXT, -- 'nil', 'trace', '+', '++', '+++'
  urine_sugar TEXT, -- 'nil', 'trace', '+', '++', '+++'
  edema BOOLEAN,
  edema_location TEXT,
  remarks TEXT,
  complaints TEXT,

  -- Doctor's notes for this visit
  clinical_notes TEXT,
  treatment_given TEXT,
  next_visit_plan TEXT,

  -- Ensure unique visit numbers per form
  CONSTRAINT unique_visit_per_form UNIQUE (antenatal_form_id, visit_number)
);

-- Create indexes for antenatal_visits
CREATE INDEX IF NOT EXISTS idx_antenatal_visits_form ON antenatal_visits(antenatal_form_id);
CREATE INDEX IF NOT EXISTS idx_antenatal_visits_patient ON antenatal_visits(patient_id);
CREATE INDEX IF NOT EXISTS idx_antenatal_visits_date ON antenatal_visits(visit_date);
CREATE INDEX IF NOT EXISTS idx_antenatal_visits_number ON antenatal_visits(visit_number);

-- Enable Row-Level Security (RLS) for antenatal_forms
ALTER TABLE antenatal_forms ENABLE ROW LEVEL SECURITY;

-- RLS Policies for antenatal_forms
-- Patients can view their own forms
CREATE POLICY "Patients can view their own antenatal forms"
  ON antenatal_forms FOR SELECT
  USING (
    auth.uid()::text IN (
      SELECT user_id FROM patients WHERE id = antenatal_forms.patient_id
    )
  );

-- Patients can create their own forms
CREATE POLICY "Patients can create their own antenatal forms"
  ON antenatal_forms FOR INSERT
  WITH CHECK (
    auth.uid()::text IN (
      SELECT user_id FROM patients WHERE id = antenatal_forms.patient_id
    )
  );

-- Patients can update their own forms
CREATE POLICY "Patients can update their own antenatal forms"
  ON antenatal_forms FOR UPDATE
  USING (
    auth.uid()::text IN (
      SELECT user_id FROM patients WHERE id = antenatal_forms.patient_id
    )
  );

-- Doctors can view forms for their patients
CREATE POLICY "Doctors can view antenatal forms for their patients"
  ON antenatal_forms FOR SELECT
  USING (
    auth.uid()::text IN (
      SELECT user_id FROM doctors WHERE id IN (
        SELECT doctor_id FROM appointments WHERE patient_id = antenatal_forms.patient_id
      )
    )
  );

-- Doctors can create forms for their patients
CREATE POLICY "Doctors can create antenatal forms for their patients"
  ON antenatal_forms FOR INSERT
  WITH CHECK (
    auth.uid()::text IN (
      SELECT user_id FROM doctors WHERE id IN (
        SELECT doctor_id FROM appointments WHERE patient_id = antenatal_forms.patient_id
      )
    )
  );

-- Doctors can update forms for their patients
CREATE POLICY "Doctors can update antenatal forms for their patients"
  ON antenatal_forms FOR UPDATE
  USING (
    auth.uid()::text IN (
      SELECT user_id FROM doctors WHERE id IN (
        SELECT doctor_id FROM appointments WHERE patient_id = antenatal_forms.patient_id
      )
    )
  );

-- Enable Row-Level Security (RLS) for antenatal_visits
ALTER TABLE antenatal_visits ENABLE ROW LEVEL SECURITY;

-- RLS Policies for antenatal_visits
-- Patients can view their own visits
CREATE POLICY "Patients can view their own antenatal visits"
  ON antenatal_visits FOR SELECT
  USING (
    auth.uid()::text IN (
      SELECT user_id FROM patients WHERE id = antenatal_visits.patient_id
    )
  );

-- Doctors can view visits for their patients
CREATE POLICY "Doctors can view antenatal visits for their patients"
  ON antenatal_visits FOR SELECT
  USING (
    auth.uid()::text IN (
      SELECT user_id FROM doctors WHERE id IN (
        SELECT doctor_id FROM appointments WHERE patient_id = antenatal_visits.patient_id
      )
    )
  );

-- Doctors can create visits for their patients
CREATE POLICY "Doctors can create antenatal visits for their patients"
  ON antenatal_visits FOR INSERT
  WITH CHECK (
    auth.uid()::text IN (
      SELECT user_id FROM doctors WHERE id IN (
        SELECT doctor_id FROM appointments WHERE patient_id = antenatal_visits.patient_id
      )
    )
  );

-- Doctors can update visits for their patients
CREATE POLICY "Doctors can update antenatal visits for their patients"
  ON antenatal_visits FOR UPDATE
  USING (
    auth.uid()::text IN (
      SELECT user_id FROM doctors WHERE id IN (
        SELECT doctor_id FROM appointments WHERE patient_id = antenatal_visits.patient_id
      )
    )
  );

-- Add comments for documentation
COMMENT ON TABLE antenatal_forms IS 'Master ANC (Antenatal Care) card - one record per pregnancy containing static pregnancy data';
COMMENT ON TABLE antenatal_visits IS 'ANC visit tracking - multiple visit records per pregnancy for serial monitoring';

COMMENT ON COLUMN antenatal_forms.lmp IS 'Last Menstrual Period - used to calculate EDD and gestational age';
COMMENT ON COLUMN antenatal_forms.edd IS 'Expected Date of Delivery - calculated from LMP (LMP + 280 days)';
COMMENT ON COLUMN antenatal_forms.scan_edd IS 'Expected Date of Delivery - determined by ultrasound scan';
COMMENT ON COLUMN antenatal_forms.clinical_edd IS 'Expected Date of Delivery - determined by clinical examination';
COMMENT ON COLUMN antenatal_forms.gestational_age_weeks IS 'Gestational age in weeks - calculated from LMP';
COMMENT ON COLUMN antenatal_forms.gravida IS 'Total number of pregnancies (including current)';
COMMENT ON COLUMN antenatal_forms.para IS 'Number of deliveries beyond 20 weeks gestation';
COMMENT ON COLUMN antenatal_forms.live IS 'Number of living children';
COMMENT ON COLUMN antenatal_forms.abortions IS 'Number of pregnancy losses before 20 weeks';

COMMENT ON COLUMN antenatal_forms.marriage_date IS 'Date of marriage';
COMMENT ON COLUMN antenatal_forms.cohabitation_period_months IS 'Period of cohabitation in months';
COMMENT ON COLUMN antenatal_forms.consanguinity IS 'Consanguineous marriage status (consanguineous/non-consanguineous) - important for genetic risk assessment';

COMMENT ON COLUMN antenatal_forms.previous_pregnancies IS 'Array of previous pregnancy details: [{pregnancy_num, mode_of_conception, mode_of_delivery, sex, age, alive, abortion, birth_weight_kg, year, breastfeeding_months, anomalies, complications}]';
COMMENT ON COLUMN antenatal_forms.risk_factors IS 'Risk factor checkboxes: {previous_lscs, previous_pph, pih, gdm, previous_stillbirth, previous_preterm, anemia, heart_disease, thyroid, other_conditions}';
COMMENT ON COLUMN antenatal_forms.usg_scans IS 'Array of USG scans: [{scan_type, date, ga_weeks, findings, crl, nt_thickness, efw, afi, position, anomalies}]. scan_type: dating, nt_scan, anomaly, growth1, growth2, growth3, other';
COMMENT ON COLUMN antenatal_forms.doppler_studies IS 'Array of Doppler studies: [{date, umbilical_artery, middle_cerebral_artery, uterine_artery, findings}]';
COMMENT ON COLUMN antenatal_forms.nst_tests IS 'Array of NST (Non-Stress Test) results: [{date, result (reactive/non_reactive), notes}]';
COMMENT ON COLUMN antenatal_forms.lab_investigations IS 'Trimester-wise lab investigations: {first_trimester: {hb, blood_group, rh, vdrl, hiv, hbsag, blood_sugar}, second_trimester: {hb, triple_marker, quadruple_marker, gtt}, third_trimester: {hb, blood_sugar, repeat_hiv, repeat_hbsag}}';
COMMENT ON COLUMN antenatal_forms.birth_plan IS 'Birth plan details (28+ weeks): {mode_of_delivery, ga_at_delivery, iol_plan, epidural, support_person, episiotomy, breastfeeding_plan}';
COMMENT ON COLUMN antenatal_forms.referrals IS 'Array of referrals: [{date, referred_to, reason, outcome}]';

COMMENT ON COLUMN antenatal_visits.visit_number IS 'Sequential visit number (1, 2, 3, ...) for this pregnancy';
COMMENT ON COLUMN antenatal_visits.fundal_height_cm IS 'Fundal height measurement in cm (should roughly match gestational age in weeks after 20 weeks)';
COMMENT ON COLUMN antenatal_visits.presentation IS 'Fetal presentation: cephalic (head down), breech (buttocks/feet down), or transverse (sideways)';
COMMENT ON COLUMN antenatal_visits.fetal_heart_rate IS 'Fetal Heart Rate (FHR) in beats per minute (normal: 110-160 bpm)';
COMMENT ON COLUMN antenatal_visits.urine_albumin IS 'Urine protein test result: nil, trace, +, ++, +++ (indicates pre-eclampsia risk)';
COMMENT ON COLUMN antenatal_visits.urine_sugar IS 'Urine glucose test result: nil, trace, +, ++, +++ (indicates gestational diabetes risk)';
COMMENT ON COLUMN antenatal_visits.edema IS 'Presence of swelling/edema (sign of fluid retention)';
