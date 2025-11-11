-- Main market data table
CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open DECIMAL(19,8) NOT NULL,
    high DECIMAL(19,8) NOT NULL,
    low DECIMAL(19,8) NOT NULL,
    close DECIMAL(19,8) NOT NULL,
    volume BIGINT NOT NULL,
    
    -- Source tracking
    source VARCHAR(20) DEFAULT 'polygon',
    
    -- Validation metadata
    validated BOOLEAN DEFAULT FALSE,
    quality_score NUMERIC(3,2) DEFAULT 0.00,
    validation_notes TEXT,
    gap_detected BOOLEAN DEFAULT FALSE,
    volume_anomaly BOOLEAN DEFAULT FALSE,
    
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(symbol, time)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_symbol_time ON market_data (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_validated ON market_data (validated) WHERE validated = TRUE;
CREATE INDEX IF NOT EXISTS idx_gap_detected ON market_data (gap_detected) WHERE gap_detected = TRUE;
CREATE INDEX IF NOT EXISTS idx_time_desc ON market_data (time DESC);

-- Validation audit log
CREATE TABLE IF NOT EXISTS validation_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    symbol VARCHAR(20),
    check_name VARCHAR(100),
    passed BOOLEAN,
    error_message TEXT,
    quality_score NUMERIC(3,2)
);

CREATE INDEX IF NOT EXISTS idx_validation_symbol_timestamp ON validation_log (symbol, timestamp DESC);

-- Import tracking (when backfill ran)
CREATE TABLE IF NOT EXISTS backfill_history (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    start_date DATE,
    end_date DATE,
    records_imported INT,
    backfill_timestamp TIMESTAMPTZ DEFAULT NOW(),
    success BOOLEAN,
    error_details TEXT
);

CREATE INDEX IF NOT EXISTS idx_backfill_symbol_timestamp ON backfill_history (symbol, backfill_timestamp DESC);

-- Monitoring: last successful backfill per symbol
CREATE TABLE IF NOT EXISTS symbol_status (
    symbol VARCHAR(20) PRIMARY KEY,
    last_backfill_date DATE,
    last_backfill_success BOOLEAN,
    last_validation_score NUMERIC(3,2),
    data_freshness_days INT,
    latest_date_in_db DATE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
