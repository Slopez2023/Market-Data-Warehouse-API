# Timeframes Feature - Setup & Usage Guide

## Overview

The timeframes feature tracks which timeframes (5m, 15m, 30m, 1h, 4h, 1d, 1w) have been backfilled for each symbol and displays this information in the dashboard.

## Architecture

### Components

1. **Database Schema** (`tracked_symbols.timeframes`)
   - PostgreSQL `TEXT[]` array column
   - Stores supported timeframes for each symbol
   - GIN index for fast queries

2. **Backfill Process** (`scripts/backfill_ohlcv.py`)
   - Fetches data from Polygon API
   - Validates data quality
   - Inserts into `market_data` table with timeframe
   - Updates `tracked_symbols.timeframes` array

3. **API Endpoint** (`/api/v1/symbols/detailed`)
   - Returns symbol statistics with timeframes
   - Joins `market_data` with `tracked_symbols`
   - Used by dashboard for display

4. **Dashboard** (`dashboard/index.html` + `dashboard/script.js`)
   - Displays timeframes column in symbol table
   - Renders timeframes in standard order: 5m, 15m, 30m, 1h, 4h, 1d, 1w
   - Shows `--` if no timeframes available

## Setup Instructions

### 1. Verify System Status

```bash
python scripts/verify_timeframes_setup.py
```

This checks:
- ✓ Database schema is correct
- ✓ Timeframes column exists
- ✓ Active symbols loaded
- ✓ GIN index optimized

### 2. Initialize Symbols (if not done)

```bash
python scripts/init_symbols.py
```

Loads symbols from Polygon API into `tracked_symbols` table.

### 3. Backfill Data with Timeframes

**Backfill all symbols with 1-day timeframe:**

```bash
python scripts/backfill_ohlcv.py --timeframe 1d
```

**Backfill specific symbols:**

```bash
python scripts/backfill_ohlcv.py --symbols AAPL,MSFT,SPY --timeframe 1d
```

**Backfill intraday data:**

```bash
python scripts/backfill_ohlcv.py --timeframe 1h --start 2024-01-01 --end 2024-01-31
```

**Available timeframes:**
- `5m` - 5-minute candles
- `15m` - 15-minute candles
- `30m` - 30-minute candles
- `1h` - Hourly candles
- `4h` - 4-hour candles
- `1d` - Daily candles (default)
- `1w` - Weekly candles

### 4. View Dashboard

```bash
# Start API server
python main.py

# Open in browser
http://localhost:8000/dashboard/
```

The dashboard now displays a **Timeframes** column showing which timeframes have been backfilled for each symbol.

### 5. Query API Directly

```bash
# Get all symbols with timeframes
curl http://localhost:8000/api/v1/symbols/detailed

# Example response
{
  "count": 3,
  "symbols": [
    {
      "symbol": "AAPL",
      "records": 1250,
      "validation_rate": 98.5,
      "latest_data": "2024-01-31T16:00:00",
      "data_age_hours": 2.5,
      "timeframes": ["1d", "1h", "4h"],
      "status": "healthy"
    },
    {
      "symbol": "MSFT",
      "records": 1250,
      "validation_rate": 97.8,
      "latest_data": "2024-01-31T16:00:00",
      "data_age_hours": 2.5,
      "timeframes": ["1d"],
      "status": "healthy"
    }
  ]
}
```

## How It Works

### Flow Diagram

```
User runs: python scripts/backfill_ohlcv.py --timeframe 1h
     ↓
[Polygon API] → Fetch 1h candles for symbol
     ↓
[ValidationService] → Validate data quality
     ↓
[DatabaseService.insert_ohlcv_batch(symbol, candles, metadata, timeframe='1h')]
     ↓
[INSERT market_data] → stores with timeframe='1h'
     ↓
[update_symbol_timeframe(symbol, '1h')]
     ↓
[UPDATE tracked_symbols] → Add '1h' to timeframes array if not present
     ↓
[Dashboard refreshes] → Shows "1h, 1d" in Timeframes column
```

### Database Updates

When backfill completes for a symbol with timeframe `1h`:

**Before:**
```sql
SELECT symbol, timeframes FROM tracked_symbols WHERE symbol='AAPL';
-- AAPL | {1d}
```

**After:**
```sql
SELECT symbol, timeframes FROM tracked_symbols WHERE symbol='AAPL';
-- AAPL | {5m,1h,1d}  (sorted in standard order)
```

### API Query

The `/api/v1/symbols/detailed` endpoint joins `market_data` with `tracked_symbols`:

```sql
SELECT 
    m.symbol,
    COUNT(*) as records,
    COUNT(*) FILTER (WHERE m.validated = TRUE)::float / COUNT(*) * 100 as validation_rate,
    MAX(m.time) as latest_data,
    EXTRACT(EPOCH FROM (NOW() - MAX(m.time))) / 3600 as data_age_hours,
    COALESCE(ts.timeframes, ARRAY[]::text[]) as timeframes
FROM market_data m
LEFT JOIN tracked_symbols ts ON m.symbol = ts.symbol
GROUP BY m.symbol, ts.timeframes
ORDER BY m.symbol ASC
```

## Common Tasks

### Check What Timeframes Are Backfilled for a Symbol

```bash
curl "http://localhost:8000/api/v1/symbols/detailed" | jq '.symbols[] | select(.symbol=="AAPL")'
```

### Backfill Multiple Timeframes for Same Symbol

