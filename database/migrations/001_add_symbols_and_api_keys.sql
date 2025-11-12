-- Migration: Verify tracked_symbols and api_keys tables exist
-- Date: 2025-11-10
-- Purpose: Ensure proper indexes and ownership for symbol and API key management

-- These tables are created in the init script - this migration just ensures proper structure
-- Verify indexes exist for tracked_symbols
CREATE INDEX IF NOT EXISTS idx_tracked_symbols_active ON tracked_symbols (active);
CREATE INDEX IF NOT EXISTS idx_tracked_symbols_asset_class ON tracked_symbols (asset_class);
CREATE INDEX IF NOT EXISTS idx_tracked_symbols_symbol ON tracked_symbols (symbol);

-- Verify indexes exist for api_keys
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys (active);
CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys (key_hash);

-- Verify indexes exist for api_key_audit
CREATE INDEX IF NOT EXISTS idx_api_key_audit_key_id ON api_key_audit (api_key_id);
CREATE INDEX IF NOT EXISTS idx_api_key_audit_timestamp ON api_key_audit (timestamp DESC);
