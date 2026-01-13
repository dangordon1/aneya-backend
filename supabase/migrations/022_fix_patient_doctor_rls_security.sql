-- Fix critical security flaw: Replace overly permissive patient_doctor RLS policies
-- with proper access controls
--
-- SECURITY FIX: patient_doctor table was previously writable by anonymous users,
-- allowing anyone to create/modify doctor-patient relationships.
--
-- This migration restricts access so that:
-- 1. Doctors can create relationships with patients (status='pending' or 'active')
-- 2. Patients can view/accept/reject relationships
-- 3. Both parties can view their own relationships
-- 4. No anonymous access

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Users can view patient_doctor relationships" ON patient_doctor;
DROP POLICY IF EXISTS "Users can create patient_doctor relationships" ON patient_doctor;
DROP POLICY IF EXISTS "Users can update patient_doctor relationships" ON patient_doctor;
DROP POLICY IF EXISTS "Anon can create patient_doctor relationships" ON patient_doctor;
DROP POLICY IF EXISTS "Anon can update patient_doctor relationships" ON patient_doctor;
DROP POLICY IF EXISTS "Enable read access for all users" ON patient_doctor;
DROP POLICY IF EXISTS "Anon can view patient_doctor" ON patient_doctor;

-- SELECT Policy 1: Doctors can view their patient relationships
CREATE POLICY "Doctors can view their patient relationships"
  ON patient_doctor
  FOR SELECT
  TO public
  USING (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- SELECT Policy 2: Patients can view their doctor relationships
CREATE POLICY "Patients can view their doctor relationships"
  ON patient_doctor
  FOR SELECT
  TO public
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- INSERT Policy: Only doctors can create patient relationships
CREATE POLICY "Doctors can create patient relationships"
  ON patient_doctor
  FOR INSERT
  TO public
  WITH CHECK (
    -- Doctor must be the one creating the relationship
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
    AND
    -- Initial status should be pending (awaiting patient approval)
    initiated_by = 'doctor'
  );

-- UPDATE Policy 1: Doctors can update their patient relationships
CREATE POLICY "Doctors can update their patient relationships"
  ON patient_doctor
  FOR UPDATE
  TO public
  USING (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- UPDATE Policy 2: Patients can update their doctor relationships (accept/reject)
CREATE POLICY "Patients can update their doctor relationships"
  ON patient_doctor
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

-- DELETE Policy 1: Doctors can delete relationships they created
CREATE POLICY "Doctors can delete their patient relationships"
  ON patient_doctor
  FOR DELETE
  TO public
  USING (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- DELETE Policy 2: Patients can delete relationships (remove doctor access)
CREATE POLICY "Patients can delete their doctor relationships"
  ON patient_doctor
  FOR DELETE
  TO public
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- Ensure indexes exist for performance
CREATE INDEX IF NOT EXISTS idx_patient_doctor_doctor_id ON patient_doctor(doctor_id);
CREATE INDEX IF NOT EXISTS idx_patient_doctor_patient_id ON patient_doctor(patient_id);
CREATE INDEX IF NOT EXISTS idx_patient_doctor_status ON patient_doctor(status);

-- Add helpful comments
COMMENT ON POLICY "Doctors can view their patient relationships" ON patient_doctor IS
'Allows doctors to view all their patient relationships regardless of status';

COMMENT ON POLICY "Patients can view their doctor relationships" ON patient_doctor IS
'Allows patients to view all their doctor relationships regardless of status';

COMMENT ON POLICY "Doctors can create patient relationships" ON patient_doctor IS
'Allows doctors to initiate relationships with patients (pending approval)';

COMMENT ON POLICY "Doctors can update their patient relationships" ON patient_doctor IS
'Allows doctors to update relationship status and metadata';

COMMENT ON POLICY "Patients can update their doctor relationships" ON patient_doctor IS
'Allows patients to accept/reject doctor relationship requests';

COMMENT ON POLICY "Doctors can delete their patient relationships" ON patient_doctor IS
'Allows doctors to remove patient relationships';

COMMENT ON POLICY "Patients can delete their doctor relationships" ON patient_doctor IS
'Allows patients to remove doctor access to their data';
