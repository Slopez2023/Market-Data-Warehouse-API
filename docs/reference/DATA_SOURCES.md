# Data Sources Reference

Complete reference of all data sources and what data is available from each.

---

## Polygon.io - Primary Data Source

**Status**: ✅ Integrated  
**Rate Limit**: 150 requests/minute  
**Documentation**: https://polygon.io/docs

### Currently Implemented

#### 1. OHLCV Candles (Fully Backfilled)
- **Endpoint**: `GET /v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from}/{to}`
- **Data**: Open, High, Low, Close, Volume, Count
- **Timeframes**: 5m, 15m, 30m, 1h, 4h, 1d, 1w
- **Assets**: Stocks, Crypto, ETFs, Forex
- **Coverage**: 60 symbols (20 stocks, 20 crypto, 20 ETFs)
- **Backfill Status**: ✅ Complete

**Sample Response**:
```json
{
  "results": [
    {
      "t": 1632960000000,
      "o": 143.75,
      "h": 144.89,
      "l": 142.51,
      "c": 144.10,
      "v": 45678900,
      "n": 123456
    }
  ]
}
```

---

### Not Yet Implemented

#### 2. Dividends
- **Endpoint**: `GET /v2/reference/dividends`
- **Data**: Dividend amount, ex-date, pay-date, record-date, type
- **Coverage**: Stocks only
- **Use Case**: Price adjustment, income strategies
- **Status**: ❌ Not backfilled

**Available Fields**:
```json
{
  "ticker": "AAPL",
  "ex_dividend_date": "2023-05-12",
  "pay_date": "2023-05-25",
  "record_date": "2023-05-15",
  "dividend_amount": 0.24,
  "dividend_type": "cd"
}
```

---

#### 3. Stock Splits
- **Endpoint**: `GET /v2/reference/splits`
- **Data**: Split ratio, execution date
- **Coverage**: Stocks only
- **Use Case**: Price history normalization
- **Status**: ❌ Not backfilled

**Available Fields**:
```json
{
  "ticker": "AAPL",
  "execution_date": "2020-08-31",
  "split_from": 1,
  "split_to": 4
}
```

---

#### 4. News Articles
- **Endpoint**: `GET /v2/reference/news`
- **Data**: Title, description, URL, author, published date, image
- **Coverage**: Stocks, ETFs, Crypto
- **Use Case**: Sentiment analysis, event detection
- **Status**: ❌ Not backfilled

**Available Fields**:
```json
{
  "title": "Apple Reports Strong Q3 Earnings",
  "description": "...",
  "published_utc": "2023-08-04T18:30:00Z",
  "author": "John Doe",
  "image_url": "https://...",
  "article_url": "https://..."
}
```

---

#### 5. Earnings Announcements
- **Endpoint**: `GET /v1/reference/financials`
- **Data**: Earnings date, estimated/actual EPS, surprise %
- **Frequency**: Quarterly per company
- **Coverage**: Stocks only
- **Use Case**: Event-driven strategies, volatility prediction
- **Status**: ❌ Not backfilled

**Available Fields**:
```json
{
  "ticker": "AAPL",
  "filing_date": "2023-10-27",
  "period_of_report_date": "2023-09-30",
  "eps": 1.46,
  "revenue": 81796000000
}
```

---

#### 6. Analyst Ratings
- **Endpoint**: Benzinga API (via Polygon partnership)
- **Data**: Rating, target price, recommendation changes
- **Coverage**: Major stocks only
- **Use Case**: Consensus signals, contrarian indicators
- **Status**: ❌ Not backfilled

---

#### 7. Ticker Details (Reference Data)
- **Endpoint**: `GET /v3/reference/tickers/{ticker}`
- **Data**: Company name, description, market cap, sector, exchange, logos
- **Coverage**: All symbols
- **Use Case**: Fundamental context, sector analysis
- **Status**: ❌ Not backfilled

**Available Fields**:
```json
{
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "market_cap": 2800000000000,
  "employees": 164000,
  "homepage_url": "https://www.apple.com",
  "industry": "Computer Hardware",
  "sector": "Technology",
  "exchange": "XNAS"
}
```

---

#### 8. Options Chain & Implied Volatility
- **Endpoint**: `GET /v3/snapshot/options/chains/{underlying}`
- **Data**: Strike price, expiration, bid/ask, IV, Greeks (Delta, Gamma, Vega, Theta, Rho)
- **Coverage**: Stocks only
- **Use Case**: Volatility regime, probability-weighted targets
- **Status**: ❌ Not backfilled (real-time focus)

**Available Fields**:
```json
{
  "ticker": "AAPL",
  "contracts": [
    {
      "contract_type": "call",
      "expiration_date": "2023-09-15",
      "strike_price": 150.00,
      "bid": 5.25,
      "ask": 5.35,
      "implied_volatility": 0.245,
      "delta": 0.65,
      "gamma": 0.012,
      "vega": 0.089,
      "theta": -0.045,
      "rho": 0.023
    }
  ]
}
```

