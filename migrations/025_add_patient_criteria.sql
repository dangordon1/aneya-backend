-- Migration 025: Add patient_criteria column to custom_forms table
-- This column is referenced in code but was missing from the schema

-- Add patient_criteria column
ALTER TABLE custom_forms
ADD COLUMN patient_criteria TEXT;

-- Add comment explaining usage
COMMENT ON COLUMN custom_forms.patient_criteria IS
'Description of which type of patients or clinical scenarios this form is designed for (e.g., "Pregnant women in antenatal care between 12-40 weeks gestation", "Patients presenting with neurological symptoms requiring initial assessment"). Used by LLM for smart form selection during consultations.';

-- Create GIN index for full-text search on patient_criteria
CREATE INDEX idx_custom_forms_patient_criteria ON custom_forms
USING gin(to_tsvector('english', patient_criteria))
WHERE patient_criteria IS NOT NULL;
