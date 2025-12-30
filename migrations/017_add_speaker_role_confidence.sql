-- Migration: Add speaker role confidence scores to consultations
-- Purpose: Track LLM confidence for speaker role assignments and support multi-speaker consultations
-- Date: 2025-12-30

-- Add columns for speaker role tracking
ALTER TABLE public.consultations
ADD COLUMN IF NOT EXISTS speaker_role_mapping JSONB,
ADD COLUMN IF NOT EXISTS speaker_confidence_scores JSONB,
ADD COLUMN IF NOT EXISTS speaker_identification_method TEXT
CHECK (speaker_identification_method IN ('llm', 'manual', 'heuristic', 'fallback'));

-- Index for querying low-confidence consultations
CREATE INDEX IF NOT EXISTS idx_consultations_low_confidence_speakers
ON public.consultations USING GIN (speaker_confidence_scores)
WHERE speaker_identification_method = 'llm';

-- Comments for documentation
COMMENT ON COLUMN public.consultations.speaker_role_mapping IS
'JSON mapping of speaker IDs to roles: {"speaker_0": "Doctor", "speaker_1": "Patient", "speaker_2": "Nurse"}';

COMMENT ON COLUMN public.consultations.speaker_confidence_scores IS
'JSON mapping of speaker IDs to confidence scores: {"speaker_0": 0.95, "speaker_1": 0.88, "speaker_2": 0.65}';

COMMENT ON COLUMN public.consultations.speaker_identification_method IS
'Method used to identify speakers: llm (AI-identified), manual (user-confirmed), heuristic (rule-based), fallback (error recovery)';
