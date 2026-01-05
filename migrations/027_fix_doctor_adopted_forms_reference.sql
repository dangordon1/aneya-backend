-- Migration 027: Fix doctor_adopted_forms to reference doctors table instead of auth.users
-- The issue: doctor_id references auth.users(id) but we need doctors(id) for our UUID lookup

-- Drop existing foreign key constraint
ALTER TABLE doctor_adopted_forms
DROP CONSTRAINT IF EXISTS doctor_adopted_forms_doctor_id_fkey;

-- Add correct foreign key constraint to doctors table
ALTER TABLE doctor_adopted_forms
ADD CONSTRAINT doctor_adopted_forms_doctor_id_fkey
FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE;

-- Update the function to use doctors.id instead of Firebase user_id
CREATE OR REPLACE FUNCTION auto_adopt_forms_for_doctor(
  p_firebase_user_id TEXT,
  p_specialty TEXT
) RETURNS INTEGER AS $$
DECLARE
  v_doctor_id UUID;
  forms_added INTEGER := 0;
BEGIN
  -- Get doctor's UUID from Firebase user_id
  SELECT id INTO v_doctor_id
  FROM doctors
  WHERE user_id = p_firebase_user_id;

  IF v_doctor_id IS NULL THEN
    -- Doctor not found, return 0
    RETURN 0;
  END IF;

  -- Insert public forms in doctor's specialty that aren't already adopted
  INSERT INTO doctor_adopted_forms (doctor_id, form_id, auto_adopted)
  SELECT
    v_doctor_id,
    cf.id,
    true
  FROM custom_forms cf
  WHERE cf.specialty = p_specialty
    AND cf.is_public = true
    AND cf.status = 'active'
    AND cf.created_by != p_firebase_user_id  -- Don't adopt your own forms
    AND NOT EXISTS (
      SELECT 1 FROM doctor_adopted_forms daf
      WHERE daf.doctor_id = v_doctor_id AND daf.form_id = cf.id
    );

  GET DIAGNOSTICS forms_added = ROW_COUNT;
  RETURN forms_added;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION auto_adopt_forms_for_doctor IS
'Auto-adopts all public forms in the specified specialty for a doctor. Takes Firebase user_id and converts to doctor UUID. Returns count of forms added. Idempotent - will not create duplicates.';
