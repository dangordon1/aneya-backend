-- Migration: Add prescriptions JSONB column to consultations table
-- Date: 2025-12-30
-- Purpose: Store prescriptions extracted from consultation transcripts during LLM summarization

-- Add prescriptions JSONB column to consultations table
ALTER TABLE consultations
ADD COLUMN prescriptions JSONB DEFAULT NULL;

-- Add comment for documentation
COMMENT ON COLUMN consultations.prescriptions IS
'Array of prescriptions extracted from consultation transcript. Each prescription contains: drug_name, amount, method, frequency, duration. Example: [{"drug_name": "Paracetamol", "amount": "500mg", "method": "oral", "frequency": "three times daily", "duration": "7 days"}]';

-- Add GIN index for efficient JSONB queries
CREATE INDEX idx_consultations_prescriptions ON consultations USING GIN (prescriptions);
