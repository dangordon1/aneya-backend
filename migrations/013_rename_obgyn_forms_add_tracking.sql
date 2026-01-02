-- Migration: Rename obgyn_forms to obgyn_consultation_forms and add tracking columns
-- Description: Renames the table and adds created_by, updated_by columns to match infertility/antenatal forms
-- Created: 2025-12-29

-- Add new columns before renaming
ALTER TABLE obgyn_forms ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id);
ALTER TABLE obgyn_forms ADD COLUMN IF NOT EXISTS updated_by UUID REFERENCES auth.users(id);
ALTER TABLE obgyn_forms ADD COLUMN IF NOT EXISTS form_type TEXT DEFAULT 'pre_consultation' CHECK (form_type IN ('pre_consultation', 'during_consultation'));
ALTER TABLE obgyn_forms ADD COLUMN IF NOT EXISTS filled_by UUID REFERENCES auth.users(id);

-- Rename table
ALTER TABLE obgyn_forms RENAME TO obgyn_consultation_forms;

-- Update index names
ALTER INDEX IF EXISTS idx_obgyn_forms_patient_id RENAME TO idx_obgyn_consultation_forms_patient_id;
ALTER INDEX IF EXISTS idx_obgyn_forms_appointment_id RENAME TO idx_obgyn_consultation_forms_appointment_id;
ALTER INDEX IF EXISTS idx_obgyn_forms_created_at RENAME TO idx_obgyn_consultation_forms_created_at;
ALTER INDEX IF EXISTS idx_obgyn_forms_status RENAME TO idx_obgyn_consultation_forms_status;
ALTER INDEX IF EXISTS idx_obgyn_forms_vitals_record RENAME TO idx_obgyn_consultation_forms_vitals_record;

-- Update trigger
DROP TRIGGER IF EXISTS trigger_obgyn_forms_updated_at ON obgyn_consultation_forms;
CREATE TRIGGER trigger_obgyn_consultation_forms_updated_at
BEFORE UPDATE ON obgyn_consultation_forms
FOR EACH ROW
EXECUTE FUNCTION update_obgyn_forms_updated_at();

-- Update comments
COMMENT ON TABLE obgyn_consultation_forms IS 'Stores OB/GYN consultation forms (pre and during consultation)';
COMMENT ON COLUMN obgyn_consultation_forms.created_by IS 'User who created this form';
COMMENT ON COLUMN obgyn_consultation_forms.updated_by IS 'User who last updated this form';
COMMENT ON COLUMN obgyn_consultation_forms.form_type IS 'Type of form: pre_consultation or during_consultation';
COMMENT ON COLUMN obgyn_consultation_forms.filled_by IS 'User ID who filled the form (doctor or patient)';
