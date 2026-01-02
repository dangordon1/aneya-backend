-- AI Feedback Collection System for RLHF
-- Migration 013: Create ai_feedback table and related infrastructure
-- Created: 2025-12-29
--
-- Purpose: Capture user feedback on AI-generated content (transcription, summary,
-- diagnosis, drug recommendations) to enable Reinforcement Learning from Human Feedback

-- Create ENUM types for feedback classification
CREATE TYPE feedback_type AS ENUM (
    'transcription',
    'summary',
    'diagnosis',
    'drug_recommendation'
);

CREATE TYPE feedback_sentiment AS ENUM (
    'positive',    -- thumbs up
    'negative'     -- thumbs down
);

-- Main feedback table
CREATE TABLE IF NOT EXISTS ai_feedback (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Consultation reference (required)
    consultation_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,

    -- Feedback metadata (required)
    feedback_type feedback_type NOT NULL,
    feedback_sentiment feedback_sentiment NOT NULL,

    -- Component-specific identifiers
    component_identifier TEXT,  -- e.g., 'diagnosis_0', 'diagnosis_1', 'drug_paracetamol', 'soap_summary'
    component_data JSONB,       -- Stores snapshot of the actual content that was rated (for audit trail)

    -- Diagnosis-specific fields (required when feedback_type='diagnosis')
    diagnosis_text TEXT,        -- The actual diagnosis text that was shown
    is_correct_diagnosis BOOLEAN DEFAULT FALSE,  -- TRUE if user marked this as the correct diagnosis

    -- Drug-specific fields (required when feedback_type='drug_recommendation')
    drug_name TEXT,             -- e.g., 'Paracetamol', 'Amoxicillin'
    drug_dosage TEXT,           -- Dosage information that was displayed

    -- User context (nullable to support anonymous feedback)
    user_id TEXT,               -- Firebase UID (nullable for anonymous feedback)
    user_role TEXT,             -- 'doctor', 'patient', 'admin', 'anonymous'

    -- Additional context
    notes TEXT,                 -- Optional user comment (max 500 chars recommended in UI)
    metadata JSONB DEFAULT '{}',-- Flexible field for future extensions

    -- Deduplication support
    fingerprint TEXT,           -- MD5 hash to prevent duplicate submissions

    -- Unique constraint on fingerprint
    CONSTRAINT unique_feedback_fingerprint UNIQUE(fingerprint)
);

-- Indexes for common query patterns
CREATE INDEX idx_ai_feedback_consultation_id ON ai_feedback(consultation_id);
CREATE INDEX idx_ai_feedback_type ON ai_feedback(feedback_type);
CREATE INDEX idx_ai_feedback_sentiment ON ai_feedback(feedback_sentiment);
CREATE INDEX idx_ai_feedback_created_at ON ai_feedback(created_at DESC);

-- Partial indexes for type-specific queries (more efficient)
CREATE INDEX idx_ai_feedback_diagnosis_text ON ai_feedback(diagnosis_text)
    WHERE feedback_type = 'diagnosis';
CREATE INDEX idx_ai_feedback_drug_name ON ai_feedback(drug_name)
    WHERE feedback_type = 'drug_recommendation';
CREATE INDEX idx_ai_feedback_correct_diagnosis ON ai_feedback(is_correct_diagnosis)
    WHERE is_correct_diagnosis = TRUE;

-- Composite indexes for analytics queries
CREATE INDEX idx_ai_feedback_analytics ON ai_feedback(feedback_type, feedback_sentiment, created_at DESC);
CREATE INDEX idx_ai_feedback_user_role ON ai_feedback(user_role, feedback_type, feedback_sentiment);

-- Trigger function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_ai_feedback_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function before each UPDATE
CREATE TRIGGER trigger_update_ai_feedback_updated_at
    BEFORE UPDATE ON ai_feedback
    FOR EACH ROW
    EXECUTE FUNCTION update_ai_feedback_updated_at();

-- Materialized view for fast analytics queries
-- Refresh this periodically (e.g., hourly via cron) for dashboard performance
CREATE MATERIALIZED VIEW ai_feedback_aggregates AS
SELECT
    feedback_type,
    feedback_sentiment,
    DATE_TRUNC('day', created_at) AS feedback_date,
    COUNT(*) AS feedback_count,
    COUNT(DISTINCT consultation_id) AS unique_consultations,
    COUNT(DISTINCT user_id) AS unique_users,

    -- Diagnosis-specific aggregates
    CASE WHEN feedback_type = 'diagnosis' THEN diagnosis_text END AS diagnosis,
    COUNT(*) FILTER (WHERE is_correct_diagnosis = TRUE) AS marked_correct_count,

    -- Drug-specific aggregates
    CASE WHEN feedback_type = 'drug_recommendation' THEN drug_name END AS drug,

    -- Calculate positive feedback percentage
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE feedback_sentiment = 'positive') /
        NULLIF(COUNT(*), 0),
        2
    ) AS positive_percentage,

    MIN(created_at) AS first_feedback_at,
    MAX(created_at) AS last_feedback_at
