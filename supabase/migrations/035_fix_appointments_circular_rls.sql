-- Fix infinite recursion in appointments RLS policies
--
-- ISSUE: Queries like `appointments?select=*,patient:patients(*)` trigger infinite recursion
--        because appointments policies query patients table, which has circular dependencies
--
-- SOLUTION: Replace circular subqueries with SECURITY DEFINER helper functions
--
-- This migration updates all appointments RLS policies to use the helper functions
-- created in migration 034_create_rls_helper_functions.sql

-- ============================================================================
-- SELECT POLICIES
-- ============================================================================

-- Fix SELECT Policy 2: Doctors can view appointments for their patients
-- BEFORE: Subquery to patient_doctor with join to doctors (causes recursion)
-- AFTER: Use helper function that bypasses RLS
DROP POLICY IF EXISTS "Doctors can view appointments for their patients" ON appointments;

CREATE POLICY "Doctors can view appointments for their patients"
  ON appointments
  FOR SELECT
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

COMMENT ON POLICY "Doctors can view appointments for their patients" ON appointments IS
'Allows doctors to view appointments for patients they have an active relationship with. Uses helper function to prevent RLS recursion.';

-- Fix SELECT Policy 3: Patients can view their own appointments
-- BEFORE: Subquery to patients table (triggers patients RLS which causes recursion)
-- AFTER: Use helper function that bypasses RLS
DROP POLICY IF EXISTS "Patients can view their own appointments" ON appointments;

CREATE POLICY "Patients can view their own appointments"
  ON appointments
  FOR SELECT
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

COMMENT ON POLICY "Patients can view their own appointments" ON appointments IS
'Allows patients to view their own appointments. Uses helper function to prevent RLS recursion.';

-- ============================================================================
-- INSERT POLICIES
-- ============================================================================

-- Fix INSERT Policy 1: Doctors can create appointments
-- BEFORE: Subquery to patient_doctor with complex join (causes recursion)
-- AFTER: Use helper function that bypasses RLS
DROP POLICY IF EXISTS "Doctors can create appointments" ON appointments;

CREATE POLICY "Doctors can create appointments"
  ON appointments
  FOR INSERT
  TO public
  WITH CHECK (
    -- Doctor must be assigned to the appointment
    doctor_id = get_user_doctor_id(auth.uid()::text)
    AND
    -- Patient must be one of the doctor's patients OR booking allowed
    (
      user_has_patient_relationship(patient_id, auth.uid()::text)
      OR booked_by = 'patient' -- Allow if patient is booking
    )
  );

COMMENT ON POLICY "Doctors can create appointments" ON appointments IS
'Allows doctors to create appointments where they are assigned and for their patients. Uses helper functions to prevent RLS recursion.';

-- Fix INSERT Policy 2: Patients can create appointments for themselves
-- BEFORE: Subquery to patients table (triggers patients RLS)
-- AFTER: Use helper function that bypasses RLS
DROP POLICY IF EXISTS "Patients can create their own appointments" ON appointments;

CREATE POLICY "Patients can create their own appointments"
  ON appointments
  FOR INSERT
  TO public
  WITH CHECK (
    patient_id = get_user_patient_id(auth.uid()::text)
    AND booked_by = 'patient'
  );

COMMENT ON POLICY "Patients can create their own appointments" ON appointments IS
'Allows patients to book appointments for themselves. Uses helper function to prevent RLS recursion.';

-- ============================================================================
-- UPDATE POLICIES
-- ============================================================================

-- Fix UPDATE Policy 2: Doctors can update appointments for their patients
-- BEFORE: Subquery to patient_doctor in both USING and WITH CHECK
-- AFTER: Use helper function that bypasses RLS
DROP POLICY IF EXISTS "Doctors can update appointments for their patients" ON appointments;

CREATE POLICY "Doctors can update appointments for their patients"
  ON appointments
  FOR UPDATE
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  )
  WITH CHECK (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

COMMENT ON POLICY "Doctors can update appointments for their patients" ON appointments IS
'Allows doctors to update appointments for their patients. Uses helper function to prevent RLS recursion.';

-- Fix UPDATE Policy 3: Patients can update their own appointments
-- BEFORE: Subquery to patients table in both USING and WITH CHECK
-- AFTER: Use helper function that bypasses RLS
DROP POLICY IF EXISTS "Patients can update their own appointments" ON appointments;

CREATE POLICY "Patients can update their own appointments"
  ON appointments
  FOR UPDATE
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  )
  WITH CHECK (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

COMMENT ON POLICY "Patients can update their own appointments" ON appointments IS
'Allows patients to update (e.g., cancel) their own appointments. Uses helper function to prevent RLS recursion.';

-- ============================================================================
-- DELETE POLICIES
-- ============================================================================

-- Fix DELETE Policy 2: Doctors can delete appointments for their patients
-- BEFORE: Subquery to patient_doctor with join
-- AFTER: Use helper function that bypasses RLS
DROP POLICY IF EXISTS "Doctors can delete appointments for their patients" ON appointments;

CREATE POLICY "Doctors can delete appointments for their patients"
  ON appointments
  FOR DELETE
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

COMMENT ON POLICY "Doctors can delete appointments for their patients" ON appointments IS
'Allows doctors to delete appointments for their patients. Uses helper function to prevent RLS recursion.';
