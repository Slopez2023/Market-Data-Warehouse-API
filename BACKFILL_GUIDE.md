# Backfill Commands - Market Data API

## Overview

Data backfill happens two ways:

1. **Automatic Backfill** - Scheduler runs daily at configured time (default: 02:00 UTC)
2. **Manual Backfill** - Run the backfill script on-demand

---

## Automatic Backfill (Scheduler)

The scheduler runs automatically when the API starts.

### Check Scheduler Status
```bash
curl http://localhost:8000/health
```

Response shows `"scheduler_running": true`

### View Last Backfill Results
```bash
curl http://localhost:8000/api/v1/metrics
```

Shows:
- `last_backfill.time` - When it last ran
- `last_backfill.successful_symbols` - Successful backfills
- `last_backfill.failed_symbols` - Failed backfills
- `last_backfill.total_records_imported` - Records added

### Change Schedule Time

Edit `.env`:
```bash
BACKFILL_SCHEDULE_HOUR=2      # UTC hour (0-23)
BACKFILL_SCHEDULE_MINUTE=0    # Minute (0-59)
```

Then restart the API:
```bash
docker-compose restart api
```

---

## Manual Backfill

Use the `backfill.py` script to fetch historical data on-demand.

### Prerequisites
1. Add symbols to track first:
```bash
python scripts/init_symbols.py
```

Or manually add via API:
```bash
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","asset_class":"stock"}'
```

### Basic Backfill (Default: 5 years, 15 large-cap stocks)
```bash
python scripts/backfill.py
```

Fetches 5 years of data for: AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, NFLX, AMD, INTC, PYPL, SQ, CRM, ADBE, MU

### Backfill Specific Symbols
```bash
python scripts/backfill.py --symbols AAPL,MSFT,GOOGL
```

### Backfill Specific Date Range
```bash
python scripts/backfill.py \
  --symbols AAPL,MSFT \
  --start 2020-01-01 \
  --end 2023-12-31
```

### Backfill Single Symbol, Recent Data
```bash
python scripts/backfill.py \
  --symbols TSLA \
  --start 2024-01-01 \
  --end 2024-11-11
```

### Backfill All Active Symbols
```bash
# Get list of active symbols from database
python scripts/backfill.py --symbols "*"
```

---

## Common Backfill Scenarios

### Scenario 1: Initial Data Load (All Symbols)
```bash
# 1. Add symbols to database
python scripts/init_symbols.py

# 2. Backfill 5 years of history
python scripts/backfill.py
```

### Scenario 2: Add New Stock Symbol
```bash
# 1. Add to database
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"NVDA","asset_class":"stock"}'

# 2. Backfill 3 years of data
python scripts/backfill.py \
  --symbols NVDA \
  --start 2021-11-11 \
  --end 2024-11-11
```

### Scenario 3: Backfill Recent Data Only
```bash
# Get last 30 days
python scripts/backfill.py \
  --symbols AAPL,MSFT,GOOGL \
  --start 2024-10-12 \
  --end 2024-11-11
```

### Scenario 4: Batch Backfill by Asset Class

Stocks:
```bash
python scripts/backfill.py --symbols AAPL,MSFT,GOOGL,AMZN,NVDA,TSLA
```

Crypto:
```bash
python scripts/backfill.py --symbols BTC,ETH,SOL,ADA,XRP
```

ETFs:
```bash
python scripts/backfill.py --symbols SPY,QQQ,IWM,EEM,AGG
```

---

## Monitor Backfill Progress

### During Backfill
Script shows progress:
```
2025-11-11 00:56:16,123 - __main__ - INFO - Backfilling AAPL: 2019-11-11 to 2024-11-11
2025-11-11 00:56:19,456 - __main__ - INFO - Fetched 1250 candles for AAPL
2025-11-11 00:56:22,789 - __main__ - INFO - ✓ Successfully backfilled 1250 records for AAPL
```

### After Backfill
Check database:
```bash
# View row counts
docker exec market_data_postgres psql -U market_user -d market_data -c "
  SELECT 
    'market_data' as table_name, 
    COUNT(*) as rows 
  FROM market_data
  UNION ALL
  SELECT 
    'tracked_symbols', 
    COUNT(*) 
  FROM tracked_symbols;
"

# View latest data by symbol
docker exec market_data_postgres psql -U market_user -d market_data -c "
  SELECT 
    symbol, 
    MAX(time) as latest_date, 
    COUNT(*) as records 
  FROM market_data 
  GROUP BY symbol 
  ORDER BY symbol;
"
```