---

#### 9. Market Status & Hours
- **Endpoint**: `GET /v1/market/status` | `GET /v3/reference/market-holidays`
- **Data**: Market open/close status, holiday dates, early closes
- **Use Case**: Prevent trading on holidays, adjust analysis
- **Status**: ❌ Not implemented

---

#### 10. Forex Data
- **Endpoint**: `GET /v2/aggs/ticker/{symbol}/range/...`
- **Data**: OHLCV for currency pairs (EUR/USD, GBP/USD, etc.)
- **Coverage**: Major pairs available
- **Status**: ❌ Not backfilled (API ready)

---

## Data Quality & Coverage Summary

| Data Type | Status | Coverage | Backfilled | Priority |
|-----------|--------|----------|------------|----------|
| OHLCV Candles | ✅ | 60 symbols × 7 TF | Yes | P0 |
| Dividends | ❌ | Stocks | No | P1 |
| Stock Splits | ❌ | Stocks | No | P1 |
| News + Sentiment | ❌ | Stocks/ETFs/Crypto | No | P1 |
| Earnings | ❌ | Stocks | No | P2 |
| Analyst Ratings | ❌ | Major stocks | No | P2 |
| Ticker Details | ❌ | All | No | P2 |
| Options/IV | ❌ | Stocks | No | P3 |
| Market Status | ❌ | Global | No | P3 |
| Forex OHLCV | ❌ | Majors | No | P4 |

---

## Asset Class Coverage

### US Stocks (20 symbols)
**Full Name** → **Ticker**
- Apple Inc. → AAPL
- Microsoft Corporation → MSFT
- Alphabet Inc. → GOOGL
- Amazon.com Inc. → AMZN
- Meta Platforms Inc. → META
- NVIDIA Corporation → NVDA
- Tesla Inc. → TSLA
- Advanced Micro Devices → AMD
- Netflix Inc. → NFLX
- Berkshire Hathaway → BRK.B
- JPMorgan Chase → JPM
- Visa Inc. → V
- Exxon Mobil → XOM
- Procter & Gamble → PG
- The Coca-Cola Company → KO
- PepsiCo Inc. → PEP
- Costco Wholesale → COST
- Intel Corporation → INTC
- The Boeing Company → BA
- The Walt Disney Company → DIS

**Data Available**:
- ✅ OHLCV (all 7 timeframes)
- ❌ Dividends
- ❌ Stock Splits
- ❌ News
- ❌ Earnings
- ❌ Options/IV

---

### Cryptocurrencies (20 symbols)
**Full Name** → **Ticker**
- Bitcoin → BTC-USD
- Ethereum → ETH-USD
- Binance Coin → BNB-USD
- Solana → SOL-USD
- XRP → XRP-USD
- Cardano → ADA-USD
- Avalanche → AVAX-USD
- Polkadot → DOT-USD
- Polygon → MATIC-USD
- Cosmos → ATOM-USD
- Dogecoin → DOGE-USD
- Shiba Inu → SHIB-USD
- Chainlink → LINK-USD
- Aave → AAVE-USD
- Uniswap → UNI-USD
- Optimism → OP-USD
- Arbitrum → ARB-USD
- Injective → INJ-USD
- Litecoin → LTC-USD
- NEAR Protocol → NEAR-USD

**Data Available**:
- ✅ OHLCV (daily & weekly only from Polygon)
- ❌ Intraday OHLCV (5m-4h not available from Polygon)
- ❌ News/Sentiment
- ❌ Earnings (N/A)
- ❌ Dividends (N/A)

---

### ETFs (20 symbols)
**Full Name** → **Ticker**
- SPDR S&P 500 ETF Trust → SPY
- Invesco QQQ Trust → QQQ
- SPDR Dow Jones Industrial Average ETF → DIA
- iShares Russell 2000 ETF → IWM
- iShares Volatility ETF → VIX
- iShares 20+ Year Treasury Bond ETF → TLT
- Technology Select Sector SPDR → XLK
- Financial Select Sector SPDR → XLF
- iShares MSCI Emerging Markets ETF → EEM
- ARK Innovation ETF → ARKK
- SPDR Gold Shares → GLD
- iShares Silver Trust → SLV
- Energy Select Sector SPDR → XLE
- Health Care Select Sector SPDR → XLV
- Industrial Select Sector SPDR → XLI
- Consumer Staples Select Sector SPDR → XLP
- Consumer Discretionary Select Sector SPDR → XLY
- Real Estate Select Sector SPDR → XLRE
- Utilities Select Sector SPDR → XLU
- Schwab U.S. Broad Market ETF → SCHB

**Data Available**:
- ✅ OHLCV (all 7 timeframes)
- ❌ Dividends
- ❌ News
- ❌ Components/Rebalancing

---

## API Integration Clients

### PolygonClient (`src/clients/polygon_client.py`)

Main async client for Polygon.io API:

