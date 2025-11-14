-- Quant Feature Engine Extension
-- Adds AI-ready price-based features to market_data table
-- Version: 1.0
-- Date: 2024-11-13

-- Add quant feature columns to market_data table
ALTER TABLE market_data
ADD COLUMN IF NOT EXISTS return_1d DECIMAL(11, 8),
ADD COLUMN IF NOT EXISTS volatility_20 DECIMAL(11, 8),
ADD COLUMN IF NOT EXISTS volatility_50 DECIMAL(11, 8),
ADD COLUMN IF NOT EXISTS atr DECIMAL(19, 10),
ADD COLUMN IF NOT EXISTS rolling_volume_20 BIGINT,
ADD COLUMN IF NOT EXISTS volume_ratio DECIMAL(11, 8),
ADD COLUMN IF NOT EXISTS structure_label VARCHAR(20),
ADD COLUMN IF NOT EXISTS trend_direction VARCHAR(10),
ADD COLUMN IF NOT EXISTS volatility_regime VARCHAR(10),
ADD COLUMN IF NOT EXISTS trend_regime VARCHAR(15),
ADD COLUMN IF NOT EXISTS compression_regime VARCHAR(15),
ADD COLUMN IF NOT EXISTS features_computed_at TIMESTAMPTZ;

-- Create indexes for efficient quant feature queries
CREATE INDEX IF NOT EXISTS idx_market_data_quant_features_symbol_time
    ON market_data(symbol, timeframe, time DESC)
    WHERE features_computed_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_market_data_structure_label
    ON market_data(structure_label)
    WHERE structure_label IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_market_data_volatility_regime
    ON market_data(volatility_regime)
    WHERE volatility_regime IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_market_data_trend_regime
    ON market_data(trend_regime)
    WHERE trend_regime IS NOT NULL;

-- Create feature computation log table
CREATE TABLE IF NOT EXISTS quant_feature_log (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    records_processed INT,
    features_computed INT,
    computation_time_ms INT,
    success BOOLEAN DEFAULT FALSE,
    error_details TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for quant feature log
CREATE INDEX IF NOT EXISTS idx_quant_feature_log_symbol_time
    ON quant_feature_log(symbol, timeframe, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_quant_feature_log_success
    ON quant_feature_log(success)
    WHERE success = FALSE;

-- Create summary table for latest quant features per symbol/timeframe
CREATE TABLE IF NOT EXISTS quant_feature_summary (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    latest_timestamp TIMESTAMPTZ NOT NULL,
    
    -- Latest numeric features
    return_1d DECIMAL(11, 8),
    volatility_20 DECIMAL(11, 8),
    volatility_50 DECIMAL(11, 8),
    atr DECIMAL(19, 10),
    rolling_volume_20 BIGINT,
    volume_ratio DECIMAL(11, 8),
    
    -- Latest categorical features
    structure_label VARCHAR(20),
    trend_direction VARCHAR(10),
    volatility_regime VARCHAR(10),
    trend_regime VARCHAR(15),
    compression_regime VARCHAR(15),
    
    -- Metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(symbol, timeframe)
);

-- Indexes for feature summary
CREATE INDEX IF NOT EXISTS idx_quant_feature_summary_symbol
    ON quant_feature_summary(symbol);

CREATE INDEX IF NOT EXISTS idx_quant_feature_summary_updated
    ON quant_feature_summary(updated_at DESC);
