# Timeframes Feature - Command Reference

## Verification & Setup

```bash
# Verify system is ready (run first!)
python scripts/verify_timeframes_setup.py

# Initialize symbols from Polygon API
python scripts/init_symbols.py
```

## Backfill Data

### Basic Backfill (Most Common)

```bash
# Backfill all symbols with 1-day candles (~5 years of data)
python scripts/backfill_ohlcv.py --timeframe 1d

# Backfill specific symbols with 1-day
python scripts/backfill_ohlcv.py --symbols AAPL,MSFT,SPY --timeframe 1d
```

### Intraday Backfill

```bash
# Backfill 1-hour candles for last month
python scripts/backfill_ohlcv.py --timeframe 1h --start 2024-01-01 --end 2024-01-31

# Backfill 4-hour candles
python scripts/backfill_ohlcv.py --timeframe 4h --start 2024-01-01 --end 2024-01-31

# Backfill 5-minute candles (more data!)
python scripts/backfill_ohlcv.py --timeframe 5m --start 2024-01-29 --end 2024-01-31
```

### Custom Date Ranges

```bash
# Backfill specific date range
python scripts/backfill_ohlcv.py --timeframe 1d --start 2023-01-01 --end 2023-12-31

# Backfill recent data only (today)
python scripts/backfill_ohlcv.py --timeframe 1d --start 2024-01-31 --end 2024-01-31
```

### Multiple Timeframes (Same Symbol)

```bash
# Backfill daily (comprehensive history)
python scripts/backfill_ohlcv.py --symbols AAPL --timeframe 1d

# Then add hourly (last month)
python scripts/backfill_ohlcv.py --symbols AAPL --timeframe 1h --start 2024-01-01 --end 2024-01-31

# Result: AAPL has timeframes: [1d, 1h]
```

### Batch Backfill

```bash
# Backfill multiple symbols, multiple timeframes
python scripts/backfill_ohlcv.py --symbols AAPL,MSFT,GOOGL,AMZN,TSLA --timeframe 1d

# Then hourly for recent month
python scripts/backfill_ohlcv.py --symbols AAPL,MSFT,GOOGL,AMZN,TSLA --timeframe 1h \
  --start 2024-01-01 --end 2024-01-31
```

## API Queries

### Get All Symbols with Timeframes

```bash
# Pretty-printed JSON
curl http://localhost:8000/api/v1/symbols/detailed | jq

# Specific symbol only
curl http://localhost:8000/api/v1/symbols/detailed | jq '.symbols[] | select(.symbol=="AAPL")'

# Just symbol and timeframes
curl http://localhost:8000/api/v1/symbols/detailed | \
  jq '.symbols[] | {symbol, timeframes, records}'

# Count symbols by timeframe
curl http://localhost:8000/api/v1/symbols/detailed | \
  jq '.symbols | group_by(.status) | map({status: .[0].status, count: length})'
```

### Get System Status

```bash
# Overall database metrics
curl http://localhost:8000/api/v1/status | jq '.database'

# Full metrics including scheduler
curl http://localhost:8000/api/v1/metrics | jq

# Health check
curl http://localhost:8000/health | jq
```

## Dashboard

```bash
# View in browser
http://localhost:8000/dashboard/

# View raw HTML (for debugging)
curl http://localhost:8000/dashboard/index.html

# Auto-refresh (opens new tab)
curl -s http://localhost:8000/dashboard/index.html | grep 'Timeframes' | head -1
```

## Database Queries

### View Timeframes Data

```bash
# Connect to database
psql postgresql://market_user:changeMe123@localhost:5432/market_data

# Show all symbols with timeframes
SELECT symbol, timeframes, active FROM tracked_symbols ORDER BY symbol;

# Show active symbols only
SELECT symbol, timeframes FROM tracked_symbols WHERE active=TRUE ORDER BY symbol;

# Sample output (first 10)
SELECT symbol, timeframes FROM tracked_symbols WHERE active=TRUE LIMIT 10;
```

### Analyze Timeframe Coverage

```bash
# Count symbols with each timeframe
SELECT 
    COUNT(*) as total_symbols,
    COUNT(*) FILTER (WHERE '5m' = ANY(timeframes)) as has_5m,
    COUNT(*) FILTER (WHERE '15m' = ANY(timeframes)) as has_15m,
    COUNT(*) FILTER (WHERE '30m' = ANY(timeframes)) as has_30m,
    COUNT(*) FILTER (WHERE '1h' = ANY(timeframes)) as has_1h,
    COUNT(*) FILTER (WHERE '4h' = ANY(timeframes)) as has_4h,
    COUNT(*) FILTER (WHERE '1d' = ANY(timeframes)) as has_1d,
    COUNT(*) FILTER (WHERE '1w' = ANY(timeframes)) as has_1w
FROM tracked_symbols WHERE active=TRUE;

# Find symbols missing certain timeframes
SELECT symbol FROM tracked_symbols 
WHERE active=TRUE AND NOT ('1d' = ANY(timeframes));

# Get record count per symbol per timeframe
SELECT 
    symbol,
    timeframe,
    COUNT(*) as records
FROM market_data
GROUP BY symbol, timeframe
ORDER BY symbol, 
    CASE timeframe 
        WHEN '5m' THEN 1
        WHEN '15m' THEN 2
        WHEN '30m' THEN 3
        WHEN '1h' THEN 4
        WHEN '4h' THEN 5
        WHEN '1d' THEN 6
        WHEN '1w' THEN 7
    END;
```

### Database Maintenance

