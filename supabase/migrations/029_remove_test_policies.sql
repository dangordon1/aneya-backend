-- Remove test/development policies from production tables
--
-- SECURITY FIX: Several tables have test policies that should not be in production.
--
-- This migration removes test policies from:
-- 1. antenatal_forms - "Test allow all antenatal inserts" and anon access
-- 2. obgyn_consultation_forms - "Test allow all inserts"

-- Drop test policies from antenatal_forms
DROP POLICY IF EXISTS "Test allow all antenatal inserts" ON antenatal_forms;
DROP POLICY IF EXISTS "Anon can update all antenatal forms" ON antenatal_forms;
DROP POLICY IF EXISTS "Anon can view antenatal forms" ON antenatal_forms;
DROP POLICY IF EXISTS "Anon can insert antenatal forms" ON antenatal_forms;

-- Drop test policies from obgyn_consultation_forms
DROP POLICY IF EXISTS "Test allow all inserts" ON obgyn_consultation_forms;
DROP POLICY IF EXISTS "Anon can insert obgyn forms" ON obgyn_consultation_forms;
DROP POLICY IF EXISTS "Anon can update obgyn forms" ON obgyn_consultation_forms;

-- Note: Proper production policies already exist on these tables from previous migrations
-- These tables already have correct policies in place:
-- - antenatal_forms has proper doctor/patient scoped policies
-- - obgyn_consultation_forms has proper doctor/patient scoped policies

-- Add a comment to document this cleanup
COMMENT ON TABLE antenatal_forms IS
'Antenatal (ANC) forms with proper RLS policies. Test policies removed in migration 029.';

COMMENT ON TABLE obgyn_consultation_forms IS
'OB/GYN consultation forms with proper RLS policies. Test policies removed in migration 029.';
