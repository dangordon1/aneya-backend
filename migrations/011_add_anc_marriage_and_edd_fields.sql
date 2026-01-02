-- Migration: Add missing ANC form fields
-- Adds marriage/social history and additional EDD fields to antenatal_forms table

-- Add new EDD fields
ALTER TABLE antenatal_forms
  ADD COLUMN IF NOT EXISTS scan_edd DATE,
  ADD COLUMN IF NOT EXISTS clinical_edd DATE;

-- Add marriage and social history fields
ALTER TABLE antenatal_forms
  ADD COLUMN IF NOT EXISTS marriage_date DATE,
  ADD COLUMN IF NOT EXISTS cohabitation_period_months INTEGER,
  ADD COLUMN IF NOT EXISTS consanguinity TEXT CHECK (consanguinity IN ('consanguineous', 'non_consanguineous'));

-- Add column comments
COMMENT ON COLUMN antenatal_forms.scan_edd IS 'Expected Date of Delivery - determined by ultrasound scan';
COMMENT ON COLUMN antenatal_forms.clinical_edd IS 'Expected Date of Delivery - determined by clinical examination';
COMMENT ON COLUMN antenatal_forms.marriage_date IS 'Date of marriage';
COMMENT ON COLUMN antenatal_forms.cohabitation_period_months IS 'Period of cohabitation in months';
COMMENT ON COLUMN antenatal_forms.consanguinity IS 'Consanguineous marriage status (consanguineous/non-consanguineous) - important for genetic risk assessment';
