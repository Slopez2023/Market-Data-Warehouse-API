# Market Data API - Setup & Deployment Guide

## Overview

This is a production-ready, validated OHLCV (stock & crypto) data warehouse API. It provides:
- Single source of truth for market data
- Daily auto-backfill scheduler
- Multi-project API key authentication
- Full observability (metrics, logging, alerts)
- Query caching and performance monitoring

## Quick Start (Docker)

### 1. Prerequisites

```bash
Docker & Docker Compose installed
PostgreSQL 13+ (TimescaleDB)
Polygon.io API key (free tier available)
```

### 2. Environment Setup

Create `.env` file in project root:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/marketdata

# Polygon API
POLYGON_API_KEY=your_polygon_key_here

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Scheduler (UTC times)
BACKFILL_SCHEDULE_HOUR=2
BACKFILL_SCHEDULE_MINUTE=0

# Logging
LOG_LEVEL=INFO

# Alerts (Optional)
ALERT_EMAIL_ENABLED=false
```

### 3. Initialize Database

```bash
# Apply migrations
psql -h localhost -U user -d marketdata -f database/migrations/001_add_symbols_and_api_keys.sql

# Apply base schema
psql -h localhost -U user -d marketdata -f database/sql/schema.sql

# Initialize default symbols (30 stocks + crypto)
python scripts/init_symbols.py
```

### 4. Generate API Key

For each project that will call this API:

```bash
python scripts/generate_api_key.py "My Project Name"
```

Output:
```
=====================================
✓ API Key Generated Successfully
=====================================

Project: My Project Name
Created: 2025-11-10T15:30:45

