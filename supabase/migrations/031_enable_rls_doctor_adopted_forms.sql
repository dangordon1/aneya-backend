-- Enable RLS on doctor_adopted_forms table
--
-- SECURITY FIX: doctor_adopted_forms table currently has NO RLS protection.
--
-- This migration:
-- 1. Enables RLS on doctor_adopted_forms
-- 2. Doctors can view forms they've adopted
-- 3. Doctors can adopt/unadopt forms for themselves
-- 4. All doctors can view public forms to decide on adoption

-- Enable Row Level Security
ALTER TABLE doctor_adopted_forms ENABLE ROW LEVEL SECURITY;

-- SELECT Policy: Doctors can view forms they've adopted
CREATE POLICY "Doctors can view forms they adopted"
  ON doctor_adopted_forms
  FOR SELECT
  TO public
  USING (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- INSERT Policy: Doctors can adopt forms for themselves
CREATE POLICY "Doctors can adopt forms for themselves"
  ON doctor_adopted_forms
  FOR INSERT
  TO public
  WITH CHECK (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- DELETE Policy: Doctors can unadopt forms they previously adopted
CREATE POLICY "Doctors can unadopt their adopted forms"
  ON doctor_adopted_forms
  FOR DELETE
  TO public
  USING (
    doctor_id IN (
      SELECT id FROM doctors WHERE user_id = auth.uid()::text
    )
  );

-- No UPDATE policy needed - this is a simple junction table with no updatable fields
-- Forms are adopted via INSERT and unadopted via DELETE

-- Ensure indexes exist
CREATE INDEX IF NOT EXISTS idx_doctor_adopted_forms_doctor_id ON doctor_adopted_forms(doctor_id);
CREATE INDEX IF NOT EXISTS idx_doctor_adopted_forms_form_id ON doctor_adopted_forms(form_id);

-- Add helpful comments
COMMENT ON POLICY "Doctors can view forms they adopted" ON doctor_adopted_forms IS
'Allows doctors to view which forms they have adopted';

COMMENT ON POLICY "Doctors can adopt forms for themselves" ON doctor_adopted_forms IS
'Allows doctors to adopt public forms into their practice';

COMMENT ON POLICY "Doctors can unadopt their adopted forms" ON doctor_adopted_forms IS
'Allows doctors to remove forms they previously adopted';
