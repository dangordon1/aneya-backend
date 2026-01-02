-- Migration: Create Custom Forms Table
-- Description: Store doctor-uploaded custom form schemas
-- Created: 2025-12-30
-- Purpose: Allow doctors to create custom forms for their specialty

-- ==============================================================================
-- CREATE CUSTOM_FORMS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS custom_forms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Form identification
  form_name TEXT NOT NULL,
  specialty TEXT NOT NULL,

  -- Ownership and permissions
  created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  organization_id UUID, -- NULL means available to all, otherwise restricted to organization
  is_public BOOLEAN DEFAULT false, -- If true, available to all doctors

  -- Form schema (JSONB for flexibility)
  form_schema JSONB NOT NULL,

  -- Generated code artifacts
  schema_code TEXT, -- Python schema definition
  migration_sql TEXT, -- SQL migration for form data table
  typescript_types TEXT, -- TypeScript type definitions

  -- Metadata
  description TEXT,
  field_count INTEGER,
  section_count INTEGER,
  image_count INTEGER,

  -- Status
  status TEXT CHECK (status IN ('draft', 'active', 'archived')) DEFAULT 'draft',

  -- Versioning
  version INTEGER DEFAULT 1,
  parent_form_id UUID REFERENCES custom_forms(id), -- For form revisions

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  activated_at TIMESTAMPTZ, -- When status changed to 'active'

  -- Constraints
  UNIQUE(form_name, created_by, version)
);

-- ==============================================================================
-- CREATE INDEXES
-- ==============================================================================

CREATE INDEX idx_custom_forms_created_by ON custom_forms(created_by);
CREATE INDEX idx_custom_forms_specialty ON custom_forms(specialty);
CREATE INDEX idx_custom_forms_status ON custom_forms(status);
CREATE INDEX idx_custom_forms_organization ON custom_forms(organization_id);
CREATE INDEX idx_custom_forms_public ON custom_forms(is_public) WHERE is_public = true;
CREATE INDEX idx_custom_forms_form_name ON custom_forms(form_name);

-- GIN index for querying form schema
CREATE INDEX idx_custom_forms_schema ON custom_forms USING gin(form_schema);

-- ==============================================================================
-- ADD COMMENTS
-- ==============================================================================

COMMENT ON TABLE custom_forms IS 'Doctor-uploaded custom form schemas organized by specialty';
COMMENT ON COLUMN custom_forms.form_name IS 'Form identifier in snake_case (e.g., cardiology_consultation)';
COMMENT ON COLUMN custom_forms.specialty IS 'Medical specialty (e.g., cardiology, neurology)';
COMMENT ON COLUMN custom_forms.created_by IS 'Doctor who created this form';
COMMENT ON COLUMN custom_forms.organization_id IS 'If set, form is only available to this organization';
COMMENT ON COLUMN custom_forms.is_public IS 'If true, form is available to all doctors';
COMMENT ON COLUMN custom_forms.form_schema IS 'JSONB schema definition matching Aneya schema format';
COMMENT ON COLUMN custom_forms.status IS 'Form lifecycle: draft (editing), active (in use), archived (deprecated)';
COMMENT ON COLUMN custom_forms.version IS 'Version number for form revisions';
COMMENT ON COLUMN custom_forms.parent_form_id IS 'Link to previous version if this is a revision';

-- ==============================================================================
-- CREATE TRIGGER FOR UPDATED_AT
-- ==============================================================================

CREATE OR REPLACE FUNCTION update_custom_forms_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_custom_forms_timestamp
  BEFORE UPDATE ON custom_forms
  FOR EACH ROW
  EXECUTE FUNCTION update_custom_forms_timestamp();

-- ==============================================================================
-- CREATE TRIGGER FOR ACTIVATED_AT
-- ==============================================================================

CREATE OR REPLACE FUNCTION set_custom_form_activated_at()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status = 'active' AND OLD.status != 'active' THEN
    NEW.activated_at = now();
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_custom_form_activated_at
  BEFORE UPDATE ON custom_forms
  FOR EACH ROW
  EXECUTE FUNCTION set_custom_form_activated_at();

-- ==============================================================================
-- CREATE CUSTOM_FORM_INSTANCES TABLE
-- ==============================================================================
-- This table stores actual form data instances (filled forms)

