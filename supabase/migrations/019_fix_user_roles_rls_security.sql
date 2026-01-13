-- Fix critical security flaw: Replace overly permissive user_roles RLS policies
-- with proper access controls
--
-- SECURITY FIX: user_roles table was previously writable by anonymous users,
-- allowing anyone to assign themselves admin/superadmin roles.
-- This migration restricts access so that:
-- 1. Users can only view their own role
-- 2. Only superadmins can create/modify user roles
-- 3. No anonymous access whatsoever

-- Drop existing overly permissive policies
DROP POLICY IF EXISTS "Allow read access for all users" ON user_roles;
DROP POLICY IF EXISTS "Allow insert on user_roles for superadmins" ON user_roles;
DROP POLICY IF EXISTS "Allow update on user_roles for superadmins" ON user_roles;
DROP POLICY IF EXISTS "Anon can insert user_roles" ON user_roles;
DROP POLICY IF EXISTS "Anon can update user_roles" ON user_roles;
DROP POLICY IF EXISTS "Enable read access for all users" ON user_roles;

-- SELECT Policy 1: Users can view their own role
CREATE POLICY "Users can view their own role"
  ON user_roles
  FOR SELECT
  TO public
  USING (
    user_id = auth.uid()::text
  );

-- SELECT Policy 2: Superadmins can view all roles
CREATE POLICY "Superadmins can view all roles"
  ON user_roles
  FOR SELECT
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM user_roles ur
      WHERE ur.user_id = auth.uid()::text
        AND ur.role = 'superadmin'
    )
  );

-- INSERT Policy: Only superadmins can create user roles
CREATE POLICY "Only superadmins can create user roles"
  ON user_roles
  FOR INSERT
  TO public
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM user_roles ur
      WHERE ur.user_id = auth.uid()::text
        AND ur.role = 'superadmin'
    )
  );

-- UPDATE Policy: Only superadmins can update user roles
CREATE POLICY "Only superadmins can update user roles"
  ON user_roles
  FOR UPDATE
  TO public
  USING (
    EXISTS (
      SELECT 1
      FROM user_roles ur
      WHERE ur.user_id = auth.uid()::text
        AND ur.role = 'superadmin'
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1
      FROM user_roles ur
      WHERE ur.user_id = auth.uid()::text
        AND ur.role = 'superadmin'
    )
  );

-- DELETE Policy: Only superadmins can delete user roles
CREATE POLICY "Only superadmins can delete user roles"
  ON user_roles
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

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_role ON user_roles(role);

-- Add helpful comments
COMMENT ON POLICY "Users can view their own role" ON user_roles IS
'Allows users to view their own assigned role for authorization checks';

COMMENT ON POLICY "Superadmins can view all roles" ON user_roles IS
'Allows superadmins to view all user roles for user management';

COMMENT ON POLICY "Only superadmins can create user roles" ON user_roles IS
'Restricts role creation to superadmins only to prevent privilege escalation';

COMMENT ON POLICY "Only superadmins can update user roles" ON user_roles IS
'Restricts role updates to superadmins only to prevent privilege escalation';

COMMENT ON POLICY "Only superadmins can delete user roles" ON user_roles IS
'Restricts role deletion to superadmins only';
