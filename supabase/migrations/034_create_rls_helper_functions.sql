-- Create SECURITY DEFINER helper functions to break circular RLS dependencies
--
-- ISSUE: Infinite recursion detected in RLS policies when querying with foreign key expansions
-- SOLUTION: Create helper functions that bypass RLS and replace circular subqueries
--
-- These functions are marked as STABLE (cached per transaction) and SECURITY DEFINER
-- (bypass RLS) to break the circular dependency chain in RLS policies.

-- Function 1: Get patient UUID for a given user_id
-- Used to replace: patient_id IN (SELECT id FROM patients WHERE user_id = auth.uid()::text)
CREATE OR REPLACE FUNCTION get_user_patient_id(p_user_id text)
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT id FROM patients WHERE user_id = p_user_id LIMIT 1;
$$;

COMMENT ON FUNCTION get_user_patient_id(text) IS
'Returns the patient UUID for a given user_id. SECURITY DEFINER bypasses RLS to prevent circular dependencies. STABLE caching ensures it is called once per transaction.';

-- Function 2: Get doctor UUID for a given user_id
-- Used to replace: doctor_id IN (SELECT id FROM doctors WHERE user_id = auth.uid()::text)
CREATE OR REPLACE FUNCTION get_user_doctor_id(p_user_id text)
RETURNS uuid
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT id FROM doctors WHERE user_id = p_user_id LIMIT 1;
$$;

COMMENT ON FUNCTION get_user_doctor_id(text) IS
'Returns the doctor UUID for a given user_id. SECURITY DEFINER bypasses RLS to prevent circular dependencies. STABLE caching ensures it is called once per transaction.';

-- Function 3: Check if user has active patient relationship
-- Used to replace: patient_id IN (SELECT pd.patient_id FROM patient_doctor pd JOIN doctors d ...)
CREATE OR REPLACE FUNCTION user_has_patient_relationship(p_patient_id uuid, p_user_id text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM patient_doctor pd
    INNER JOIN doctors d ON d.id = pd.doctor_id
    WHERE pd.patient_id = p_patient_id
      AND d.user_id = p_user_id
      AND pd.status = 'active'
  );
$$;

COMMENT ON FUNCTION user_has_patient_relationship(uuid, text) IS
'Checks if a doctor (identified by user_id) has an active relationship with a patient. SECURITY DEFINER bypasses RLS to prevent circular dependencies. STABLE caching ensures it is called once per transaction.';

-- Grant execute permissions to authenticated users
GRANT EXECUTE ON FUNCTION get_user_patient_id(text) TO authenticated;
GRANT EXECUTE ON FUNCTION get_user_doctor_id(text) TO authenticated;
GRANT EXECUTE ON FUNCTION user_has_patient_relationship(uuid, text) TO authenticated;

-- Grant execute permissions to service role (backend)
GRANT EXECUTE ON FUNCTION get_user_patient_id(text) TO service_role;
GRANT EXECUTE ON FUNCTION get_user_doctor_id(text) TO service_role;
GRANT EXECUTE ON FUNCTION user_has_patient_relationship(uuid, text) TO service_role;
