-- Fix circular RLS dependency in patient/appointment access
--
-- ISSUE: Current RLS policies create circular dependencies when querying with joins:
--        patient_doctor RLS → patients RLS → back to patient_doctor table
--        This causes 400/500 errors when doctors try to query their patients
--
-- SOLUTION: Rewrite all RLS policies to use direct inline subqueries without helper functions
--          All policies will inline check against doctors and patient_doctor tables
--          No helper functions needed - breaking the circular dependency at the policy level
--
-- AFFECTED TABLES: 7 tables, 19 policies total
-- - patients (2 policies)
-- - appointments (4 policies)
-- - patient_demographics (3 policies)
-- - infertility_forms (4 policies)
-- - symptom_tracker (1 policy)
-- - consultation_forms (4 policies)
-- - patient_symptoms (1 policy)

-- ============================================================================
-- STEP 1: Fix patients table RLS policies
-- ============================================================================

-- Fix SELECT Policy: Doctors can view their patients
DROP POLICY IF EXISTS "Doctors can view their patients" ON patients;

CREATE POLICY "Doctors can view their patients"
  ON patients
  FOR SELECT
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = patients.id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

COMMENT ON POLICY "Doctors can view their patients" ON patients IS
'Allows doctors to view patients they have an active relationship with. Uses inline EXISTS to prevent RLS recursion.';

-- Fix UPDATE Policy: Doctors can update their patients
DROP POLICY IF EXISTS "Doctors can update their patients" ON patients;

CREATE POLICY "Doctors can update their patients"
  ON patients
  FOR UPDATE
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = patients.id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = patients.id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

COMMENT ON POLICY "Doctors can update their patients" ON patients IS
'Allows doctors to update patient information for patients they have an active relationship with. Uses inline EXISTS to prevent RLS recursion.';

-- ============================================================================
-- STEP 2: Fix appointments table RLS policies
-- ============================================================================

-- Fix SELECT Policy 2: Doctors can view appointments for their patients
DROP POLICY IF EXISTS "Doctors can view appointments for their patients" ON appointments;

CREATE POLICY "Doctors can view appointments for their patients"
  ON appointments
  FOR SELECT
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = appointments.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

COMMENT ON POLICY "Doctors can view appointments for their patients" ON appointments IS
'Allows doctors to view appointments for patients they have an active relationship with. Uses inline EXISTS to prevent RLS recursion.';

-- Fix INSERT Policy 1: Doctors can create appointments
DROP POLICY IF EXISTS "Doctors can create appointments" ON appointments;

CREATE POLICY "Doctors can create appointments"
  ON appointments
  FOR INSERT
  TO public
  WITH CHECK (
    -- Doctor must be assigned to the appointment
    doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
    AND
    -- Patient must be one of the doctor's patients OR booking allowed
    (
      EXISTS (
        SELECT 1
        FROM patient_doctor pd
        WHERE pd.patient_id = appointments.patient_id
          AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
          AND pd.status = 'active'
      )
      OR booked_by = 'patient' -- Allow if patient is booking
    )
  );

COMMENT ON POLICY "Doctors can create appointments" ON appointments IS
'Allows doctors to create appointments where they are assigned and for their patients. Uses inline EXISTS to prevent RLS recursion.';

-- Fix UPDATE Policy 2: Doctors can update appointments for their patients
DROP POLICY IF EXISTS "Doctors can update appointments for their patients" ON appointments;

CREATE POLICY "Doctors can update appointments for their patients"
  ON appointments
  FOR UPDATE
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = appointments.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = appointments.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

COMMENT ON POLICY "Doctors can update appointments for their patients" ON appointments IS
'Allows doctors to update appointments for their patients. Uses inline EXISTS to prevent RLS recursion.';

-- Fix DELETE Policy 2: Doctors can delete appointments for their patients
DROP POLICY IF EXISTS "Doctors can delete appointments for their patients" ON appointments;

CREATE POLICY "Doctors can delete appointments for their patients"
  ON appointments
  FOR DELETE
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = appointments.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

COMMENT ON POLICY "Doctors can delete appointments for their patients" ON appointments IS
'Allows doctors to delete appointments for their patients. Uses inline EXISTS to prevent RLS recursion.';

-- ============================================================================
-- STEP 3: Fix patient_demographics table RLS policies
-- ============================================================================

-- Fix SELECT Policy 1: Doctors can view demographics for their patients
DROP POLICY IF EXISTS "Doctors can view their patients' demographics" ON patient_demographics;

CREATE POLICY "Doctors can view their patients' demographics"
  ON patient_demographics
  FOR SELECT
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = patient_demographics.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

COMMENT ON POLICY "Doctors can view their patients' demographics" ON patient_demographics IS
'Allows doctors to view demographic information for their patients. Uses inline EXISTS to prevent RLS recursion.';

-- Fix INSERT Policy
DROP POLICY IF EXISTS "Doctors and patients can create demographics" ON patient_demographics;

