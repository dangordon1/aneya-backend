-- Enable RLS on email_verifications table
--
-- SECURITY FIX: email_verifications table has RLS policies but RLS is NOT enabled.
-- This is a critical security flaw discovered by Supabase security advisor.
--
-- This migration:
-- 1. Enables RLS on email_verifications table
-- 2. Keeps existing policies intact (they are already correctly defined)

-- Enable Row Level Security
ALTER TABLE email_verifications ENABLE ROW LEVEL SECURITY;

-- Add comment to document this fix
COMMENT ON TABLE email_verifications IS
'Email verification tracking table with RLS enabled. Fixed in migration 032.';
