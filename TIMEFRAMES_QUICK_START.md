# Timeframes Feature - Quick Start

## ✓ Status: Ready to Use

System verification complete. All components working.

## 5-Minute Setup

### 1. Verify System
```bash
python scripts/verify_timeframes_setup.py
```

### 2. Backfill Data
```bash
# Daily candles (all symbols, ~5 years)
python scripts/backfill_ohlcv.py --timeframe 1d

# Or specific symbols only
python scripts/backfill_ohlcv.py --symbols AAPL,MSFT,SPY --timeframe 1d

# Or intraday data
python scripts/backfill_ohlcv.py --timeframe 1h --start 2024-01-01 --end 2024-01-31
```

### 3. View Results

**Dashboard:**
```
http://localhost:8000/dashboard/
```
Look for the **Timeframes** column in the symbol table.

**API:**
```bash
curl http://localhost:8000/api/v1/symbols/detailed | jq
```

**Database:**
```bash
psql -c "SELECT symbol, timeframes FROM tracked_symbols WHERE active=TRUE LIMIT 5;"
```

## What Gets Updated Automatically

✓ `tracked_symbols.timeframes` - Array of backfilled timeframes  
✓ `market_data.timeframe` - Each candle records its timeframe  
✓ Dashboard display - Shows available timeframes per symbol  
✓ API response - Includes timeframes in `/api/v1/symbols/detailed`  

## Available Timeframes

| Timeframe | Use Case |
|-----------|----------|
| `5m` | Intraday scalping |
| `15m` | Short-term trading |
| `30m` | Swing trading |
| `1h` | Hourly analysis |
| `4h` | Intermediate |
| `1d` | Daily/long-term |
| `1w` | Weekly/trend |

## Examples

### Backfill Multiple Timeframes Same Symbol
```bash
# Daily first
python scripts/backfill_ohlcv.py --symbols AAPL --timeframe 1d

# Then add hourly (1 month)
python scripts/backfill_ohlcv.py --symbols AAPL --timeframe 1h \
  --start 2024-01-01 --end 2024-01-31
```

Result: `AAPL` will have `timeframes: ["1d", "1h"]`

### Check What's Backfilled
```bash
curl -s http://localhost:8000/api/v1/symbols/detailed | \
  jq '.symbols[] | {symbol, timeframes, records}'
```

### Database Direct Query
```bash
psql -c "
SELECT symbol, timeframes, COUNT(*) as record_count 
FROM tracked_symbols ts
LEFT JOIN market_data m ON ts.symbol = m.symbol
WHERE ts.active = TRUE
GROUP BY symbol, timeframes
ORDER BY symbol;"
```

## Schema Overview

### tracked_symbols table
```
symbol       | VARCHAR(20)
timeframes   | TEXT[] (e.g., ['1d', '1h', '4h'])
active       | BOOLEAN
last_backfill| TIMESTAMPTZ
```

### market_data table
```
symbol   | VARCHAR(20)
timeframe| VARCHAR(10) (e.g., '1d')
time     | TIMESTAMP
open, high, low, close, volume
validated, quality_score, ...
```

## Common Commands

**Full Daily Backfill (All Symbols)**
```bash
python scripts/backfill_ohlcv.py --timeframe 1d
```

**Specific Symbols + Timeframe + Date Range**
```bash
python scripts/backfill_ohlcv.py \
  --symbols AAPL,MSFT,GOOGL \
  --timeframe 1h \
  --start 2024-01-01 \
  --end 2024-01-31
```

**Recent Data Only (Last 30 Days)**
```bash
python scripts/backfill_ohlcv.py \
  --timeframe 4h \
  --start 2023-12-01 \
  --end 2024-01-31
```

**Check Status**
```bash
curl http://localhost:8000/api/v1/status | jq '.database'
```

## Monitoring

**Watch Backfill Progress**
```bash
tail -f api.log | grep -E "backfill|timeframe"
```

**Check Database Size**
```bash
curl http://localhost:8000/api/v1/metrics | jq '.database'
```

**View Dashboard Directly**
```bash
# HTML with embedded data
curl http://localhost:8000/dashboard/index.html
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No timeframes showing | Run backfill: `python scripts/backfill_ohlcv.py --timeframe 1d` |
| Backfill fails | Check `api.log` and verify `POLYGON_API_KEY` env var |
| Dashboard not loading | Restart API: `python main.py` |
| Slow queries | Run: `psql -c "ANALYZE tracked_symbols;"` |

## Architecture

```
Polygon API
    ↓
backfill_ohlcv.py
    ├→ Fetch candles (timeframe)
    ├→ Validate data
    ├→ INSERT market_data
    └→ UPDATE tracked_symbols.timeframes
    
API Server (main.py)
    └→ GET /api/v1/symbols/detailed
        └→ JOIN market_data + tracked_symbols
        
Dashboard (index.html)
    └→ Fetch /api/v1/symbols/detailed
    └→ Render table with timeframes column
```

## Next Steps

1. ✓ Run verification: `python scripts/verify_timeframes_setup.py`
2. ✓ Backfill data: `python scripts/backfill_ohlcv.py --timeframe 1d`
3. ✓ View dashboard: `http://localhost:8000/dashboard/`
4. ✓ Add more timeframes: `python scripts/backfill_ohlcv.py --timeframe 1h`
5. ✓ Schedule automatic backfills (see TIMEFRAMES_SETUP.md)

## Files Modified/Created

- ✓ `database/migrations/003_add_timeframes_to_symbols.sql` - Schema
- ✓ `src/services/database_service.py` - `get_all_symbols_detailed()` method
- ✓ `scripts/backfill_ohlcv.py` - `update_symbol_timeframe()` function
- ✓ `dashboard/index.html` - Timeframes column + colspan fixes
- ✓ `dashboard/script.js` - `formatTimeframes()` function
- ✓ `main.py` - `/api/v1/symbols/detailed` endpoint

## Full Documentation

See `TIMEFRAMES_SETUP.md` for complete documentation, architecture details, and advanced usage.
