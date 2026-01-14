-- Fix infinite recursion in remaining tables with circular RLS policies
--
-- ISSUE: Multiple tables have RLS policies that query patients/doctors tables,
--        creating circular dependencies similar to appointments table
--
-- SOLUTION: Replace circular subqueries with SECURITY DEFINER helper functions
--
-- This migration fixes RLS policies in 6 tables:
-- 1. patient_demographics
-- 2. infertility_forms
-- 3. messages
-- 4. symptom_tracker
-- 5. consultation_forms
-- 6. patient_symptoms

-- ============================================================================
-- TABLE 1: patient_demographics
-- ============================================================================

-- Fix SELECT Policy 1: Doctors can view demographics for their patients
DROP POLICY IF EXISTS "Doctors can view their patients' demographics" ON patient_demographics;

CREATE POLICY "Doctors can view their patients' demographics"
  ON patient_demographics
  FOR SELECT
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

-- Fix SELECT Policy 2: Patients can view their own demographics
DROP POLICY IF EXISTS "Patients can view their own demographics" ON patient_demographics;

CREATE POLICY "Patients can view their own demographics"
  ON patient_demographics
  FOR SELECT
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- Fix INSERT Policy
DROP POLICY IF EXISTS "Doctors and patients can create demographics" ON patient_demographics;

CREATE POLICY "Doctors and patients can create demographics"
  ON patient_demographics
  FOR INSERT
  TO public
  WITH CHECK (
    -- Doctor creating for their patient
    (
      user_has_patient_relationship(patient_id, auth.uid()::text)
      AND created_by = auth.uid()
    )
    OR
    -- Patient creating their own
    (
      patient_id = get_user_patient_id(auth.uid()::text)
      AND created_by = auth.uid()
    )
  );

-- Fix UPDATE Policy 1: Doctors can update demographics
DROP POLICY IF EXISTS "Doctors can update their patients' demographics" ON patient_demographics;