API Key (save this - it won't be shown again):

  mdw_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6

Key Preview (for reference): mdw_a1b2...

Usage in requests:
  curl -H 'X-API-Key: mdw_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6' \
    'http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31'
```

### 5. Start API

```bash
# Development
python main.py

# Docker
docker-compose up -d
```

API will be available at `http://localhost:8000`
- Dashboard: `http://localhost:3000`
- API Docs: `http://localhost:8000/docs`

---

## API Usage

### Public Endpoints (No Auth Required)

#### Health Check
```bash
curl http://localhost:8000/health
```

#### System Status
```bash
curl http://localhost:8000/api/v1/status
```

#### Historical Data
```bash
curl "http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31"
```

### Admin Endpoints (Requires X-API-Key)

#### Add Symbol
```bash
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: your_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC", "asset_class": "crypto"}'
```

#### List All Symbols
```bash
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:8000/api/v1/admin/symbols
```

#### Get Specific Symbol
```bash
curl -H "X-API-Key: your_api_key_here" \
  http://localhost:8000/api/v1/admin/symbols/BTC
```

#### Deactivate Symbol (Stop Backfilling)
```bash
curl -X DELETE http://localhost:8000/api/v1/admin/symbols/OLDCOIN \
  -H "X-API-Key: your_api_key_here"
```

---

## Symbol Management

### Add 15 More Stocks

```bash
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "CRM", "asset_class": "stock"}'

curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "ADBE", "asset_class": "stock"}'

# ... repeat for each symbol
```

Or use a script (create `add_symbols.sh`):

```bash
#!/bin/bash

API_KEY="your_api_key"
API_URL="http://localhost:8000/api/v1/admin/symbols"

symbols=("CRM" "ADBE" "MU" "CSCO" "IBM" "QCOM" "AMAT" "LRCX" "SNPS" "CDNS" "MCHP" "XLNX" "ASML" "TSM" "AVGO")

for symbol in "${symbols[@]}"; do
  echo "Adding $symbol..."
  curl -X POST "$API_URL" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"symbol\": \"$symbol\", \"asset_class\": \"stock\"}" \
    -s | jq .
done
```

### Add Crypto Assets

Default crypto symbols (added by `init_symbols.py`):
- BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, MATIC, LINK, LTC, UNI, ARB, OP, PEPE

To add more:
```bash
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "NEAR", "asset_class": "crypto"}'
```

---

## Multi-Project Integration

### For Your Other Projects

1. **Generate API Key** (do this once, on the warehouse server):
   ```bash
   python scripts/generate_api_key.py "Project Alpha"
   # Save the output API key
   ```

2. **In Your Project Code**:
   ```python
   import requests
   
   API_KEY = "mdw_your_api_key_here"
   WAREHOUSE_URL = "http://warehouse:8000"
   
   # Fetch historical data
   response = requests.get(
       f"{WAREHOUSE_URL}/api/v1/historical/AAPL",
       params={
           "start": "2023-01-01",
           "end": "2023-12-31",
           "validated_only": True,
           "min_quality": 0.85
       },
       headers={"X-API-Key": API_KEY}
   )
   
   data = response.json()
   for candle in data['data']:
       print(candle)
   ```

3. **cURL Example**:
   ```bash
   curl -H "X-API-Key: mdw_your_api_key_here" \
     "http://warehouse:8000/api/v1/historical/BTC?start=2023-01-01&end=2023-12-31"
   ```

---

## Monitoring

### Dashboard
Open `http://localhost:3000` to view:
- Symbol count
- Total records in database
- Validation rates
- Latest data timestamp
- Scheduler status
- System alerts

### API Metrics Endpoint
```bash
curl http://localhost:8000/api/v1/observability/metrics
```

Returns:
- Request counts & error rates
- Response time statistics
- Per-endpoint metrics
- Error summaries

### Performance Stats
```bash
curl http://localhost:8000/api/v1/performance/summary
```

Returns:
- Cache hit rates
- Query performance (min/max/median/p95/p99)
- Performance bottlenecks
- Optimization recommendations

---

## Maintenance

### Backfill Scheduler

Runs automatically every day at configured time (default: 2 AM UTC)

**What it does:**
1. Loads all active symbols from database
2. Fetches last 30 days of OHLCV from Polygon
3. Validates each candle
4. Inserts validated records into database
5. Logs results and updates backfill history

**Monitor scheduler:**
```bash
curl http://localhost:8000/api/v1/metrics
```

### Updating Symbols

**Add a symbol:**
```bash
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "NEW", "asset_class": "stock"}'
```

Next scheduled backfill will automatically fetch data.

**Stop backfilling a symbol:**
```bash
curl -X DELETE http://localhost:8000/api/v1/admin/symbols/OLD \
  -H "X-API-Key: your_key"
```

Historical data is NOT deleted, just no longer backfilled.

### Database Maintenance

Check database size:
```bash
psql -d marketdata -c "SELECT pg_size_pretty(pg_total_relation_size('market_data'));"
```

Check latest data:
```bash
psql -d marketdata -c "SELECT symbol, MAX(time) as latest FROM market_data GROUP BY symbol ORDER BY latest DESC;"
```

---

## Troubleshooting

### Scheduler Not Running
```bash
curl http://localhost:8000/api/v1/metrics
# Check "scheduler.running" field
```

Check logs:
```bash
docker logs api  # if using Docker
# or check application logs
```

### No Data for Symbol
1. Verify symbol is active:
   ```bash
   curl -H "X-API-Key: your_key" \
     http://localhost:8000/api/v1/admin/symbols/BTC
   ```

2. Check if Polygon has data:
   ```bash
   curl "https://api.polygon.io/v1/open-close/BTC/USD/2025-11-10?apiKey=your_key"
   ```

3. Manually trigger backfill (coming in next update):
   ```bash
   # For now: wait for next scheduled time or restart scheduler
   ```

### High Error Rate
Check alerts:
```bash
curl http://localhost:8000/api/v1/observability/alerts?limit=20
```

Common causes:
- Database connection issues
- Polygon API rate limit
- Invalid symbols
- Network connectivity

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | required | PostgreSQL connection string |
| POLYGON_API_KEY | required | Polygon.io API key |
| API_HOST | 0.0.0.0 | API host binding |
| API_PORT | 8000 | API port |
| API_WORKERS | 4 | Worker threads |
| BACKFILL_SCHEDULE_HOUR | 2 | UTC hour for daily backfill |
| BACKFILL_SCHEDULE_MINUTE | 0 | Minute for daily backfill |
| LOG_LEVEL | INFO | DEBUG, INFO, WARNING, ERROR |

### Database Tables

**tracked_symbols** - Configuration for what to backfill
```
id, symbol, asset_class, active, date_added, last_backfill, backfill_status
```

**api_keys** - API key authentication
```
id, key_hash, name, active, created_at, last_used, request_count
```

**market_data** - Time-series OHLCV data (TimescaleDB hypertable)
```
time, symbol, open, high, low, close, volume, validated, quality_score, ...
```

---

## Next Steps

1. ✅ Initialize database with symbols
2. ✅ Generate API keys for your projects
3. ✅ Configure environment variables
4. ✅ Start the application
5. ⭕ Monitor data quality via dashboard
6. ⭕ Add more symbols as needed
7. ⭕ Set up alerting (email/webhook)

---

## Support

For issues or questions, check:
- `OBSERVABILITY.md` - Monitoring and alerting guide
- `PERFORMANCE_QUICK_REFERENCE.md` - Performance tuning
- `API_ENDPOINTS.md` - Full endpoint reference
- Application logs (Docker: `docker logs api`)

---

**Version**: 1.0.0  
**Last Updated**: November 10, 2025  
**Status**: Production Ready