**Implemented Methods**:
```python
# OHLCV Data
async def fetch_range(
    symbol: str,
    timeframe: str,        # 5m, 15m, 30m, 1h, 4h, 1d, 1w
    start: str,            # YYYY-MM-DD
    end: str,
    is_crypto: bool = False,
    adjusted: bool = False
) -> List[Dict]

async def fetch_daily_range(
    symbol: str,
    start: str,
    end: str
) -> List[Dict]

async def fetch_crypto_daily_range(
    symbol: str,
    start: str,
    end: str
) -> List[Dict]

# Reference Data
async def fetch_ticker_details(symbol: str) -> Optional[Dict]
async def fetch_news(symbol: str, start: str, end: str) -> List[Dict]
async def fetch_earnings(symbol: str, start: str, end: str) -> List[Dict]
async def fetch_dividends(symbol: str, start: str, end: str) -> List[Dict]
async def fetch_stock_splits(symbol: str, start: str, end: str) -> List[Dict]

# Options
async def fetch_options_chain(symbol: str, date: datetime) -> Optional[Dict]
```

**Features**:
- Automatic retry with exponential backoff (3 attempts)
- Rate limit handling (429 errors)
- Crypto symbol normalization (BTC-USD → BTC)
- Response validation and error handling
- Async/await implementation
- Timeout: 30 seconds per request

---

## Backfill Scripts

### Current Backfill Scripts

1. **`scripts/backfill_ohlcv.py`**
   - Backfills OHLCV data for all symbols
   - Supports multiple timeframes
   - Configurable date ranges
   - Runs daily via scheduler

2. **`scripts/backfill_dividends.py`** (Not hooked up)
   - Fetches historical dividends
   - Uses Polygon `fetch_dividends()` method
   - Stores in database

3. **`scripts/backfill_splits.py`** (Not hooked up)
   - Fetches historical stock splits
   - Uses Polygon `fetch_stock_splits()` method
   - Stores in database

4. **`scripts/backfill_earnings.py`** (Not hooked up)
   - Fetches earnings data via Polygon financials endpoint
   - Calculates EPS surprises
   - Tracks fiscal year/quarter

5. **`scripts/backfill_news.py`** (Not hooked up)
   - Fetches news articles
   - Applies sentiment analysis
   - Stores with metadata

6. **`scripts/backfill_options_iv.py`** (Not hooked up)
   - Fetches options chain snapshots
   - Extracts IV and Greeks
   - Stores for analysis

---

## Scheduled Backfill (`src/scheduler.py`)

**AutoBackfillScheduler** runs daily OHLCV backfill:

```python
class AutoBackfillScheduler:
    async def auto_backfill_ohlcv(self):
        """
        Daily scheduled job that:
        1. Loads all active symbols from database
        2. Fetches OHLCV data for configured timeframes
        3. Validates data quality
        4. Inserts into database
        5. Handles errors with exponential backoff
        """
```

**Configuration**:
```env
BACKFILL_SCHEDULE_HOUR=0      # Run at 00:00 UTC
BACKFILL_SCHEDULE_MINUTE=0
```

---

## Data Validation

### Validation Service (`src/services/validation_service.py`)

Applied to all OHLCV data:

- **Price Range**: Open/High/Low/Close within 50% of previous close
- **Volume Anomalies**: Detects unusual volume spikes
- **Price Gaps**: Identifies trading gaps > 5%
- **Data Completeness**: Ensures all OHLCV fields present
- **Quality Scoring**: 0.0 (invalid) to 1.0 (perfect)

**Example Validation Response**:
```json
{
  "is_valid": true,
  "quality_score": 0.95,
  "validation_issues": [],
  "data_points": 1000
}
```

---

## Recommended Implementation Priority

### Phase 1 (Data Quality - Essential)
1. **Dividends backfill** - Adjust OHLCV for accurate analysis
2. **Stock Splits backfill** - Normalize price history
3. **News + Sentiment** - Strong ML signals

### Phase 2 (Advanced Analytics)
1. **Earnings data** - Event-driven strategies
2. **Analyst ratings** - Consensus signals
3. **Ticker fundamentals** - Sector analysis

### Phase 3 (Nice to Have)
1. **Options IV** - Volatility regime
2. **Market holidays** - Clean backtesting
3. **Forex OHLCV** - Currency trading

### Phase 4 (Low Priority)
1. **Detailed financials** - Hedge fund level
2. **Options Greeks** - Advanced volatility
3. **Futures data** - Separate infrastructure

---

## Next Steps

To implement additional data sources:

1. Add method to `PolygonClient` (if Polygon data)
2. Create backfill script in `scripts/`
3. Add database table/schema in `database/sql/`
4. Create service layer in `src/services/`
5. Add API endpoints in `src/routes/`
6. Write tests
7. Update documentation

---

**Status**: Production Ready (OHLCV only) ✅  
**Last Updated**: November 13, 2025  
**Next Review**: When implementing Phase 1 backfills
