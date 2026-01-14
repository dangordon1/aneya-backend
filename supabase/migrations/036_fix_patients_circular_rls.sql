-- Fix infinite recursion in patients RLS policies
--
-- ISSUE: Patients RLS policies query patient_doctor table with joins,
--        creating circular dependencies when appointments query patients
--
-- SOLUTION: Replace circular subqueries with SECURITY DEFINER helper functions
--
-- This migration updates patients RLS policies to use the helper functions
-- created in migration 034_create_rls_helper_functions.sql

-- ============================================================================
-- SELECT POLICIES
-- ============================================================================

-- Fix SELECT Policy 1: Doctors can view their patients
-- BEFORE: Complex subquery to patient_doctor joined with doctors (causes recursion)
-- AFTER: Use helper function that bypasses RLS
DROP POLICY IF EXISTS "Doctors can view their patients" ON patients;

CREATE POLICY "Doctors can view their patients"
  ON patients
  FOR SELECT
  TO public
  USING (
    user_has_patient_relationship(id, auth.uid()::text)
  );

COMMENT ON POLICY "Doctors can view their patients" ON patients IS
'Allows doctors to view patients they have an active relationship with. Uses helper function to prevent RLS recursion.';

-- ============================================================================
-- UPDATE POLICIES
-- ============================================================================

-- Fix UPDATE Policy 1: Doctors can update their patients
-- BEFORE: Complex subquery to patient_doctor in both USING and WITH CHECK
-- AFTER: Use helper function that bypasses RLS
DROP POLICY IF EXISTS "Doctors can update their patients" ON patients;

CREATE POLICY "Doctors can update their patients"
  ON patients
  FOR UPDATE
  TO public
  USING (
    user_has_patient_relationship(id, auth.uid()::text)
  )
  WITH CHECK (
    user_has_patient_relationship(id, auth.uid()::text)
  );

COMMENT ON POLICY "Doctors can update their patients" ON patients IS
'Allows doctors to update patient information for patients they have an active relationship with. Uses helper function to prevent RLS recursion.';
