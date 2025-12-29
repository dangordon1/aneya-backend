-- Migration: Add transcription status tracking to consultations table
-- Purpose: Enable async diarisation processing with status tracking
-- Date: 2025-12-29

-- Add transcription status tracking fields
ALTER TABLE public.consultations
ADD COLUMN transcription_status TEXT DEFAULT 'completed'
CHECK (transcription_status IN ('pending', 'processing', 'completed', 'failed'));

ALTER TABLE public.consultations
ADD COLUMN transcription_error TEXT;

ALTER TABLE public.consultations
ADD COLUMN transcription_started_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE public.consultations
ADD COLUMN transcription_completed_at TIMESTAMP WITH TIME ZONE;

-- Create index for efficient realtime queries on pending/processing status
CREATE INDEX idx_consultations_transcription_status
ON public.consultations(transcription_status)
WHERE transcription_status IN ('pending', 'processing');

-- Backfill existing consultations as 'completed' (already processed)
UPDATE public.consultations
SET transcription_status = 'completed'
WHERE transcription_status IS NULL;

-- Make status NOT NULL after backfill
ALTER TABLE public.consultations
ALTER COLUMN transcription_status SET NOT NULL;

-- Add comment for documentation
COMMENT ON COLUMN public.consultations.transcription_status IS
'Status of speaker diarisation processing: pending (queued), processing (in progress), completed (done), failed (error occurred)';

COMMENT ON COLUMN public.consultations.transcription_error IS
'Error message if transcription_status is failed';

COMMENT ON COLUMN public.consultations.transcription_started_at IS
'Timestamp when async diarisation processing started';

COMMENT ON COLUMN public.consultations.transcription_completed_at IS
'Timestamp when async diarisation processing completed (success or failure)';
