# Market Data API

Production-grade OHLCV warehouse for US stocks. Single source of truth for validated historical data.

**Status:** MVP Implementation in Progress  
**Architecture:** Polygon.io → TimescaleDB → FastAPI REST API  
**Target:** 5+ years of US stocks, <100ms queries, 95%+ validation rate

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for production)
- Polygon.io API key ($29.99/mo)

### Local Development

1. **Clone and setup**
   ```bash
   cd market-data-api
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Create .env file**
   ```bash
   cp .env.example .env
   # Edit .env and add your Polygon API key
   ```

3. **Start TimescaleDB**
   ```bash
   docker-compose up -d timescaledb
   # Wait for health check to pass
   ```

4. **Initialize database**
   ```bash
   PGPASSWORD=password psql -h localhost -U postgres -d market_data -f sql/schema.sql
   ```

5. **Run API locally**
   ```bash
   python main.py
   ```

   API will be available at `http://localhost:8000`

6. **View documentation**
   - Swagger UI: `http://localhost:8000/docs`
   - ReDoc: `http://localhost:8000/redoc`

---

## API Endpoints

### Health Check
```bash
GET /health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-09T16:30:00",
  "scheduler_running": true
}
```

### System Status
```bash
GET /api/v1/status
```

Returns database metrics, validation rates, data quality indicators.

### Historical Data
```bash
GET /api/v1/historical/{symbol}?start=YYYY-MM-DD&end=YYYY-MM-DD&validated_only=true&min_quality=0.85
```

Example:
```bash
curl "http://localhost:8000/api/v1/historical/AAPL?start=2022-01-01&end=2023-12-31"
```

Response:
```json
{
  "symbol": "AAPL",
  "start_date": "2022-01-01",
  "end_date": "2023-12-31",
  "count": 504,
  "data": [
    {
      "time": "2022-01-03T00:00:00",
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

---

## Data Validation

Every candle is validated against:

1. **OHLCV Constraints**
   - High ≥ max(open, close)
   - Low ≤ min(open, close)
   - Prices > 0

2. **Price Anomalies**
   - Single-day move < 500%

3. **Gap Detection**
   - Flags potential stock splits (>10% gap non-weekend)
   - Detects market halts and delisting

4. **Volume Anomalies**
   - Flags volume >10x median
   - Flags volume <10% median (delisting warning)

**Quality Score:** 0.0-1.0 (0.85+ = validated)

---

## Scheduled Backfill

Daily auto-backfill runs at **2:00 AM UTC** by default (configurable).

For each symbol:
1. Fetch last 30 days from Polygon.io
2. Validate each candle
3. Insert/update in TimescaleDB
4. Log results to `backfill_history` table

**Rate limit:** 150 req/min (we use ~10/min for daily backfill)

---

## Database Schema

### market_data
Main hypertable (auto-partitioned by time):
- `time` (TIMESTAMPTZ) - Trading timestamp
- `symbol` (VARCHAR) - Stock ticker
- `open, high, low, close` (DECIMAL) - OHLC prices
- `volume` (BIGINT) - Trading volume
- `validated` (BOOLEAN) - Passed quality checks
- `quality_score` (NUMERIC) - 0.0-1.0 rating
- `gap_detected` (BOOLEAN) - Flagged as unusual gap
- `volume_anomaly` (BOOLEAN) - Flagged as volume spike/drought

Indexes:
- (symbol, time DESC) - Fast symbol queries
- (validated) - Filter to validated only
- (gap_detected) - Anomaly review

### validation_log
Audit trail of validation checks per symbol.

### backfill_history
Tracks when backfills ran, success/failure, record counts.

### symbol_status
Current status per symbol (last backfill date, data freshness, quality score).

---

## Configuration

Edit `.env`:

```bash
# Data source
POLYGON_API_KEY=your_key_here

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/market_data
DB_PASSWORD=password

# Logging
LOG_LEVEL=INFO

# API server
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Scheduler
BACKFILL_SCHEDULE_HOUR=2
BACKFILL_SCHEDULE_MINUTE=0
```

---

## Docker Deployment

### Local Development
```bash
docker-compose up -d
```

Both services (TimescaleDB + API) will start together.

```bash
# View logs
docker-compose logs -f api

# Health check
curl http://localhost:8000/health

# Stop
docker-compose down
```

### Using docker-start.sh Helper
```bash
./docker-start.sh up       # Start services
./docker-start.sh status   # Check status
./docker-start.sh logs     # Watch logs
./docker-start.sh test     # Run health checks
./docker-start.sh down     # Stop services
```

### Production Deployment (Proxmox)

**See [DEPLOYMENT.md](DEPLOYMENT.md) for complete step-by-step guide.**

Quick summary:
1. Install Docker + dependencies on Proxmox
2. Clone repo to `/opt/market-data-api`
3. Create `.env` with API keys
4. Build and start: `docker-compose up -d`
5. Install systemd service for auto-start: `sudo cp market-data-api.service /etc/systemd/system/`
6. Setup backup cron: `crontab -e` (add backup.sh to Sunday 3 AM)
7. Monitor with `./monitor.sh`

**Complete checklist:** See [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) (4-5 hours, one-time setup)

---

## Testing

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_validation.py

# Run with coverage
pytest --cov=src tests/
```

