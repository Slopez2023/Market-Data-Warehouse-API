# Backfill V2 - Comprehensive Market Data Reference

Backfill V2 extends the original backfill script to include all available market data from Polygon.io and derived features.

## Overview

**Backfill V1** (backfill.py):
- OHLCV candles
- Validation metadata (quality scores, anomaly detection)

**Backfill V2** (backfill_v2.py):
- ✅ OHLCV candles
- ✅ News articles with sentiment analysis
- ✅ Earnings announcements and estimates
- ✅ Dividend records
- ✅ Stock splits
- ✅ Options IV and chain snapshots
- ✅ Adjusted OHLCV (split/dividend adjusted)

---

## Quick Start

### Full Database Population (All Assets, All Data)

```bash
# Run complete backfill for all active symbols
python scripts/backfill_v2.py

# With custom timeframe
python scripts/backfill_v2.py --timeframe 1h

# With custom date range (3 years instead of 5)
python scripts/backfill_v2.py --start 2022-01-01 --end 2025-01-01
```

### Selective Backfill

```bash
# Skip certain data types to speed up backfill
python scripts/backfill_v2.py --skip-options --skip-news

# Backfill only OHLCV and dividends
python scripts/backfill_v2.py --skip-news --skip-earnings --skip-options --skip-adjusted

# Specific symbols only
python scripts/backfill_v2.py --symbols AAPL,MSFT,GOOGL
```

---

## Data Types & Coverage

### 1. OHLCV Candles
**Description:** Open, High, Low, Close, Volume price data
**Timeframes:** 5m, 15m, 30m, 1h, 4h, 1d, 1w
**Coverage:** 5 years of historical data (configurable)
**Database Table:** `market_data`

```bash
python scripts/backfill_v2.py --skip-news --skip-earnings --skip-dividends --skip-splits --skip-options --skip-adjusted
```

### 2. News & Sentiment
**Description:** News articles with AI sentiment analysis (positive/negative/neutral)
**Coverage:** News from past 5 years for each symbol
**Database Table:** `news`
**Fields:** title, description, sentiment_score, sentiment_label, sentiment_confidence

```bash
python scripts/backfill_v2.py --skip-ohlcv --skip-earnings --skip-dividends --skip-splits --skip-options --skip-adjusted
```

### 3. Earnings
**Description:** Earnings announcements with estimates and actuals
**Coverage:** All historical earnings announcements
**Database Table:** `earnings`
**Fields:** earnings_date, estimated_eps, actual_eps, surprise_eps, surprise_pct

```bash
python scripts/backfill_v2.py --skip-ohlcv --skip-news --skip-dividends --skip-splits --skip-options --skip-adjusted
```

### 4. Dividends
**Description:** Dividend payment records
**Coverage:** All historical dividends
**Database Table:** `dividends`
**Fields:** ex_date, record_date, pay_date, dividend_amount, dividend_type

```bash
python scripts/backfill_v2.py --skip-ohlcv --skip-news --skip-earnings --skip-splits --skip-options --skip-adjusted
```

### 5. Stock Splits
**Description:** Historical stock split events
**Coverage:** All historical stock splits
**Database Table:** `stock_splits`
**Fields:** execution_date, split_from, split_to, split_ratio

```bash
python scripts/backfill_v2.py --skip-ohlcv --skip-news --skip-earnings --skip-dividends --skip-options --skip-adjusted
```

