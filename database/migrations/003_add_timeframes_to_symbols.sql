-- Migration: Add timeframes column to tracked_symbols
-- Date: 2025-11-11
-- Purpose: Enable per-symbol timeframe configuration
-- Updated: 2025-11-12 - Changed default to include all supported timeframes

ALTER TABLE tracked_symbols
ADD COLUMN IF NOT EXISTS timeframes TEXT[] DEFAULT ARRAY['5m', '15m', '30m', '1h', '4h', '1d', '1w'];

CREATE INDEX IF NOT EXISTS idx_tracked_symbols_timeframes ON tracked_symbols USING GIN(timeframes);

-- Update all existing symbols to use all supported timeframes (if they only have defaults)
UPDATE tracked_symbols
SET timeframes = ARRAY['5m', '15m', '30m', '1h', '4h', '1d', '1w']
WHERE timeframes IS NULL OR timeframes = ARRAY['1h', '1d'];
