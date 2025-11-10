-- Migration: Add market_data table
-- Date: 2025-11-10
-- Purpose: Store OHLCV data for market symbols

CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    time TIMESTAMPTZ NOT NULL,
    open DECIMAL(15, 2) NOT NULL,
    high DECIMAL(15, 2) NOT NULL,
    low DECIMAL(15, 2) NOT NULL,
    close DECIMAL(15, 2) NOT NULL,
    volume BIGINT NOT NULL,
    source VARCHAR(50) DEFAULT 'polygon',
    validated BOOLEAN DEFAULT FALSE,
    gap_detected BOOLEAN DEFAULT FALSE,
    quality_score DECIMAL(3, 2) DEFAULT 1.0,
    validation_timestamp TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol);
CREATE INDEX IF NOT EXISTS idx_market_data_time ON market_data(time DESC);
