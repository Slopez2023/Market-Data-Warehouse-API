-- Migration: Add timeframe column to market_data
-- Date: 2025-11-11
-- Purpose: Track which timeframe each OHLCV candle belongs to

ALTER TABLE market_data
ADD COLUMN IF NOT EXISTS timeframe VARCHAR(10) DEFAULT '1d';

-- Backfill existing rows with default '1d'
UPDATE market_data
SET timeframe = '1d'
WHERE timeframe IS NULL;

-- Drop old constraint if it exists (for idempotency)
ALTER TABLE market_data
DROP CONSTRAINT IF EXISTS unique_market_data_symbol_timeframe_time;

-- Drop old indexes that don't include timeframe
DROP INDEX IF EXISTS idx_market_data_symbol_time;

-- Delete duplicate rows, keeping only the most recent one for each (symbol, timeframe, time)
DELETE FROM market_data
WHERE id NOT IN (
  SELECT MAX(id) 
  FROM market_data
  GROUP BY symbol, timeframe, time
);

-- Create new composite index with timeframe
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timeframe_time 
ON market_data(symbol, timeframe, time DESC);

-- Keep single symbol index for backward compatibility
CREATE INDEX IF NOT EXISTS idx_market_data_symbol ON market_data(symbol);

-- Add unique constraint on (symbol, timeframe, time) to prevent duplicates
ALTER TABLE market_data
ADD CONSTRAINT unique_market_data_symbol_timeframe_time 
UNIQUE (symbol, timeframe, time);
