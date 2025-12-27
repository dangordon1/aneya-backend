-- Migration: Create OB/GYN Forms Table
-- Description: Creates the obgyn_forms table for storing patient OB/GYN intake forms
-- Created: 2025-12-21

-- Create the obgyn_forms table
CREATE TABLE IF NOT EXISTS obgyn_forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    form_data JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'completed', 'reviewed', 'submitted')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_obgyn_forms_patient_id ON obgyn_forms(patient_id);
CREATE INDEX IF NOT EXISTS idx_obgyn_forms_appointment_id ON obgyn_forms(appointment_id);
CREATE INDEX IF NOT EXISTS idx_obgyn_forms_created_at ON obgyn_forms(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_obgyn_forms_status ON obgyn_forms(status);

-- Create a trigger to automatically update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_obgyn_forms_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_obgyn_forms_updated_at ON obgyn_forms;
CREATE TRIGGER trigger_obgyn_forms_updated_at
BEFORE UPDATE ON obgyn_forms
FOR EACH ROW
EXECUTE FUNCTION update_obgyn_forms_updated_at();

-- Enable Row-Level Security (RLS)
ALTER TABLE obgyn_forms ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
-- Allow users to view only their own forms (through patient relationship)
CREATE POLICY "Users can view own forms"
    ON obgyn_forms FOR SELECT
    USING (
        auth.uid() = (SELECT user_id FROM patients WHERE id = patient_id)
    );

-- Allow users to insert forms for their own patients
CREATE POLICY "Users can insert own forms"
    ON obgyn_forms FOR INSERT
    WITH CHECK (
        auth.uid() = (SELECT user_id FROM patients WHERE id = patient_id)
    );

-- Allow users to update own forms
CREATE POLICY "Users can update own forms"
    ON obgyn_forms FOR UPDATE
    USING (
        auth.uid() = (SELECT user_id FROM patients WHERE id = patient_id)
    )
    WITH CHECK (
        auth.uid() = (SELECT user_id FROM patients WHERE id = patient_id)
    );

-- Allow users to delete own forms
CREATE POLICY "Users can delete own forms"
    ON obgyn_forms FOR DELETE
    USING (
        auth.uid() = (SELECT user_id FROM patients WHERE id = patient_id)
    );

-- Policy for service role (backend operations)
CREATE POLICY "Service role can manage all forms"
    ON obgyn_forms
    USING (current_user = 'service_role')
    WITH CHECK (current_user = 'service_role');

-- Add comments for documentation
COMMENT ON TABLE obgyn_forms IS 'Stores OB/GYN patient intake forms';
COMMENT ON COLUMN obgyn_forms.id IS 'Unique form identifier';
COMMENT ON COLUMN obgyn_forms.patient_id IS 'Reference to patient';
COMMENT ON COLUMN obgyn_forms.appointment_id IS 'Optional reference to appointment';
COMMENT ON COLUMN obgyn_forms.form_data IS 'JSON form data with patient_demographics, obstetric_history, gynecologic_history sections';
COMMENT ON COLUMN obgyn_forms.status IS 'Form status: draft, completed, reviewed, submitted';
COMMENT ON COLUMN obgyn_forms.created_at IS 'Form creation timestamp';
COMMENT ON COLUMN obgyn_forms.updated_at IS 'Last update timestamp';
