-- Fix critical security flaw: Replace overly permissive consultations RLS policies
-- with proper user-scoped access controls
--
-- SECURITY FIX: Consultations were previously visible to all users.
-- This migration restricts access so that:
-- 1. Doctors can only see consultations for their patients (via patient_doctor relationship)
-- 2. Patients can only see their own consultations
-- 3. Only authorized users can create/update/delete consultations

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Allow all select on consultations" ON consultations;
DROP POLICY IF EXISTS "Allow all insert on consultations" ON consultations;
DROP POLICY IF EXISTS "Allow all update on consultations" ON consultations;
DROP POLICY IF EXISTS "Allow all delete on consultations" ON consultations;

-- SELECT Policy 1: Doctors can view consultations for their patients
CREATE POLICY "Doctors can view their patients' consultations"
  ON consultations
  FOR SELECT
  TO public
  USING (
    patient_id IN (
      SELECT pd.patient_id
      FROM patient_doctor pd
      INNER JOIN doctors d ON d.id = pd.doctor_id
      WHERE d.user_id = auth.uid()::text
        AND pd.status = 'active'
    )
  );

-- SELECT Policy 2: Patients can view their own consultations
CREATE POLICY "Patients can view their own consultations"
  ON consultations
  FOR SELECT
  TO public
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- INSERT Policy: Doctors can create consultations for their patients
CREATE POLICY "Doctors can create consultations for their patients"
  ON consultations
  FOR INSERT
  TO public
  WITH CHECK (
    patient_id IN (
      SELECT pd.patient_id
      FROM patient_doctor pd
      JOIN doctors d ON d.id = pd.doctor_id
      WHERE d.user_id = auth.uid()::text
        AND pd.status = 'active'
    )
  );

-- UPDATE Policy: Doctors can update consultations for their patients
CREATE POLICY "Doctors can update their patients' consultations"
  ON consultations
  FOR UPDATE
  TO public
  USING (
    patient_id IN (
      SELECT pd.patient_id
      FROM patient_doctor pd
      JOIN doctors d ON d.id = pd.doctor_id
      WHERE d.user_id = auth.uid()::text
        AND pd.status = 'active'
    )
  )
  WITH CHECK (
    patient_id IN (
      SELECT pd.patient_id
      FROM patient_doctor pd
      JOIN doctors d ON d.id = pd.doctor_id
      WHERE d.user_id = auth.uid()::text
        AND pd.status = 'active'
    )
  );

-- DELETE Policy: Only doctors who performed the consultation can delete it
CREATE POLICY "Doctors can delete their own consultations"
  ON consultations
  FOR DELETE
  TO public
  USING (
    performed_by = auth.uid()::text
    OR
    patient_id IN (
      SELECT pd.patient_id
      FROM patient_doctor pd
      JOIN doctors d ON d.id = pd.doctor_id
      WHERE d.user_id = auth.uid()::text
        AND pd.status = 'active'
    )
  );

-- Create indexes for better query performance on RLS policies
CREATE INDEX IF NOT EXISTS idx_consultations_patient_id ON consultations(patient_id);
CREATE INDEX IF NOT EXISTS idx_consultations_performed_by ON consultations(performed_by);
CREATE INDEX IF NOT EXISTS idx_patient_doctor_lookup ON patient_doctor(doctor_id, patient_id, status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_patients_user_id ON patients(user_id);

-- Add helpful comments
COMMENT ON POLICY "Doctors can view their patients' consultations" ON consultations IS
'Allows doctors to view consultations for patients they have an active relationship with via patient_doctor table';

COMMENT ON POLICY "Patients can view their own consultations" ON consultations IS
'Allows patients to view consultations for their own patient record using user_id';

COMMENT ON POLICY "Doctors can create consultations for their patients" ON consultations IS
'Allows doctors to create new consultations for patients they have an active relationship with';

COMMENT ON POLICY "Doctors can update their patients' consultations" ON consultations IS
'Allows doctors to update consultations for patients they have an active relationship with';

COMMENT ON POLICY "Doctors can delete their own consultations" ON consultations IS
'Allows doctors to delete consultations they performed or for patients they have an active relationship with';
