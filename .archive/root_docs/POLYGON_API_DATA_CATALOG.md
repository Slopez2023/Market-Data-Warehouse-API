# Polygon.io (Massive.com) - Complete Data Catalog

Complete reference of all data available from Polygon.io API that can be backfilled and used for trading strategies and AI pattern recognition.

---

## 1. PRICE & VOLUME DATA (Currently Implemented)

### Aggregates (OHLCV Candles)
- **Timeframes**: 5m, 15m, 30m, 1h, 4h, 1d, 1w
- **Assets**: Stocks, Crypto, Forex
- **Fields**: Open, High, Low, Close, Volume, Count
- **Implementation**: ✅ Fully backfilled for all 60 symbols × 7 timeframes
- **Polygon Endpoint**: `GET /v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from}/{to}`

### Real-time Prices (Quotes & Trades)
- **Last trade price**: Real-time bid/ask for stocks
- **Volume at bid/ask**: Market microstructure data
- **Implementation**: ❌ Not backfilled (requires real-time streaming)
- **Polygon Endpoint**: `GET /v3/quotes/last`

---

## 2. CORPORATE ACTIONS (High Priority for AI)

### Dividends
- **Data**: Dividend amount, ex-date, pay-date, record-date, type
- **Use Case**: Adjust OHLCV for accurate backtesting, detect income-based trading patterns
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: `GET /v2/reference/dividends`
- **Backfill Recommendation**: **HIGH PRIORITY** - Essential for clean price history

### Stock Splits
- **Data**: Split ratio, execution date
- **Use Case**: Critical for OHLCV normalization, detect post-split volatility patterns
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: `GET /v2/reference/splits`
- **Backfill Recommendation**: **HIGH PRIORITY** - Prevents false pattern detection

### Corporate Actions (General)
- **Types**: Mergers, spin-offs, rights offerings
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: `GET /v1/reference/corporateactions`

---

## 3. FUNDAMENTALS & REFERENCE DATA

### Ticker Details
- **Fields**: 
  - Company name, description, homepage URL
  - Market cap, employees, phone number
  - Industry (SIC code), sector
  - Exchange, currency
  - Logo/branding URLs
  - Active status, delisted date
  - CUSIP, CIK, FIGI codes
- **Use Case**: Sector rotation signals, fundamental context for ML models
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: `GET /v3/reference/tickers/{ticker}`

### Financial Statements (SEC Filings - XBRL)
- **Data**: Revenue, net income, total assets, debt, cash flow, earnings per share
- **Frequency**: Quarterly (10-Q) and Annual (10-K)
- **Use Case**: Long-term trend analysis, fundamental score features for ML
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: `GET /vX/reference/financials` (experimental)
- **Note**: Lower priority - overkill unless building hedge-fund-grade system

### Exchange Information
- **Fields**: Exchange code, name, timezone, status
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: `GET /v3/reference/exchanges`

---

## 4. NEWS & SENTIMENT (Highest Priority for AI)

### Ticker News
- **Fields**: Title, description, URL, author, published date, image URL
- **Coverage**: Real-time and historical news articles
- **Use Case**: **ML text analysis** → sentiment scores, event detection, price correlation
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: `GET /v2/reference/news`
- **Backfill Recommendation**: **HIGHEST PRIORITY** - Strong ML signals

### Sentiment Analysis (via Benzinga Partnership)
- **Data**: Sentiment score (-1.0 to 1.0), sentiment label (bearish/neutral/bullish)
- **Coverage**: Earnings, analyst ratings, corporate guidance
- **Use Case**: **Directional bias signals**, ML feature for volatility/returns prediction
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: Benzinga Analyst Ratings, Earnings APIs
- **Backfill Recommendation**: **HIGH PRIORITY** - Excellent for directional models

### Analyst Ratings (Benzinga)
- **Data**: Analyst rating, target price, recommendation changes
- **Frequency**: Real-time updates
- **Use Case**: Consensus signals, contrarian indicators
- **Implementation**: ❌ Not backfilled

---

## 5. EARNINGS DATA (High Priority for Event-Driven AI)

### Earnings Announcements
- **Fields**: Earnings date, time, estimated EPS, actual EPS, surprise %
- **Frequency**: Quarterly per company
- **Use Case**: **Event-driven strategies**, volatility clustering post-earnings, directional bias
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: Benzinga Earnings API
- **Backfill Recommendation**: **HIGH PRIORITY** - Major ML catalyst signals

---

## 6. VOLATILITY & OPTIONS DATA (Medium Priority)

### Options Contracts
- **Fields**: Strike price, expiration date, bid/ask, implied volatility, Greeks (Delta, Gamma, Vega, Theta, Rho)
- **Use Case**: **Volatility regime identification**, probability-weighted price targets
- **Implementation**: ❌ Not backfilled (real-time only useful)
- **Polygon Endpoint**: `GET /v3/snapshot/options/chains/{underlying}`
- **Note**: Limited historical data; lower priority for backtesting

### Implied Volatility (IV)
- **Data**: IV index per strike, term structure
- **Use Case**: **Volatility prediction**, inverse relationship with price = reversal signals
- **Implementation**: ❌ Not backfilled
- **Note**: IV crush/expansion patterns useful for ML

---

## 7. MARKET OPERATIONS & REFERENCE

### Market Holidays
- **Data**: Holiday dates, early closes
- **Use Case**: Prevent backtesting/signal errors on non-trading days
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: `GET /v3/reference/market-holidays`

