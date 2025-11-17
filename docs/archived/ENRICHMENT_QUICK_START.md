# Enrichment Data - Quick Start

## 5-Minute Setup

### 1. Verify Environment Variables
```bash
# Check .env file has these set:
echo $DATABASE_URL
echo $POLYGON_API_KEY
```

If missing, create `.env` file:
```bash
cp .env.example .env
# Edit .env and add your actual values
```

### 2. Start the API
```bash
python main.py
# Enrichment scheduler will start automatically
```

### 3. Trigger Enrichment (in another terminal)
```bash
# Single symbol
curl -X POST "http://localhost:8000/api/v1/enrichment/trigger?symbol=AAPL"

# Get response with job_id
# {
#   "job_id": "uuid-here",
#   "symbols": ["AAPL"],
#   "status": "queued"
# }
```

### 4. Check Status
```bash
# Check overall dashboard
curl http://localhost:8000/api/v1/enrichment/dashboard/overview

# Check specific symbol
curl http://localhost:8000/api/v1/enrichment/dashboard/job-status/AAPL

# Check recent jobs
curl http://localhost:8000/api/v1/enrichment/history?limit=10
```

## Backfill Historical Data

Run these in order to populate enrichment tables with historical data:

```bash
# 1. Dividends (fastest, ~2 min for 50 symbols)
python scripts/backfill_dividends.py

# 2. Stock Splits (fastest, ~1 min for 50 symbols)
python scripts/backfill_splits.py

# 3. Earnings (medium, ~3 min for 50 symbols)
python scripts/backfill_earnings.py

# 4. Options IV (slowest, ~5-10 min for 50 symbols)
python scripts/backfill_options_iv.py --days 30
```

### Resume Interrupted Backfills
```bash
# Add --resume flag to skip already completed symbols
python scripts/backfill_dividends.py --resume
python scripts/backfill_earnings.py --resume
python scripts/backfill_splits.py --resume
```

## Verify Data Was Populated

```sql
-- In your PostgreSQL client
SELECT COUNT(*), symbol FROM dividends GROUP BY symbol LIMIT 5;
SELECT COUNT(*), symbol FROM earnings GROUP BY symbol LIMIT 5;
SELECT COUNT(*), symbol FROM stock_splits GROUP BY symbol LIMIT 5;
SELECT COUNT(*), symbol FROM options_iv GROUP BY symbol LIMIT 5;
```

## Monitor Scheduler

```bash
# Check scheduler health
curl http://localhost:8000/api/v1/enrichment/dashboard/health

# Check metrics (success rates, counts)
curl http://localhost:8000/api/v1/enrichment/dashboard/metrics

# Pause scheduler if needed
curl http://localhost:8000/api/v1/enrichment/pause

# Resume scheduler
curl http://localhost:8000/api/v1/enrichment/resume
```

## Common Commands Reference

```bash
# Backfill single symbol
python scripts/backfill_dividends.py --symbol AAPL

# Backfill with custom date range (days back)
python scripts/backfill_earnings.py --days 365

# Backfill options with 90-day lookback
python scripts/backfill_options_iv.py --days 90

# Run tests
pytest tests/test_enrichment_integration.py -v
```

## Troubleshooting

**No data appearing in database:**
1. Check API key is valid: `echo $POLYGON_API_KEY`
2. Check database connection: `curl http://localhost:8000/api/v1/enrichment/dashboard/health`
3. Check logs: Look at API output for errors
4. Try single symbol: `python scripts/backfill_dividends.py --symbol AAPL`

**Backfill script fails:**
1. Ensure `.env` is properly configured
2. Check Polygon API quota isn't exceeded
3. Verify database is accessible
4. Run with `--resume` flag to skip failed symbols

**Scheduler not enriching data:**
1. Check scheduler is running: `curl http://localhost:8000/api/v1/enrichment/dashboard/health`
2. Check if paused: Resume if needed with `/resume` endpoint
3. Check next scheduled run time in health response
4. Manually trigger for immediate test: `/trigger` endpoint

## What's Happening Behind the Scenes

1. **API receives request** → `/api/v1/enrichment/trigger`
2. **Scheduler queues job** with unique ID
3. **Background task starts** (doesn't block request)
4. **Service fetches data** from Polygon API
5. **Data validated** and inserted into tables
6. **Status updated** in `enrichment_status` table
7. **Job tracked** in job history for monitoring

All of this happens asynchronously - your API request returns immediately while enrichment continues in background.

## Next Steps

- Review full guide: `ENRICHMENT_IMPLEMENTATION_COMPLETE.md`
- Configure scheduler timing in `main.py` if needed
- Set up alerting for enrichment failures
- Schedule backfills on a cron job for daily updates