CREATE TABLE IF NOT EXISTS custom_form_instances (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  custom_form_id UUID NOT NULL REFERENCES custom_forms(id) ON DELETE CASCADE,
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,

  -- Form metadata
  form_type TEXT CHECK (form_type IN ('pre_consultation', 'during_consultation')),
  status TEXT CHECK (status IN ('draft', 'partial', 'completed')) DEFAULT 'draft',
  filled_by UUID REFERENCES auth.users(id),

  -- Form data (JSONB for flexibility)
  form_data JSONB NOT NULL DEFAULT '{}',

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  created_by UUID REFERENCES auth.users(id),
  updated_by UUID REFERENCES auth.users(id)
);

-- Indexes for custom_form_instances
CREATE INDEX idx_custom_form_instances_custom_form ON custom_form_instances(custom_form_id);
CREATE INDEX idx_custom_form_instances_patient ON custom_form_instances(patient_id);
CREATE INDEX idx_custom_form_instances_appointment ON custom_form_instances(appointment_id);
CREATE INDEX idx_custom_form_instances_status ON custom_form_instances(status);

-- GIN index for querying form data
CREATE INDEX idx_custom_form_instances_data ON custom_form_instances USING gin(form_data);

COMMENT ON TABLE custom_form_instances IS 'Filled instances of custom forms';
COMMENT ON COLUMN custom_form_instances.custom_form_id IS 'Reference to custom form definition';
COMMENT ON COLUMN custom_form_instances.form_data IS 'JSONB containing all form field values';

-- Trigger for updated_at
CREATE TRIGGER trigger_update_custom_form_instances_timestamp
  BEFORE UPDATE ON custom_form_instances
  FOR EACH ROW
  EXECUTE FUNCTION update_custom_forms_timestamp();

-- ==============================================================================
-- ENABLE ROW LEVEL SECURITY (RLS)
-- ==============================================================================

ALTER TABLE custom_forms ENABLE ROW LEVEL SECURITY;
ALTER TABLE custom_form_instances ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own forms
CREATE POLICY custom_forms_select_own ON custom_forms
  FOR SELECT
  USING (auth.uid() = created_by);

-- Policy: Users can view public forms
CREATE POLICY custom_forms_select_public ON custom_forms
  FOR SELECT
  USING (is_public = true AND status = 'active');

-- Policy: Users can insert their own forms
CREATE POLICY custom_forms_insert ON custom_forms
  FOR INSERT
  WITH CHECK (auth.uid() = created_by);

-- Policy: Users can update their own forms
CREATE POLICY custom_forms_update ON custom_forms
  FOR UPDATE
  USING (auth.uid() = created_by);

-- Policy: Users can delete their own draft forms
CREATE POLICY custom_forms_delete ON custom_forms
  FOR DELETE
  USING (auth.uid() = created_by AND status = 'draft');

-- Policy: Users can view form instances they created or for their patients
CREATE POLICY custom_form_instances_select ON custom_form_instances
  FOR SELECT
  USING (
    auth.uid() = created_by
    OR auth.uid() = filled_by
    OR patient_id IN (
      SELECT id FROM patients WHERE created_by::uuid = auth.uid()
    )
  );

-- Policy: Users can insert form instances
CREATE POLICY custom_form_instances_insert ON custom_form_instances
  FOR INSERT
  WITH CHECK (auth.uid() = created_by);

-- Policy: Users can update form instances they created
CREATE POLICY custom_form_instances_update ON custom_form_instances
  FOR UPDATE
  USING (auth.uid() = created_by OR auth.uid() = updated_by);

-- ==============================================================================
-- MIGRATION NOTES
-- ==============================================================================
-- This migration creates infrastructure for doctor-uploaded custom forms:
--
-- Key Features:
-- 1. Doctor-specific forms with ownership tracking
-- 2. Organization-level or public sharing
-- 3. Version control for form revisions
-- 4. JSONB storage for flexible schema
-- 5. Separate table for form instances (actual filled forms)
-- 6. RLS policies for data security
--
-- Workflow:
-- 1. Doctor uploads form images via API
-- 2. Form converter generates schema
-- 3. Schema stored in custom_forms table
-- 4. Doctor can activate form for use
-- 5. Form instances created when patients fill forms
--
-- Next steps:
-- - Add API endpoints for custom form management
-- - Create frontend UI for form upload
-- - Implement form sharing/publishing workflow
-- ==============================================================================
