-- Migration: Create enrichment tables for Phase 1d/1e/1f
-- Tables for tracking enrichment pipeline: fetch logs, compute logs, quality metrics, backfill state

-- Backfill state tracking (for resumable backfills)
CREATE TABLE IF NOT EXISTS backfill_state (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL,  -- 'stock', 'crypto', 'etf'
    timeframe VARCHAR(10) NOT NULL,
    backfill_job_id UUID NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    last_successful_date DATE,
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'failed'
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT backfill_state_unique UNIQUE(symbol, asset_class, timeframe, backfill_job_id)
);

CREATE INDEX IF NOT EXISTS idx_backfill_state_symbol_status 
    ON backfill_state(symbol, status);
CREATE INDEX IF NOT EXISTS idx_backfill_state_job 
    ON backfill_state(backfill_job_id);

-- Data source fetch log (audit trail for fetches)
CREATE TABLE IF NOT EXISTS enrichment_fetch_log (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10),
    source VARCHAR(20),  -- 'polygon', 'binance', 'yahoo'
    timeframe VARCHAR(10),
    records_fetched INT DEFAULT 0,
    records_inserted INT DEFAULT 0,
    records_updated INT DEFAULT 0,
    fetch_timestamp TIMESTAMPTZ,
    source_response_time_ms INT,
    success BOOLEAN DEFAULT TRUE,
    error_details TEXT,
    api_quota_remaining INT,
    job_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichment_fetch_symbol_time 
    ON enrichment_fetch_log(symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_enrichment_fetch_success 
    ON enrichment_fetch_log(success, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_enrichment_fetch_source 
    ON enrichment_fetch_log(source);

-- Feature computation log (debugging/monitoring)
CREATE TABLE IF NOT EXISTS enrichment_compute_log (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10),
    timeframe VARCHAR(10),
    computation_timestamp TIMESTAMPTZ,
    features_computed INT DEFAULT 0,
    missing_fields TEXT[],
    computation_time_ms INT,
    success BOOLEAN DEFAULT TRUE,
    error_details TEXT,
    job_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichment_compute_symbol_time 
    ON enrichment_compute_log(symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_enrichment_compute_success 
    ON enrichment_compute_log(success);

-- Data quality metrics (aggregated stats per symbol/day)
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10),
    metric_date DATE NOT NULL,
    total_records INT DEFAULT 0,
    validated_records INT DEFAULT 0,
    validation_rate DECIMAL(5, 2) DEFAULT 0.00,
    gaps_detected INT DEFAULT 0,
    anomalies_detected INT DEFAULT 0,
    avg_quality_score DECIMAL(3, 2) DEFAULT 0.00,
    data_completeness DECIMAL(3, 2) DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT data_quality_metrics_unique UNIQUE(symbol, asset_class, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_data_quality_symbol_date 
    ON data_quality_metrics(symbol, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_data_quality_validation_rate 
    ON data_quality_metrics(validation_rate);

-- Data corrections tracking (audit trail for data amendments)
CREATE TABLE IF NOT EXISTS data_corrections (
    id BIGSERIAL PRIMARY KEY,
    original_record_id BIGINT,
    symbol VARCHAR(20),
    timeframe VARCHAR(10),
    timestamp TIMESTAMPTZ,
    field_corrected VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason VARCHAR(200),  -- 'source_updated', 'bug_fix', 'manual_correction'
    corrected_by VARCHAR(100),
    correction_timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_corrections_symbol_time 
    ON data_corrections(symbol, correction_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_data_corrections_reason 
    ON data_corrections(reason);

-- Enrichment status per symbol (latest status)
CREATE TABLE IF NOT EXISTS enrichment_status (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10),
    status VARCHAR(20),  -- 'healthy', 'warning', 'stale', 'error'
    last_enrichment_time TIMESTAMPTZ,
    last_successful_enrichment TIMESTAMPTZ,
    data_age_seconds INT,
    records_available INT DEFAULT 0,
    quality_score DECIMAL(3, 2),
    validation_rate DECIMAL(5, 2),
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT enrichment_status_unique UNIQUE(symbol)
);

CREATE INDEX IF NOT EXISTS idx_enrichment_status_status 
    ON enrichment_status(status);
CREATE INDEX IF NOT EXISTS idx_enrichment_status_symbol 
    ON enrichment_status(symbol);
