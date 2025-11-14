-- Phase 4: Data Quality Monitoring
-- Tracks data anomalies and health metrics

CREATE TABLE IF NOT EXISTS data_anomalies (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    timeframe VARCHAR(20) NOT NULL DEFAULT '1d',
    anomaly_type VARCHAR(100) NOT NULL,  -- gap, duplicate, outlier, stale, etc.
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',  -- low, medium, high, critical
    description TEXT,
    data_point_time TIMESTAMP WITH TIME ZONE,
    affected_rows INTEGER,
    resolution_status VARCHAR(50) DEFAULT 'open',  -- open, acknowledged, resolved
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_anomalies_symbol_time 
    ON data_anomalies(symbol, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_anomalies_severity 
    ON data_anomalies(severity, resolution_status);

CREATE TABLE IF NOT EXISTS duplicate_records_log (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL,
    timeframe VARCHAR(20) NOT NULL DEFAULT '1d',
    candle_time TIMESTAMP WITH TIME ZONE NOT NULL,
    duplicate_count INTEGER NOT NULL,
    cleaned_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    duplicate_ids BIGINT[],  -- IDs of duplicate records removed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_duplicates_symbol_time 
    ON duplicate_records_log(symbol, candle_time);

CREATE INDEX IF NOT EXISTS idx_duplicates_cleaned 
    ON duplicate_records_log(cleaned_at DESC);

-- Consecutive failure tracking
CREATE TABLE IF NOT EXISTS symbol_failure_tracking (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(50) NOT NULL UNIQUE,
    consecutive_failures INTEGER DEFAULT 0,
    last_failure_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    alert_sent BOOLEAN DEFAULT FALSE,
    alert_sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient queries
CREATE INDEX IF NOT EXISTS idx_failure_tracking_failures 
    ON symbol_failure_tracking(consecutive_failures DESC);

CREATE INDEX IF NOT EXISTS idx_failure_tracking_alert 
    ON symbol_failure_tracking(alert_sent, consecutive_failures);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_failure_tracking_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS failure_tracking_timestamp_trigger 
    ON symbol_failure_tracking;

CREATE TRIGGER failure_tracking_timestamp_trigger
BEFORE UPDATE ON symbol_failure_tracking
FOR EACH ROW
EXECUTE FUNCTION update_failure_tracking_timestamp();