CREATE POLICY "Doctors can update their patients' demographics"
  ON patient_demographics
  FOR UPDATE
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  )
  WITH CHECK (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

-- Fix UPDATE Policy 2: Patients can update their own demographics
DROP POLICY IF EXISTS "Patients can update their own demographics" ON patient_demographics;

CREATE POLICY "Patients can update their own demographics"
  ON patient_demographics
  FOR UPDATE
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  )
  WITH CHECK (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- ============================================================================
-- TABLE 2: infertility_forms
-- ============================================================================

-- Fix SELECT Policy 1: Doctors can view infertility forms
DROP POLICY IF EXISTS "Doctors can view their patients' infertility forms" ON infertility_forms;

CREATE POLICY "Doctors can view their patients' infertility forms"
  ON infertility_forms
  FOR SELECT
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

-- Fix SELECT Policy 2: Patients can view their own forms
DROP POLICY IF EXISTS "Patients can view their own infertility forms" ON infertility_forms;

CREATE POLICY "Patients can view their own infertility forms"
  ON infertility_forms
  FOR SELECT
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- Fix INSERT Policy
DROP POLICY IF EXISTS "Doctors can create infertility forms for their patients" ON infertility_forms;

CREATE POLICY "Doctors can create infertility forms for their patients"
  ON infertility_forms
  FOR INSERT
  TO public
  WITH CHECK (
    user_has_patient_relationship(patient_id, auth.uid()::text)
    AND
    (filled_by = auth.uid() OR current_user = 'service_role')
  );

-- Fix UPDATE Policy
DROP POLICY IF EXISTS "Doctors can update their patients' infertility forms" ON infertility_forms;

CREATE POLICY "Doctors can update their patients' infertility forms"
  ON infertility_forms
  FOR UPDATE
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  )
  WITH CHECK (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

-- Fix DELETE Policy
DROP POLICY IF EXISTS "Doctors can delete their patients' infertility forms" ON infertility_forms;

CREATE POLICY "Doctors can delete their patients' infertility forms"
  ON infertility_forms
  FOR DELETE
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

-- ============================================================================
-- TABLE 3: messages
-- ============================================================================

-- Fix SELECT Policy: Users can view their own messages
DROP POLICY IF EXISTS "Users can view their own messages" ON messages;

CREATE POLICY "Users can view their own messages"
  ON messages
  FOR SELECT
  TO public
  USING (
    (sender_type = 'doctor' AND sender_id = get_user_doctor_id(auth.uid()::text))
    OR
    (sender_type = 'patient' AND sender_id = get_user_patient_id(auth.uid()::text))
    OR
    (recipient_type = 'doctor' AND recipient_id = get_user_doctor_id(auth.uid()::text))
    OR
    (recipient_type = 'patient' AND recipient_id = get_user_patient_id(auth.uid()::text))
  );

-- Fix INSERT Policy
DROP POLICY IF EXISTS "Users can send messages as themselves" ON messages;

CREATE POLICY "Users can send messages as themselves"
  ON messages
  FOR INSERT
  TO public
  WITH CHECK (
    (sender_type = 'doctor' AND sender_id = get_user_doctor_id(auth.uid()::text))
    OR
    (sender_type = 'patient' AND sender_id = get_user_patient_id(auth.uid()::text))
  );

-- Fix UPDATE Policy
DROP POLICY IF EXISTS "Users can update received messages" ON messages;

CREATE POLICY "Users can update received messages"
  ON messages
  FOR UPDATE
  TO public
  USING (
    (recipient_type = 'doctor' AND recipient_id = get_user_doctor_id(auth.uid()::text))
    OR
    (recipient_type = 'patient' AND recipient_id = get_user_patient_id(auth.uid()::text))
  )
  WITH CHECK (
    (recipient_type = 'doctor' AND recipient_id = get_user_doctor_id(auth.uid()::text))
    OR
    (recipient_type = 'patient' AND recipient_id = get_user_patient_id(auth.uid()::text))
  );

-- Fix DELETE Policy
DROP POLICY IF EXISTS "Users can delete messages they sent" ON messages;

CREATE POLICY "Users can delete messages they sent"
  ON messages
  FOR DELETE
  TO public
  USING (
    (sender_type = 'doctor' AND sender_id = get_user_doctor_id(auth.uid()::text))
    OR
    (sender_type = 'patient' AND sender_id = get_user_patient_id(auth.uid()::text))
  );

-- ============================================================================
-- TABLE 4: symptom_tracker
-- ============================================================================

-- Fix SELECT Policy 1: Patients can view their own symptoms
DROP POLICY IF EXISTS "Patients can view their own symptoms" ON symptom_tracker;

CREATE POLICY "Patients can view their own symptoms"
  ON symptom_tracker
  FOR SELECT
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- Fix SELECT Policy 2: Doctors can view symptoms
DROP POLICY IF EXISTS "Doctors can view their patients' symptoms" ON symptom_tracker;

CREATE POLICY "Doctors can view their patients' symptoms"
  ON symptom_tracker
  FOR SELECT
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

-- Fix INSERT Policy
DROP POLICY IF EXISTS "Patients can create their own symptoms" ON symptom_tracker;

CREATE POLICY "Patients can create their own symptoms"
  ON symptom_tracker
  FOR INSERT
  TO public
  WITH CHECK (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- Fix UPDATE Policy
DROP POLICY IF EXISTS "Patients can update their own symptoms" ON symptom_tracker;

CREATE POLICY "Patients can update their own symptoms"
  ON symptom_tracker
  FOR UPDATE
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  )
  WITH CHECK (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- Fix DELETE Policy
DROP POLICY IF EXISTS "Patients can delete their own symptoms" ON symptom_tracker;

CREATE POLICY "Patients can delete their own symptoms"
  ON symptom_tracker
  FOR DELETE
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- ============================================================================
-- TABLE 5: consultation_forms
-- ============================================================================

-- Fix SELECT Policy 1: Doctors can view consultation forms
DROP POLICY IF EXISTS "Doctors can view their patients' consultation forms" ON consultation_forms;

CREATE POLICY "Doctors can view their patients' consultation forms"
  ON consultation_forms
  FOR SELECT
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

-- Fix SELECT Policy 2: Patients can view their own forms
DROP POLICY IF EXISTS "Patients can view their own consultation forms" ON consultation_forms;

CREATE POLICY "Patients can view their own consultation forms"
  ON consultation_forms
  FOR SELECT
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- Fix INSERT Policy
DROP POLICY IF EXISTS "Doctors can create consultation forms for their patients" ON consultation_forms;

CREATE POLICY "Doctors can create consultation forms for their patients"
  ON consultation_forms
  FOR INSERT
  TO public
  WITH CHECK (
    user_has_patient_relationship(patient_id, auth.uid()::text)
    AND
    created_by = auth.uid()::text
  );

-- Fix UPDATE Policy
DROP POLICY IF EXISTS "Doctors can update their patients' consultation forms" ON consultation_forms;

CREATE POLICY "Doctors can update their patients' consultation forms"
  ON consultation_forms
  FOR UPDATE
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  )
  WITH CHECK (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

-- Fix DELETE Policy
DROP POLICY IF EXISTS "Doctors can delete their patients' consultation forms" ON consultation_forms;

CREATE POLICY "Doctors can delete their patients' consultation forms"
  ON consultation_forms
  FOR DELETE
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

-- ============================================================================
-- TABLE 6: patient_symptoms
-- ============================================================================

-- Fix SELECT Policy 1: Patients can view their own symptoms
DROP POLICY IF EXISTS "Patients can view their own symptoms" ON patient_symptoms;

CREATE POLICY "Patients can view their own symptoms"
  ON patient_symptoms
  FOR SELECT
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- Fix SELECT Policy 2: Doctors can view symptoms
DROP POLICY IF EXISTS "Doctors can view their patients' symptoms" ON patient_symptoms;

CREATE POLICY "Doctors can view their patients' symptoms"
  ON patient_symptoms
  FOR SELECT
  TO public
  USING (
    user_has_patient_relationship(patient_id, auth.uid()::text)
  );

-- Fix INSERT Policy
DROP POLICY IF EXISTS "Patients can create their own symptoms" ON patient_symptoms;

CREATE POLICY "Patients can create their own symptoms"
  ON patient_symptoms
  FOR INSERT
  TO public
  WITH CHECK (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- Fix UPDATE Policy
DROP POLICY IF EXISTS "Patients can update their own symptoms" ON patient_symptoms;

CREATE POLICY "Patients can update their own symptoms"
  ON patient_symptoms
  FOR UPDATE
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  )
  WITH CHECK (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- Fix DELETE Policy
DROP POLICY IF EXISTS "Patients can delete their own symptoms" ON patient_symptoms;

CREATE POLICY "Patients can delete their own symptoms"
  ON patient_symptoms
  FOR DELETE
  TO public
  USING (
    patient_id = get_user_patient_id(auth.uid()::text)
  );

-- ============================================================================
-- UPDATE COMMENTS
-- ============================================================================

-- Update policy comments to reflect the use of helper functions
COMMENT ON POLICY "Doctors can view their patients' demographics" ON patient_demographics IS
'Allows doctors to view demographic information for their patients. Uses helper function to prevent RLS recursion.';

COMMENT ON POLICY "Doctors can view their patients' infertility forms" ON infertility_forms IS
'Allows doctors to view infertility forms for their patients. Uses helper function to prevent RLS recursion.';

COMMENT ON POLICY "Users can view their own messages" ON messages IS
'Allows users to view messages they sent or received. Uses helper functions to prevent RLS recursion.';

COMMENT ON POLICY "Doctors can view their patients' symptoms" ON symptom_tracker IS
'Allows doctors to view symptom records for their patients. Uses helper function to prevent RLS recursion.';

COMMENT ON POLICY "Doctors can view their patients' consultation forms" ON consultation_forms IS
'Allows doctors to view consultation forms for their patients. Uses helper function to prevent RLS recursion.';

COMMENT ON POLICY "Doctors can view their patients' symptoms" ON patient_symptoms IS
'Allows doctors to view symptom records for their patients. Uses helper function to prevent RLS recursion.';
