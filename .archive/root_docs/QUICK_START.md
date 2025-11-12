# Quick Start - Market Data API

## Current Status: ✓ RUNNING

All services are running and healthy.

---

## Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| **API** | http://localhost:8000 | RESTful API endpoints |
| **Docs** | http://localhost:8000/docs | Swagger API documentation |
| **Dashboard** | http://localhost:3001 | Web UI dashboard |
| **Health** | http://localhost:8000/health | Service health status |

---

## Quick Commands

### Check Service Status
```bash
docker-compose ps
```

### View Logs
```bash
# API logs
docker logs -f market_data_api

# Database logs
docker logs -f market_data_postgres

# Dashboard logs
docker logs -f market_data_dashboard
```

### Stop All Services
```bash
docker-compose down
```

### Start All Services
```bash
docker-compose up -d
```

### Rebuild and Start
```bash
docker-compose down
docker-compose up -d --build
```

### Reset Database (WARNING: Deletes all data)
```bash
docker-compose down -v
docker-compose up -d
```

---

## Test API

### Health Check
```bash
curl http://localhost:8000/health
```

### API Status
```bash
curl http://localhost:8000/api/v1/status
```

### List Symbols
```bash
curl http://localhost:8000/api/v1/symbols
```

### Get Historical Data (once symbols are added)
```bash
curl "http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31"
```

---

## Configuration

Edit `.env` to customize:
- `POLYGON_API_KEY` - Your Polygon.io API key
- `DATABASE_URL` - Database connection string
- `API_PORT` - API port (default: 8000)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `BACKFILL_SCHEDULE_HOUR` - Daily backfill hour (UTC 0-23)
- `BACKFILL_SCHEDULE_MINUTE` - Daily backfill minute (0-59)

**After editing .env, restart the API:**
```bash
docker-compose restart api
```

---

## Database

### Connect to Database
```bash
psql postgresql://market_user:changeMe123@localhost:5432/market_data
```

### View Tables
```bash
docker exec market_data_postgres psql -U market_user -d market_data -c "\dt"
```

### Check Row Counts
```bash
docker exec market_data_postgres psql -U market_user -d market_data -c "
  SELECT 'market_data' as table_name, COUNT(*) as rows FROM market_data
  UNION ALL
  SELECT 'tracked_symbols', COUNT(*) FROM tracked_symbols
  UNION ALL
  SELECT 'api_keys', COUNT(*) FROM api_keys;
"
```

---

## Next Steps

1. **Get Polygon API Key**
   - Visit https://polygon.io
   - Sign up for free tier
   - Copy API key
   - Update in `.env` file

2. **Add Symbols**
   - Use the admin API with a valid X-API-Key header
   - Or use `/api/v1/admin/` endpoints in the docs

3. **Query Data**
   - Once symbols are added, use `/api/v1/historical/` endpoint
   - Data will backfill on the scheduled time or manually

4. **Create API Keys**
   - Use `/api/v1/admin/api-keys` endpoint
   - Distribute keys to client applications

---

## Troubleshooting

### API Won't Start
```bash
# Check logs
docker logs market_data_api

# Common fix: Restart services
docker-compose restart
```

### Database Connection Error
```bash
# Verify PostgreSQL is running
docker ps | grep postgres

# Restart database
docker-compose restart database
docker-compose restart api
```

### "Database migrations failed" Error
```bash
# This usually means permissions issue - already fixed
# If it persists:
docker-compose down -v
docker-compose up -d
```

### Dashboard Not Loading
```bash
# Check Nginx logs
docker logs market_data_dashboard

# Restart dashboard
docker-compose restart dashboard
```

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│          Market Data Warehouse API               │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │  FastAPI │  │ Nginx    │  │Scheduler │     │
│  │  (port   │  │(Dashboard│  │(Backfill)│     │
│  │  8000)   │  │ port     │  │          │     │
│  │          │  │ 3001)    │  │          │     │
│  └────┬─────┘  └─────┬────┘  └────┬─────┘     │
│       │              │            │            │
│       └──────────────┼────────────┘            │
│                      │                         │
│                      ▼                         │
│          ┌──────────────────────┐             │
│          │  PostgreSQL Database  │             │
│          │  (port 5432)          │             │
│          │  - market_data        │             │
│          │  - market_user        │             │
│          └──────────────────────┘             │
│                                                │
└─────────────────────────────────────────────────┘

External:
┌────────────────┐
│  Polygon.io    │  Market data source
│  REST API      │
└────────────────┘
```

---

## Files & Directories

```
MarketDataAPI/
├── .env                          # Configuration (secrets - don't commit!)
├── docker-compose.yml            # Docker services definition
├── Dockerfile                    # API container image
├── main.py                       # FastAPI entry point
├── requirements.txt              # Python dependencies
├── REBUILD_COMPLETE.md           # Rebuild documentation
├── QUICK_START.md               # This file
│
├── src/                          # Application code
│   ├── config.py                # Configuration management
│   ├── models.py                # Data models
│   ├── scheduler.py             # Backfill scheduler
│   ├── services/                # Business logic
│   │   ├── database_service.py
│   │   ├── auth.py
│   │   ├── symbol_manager.py
│   │   └── ... others
│   ├── middleware/              # Request processing
│   └── routes/                  # API endpoints
│
├── database/                     # Database files
│   ├── sql/                     # Initial schema
│   │   ├── init-user.sql
│   │   └── schema.sql
│   └── migrations/              # Schema migrations
│       ├── 001_*.sql
│       └── 002_*.sql
│
├── dashboard/                    # Web UI
│   ├── index.html
│   ├── styles/
│   └── js/
│
└── docs/                         # Documentation
```

---

## Performance Tuning

### Connection Pool
- Configured in `docker-compose.yml`
- Increase `API_WORKERS` for more parallel requests

### Cache
- Query results cached with 5-minute TTL
- Monitor at `/api/v1/performance/cache`

### Database Indexes
- Market data indexed by (symbol, time)
- Validation data indexed by symbol and timestamp
- Check query performance at `/api/v1/performance/queries`

### Backfill Schedule
- Default: 02:00 UTC daily
- Adjust `BACKFILL_SCHEDULE_HOUR` and `BACKFILL_SCHEDULE_MINUTE` in `.env`

---

## Security

- ✓ Database user with minimal required privileges
- ✓ API key authentication for admin endpoints
- ✓ Audit logging for all API key operations
- ✓ CORS enabled for cross-origin requests
- ✓ Secrets in `.env` (excluded from version control)

**Recommendations:**
- Use environment variables for secrets
- Rotate API keys regularly
- Monitor audit logs
- Use HTTPS in production (add reverse proxy)
- Restrict database access to trusted networks

---

**Last Updated**: November 11, 2025
**API Version**: 1.0.0
**Status**: Production Ready