### Market Status
- **Data**: Market open/closed status, pre-market/after-hours status
- **Implementation**: ❌ Not backfilled
- **Polygon Endpoint**: `GET /v1/market/status`

### Trading Conditions
- **Data**: SIP conditions, order types, order statuses
- **Use Case**: Advanced order microstructure analysis (niche)
- **Implementation**: ❌ Not backfilled

---

## 8. ASSET CLASS COVERAGE

### Stocks
- ✅ OHLCV candles (all timeframes)
- ❌ Options, earnings, dividends, news, sentiment
- **50+ symbols backfilled with 1d/1w, most with intraday (5m-4h)**

### Crypto
- ✅ OHLCV candles daily/weekly only (intraday not available from Polygon)
- ❌ News, sentiment (no official source)
- ❌ Earnings (not applicable)
- ❌ Dividends (not applicable)
- **20 symbols backfilled with 1d/1w candles**

### Forex
- ✅ OHLCV candles (all timeframes)
- ❌ News, sentiment (limited)
- **Not yet backfilled; available via API**

### Futures
- ❌ Currently not supported (requires separate setup)
- **Available from Polygon but not integrated**

### Indices
- ✅ OHLCV candles (all timeframes)
- ❌ Components, rebalancing data
- **Not backfilled; available via API**

---

## 9. DATA QUALITY & ADJUSTMENTS

### Data Issues Currently Handled
- ✅ Volume anomaly detection
- ✅ Price gap validation
- ✅ Data range validation
- ❌ Dividend-adjusted prices
- ❌ Split-adjusted prices
- ❌ Data reconciliation with other sources

### Recommended Adjustments for Clean Data
1. **Dividend adjustment**: Close price *= (1 - dividend yield)
2. **Split adjustment**: Divide OHLCV by split ratio
3. **Delisting detection**: Flag symbols with trading gaps > 30 days

---

## 10. RECOMMENDED BACKFILL PRIORITY

### Priority 1: Essential for Backtesting (Do First)
1. **Dividends** - OHLCV normalization
2. **Stock Splits** - Price history accuracy
3. **News + Sentiment** - ML feature richness, strong price correlation

### Priority 2: High Value for ML (Do Second)
1. **Earnings data** - Event detection, volatility prediction
2. **Analyst ratings** - Consensus signals, contrarian strategies
3. **Ticker details** - Sector rotation, fundamental context

### Priority 3: Nice to Have (Do Later)
1. **Options IV** - Volatility regime identification
2. **Market holidays** - Clean backtesting windows
3. **Exchange info** - Data validation

### Priority 4: Skip (Unless Hedge Fund)
1. Detailed financial statements
2. Options Greeks (low historical depth)
3. Futures data (separate infrastructure needed)

---

## 11. IMPLEMENTATION ROADMAP

### Current State
```
✅ OHLCV candles: 60 symbols × 7 timeframes (5m-1w)
✅ Validation: Volume anomalies, price gaps, data ranges
❌ Everything else
```

### Phase 2 (Recommended)
```
🔲 Dividends backfill (all stocks)
🔲 Stock splits backfill (all stocks)
🔲 News + sentiment backfill (recent 2-3 years)
```

### Phase 3
```
🔲 Earnings announcements (2-3 years historical)
🔲 Analyst ratings (recent only)
🔲 Ticker fundamentals (company info, market cap)
```

### Phase 4+
```
🔲 Market holidays, trading status
🔲 Options data (real-time focus)
🔲 Forex backfill
```

---

## 12. API LIMITS & RATE LIMITS

- **Request Limit**: 150 requests/minute (free tier)
- **Aggregates Limit**: 50,000 results per request (pagination needed for 5m+ data)
- **Historical Depth**: Full historical data for stocks/crypto/forex
- **Real-time Data**: Requires WebSocket connection (separate from backfill)

---

## 13. USAGE EXAMPLES FOR AI/ML

### Sentiment-Based Strategy
```python
# Pseudo-code
news_sentiment = get_ticker_news_sentiment(symbol)
price_momentum = calculate_price_momentum(ohlcv)
predicted_direction = ml_model(news_sentiment, price_momentum)
```

### Earnings-Driven Strategy
```python
earnings_surprise = (actual_eps - expected_eps) / expected_eps
post_earnings_volatility = calculate_volatility(ohlcv_post_earnings)
reversal_signal = ml_model(earnings_surprise, volatility)
```

### Dividend Yield Rotation
```python
dividend_yield = annual_dividend / current_price
sector_rotation = compare_yields_across_sector(fundamentals)
rebalance_signal = ml_model(yield_change, sector_trend)
```

---

## 14. DATA SCHEMA FOR FUTURE STORAGE

### Minimal Schema (Priority 1-2)
```sql
CREATE TABLE dividends (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    ex_date DATE,
    pay_date DATE,
    record_date DATE,
    dividend_amount DECIMAL,
    dividend_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE stock_splits (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    execution_date DATE,
    split_from INT,
    split_to INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE news (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    title TEXT,
    description TEXT,
    published_date TIMESTAMP,
    sentiment_score DECIMAL(-1.0 to 1.0),
    url VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE earnings (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    earnings_date DATE,
    estimated_eps DECIMAL,
    actual_eps DECIMAL,
    surprise_pct DECIMAL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## Summary

**Current Implementation**: OHLCV candles only (60 symbols × 7 timeframes)

**Next Steps for AI**:
1. Add dividends & splits (data quality)
2. Add news & sentiment (ML features)
3. Add earnings (event detection)

**Expected Impact**: 3-5x more ML signal richness, dramatically better backtesting accuracy
