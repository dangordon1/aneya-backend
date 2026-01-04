-- Migration: Add table_metadata column to custom_forms
-- Purpose: Store classification metadata for form tables (data source types, field mappings)
-- Run this in Supabase SQL Editor

-- Add column to store table classification metadata
ALTER TABLE custom_forms
ADD COLUMN IF NOT EXISTS table_metadata JSONB;

-- Create GIN index for fast JSONB queries on table_metadata
CREATE INDEX IF NOT EXISTS idx_custom_forms_table_metadata
ON custom_forms USING GIN (table_metadata);

-- Add column comment
COMMENT ON COLUMN custom_forms.table_metadata IS
'Classification metadata for tables: data source types (visit_history, lab_results, scan_results, etc.),
field mappings to external data sources, and whether tables reference previous consultations.
Structure: {"tables": {"table_name": {"data_source_type": "...", "references_previous_consultation": true/false, "external_data_mappings": {...}, "confidence": 0.0-1.0}}}';

-- Verify migration
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'custom_forms'
AND column_name = 'table_metadata';
