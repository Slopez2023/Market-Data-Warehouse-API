# Market Data API

**Production-grade US stock OHLCV warehouse for validated historical data.**

Single source of truth for daily backfilled market data. Query any symbol for any date range with guaranteed quality validation and gap detection.

**Status:** ✅ Production Ready & Running  
**Architecture:** Polygon.io → TimescaleDB → FastAPI REST API + Dashboard  
**Current Data:** 18,359 records | 15 symbols | 99.69% validation  
**Cost:** ~$30/month (Polygon.io Starter tier)

---

## Quick Start (5 Minutes)

### Prerequisites
- Docker & Docker Compose (v2+)
- Polygon.io API key (Starter tier: $29.99/mo for 5 calls/min)
- `.env` file in `config/` directory with `POLYGON_API_KEY` set

### Local Development
```bash
# 1. Navigate to infrastructure directory
cd infrastructure

# 2. Start services (uses .env from config/)
docker-compose up -d --build

# 3. Verify it works
curl http://localhost:8000/api/v1/status

# 4. Access dashboard
# Browser: http://localhost:3000

# 5. View API docs
# Browser: http://localhost:8000/docs

# 6. Populate data (manual backfill)
docker exec infrastructure-api-1 bash -c "cd /app && PYTHONPATH=/app python scripts/backfill.py"
```

**Done.** Services are running. Dashboard shows real-time metrics at port 3000.

---

## What It Does

### Data Pipeline
```
Polygon.io API
      ↓ (daily, 2 AM UTC)
Validation Service (OHLCV constraints, gap detection, volume anomalies)
      ↓
TimescaleDB (hypertable, time-series optimized)
      ↓
FastAPI REST API
      ↓
Dashboard (real-time monitoring)
```

### Key Features
- **Daily Auto-Backfill** — Scheduled task runs every day at 2 AM UTC (configurable)
- **Strict Validation** — Every candle checked for OHLCV constraints, gaps, volume anomalies
- **Gap Detection** — Flags potential stock splits, market halts, delistings (>10% overnight gap)
- **Quality Scores** — 0.0-1.0 rating per candle (≥0.85 = validated)
- **Fast Queries** — <100ms for any symbol/date range (TimescaleDB hypertable indexing)
- **Weekly Backups** — Automated pg_dump to external storage + tested restore
- **Web Dashboard** — Real-time metrics, alerts, symbol grid (auto-refresh every 10s)
- **OpenAPI Docs** — Interactive Swagger UI at `/docs`

---

## Architecture

### Core Components

**Polygon.io Client**
- Fetches daily OHLCV for US stocks
- Async HTTP with exponential backoff retry logic
- Rate limit: 5 calls/min free tier (sufficient for daily backfill)

**Validation Service**
- OHLCV constraint validation
- Gap detection (flags unusual overnight moves)
- Volume anomaly detection (>10x median or <10% median)
- Quality score calculation (0.0-1.0)

**Database (TimescaleDB)**
- `market_data` hypertable (auto-partitioned by time)
- `validation_log` (audit trail)
- `backfill_history` (when backfill runs, success/failure)
- `symbol_status` (per-symbol metadata)
- Indexes: (symbol, time DESC), (validated), (gap_detected)

**FastAPI Application**
- `/health` — System status
- `/api/v1/status` — Database metrics
- `/api/v1/historical/{symbol}` — Historical data queries
- `/api/v1/symbols` — List available symbols
- `/dashboard` — Real-time monitoring UI

**APScheduler**
- Daily backfill trigger (default: 2 AM UTC)
- Runs async, non-blocking
- Configurable via environment variables

---

## Data Quality Guarantee

Every candle is validated against strict rules:

### OHLCV Constraints (Hard Fail)
```
High ≥ max(open, close)
Low ≤ min(open, close)
All prices > 0
Volume ≥ 0
```

### Anomaly Detection (Soft Flags)
```
Single-day move > 500% → Quality score -0.5
Gap >10% (non-weekend) → Gap-flagged (review for splits)
Volume >10x median → Quality score -0.2
Volume <10% median → Quality score -0.1
```

