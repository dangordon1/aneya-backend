-- Fix security flaw: Replace overly permissive messages RLS policies
--
-- SECURITY FIX: messages table allowed users to send messages as anyone.
--
-- This migration restricts access so that:
-- 1. Users can only send messages as themselves (sender verification)
-- 2. Users can only view messages they sent or received
-- 3. Users can only mark their received messages as read

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Users can view their messages" ON messages;
DROP POLICY IF EXISTS "Users can send messages" ON messages;
DROP POLICY IF EXISTS "Users can update received messages" ON messages;

-- SELECT Policy: Users can view messages they sent or received
CREATE POLICY "Users can view their own messages"
  ON messages
  FOR SELECT
  TO public
  USING (
    (sender_type = 'doctor' AND sender_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    ))
    OR
    (sender_type = 'patient' AND sender_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    ))
    OR
    (recipient_type = 'doctor' AND recipient_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    ))
    OR
    (recipient_type = 'patient' AND recipient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    ))
  );

-- INSERT Policy: Users can send messages as themselves
-- Enforces that sender_id matches the current user
CREATE POLICY "Users can send messages as themselves"
  ON messages
  FOR INSERT
  TO public
  WITH CHECK (
    (sender_type = 'doctor' AND sender_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    ))
    OR
    (sender_type = 'patient' AND sender_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    ))
  );

-- UPDATE Policy: Users can only update messages they received (for marking as read)
CREATE POLICY "Users can update received messages"
  ON messages
  FOR UPDATE
  TO public
  USING (
    (recipient_type = 'doctor' AND recipient_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    ))
    OR
    (recipient_type = 'patient' AND recipient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    ))
  )
  WITH CHECK (
    (recipient_type = 'doctor' AND recipient_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    ))
    OR
    (recipient_type = 'patient' AND recipient_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    ))
  );

-- DELETE Policy: Users can delete messages they sent
CREATE POLICY "Users can delete messages they sent"
  ON messages
  FOR DELETE
  TO public
  USING (
    (sender_type = 'doctor' AND sender_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    ))
    OR
    (sender_type = 'patient' AND sender_id IN (
      SELECT id FROM patients WHERE user_id = auth.uid()::text
    ))
  );

-- Ensure indexes exist
CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender_type, sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_type, recipient_id);
CREATE INDEX IF NOT EXISTS idx_messages_patient_doctor ON messages(patient_doctor_id);

-- Add helpful comments
COMMENT ON POLICY "Users can view their own messages" ON messages IS
'Allows users to view messages they sent or received';

COMMENT ON POLICY "Users can send messages as themselves" ON messages IS
'Allows users to send messages but only as themselves (prevents impersonation)';

COMMENT ON POLICY "Users can update received messages" ON messages IS
'Allows users to update (mark as read) messages they received';

COMMENT ON POLICY "Users can delete messages they sent" ON messages IS
'Allows users to delete messages they sent';
