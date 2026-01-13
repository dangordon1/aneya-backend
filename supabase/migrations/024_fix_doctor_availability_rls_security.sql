-- Fix security flaw: Replace overly permissive doctor_availability RLS policies
--
-- SECURITY FIX: doctor_availability table was previously writable by anonymous users.
--
-- This migration restricts access so that:
-- 1. All authenticated users can view doctor availability (for booking)
-- 2. Only doctors can create/update/delete their own availability
-- 3. No anonymous write access

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Allow read access for all users" ON doctor_availability;
DROP POLICY IF EXISTS "Anon can delete doctor_availability" ON doctor_availability;
DROP POLICY IF EXISTS "Anon can insert doctor_availability" ON doctor_availability;
DROP POLICY IF EXISTS "Anon can update doctor_availability" ON doctor_availability;
DROP POLICY IF EXISTS "Doctors can delete their own availability" ON doctor_availability;
DROP POLICY IF EXISTS "Doctors can manage their own availability" ON doctor_availability;
DROP POLICY IF EXISTS "Doctors can update their own availability" ON doctor_availability;
DROP POLICY IF EXISTS "Enable read access for all users" ON doctor_availability;
DROP POLICY IF EXISTS "Users can view doctor_availability" ON doctor_availability;

-- SELECT Policy: All authenticated users can view availability (for booking)
CREATE POLICY "Authenticated users can view all doctor availability"
  ON doctor_availability
  FOR SELECT
  TO public
  USING (
    auth.uid() IS NOT NULL
  );

-- INSERT Policy: Only doctors can create their own availability
CREATE POLICY "Doctors can create their own availability"
  ON doctor_availability
  FOR INSERT
  TO public
  WITH CHECK (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- UPDATE Policy: Only doctors can update their own availability
CREATE POLICY "Doctors can update their own availability"
  ON doctor_availability
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

-- DELETE Policy: Only doctors can delete their own availability
CREATE POLICY "Doctors can delete their own availability"
  ON doctor_availability
  FOR DELETE
  TO public
  USING (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- Ensure indexes exist
CREATE INDEX IF NOT EXISTS idx_doctor_availability_doctor_id ON doctor_availability(doctor_id);
CREATE INDEX IF NOT EXISTS idx_doctor_availability_day_of_week ON doctor_availability(day_of_week);

-- Add helpful comments
COMMENT ON POLICY "Authenticated users can view all doctor availability" ON doctor_availability IS
'Allows authenticated users to view doctor availability for booking appointments';

COMMENT ON POLICY "Doctors can create their own availability" ON doctor_availability IS
'Allows doctors to create their own availability schedule';

COMMENT ON POLICY "Doctors can update their own availability" ON doctor_availability IS
'Allows doctors to update only their own availability schedule';

COMMENT ON POLICY "Doctors can delete their own availability" ON doctor_availability IS
'Allows doctors to delete only their own availability slots';
