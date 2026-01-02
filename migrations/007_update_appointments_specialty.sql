-- Migration: Add Specialty and Subtype Support to Appointments
-- Description: Extends appointment_type with 2-level specialty system
-- Created: 2025-12-27
-- Purpose: Enable specialty-specific appointment types (e.g., OB/GYN → Infertility)

-- ==============================================================================
-- ADD SPECIALTY COLUMNS TO APPOINTMENTS TABLE
-- ==============================================================================

ALTER TABLE appointments
  ADD COLUMN IF NOT EXISTS specialty TEXT DEFAULT 'general',
  ADD COLUMN IF NOT EXISTS specialty_subtype TEXT;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_appointments_specialty ON appointments(specialty);
CREATE INDEX IF NOT EXISTS idx_appointments_specialty_subtype ON appointments(specialty_subtype);
CREATE INDEX IF NOT EXISTS idx_appointments_specialty_combined ON appointments(specialty, specialty_subtype);

-- Add column comments for documentation
COMMENT ON COLUMN appointments.specialty IS 'Medical specialty (general, obgyn, cardiology, etc.)';
COMMENT ON COLUMN appointments.specialty_subtype IS 'Specialty subtype (e.g., infertility, antenatal, routine_gyn for OBGYN)';

-- ==============================================================================
-- MIGRATE EXISTING DATA
-- ==============================================================================

-- Set specialty to 'general' for all existing appointments
UPDATE appointments
SET specialty = 'general'
WHERE specialty IS NULL;

-- ==============================================================================
-- CREATE HELPER FUNCTION: PARSE APPOINTMENT TYPE
-- ==============================================================================

CREATE OR REPLACE FUNCTION parse_appointment_type(p_appointment_type TEXT)
RETURNS TABLE(specialty TEXT, specialty_subtype TEXT) AS $$
BEGIN
  -- Parse appointment_type like 'obgyn_infertility' into specialty and subtype
  IF p_appointment_type LIKE '%\_%' THEN
    RETURN QUERY SELECT
      split_part(p_appointment_type, '_', 1)::TEXT,
      split_part(p_appointment_type, '_', 2)::TEXT;
  ELSE
    RETURN QUERY SELECT
      p_appointment_type::TEXT,
      NULL::TEXT;
  END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION parse_appointment_type(TEXT) IS 'Parses appointment_type string into specialty and subtype components';

-- ==============================================================================
-- CREATE HELPER FUNCTION: BUILD APPOINTMENT TYPE
-- ==============================================================================

CREATE OR REPLACE FUNCTION build_appointment_type(p_specialty TEXT, p_subtype TEXT DEFAULT NULL)
RETURNS TEXT AS $$
BEGIN
  IF p_subtype IS NOT NULL THEN
    RETURN p_specialty || '_' || p_subtype;
  ELSE
    RETURN p_specialty;
  END IF;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION build_appointment_type(TEXT, TEXT) IS 'Builds appointment_type string from specialty and subtype';

-- ==============================================================================
-- MIGRATION NOTES
-- ==============================================================================
-- This migration enables a 2-level appointment system:
-- - Level 1: Specialty (general, obgyn, cardiology, neurology, etc.)
-- - Level 2: Subtype (infertility, antenatal, routine_gyn for OBGYN)
--
-- The existing `appointment_type` column is kept for backward compatibility
-- New appointments should set both specialty+subtype AND appointment_type
--
-- Examples:
-- - General appointment: specialty='general', specialty_subtype=NULL
-- - OBGYN Infertility: specialty='obgyn', specialty_subtype='infertility'
-- - OBGYN Antenatal: specialty='obgyn', specialty_subtype='antenatal'
--
-- Usage:
-- SELECT * FROM parse_appointment_type('obgyn_infertility');
-- SELECT build_appointment_type('obgyn', 'infertility');
-- ==============================================================================