CREATE POLICY "Doctors and patients can create demographics"
  ON patient_demographics
  FOR INSERT
  TO public
  WITH CHECK (
    -- Doctor creating for their patient
    (
      EXISTS (
        SELECT 1
        FROM patient_doctor pd
        WHERE pd.patient_id = patient_demographics.patient_id
          AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
          AND pd.status = 'active'
      )
      AND created_by = auth.uid()
    )
    OR
    -- Patient creating their own
    (
      patient_id = (SELECT id FROM patients WHERE user_id = auth.uid()::text LIMIT 1)
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
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = patient_demographics.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = patient_demographics.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

-- ============================================================================
-- STEP 4: Fix infertility_forms table RLS policies
-- ============================================================================

-- Fix SELECT Policy 1: Doctors can view infertility forms
DROP POLICY IF EXISTS "Doctors can view their patients' infertility forms" ON infertility_forms;

CREATE POLICY "Doctors can view their patients' infertility forms"
  ON infertility_forms
  FOR SELECT
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = infertility_forms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

COMMENT ON POLICY "Doctors can view their patients' infertility forms" ON infertility_forms IS
'Allows doctors to view infertility forms for their patients. Uses inline EXISTS to prevent RLS recursion.';

-- Fix INSERT Policy
DROP POLICY IF EXISTS "Doctors can create infertility forms for their patients" ON infertility_forms;

CREATE POLICY "Doctors can create infertility forms for their patients"
  ON infertility_forms
  FOR INSERT
  TO public
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = infertility_forms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
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
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = infertility_forms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = infertility_forms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

-- Fix DELETE Policy
DROP POLICY IF EXISTS "Doctors can delete their patients' infertility forms" ON infertility_forms;

CREATE POLICY "Doctors can delete their patients' infertility forms"
  ON infertility_forms
  FOR DELETE
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = infertility_forms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

-- ============================================================================
-- STEP 5: Fix symptom_tracker table RLS policies
-- ============================================================================

-- Fix SELECT Policy 2: Doctors can view symptoms
DROP POLICY IF EXISTS "Doctors can view their patients' symptoms" ON symptom_tracker;

CREATE POLICY "Doctors can view their patients' symptoms"
  ON symptom_tracker
  FOR SELECT
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = symptom_tracker.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

COMMENT ON POLICY "Doctors can view their patients' symptoms" ON symptom_tracker IS
'Allows doctors to view symptom records for their patients. Uses inline EXISTS to prevent RLS recursion.';

-- ============================================================================
-- STEP 6: Fix consultation_forms table RLS policies
-- ============================================================================

-- Fix SELECT Policy 1: Doctors can view consultation forms
DROP POLICY IF EXISTS "Doctors can view their patients' consultation forms" ON consultation_forms;

CREATE POLICY "Doctors can view their patients' consultation forms"
  ON consultation_forms
  FOR SELECT
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = consultation_forms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

COMMENT ON POLICY "Doctors can view their patients' consultation forms" ON consultation_forms IS
'Allows doctors to view consultation forms for their patients. Uses inline EXISTS to prevent RLS recursion.';

-- Fix INSERT Policy
DROP POLICY IF EXISTS "Doctors can create consultation forms for their patients" ON consultation_forms;

CREATE POLICY "Doctors can create consultation forms for their patients"
  ON consultation_forms
  FOR INSERT
  TO public
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = consultation_forms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
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
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = consultation_forms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = consultation_forms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

-- Fix DELETE Policy
DROP POLICY IF EXISTS "Doctors can delete their patients' consultation forms" ON consultation_forms;

CREATE POLICY "Doctors can delete their patients' consultation forms"
  ON consultation_forms
  FOR DELETE
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = consultation_forms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

-- ============================================================================
-- STEP 7: Fix patient_symptoms table RLS policies
-- ============================================================================

-- Fix SELECT Policy 2: Doctors can view symptoms
DROP POLICY IF EXISTS "Doctors can view their patients' symptoms" ON patient_symptoms;

CREATE POLICY "Doctors can view their patients' symptoms"
  ON patient_symptoms
  FOR SELECT
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM patient_doctor pd
      WHERE pd.patient_id = patient_symptoms.patient_id
        AND pd.doctor_id = (SELECT id FROM doctors WHERE user_id = auth.uid()::text LIMIT 1)
        AND pd.status = 'active'
    )
  );

COMMENT ON POLICY "Doctors can view their patients' symptoms" ON patient_symptoms IS
'Allows doctors to view symptom records for their patients. Uses inline EXISTS to prevent RLS recursion.';

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Summary:
-- - Updated 19 RLS policies across 7 tables with inline subqueries
-- - All policies now use direct inline queries: (SELECT id FROM doctors WHERE user_id = auth.uid()...)
-- - No helper functions needed - breaks circular dependencies at the policy level
-- - Each policy independently queries doctors/patient_doctor tables
-- - No more circular dependencies: policies check doctors table directly
