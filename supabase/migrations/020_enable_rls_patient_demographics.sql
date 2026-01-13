-- Enable RLS on patient_demographics table
--
-- SECURITY FIX: patient_demographics table currently has NO RLS protection,
-- exposing all patient PII (name, DOB, phone, email, address, emergency contacts)
-- to all authenticated users.
--
-- This migration:
-- 1. Enables RLS on patient_demographics
-- 2. Allows doctors to view/create/update demographics for their patients
-- 3. Allows patients to view/update their own demographics
-- 4. Restricts deletion to superadmins only

-- Enable Row Level Security
ALTER TABLE patient_demographics ENABLE ROW LEVEL SECURITY;

-- SELECT Policy 1: Doctors can view demographics for their patients
CREATE POLICY "Doctors can view their patients' demographics"
  ON patient_demographics
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

-- SELECT Policy 2: Patients can view their own demographics
CREATE POLICY "Patients can view their own demographics"
  ON patient_demographics
  FOR SELECT
  TO public
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- INSERT Policy: Only doctors or the patient themselves can create demographics
CREATE POLICY "Doctors and patients can create demographics"
  ON patient_demographics
  FOR INSERT
  TO public
  WITH CHECK (
    -- Doctor creating for their patient
    (
      patient_id IN (
        SELECT pd.patient_id
        FROM patient_doctor pd
        JOIN doctors d ON d.id = pd.doctor_id
        WHERE d.user_id = auth.uid()::text
          AND pd.status = 'active'
      )
      AND created_by = auth.uid()
    )
    OR
    -- Patient creating their own
    (
      patient_id IN (
        SELECT id FROM patients WHERE user_id = auth.uid()::text
      )
      AND created_by = auth.uid()
    )
  );

-- UPDATE Policy 1: Doctors can update demographics for their patients
CREATE POLICY "Doctors can update their patients' demographics"
  ON patient_demographics
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

-- UPDATE Policy 2: Patients can update their own demographics
CREATE POLICY "Patients can update their own demographics"
  ON patient_demographics
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

-- DELETE Policy: Only superadmins can delete demographics
CREATE POLICY "Only superadmins can delete demographics"
  ON patient_demographics
  FOR DELETE
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM user_roles ur
      WHERE ur.user_id = auth.uid()::text
        AND ur.role = 'superadmin'
    )
  );

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_patient_demographics_patient_id ON patient_demographics(patient_id);

-- Add helpful comments
COMMENT ON POLICY "Doctors can view their patients' demographics" ON patient_demographics IS
'Allows doctors to view demographic information for patients they have an active relationship with';

COMMENT ON POLICY "Patients can view their own demographics" ON patient_demographics IS
'Allows patients to view their own demographic information';

COMMENT ON POLICY "Doctors and patients can create demographics" ON patient_demographics IS
'Allows doctors to create demographics for their patients or patients to create their own';

COMMENT ON POLICY "Doctors can update their patients' demographics" ON patient_demographics IS
'Allows doctors to update demographic information for their patients';

COMMENT ON POLICY "Patients can update their own demographics" ON patient_demographics IS
'Allows patients to update their own demographic information';

COMMENT ON POLICY "Only superadmins can delete demographics" ON patient_demographics IS
'Restricts demographics deletion to superadmins only';
