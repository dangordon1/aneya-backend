-- OTP Email Verification System
-- Created: 2026-01-13
-- Purpose: Replace Firebase email verification with custom OTP system

-- Create email_verifications table for OTP tracking
CREATE TABLE email_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL UNIQUE,  -- Firebase UID
    email TEXT NOT NULL,
    otp_hash TEXT NOT NULL,  -- bcrypt hash of OTP
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,  -- created_at + 10 minutes
    verified_at TIMESTAMPTZ,
    is_verified BOOLEAN NOT NULL DEFAULT false,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    locked_until TIMESTAMPTZ,  -- Temporary lock after too many failed attempts
    resend_count INTEGER NOT NULL DEFAULT 0,
    last_resent_at TIMESTAMPTZ
);

-- Indexes for performance
CREATE INDEX idx_email_verifications_user_id ON email_verifications(user_id);
CREATE INDEX idx_email_verifications_expires_at ON email_verifications(expires_at);
CREATE INDEX idx_email_verifications_verified ON email_verifications(is_verified, expires_at);
CREATE INDEX idx_email_verifications_email ON email_verifications(email);

-- RLS Policies
ALTER TABLE email_verifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own verification"
    ON email_verifications FOR SELECT
    TO authenticated
    USING (user_id = auth.uid()::text);

CREATE POLICY "Service role can manage all"
    ON email_verifications FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Add email_verified to user_roles table
ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS idx_user_roles_email_verified ON user_roles(user_id, email_verified);

-- Comments for documentation
COMMENT ON TABLE email_verifications IS 'OTP verification records for email verification during signup';
COMMENT ON COLUMN email_verifications.user_id IS 'Firebase UID of the user';
COMMENT ON COLUMN email_verifications.otp_hash IS 'Bcrypt hash of the 6-digit OTP';
COMMENT ON COLUMN email_verifications.expires_at IS 'Expiry timestamp (created_at + 10 minutes)';
COMMENT ON COLUMN email_verifications.locked_until IS 'Temporary lock timestamp after exceeding max_attempts';
COMMENT ON COLUMN email_verifications.attempts IS 'Number of failed verification attempts';
COMMENT ON COLUMN email_verifications.resend_count IS 'Number of times OTP has been resent';
COMMENT ON COLUMN email_verifications.last_resent_at IS 'Timestamp of last OTP resend';
