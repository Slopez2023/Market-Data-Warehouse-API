-- Market Data V2 Schema
-- Enriched OHLCV with computed features and crypto-specific data
-- Version: 1.0
-- Date: 2024-11-13

-- Master enriched data table
CREATE TABLE IF NOT EXISTS market_data_v2 (
    -- Primary Keys & Identification
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL, -- 'stock', 'crypto', 'etf'
    timeframe VARCHAR(10) NOT NULL,   -- '5m', '15m', '30m', '1h', '4h', '1d', '1w'
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- RAW OHLCV Data (from all sources)
    open DECIMAL(19, 10),
    high DECIMAL(19, 10),
    low DECIMAL(19, 10),
    close DECIMAL(19, 10),
    volume BIGINT,
    
    -- Crypto-specific raw data (Binance)
    open_interest DECIMAL(19, 8),           -- Only for crypto
    funding_rate DECIMAL(11, 8),            -- Only for crypto
    liquidations_long DECIMAL(19, 8),       -- Only for crypto
    liquidations_short DECIMAL(19, 8),      -- Only for crypto
    taker_buy_volume DECIMAL(19, 8),        -- Only for crypto
    taker_sell_volume DECIMAL(19, 8),       -- Only for crypto
    
    -- UNIVERSAL COMPUTED FEATURES (all assets)
    return_1h DECIMAL(11, 8),
    return_1d DECIMAL(11, 8),
    volatility_20 DECIMAL(11, 8),
    volatility_50 DECIMAL(11, 8),
    atr DECIMAL(19, 10),
    trend_direction VARCHAR(10),            -- 'up', 'down', 'neutral'
    market_structure VARCHAR(20),           -- 'bullish', 'bearish', 'range'
    rolling_volume_20 BIGINT,
    
    -- CRYPTO-SPECIFIC COMPUTED FEATURES
    delta DECIMAL(11, 8),                   -- Long - Short volume
    buy_sell_ratio DECIMAL(11, 8),
    liquidation_intensity DECIMAL(11, 8),
    volume_spike_score DECIMAL(11, 8),
    long_short_ratio DECIMAL(11, 8),
    funding_rate_percentile DECIMAL(5, 2),
    exchange_inflow DECIMAL(19, 8),
    open_interest_change DECIMAL(11, 8),
    
    -- Data Quality & Source Tracking
    source VARCHAR(20),                     -- 'polygon', 'binance', 'yahoo'
    is_validated BOOLEAN DEFAULT FALSE,
    quality_score DECIMAL(3, 2),
    validation_notes TEXT,
    gap_detected BOOLEAN DEFAULT FALSE,
    volume_anomaly BOOLEAN DEFAULT FALSE,
    data_completeness DECIMAL(3, 2),        -- % of expected fields present
    
    -- Data Integrity & Versioning
    revision INT DEFAULT 1,
    amended_from BIGINT,
    
    -- Metadata
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint to prevent duplicates
    UNIQUE(symbol, asset_class, timeframe, timestamp, revision)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_market_data_v2_symbol_asset_timeframe_time 
    ON market_data_v2(symbol, asset_class, timeframe, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_v2_timestamp_desc 
    ON market_data_v2(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_v2_validated 
    ON market_data_v2(is_validated) WHERE is_validated = TRUE;
CREATE INDEX IF NOT EXISTS idx_market_data_v2_source 
    ON market_data_v2(source);
CREATE INDEX IF NOT EXISTS idx_market_data_v2_symbol_timestamp 
    ON market_data_v2(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_v2_asset_class 
    ON market_data_v2(asset_class);

-- Backfill state tracking table
CREATE TABLE IF NOT EXISTS backfill_state (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    backfill_job_id UUID NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    last_successful_date DATE,
    status VARCHAR(20) NOT NULL,  -- 'pending', 'in_progress', 'completed', 'failed'
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, asset_class, timeframe, backfill_job_id)
);

CREATE INDEX IF NOT EXISTS idx_backfill_state_status 
    ON backfill_state(status);
CREATE INDEX IF NOT EXISTS idx_backfill_state_symbol 
    ON backfill_state(symbol, status);

-- Data corrections and amendment log
CREATE TABLE IF NOT EXISTS data_corrections (
    id BIGSERIAL PRIMARY KEY,
    original_record_id BIGINT NOT NULL,
    field_corrected VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason VARCHAR(200),  -- 'source_updated', 'bug_fix', 'manual_correction'
    corrected_by VARCHAR(100),
    correction_timestamp TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (original_record_id) REFERENCES market_data_v2(id)
);

CREATE INDEX IF NOT EXISTS idx_data_corrections_record_id 
    ON data_corrections(original_record_id);
CREATE INDEX IF NOT EXISTS idx_data_corrections_timestamp 
    ON data_corrections(correction_timestamp DESC);

-- Data source API call log
CREATE TABLE IF NOT EXISTS enrichment_fetch_log (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    asset_class VARCHAR(10),
    source VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10),
    records_fetched INT,
    records_inserted INT,
    records_updated INT,
    fetch_timestamp TIMESTAMPTZ NOT NULL,
    source_response_time_ms INT,
    success BOOLEAN DEFAULT FALSE,
    error_details TEXT,
    api_quota_remaining INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichment_fetch_log_symbol_time 
    ON enrichment_fetch_log(symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_enrichment_fetch_log_source 
    ON enrichment_fetch_log(source, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_enrichment_fetch_log_success 
    ON enrichment_fetch_log(success) WHERE success = FALSE;

-- Feature computation log
CREATE TABLE IF NOT EXISTS enrichment_compute_log (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    asset_class VARCHAR(10),
    timeframe VARCHAR(10),
    computation_timestamp TIMESTAMPTZ NOT NULL,
    features_computed INT,
    missing_fields TEXT[],
    computation_time_ms INT,
    success BOOLEAN DEFAULT FALSE,
    error_details TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichment_compute_log_symbol_time 
    ON enrichment_compute_log(symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_enrichment_compute_log_success 
    ON enrichment_compute_log(success) WHERE success = FALSE;

-- Data quality metrics aggregation
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    asset_class VARCHAR(10),
    metric_date DATE NOT NULL,
    total_records INT,
    validated_records INT,
    validation_rate DECIMAL(5, 2),
    gaps_detected INT,
    anomalies_detected INT,
    avg_quality_score DECIMAL(3, 2),
    data_completeness DECIMAL(3, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, asset_class, metric_date)
);

CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_symbol_date 
    ON data_quality_metrics(symbol, metric_date DESC);
CREATE INDEX IF NOT EXISTS idx_data_quality_metrics_date 
    ON data_quality_metrics(metric_date DESC);

-- Enrichment status tracking
CREATE TABLE IF NOT EXISTS enrichment_status (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL,
    last_enriched_at TIMESTAMPTZ,
    data_freshness_seconds INT,
    is_stale BOOLEAN DEFAULT FALSE,
    last_error TEXT,
    consecutive_failures INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, asset_class)
);

CREATE INDEX IF NOT EXISTS idx_enrichment_status_symbol 
    ON enrichment_status(symbol);
CREATE INDEX IF NOT EXISTS idx_enrichment_status_stale 
    ON enrichment_status(is_stale) WHERE is_stale = TRUE;