FROM ai_feedback
GROUP BY
    feedback_type,
    feedback_sentiment,
    DATE_TRUNC('day', created_at),
    CASE WHEN feedback_type = 'diagnosis' THEN diagnosis_text END,
    CASE WHEN feedback_type = 'drug_recommendation' THEN drug_name END;

-- Index on materialized view for fast queries
CREATE INDEX idx_feedback_aggregates_date ON ai_feedback_aggregates(feedback_date DESC);
CREATE INDEX idx_feedback_aggregates_type ON ai_feedback_aggregates(feedback_type, feedback_sentiment);

-- Function to refresh materialized view (can be called via cron or manually)
CREATE OR REPLACE FUNCTION refresh_ai_feedback_aggregates()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY ai_feedback_aggregates;
END;
$$ LANGUAGE plpgsql;

-- Enable Row Level Security (RLS)
ALTER TABLE ai_feedback ENABLE ROW LEVEL SECURITY;

-- RLS Policy 1: Anyone can submit feedback (authenticated or anonymous)
-- This allows both logged-in users and anonymous visitors to provide feedback
CREATE POLICY "Anyone can submit feedback"
ON ai_feedback
FOR INSERT
TO public
WITH CHECK (true);

-- RLS Policy 2: Users can view their own feedback
-- Authenticated users can see feedback they submitted
-- Anonymous feedback (user_id IS NULL) is viewable by everyone
CREATE POLICY "Users can view own feedback"
ON ai_feedback
FOR SELECT
TO public
USING (
    user_id = current_setting('request.jwt.claims', true)::json->>'sub'
    OR user_id IS NULL  -- Allow viewing anonymous feedback
);

-- RLS Policy 3: Doctors can view all feedback for their consultations
-- Allows doctors to see feedback on consultations they performed
CREATE POLICY "Doctors can view feedback for their consultations"
ON ai_feedback
FOR SELECT
TO public
USING (
    EXISTS (
        SELECT 1 FROM consultations c
        WHERE c.id = ai_feedback.consultation_id
        AND c.performed_by = current_setting('request.jwt.claims', true)::json->>'sub'
    )
);

-- RLS Policy 4: Admins can view all feedback
-- Superadmins and admins have full read access for monitoring and analysis
CREATE POLICY "Admins can view all feedback"
ON ai_feedback
FOR SELECT
TO public
USING (
    EXISTS (
        SELECT 1 FROM user_roles
        WHERE user_id = current_setting('request.jwt.claims', true)::json->>'sub'
        AND role IN ('admin', 'superadmin')
    )
);

-- RLS Policy 5: Users can update their own feedback (no time restriction)
-- Allows users to change their mind about feedback at any time
CREATE POLICY "Users can update own feedback"
ON ai_feedback
FOR UPDATE
TO public
USING (
    user_id = current_setting('request.jwt.claims', true)::json->>'sub'
)
WITH CHECK (
    user_id = current_setting('request.jwt.claims', true)::json->>'sub'
);

-- Comments for documentation
COMMENT ON TABLE ai_feedback IS 'Captures user feedback on AI-generated content for RLHF analysis and continuous improvement';
COMMENT ON COLUMN ai_feedback.fingerprint IS 'MD5 hash of (consultation_id, feedback_type, component_identifier, user_id) to prevent duplicate submissions';
COMMENT ON COLUMN ai_feedback.component_data IS 'Stores snapshot of the actual content shown to user at time of feedback (for audit trail)';
COMMENT ON COLUMN ai_feedback.is_correct_diagnosis IS 'For diagnosis feedback only: marks which diagnosis(es) the clinician identified as correct. Multiple diagnoses can be marked correct for co-morbidities.';
COMMENT ON COLUMN ai_feedback.metadata IS 'Flexible JSONB field for future extensions (e.g., click tracking, time spent viewing, confidence levels)';
COMMENT ON MATERIALIZED VIEW ai_feedback_aggregates IS 'Pre-computed analytics for RLHF dashboard - refresh hourly for performance';
COMMENT ON POLICY "Anyone can submit feedback" ON ai_feedback IS 'Allows both authenticated and anonymous users to provide feedback';
COMMENT ON POLICY "Users can update own feedback" ON ai_feedback IS 'Allows users to change their feedback at any time (no time restriction)';
