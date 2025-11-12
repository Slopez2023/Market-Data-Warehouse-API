-- Create tracked_symbols table
CREATE TABLE IF NOT EXISTS tracked_symbols (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    asset_class VARCHAR(20) NOT NULL DEFAULT 'stock',  -- 'stock', 'crypto', 'etf', etc.
    active BOOLEAN DEFAULT TRUE,
    date_added TIMESTAMPTZ DEFAULT NOW(),
    last_backfill TIMESTAMPTZ,
    backfill_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'failed'
    backfill_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_tracked_symbols_active ON tracked_symbols (active);
CREATE INDEX IF NOT EXISTS idx_tracked_symbols_asset_class ON tracked_symbols (asset_class);
CREATE INDEX IF NOT EXISTS idx_tracked_symbols_symbol ON tracked_symbols (symbol);
