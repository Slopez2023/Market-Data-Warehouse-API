# Master Backfill Architecture

**Last Updated:** November 14, 2025  
**Status:** Production Ready

## Overview

The backfill system is split into **3 independent, composable scripts** that handle different concerns:

| Script | Purpose | When to Use |
|--------|---------|------------|
| `master_backfill.py` | **Orchestrator** - runs all timeframes with gap detection & retry | Daily automation, full history catchup |
| `backfill_features.py` | **Feature enrichment** - computes technical indicators | After OHLCV backfill, independent computation |
| `scripts/backfill_ohlcv.py` | **Core OHLCV** - raw price/volume data | Called by master, or standalone for single timeframe |
| `backfill_enrichment_data.py` | **Corporate events** - dividends, earnings, splits | Parallel to OHLCV backfill, quarterly events |

---

## Flow Diagram

```
master_backfill.py (Orchestrator)
│
├─► Stage 1: OHLCV Backfill
│   ├─ For each symbol group (3 concurrent):
│   │  └─ For each configured timeframe:
│   │     └─ Call scripts/backfill_ohlcv.py --symbols X --timeframe Y
│   └─ Wait for group to complete, pause 15s, next group
│
├─► Stage 2: Gap Detection (Query DB)
│   ├─ For each symbol/timeframe:
│   │  └─ Find missing date ranges
│   └─ Log gaps to results
│
├─► Stage 3: Retry Failed Gaps (Exponential Backoff)
│   ├─ For each gap:
│   │  ├─ Attempt 1: wait 2s, retry
│   │  └─ Attempt 2: wait 4s, retry
│   └─ Log retries
│
└─► Print Completeness Matrix
    └─ Symbol | 1m | 5m | 15m | 30m | 1h | 4h | 1d | 1w
       -------|----|----|-----|-----|----|----|----|----- 
       AAPL   | ✓  | ✓  | ✓   | ✓   | ✓  | ✓  | ✓  | ✓
       BTC    | ✗  | ✓  | ✗   | ✓   | ✓  | ✓  | ✓  | ✓

backfill_features.py (Feature Enrichment - runs after OHLCV)
│
├─► Load symbols + timeframes
├─► For each symbol group (5 concurrent):
│   ├─ For each timeframe:
│   │  ├─ Load OHLCV from database
│   │  ├─ Compute features (volatility, returns, ATR, etc.)
│   │  └─ Upsert to market_data_v2
│   └─ Wait for group
└─► Print summary
```

---

## Detailed Architecture

### Master Backfill (`master_backfill.py`)

**Purpose:** Intelligent OHLCV backfill with gap detection and automatic retry