### Via API
```bash
curl http://localhost:8000/api/v1/status | python -m json.tool
```

Shows:
- symbols_available
- total_records
- latest_data
- validation_rate

---

## Advanced Options

### Run Backfill Inside Container
```bash
docker exec market_data_api python scripts/backfill.py --symbols AAPL,MSFT
```

### Backfill with Custom Database
```bash
DATABASE_URL=postgresql://user:password@host:5432/db python scripts/backfill.py
```

### View Backfill History
```bash
# Check backfill_history table
docker exec market_data_postgres psql -U market_user -d market_data -c "
  SELECT 
    symbol, 
    backfill_timestamp, 
    records_imported, 
    success, 
    error_details 
  FROM backfill_history 
  ORDER BY backfill_timestamp DESC 
  LIMIT 20;
"
```

---

## Troubleshooting

### "POLYGON_API_KEY not set"
```bash
# Check .env
grep POLYGON_API_KEY .env

# If missing, add it:
echo "POLYGON_API_KEY=your_key_here" >> .env
```

### "No data returned for symbol"
- Symbol might not exist in Polygon.io
- Check symbol is correct (e.g., AAPL not AAP)
- Verify Polygon API key has access
- Try with a known symbol like AAPL

### Database connection fails
```bash
# Check database is running
docker-compose ps | grep postgres

# If not running:
docker-compose restart database
docker-compose restart api
```

### Backfill takes too long
- Reduce date range: `--start 2024-01-01` instead of 5 years
- Backfill fewer symbols at once
- Run multiple scripts in parallel (different symbols)

### "Duplicate key value" error
- Data already exists for that date range
- Polygon API returns same data multiple times
- Safe to ignore - just means data was already there

---

## Performance Tips

### Backfill Multiple Symbols Faster
Run in parallel (from separate terminals):
```bash
# Terminal 1
python scripts/backfill.py --symbols AAPL,MSFT,GOOGL

# Terminal 2
python scripts/backfill.py --symbols AMZN,NVDA,TSLA

# Terminal 3
python scripts/backfill.py --symbols META,NFLX,AMD
```

### Backfill Large Date Ranges
Break into chunks:
```bash
# Year 1
python scripts/backfill.py --symbols AAPL --start 2019-11-11 --end 2020-11-11

# Year 2
python scripts/backfill.py --symbols AAPL --start 2020-11-11 --end 2021-11-11

# Year 3
python scripts/backfill.py --symbols AAPL --start 2021-11-11 --end 2022-11-11
```

### Monitor API Rate Limits
Polygon.io free tier: 150 requests/minute
- Script is optimized for this rate
- Default script runs fine within limits
- If you need faster, upgrade plan

---

## Query After Backfill

Once data is loaded, query via API:

### Get Historical Data
```bash
curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-01-01&end=2024-11-11"
```

### List Available Symbols
```bash
curl http://localhost:8000/api/v1/symbols
```

### Get Symbol Stats
```bash
curl http://localhost:8000/api/v1/status | python -m json.tool
```

---

## Schedule Customization

### Daily at 3 AM UTC
```bash
# .env
BACKFILL_SCHEDULE_HOUR=3
BACKFILL_SCHEDULE_MINUTE=0
```

### Multiple times per day
Not supported in current scheduler. Workaround:
1. Disable auto backfill
2. Run manual script via cron:
```bash
# Backfill at 02:00 and 14:00 UTC
0 2 * * * cd /path/to/api && python scripts/backfill.py
0 14 * * * cd /path/to/api && python scripts/backfill.py
```

---

## Summary

| Task | Command |
|------|---------|
| Check scheduler | `curl http://localhost:8000/health` |
| View last results | `curl http://localhost:8000/api/v1/metrics` |
| Backfill default (5y, 15 stocks) | `python scripts/backfill.py` |
| Backfill specific stocks | `python scripts/backfill.py --symbols AAPL,MSFT` |
| Backfill date range | `python scripts/backfill.py --start 2024-01-01 --end 2024-11-11` |
| View backfill history | `curl http://localhost:8000/api/v1/metrics` |

---

**For detailed help:**
```bash
python scripts/backfill.py --help
```
