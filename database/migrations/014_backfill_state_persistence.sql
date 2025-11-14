-- Phase 4: Backfill State Persistence
-- Tracks concurrent backfill job states and prevents duplicate execution

CREATE TABLE IF NOT EXISTS backfill_state_persistent (
    id BIGSERIAL PRIMARY KEY,
    execution_id UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    asset_class VARCHAR(20) NOT NULL DEFAULT 'stock',
    timeframe VARCHAR(20) NOT NULL DEFAULT '1d',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, in_progress, completed, failed
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    records_inserted INTEGER DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    last_retry_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_backfill_state_symbol_status 
    ON backfill_state_persistent(symbol, status);

CREATE INDEX IF NOT EXISTS idx_backfill_state_execution 
    ON backfill_state_persistent(execution_id);

CREATE INDEX IF NOT EXISTS idx_backfill_state_created 
    ON backfill_state_persistent(created_at DESC);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_backfill_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS backfill_state_timestamp_trigger 
    ON backfill_state_persistent;

CREATE TRIGGER backfill_state_timestamp_trigger
BEFORE UPDATE ON backfill_state_persistent
FOR EACH ROW
EXECUTE FUNCTION update_backfill_state_timestamp();
