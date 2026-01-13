-- Migration 026: Create doctor_adopted_forms junction table for "My Forms" library
-- This table tracks which public forms each doctor has adopted into their personal library

-- Create junction table for doctor-form library
CREATE TABLE doctor_adopted_forms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  doctor_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  form_id UUID NOT NULL REFERENCES custom_forms(id) ON DELETE CASCADE,
  adopted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  auto_adopted BOOLEAN NOT NULL DEFAULT false,
  UNIQUE(doctor_id, form_id)  -- Prevent duplicate adoptions
);

-- Create indexes for performance
CREATE INDEX idx_doctor_adopted_forms_doctor_id ON doctor_adopted_forms(doctor_id);
CREATE INDEX idx_doctor_adopted_forms_form_id ON doctor_adopted_forms(form_id);
CREATE INDEX idx_doctor_adopted_forms_adopted_at ON doctor_adopted_forms(adopted_at);

-- Add comments
COMMENT ON TABLE doctor_adopted_forms IS
'Tracks which public forms each doctor has adopted into their "My Forms" library. Owned forms (created_by doctor) are NOT in this table - they are tracked via custom_forms.created_by. This table only stores adoptions of public forms.';

COMMENT ON COLUMN doctor_adopted_forms.auto_adopted IS
'True if form was automatically adopted based on doctor specialty match. False if manually added by doctor via "Add Form" button.';

-- Helper function to auto-adopt public forms by specialty
CREATE OR REPLACE FUNCTION auto_adopt_forms_for_doctor(
  p_doctor_id UUID,
  p_specialty TEXT
) RETURNS INTEGER AS $$
DECLARE
  forms_added INTEGER := 0;
BEGIN
  -- Insert public forms in doctor's specialty that aren't already adopted
  -- This is idempotent - won't create duplicates
  INSERT INTO doctor_adopted_forms (doctor_id, form_id, auto_adopted)
  SELECT
    p_doctor_id,
    cf.id,
    true
  FROM custom_forms cf
  WHERE cf.specialty = p_specialty
    AND cf.is_public = true
    AND cf.status = 'active'
    AND cf.created_by != p_doctor_id  -- Don't adopt your own forms
    AND NOT EXISTS (
      SELECT 1 FROM doctor_adopted_forms daf
      WHERE daf.doctor_id = p_doctor_id AND daf.form_id = cf.id
    );

  GET DIAGNOSTICS forms_added = ROW_COUNT;
  RETURN forms_added;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION auto_adopt_forms_for_doctor IS
'Auto-adopts all public forms in the specified specialty for a doctor. Called when doctor accesses "My Forms" for the first time or when new public forms are created. Returns count of forms added. Idempotent - will not create duplicates.';
