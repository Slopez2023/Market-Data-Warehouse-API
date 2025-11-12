-- Migration: Add options implied volatility tables
-- Date: 2025-11-11
-- Purpose: Phase 3 - Volatility regime identification and options pricing data

-- Table: options_iv (options chain snapshots with IV metrics)
CREATE TABLE IF NOT EXISTS options_iv (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL, -- Unix milliseconds
    quote_date DATE NOT NULL,
    expiration_date DATE NOT NULL,
    dte INT, -- Days to expiration (calculated)
    
    strike_price DECIMAL(12, 4) NOT NULL,
    option_type VARCHAR(4) NOT NULL, -- 'call' or 'put'
    
    -- IV metrics
    implied_volatility DECIMAL(8, 6),
    iv_rank DECIMAL(5, 2), -- 0-100
    iv_percentile DECIMAL(5, 2), -- 0-100
    iv_index DECIMAL(8, 6), -- Often Vix-related
    
    -- Greeks
    delta DECIMAL(5, 4),
    gamma DECIMAL(8, 6),
    vega DECIMAL(8, 6),
    theta DECIMAL(8, 6),
    rho DECIMAL(8, 6),
    
    -- Market data
    bid_price DECIMAL(12, 4),
    ask_price DECIMAL(12, 4),
    last_price DECIMAL(12, 4),
    bid_size INT,
    ask_size INT,
    volume INT,
    open_interest INT,
    
    -- Additional metrics
    intrinsic_value DECIMAL(12, 4),
    time_value DECIMAL(12, 4),
    probability_itm DECIMAL(5, 2), -- In-the-money probability
    
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, timestamp, option_type, strike_price, expiration_date),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX IF NOT EXISTS idx_options_iv_symbol ON options_iv(symbol);
CREATE INDEX IF NOT EXISTS idx_options_iv_timestamp ON options_iv(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_options_iv_expiration ON options_iv(expiration_date);
CREATE INDEX IF NOT EXISTS idx_options_iv_symbol_timestamp ON options_iv(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_options_iv_symbol_expiration ON options_iv(symbol, expiration_date, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_options_iv_symbol_date ON options_iv(symbol, quote_date DESC);

-- Table: options_chain_snapshot (compressed storage of entire chains)
CREATE TABLE IF NOT EXISTS options_chain_snapshot (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL,
    quote_date DATE NOT NULL,
    
    -- Aggregate IV metrics across chain
    atm_iv_call DECIMAL(8, 6), -- At-the-money IV for calls
    atm_iv_put DECIMAL(8, 6), -- At-the-money IV for puts
    atm_iv_avg DECIMAL(8, 6), -- Average ATM IV
    iv_skew DECIMAL(8, 6), -- Put IV - Call IV (measures tail risk)
    
    -- Chain statistics
    total_call_volume INT,
    total_put_volume INT,
    total_open_interest INT,
    call_oi INT,
    put_oi INT,
    put_call_ratio DECIMAL(8, 4),
    
    -- Volatility surface metrics
    iv_volatility DECIMAL(8, 6), -- Volatility of IV across strikes
    term_structure_slope DECIMAL(8, 6), -- Near-term vs far-term IV spread
    
    -- Composite indices
    vix_equivalent DECIMAL(8, 4), -- Synthetic VIX for stock
    
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, timestamp),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX IF NOT EXISTS idx_options_chain_snapshot_symbol ON options_chain_snapshot(symbol);
CREATE INDEX IF NOT EXISTS idx_options_chain_snapshot_timestamp ON options_chain_snapshot(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_options_chain_snapshot_symbol_timestamp ON options_chain_snapshot(symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_options_chain_snapshot_date ON options_chain_snapshot(quote_date DESC);

-- Materialized view: options_iv_daily_summary (daily summary for all symbols)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_options_iv_summary AS
SELECT 
    symbol,
    quote_date,
    
    -- ATM IV for each type
    AVG(CASE WHEN option_type = 'call' AND ABS(strike_price - 100) < 5 THEN implied_volatility END) as atm_iv_call,
    AVG(CASE WHEN option_type = 'put' AND ABS(strike_price - 100) < 5 THEN implied_volatility END) as atm_iv_put,
    
    -- Overall chain IV
    AVG(implied_volatility) as avg_iv,
    MAX(implied_volatility) as max_iv,
    MIN(implied_volatility) as min_iv,
    STDDEV(implied_volatility) as iv_std,
    
    -- Volume and OI
    SUM(volume) as total_volume,
    SUM(open_interest) as total_oi,
    SUM(CASE WHEN option_type = 'call' THEN open_interest ELSE 0 END) as call_oi,
    SUM(CASE WHEN option_type = 'put' THEN open_interest ELSE 0 END) as put_oi,
    
    -- Expiration metrics
    COUNT(DISTINCT expiration_date) as num_expirations,
    MIN(CASE WHEN expiration_date > quote_date THEN dte END) as min_dte,
    MAX(dte) as max_dte
FROM options_iv
GROUP BY symbol, quote_date;

CREATE INDEX IF NOT EXISTS idx_mv_options_iv_summary_symbol ON mv_options_iv_summary(symbol);
CREATE INDEX IF NOT EXISTS idx_mv_options_iv_summary_date ON mv_options_iv_summary(quote_date DESC);

-- Table: volatility_regime (classified regime by symbol and date)
CREATE TABLE IF NOT EXISTS volatility_regime (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    quote_date DATE NOT NULL,
    timestamp BIGINT NOT NULL,
    
    -- IV metrics
    iv_level DECIMAL(8, 6),
    iv_percentile_52w DECIMAL(5, 2), -- 0-100, 52-week percentile
    
    -- Regime classification
    regime VARCHAR(20), -- 'very_low', 'low', 'normal', 'high', 'very_high'
    regime_change VARCHAR(20), -- 'up', 'down', 'stable'
    
    -- Comparison to history
    iv_zscore DECIMAL(8, 4), -- Z-score vs 52-week history
    iv_percentile_252d DECIMAL(5, 2), -- 252-day (1-year) percentile
    
    -- Supporting metrics
    hv_30d DECIMAL(8, 6), -- 30-day historical volatility
    hv_252d DECIMAL(8, 6), -- 252-day historical volatility
    iv_hv_ratio DECIMAL(8, 4), -- IV / HV ratio (risk premium)
    
    put_call_ratio_iv DECIMAL(8, 4), -- Put/call IV ratio (tail risk premium)
    
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, quote_date),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX IF NOT EXISTS idx_volatility_regime_symbol ON volatility_regime(symbol);
CREATE INDEX IF NOT EXISTS idx_volatility_regime_date ON volatility_regime(quote_date DESC);
CREATE INDEX IF NOT EXISTS idx_volatility_regime_symbol_date ON volatility_regime(symbol, quote_date DESC);
CREATE INDEX IF NOT EXISTS idx_volatility_regime_regime ON volatility_regime(regime);
