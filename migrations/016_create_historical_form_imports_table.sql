-- Migration: Create Historical Form Imports Table
-- Description: Store uploaded historical patient forms for review and approval
-- Created: 2025-12-30
-- Purpose: Allow doctors to upload past appointment forms and update patient records after review

-- ==============================================================================
-- CREATE HISTORICAL_FORM_IMPORTS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS historical_form_imports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Patient and doctor identification
  patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  uploaded_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE, -- Doctor who uploaded

  -- File metadata
  file_count INTEGER NOT NULL,
  file_metadata JSONB NOT NULL DEFAULT '[]', -- Array of {file_name, file_type, gcs_path, file_size_bytes}

  -- Extracted data organized by target tables
  extracted_data JSONB NOT NULL DEFAULT '{}', -- {demographics: {...}, vitals: [{...}], medications: [{...}], allergies: [{...}], forms: [{form_type, data}]}

  -- Current patient data snapshot (for comparison)
  current_data JSONB NOT NULL DEFAULT '{}', -- Same structure as extracted_data

  -- Conflict analysis
  conflicts JSONB NOT NULL DEFAULT '{}', -- {field_path: {current_value, extracted_value, conflict_type}}
  has_conflicts BOOLEAN DEFAULT false,

  -- Processing metadata
  extraction_confidence NUMERIC(3,2), -- 0.00 to 1.00 confidence score from AI
  fields_extracted INTEGER, -- Total number of fields extracted
  processing_status TEXT CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed')) DEFAULT 'pending',
  processing_error TEXT, -- Error message if processing failed
  processed_at TIMESTAMPTZ,

  -- Review status
  review_status TEXT CHECK (review_status IN ('pending_review', 'approved', 'rejected', 'partially_approved')) DEFAULT 'pending_review',
  reviewed_by UUID REFERENCES auth.users(id),
  reviewed_at TIMESTAMPTZ,

  -- Approval decisions
  approved_fields JSONB DEFAULT '[]', -- Array of field paths that were approved (e.g., ["demographics.phone", "vitals.0.systolic_bp"])
  rejected_fields JSONB DEFAULT '[]', -- Array of field paths that were rejected
  review_notes TEXT, -- Doctor's notes about the review

  -- Form date (when the original form was filled)
  form_date DATE, -- Extracted or manually entered date of the original appointment

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ==============================================================================
-- CREATE INDEXES
-- ==============================================================================

CREATE INDEX idx_historical_imports_patient ON historical_form_imports(patient_id);
CREATE INDEX idx_historical_imports_uploaded_by ON historical_form_imports(uploaded_by);
CREATE INDEX idx_historical_imports_review_status ON historical_form_imports(review_status);
CREATE INDEX idx_historical_imports_processing_status ON historical_form_imports(processing_status);
CREATE INDEX idx_historical_imports_has_conflicts ON historical_form_imports(has_conflicts) WHERE has_conflicts = true;
CREATE INDEX idx_historical_imports_form_date ON historical_form_imports(form_date);
CREATE INDEX idx_historical_imports_created_at ON historical_form_imports(created_at);

-- GIN indexes for querying JSONB data
CREATE INDEX idx_historical_imports_extracted_data ON historical_form_imports USING gin(extracted_data);
CREATE INDEX idx_historical_imports_conflicts ON historical_form_imports USING gin(conflicts);
CREATE INDEX idx_historical_imports_file_metadata ON historical_form_imports USING gin(file_metadata);

-- ==============================================================================
-- ADD COMMENTS
-- ==============================================================================

