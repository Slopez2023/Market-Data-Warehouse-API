-- Migration: Add tracked_symbols and api_keys tables
-- Date: 2025-11-10
-- Purpose: Enable dynamic symbol management and API key authentication

-- Tracked symbols table
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

-- API keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id BIGSERIAL PRIMARY KEY,
    key_hash VARCHAR(64) NOT NULL UNIQUE,  -- SHA256 hex digest
    name VARCHAR(100) NOT NULL,  -- e.g., "Project Alpha", "Personal"
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used TIMESTAMPTZ,
    last_used_endpoint VARCHAR(200),
    request_count BIGINT DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys (active);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys (key_hash);

-- Audit table for API key usage
CREATE TABLE IF NOT EXISTS api_key_audit (
    id BIGSERIAL PRIMARY KEY,
    api_key_id BIGINT NOT NULL,
    endpoint VARCHAR(200),
    method VARCHAR(10),
    status_code INT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_api_key_audit_key_id ON api_key_audit (api_key_id);
CREATE INDEX IF NOT EXISTS idx_api_key_audit_timestamp ON api_key_audit (timestamp DESC);
