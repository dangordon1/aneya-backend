-- Fix security flaw: Replace overly permissive consultation_forms RLS policies
--
-- SECURITY FIX: consultation_forms table allowed all users to access all forms.
--
-- This migration restricts access so that:
-- 1. Doctors can view/create/update forms for their patients
-- 2. Patients can view their own forms
-- 3. Proper patient-doctor scoping via patient_doctor relationship

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Users can view all consultation forms" ON consultation_forms;
DROP POLICY IF EXISTS "Users can create consultation forms" ON consultation_forms;
DROP POLICY IF EXISTS "Users can update own consultation forms" ON consultation_forms;

-- SELECT Policy 1: Doctors can view forms for their patients
CREATE POLICY "Doctors can view their patients' consultation forms"
  ON consultation_forms
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

-- SELECT Policy 2: Patients can view their own forms
CREATE POLICY "Patients can view their own consultation forms"
  ON consultation_forms
  FOR SELECT
  TO public
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- INSERT Policy: Only doctors can create consultation forms for their patients
CREATE POLICY "Doctors can create consultation forms for their patients"
  ON consultation_forms
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
    AND
    created_by = auth.uid()::text
  );

-- UPDATE Policy: Doctors can update forms for their patients
CREATE POLICY "Doctors can update their patients' consultation forms"
  ON consultation_forms
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

-- DELETE Policy: Doctors can delete forms for their patients
CREATE POLICY "Doctors can delete their patients' consultation forms"
  ON consultation_forms
  FOR DELETE
  TO public
  USING (
    patient_id IN (
      SELECT pd.patient_id
      FROM patient_doctor pd
      JOIN doctors d ON d.id = pd.doctor_id
      WHERE d.user_id = auth.uid()::text
        AND pd.status = 'active'
    )
  );

-- Ensure indexes exist
CREATE INDEX IF NOT EXISTS idx_consultation_forms_patient_id ON consultation_forms(patient_id);
CREATE INDEX IF NOT EXISTS idx_consultation_forms_appointment_id ON consultation_forms(appointment_id);
CREATE INDEX IF NOT EXISTS idx_consultation_forms_form_type ON consultation_forms(form_type);

-- Add helpful comments
COMMENT ON POLICY "Doctors can view their patients' consultation forms" ON consultation_forms IS
'Allows doctors to view consultation forms for patients they have an active relationship with';

COMMENT ON POLICY "Patients can view their own consultation forms" ON consultation_forms IS
'Allows patients to view their own consultation forms';

COMMENT ON POLICY "Doctors can create consultation forms for their patients" ON consultation_forms IS
'Allows doctors to create consultation forms for their patients';

COMMENT ON POLICY "Doctors can update their patients' consultation forms" ON consultation_forms IS
'Allows doctors to update consultation forms for their patients';

COMMENT ON POLICY "Doctors can delete their patients' consultation forms" ON consultation_forms IS
'Allows doctors to delete consultation forms for their patients';
