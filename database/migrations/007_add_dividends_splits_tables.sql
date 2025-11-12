-- Migration: Add dividends, stock_splits, and ohlcv_adjusted tables
-- Date: 2025-11-11
-- Purpose: Phase 1 - Support dividend/split adjustments for accurate backtesting

-- Table: dividends
CREATE TABLE IF NOT EXISTS dividends (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    ex_date DATE NOT NULL,
    record_date DATE,
    pay_date DATE,
    dividend_amount DECIMAL(12, 4) NOT NULL,
    dividend_type VARCHAR(50) DEFAULT 'regular',
    adjusted BOOLEAN DEFAULT FALSE,
    currency VARCHAR(3) DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, ex_date),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX IF NOT EXISTS idx_dividends_symbol ON dividends(symbol);
CREATE INDEX IF NOT EXISTS idx_dividends_ex_date ON dividends(ex_date);
CREATE INDEX IF NOT EXISTS idx_dividends_symbol_date ON dividends(symbol, ex_date DESC);

-- Table: stock_splits
CREATE TABLE IF NOT EXISTS stock_splits (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    execution_date DATE NOT NULL,
    split_from INT NOT NULL,
    split_to INT NOT NULL,
    split_ratio DECIMAL(10, 4) NOT NULL,
    adjusted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, execution_date),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX IF NOT EXISTS idx_splits_symbol ON stock_splits(symbol);
CREATE INDEX IF NOT EXISTS idx_splits_execution_date ON stock_splits(execution_date);
CREATE INDEX IF NOT EXISTS idx_splits_symbol_date ON stock_splits(symbol, execution_date DESC);

-- Table: ohlcv_adjusted (stores cached adjusted prices)
CREATE TABLE IF NOT EXISTS ohlcv_adjusted (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open_adj DECIMAL(12, 4),
    high_adj DECIMAL(12, 4),
    low_adj DECIMAL(12, 4),
    close_adj DECIMAL(12, 4),
    volume_adj BIGINT,
    adjustment_factor DECIMAL(12, 8),
    adjustment_note TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, timestamp, timeframe),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_adj_symbol_time ON ohlcv_adjusted(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_ohlcv_adj_symbol_timeframe ON ohlcv_adjusted(symbol, timeframe);

-- Table: backfill_progress (for resumable backfills)
CREATE TABLE IF NOT EXISTS backfill_progress (
    id SERIAL PRIMARY KEY,
    backfill_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    last_processed_date DATE,
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    attempted_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    UNIQUE(backfill_type, symbol)
);

CREATE INDEX IF NOT EXISTS idx_backfill_progress_type_status ON backfill_progress(backfill_type, status);
CREATE INDEX IF NOT EXISTS idx_backfill_progress_symbol ON backfill_progress(symbol);
