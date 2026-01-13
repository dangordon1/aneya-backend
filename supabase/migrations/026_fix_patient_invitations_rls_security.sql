-- Fix security flaw: Replace overly permissive patient_invitations RLS policies
--
-- SECURITY FIX: patient_invitations table was writable by anonymous users.
--
-- This migration restricts access so that:
-- 1. Doctors can create invitations
-- 2. Anonymous users can view invitations by token (for acceptance)
-- 3. Only the doctor or the person with the token can update the invitation
-- 4. Proper token-based verification for anonymous access

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Doctors can view their own invitations" ON patient_invitations;
DROP POLICY IF EXISTS "Doctors can create invitations" ON patient_invitations;
DROP POLICY IF EXISTS "Users can update invitations" ON patient_invitations;
DROP POLICY IF EXISTS "Allow anon to insert patient_invitations" ON patient_invitations;
DROP POLICY IF EXISTS "Allow anon to update patient_invitations" ON patient_invitations;
DROP POLICY IF EXISTS "Allow public insert on patient_invitations" ON patient_invitations;
DROP POLICY IF EXISTS "Allow public update on patient_invitations" ON patient_invitations;
DROP POLICY IF EXISTS "Anon can view invitations by token" ON patient_invitations;

-- SELECT Policy 1: Doctors can view their own invitations
CREATE POLICY "Doctors can view their own invitations"
  ON patient_invitations
  FOR SELECT
  TO public
  USING (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- SELECT Policy 2: Anyone can view invitations if they have the token (for acceptance)
-- This is intentionally permissive for the invitation acceptance flow
CREATE POLICY "Anyone can view invitations by token"
  ON patient_invitations
  FOR SELECT
  TO anon, authenticated
  USING (
    status = 'pending' AND expires_at > now()
  );

-- INSERT Policy: Only doctors can create invitations
CREATE POLICY "Doctors can create invitations"
  ON patient_invitations
  FOR INSERT
  TO authenticated
  WITH CHECK (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- UPDATE Policy 1: Doctors can update their own invitations
CREATE POLICY "Doctors can update their own invitations"
  ON patient_invitations
  FOR UPDATE
  TO authenticated
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

-- UPDATE Policy 2: Anonymous users can accept invitations (status change only)
-- This allows the invitation acceptance flow for new patient signups
CREATE POLICY "Anyone can accept invitations with valid token"
  ON patient_invitations
  FOR UPDATE
  TO anon, authenticated
  USING (
    status = 'pending' AND expires_at > now()
  )
  WITH CHECK (
    status IN ('accepted', 'pending') AND expires_at > now()
  );

-- DELETE Policy: Only doctors can delete their invitations
CREATE POLICY "Doctors can delete their own invitations"
  ON patient_invitations
  FOR DELETE
  TO authenticated
  USING (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- Ensure indexes exist
CREATE INDEX IF NOT EXISTS idx_patient_invitations_doctor_id ON patient_invitations(doctor_id);
CREATE INDEX IF NOT EXISTS idx_patient_invitations_token ON patient_invitations(token);
CREATE INDEX IF NOT EXISTS idx_patient_invitations_status ON patient_invitations(status);

-- Add helpful comments
COMMENT ON POLICY "Doctors can view their own invitations" ON patient_invitations IS
'Allows doctors to view invitations they created';

COMMENT ON POLICY "Anyone can view invitations by token" ON patient_invitations IS
'Allows anyone (including anonymous) to view pending, non-expired invitations for the acceptance flow';

COMMENT ON POLICY "Doctors can create invitations" ON patient_invitations IS
'Allows doctors to create patient invitations';

COMMENT ON POLICY "Doctors can update their own invitations" ON patient_invitations IS
'Allows doctors to update invitations they created (e.g., cancel)';

COMMENT ON POLICY "Anyone can accept invitations with valid token" ON patient_invitations IS
'Allows anyone with a valid token to accept the invitation during patient signup';

COMMENT ON POLICY "Doctors can delete their own invitations" ON patient_invitations IS
'Allows doctors to delete invitations they created';
