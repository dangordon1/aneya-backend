-- Migration: Create Infertility Forms Table
-- Description: Specialty-specific table for infertility consultation forms
-- Created: 2025-12-27
-- Purpose: Pilot implementation for multi-specialty forms system with JSONB flexibility

-- ==============================================================================
-- CREATE INFERTILITY_FORMS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS infertility_forms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,

  -- Form metadata
  form_type TEXT CHECK (form_type IN ('pre_consultation', 'during_consultation')),
  status TEXT CHECK (status IN ('draft', 'partial', 'completed')) DEFAULT 'draft',
  filled_by UUID REFERENCES auth.users(id), -- NULL if patient, doctor_id if doctor-filled

  -- Reference to shared health records (prevents duplication)
  vitals_record_id UUID REFERENCES patient_vitals(id),

  -- Infertility-specific fields (JSONB for flexibility - no schema updates needed)
  infertility_data JSONB NOT NULL DEFAULT '{}',

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  created_by UUID REFERENCES auth.users(id),
  updated_by UUID REFERENCES auth.users(id)
);

-- Create indexes for common queries
CREATE INDEX idx_infertility_forms_patient ON infertility_forms(patient_id);
CREATE INDEX idx_infertility_forms_appointment ON infertility_forms(appointment_id);
CREATE INDEX idx_infertility_forms_status ON infertility_forms(status);
CREATE INDEX idx_infertility_forms_form_type ON infertility_forms(form_type);

-- JSONB GIN index for querying nested fields efficiently
CREATE INDEX idx_infertility_data ON infertility_forms USING gin(infertility_data);

-- Add column comments for documentation
COMMENT ON TABLE infertility_forms IS 'Specialty-specific forms for infertility consultations';
COMMENT ON COLUMN infertility_forms.form_type IS 'When form is filled: pre_consultation (patient) or during_consultation (doctor)';
COMMENT ON COLUMN infertility_forms.status IS 'Form completion status: draft, partial, completed';
COMMENT ON COLUMN infertility_forms.filled_by IS 'NULL if filled by patient, doctor user_id if filled by doctor';
COMMENT ON COLUMN infertility_forms.vitals_record_id IS 'Reference to shared patient_vitals table (prevents duplication)';
COMMENT ON COLUMN infertility_forms.infertility_data IS 'JSONB containing all infertility-specific fields (flexible schema)';

-- ==============================================================================
-- INFERTILITY_DATA JSONB STRUCTURE (DOCUMENTED)
-- ==============================================================================
-- {
--   "infertility_type": "primary" | "secondary",
--
--   "menstrual_history": {
--     "lmp": "2024-01-15",
--     "cycle_length_days": 28,
--     "cycle_regularity": "regular" | "irregular" | "absent",
--     "bleeding_pattern": {
--       "normal_flow": true,
--       "heavy_bleeding": false,
--       "light_bleeding": false,
--       "menstrual_clotting": false,
--       "premenstrual_spotting": false,
--       "postmenstrual_spotting": false,
--       "postcoital_bleeding": false,
--       "intermenstrual_bleeding": false
--     }
--   },
--
--   "sexual_history": {
--     "dyspareunia": false,  // pain during intercourse (Complaints section)
--     "dyspareunia_description": "..."
--     // NOTE: frequency and satisfaction fields removed to match paper form
--   },
--
--   "medical_history": {
--     "diabetes": false,
--     "hypertension": false,
--     "thyroid_disorder": false,
--     "pcos": false,
--     "endometriosis": false,
--     "previous_surgeries": ["laparoscopy"]
--   },
--
--   "previous_treatment": {
--     "ovulation_induction": true,
--     "iui_cycles": 2,
--     "ivf_cycles": 1,
--     "ivf_outcomes": [
--       {
--         "cycle_number": 1,
--         "outcome": "not_pregnant",
--         "date": "2024-06-01"
--       }
--     ]
--   },
--
--   "investigations": {
--     "hormones": {
--       "fsh": 8.5,
--       "lh": 5.2,
--       "amh": 2.1,
--       "prolactin": 15,
--       "thyroid": {
--         "tsh": 2.5,
--         "t3": 1.2,
--         "t4": 9.0
--       }
--     },
--     "ultrasound": {
--       "date": "2024-01-10",
--       "findings": "Normal uterus, bilateral ovaries visualized",
--       "antral_follicle_count": 12
--     },
--     "hsg": {
--       "date": "2024-02-15",
--       "findings": "Both tubes patent",
--       "tubes_patent": true
--     },
--     "semen_analysis": {
--       "date": "2024-01-20",
--       "count": 20,  // million/mL
--       "motility": 60,  // percentage
--       "morphology": 4  // percentage normal
--     }
--   },
--
--   "treatment_cycles": [
--     {
--       "date": "2024-03-01",
--       "cycle_type": "IUI",
--       "medications": "Letrozole 5mg, HCG trigger",
--       "outcome": "Not pregnant",
--       "notes": "..."
--     }
--   ]
-- }
-- ==============================================================================

-- ==============================================================================
-- CREATE TRIGGER FOR UPDATED_AT
-- ==============================================================================

CREATE OR REPLACE FUNCTION update_infertility_forms_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_infertility_forms_timestamp
  BEFORE UPDATE ON infertility_forms
  FOR EACH ROW
  EXECUTE FUNCTION update_infertility_forms_timestamp();

-- ==============================================================================
-- MIGRATION NOTES
-- ==============================================================================
-- This table implements the JSONB-based flexible schema approach:
-- - No schema updates needed to add new fields
-- - GIN index enables fast JSONB queries
-- - References shared health records (vitals) to prevent duplication
-- - Field registration in field_definitions table happens at application layer
--
-- Benefits:
-- 1. Rapid iteration - add fields without migrations
-- 2. Type safety - validated by TypeScript interfaces
-- 3. Performance - GIN indexes provide fast queries
-- 4. No duplication - shared data stored in generic tables
--
-- Next steps:
-- - Create TypeScript interfaces (InfertilityFormData)
-- - Build InfertilityPreConsultationForm component
-- - Implement useInfertilityForms hook
-- - Add field registration logic
-- ==============================================================================
