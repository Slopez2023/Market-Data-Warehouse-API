-- Migration: Ensure market_data table ownership and indexes
-- Date: 2025-11-10
-- Purpose: Fix table ownership and ensure proper indexes

-- Note: market_data table is created in init script
-- This migration ensures market_user has proper ownership

-- Transfer ownership to market_user if not already owned
DO $$ BEGIN
    -- Only attempt if table exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='market_data') THEN
        ALTER TABLE market_data OWNER TO market_user;
        GRANT ALL PRIVILEGES ON TABLE market_data TO market_user;
    END IF;
EXCEPTION WHEN OTHERS THEN
    NULL;  -- Silently skip if table doesn't exist or other error
END $$;

-- Ensure indexes exist (safe to run multiple times)
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol);
CREATE INDEX IF NOT EXISTS idx_market_data_time ON market_data(time DESC);
