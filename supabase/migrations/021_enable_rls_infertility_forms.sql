-- Enable RLS on infertility_forms table
--
-- SECURITY FIX: infertility_forms table currently has NO RLS protection,
-- exposing sensitive fertility medical history to all authenticated users.
--
-- This migration:
-- 1. Enables RLS on infertility_forms
-- 2. Follows the same pattern as obgyn_consultation_forms
-- 3. Allows doctors to view/create/update forms for their patients
-- 4. Allows patients to view their own forms (read-only)

-- Enable Row Level Security
ALTER TABLE infertility_forms ENABLE ROW LEVEL SECURITY;

-- SELECT Policy 1: Doctors can view forms for their patients
CREATE POLICY "Doctors can view their patients' infertility forms"
  ON infertility_forms
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
CREATE POLICY "Patients can view their own infertility forms"
  ON infertility_forms
  FOR SELECT
  TO public
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- INSERT Policy: Only doctors can create infertility forms for their patients
CREATE POLICY "Doctors can create infertility forms for their patients"
  ON infertility_forms
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
    -- Ensure the filled_by is set to the current user (doctor or service role)
    (filled_by = auth.uid() OR current_user = 'service_role')
  );

-- UPDATE Policy: Doctors can update forms for their patients
CREATE POLICY "Doctors can update their patients' infertility forms"
  ON infertility_forms
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

-- DELETE Policy: Only doctors can delete forms for their patients
CREATE POLICY "Doctors can delete their patients' infertility forms"
  ON infertility_forms
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

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_infertility_forms_patient_id ON infertility_forms(patient_id);
CREATE INDEX IF NOT EXISTS idx_infertility_forms_appointment_id ON infertility_forms(appointment_id);

-- Add helpful comments
COMMENT ON POLICY "Doctors can view their patients' infertility forms" ON infertility_forms IS
'Allows doctors to view infertility forms for patients they have an active relationship with';

COMMENT ON POLICY "Patients can view their own infertility forms" ON infertility_forms IS
'Allows patients to view their own infertility forms (read-only from patient perspective)';

COMMENT ON POLICY "Doctors can create infertility forms for their patients" ON infertility_forms IS
'Allows doctors to create infertility forms for their patients during consultations';

COMMENT ON POLICY "Doctors can update their patients' infertility forms" ON infertility_forms IS
'Allows doctors to update infertility forms for their patients';

COMMENT ON POLICY "Doctors can delete their patients' infertility forms" ON infertility_forms IS
'Allows doctors to delete infertility forms for their patients if needed';
