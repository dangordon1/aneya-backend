-- Migration: Add PDF Template Support to Custom Forms
-- Description: Store PDF layout configuration for custom forms
-- Created: 2025-01-03

-- ==============================================================================
-- ADD PDF_TEMPLATE COLUMN TO CUSTOM_FORMS
-- ==============================================================================

ALTER TABLE custom_forms
ADD COLUMN pdf_template JSONB;

-- ==============================================================================
-- CREATE INDEX
-- ==============================================================================

-- Add GIN index for efficient JSON queries on pdf_template
CREATE INDEX idx_custom_forms_pdf_template ON custom_forms USING GIN (pdf_template);

-- ==============================================================================
-- ADD COMMENTS
-- ==============================================================================

COMMENT ON COLUMN custom_forms.pdf_template IS 'JSONB PDF layout configuration (page_config, sections, styling)';

-- ==============================================================================
-- MIGRATION NOTES
-- ==============================================================================
-- This migration adds support for storing PDF templates alongside form schemas.
--
-- Key Features:
-- 1. pdf_template is nullable (backward compatibility with existing forms)
-- 2. Forms without pdf_template will use default layout generator
-- 3. PDF template structure includes:
--    - page_config: Page size, margins, header, footer configuration
--    - sections: Array of section layout configurations with field positioning
--    - styling: Color scheme, font sizes, and styling rules
--
-- Template Structure Example:
-- {
--   "page_config": {
--     "size": "A4",
--     "margins": {"top": 40, "bottom": 40, "left": 50, "right": 50},
--     "header": {"show_logo": true, "show_clinic_name": true},
--     "footer": {"show_page_numbers": true}
--   },
--   "sections": [
--     {
--       "id": "patient_demographics",
--       "title": "Patient Information",
--       "layout": "two_column",
--       "page_break_before": false,
--       "fields": [...]
--     }
--   ],
--   "styling": {
--     "primary_color": "#0c3555",
--     "section_header_size": 12
--   }
-- }
-- ==============================================================================
