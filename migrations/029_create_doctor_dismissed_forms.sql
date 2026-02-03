-- Migration 029: Create doctor_dismissed_forms table to track forms a doctor has explicitly removed
-- This prevents auto_adopt_forms_for_doctor from re-adopting forms a doctor has dismissed

-- Drop the old UUID-parameter overload that's no longer used
DROP FUNCTION IF EXISTS auto_adopt_forms_for_doctor(UUID, TEXT);

CREATE TABLE IF NOT EXISTS doctor_dismissed_forms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
  form_id UUID NOT NULL REFERENCES custom_forms(id) ON DELETE CASCADE,
  dismissed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(doctor_id, form_id)
);

CREATE INDEX IF NOT EXISTS idx_doctor_dismissed_forms_doctor_id ON doctor_dismissed_forms(doctor_id);

COMMENT ON TABLE doctor_dismissed_forms IS
'Tracks forms a doctor has explicitly removed from their library. Used by auto_adopt_forms_for_doctor to avoid re-adopting dismissed forms.';

-- Update auto_adopt_forms_for_doctor to exclude dismissed forms
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
    RETURN 0;
  END IF;

  -- Insert public forms in doctor's specialty that aren't already adopted AND aren't dismissed
  INSERT INTO doctor_adopted_forms (doctor_id, form_id, auto_adopted)
  SELECT
    v_doctor_id,
    cf.id,
    true
  FROM custom_forms cf
  WHERE cf.specialty = p_specialty
    AND cf.is_public = true
    AND cf.status = 'active'
    AND cf.created_by != p_firebase_user_id
    AND NOT EXISTS (
      SELECT 1 FROM doctor_adopted_forms daf
      WHERE daf.doctor_id = v_doctor_id AND daf.form_id = cf.id
    )
    AND NOT EXISTS (
      SELECT 1 FROM doctor_dismissed_forms ddf
      WHERE ddf.doctor_id = v_doctor_id AND ddf.form_id = cf.id
    );

  GET DIAGNOSTICS forms_added = ROW_COUNT;
  RETURN forms_added;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION auto_adopt_forms_for_doctor(TEXT, TEXT) IS
'Auto-adopts all public forms in the specified specialty for a doctor. Takes Firebase user_id and converts to doctor UUID. Skips forms the doctor has previously dismissed. Returns count of forms added. Idempotent - will not create duplicates.';