```bash
# Backfill 1-day first
python scripts/backfill_ohlcv.py --symbols AAPL --timeframe 1d

# Then backfill 1-hour (will add to existing timeframes)
python scripts/backfill_ohlcv.py --symbols AAPL --timeframe 1h --start 2024-01-01 --end 2024-01-31

# Check result
curl "http://localhost:8000/api/v1/symbols/detailed" | jq '.symbols[] | select(.symbol=="AAPL")'
# Output: "timeframes": ["1d", "1h"]
```

### Backfill All Symbols with Multiple Timeframes

```bash
# Daily data (5+ years)
python scripts/backfill_ohlcv.py --timeframe 1d

# Hourly data (last 60 days)
python scripts/backfill_ohlcv.py --timeframe 1h --start 2023-12-02 --end 2024-01-31
```

### Database Query to View Timeframes

```bash
psql postgresql://market_user:changeMe123@localhost:5432/market_data

-- View all symbols and their timeframes
SELECT symbol, timeframes, active FROM tracked_symbols ORDER BY symbol;

-- Count symbols by timeframe availability
SELECT 
    COUNT(*) as total_symbols,
    COUNT(*) FILTER (WHERE timeframes @> ARRAY['1d']) as has_1d,
    COUNT(*) FILTER (WHERE timeframes @> ARRAY['1h']) as has_1h,
    COUNT(*) FILTER (WHERE timeframes @> ARRAY['4h']) as has_4h
FROM tracked_symbols WHERE active = TRUE;
```

## Troubleshooting

### Dashboard shows `--` for all timeframes

**Cause:** No backfill has been run yet or `tracked_symbols` is empty

**Fix:**
```bash
python scripts/init_symbols.py
python scripts/backfill_ohlcv.py --timeframe 1d
```

### Timeframes not updating after backfill

**Cause:** Database migrations not run or connection issue

**Fix:**
```bash
# Verify setup
python scripts/verify_timeframes_setup.py

# Check API is running
curl http://localhost:8000/health

# Check database directly
psql -c "SELECT symbol, timeframes FROM tracked_symbols LIMIT 5;"
```

### Performance issues with large dataset

**Solution:** The GIN index on timeframes is automatically created. If queries are still slow:

```bash
# Refresh index statistics
psql -c "ANALYZE tracked_symbols;"
```

## API Reference

### GET /api/v1/symbols/detailed

Returns detailed statistics for all symbols including timeframes.

**Response:**
```json
{
  "count": 3,
  "timestamp": "2024-01-31T18:30:00",
  "symbols": [
    {
      "symbol": "AAPL",
      "records": 1250,
      "validation_rate": 98.5,
      "latest_data": "2024-01-31T16:00:00",
      "data_age_hours": 2.5,
      "timeframes": ["1d", "1h", "4h"],
      "status": "healthy"
    }
  ]
}
```

**Status values:**
- `healthy` - Recent data (< 24h) with good validation (≥ 95%)
- `warning` - Moderate data age (> 24h) or moderate validation (85-95%)
- `stale` - Old data (> 72h) or poor validation (< 85%)

## Implementation Details

### Update Logic (backfill_ohlcv.py)

```python
async def update_symbol_timeframe(database_url: str, symbol: str, timeframe: str) -> bool:
    """Update tracked_symbols to include the backfilled timeframe."""
    conn = await asyncpg.connect(database_url)
    
    # Get current timeframes
    row = await conn.fetchrow(
        "SELECT timeframes FROM tracked_symbols WHERE symbol = $1", symbol
    )
    
    current_timeframes = list(row['timeframes']) if row['timeframes'] else []
    
    # Add timeframe if not already present
    if timeframe not in current_timeframes:
        current_timeframes.append(timeframe)
        # Sort for consistency: 5m, 15m, 30m, 1h, 4h, 1d, 1w
        current_timeframes = sorted(
            current_timeframes,
            key=lambda x: (['5m', '15m', '30m', '1h', '4h', '1d', '1w'].index(x))
        )
        
        await conn.execute(
            "UPDATE tracked_symbols SET timeframes = $1 WHERE symbol = $2",
            current_timeframes,
            symbol
        )
```

### Database Migration (003_add_timeframes_to_symbols.sql)

```sql
ALTER TABLE tracked_symbols
ADD COLUMN IF NOT EXISTS timeframes TEXT[] DEFAULT ARRAY['5m', '15m', '30m', '1h', '4h', '1d', '1w'];

CREATE INDEX IF NOT EXISTS idx_tracked_symbols_timeframes ON tracked_symbols USING GIN(timeframes);
```

## Performance Notes

- **GIN Index:** Enables fast queries for timeframes (e.g., find symbols with 1h data)
- **Array Operations:** PostgreSQL `@>` operator efficiently checks array membership
- **Caching:** API responses cached for 5 minutes (configurable)
- **Typical Query Time:** < 100ms for 1000+ symbols

## Next Steps

1. ✓ Verify system with `verify_timeframes_setup.py`
2. ✓ Run initial backfill: `backfill_ohlcv.py --timeframe 1d`
3. ✓ Check dashboard: `/dashboard/`
4. ✓ Configure scheduler for automatic backfills
5. ✓ Add more timeframes as needed: `--timeframe 1h`, `--timeframe 4h`

## Support

For issues or questions:
- Check `api.log` for error details
- Run verification script: `python scripts/verify_timeframes_setup.py`
- Review database logs: `psql -l` and check migration status
