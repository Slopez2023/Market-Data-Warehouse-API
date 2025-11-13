# Market Prediction Implementation Guide

## What You're Building

A complete data pipeline to collect free market data beyond OHLCV for ML model training.

## Files Created

### 1. **Database Schema** 
- `database/sql/05-market-prediction-tables.sql`
- Creates tables for: dividends, splits, earnings, news, options IV, indicators, fundamentals

### 2. **Data Collection Script**
- `scripts/backfill_prediction_data.py`
- Collects from yfinance (free): dividends, splits, earnings, news, options, fundamentals, technical indicators
- Optional Finnhub integration for analyst ratings

### 3. **Feature Engineering**
- `scripts/feature_engineering.py`
- Converts raw data into ML features
- Combines OHLCV + fundamentals + events + sentiment + technicals

### 4. **Planning Docs**
- `MARKET_PREDICTION_PLAN.md` - Strategy & priorities
- `DATA_MATRIX.txt` - What each source provides
- `FREE_SOURCES_PLAN.txt` - Test script documentation

---

## Quick Start (3 Steps)

### Step 1: Setup Database
```bash
# Apply migration
psql -h $DB_HOST -U $DB_USER -d $DB_NAME < database/sql/05-market-prediction-tables.sql
```

### Step 2: Get API Keys (Optional)
```bash
# In .env file, add:
FINNHUB_API_KEY=your_key      # For analyst ratings
FRED_API_KEY=your_key          # For economic data
```

### Step 3: Run Backfill
```bash
# Backfill prediction data for symbols
python scripts/backfill_prediction_data.py AAPL MSFT GOOGL AMZN

# Output: Fills all tables with historical data
```

---

## Data Collected

### From yfinance (FREE, NO AUTH)
✓ Dividends - payment history  
✓ Stock Splits - historical splits  
✓ Earnings - announcements & EPS  
✓ News - company news articles  
✓ Options Chain - calls/puts, IV  
✓ Company Fundamentals - PE, market cap, sector, etc.  
✓ Technical Indicators - RSI, MACD, Bollinger Bands, ATR  

### From Finnhub (FREE TIER, API KEY)
✓ Analyst Ratings - buy/hold/sell counts  

### From FRED (FREE, API KEY)
✓ Economic Indicators - GDP, unemployment, interest rates  

---

## What This Enables

### Price Prediction (1-5 days)
- OHLCV + Technical Indicators + Volume
- News Sentiment + Earnings Surprises
- Options IV (forward-looking volatility)

### Fundamental Analysis
- PE Ratio, PB Ratio, ROE, ROA
- Dividend Yield, Debt-to-Equity
- Company Sector/Industry

### Event Detection
- Earnings announcements (days until)
- Dividend exes (days until)
- Recent news sentiment

### Market Context
- Economic indicators (macro trends)
- Market breadth
- Volatility environment

---

## ML Feature Engineering

The `feature_engineering.py` script builds features from raw data:

```python
from scripts.feature_engineering import build_ml_dataset

# Load data from database
ohlcv = get_ohlcv('AAPL', '2023-01-01', '2024-01-01')
technical = get_technical_indicators('AAPL')
earnings = get_earnings('AAPL')
news = get_news('AAPL')

# Build features
X, y = build_ml_dataset(
    ohlcv_df=ohlcv,
    technical_df=technical,
    earnings_df=earnings,
    news_df=news,
    target_horizon=5,  # Predict 5 days ahead
    regression=False   # Classification: up/down
)

# Train model
model.fit(X, y)
```

### Features Generated

**Price/Volume:**
- 1d, 5d, 20d returns
- High/low ratio
- Volatility (20/60 day)
- Volume ratio & trend
- On-Balance Volume (OBV)

**Momentum:**
- Rate of Change (ROC)
- MACD crossovers
- SMA crossovers (20/50)
- RSI overbought/oversold

**Events:**
- Days to earnings
- Days to dividend
- Recent earnings surprise
- Recent positive/negative news count

**Fundamentals:**
- PE Ratio
- PB Ratio
- ROE, ROA
- Dividend Yield

**Options:**
- At-The-Money IV (calls/puts)
- IV Skew

---

## Database Schema Overview

