-- Migration: Add Abnormal Bleeding Pattern Fields to OB/GYN Forms
-- Description: Adds 4 boolean fields for tracking abnormal menstrual bleeding patterns
-- Created: 2025-12-27
-- Purpose: Enable comprehensive menstrual health tracking with specific bleeding abnormalities

-- ==============================================================================
-- ADD BLEEDING PATTERN COLUMNS TO OBGYN_FORMS TABLE
-- ==============================================================================

ALTER TABLE obgyn_forms
  ADD COLUMN IF NOT EXISTS premenstrual_spotting BOOLEAN,
  ADD COLUMN IF NOT EXISTS postmenstrual_spotting BOOLEAN,
  ADD COLUMN IF NOT EXISTS postcoital_bleeding BOOLEAN,
  ADD COLUMN IF NOT EXISTS intermenstrual_bleeding BOOLEAN;

-- Add column comments for clinical documentation
COMMENT ON COLUMN obgyn_forms.premenstrual_spotting IS 'Spotting before menstrual period begins - may indicate progesterone deficiency, polyps, or fibroids';
COMMENT ON COLUMN obgyn_forms.postmenstrual_spotting IS 'Spotting after menstrual period ends - may suggest retained products, infection, or structural abnormalities';
COMMENT ON COLUMN obgyn_forms.postcoital_bleeding IS 'Bleeding after sexual intercourse - important red flag that could indicate cervical pathology requiring investigation';
COMMENT ON COLUMN obgyn_forms.intermenstrual_bleeding IS 'Bleeding between menstrual periods - can indicate ovulation bleeding (physiologic) or pathologic causes';

-- ==============================================================================
-- CLINICAL SIGNIFICANCE
-- ==============================================================================
-- These fields help identify important menstrual abnormalities:
--
-- 1. Pre-menstrual spotting: Can indicate hormonal imbalances or structural issues
-- 2. Post-menstrual spotting: May suggest endometrial or cervical pathology
-- 3. Post-coital bleeding: Red flag requiring investigation for cervical disease
-- 4. Inter-menstrual bleeding: Helps differentiate ovulatory from pathologic bleeding
--
-- All fields are nullable (NULL = not asked/not applicable, FALSE = explicitly absent)
-- ==============================================================================
