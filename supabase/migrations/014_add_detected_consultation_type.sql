-- Migration: Add detected_consultation_type to consultations table
-- Purpose: Store AI-detected consultation type from form auto-fill feature
-- This allows the frontend to show the correct form component based on actual consultation content

-- Add detected_consultation_type column
ALTER TABLE consultations
ADD COLUMN detected_consultation_type TEXT CHECK (detected_consultation_type IN ('obgyn', 'infertility', 'antenatal'));

-- Add comment explaining the column
COMMENT ON COLUMN consultations.detected_consultation_type IS 'AI-detected consultation type from form auto-fill. Determines which specialty form to display. Null if consultation has not been processed for form auto-fill.';
