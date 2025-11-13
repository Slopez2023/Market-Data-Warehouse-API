# Backfill Commands Reference

## Quick Start: Backfill All Stocks with All Timeframes

```bash
./BACKFILL_ALL_TIMEFRAMES.sh
```

This will automatically:
- Fetch all active symbols from the database
- Backfill 5 years of data for each symbol
- Process all 7 supported timeframes: `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`
- Display final database statistics

---

## Individual Timeframe Commands

If you prefer to backfill one timeframe at a time:

```bash
# Backfill all symbols with 1-day candles
python scripts/backfill.py --timeframe 1d

# Backfill all symbols with 4-hour candles
python scripts/backfill.py --timeframe 4h

# Backfill all symbols with 1-hour candles
python scripts/backfill.py --timeframe 1h

# Backfill all symbols with 15-minute candles
python scripts/backfill.py --timeframe 15m

# Backfill all symbols with 5-minute candles
python scripts/backfill.py --timeframe 5m

# Backfill all symbols with 30-minute candles
python scripts/backfill.py --timeframe 30m

# Backfill all symbols with 1-week candles
python scripts/backfill.py --timeframe 1w
```

---

## Backfill Specific Symbols

```bash
# Backfill only AAPL, MSFT, GOOGL with 1-day timeframe
python scripts/backfill.py --symbols AAPL,MSFT,GOOGL --timeframe 1d

# Backfill single symbol with multiple timeframes
python scripts/backfill.py --symbols SPY --timeframe 1h
python scripts/backfill.py --symbols SPY --timeframe 4h
python scripts/backfill.py --symbols SPY --timeframe 1d
```

---

## Custom Date Range

```bash
# Backfill from specific dates
python scripts/backfill.py \
  --start 2023-01-01 \
  --end 2024-12-31 \
  --timeframe 1d

# Backfill last 1 year only
python scripts/backfill.py \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --timeframe 1h
```

---

## Advanced: Update Symbol Configuration

Configure which timeframes each symbol should fetch via the scheduler:

```bash
# Set AAPL to fetch all 7 timeframes
curl -X PUT http://localhost:8000/api/v1/admin/symbols/AAPL/timeframes \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "timeframes": ["5m", "15m", "30m", "1h", "4h", "1d", "1w"]
  }'

# Set a symbol to fetch only daily and weekly
curl -X PUT http://localhost:8000/api/v1/admin/symbols/SPY/timeframes \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "timeframes": ["1d", "1w"]
  }'
```

After configuration, the scheduler will automatically backfill these timeframes daily at 02:00 UTC.

---

## Monitor Backfill Progress

```bash
# Check API status (shows database metrics)
curl http://localhost:8000/api/v1/status | python -m json.tool

# View backfill history
curl http://localhost:8000/api/v1/status | python -m json.tool | grep -A 20 "data_quality"

# Check specific symbol data
curl "http://localhost:8000/api/v1/historical/AAPL?timeframe=1d&start=2024-01-01&end=2024-12-31" | python -m json.tool
```

---

## Troubleshooting

### Issue: "No data returned for symbol"
- Symbol may not be active in database
- Check: `SELECT * FROM tracked_symbols WHERE active = TRUE;`
- Activate: Use API to set symbol active or run `python scripts/init_symbols.py`

### Issue: "POLYGON_API_KEY not set"
- Ensure `.env` file has `POLYGON_API_KEY=pk_xxxx`
- Or export: `export POLYGON_API_KEY=pk_xxxx`

### Issue: Database connection failed
- Ensure Docker containers are running: `docker-compose ps`
- Check DATABASE_URL in `.env` matches container setup

### Issue: Script takes too long
- Running all 7 timeframes for many symbols takes hours
- Consider running during off-peak hours or in background: `nohup ./BACKFILL_ALL_TIMEFRAMES.sh &`

---

## Supported Timeframes

| Timeframe | Description | Use Case |
|-----------|-------------|----------|
| 5m | 5-minute candles | High-frequency trading, intraday scalping |
| 15m | 15-minute candles | Intraday swing trading |
| 30m | 30-minute candles | Intraday analysis |
| 1h | 1-hour candles | Short-term trading |
| 4h | 4-hour candles | Medium-term swing trading |
| 1d | 1-day candles | Position trading, trend analysis |
| 1w | 1-week candles | Long-term trend analysis |

---

## Data Statistics After Backfill

Expected results after complete backfill:

```
Database status:
  Symbols: ~3500+ (depending on tracked symbols)
  Total records: ~50M+ (varies by symbol and timeframe)
  Validated records: ~95%+ (quality-checked)
  Validation rate: ~96%+
  Latest data: Current date
```

---

## Performance Notes

- **Backfill time**: ~10-30 minutes for all timeframes of 50 symbols
- **Database size**: ~5-10 GB for 5 years of data across 7 timeframes
- **API latency**: <100ms for typical queries
- **Memory usage**: ~500 MB during backfill

---

## Automatic Scheduling

By default, the scheduler runs daily at **02:00 UTC** and backfills configured timeframes for all active symbols. To change:

In `.env` or `docker-compose.yml`:
```env
BACKFILL_SCHEDULE_HOUR=2        # 0-23 (UTC)
BACKFILL_SCHEDULE_MINUTE=0      # 0-59
```

Then restart the API container:
```bash
docker-compose restart api
```

---

## Key Environment Variables

```env
# Required
POLYGON_API_KEY=pk_xxx...          # Your Polygon.io API key
DATABASE_URL=postgresql://...       # Database connection string

# Optional
DB_PASSWORD=yourpassword            # Database password
DB_HOST=localhost                   # Database host
DB_PORT=5432                        # Database port
BACKFILL_SCHEDULE_HOUR=2            # Scheduler hour (0-23 UTC)
BACKFILL_SCHEDULE_MINUTE=0          # Scheduler minute (0-59)
```

---

## Support & Links

- **Polygon.io API**: https://polygon.io/docs/stocks/get_aggs
- **API Documentation**: http://localhost:8000/docs
- **Dashboard**: http://localhost:3001
- **Health Check**: http://localhost:8000/health
