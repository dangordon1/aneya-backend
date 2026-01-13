-- Enable RLS on field_definitions table
--
-- SECURITY FIX: field_definitions table currently has NO RLS protection.
--
-- This migration:
-- 1. Enables RLS on field_definitions
-- 2. Allows all authenticated users to view field definitions (needed for forms)
-- 3. Only admins can create/update field definitions
-- 4. No deletion (system metadata)

-- Enable Row Level Security
ALTER TABLE field_definitions ENABLE ROW LEVEL SECURITY;

-- SELECT Policy: All authenticated users can view field definitions
-- This is needed for form rendering and validation
CREATE POLICY "Authenticated users can view field definitions"
  ON field_definitions
  FOR SELECT
  TO public
  USING (
    auth.uid() IS NOT NULL
  );

-- INSERT Policy: Only superadmins can create field definitions
CREATE POLICY "Only superadmins can create field definitions"
  ON field_definitions
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

-- UPDATE Policy: Only superadmins can update field definitions
CREATE POLICY "Only superadmins can update field definitions"
  ON field_definitions
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

-- DELETE Policy: Only superadmins can delete field definitions
CREATE POLICY "Only superadmins can delete field definitions"
  ON field_definitions
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
CREATE INDEX IF NOT EXISTS idx_field_definitions_field_name ON field_definitions(field_name);
CREATE INDEX IF NOT EXISTS idx_field_definitions_field_type ON field_definitions(field_type);

-- Add helpful comments
COMMENT ON POLICY "Authenticated users can view field definitions" ON field_definitions IS
'Allows all authenticated users to view field definitions for form rendering and validation';

COMMENT ON POLICY "Only superadmins can create field definitions" ON field_definitions IS
'Restricts field definition creation to superadmins only';

COMMENT ON POLICY "Only superadmins can update field definitions" ON field_definitions IS
'Restricts field definition updates to superadmins only';

COMMENT ON POLICY "Only superadmins can delete field definitions" ON field_definitions IS
'Restricts field definition deletion to superadmins only';