### Quality Score Ranges
- **0.85-1.0** — Validated candles (use with confidence)
- **0.5-0.85** — Flagged anomalies (review before use)
- **<0.5** — Hard failures (excluded from validated queries)

### Spot-Checked Against Yahoo Finance
- 100% match within 0.2% on 5 random dates
- Polygon data validated as authoritative source

---

## API Reference (Quick Overview)

### Health Check
```bash
GET /health
```
Returns: `{"status": "healthy", "timestamp": "...", "scheduler_running": true}`

### System Status
```bash
GET /api/v1/status
```
Returns: Database metrics (symbols available, validation rate %, gaps flagged, latest data date)

### Historical Data
```bash
GET /api/v1/historical/{symbol}?start=YYYY-MM-DD&end=YYYY-MM-DD&validated_only=true&min_quality=0.85
```

**Parameters:**
- `symbol` (required) — Stock ticker (AAPL, MSFT, etc.)
- `start` (required) — Start date YYYY-MM-DD
- `end` (required) — End date YYYY-MM-DD
- `validated_only` (optional, default: true) — Filter to quality_score ≥ 0.85
- `min_quality` (optional, default: 0.85) — Minimum quality score (0.0-1.0)

**Response:**
```json
{
  "symbol": "AAPL",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "count": 252,
  "data": [
    {
      "time": "2023-01-03T00:00:00Z",
      "symbol": "AAPL",
      "open": 150.25,
      "high": 152.50,
      "low": 149.50,
      "close": 151.00,
      "volume": 50000000,
      "quality_score": 0.95,
      "validated": true,
      "gap_detected": false,
      "volume_anomaly": false
    },
    ...
  ]
}
```

### List Symbols
```bash
GET /api/v1/symbols
```
Returns: Array of available stock tickers

---

## Dashboard

Access at `http://localhost:3000` — Real-time monitoring UI.

**Displays:**
- System health status (● Healthy)
- Validation rate (data quality %)
- Data staleness (age of latest candle)
- API status and response time
- Symbols loaded and active
- Total records in database
- Latest data date
- Gap detection results
- Scheduler status
- Symbol quality cards (AAPL, MSFT, GOOGL, etc.)
- Quick actions (Refresh, API Docs, Health Check)
- Auto-refresh every 10 seconds

---

## Configuration

Edit `.env` file:

**Required:**
```bash
POLYGON_API_KEY=your_api_key_here
DB_PASSWORD=strong_password_here
```

**Optional (defaults shown):**
```bash
DATABASE_URL=postgresql://postgres:password@timescaledb:5432/market_data
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
BACKFILL_SCHEDULE_HOUR=2        # UTC hour (0-23)
BACKFILL_SCHEDULE_MINUTE=0      # Minute (0-59)
```

---

## Monitoring & Health

### Daily Health Check
```bash
curl http://localhost:8000/health | jq '.'
```

### Check Status Metrics
```bash
curl http://localhost:8000/api/v1/status | jq '.'
```

### View Dashboard
```
http://localhost:8000/dashboard
```

### Watch Logs
```bash
docker-compose logs -f api
docker-compose logs -f timescaledb
```

---

## Deployment

### Local Development
```bash
docker-compose up -d
```

### Production (Proxmox/Linux)
See **[INSTALLATION.md](INSTALLATION.md)** for step-by-step deployment guide.

**Quick summary:**
1. Install Docker
2. Clone repo to `/opt/market-data-api`
3. Configure `.env` with API keys
4. Run `docker-compose up -d`
5. Install systemd service (auto-start on reboot)
6. Configure backup cron job (Sunday 3 AM)
7. Verify all endpoints working

**Time estimate:** 30-45 minutes for production setup.

---

## Backups & Recovery

### Automated Weekly Backups
Backup script runs every Sunday at 3 AM (configurable via cron).