```bash
# Refresh index statistics (performance optimization)
ANALYZE tracked_symbols;

# Check table size
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) as size
FROM pg_tables
WHERE schemaname='public'
ORDER BY pg_total_relation_size(tablename::regclass) DESC;

# Verify GIN index
SELECT indexname FROM pg_indexes 
WHERE tablename='tracked_symbols' AND indexname LIKE '%timeframes%';
```

## Monitoring

### Watch Backfill Progress

```bash
# Live log tail (while backfilling)
tail -f api.log | grep -E "backfill|timeframe|Successfully"

# Show last 20 backfill entries
tail -20 api.log | grep -i backfill

# Count successful backfills today
grep "Successfully backfilled" api.log | wc -l
```

### Monitor API Performance

```bash
# Test response time
time curl -s http://localhost:8000/api/v1/symbols/detailed > /dev/null

# Count symbols loaded
curl -s http://localhost:8000/api/v1/symbols/detailed | jq '.count'

# Check timestamp freshness
curl -s http://localhost:8000/api/v1/symbols/detailed | jq '.timestamp'
```

## Debugging

### Check What Timeframes Exist

```bash
# Via API
curl -s http://localhost:8000/api/v1/symbols/detailed | \
  jq '.symbols | map(.timeframes) | unique | sort'

# Via database
psql -c "SELECT DISTINCT unnest(timeframes) FROM tracked_symbols ORDER BY 1;"
```

### Troubleshoot Missing Timeframes

```bash
# 1. Check if symbols exist
psql -c "SELECT COUNT(*) FROM tracked_symbols WHERE active=TRUE;"

# 2. Check if timeframe data inserted
psql -c "SELECT DISTINCT timeframe FROM market_data ORDER BY timeframe;"

# 3. Check tracked_symbols has timeframes
psql -c "SELECT symbol, timeframes FROM tracked_symbols WHERE timeframes IS NOT NULL LIMIT 5;"

# 4. Check API endpoint works
curl http://localhost:8000/api/v1/symbols/detailed | jq '.count'

# 5. Verify backfill updated timeframes
psql -c "SELECT symbol, timeframes FROM tracked_symbols WHERE symbol='AAPL';"
```

### Error Messages & Solutions

```bash
# API returns 500 error
tail -50 api.log | grep ERROR

# Backfill fails with API error
# Check POLYGON_API_KEY is set
echo $POLYGON_API_KEY

# Database connection error
psql postgresql://market_user:changeMe123@localhost:5432/market_data

# Migration failed
psql -c "SELECT version();"
```

## Development Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run timeframe tests only
python -m pytest tests/test_phase_7_timeframe_api.py -v

# Run with coverage
python -m pytest tests/ --cov=src

# Run specific test
python -m pytest tests/test_phase_7_timeframe_api.py::TestTimeframeTracking -v
```

## Common Workflows

### Complete Setup from Scratch

```bash
# 1. Verify system
python scripts/verify_timeframes_setup.py

# 2. Load symbols
python scripts/init_symbols.py

# 3. Backfill daily data (5 years)
python scripts/backfill_ohlcv.py --timeframe 1d

# 4. Check results
curl http://localhost:8000/api/v1/symbols/detailed | jq '.count'

# 5. View dashboard
# Open: http://localhost:8000/dashboard/
```

### Add New Timeframe to Existing Symbols

```bash
# Backfill intraday for recent month
python scripts/backfill_ohlcv.py --timeframe 1h --start 2024-01-01 --end 2024-01-31

# Verify update
curl -s http://localhost:8000/api/v1/symbols/detailed | \
  jq '.symbols[] | select(.timeframes | length > 1)'
```

### Monitor Ongoing Backfills

```bash
# Terminal 1: Watch logs
tail -f api.log | grep -E "Backfilling|Successfully|Error"

# Terminal 2: Check progress periodically
watch -n 5 'curl -s http://localhost:8000/api/v1/symbols/detailed | jq ".count"'

# Terminal 3: Run backfill
python scripts/backfill_ohlcv.py --timeframe 1d
```

### Database Backup/Restore

```bash
# Backup database (keeps timeframes data)
pg_dump postgresql://market_user:changeMe123@localhost:5432/market_data > backup.sql

# Restore
psql postgresql://market_user:changeMe123@localhost:5432/market_data < backup.sql

# Verify timeframes preserved
psql -c "SELECT COUNT(*) FROM tracked_symbols WHERE timeframes IS NOT NULL;"
```

## Quick Aliases (Optional)

```bash
# Add to ~/.bash_profile or ~/.zshrc
alias backfill-daily='python scripts/backfill_ohlcv.py --timeframe 1d'
alias backfill-hourly='python scripts/backfill_ohlcv.py --timeframe 1h'
alias check-symbols='curl -s http://localhost:8000/api/v1/symbols/detailed | jq ".count"'
alias dashboard='open http://localhost:8000/dashboard/'
alias verify-tf='python scripts/verify_timeframes_setup.py'
```

Then use:
```bash
backfill-daily
check-symbols
dashboard
verify-tf
```

## Key Parameters

| Parameter | Default | Example | Description |
|-----------|---------|---------|-------------|
| `--timeframe` | `1d` | `1h`, `4h`, `1w` | Candle timeframe |
| `--symbols` | All | `AAPL,MSFT,SPY` | Comma-separated symbols |
| `--start` | 5y ago | `2024-01-01` | Start date (YYYY-MM-DD) |
| `--end` | Today | `2024-01-31` | End date (YYYY-MM-DD) |

## Support

- **Quick Start:** `TIMEFRAMES_QUICK_START.md`
- **Full Documentation:** `TIMEFRAMES_SETUP.md`
- **Implementation Details:** `IMPLEMENTATION_SUMMARY.md`
- **This File:** `TIMEFRAMES_COMMANDS.md`
