-- Migration: Create Patient Demographics Table
-- Description: Separates demographics from patients table into proper health record table
-- Created: 2025-12-27
-- Purpose: Enable flexible health record management across specialties

-- ==============================================================================
-- CREATE PATIENT_DEMOGRAPHICS TABLE
-- ==============================================================================

CREATE TABLE IF NOT EXISTS patient_demographics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID NOT NULL UNIQUE REFERENCES patients(id) ON DELETE CASCADE,

  -- Core Demographics
  name TEXT NOT NULL,
  date_of_birth DATE NOT NULL,
  sex TEXT CHECK (sex IN ('male', 'female', 'other', 'unknown')),
  phone TEXT,
  email TEXT,
  address TEXT,
  emergency_contact_name TEXT,
  emergency_contact_phone TEXT,

  -- Metadata
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  created_by UUID REFERENCES auth.users(id),
  updated_by UUID REFERENCES auth.users(id)
);

-- Create indexes for common queries
CREATE INDEX idx_patient_demographics_patient_id ON patient_demographics(patient_id);
CREATE INDEX idx_patient_demographics_email ON patient_demographics(email);
CREATE INDEX idx_patient_demographics_phone ON patient_demographics(phone);

-- Add column comments for documentation
COMMENT ON TABLE patient_demographics IS 'Centralized patient demographic information, shared across all specialties';
COMMENT ON COLUMN patient_demographics.patient_id IS 'Foreign key to patients table (auth)';
COMMENT ON COLUMN patient_demographics.sex IS 'Biological sex for medical purposes';
COMMENT ON COLUMN patient_demographics.emergency_contact_name IS 'Primary emergency contact';
COMMENT ON COLUMN patient_demographics.emergency_contact_phone IS 'Emergency contact phone number';

-- ==============================================================================
-- MIGRATION NOTES
-- ==============================================================================
-- This table separates demographics from the auth-related `patients` table
-- It serves as the foundation for the multi-specialty forms system
-- Data from existing `patients` table can be migrated to this table as needed
-- ==============================================================================