---

## Monitoring

### Key Metrics
- **symbols_available**: Number of distinct symbols in DB
- **validation_rate_pct**: % of candles passing quality checks
- **records_with_gaps_flagged**: Potential anomalies to review
- **latest_data**: Most recent candle timestamp

### Check Status
```bash
curl http://localhost:8000/api/v1/status | jq .
```

### View Backfill Logs
```bash
# Via psql
PGPASSWORD=password psql -h localhost -U postgres -d market_data
SELECT * FROM backfill_history ORDER BY backfill_timestamp DESC LIMIT 10;
```

---

## Backup & Recovery

### Automated Backups
Weekly Sunday 3 AM backup to external USB drive:
```bash
pg_dump -h localhost -U postgres market_data | gzip > /mnt/external-backup/market_data_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Manual Backup
```bash
PGPASSWORD=password pg_dump -h localhost -U postgres market_data | gzip > backup.sql.gz
```

### Restore
```bash
gunzip -c backup.sql.gz | PGPASSWORD=password psql -h localhost -U postgres -d market_data
```

---

## Troubleshooting

### API won't start
```bash
# Check if port 8000 is already in use
lsof -i :8000

# Check database connection
PGPASSWORD=password psql -h localhost -U postgres market_data
```

### Backfill failing
```bash
# Check Polygon API key is valid
curl "https://api.polygon.io/v1/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-31?apiKey=$POLYGON_API_KEY" | jq .status

# Check API logs
docker-compose logs api | grep -i error
```

### High memory usage
- TimescaleDB may need restarting (connection pooling issue)
- Check if backfill is running (may consume resources)

### Slow queries
- Verify indexes are created: `SELECT * FROM pg_indexes WHERE tablename='market_data';`
- Consider adding more workers to FastAPI (`API_WORKERS`)

---

## Cost Breakdown

| Item | Cost | Notes |
|---|---|---|
| Polygon.io Starter | $29.99/mo | 150 req/min, sufficient |
| Infrastructure | $0 | Your hardware |
| TimescaleDB | $0 | Open source |
| FastAPI | $0 | Open source |
| **Total** | **~$30/mo** | Scales to 500+ symbols |

---

## Future Roadmap

- **Phase 2:** Multi-timeframe aggregates (1d→5d→1w)
- **Phase 3:** Crypto + FX data (Binance, OANDA)
- **Phase 4:** Pre-computed indicators (RSI, MACD, Bollinger Bands)
- **Phase 5:** ML-based price prediction

Current design supports all expansions without refactoring.

---

## License

Private. For research and analysis use only.

---

## Documentation

- **[PROJECT_IDEA.md](PROJECT_IDEA.md)** - Full specification, architecture, 5-week plan
- **[PROGRESS.md](PROGRESS.md)** - Implementation status (Week 0-4)
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment guide for Proxmox
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Step-by-step deployment checklist
- **[docker-start.sh](docker-start.sh)** - Container management helper script
- **[backup.sh](backup.sh)** - Automated backup script (Sunday 3 AM)
- **[monitor.sh](monitor.sh)** - Real-time system monitoring dashboard
- **[market-data-api.service](market-data-api.service)** - Systemd service template for auto-start

## Key Files

```
market-data-api/
├── main.py                      # FastAPI application
├── Dockerfile                   # Docker image
├── docker-compose.yml           # Service orchestration
├── docker-start.sh              # Container helper
├── backup.sh                    # Automated backups
├── monitor.sh                   # Monitoring dashboard
├── market-data-api.service      # Systemd service
├── requirements.txt             # Python dependencies
├── .env.example                 # Configuration template
├── sql/schema.sql               # Database schema
├── src/
│   ├── clients/polygon_client.py      # Polygon.io API client
│   ├── services/
│   │   ├── validation_service.py      # OHLCV validation
│   │   └── database_service.py        # Database operations
│   ├── models.py                      # Pydantic schemas
│   └── scheduler.py                   # Daily auto-backfill
├── tests/                       # Unit & integration tests (19 tests passing)
├── migrations/                  # Alembic schema versions
└── logs/                        # Application logs
```

## Next Steps

1. Deploy to Proxmox (follow [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md))
2. Monitor first week of auto-backfills
3. Spot-check data quality against Yahoo Finance
4. Expand symbol list in `src/scheduler.py` if needed
5. Plan Phase 2 features (indicators, crypto, etc.)
