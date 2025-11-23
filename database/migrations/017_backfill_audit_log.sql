-- Backfill audit logging for tracking who triggered backfills and their results

CREATE TABLE IF NOT EXISTS backfill_audit_log (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL,
    event VARCHAR(50) NOT NULL, -- 'backfill_started', 'backfill_completed', 'backfill_failed', 'backfill_error'
    user_id VARCHAR(255), -- Optional user ID from API key or CLI
    details JSONB, -- Details about the backfill (symbols, timeframes, error messages, etc.)
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_backfill_audit_job_id ON backfill_audit_log(job_id);
CREATE INDEX IF NOT EXISTS idx_backfill_audit_created_at ON backfill_audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backfill_audit_event ON backfill_audit_log(event);
CREATE INDEX IF NOT EXISTS idx_backfill_audit_user_id ON backfill_audit_log(user_id);
