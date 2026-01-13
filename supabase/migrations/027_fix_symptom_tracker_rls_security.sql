-- Fix security flaw: Replace overly permissive symptom_tracker RLS policies
--
-- SECURITY FIX: symptom_tracker table was accessible to all users.
--
-- This migration restricts access so that:
-- 1. Patients can view/create/update/delete their own symptoms
-- 2. Doctors can view symptoms for their patients (read-only)
-- 3. No anonymous access

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Allow all select on symptom_tracker" ON symptom_tracker;
DROP POLICY IF EXISTS "Allow all insert on symptom_tracker" ON symptom_tracker;
DROP POLICY IF EXISTS "Allow all update on symptom_tracker" ON symptom_tracker;
DROP POLICY IF EXISTS "Allow all delete on symptom_tracker" ON symptom_tracker;

-- SELECT Policy 1: Patients can view their own symptoms
CREATE POLICY "Patients can view their own symptoms"
  ON symptom_tracker
  FOR SELECT
  TO public
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- SELECT Policy 2: Doctors can view symptoms for their patients
CREATE POLICY "Doctors can view their patients' symptoms"
  ON symptom_tracker
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

-- INSERT Policy: Only patients can create their own symptoms
CREATE POLICY "Patients can create their own symptoms"
  ON symptom_tracker
  FOR INSERT
  TO public
  WITH CHECK (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- UPDATE Policy: Only patients can update their own symptoms
CREATE POLICY "Patients can update their own symptoms"
  ON symptom_tracker
  FOR UPDATE
  TO public
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- DELETE Policy: Only patients can delete their own symptoms
CREATE POLICY "Patients can delete their own symptoms"
  ON symptom_tracker
  FOR DELETE
  TO public
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- Ensure indexes exist
CREATE INDEX IF NOT EXISTS idx_symptom_tracker_patient_id ON symptom_tracker(patient_id);
CREATE INDEX IF NOT EXISTS idx_symptom_tracker_symptom_date ON symptom_tracker(symptom_date);

-- Add helpful comments
COMMENT ON POLICY "Patients can view their own symptoms" ON symptom_tracker IS
'Allows patients to view their own symptom records';

COMMENT ON POLICY "Doctors can view their patients' symptoms" ON symptom_tracker IS
'Allows doctors to view symptom records for their patients (read-only)';

COMMENT ON POLICY "Patients can create their own symptoms" ON symptom_tracker IS
'Allows patients to create symptom records for themselves';

COMMENT ON POLICY "Patients can update their own symptoms" ON symptom_tracker IS
'Allows patients to update their own symptom records';

COMMENT ON POLICY "Patients can delete their own symptoms" ON symptom_tracker IS
'Allows patients to delete their own symptom records';
