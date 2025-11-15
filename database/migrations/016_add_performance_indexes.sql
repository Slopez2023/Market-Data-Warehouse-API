-- Performance optimization indexes
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_timeframe ON market_data(timeframe);
CREATE INDEX IF NOT EXISTS idx_tracked_symbols_symbol ON tracked_symbols(symbol);
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timeframe ON market_data(symbol, timeframe, time DESC);
