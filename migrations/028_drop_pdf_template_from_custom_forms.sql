-- Drop pdf_template column from custom_forms table
-- PDF rendering now derives layout from form_schema.
DROP INDEX IF EXISTS idx_custom_forms_pdf_template;
ALTER TABLE custom_forms DROP COLUMN IF EXISTS pdf_template;
