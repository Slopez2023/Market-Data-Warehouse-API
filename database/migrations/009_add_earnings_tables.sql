-- Migration: Add earnings and earnings_surprise tables
-- Date: 2025-11-11
-- Purpose: Phase 3 - Event detection for algo triggers and backtesting adjustments

-- Table: earnings (earnings announcements with estimates vs actuals)
CREATE TABLE IF NOT EXISTS earnings (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    earnings_date DATE NOT NULL,
    earnings_time VARCHAR(20), -- 'bmo' (before market open), 'amc' (after market close), 'after_hours'
    fiscal_year INT,
    fiscal_quarter INT,
    
    -- Estimates
    estimated_eps DECIMAL(12, 4),
    estimated_revenue DECIMAL(18, 2),
    estimated_gross_margin DECIMAL(5, 2),
    estimated_operating_margin DECIMAL(5, 2),
    
    -- Actuals
    actual_eps DECIMAL(12, 4),
    actual_revenue DECIMAL(18, 2),
    actual_gross_margin DECIMAL(5, 2),
    actual_operating_margin DECIMAL(5, 2),
    
    -- Surprises
    surprise_eps DECIMAL(12, 4),
    surprise_eps_pct DECIMAL(8, 4),
    surprise_revenue DECIMAL(18, 2),
    surprise_revenue_pct DECIMAL(8, 4),
    
    -- Context
    prior_eps DECIMAL(12, 4),
    prior_revenue DECIMAL(18, 2),
    eps_guidance_high DECIMAL(12, 4),
    eps_guidance_low DECIMAL(12, 4),
    revenue_guidance_high DECIMAL(18, 2),
    revenue_guidance_low DECIMAL(18, 2),
    conference_call_url VARCHAR(500),
    
    -- Metadata
    data_source VARCHAR(50), -- 'polygon', 'benzinga', 'manual'
    confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(symbol, earnings_date),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX IF NOT EXISTS idx_earnings_symbol ON earnings(symbol);
CREATE INDEX IF NOT EXISTS idx_earnings_date ON earnings(earnings_date);
CREATE INDEX IF NOT EXISTS idx_earnings_symbol_date ON earnings(symbol, earnings_date DESC);
CREATE INDEX IF NOT EXISTS idx_earnings_fiscal ON earnings(symbol, fiscal_year, fiscal_quarter);

-- Table: earnings_estimates (historical estimates for tracking revisions)
CREATE TABLE IF NOT EXISTS earnings_estimates (
    id SERIAL PRIMARY KEY,
    earnings_id INT NOT NULL,
    estimate_date DATE NOT NULL,
    estimated_eps DECIMAL(12, 4),
    estimated_revenue DECIMAL(18, 2),
    num_analysts INT,
    revision_direction VARCHAR(20), -- 'up', 'down', 'none'
    
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (earnings_id) REFERENCES earnings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_earnings_estimates_earnings_id ON earnings_estimates(earnings_id);
CREATE INDEX IF NOT EXISTS idx_earnings_estimates_date ON earnings_estimates(estimate_date);

-- Materialized view: earnings_summary (aggregated metrics by symbol)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_earnings_summary AS
SELECT 
    symbol,
    COUNT(*) as total_earnings,
    AVG(surprise_eps_pct) as avg_eps_surprise_pct,
    AVG(surprise_revenue_pct) as avg_revenue_surprise_pct,
    SUM(CASE WHEN surprise_eps > 0 THEN 1 ELSE 0 END) as positive_eps_surprises,
    SUM(CASE WHEN surprise_revenue > 0 THEN 1 ELSE 0 END) as positive_revenue_surprises,
    MAX(earnings_date) as latest_earnings,
    (SELECT COUNT(*) FROM earnings e2 WHERE e2.symbol = e1.symbol AND e2.earnings_date > NOW() - INTERVAL '90 days') as recent_earnings_count
FROM earnings e1
WHERE earnings_date IS NOT NULL
GROUP BY symbol;

CREATE INDEX IF NOT EXISTS idx_mv_earnings_summary_symbol ON mv_earnings_summary(symbol);
