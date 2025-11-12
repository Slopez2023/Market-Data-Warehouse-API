-- Migration: Backfill existing market_data with timeframes
-- Date: 2025-11-11
-- Purpose: Set timeframe='1d' for all existing records without timeframes

-- Backfill market_data table with default timeframe for existing records
UPDATE market_data
SET timeframe = '1d'
WHERE timeframe IS NULL OR timeframe = '';

-- If this migration fails due to permissions, it will be logged but won't halt startup
-- The application defaults timeframe to '1d' when not specified
