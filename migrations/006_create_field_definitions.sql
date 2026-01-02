-- Migration: Create Field Definitions Metadata System
-- Description: Tracks field usage across specialties and enables automatic migration detection
-- Created: 2025-12-27
-- Purpose: Prevent field duplication and enable dynamic form generation

-- ==============================================================================
-- CREATE FIELD_DEFINITIONS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS field_definitions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  field_name TEXT NOT NULL UNIQUE,
  display_label TEXT NOT NULL,
  field_type TEXT NOT NULL CHECK (field_type IN ('text', 'number', 'date', 'boolean', 'select', 'textarea', 'jsonb')),

  -- Usage tracking
  specialties_using TEXT[] DEFAULT ARRAY[]::TEXT[], -- e.g., ['infertility', 'anc', 'routine_gyn']
  usage_count INTEGER DEFAULT 1,
  is_generic BOOLEAN DEFAULT false, -- true if migrated to generic table
  generic_table_name TEXT, -- e.g., 'patient_vitals', 'patient_medications'
  generic_column_name TEXT,

  -- Field configuration (JSONB for flexibility)
  validation_rules JSONB DEFAULT '{}', -- e.g., {"min": 0, "max": 100, "required": true}
  select_options JSONB DEFAULT '[]', -- for select fields: ["option1", "option2"]
  description TEXT,
  clinical_notes TEXT,

  -- Metadata
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  last_used_at TIMESTAMPTZ DEFAULT now()
);

-- Create indexes for common queries
CREATE INDEX idx_field_definitions_field_name ON field_definitions(field_name);
CREATE INDEX idx_field_definitions_is_generic ON field_definitions(is_generic);
CREATE INDEX idx_field_definitions_specialties_using ON field_definitions USING gin(specialties_using);

-- Add column comments for documentation
COMMENT ON TABLE field_definitions IS 'Metadata system tracking field usage across specialties';
COMMENT ON COLUMN field_definitions.specialties_using IS 'Array of specialty names using this field';
COMMENT ON COLUMN field_definitions.usage_count IS 'Total number of times field has been used';
COMMENT ON COLUMN field_definitions.is_generic IS 'True if field has been migrated to a generic table';
COMMENT ON COLUMN field_definitions.validation_rules IS 'JSONB containing validation constraints';
COMMENT ON COLUMN field_definitions.select_options IS 'JSONB array of options for select fields';

-- ==============================================================================
-- CREATE MIGRATION DETECTION FUNCTION
-- ==============================================================================

CREATE OR REPLACE FUNCTION detect_fields_for_migration()
RETURNS TABLE(field_name TEXT, specialties TEXT[], usage_count INTEGER) AS $$
BEGIN
  RETURN QUERY
  SELECT
    fd.field_name,
    fd.specialties_using,
    fd.usage_count
  FROM field_definitions fd
  WHERE
    array_length(fd.specialties_using, 1) >= 2  -- Used by 2+ specialties
    AND fd.is_generic = false  -- Not already migrated
  ORDER BY fd.usage_count DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION detect_fields_for_migration() IS 'Identifies fields used by 2+ specialties that should be migrated to generic tables';

-- ==============================================================================
-- CREATE FIELD USAGE UPDATE TRIGGER FUNCTION
-- ==============================================================================

CREATE OR REPLACE FUNCTION update_field_usage()
RETURNS TRIGGER AS $$
BEGIN
  -- Update last_used_at timestamp
  NEW.last_used_at = now();

  -- Ensure specialties_using is an array (not null)
  IF NEW.specialties_using IS NULL THEN
    NEW.specialties_using = ARRAY[]::TEXT[];
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to auto-update timestamps
CREATE TRIGGER trigger_update_field_usage
  BEFORE UPDATE ON field_definitions
  FOR EACH ROW
  EXECUTE FUNCTION update_field_usage();

COMMENT ON FUNCTION update_field_usage() IS 'Trigger function to update field usage metadata';

-- ==============================================================================
-- HELPER FUNCTION: REGISTER FIELD USAGE
-- ==============================================================================

CREATE OR REPLACE FUNCTION register_field_usage(
  p_field_name TEXT,
  p_specialty TEXT,
  p_display_label TEXT DEFAULT NULL,
  p_field_type TEXT DEFAULT 'text'
)
RETURNS void AS $$
BEGIN
  INSERT INTO field_definitions (field_name, display_label, field_type, specialties_using, usage_count)
  VALUES (
    p_field_name,
    COALESCE(p_display_label, p_field_name),
    p_field_type,
    ARRAY[p_specialty],
    1
  )
  ON CONFLICT (field_name) DO UPDATE SET
    specialties_using = CASE
      WHEN NOT (p_specialty = ANY(field_definitions.specialties_using))
      THEN array_append(field_definitions.specialties_using, p_specialty)
      ELSE field_definitions.specialties_using
    END,
    usage_count = field_definitions.usage_count + 1,
    last_used_at = now();
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION register_field_usage(TEXT, TEXT, TEXT, TEXT) IS 'Registers or updates field usage for a specific specialty';

-- ==============================================================================
-- MIGRATION NOTES
-- ==============================================================================
-- This system enables:
-- 1. Automatic detection of fields used by multiple specialties
-- 2. Prevention of field duplication across specialty forms
-- 3. Dynamic form generation based on field definitions
-- 4. Migration path from JSONB to typed columns when needed
--
-- Usage:
-- SELECT * FROM detect_fields_for_migration();
-- SELECT register_field_usage('cycle_length_days', 'infertility', 'Cycle Length (days)', 'number');
-- ==============================================================================
