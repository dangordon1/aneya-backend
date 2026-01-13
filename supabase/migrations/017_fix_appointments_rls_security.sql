-- Fix critical security flaw: Replace overly permissive appointments RLS policies
-- with proper user-scoped access controls
--
-- SECURITY FIX: Appointments were previously visible to all users.
-- This migration restricts access so that:
-- 1. Doctors can only see appointments where they are the assigned doctor OR for their patients
-- 2. Patients can only see their own appointments
-- 3. Only authorized users can create/update/delete appointments

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Allow all select on appointments" ON appointments;
DROP POLICY IF EXISTS "Allow all insert on appointments" ON appointments;
DROP POLICY IF EXISTS "Allow all update on appointments" ON appointments;
DROP POLICY IF EXISTS "Allow all delete on appointments" ON appointments;
DROP POLICY IF EXISTS "Enable insert for authenticated users only" ON appointments;

-- SELECT Policy 1: Doctors can view appointments where they are the assigned doctor
CREATE POLICY "Doctors can view appointments where they are assigned"
  ON appointments
  FOR SELECT
  TO public
  USING (
    doctor_id IN (
      SELECT d.id
      FROM doctors d
      WHERE d.user_id = auth.uid()::text
    )
  );

-- SELECT Policy 2: Doctors can view appointments for their patients
CREATE POLICY "Doctors can view appointments for their patients"
  ON appointments
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

-- SELECT Policy 3: Patients can view their own appointments
CREATE POLICY "Patients can view their own appointments"
  ON appointments
  FOR SELECT
  TO public
  USING (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
  );

-- INSERT Policy: Doctors can create appointments for their patients or where they are assigned
CREATE POLICY "Doctors can create appointments"
  ON appointments
  FOR INSERT
  TO public
  WITH CHECK (
    -- Doctor must be assigned to the appointment
    doctor_id IN (
      SELECT d.id
      FROM doctors d
      WHERE d.user_id = auth.uid()::text
    )
    AND
    -- Patient must be one of the doctor's patients OR booking allowed
    (
      patient_id IN (
        SELECT pd.patient_id
        FROM patient_doctor pd
        JOIN doctors d ON d.id = pd.doctor_id
        WHERE d.user_id = auth.uid()::text
          AND pd.status = 'active'
      )
      OR booked_by = 'patient' -- Allow if patient is booking
    )
  );

-- INSERT Policy 2: Patients can create appointments for themselves
CREATE POLICY "Patients can create their own appointments"
  ON appointments
  FOR INSERT
  TO public
  WITH CHECK (
    patient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    )
    AND booked_by = 'patient'
  );

-- UPDATE Policy: Doctors can update appointments where they are assigned
CREATE POLICY "Doctors can update appointments where they are assigned"
  ON appointments
  FOR UPDATE
  TO public
  USING (
    doctor_id IN (
      SELECT d.id
      FROM doctors d
      WHERE d.user_id = auth.uid()::text
    )
  )
  WITH CHECK (
    doctor_id IN (
      SELECT d.id
      FROM doctors d
      WHERE d.user_id = auth.uid()::text
    )
  );

-- UPDATE Policy 2: Doctors can update appointments for their patients
CREATE POLICY "Doctors can update appointments for their patients"
  ON appointments
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

-- UPDATE Policy 3: Patients can update their own appointments (e.g., cancellation)
CREATE POLICY "Patients can update their own appointments"
  ON appointments
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

-- DELETE Policy: Only doctors who are assigned can delete appointments
CREATE POLICY "Doctors can delete appointments where they are assigned"
  ON appointments
  FOR DELETE
  TO public
  USING (
    doctor_id IN (
      SELECT d.id
      FROM doctors d
      WHERE d.user_id = auth.uid()::text
    )
  );

-- DELETE Policy 2: Doctors can delete appointments for their patients
CREATE POLICY "Doctors can delete appointments for their patients"
  ON appointments
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

-- Create indexes for better query performance on RLS policies
CREATE INDEX IF NOT EXISTS idx_appointments_doctor_id ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_patient_id ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled_time ON appointments(scheduled_time);

-- Add helpful comments
COMMENT ON POLICY "Doctors can view appointments where they are assigned" ON appointments IS
'Allows doctors to view appointments where they are the assigned doctor (via doctor_id column)';

COMMENT ON POLICY "Doctors can view appointments for their patients" ON appointments IS
'Allows doctors to view appointments for patients they have an active relationship with';

COMMENT ON POLICY "Patients can view their own appointments" ON appointments IS
'Allows patients to view their own appointments using user_id';

COMMENT ON POLICY "Doctors can create appointments" ON appointments IS
'Allows doctors to create appointments where they are assigned as the doctor and for their patients';

COMMENT ON POLICY "Patients can create their own appointments" ON appointments IS
'Allows patients to book appointments for themselves';

COMMENT ON POLICY "Doctors can update appointments where they are assigned" ON appointments IS
'Allows doctors to update appointments where they are the assigned doctor';

COMMENT ON POLICY "Doctors can update appointments for their patients" ON appointments IS
'Allows doctors to update appointments for their patients';

COMMENT ON POLICY "Patients can update their own appointments" ON appointments IS
'Allows patients to update (e.g., cancel) their own appointments';

COMMENT ON POLICY "Doctors can delete appointments where they are assigned" ON appointments IS
'Allows doctors to delete appointments where they are the assigned doctor';

COMMENT ON POLICY "Doctors can delete appointments for their patients" ON appointments IS
'Allows doctors to delete appointments for their patients';
