-- Fix security flaw: Replace overly permissive doctors RLS policies
--
-- SECURITY FIX: doctors table was previously writable by anonymous users.
--
-- This migration restricts access so that:
-- 1. All authenticated users can view doctor profiles (for booking appointments)
-- 2. Doctors can only update their own profile
-- 3. Only authenticated users can create doctor profiles (registration)
-- 4. No anonymous write access

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Allow read access for all users" ON doctors;
DROP POLICY IF EXISTS "Anon can insert doctors" ON doctors;
DROP POLICY IF EXISTS "Anon can update doctors" ON doctors;
DROP POLICY IF EXISTS "Doctors can insert their own profile" ON doctors;
DROP POLICY IF EXISTS "Doctors can update their own profile" ON doctors;
DROP POLICY IF EXISTS "Enable read access for all users" ON doctors;
DROP POLICY IF EXISTS "Users can view doctors" ON doctors;

-- SELECT Policy: All authenticated users can view doctor profiles (for booking)
CREATE POLICY "Authenticated users can view all doctors"
  ON doctors
  FOR SELECT
  TO public
  USING (
    auth.uid() IS NOT NULL
  );

-- INSERT Policy: Only authenticated users can create their own doctor profile
CREATE POLICY "Authenticated users can create their own doctor profile"
  ON doctors
  FOR INSERT
  TO public
  WITH CHECK (
    user_id = auth.uid()::text
  );

-- UPDATE Policy: Doctors can only update their own profile
CREATE POLICY "Doctors can update their own profile"
  ON doctors
  FOR UPDATE
  TO public
  USING (
    user_id = auth.uid()::text
  )
  WITH CHECK (
    user_id = auth.uid()::text
  );

-- DELETE Policy: Only superadmins can delete doctor profiles
CREATE POLICY "Only superadmins can delete doctor profiles"
  ON doctors
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

-- Ensure indexes exist
CREATE INDEX IF NOT EXISTS idx_doctors_user_id ON doctors(user_id);
CREATE INDEX IF NOT EXISTS idx_doctors_specialty ON doctors(specialty);

-- Add helpful comments
COMMENT ON POLICY "Authenticated users can view all doctors" ON doctors IS
'Allows all authenticated users to browse doctor profiles for booking appointments';

COMMENT ON POLICY "Authenticated users can create their own doctor profile" ON doctors IS
'Allows authenticated users to create their own doctor profile during registration';

COMMENT ON POLICY "Doctors can update their own profile" ON doctors IS
'Allows doctors to update only their own profile information';

COMMENT ON POLICY "Only superadmins can delete doctor profiles" ON doctors IS
'Restricts doctor profile deletion to superadmins only';
