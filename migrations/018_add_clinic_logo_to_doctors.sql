-- Add clinic_logo_url field to doctors table for storing logo images in GCS
-- Migration: 018_add_clinic_logo_to_doctors.sql
-- Description: Adds support for clinic logos that appear on PDF consultation reports

ALTER TABLE doctors
ADD COLUMN clinic_logo_url TEXT NULL;

COMMENT ON COLUMN doctors.clinic_logo_url IS
'Public URL to clinic logo image in GCS. Displayed on PDF consultation reports. Logo appears in top-right corner of generated PDFs.';

-- Create partial index for faster lookups when logo exists
CREATE INDEX idx_doctors_clinic_logo_url
ON doctors(clinic_logo_url)
WHERE clinic_logo_url IS NOT NULL;
