-- Add age_years field to patients table
-- This allows storing patient age when exact DOB is unknown

ALTER TABLE patients
ADD COLUMN IF NOT EXISTS age_years INTEGER NULL
CHECK (age_years > 0 AND age_years < 150);

COMMENT ON COLUMN patients.age_years IS
  'Patient age in years when exact DOB is unknown. Mutually exclusive with date_of_birth - at least one must be provided.';

-- Make date_of_birth nullable (was previously required)
ALTER TABLE patients
ALTER COLUMN date_of_birth DROP NOT NULL;

-- Ensure at least one age field is provided
ALTER TABLE patients
ADD CONSTRAINT patients_age_or_dob_required
CHECK (date_of_birth IS NOT NULL OR age_years IS NOT NULL);

-- Create index for age_years queries
CREATE INDEX IF NOT EXISTS idx_patients_age_years
ON patients(age_years)
WHERE age_years IS NOT NULL;
