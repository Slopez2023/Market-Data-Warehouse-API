-- Migration: Add timeframes column to tracked_symbols
-- Date: 2025-11-11
-- Purpose: Enable per-symbol timeframe configuration

ALTER TABLE tracked_symbols
ADD COLUMN IF NOT EXISTS timeframes TEXT[] DEFAULT ARRAY['1h', '1d'];

CREATE INDEX IF NOT EXISTS idx_tracked_symbols_timeframes ON tracked_symbols USING GIN(timeframes);

-- Verify all existing symbols have default timeframes
UPDATE tracked_symbols
SET timeframes = ARRAY['1h', '1d']
WHERE timeframes IS NULL;
