# Backfill Quick Start

## What Changed?

**Old:** Multiple redundant backfill scripts  
**New:** 3 clean, focused scripts + orchestrator

| Before | After |
|--------|-------|
| backfill_1m_data.py | ❌ Deleted (use backfill_ohlcv.py --timeframe 1m) |
| backfill_ohlcv.py | ✅ Kept (core OHLCV backfill) |
| scheduler.py (backfill) | ✅ Still works (unchanged) |
| **NEW:** master_backfill.py | ✅ Orchestrator with gap detection |
| **NEW:** backfill_features.py | ✅ Feature enrichment standalone |

---

## Quick Usage

### 1. Full Backfill (Recommended First Run)

```bash
python master_backfill.py
```

**What it does:**
- Backfills all 8 timeframes for all active symbols
- Detects gaps (missing candles)
- Retries failed gaps automatically
- Shows completeness matrix

**Output:** JSON results in `/tmp/master_backfill_results.json`

---

### 2. Backfill Specific Symbols

```bash
python master_backfill.py --symbols AAPL,BTC,SPY
```

**Result:** Only those 3 symbols, all timeframes

---

### 3. Backfill Specific Timeframes

```bash
python master_backfill.py --timeframes 1h,1d
```

**Result:** All symbols, but only 1h and 1d candles

---

### 4. Backfill Last 30 Days (Faster)

```bash
python master_backfill.py --days 30
```

**Result:** All symbols/timeframes, but only 30 days history

---

### 5. Then Compute Features

```bash
python backfill_features.py
```

**What it does:**
- Computes volatility, returns, trend, ATR, etc.
- Stores in market_data_v2 table
- Works on data already in database

---

### 6. Backfill Just One Symbol (Debug)

```bash
python scripts/backfill_ohlcv.py --symbols AAPL --timeframe 1d
```

**Result:** Single timeframe, single symbol (fastest for testing)

---

## Expected Output

### master_backfill.py

```
================================================================================
MASTER BACKFILL ORCHESTRATOR STARTED
================================================================================
Loaded 25 symbols

================================================================================
STAGE 1: BACKFILLING OHLCV DATA
================================================================================
Processing symbol group 1
  AAPL/1m: backfilling...
  AAPL/5m: backfilling...
  ...
Pausing 15s between groups for rate limiting...

================================================================================
STAGE 2: DETECTING GAPS
================================================================================
AAPL/1m: 0 gap(s) detected
BTC/1m: 2 gap(s) detected

================================================================================
STAGE 3: RETRYING FAILED GAPS
================================================================================
  BTC/1m: retrying gap 2025-11-05 to 2025-11-08 (attempt 1/2)...
  BTC/1m: ✓ gap filled (45 candles)

================================================================================
DATA COMPLETENESS MATRIX
================================================================================
Symbol      1m    5m   15m   30m   1h    4h    1d    1w  
------|----|----|-----|-----|----|----|----|----- 
AAPL      ✓     ✓     ✓     ✓     ✓     ✓     ✓     ✓  
BTC       ✓     ✓     ✓     ✓     ✓     ✓     ✓     ✓  
SPY       ✓     ✓     ✓     ✓     ✓     ✓     ✓     ✓  

================================================================================
BACKFILL SUMMARY
================================================================================
Duration: 245.3s
Symbols Processed: 3
  Successful: 3
Gaps Detected: 2
Gaps Filled: 1
Total Candles Inserted: 45,230
================================================================================
```

### backfill_features.py

```
================================================================================
FEATURE ENRICHMENT PIPELINE STARTED
================================================================================
Loaded 25 symbols
Date range: 2024-11-14 to 2025-11-14

Processing group 1 (5 symbols)
  AAPL/1m: computing features...
  AAPL/5m: computing features...
  ...
  AAPL/1m: ✓ processed=1200, inserted=0, updated=1200
  AAPL/5m: ✓ processed=1300, inserted=0, updated=1300
  ...

================================================================================
ENRICHMENT SUMMARY
================================================================================
Duration: 125.4s
Symbols Processed: 25
  Successful: 25
Total Records Processed: 302,400
Total Features Computed: 302,400
================================================================================
```

---

## Typical Workflow

```bash
# Monday morning: Full backfill + enrichment

# 1. Backfill OHLCV (5-10 minutes depending on symbols)
python master_backfill.py

# 2. Check results
cat /tmp/master_backfill_results.json | jq .summary

# 3. If gaps exist, see them in JSON
cat /tmp/master_backfill_results.json | jq .gaps_detected

# 4. Compute features on enriched data (2-3 minutes)
python backfill_features.py

# 5. Verify in database
psql $DATABASE_URL
> SELECT symbol, timeframe, COUNT(*) as records FROM market_data GROUP BY symbol, timeframe ORDER BY records DESC LIMIT 20;
```

---

## How Long Does It Take?

| Operation | Symbols | Timeframes | Duration | Notes |
|-----------|---------|-----------|----------|-------|
| master_backfill | 5 | 8 | ~1 min | Parallel, rate-limited |
| master_backfill | 25 | 8 | ~5 min | Typical production |
| master_backfill | 100 | 8 | ~20 min | Large dataset |
| backfill_features | 25 | 8 | ~2 min | Parallel, 5 concurrent |
| backfill_ohlcv (1 sym, 1 tf) | 1 | 1 | ~2 sec | Single test |

---

## Troubleshooting

### "Polygon API Rate Limited (429 errors)"
**Solution:** This should not happen. master_backfill.py enforces 2.5 req/sec automatically.  
**If it does:** Check that polygon_client.py rate limiter is working.

### "Gap detected but retry failed"
**Symptom:** Completeness matrix shows `✗` after backfill  
**Solution:** Check Polygon API has data for that symbol/date range.  
**Fallback:** Retry manually with explicit date range:
```bash
python scripts/backfill_ohlcv.py --symbols BTC --timeframe 1m --start 2025-11-05 --end 2025-11-08
```

### "No symbols to backfill"
**Cause:** No active symbols in database  
**Solution:** Add symbols first:
```bash
curl -X POST http://localhost:8000/api/v1/symbols \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"symbol": "AAPL", "asset_class": "stock"}'
```

### "Features computed = 0"
**Cause:** No OHLCV data in database  
**Solution:** Run master_backfill.py first

---

## Schedule This

Add to crontab or systemd timer:

```bash
# Daily 2 AM UTC: backfill
0 2 * * * cd /path/to/project && python master_backfill.py >> /var/log/backfill.log 2>&1

# Daily 3:30 AM UTC: enrich features
30 3 * * * cd /path/to/project && python backfill_features.py >> /var/log/enrich.log 2>&1
```

Or use `scheduler.py` (already integrated):
```python
self.scheduler.add_job(
    subprocess.run,
    args=([sys.executable, "master_backfill.py"],),
    trigger=CronTrigger(hour=2, minute=0),
    id="master_backfill"
)
```

---

## Key Points

✅ **master_backfill.py** = Daily OHLCV + gap detection  
✅ **backfill_features.py** = Feature enrichment (after OHLCV)  
✅ **scripts/backfill_ohlcv.py** = Core data fetch (standalone or called by master)  
✅ **backfill_enrichment_data.py** = Corporate events (dividends, earnings, splits)  

**Deleted:**
❌ **backfill_1m_data.py** → Use `--timeframe 1m` on backfill_ohlcv.py

---

## For More Details

See: [BACKFILL_ARCHITECTURE.md](./BACKFILL_ARCHITECTURE.md)
