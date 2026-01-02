-- Migration: Standardize Doctor Specialty
-- Date: 2025-12-27
-- Description: Creates enum type for medical specialties and migrates existing free-text data

-- Step 1: Create the medical specialty enum type
CREATE TYPE medical_specialty_type AS ENUM (
  'general',
  'obgyn',
  'cardiology',
  'neurology',
  'dermatology',
  'other'
);

-- Step 2: Migrate existing data to standardized values
-- Note: We'll first update the text values to match enum values

-- Map OB/GYN variations to 'obgyn'
UPDATE doctors
SET specialty = 'obgyn'
WHERE LOWER(specialty) SIMILAR TO '%(ob|gyn|obstetric|gynaec|gynec)%';

-- Map cardiology variations to 'cardiology'
UPDATE doctors
SET specialty = 'cardiology'
WHERE LOWER(specialty) LIKE '%cardio%';

-- Map neurology variations to 'neurology'
UPDATE doctors
SET specialty = 'neurology'
WHERE LOWER(specialty) LIKE '%neuro%';

-- Map dermatology variations to 'dermatology'
UPDATE doctors
SET specialty = 'dermatology'
WHERE LOWER(specialty) LIKE '%dermat%';

-- Map general practice variations to 'general'
UPDATE doctors
SET specialty = 'general'
WHERE LOWER(specialty) SIMILAR TO '%(general|family|primary)%';

-- Default NULL or empty to 'general'
UPDATE doctors
SET specialty = 'general'
WHERE specialty IS NULL OR TRIM(specialty) = '';

-- Map any remaining unmapped values to 'other'
UPDATE doctors
SET specialty = 'other'
WHERE specialty NOT IN ('general', 'obgyn', 'cardiology', 'neurology', 'dermatology');

-- Step 3: Alter column to use the enum type
ALTER TABLE doctors
ALTER COLUMN specialty TYPE medical_specialty_type
USING specialty::medical_specialty_type;

-- Step 4: Set default and NOT NULL constraint
ALTER TABLE doctors
ALTER COLUMN specialty SET DEFAULT 'general';

ALTER TABLE doctors
ALTER COLUMN specialty SET NOT NULL;

-- Step 5: Add comment for documentation
COMMENT ON COLUMN doctors.specialty IS 'Medical specialty of the doctor. Determines which specialty-specific forms are available to patients.';
COMMENT ON TYPE medical_specialty_type IS 'Enum type for standardized medical specialties';
