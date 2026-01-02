-- Migration: Add Normal Bleeding Pattern Fields to OB/GYN Forms
-- Description: Adds 4 boolean fields for tracking normal bleeding patterns (complementing abnormal patterns from migration 003)
-- Created: 2025-12-27
-- Purpose: Enable comprehensive menstrual bleeding pattern tracking with both normal and abnormal characteristics

-- ==============================================================================
-- ADD NORMAL BLEEDING PATTERN COLUMNS TO OBGYN_FORMS TABLE
-- ==============================================================================

ALTER TABLE obgyn_forms
  ADD COLUMN IF NOT EXISTS normal_menstrual_flow BOOLEAN,
  ADD COLUMN IF NOT EXISTS heavy_menstrual_bleeding BOOLEAN,
  ADD COLUMN IF NOT EXISTS light_menstrual_bleeding BOOLEAN,
  ADD COLUMN IF NOT EXISTS menstrual_clotting BOOLEAN;

-- Add column comments for clinical documentation
COMMENT ON COLUMN obgyn_forms.normal_menstrual_flow IS 'Regular, normal menstrual flow pattern';
COMMENT ON COLUMN obgyn_forms.heavy_menstrual_bleeding IS 'Menorrhagia - heavy or prolonged menstrual bleeding';
COMMENT ON COLUMN obgyn_forms.light_menstrual_bleeding IS 'Hypomenorrhea - unusually light menstrual flow';
COMMENT ON COLUMN obgyn_forms.menstrual_clotting IS 'Presence of blood clots during menstruation';

-- ==============================================================================
-- CLINICAL SIGNIFICANCE
-- ==============================================================================
-- These fields work together with the abnormal bleeding fields from migration 003 to provide
-- a comprehensive bleeding pattern assessment:
--
-- Normal Patterns:
-- 1. Normal flow: Baseline for comparison
-- 2. Heavy bleeding: May indicate fibroids, adenomyosis, bleeding disorders
-- 3. Light bleeding: Can suggest hormonal imbalances, Asherman's syndrome
-- 4. Clotting: Important for assessing bleeding severity and potential pathology
--
-- When combined with abnormal patterns (pre/post-menstrual spotting, post-coital bleeding,
-- inter-menstrual bleeding), provides complete picture for clinical decision-making
--
-- All fields are nullable (NULL = not asked/not applicable, FALSE = explicitly absent)
-- ==============================================================================
