-- Phase 1: Observability - Scheduler Monitoring Tables
-- Created: 2024-11-13
-- Purpose: Track scheduler execution, feature freshness, and computation failures

-- Table 1: Scheduler Execution Log
-- Tracks every backfill job run for audit trail and debugging
CREATE TABLE IF NOT EXISTS scheduler_execution_log (
    id BIGSERIAL PRIMARY KEY,
    execution_id UUID DEFAULT gen_random_uuid() UNIQUE,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    total_symbols INTEGER,
    successful_symbols INTEGER,
    failed_symbols INTEGER,
    total_records_processed INTEGER,
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_scheduler_execution_log_started_at 
    ON scheduler_execution_log(started_at DESC);
CREATE INDEX idx_scheduler_execution_log_status 
    ON scheduler_execution_log(status);

-- Table 2: Feature Computation Failures
-- Tracks which symbols/timeframes failed feature computation for alerting
CREATE TABLE IF NOT EXISTS feature_computation_failures (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    error_message TEXT NOT NULL,
    execution_id UUID REFERENCES scheduler_execution_log(execution_id),
    failed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    retry_count INTEGER DEFAULT 0,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_feature_computation_failures_symbol_timeframe 
    ON feature_computation_failures(symbol, timeframe);
CREATE INDEX idx_feature_computation_failures_failed_at 
    ON feature_computation_failures(failed_at DESC);
CREATE INDEX idx_feature_computation_failures_resolved 
    ON feature_computation_failures(resolved);

-- Table 3: Feature Freshness Cache
-- Tracks latest feature computation timestamp per symbol/timeframe for quick staleness checks
CREATE TABLE IF NOT EXISTS feature_freshness (
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    last_computed_at TIMESTAMP WITH TIME ZONE,
    data_point_count INTEGER,
    status VARCHAR(20) DEFAULT 'unknown' CHECK (status IN ('unknown', 'fresh', 'aging', 'stale', 'missing')),
    staleness_seconds INTEGER,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (symbol, timeframe)
);

CREATE INDEX idx_feature_freshness_status 
    ON feature_freshness(status);
CREATE INDEX idx_feature_freshness_staleness 
    ON feature_freshness(staleness_seconds DESC);

-- Table 4: Symbol Computation Status (per run)
-- Details of each symbol processed in a backfill execution
CREATE TABLE IF NOT EXISTS symbol_computation_status (
    id BIGSERIAL PRIMARY KEY,
    execution_id UUID NOT NULL REFERENCES scheduler_execution_log(execution_id),
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(20),
    timeframe VARCHAR(10),
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    records_processed INTEGER,
    records_inserted INTEGER,
    features_computed INTEGER,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER
);

CREATE INDEX idx_symbol_computation_status_execution_id 
    ON symbol_computation_status(execution_id);
CREATE INDEX idx_symbol_computation_status_symbol 
    ON symbol_computation_status(symbol);
CREATE INDEX idx_symbol_computation_status_status 
    ON symbol_computation_status(status);

-- Grants for observability (if needed for role-based access)
GRANT SELECT ON scheduler_execution_log TO postgres;
GRANT SELECT ON feature_computation_failures TO postgres;
GRANT SELECT ON feature_freshness TO postgres;
GRANT SELECT ON symbol_computation_status TO postgres;
