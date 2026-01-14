-- Add performance indexes for RLS helper function lookups
--
-- PURPOSE: Optimize the SECURITY DEFINER helper functions created in migration 034
--          to ensure fast RLS policy evaluation
--
-- These indexes support the following lookups:
-- 1. get_user_patient_id(user_id) -> patients.user_id lookup
-- 2. get_user_doctor_id(user_id) -> doctors.user_id lookup
-- 3. user_has_patient_relationship(patient_id, user_id) -> patient_doctor relationship lookup

-- ============================================================================
-- PATIENTS TABLE INDEXES
-- ============================================================================

-- Index for get_user_patient_id() function
-- Supports: SELECT id FROM patients WHERE user_id = p_user_id LIMIT 1
CREATE INDEX IF NOT EXISTS idx_patients_user_id_lookup
  ON patients(user_id)
  WHERE archived = false;

COMMENT ON INDEX idx_patients_user_id_lookup IS
'Optimizes get_user_patient_id() helper function lookups. Filters out archived patients for better performance.';

-- ============================================================================
-- DOCTORS TABLE INDEXES
-- ============================================================================

-- Index for get_user_doctor_id() function
-- Supports: SELECT id FROM doctors WHERE user_id = p_user_id LIMIT 1
CREATE INDEX IF NOT EXISTS idx_doctors_user_id_lookup
  ON doctors(user_id);

COMMENT ON INDEX idx_doctors_user_id_lookup IS
'Optimizes get_user_doctor_id() helper function lookups.';

-- ============================================================================
-- PATIENT_DOCTOR TABLE INDEXES
-- ============================================================================

-- Index for user_has_patient_relationship() function
-- Supports: Complex join query in the helper function
-- Note: We already have idx_patient_doctor_lookup from migration 016, but let's add a more specific one
CREATE INDEX IF NOT EXISTS idx_patient_doctor_relationship_lookup
  ON patient_doctor(patient_id, status)
  WHERE status = 'active';

COMMENT ON INDEX idx_patient_doctor_relationship_lookup IS
'Optimizes user_has_patient_relationship() helper function lookups. Partial index on active relationships only.';

-- Ensure doctor_id index exists for the join in user_has_patient_relationship()
CREATE INDEX IF NOT EXISTS idx_patient_doctor_doctor_id_active
  ON patient_doctor(doctor_id)
  WHERE status = 'active';

COMMENT ON INDEX idx_patient_doctor_doctor_id_active IS
'Optimizes the doctor_id join in user_has_patient_relationship() helper function.';

-- ============================================================================
-- ANALYZE TABLES
-- ============================================================================

-- Update table statistics to help query planner use these new indexes effectively
ANALYZE patients;
ANALYZE doctors;
ANALYZE patient_doctor;