COMMENT ON TABLE historical_form_imports IS 'Uploaded historical patient forms pending doctor review and approval';
COMMENT ON COLUMN historical_form_imports.patient_id IS 'Patient whose historical data is being imported';
COMMENT ON COLUMN historical_form_imports.uploaded_by IS 'Doctor who uploaded the historical forms';
COMMENT ON COLUMN historical_form_imports.file_metadata IS 'Array of uploaded file information with GCS paths';
COMMENT ON COLUMN historical_form_imports.extracted_data IS 'Structured data extracted from uploaded forms organized by target tables';
COMMENT ON COLUMN historical_form_imports.current_data IS 'Snapshot of current patient data for comparison';
COMMENT ON COLUMN historical_form_imports.conflicts IS 'Detected conflicts between extracted and current data';
COMMENT ON COLUMN historical_form_imports.has_conflicts IS 'Quick flag for filtering imports with conflicts';
COMMENT ON COLUMN historical_form_imports.extraction_confidence IS 'AI confidence score (0-1) for data extraction quality';
COMMENT ON COLUMN historical_form_imports.processing_status IS 'File processing status: pending, processing, completed, failed';
COMMENT ON COLUMN historical_form_imports.review_status IS 'Doctor review status: pending_review, approved, rejected, partially_approved';
COMMENT ON COLUMN historical_form_imports.approved_fields IS 'Array of field paths approved by doctor for import';
COMMENT ON COLUMN historical_form_imports.rejected_fields IS 'Array of field paths rejected by doctor';
COMMENT ON COLUMN historical_form_imports.form_date IS 'Original date when the form was filled (extracted or manually entered)';

-- ==============================================================================
-- CREATE TRIGGER FOR UPDATED_AT
-- ==============================================================================

CREATE OR REPLACE FUNCTION update_historical_imports_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_historical_imports_timestamp
  BEFORE UPDATE ON historical_form_imports
  FOR EACH ROW
  EXECUTE FUNCTION update_historical_imports_timestamp();

-- ==============================================================================
-- CREATE TRIGGER FOR REVIEW TIMESTAMP
-- ==============================================================================

CREATE OR REPLACE FUNCTION set_historical_import_reviewed_at()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.review_status IN ('approved', 'rejected', 'partially_approved')
     AND OLD.review_status = 'pending_review' THEN
    NEW.reviewed_at = now();
    IF NEW.reviewed_by IS NULL THEN
      NEW.reviewed_by = auth.uid();
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_historical_import_reviewed_at
  BEFORE UPDATE ON historical_form_imports
  FOR EACH ROW
  EXECUTE FUNCTION set_historical_import_reviewed_at();

-- ==============================================================================
-- CREATE IMPORT APPLIED RECORDS TABLE
-- ==============================================================================
-- Track which imports have been applied and what records were created/updated

CREATE TABLE IF NOT EXISTS historical_import_applied_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  import_id UUID NOT NULL REFERENCES historical_form_imports(id) ON DELETE CASCADE,

  -- Record tracking
  table_name TEXT NOT NULL, -- e.g., 'patient_demographics', 'patient_vitals', 'patient_medications'
  record_id UUID NOT NULL, -- The ID of the created/updated record
  operation TEXT CHECK (operation IN ('insert', 'update')) NOT NULL,

  -- Data snapshot
  previous_data JSONB, -- Previous record data (NULL for inserts)
  new_data JSONB NOT NULL, -- New/updated record data

  -- Timestamps
  applied_at TIMESTAMPTZ DEFAULT now(),
  applied_by UUID NOT NULL REFERENCES auth.users(id)
);

CREATE INDEX idx_import_applied_records_import ON historical_import_applied_records(import_id);
CREATE INDEX idx_import_applied_records_table ON historical_import_applied_records(table_name);
CREATE INDEX idx_import_applied_records_record ON historical_import_applied_records(record_id);
CREATE INDEX idx_import_applied_records_applied_by ON historical_import_applied_records(applied_by);

COMMENT ON TABLE historical_import_applied_records IS 'Audit trail of records created/updated from historical form imports';
COMMENT ON COLUMN historical_import_applied_records.import_id IS 'Reference to the import that created this record';
COMMENT ON COLUMN historical_import_applied_records.table_name IS 'Database table where record was created/updated';
COMMENT ON COLUMN historical_import_applied_records.record_id IS 'ID of the record in the target table';
COMMENT ON COLUMN historical_import_applied_records.operation IS 'Whether record was inserted or updated';
COMMENT ON COLUMN historical_import_applied_records.previous_data IS 'Snapshot of data before update (NULL for inserts)';
COMMENT ON COLUMN historical_import_applied_records.new_data IS 'Snapshot of data after insert/update';

-- ==============================================================================
-- ENABLE ROW LEVEL SECURITY (RLS)
-- ==============================================================================