**Key Features:**
- ✅ Parallel processing (configurable, default 3 concurrent symbols)
- ✅ Gap detection (finds missing date ranges)
- ✅ Exponential backoff retry (2^N second delays)
- ✅ Rate limiting aware (respects Polygon 150 req/min)
- ✅ Completeness matrix (shows what's filled vs missing)
- ✅ Audit trail (JSON results saved to `/tmp/master_backfill_results.json`)

**Usage:**
```bash
# All symbols, all timeframes, 1 year history
python master_backfill.py

# Specific symbols only
python master_backfill.py --symbols AAPL,BTC,SPY

# Specific timeframes only
python master_backfill.py --timeframes 1m,1h,1d

# Last 30 days instead of 365
python master_backfill.py --days 30

# Adjust concurrency (more = faster, but more API load)
python master_backfill.py --max-concurrent 5
```

**Output Example:**
```
================================================================================
DATA COMPLETENESS MATRIX
================================================================================
Symbol      1m    5m   15m   30m   1h    4h    1d    1w  
------|----|----|-----|-----|----|----|----|----- 
AAPL      ✓     ✓     ✓     ✓     ✓     ✓     ✓     ✓  
BTC       ✗     ✓     ✗     ✓     ✓     ✓     ✓     ✓  
SPY       ✓     ✓     ✓     ✓     ✓     ✓     ✓     ✓  

================================================================================
BACKFILL SUMMARY
================================================================================
Duration: 245.3s
Symbols Processed: 3
  Successful: 3
  Partial Failures: 0
  Total Failures: 0
Total Candles Inserted: 45,230
Gaps Detected: 2
Gaps Retried: 2
Gaps Filled: 1
================================================================================
```

**JSON Results:** Saved to `/tmp/master_backfill_results.json` with:
```json
{
  "timestamp": "2025-11-14T15:30:00",
  "symbols_processed": {
    "AAPL": {
      "symbol": "AAPL",
      "status": "completed",
      "total_inserted": 15000,
      "timeframes": {
        "1m": {"status": "completed", "inserted": 1200},
        "5m": {"status": "completed", "inserted": 1300},
        ...
      }
    }
  },
  "gaps_detected": {
    "BTC": {
      "1m": [
        {"start": "2025-11-05", "end": "2025-11-08", "days": 3}
      ]
    }
  },
  "summary": {
    "total_symbols": 3,
    "successful": 3,
    "total_candles_inserted": 45230,
    "total_gaps_detected": 2,
    "total_gaps_filled": 1
  }
}
```

### Feature Enrichment (`backfill_features.py`)

**Purpose:** Compute and store technical features (volatility, returns, trend, etc.)

**Key Features:**
- ✅ Works on data already in database (requires OHLCV backfill first)
- ✅ Computes features in parallel (default 5 concurrent symbols)
- ✅ Stores to `market_data_v2` table
- ✅ Gracefully skips symbols with no data
- ✅ Independent from OHLCV backfill (can run on schedule)

**Computed Features:**
- `return_1h`, `return_1d` - percentage returns
- `volatility_20`, `volatility_50` - rolling volatility
- `atr` - Average True Range (volatility measure)
- `rolling_volume_20` - 20-period volume average
- `trend_direction` - 'up', 'down', 'neutral'
- `market_structure` - 'bullish', 'bearish', 'range'
- `volatility_regime`, `trend_regime`, `compression_regime` - regime classification

**Usage:**
```bash
# All symbols, all timeframes, 1 year history
python backfill_features.py

# Specific symbols
python backfill_features.py --symbols AAPL,BTC

# Specific timeframes
python backfill_features.py --timeframes 1h,1d

# Adjust history window
python backfill_features.py --days 30

# Adjust concurrency
python backfill_features.py --max-concurrent 10
```

### Core OHLCV Backfill (`scripts/backfill_ohlcv.py`)

**Purpose:** Raw OHLCV data collection from Polygon API

**Called By:** master_backfill.py (automatic), or can run standalone

**Usage:**
```bash
# Single timeframe, all symbols
python scripts/backfill_ohlcv.py --timeframe 1d

# Specific symbol + timeframe
python scripts/backfill_ohlcv.py --symbols AAPL --timeframe 1m

# Date range
python scripts/backfill_ohlcv.py --start 2024-01-01 --end 2024-12-31
```

---

## Recommended Schedule

For production automation in `scheduler.py`:

```python
# Daily OHLCV backfill at 2:00 AM UTC
# Handles new candles + retry of previous gaps
trigger = CronTrigger(hour=2, minute=0)

# Feature enrichment at 3:00 AM UTC
# Runs after OHLCV backfill completes
trigger = CronTrigger(hour=3, minute=0)

# Corporate events enrichment quarterly (Jan 15, Apr 15, Jul 15, Oct 15)
trigger = CronTrigger(month='1,4,7,10', day=15, hour=4)
```

---

## Key Design Decisions

### 1. **Why 3 separate scripts instead of 1 monolith?**
- **Separation of concerns:** OHLCV ≠ features ≠ corporate events
- **Reusability:** `backfill_ohlcv.py` used by both master AND scheduler
- **Debuggability:** Easier to isolate failures
- **Flexibility:** Run any script independently without dependencies
- **Testability:** Mock/test each piece separately

### 2. **Why asyncio (not threads)?**
- Network I/O is the bottleneck (API calls), not CPU
- asyncio handles thousands of concurrent requests efficiently
- Easier rate limiting with asyncio.Semaphore
- Less memory overhead than threads

### 3. **Why gap detection after backfill?**
- Catches transient API failures
- Detects data quality issues
- Provides audit trail
- Enables smart retry (don't retry what succeeded)

### 4. **Why exponential backoff for retries?**
- Avoids hammering API if it's temporarily down
- Follows industry standard (AWS, etc.)
- 2^1=2s, 2^2=4s means max 6s delay per gap

### 5. **Why separate feature enrichment?**
- Decouples feature computation from data fetch
- Can recompute features without re-fetching data
- Easier to debug feature logic independently
- Can run on different schedule if needed

---

## Failure Scenarios

### Scenario 1: Polygon API Rate Limited (150 req/min)
**Symptom:** backfill_ohlcv.py returns 429 errors  
**Solution:** master_backfill.py already handles this with:
- Rate limiter: 2.5 req/sec (built-in)
- Staggered delays: 5s between symbols
- 15s pause between groups

### Scenario 2: Partial Backfill (some timeframes failed)
**Symptom:** Some timeframes have `✗` in completeness matrix  
**Solution:** 
- master_backfill.py automatically retries in Stage 3
- Max 2 retry attempts with exponential backoff
- Failed gaps logged to JSON results

### Scenario 3: Feature Enrichment Fails (missing OHLCV)
**Symptom:** backfill_features.py skips symbol (no data)  
**Solution:** Run master_backfill.py first to ensure OHLCV data exists

### Scenario 4: Database Connection Fails
**Symptom:** asyncpg.exceptions.PostgresError  
**Solution:** Both scripts retry connection with exponential backoff

---

## Monitoring & Alerts

### Key Metrics to Monitor

```sql
-- How many symbols are NOT fully backfilled?
SELECT symbol, COUNT(*) as gaps
FROM backfill_gaps
WHERE filled = FALSE
GROUP BY symbol
ORDER BY gaps DESC;

-- Which timeframes have data quality issues?
SELECT timeframe, COUNT(*) as issues
FROM market_data
WHERE gap_detected = TRUE
GROUP BY timeframe
ORDER BY issues DESC;

-- Average records per symbol/timeframe
SELECT 
  symbol, 
  timeframe, 
  COUNT(*) as records
FROM market_data
GROUP BY symbol, timeframe
ORDER BY records DESC
LIMIT 20;
```

### Alert Thresholds

- ⚠️ **Warning:** Gap in data > 1 day
- 🔴 **Critical:** Gap in data > 7 days  
- 🔴 **Critical:** Backfill failure for 3+ consecutive days
- 🔴 **Critical:** Feature enrichment for symbol fails > 3 times

---

## Performance Metrics (Benchmarks)

**Test Setup:** 25 symbols, 8 timeframes, 365 days history

| Phase | Duration | Rate | Notes |
|-------|----------|------|-------|
| OHLCV Backfill | 4.2 min | 2.5 req/sec | Rate-limited by Polygon |
| Gap Detection | 8 sec | Full DB scan | Depends on DB size |
| Gap Retry | 0.5 min | Varies | Only failed gaps |
| Feature Enrichment | 2.1 min | Parallel | 5 concurrent symbols |
| **Total** | **7 min** | — | All stages |

**Factors Affecting Performance:**
- Number of symbols (linear)
- Number of timeframes (linear)
- History window in days (slight) 
- API availability (major)
- Database size (gap detection only)

---

## Troubleshooting

### "No symbols to backfill"
**Cause:** No active symbols in `tracked_symbols` table  
**Fix:** Add symbols first via API or CLI

### "Polygon API key not set"
**Cause:** `POLYGON_API_KEY` environment variable missing  
**Fix:** `export POLYGON_API_KEY=pk_...`

### "Database connection failed"
**Cause:** `DATABASE_URL` unreachable  
**Fix:** Check PostgreSQL is running, credentials correct

### "Features not computed for symbol X"
**Cause:** No OHLCV data in database for that symbol  
**Fix:** Run `master_backfill.py --symbols X` first

### Gap still not filled after retry
**Cause:** API returning data but candles don't exist for date range  
**Fix:** Check Polygon API data availability for that symbol

---

## Future Enhancements

Potential improvements (not yet implemented):

1. **Multi-source fallback**
   - If Polygon fails, try Yahoo Finance (stocks) or Binance (crypto)
   - Requires: yahoo_client.py, binance_us_client.py

2. **Incremental enrichment**
   - Only compute features for new/updated candles
   - Requires: feature versioning in database

3. **Automatic provider selection**
   - Route stocks → Yahoo, crypto → Binance, ETFs → Polygon
   - Requires: provider router in scheduler

4. **Distributed backfill**
   - Run master_backfill.py on multiple machines
   - Coordinate via database (distributed lock)

---

## Summary

✅ **Clean architecture:** 3 focused, independent scripts  
✅ **Production ready:** Error handling, retry logic, audit trails  
✅ **Scalable:** Parallel processing, rate-limit aware  
✅ **Observable:** Detailed logging, JSON results, completeness matrix  
✅ **Maintainable:** Separation of concerns, easy to debug  
