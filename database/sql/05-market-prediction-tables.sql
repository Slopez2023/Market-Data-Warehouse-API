-- Market Prediction Data Tables
-- Adds fundamental, news, and indicator data needed for ML models

-- Dividends & Corporate Actions
CREATE TABLE IF NOT EXISTS dividends (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    ex_date DATE NOT NULL,
    record_date DATE,
    payment_date DATE,
    dividend_amount DECIMAL(19,8) NOT NULL,
    dividend_type VARCHAR(50),
    data_source VARCHAR(50) DEFAULT 'yfinance',
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, ex_date, dividend_amount)
);

CREATE INDEX IF NOT EXISTS idx_dividends_symbol_date ON dividends (symbol, ex_date DESC);


-- Stock Splits
CREATE TABLE IF NOT EXISTS stock_splits (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    split_date DATE NOT NULL,
    split_ratio DECIMAL(19,8) NOT NULL,
    description VARCHAR(255),
    data_source VARCHAR(50) DEFAULT 'yfinance',
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, split_date, split_ratio)
);

CREATE INDEX IF NOT EXISTS idx_splits_symbol_date ON stock_splits (symbol, split_date DESC);


-- Earnings Announcements
CREATE TABLE IF NOT EXISTS earnings (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    earnings_date DATE NOT NULL,
    announced_date DATE,
    fiscal_period VARCHAR(20),
    eps_estimate DECIMAL(19,8),
    eps_actual DECIMAL(19,8),
    eps_surprise DECIMAL(5,2),
    revenue_estimate BIGINT,
    revenue_actual BIGINT,
    revenue_surprise DECIMAL(5,2),
    surprise_percent DECIMAL(5,2),
    data_source VARCHAR(50) DEFAULT 'yfinance',
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, earnings_date)
);

CREATE INDEX IF NOT EXISTS idx_earnings_symbol_date ON earnings (symbol, earnings_date DESC);
CREATE INDEX IF NOT EXISTS idx_earnings_announced ON earnings (announced_date DESC);


-- Analyst Ratings
CREATE TABLE IF NOT EXISTS analyst_ratings (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    rating_date DATE NOT NULL,
    buy_count INT,
    hold_count INT,
    sell_count INT,
    strong_buy_count INT,
    strong_sell_count INT,
    avg_target_price DECIMAL(19,8),
    recommendation VARCHAR(50),
    data_source VARCHAR(50) DEFAULT 'finnhub',
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, rating_date)
);

CREATE INDEX IF NOT EXISTS idx_ratings_symbol_date ON analyst_ratings (symbol, rating_date DESC);


-- News Articles
CREATE TABLE IF NOT EXISTS news_articles (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    news_date TIMESTAMPTZ NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,
    url VARCHAR(2048),
    source VARCHAR(100),
    sentiment VARCHAR(20),
    sentiment_score DECIMAL(3,2),
    importance_score DECIMAL(3,2),
    data_source VARCHAR(50) DEFAULT 'yfinance',
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, url)
);

CREATE INDEX IF NOT EXISTS idx_news_symbol_date ON news_articles (symbol, news_date DESC);
CREATE INDEX IF NOT EXISTS idx_news_sentiment ON news_articles (symbol, sentiment, news_date DESC);


-- Options Implied Volatility
CREATE TABLE IF NOT EXISTS options_iv (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    expiration_date DATE NOT NULL,
    strike_price DECIMAL(19,8) NOT NULL,
    option_type VARCHAR(10),
    implied_volatility DECIMAL(5,4),
    open_interest INT,
    volume INT,
    last_price DECIMAL(19,8),
    bid DECIMAL(19,8),
    ask DECIMAL(19,8),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    data_source VARCHAR(50) DEFAULT 'yfinance',
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, expiration_date, strike_price, option_type, updated_at::DATE)
);

CREATE INDEX IF NOT EXISTS idx_options_symbol_expiry ON options_iv (symbol, expiration_date);
CREATE INDEX IF NOT EXISTS idx_options_iv_value ON options_iv (symbol, implied_volatility DESC);


-- Economic Indicators (FRED data)
CREATE TABLE IF NOT EXISTS economic_indicators (
    id BIGSERIAL PRIMARY KEY,
    indicator_code VARCHAR(20) NOT NULL,
    indicator_name VARCHAR(255),
    value_date DATE NOT NULL,
    value DECIMAL(19,8),
    unit VARCHAR(50),
    data_source VARCHAR(50) DEFAULT 'fred',
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(indicator_code, value_date)
);

CREATE INDEX IF NOT EXISTS idx_economic_code_date ON economic_indicators (indicator_code, value_date DESC);
CREATE INDEX IF NOT EXISTS idx_economic_date ON economic_indicators (value_date DESC);


-- Technical Indicators (Computed Features)
CREATE TABLE IF NOT EXISTS technical_indicators (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    indicator_date DATE NOT NULL,
    rsi_14 DECIMAL(5,2),
    macd DECIMAL(19,8),
    macd_signal DECIMAL(19,8),
    macd_histogram DECIMAL(19,8),
    sma_20 DECIMAL(19,8),
    sma_50 DECIMAL(19,8),
    sma_200 DECIMAL(19,8),
    ema_12 DECIMAL(19,8),
    ema_26 DECIMAL(19,8),
    bb_upper DECIMAL(19,8),
    bb_middle DECIMAL(19,8),
    bb_lower DECIMAL(19,8),
    atr_14 DECIMAL(19,8),
    volume_sma_20 BIGINT,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, indicator_date)
);

CREATE INDEX IF NOT EXISTS idx_indicators_symbol_date ON technical_indicators (symbol, indicator_date DESC);


-- Company Fundamentals (Cached)
CREATE TABLE IF NOT EXISTS company_fundamentals (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    company_name VARCHAR(255),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap BIGINT,
    pe_ratio DECIMAL(10,2),
    pb_ratio DECIMAL(10,2),
    dividend_yield DECIMAL(5,4),
    current_ratio DECIMAL(10,2),
    debt_to_equity DECIMAL(10,2),
    roe DECIMAL(5,2),
    roa DECIMAL(5,2),
    current_price DECIMAL(19,8),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    data_source VARCHAR(50) DEFAULT 'yfinance',
    fetched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fundamentals_sector ON company_fundamentals (sector);


-- Market Status & Holidays
CREATE TABLE IF NOT EXISTS market_status (
    id BIGSERIAL PRIMARY KEY,
    status_date DATE UNIQUE NOT NULL,
    is_market_open BOOLEAN,
    market_hour_open TIME,
    market_hour_close TIME,
    is_holiday BOOLEAN,
    holiday_name VARCHAR(255),
    early_close BOOLEAN,
    early_close_time TIME,
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_status_date ON market_status (status_date);