### 6. Options IV & Chain Data
**Description:** Options chain snapshot with implied volatility metrics
**Coverage:** Current snapshot (Polygon doesn't provide historical options chains)
**Database Tables:** `options_iv`, `options_chain_snapshot`
**Fields:** strike, expiration, iv (implied volatility), delta, gamma, vega, theta, rho

```bash
python scripts/backfill_v2.py --skip-ohlcv --skip-news --skip-earnings --skip-dividends --skip-splits --skip-adjusted
```

### 7. Adjusted OHLCV
**Description:** OHLCV prices adjusted for stock splits and dividends
**Coverage:** 5 years of adjusted price history
**Database Table:** `ohlcv_adjusted`
**Note:** Provides price continuity across corporate actions

```bash
python scripts/backfill_v2.py --skip-ohlcv --skip-news --skip-earnings --skip-dividends --skip-splits --skip-options
```

---

## Advanced Usage

### Backfill Specific Symbols with All Data

```bash
# AAPL, MSFT, GOOGL with all 7 timeframes and all data types
python scripts/backfill_v2.py --symbols AAPL,MSFT,GOOGL --timeframe 1d
python scripts/backfill_v2.py --symbols AAPL,MSFT,GOOGL --timeframe 1h
python scripts/backfill_v2.py --symbols AAPL,MSFT,GOOGL --timeframe 4h
```

### Backfill with Progress Tracking

```bash
# Run in background and capture logs
nohup python scripts/backfill_v2.py --start 2023-01-01 > backfill_$(date +%Y%m%d_%H%M%S).log 2>&1 &
```

### Backfill Specific Date Range

```bash
# Last 2 years only
python scripts/backfill_v2.py --start 2023-01-01 --end 2025-01-01

# Single year
python scripts/backfill_v2.py --start 2024-01-01 --end 2024-12-31
```

---

## Command-Line Options

```
usage: backfill_v2.py [-h] [--symbols SYMBOLS] [--start START] [--end END] 
                      [--timeframe TIMEFRAME] [--skip-ohlcv] [--skip-news] 
                      [--skip-dividends] [--skip-splits] [--skip-earnings] 
                      [--skip-options] [--skip-adjusted]

Comprehensive backfill for all market data

optional arguments:
  -h, --help              show this help message and exit
  --symbols SYMBOLS       Comma-separated symbols (e.g., AAPL,MSFT)
                         If omitted, backfills all active symbols
  
  --start START          Start date (YYYY-MM-DD)
                         Default: ~5 years ago
  
  --end END              End date (YYYY-MM-DD)
                         Default: today (UTC)
  
  --timeframe TIMEFRAME   Timeframe: 5m, 15m, 30m, 1h, 4h, 1d (default), 1w
  
  --skip-ohlcv           Skip OHLCV backfill
  --skip-news            Skip news/sentiment backfill
  --skip-dividends       Skip dividend backfill
  --skip-splits          Skip stock split backfill
  --skip-earnings        Skip earnings backfill
  --skip-options         Skip options IV backfill
  --skip-adjusted        Skip adjusted OHLCV backfill
```

---

## Database Statistics

After complete backfill of ~3500 symbols with all data types:

```
Database Status:
  Symbols: ~3500+
  OHLCV Records: ~50M+ (varies by timeframes)
  News Articles: ~100K+ (with sentiment)
  Earnings Records: ~50K+
  Dividend Records: ~200K+
  Stock Splits: ~5K+
  Options Snapshots: ~3500+ (one per symbol)
  Adjusted OHLCV: ~50M+ (mirroring OHLCV)
```

**Total Database Size:** 10-15 GB (across all data types)

---

## Environment Variables

Required:
```env
POLYGON_API_KEY=pk_xxx...         # Polygon.io API key
DATABASE_URL=postgresql://...      # Database connection string
```

Optional:
```env
DB_PASSWORD=yourpassword
DB_HOST=localhost
DB_PORT=5432
```

---

## Performance & Timing

**Estimated Backfill Times:**

| Data Type | Time (50 symbols) | Time (3500 symbols) |
|-----------|-------------------|-------------------|
| OHLCV (1d) | 5-10 min | 6-12 hours |
| News/Sentiment | 10-20 min | 12-24 hours |
| Earnings | 2-5 min | 1-2 hours |
| Dividends | 2-5 min | 1-2 hours |
| Stock Splits | 1-2 min | 30 min |
| Options IV | 5-10 min | 1-2 hours |
| Adjusted OHLCV | 5-10 min | 6-12 hours |
| **Total (All Data)** | **30-60 min** | **2-4 days** |

---

## Common Usage Patterns

### Scenario 1: Initial Full Database Population
```bash
# Populate all symbols with all data (from database)
python scripts/backfill_v2.py

# Or specific symbols
python scripts/backfill_v2.py --symbols AAPL,MSFT,GOOGL,AMZN,TSLA
```

### Scenario 2: Add Intraday Data to Existing Database
```bash
# Add 1-hour candles for all symbols
python scripts/backfill_v2.py --timeframe 1h --skip-news --skip-earnings --skip-dividends --skip-splits --skip-options

# Add 15-minute candles
python scripts/backfill_v2.py --timeframe 15m --skip-news --skip-earnings --skip-dividends --skip-splits --skip-options
```

### Scenario 3: Update News & Sentiment Only
```bash
python scripts/backfill_v2.py --skip-ohlcv --skip-earnings --skip-dividends --skip-splits --skip-options --skip-adjusted
```

### Scenario 4: Minimal Backfill (Quick Setup)
```bash
# Just OHLCV and dividends for fastest setup
python scripts/backfill_v2.py --skip-news --skip-earnings --skip-splits --skip-options --skip-adjusted
```

---

## Troubleshooting

### Issue: "POLYGON_API_KEY not set"
```bash
export POLYGON_API_KEY=pk_your_key_here
python scripts/backfill_v2.py
```

### Issue: Database connection failed
```bash
# Ensure Docker containers are running
docker-compose ps

# Check DATABASE_URL in .env
echo $DATABASE_URL
```

### Issue: Rate limiting (429 errors)
- Polygon.io has 150 requests/minute limit on free tier
- Backfill V2 handles retries automatically
- Increase delay between requests by running fewer symbols at once:
```bash
python scripts/backfill_v2.py --symbols AAPL,MSFT
```

### Issue: Out of memory during large backfill
```bash
# Run in smaller batches
python scripts/backfill_v2.py --symbols AAPL,MSFT,GOOGL
python scripts/backfill_v2.py --symbols AMZN,TSLA,META
```

---

## Comparison: Backfill V1 vs V2

| Feature | V1 | V2 |
|---------|----|----|
| OHLCV | ✅ | ✅ |
| Timeframes | ✅ | ✅ |
| Validation Metadata | ✅ | ✅ |
| News/Sentiment | ❌ | ✅ |
| Earnings | ❌ | ✅ |
| Dividends | ❌ | ✅ |
| Stock Splits | ❌ | ✅ |
| Options IV | ❌ | ✅ |
| Adjusted OHLCV | ❌ | ✅ |
| Selective Data Skip | ❌ | ✅ |
| Progress Reporting | Basic | Detailed |

---

## Related Commands

```bash
# Initialize symbols database
python scripts/init_symbols.py

# Check API status and database metrics
curl http://localhost:8000/api/v1/status | python -m json.tool

# Query historical data
curl "http://localhost:8000/api/v1/historical/AAPL?timeframe=1d&start=2024-01-01" | python -m json.tool
```

---

## Support & Documentation

- **Polygon.io API Docs:** https://polygon.io/docs/stocks
- **API Documentation:** http://localhost:8000/docs
- **Dashboard:** http://localhost:3001
- **Health Check:** http://localhost:8000/health
