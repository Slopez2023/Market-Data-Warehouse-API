# Market Prediction Data Implementation Plan

## What We Need For Predictive Models

### Tier 1: Essential (Already have OHLCV)
- ✓ OHLCV data (daily, intraday)
- Volume trend
- Price momentum (RSI, MACD)
- Moving averages (SMA, EMA)

### Tier 2: Important (To Add)
- **Dividends** - affects stock pricing models
- **Earnings** - major price drivers
- **Stock Splits** - data integrity
- **News Sentiment** - market reaction predictor
- **Analyst Ratings** - consensus predictions
- **Options Implied Volatility** - forward-looking risk

### Tier 3: Context (Macro)
- **Economic Indicators** - Fed rates, unemployment, GDP
- **Market Breadth** - market health indicators
- **Index Levels** - SPY, QQQ, DIA

## Database Schema Additions

### New Tables Needed

```sql
-- Fundamentals & Corporate Actions
dividends (symbol, date, amount)
stock_splits (symbol, date, ratio)
earnings (symbol, date, announced_date, eps_estimate, eps_actual, surprise%)
analyst_ratings (symbol, date, buy_count, hold_count, sell_count, avg_target)

-- Market Data Enhancements
news_articles (symbol, date, title, sentiment, source)
options_iv (symbol, expiration, strike, call_iv, put_iv, updated_at)

-- Economic Data
economic_indicators (indicator_code, date, value, unit)

-- Computed Features
technical_indicators (symbol, date, rsi, macd, sma_20, sma_50, ema_12, ema_26)
```

## Implementation Priority

### Phase 1: Core Prediction Data (Week 1)
1. Dividends & Splits (low volume, historical)
2. Basic news scraping (headlines + sentiment)
3. Options IV (when available)
4. Historical earnings

### Phase 2: Market Context (Week 2)
1. Economic indicators (FRED API)
2. Market status and holidays
3. Analyst ratings

### Phase 3: Real-time Enhancement (Week 3)
1. Intraday technical indicators
2. Real-time sentiment updates
3. Earnings surprises

## Data Sources Used

| Data Type | Source | Free? | API Key? | Rate Limit |
|-----------|--------|-------|----------|-----------|
| Dividends | yfinance | YES | NO | Unlimited |
| Stock Splits | yfinance | YES | NO | Unlimited |
| Earnings | yfinance | YES | NO | Unlimited |
| Analyst Ratings | Finnhub | YES* | YES | 60/min |
| News Sentiment | yfinance + Finnhub | YES* | YES | 60/min |
| Options IV | yfinance | YES | NO | Unlimited |
| Economic Data | FRED | YES | YES | Unlimited |
| Technical Indicators | Polygon/Alpha Vantage | YES* | YES | Limited |

## Implementation Details

### Step 1: Extend Database Schema
- Add new tables for each data type
- Create indexes for fast lookup
- Add foreign keys to market_data

### Step 2: Create Data Collection Scripts
- Backfill historical data (one-time)
- Daily incremental updates
- Scheduler integration

### Step 3: Add API Endpoints
- `/api/v1/fundamentals/{symbol}`
- `/api/v1/news/{symbol}`
- `/api/v1/dividends/{symbol}`
- `/api/v1/earnings/{symbol}`
- `/api/v1/indicators/{symbol}`

### Step 4: Build Feature Engineering Layer
- Calculate technical indicators from OHLCV
- Normalize fundamentals data
- Create training features for ML

## Expected Outcome

With this data, you can build models that predict:
- Short-term price movements (1-5 days) using technical + sentiment
- Medium-term trends (1-3 months) using fundamentals + earnings
- Volatility using IV + economic context
- Event-driven moves using news + earnings surprises

## Quick Start Order

1. `backfill_fundamentals.py` - Dividends, splits, earnings
2. `backfill_news_sentiment.py` - News headlines
3. `backfill_options_iv.py` - Options chain IV
4. `backfill_economic_data.py` - FRED indicators
5. Scheduler additions to run daily
6. Feature engineering notebook
