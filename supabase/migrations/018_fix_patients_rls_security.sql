-- Fix critical security flaw: Replace overly permissive patients RLS policies
-- with proper user-scoped access controls
--
-- SECURITY FIX: Patients table was previously accessible to all users.
-- This migration restricts access so that:
-- 1. Doctors can only see/update patients they have an active relationship with
-- 2. Patients can only see/update their own record
-- 3. Only doctors can create new patient records
-- 4. No one can delete patients (use archived flag instead)

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Allow all select on patients" ON patients;
DROP POLICY IF EXISTS "Allow all insert on patients" ON patients;
DROP POLICY IF EXISTS "Allow all update on patients" ON patients;
DROP POLICY IF EXISTS "Allow all delete on patients" ON patients;
DROP POLICY IF EXISTS "Enable insert for authenticated users only" ON patients;
DROP POLICY IF EXISTS "Anon can view patients" ON patients;

-- SELECT Policy 1: Doctors can view patients they have an active relationship with
CREATE POLICY "Doctors can view their patients"
  ON patients
  FOR SELECT
  TO public
  USING (
    id IN (
      SELECT pd.patient_id
      FROM patient_doctor pd
      INNER JOIN doctors d ON d.id = pd.doctor_id
      WHERE d.user_id = auth.uid()::text
        AND pd.status = 'active'
    )
  );

-- SELECT Policy 2: Patients can view their own record
CREATE POLICY "Patients can view their own record"
  ON patients
  FOR SELECT
  TO public
  USING (
    user_id = auth.uid()::text
  );

-- INSERT Policy: Only doctors can create patient records
CREATE POLICY "Doctors can create patient records"
  ON patients
  FOR INSERT
  TO public
  WITH CHECK (
    -- The doctor creating the patient must exist
    EXISTS (
      SELECT 1
      FROM doctors d
      WHERE d.user_id = auth.uid()::text
    )
    AND
    -- The created_by field should match the doctor's user_id
    created_by = auth.uid()::text
  );

-- UPDATE Policy 1: Doctors can update patients they have an active relationship with
CREATE POLICY "Doctors can update their patients"
  ON patients
  FOR UPDATE
  TO public
  USING (
    id IN (
      SELECT pd.patient_id
      FROM patient_doctor pd
      JOIN doctors d ON d.id = pd.doctor_id
      WHERE d.user_id = auth.uid()::text
        AND pd.status = 'active'
    )
  )
  WITH CHECK (
    id IN (
      SELECT pd.patient_id
      FROM patient_doctor pd
      JOIN doctors d ON d.id = pd.doctor_id
      WHERE d.user_id = auth.uid()::text
        AND pd.status = 'active'
    )
  );

-- UPDATE Policy 2: Patients can update their own record
CREATE POLICY "Patients can update their own record"
  ON patients
  FOR UPDATE
  TO public
  USING (
    user_id = auth.uid()::text
  )
  WITH CHECK (
    user_id = auth.uid()::text
  );

-- DELETE Policy: No direct deletes - use archived flag instead
-- This policy restricts deletes to only superadmins if absolutely necessary
CREATE POLICY "Only superadmins can delete patients"
  ON patients
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

-- Create indexes for better query performance on RLS policies
CREATE INDEX IF NOT EXISTS idx_patients_user_id_not_archived ON patients(user_id) WHERE archived = false;
CREATE INDEX IF NOT EXISTS idx_patients_created_by ON patients(created_by);

-- Add helpful comments
COMMENT ON POLICY "Doctors can view their patients" ON patients IS
'Allows doctors to view patients they have an active relationship with via patient_doctor table';

COMMENT ON POLICY "Patients can view their own record" ON patients IS
'Allows patients to view their own patient record using their user_id';

COMMENT ON POLICY "Doctors can create patient records" ON patients IS
'Allows doctors to create new patient records. The created_by field is verified to match the doctor user_id';

COMMENT ON POLICY "Doctors can update their patients" ON patients IS
'Allows doctors to update patient information for patients they have an active relationship with';

COMMENT ON POLICY "Patients can update their own record" ON patients IS
'Allows patients to update their own demographic and medical information';

COMMENT ON POLICY "Only superadmins can delete patients" ON patients IS
'Restricts patient deletion to superadmins only. Use archived=true flag for soft deletes instead';