ALTER TABLE historical_form_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE historical_import_applied_records ENABLE ROW LEVEL SECURITY;

-- Policy: Doctors can view imports for their patients
CREATE POLICY historical_imports_select ON historical_form_imports
  FOR SELECT
  USING (
    auth.uid() = uploaded_by
    OR patient_id IN (
      SELECT id FROM patients WHERE created_by = auth.uid()::text
    )
  );

-- Policy: Doctors can create imports for their patients
CREATE POLICY historical_imports_insert ON historical_form_imports
  FOR INSERT
  WITH CHECK (
    auth.uid() = uploaded_by
    AND patient_id IN (
      SELECT id FROM patients WHERE created_by = auth.uid()::text
    )
  );

-- Policy: Doctors can update imports they created or for their patients
CREATE POLICY historical_imports_update ON historical_form_imports
  FOR UPDATE
  USING (
    auth.uid() = uploaded_by
    OR patient_id IN (
      SELECT id FROM patients WHERE created_by = auth.uid()::text
    )
  );

-- Policy: Doctors can delete pending imports they created
CREATE POLICY historical_imports_delete ON historical_form_imports
  FOR DELETE
  USING (
    auth.uid() = uploaded_by
    AND review_status = 'pending_review'
  );

-- Policy: Doctors can view applied records for their patients
CREATE POLICY import_applied_records_select ON historical_import_applied_records
  FOR SELECT
  USING (
    auth.uid() = applied_by
    OR import_id IN (
      SELECT id FROM historical_form_imports
      WHERE patient_id IN (
        SELECT id FROM patients WHERE created_by = auth.uid()::text
      )
    )
  );

-- Policy: System can insert applied records
CREATE POLICY import_applied_records_insert ON historical_import_applied_records
  FOR INSERT
  WITH CHECK (auth.uid() = applied_by);

-- ==============================================================================
-- MIGRATION NOTES
-- ==============================================================================
-- This migration creates infrastructure for historical form imports:
--
-- Key Features:
-- 1. Upload historical patient forms (images, PDFs, digital data)
-- 2. AI-powered data extraction using Claude Vision API
-- 3. Conflict detection comparing extracted vs current patient data
-- 4. Review UI showing side-by-side comparison
-- 5. Doctor approval workflow with field-level granularity
-- 6. Audit trail of all applied changes
-- 7. Support for multiple file formats per import
--
-- Workflow:
-- 1. Doctor uploads historical forms for a patient
-- 2. System processes files (OCR, PDF extraction, etc.)
-- 3. AI extracts structured data and detects conflicts
-- 4. Doctor reviews in UI with side-by-side comparison
-- 5. Doctor approves/rejects specific fields
-- 6. System applies approved changes to patient record
-- 7. Audit trail created in historical_import_applied_records
--
-- Extracted Data Structure:
-- {
--   "demographics": {
--     "name": "John Doe",
--     "date_of_birth": "1990-01-15",
--     "phone": "+91-9876543210",
--     ...
--   },
--   "vitals": [
--     {
--       "recorded_at": "2024-01-15T10:30:00Z",
--       "systolic_bp": 120,
--       "diastolic_bp": 80,
--       ...
--     }
--   ],
--   "medications": [
--     {
--       "medication_name": "Metformin",
--       "dosage": "500mg",
--       "frequency": "Twice daily",
--       ...
--     }
--   ],
--   "allergies": [
--     {
--       "allergen": "Penicillin",
--       "severity": "severe",
--       "reaction": "Anaphylaxis"
--     }
--   ],
--   "forms": [
--     {
--       "form_type": "obgyn",
--       "form_subtype": "pre_consultation",
--       "data": {...}
--     }
--   ]
-- }
--
-- Conflict Structure:
-- {
--   "demographics.phone": {
--     "current_value": "+91-9876543210",
--     "extracted_value": "+91-9876543211",
--     "conflict_type": "value_mismatch"
--   },
--   "vitals.0.systolic_bp": {
--     "current_value": 118,
--     "extracted_value": 120,
--     "conflict_type": "close_match"
--   }
-- }
-- ==============================================================================
