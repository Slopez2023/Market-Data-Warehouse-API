-- Migration: Add timeframe tracking to backfill_history
-- Date: 2025-11-11
-- Purpose: Track backfill results per (symbol, timeframe) pair

-- Check if backfill_history table exists, if so add timeframe column
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name = 'backfill_history'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns 
      WHERE table_schema = 'public' 
      AND table_name = 'backfill_history' 
      AND column_name = 'timeframe'
    ) THEN
      ALTER TABLE backfill_history
      ADD COLUMN timeframe VARCHAR(10) DEFAULT '1d';
      
      CREATE INDEX IF NOT EXISTS idx_backfill_history_symbol_timeframe 
      ON backfill_history(symbol, timeframe, backfill_timestamp DESC);
    END IF;
  END IF;
END $$;