```
dividends
├─ symbol, ex_date, dividend_amount
└─ payment_date, record_date

stock_splits
├─ symbol, split_date, split_ratio

earnings
├─ symbol, earnings_date, eps_estimate, eps_actual
├─ eps_surprise, revenue_surprise
└─ announced_date

news_articles
├─ symbol, news_date, title, sentiment
└─ sentiment_score, source

options_iv
├─ symbol, expiration_date, strike_price
├─ option_type, implied_volatility
└─ open_interest, volume

technical_indicators
├─ symbol, indicator_date
├─ rsi_14, macd, macd_signal, macd_histogram
├─ sma_20/50/200, ema_12/26
├─ bollinger_bands (upper/middle/lower)
├─ atr_14, volume_sma_20

company_fundamentals
├─ symbol (unique)
├─ company_name, sector, industry
├─ market_cap, pe_ratio, pb_ratio
├─ dividend_yield, roe, roa, debt_to_equity

economic_indicators
├─ indicator_code, value_date, value
└─ indicator_name, unit

market_status
├─ status_date, is_market_open
└─ holiday_name, early_close
```

---

## Next Steps After Backfill

### 1. Add API Endpoints
Create endpoints to serve the data:
```python
@app.get("/api/v1/{symbol}/fundamentals")
@app.get("/api/v1/{symbol}/news")
@app.get("/api/v1/{symbol}/earnings")
@app.get("/api/v1/{symbol}/indicators")
@app.get("/api/v1/{symbol}/dividend-history")
```

### 2. Create ML Model
```python
X, y = build_ml_dataset(...)
model = XGBClassifier()
model.fit(X, y)
model.save('price_prediction_model.pkl')
```

### 3. Real-time Predictions
Add scheduler task:
```python
@scheduler.scheduled_job('cron', hour=16)
def predict_next_day():
    # Get latest data
    # Make predictions
    # Store results
    pass
```

### 4. Backtest
Test model on historical data:
```python
results = backtest_model(
    model,
    start_date='2023-01-01',
    end_date='2024-01-01'
)
print(f"Accuracy: {results['accuracy']}")
print(f"Sharpe: {results['sharpe_ratio']}")
```

---

## Rate Limits & Costs

| Source | Rate Limit | Cost | Notes |
|--------|-----------|------|-------|
| yfinance | Unlimited | FREE | Best for stock data |
| Finnhub | 60/min | FREE tier | Analyst ratings |
| FRED | Unlimited | FREE | Economic data |
| Alpha Vantage | 5/min | FREE tier | Intraday data |
| Polygon | Various | $200+/mo | Advanced features |
| CoinGecko | Unlimited | FREE | Crypto only |

---

## Troubleshooting

### No data returned
- Check API keys in .env
- Verify symbol spelling
- yfinance might be rate limited - wait & retry

### Database errors
- Ensure migration ran: `05-market-prediction-tables.sql`
- Check DB connection in .env
- Verify user has CREATE TABLE permission

### Feature engineering errors
- Ensure technical_indicators table is populated first
- News/earnings tables might be empty for newer symbols
- Fill NaN values before training

---

## Testing

Run tests for free data sources:
```bash
python scripts/test_free_datasources.py
# Outputs: datasource_test_results_YYYYMMDD_HHMMSS.json
```

This tests all 7 sources and shows what each provides.

---

## Model Prediction Example

```python
import pandas as pd
from scripts.feature_engineering import build_ml_dataset
import pickle

# Load trained model
model = pickle.load(open('price_prediction_model.pkl', 'rb'))

# Get latest data
ohlcv = get_ohlcv('AAPL', days=100)
technical = get_technical_indicators('AAPL')
earnings = get_earnings('AAPL')
news = get_news('AAPL')

# Build features
X, _ = build_ml_dataset(
    ohlcv_df=ohlcv,
    technical_df=technical,
    earnings_df=earnings,
    news_df=news
)

# Predict
prediction = model.predict(X.iloc[-1:])
probability = model.predict_proba(X.iloc[-1:])

print(f"Tomorrow's prediction: {'UP' if prediction[0] else 'DOWN'}")
print(f"Confidence: {probability[0][prediction[0]]:.2%}")
```

---

## Architecture Summary

```
Free Data Sources
    ↓
[backfill_prediction_data.py]
    ↓
PostgreSQL Database
    ├─ market_data (OHLCV)
    ├─ dividends
    ├─ earnings
    ├─ news_articles
    ├─ options_iv
    ├─ technical_indicators
    ├─ company_fundamentals
    └─ economic_indicators
    ↓
[feature_engineering.py]
    ↓
ML Features (X, y)
    ↓
ML Model (XGBoost, Neural Net, etc)
    ↓
Price Predictions
```

This gives you everything needed for market prediction models using only free data.