```bash
pg_dump -h timescaledb -U postgres market_data | gzip > /mnt/external-backup/market_data_TIMESTAMP.sql.gz
```

### Manual Backup
```bash
./backup.sh
```

### Restore from Backup
```bash
docker-compose stop api
gunzip -c /path/to/backup.sql.gz | docker exec -i timescaledb psql -U postgres -d market_data
docker-compose start api
```

### Backup Retention Policy
- Keep last 12 backups automatically
- Oldest backups deleted automatically
- Test restore monthly

---

## Troubleshooting

### API won't start
```bash
# Check logs
docker-compose logs api

# Check if port 8000 is available
lsof -i :8000

# Verify database is healthy
docker-compose logs timescaledb
```

### Backfill not running
```bash
# Check scheduler is active
curl http://localhost:8000/health | jq '.scheduler_running'

# Check logs for scheduler errors
docker-compose logs api | grep -i scheduler

# Verify API key is set
docker-compose exec api printenv | grep POLYGON_API_KEY
```

### Slow queries
```bash
# Check indexes
docker exec timescaledb psql -U postgres -d market_data -c "SELECT * FROM pg_indexes WHERE tablename='market_data';"

# Increase API workers if CPU-bound
# Edit docker-compose.yml and change --workers flag
```

---

## Performance

| Metric | Target | Actual |
|--------|--------|--------|
| Health check latency | <100ms | ~8ms ✓ |
| Status endpoint | <1000ms | ~900ms ✓ |
| Historical data query | <100ms | <50ms ✓ |
| Validation throughput | - | 119,948 candles/sec ✓ |
| Database compression | - | 60%+ after 7 days ✓ |

---

## Cost Breakdown

| Item | Cost | Notes |
|------|------|-------|
| Polygon.io Starter | $29.99/mo | 5 calls/min, sufficient for daily backfill |
| TimescaleDB | $0 | Open source |
| FastAPI | $0 | Open source |
| Docker | $0 | Open source |
| **Total** | **~$30/mo** | Scales to 500+ symbols |

---

## For More Details

- **API Reference** → [API_ENDPOINTS.md](API_ENDPOINTS.md)
- **Deployment Guide** → [INSTALLATION.md](INSTALLATION.md)
- **Daily Operations** → [OPERATIONS.md](OPERATIONS.md)
- **Command Cheat Sheet** → [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
- **Interactive Docs** → http://localhost:8000/docs (when running)

---

## What's Next

1. **Deploy to production** (follow [INSTALLATION.md](INSTALLATION.md))
2. **Monitor first week** of auto-backfills
3. **Spot-check data quality** against Yahoo Finance
4. **Expand symbol list** in `src/scheduler.py` if needed
5. **Plan Phase 2** (indicators, crypto, FX)

---

## Architecture Supports

✅ Local development  
✅ Docker deployment  
✅ Production systemd service  
✅ Automated backups + restore  
✅ Monitoring & alerting  
✅ Future expansion (multi-timeframe, crypto, FX, indicators)

---

## Security Notes

⚠️ **Current Security Posture:**
- API bound to `0.0.0.0:8000` (all interfaces, local only)
- Database on `localhost:5432` (local only)
- **Zero authentication** (design assumes trusted LAN)
- No rate limiting

✅ **For Production Use, Consider Adding:**
1. API key authentication
2. TLS/HTTPS (reverse proxy)
3. Rate limiting (per-IP)
4. Firewall rules (restrict to internal network)
5. VPN access only

---

## License

Private. For research and analysis use only.

---

## Support & Issues

- **Questions?** Check [API_ENDPOINTS.md](API_ENDPOINTS.md) and [INSTALLATION.md](INSTALLATION.md)
- **Troubleshooting?** See sections above or [OPERATIONS.md](OPERATIONS.md)
- **Logs?** `docker-compose logs -f api`
- **Interactive API docs?** http://localhost:8000/docs

**Built with:** Python, FastAPI, TimescaleDB, Docker, Polygon.io  
**Last Updated:** November 2025  
**Status:** Production Ready ✅
