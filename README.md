# Market Data Warehouse API

**Production-Ready | Enterprise Grade | All Tests Passing** ✅

A comprehensive market data API serving stocks, ETFs, and cryptocurrency data with multi-timeframe support, advanced analytics (earnings, sentiment, options), API key management, performance monitoring, and full observability.

---

## Quick Start

Get up and running in 5 minutes with Docker Compose:

```bash
# 1. Clone and setup
git clone https://github.com/Slopez2023/Market-Data-Warehouse-API
cd MarketDataAPI

# 2. Configure environment
cp .env.example .env
# Edit .env with your POLYGON_API_KEY and DB_PASSWORD

# 3. Start all services (PostgreSQL, API, Dashboard)
docker-compose up
```

**Services available at:**
- **API**: `http://localhost:8000`
- **Interactive Docs**: `http://localhost:8000/docs`
- **Dashboard**: `http://localhost:3001`
- **Database**: `localhost:5432`

See [Installation Guide](/docs/getting-started/INSTALLATION.md) for detailed setup.

---

## What's Included

### 📊 Market Data
- **Real-time & historical data** from Polygon.io
- **Multi-timeframe support**: 5m, 15m, 30m, 1h, 4h, 1d, 1w candles
- **Per-symbol configuration**: Different timeframes for each symbol
- **OHLCV data**: Open, High, Low, Close, Volume with validation
- **60+ symbols**: 20+ stocks, 20+ cryptos, 20+ ETFs

### 📈 Advanced Analytics
- **Earnings data**: Historical earnings with beat/miss rates and surprises
- **News sentiment**: Articles with sentiment scoring for symbols
- **Options & IV**: Implied volatility, Greeks, volatility regime classification
- **Composite features**: ML-ready feature vectors combining all metrics

### 🔐 Enterprise Security & Management
- **API key management**: Full CRUD with audit logging
- **Request authentication**: Middleware-based API key validation
- **Audit trail**: Complete history of all API key operations
- **Rate limiting**: Request throttling and validation

### ⚡ Performance & Optimization
- **Query result caching**: TTL-based cache with hit rates
- **Connection pooling**: Optimized database connections
- **Async/await**: Full async implementation throughout
- **Performance monitoring**: Bottleneck detection and metrics

### 🎯 Observability & Monitoring
- **Structured JSON logging**: Trace IDs across requests
- **Metrics collection**: Requests, errors, latency, cache stats
- **Alert management**: Configurable thresholds and handlers
- **Real-time dashboards**: Monitor system health and performance

### ✅ Quality & Reliability
- **Data validation**: Automatic OHLCV data quality checks
- **Anomaly detection**: Price/volume spike detection
- **Consistency checks**: Gap detection and data integrity
- **Quality scoring**: Per-candle quality metrics (0-1)
- **Comprehensive testing**: 400+ tests, 100% pass rate

---

## Key Features by Category

### Historical Data & Timeframes
```bash
# Get daily data for a symbol
curl "http://localhost:8000/api/v1/historical/AAPL?timeframe=1d&start=2024-01-01&end=2024-12-31"

# Get hourly data with validation filters
curl "http://localhost:8000/api/v1/historical/BTC?timeframe=1h&start=2024-01-01&end=2024-01-31&validated_only=true&min_quality=0.9"

# List available symbols
curl "http://localhost:8000/api/v1/symbols"

# Get detailed symbol stats
curl "http://localhost:8000/api/v1/symbols/detailed"
```

### Symbol & Timeframe Management (Admin)
```bash
# Add a new symbol to track
curl -X POST "http://localhost:8000/api/v1/admin/symbols" \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "NVDA",
    "name": "NVIDIA",
    "asset_type": "stock",
    "timeframes": ["1h", "1d"]
  }'

# Update symbol timeframes
curl -X PUT "http://localhost:8000/api/v1/admin/symbols/NVDA/timeframes" \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"timeframes": ["5m", "1h", "4h", "1d"]}'
```

### Analytics Endpoints
```bash
# Get earnings history
curl "http://localhost:8000/api/v1/earnings/AAPL?days=365&limit=20"

# Get earnings summary with beat rates
curl "http://localhost:8000/api/v1/earnings/AAPL/summary"

# Get upcoming earnings
curl "http://localhost:8000/api/v1/earnings/upcoming?days=30"

# Get news with sentiment
curl "http://localhost:8000/api/v1/news/AAPL?days=30&limit=50"

# Get sentiment aggregate
curl "http://localhost:8000/api/v1/sentiment/AAPL?days=30"

# Compare sentiment across symbols
curl "http://localhost:8000/api/v1/sentiment/compare?symbols=AAPL,MSFT,GOOGL&days=30"

# Get options IV data
curl "http://localhost:8000/api/v1/options/iv/AAPL"

# Get volatility regime
curl "http://localhost:8000/api/v1/volatility/regime/AAPL"

# Get composite ML features
curl "http://localhost:8000/api/v1/features/composite/AAPL"

# Get feature importance weights
curl "http://localhost:8000/api/v1/features/importance"
```

### API Key Management (Admin)
```bash
# Create API key
curl -X POST "http://localhost:8000/api/v1/admin/api-keys" \
  -H "X-API-Key: your-admin-key" \
  -d '{"name": "mobile-app"}'

# List API keys
curl "http://localhost:8000/api/v1/admin/api-keys" \
  -H "X-API-Key: your-admin-key"

# Get audit log for a key
curl "http://localhost:8000/api/v1/admin/api-keys/{key_id}/audit" \
  -H "X-API-Key: your-admin-key"

# Update API key
curl -X PUT "http://localhost:8000/api/v1/admin/api-keys/{key_id}" \
  -H "X-API-Key: your-admin-key" \
  -d '{"name": "mobile-app-v2"}'

# Delete API key
curl -X DELETE "http://localhost:8000/api/v1/admin/api-keys/{key_id}" \
  -H "X-API-Key: your-admin-key"
```

### Monitoring & Operations
```bash
# System health check
curl "http://localhost:8000/health"

# Complete status with database metrics
curl "http://localhost:8000/api/v1/status"

# Observability metrics
curl "http://localhost:8000/api/v1/observability/metrics"

# Alert status
curl "http://localhost:8000/api/v1/observability/alerts"

# Cache performance stats
curl "http://localhost:8000/api/v1/performance/cache"

# Query performance analysis
curl "http://localhost:8000/api/v1/performance/queries"

# System health summary
curl "http://localhost:8000/api/v1/performance/summary"

# System metrics
curl "http://localhost:8000/api/v1/metrics"
```

### Testing
```bash
# Run all tests via API
curl "http://localhost:8000/api/v1/tests/run"
```

---

## Documentation

**📘 [Complete Documentation Index](INDEX.md)** ← Full navigation

Quick links:
- [Installation & Setup](/docs/getting-started/INSTALLATION.md)
- [API Reference](/docs/api/ENDPOINTS.md)
- [Multi-Timeframe Guide](/docs/features/TIMEFRAME_EXPANSION.md)
- [Deployment Guide](/docs/operations/DEPLOYMENT.md)
- [Monitoring & Observability](/docs/operations/MONITORING.md)
- [Troubleshooting](/docs/operations/TROUBLESHOOTING.md)
- [FAQ](/docs/reference/FAQ.md)
- [Architecture](/docs/development/ARCHITECTURE.md)

---

## Project Architecture

```
MarketDataAPI/
├── src/
│   ├── clients/              # External API clients (Polygon.io, etc.)
│   ├── middleware/           # Request/response middleware
│   ├── services/             # Business logic services
│   │   ├── database_service.py       # Data persistence
│   │   ├── auth.py                   # API key authentication
│   │   ├── symbol_manager.py         # Symbol lifecycle management
│   │   ├── caching.py                # Query result caching
│   │   ├── metrics.py                # Metrics collection
│   │   ├── structured_logging.py     # JSON logging with trace IDs
│   │   ├── alerting.py               # Alert management
│   │   ├── performance_monitor.py    # Performance analysis
│   │   ├── news_service.py           # News & sentiment
│   │   ├── earnings_service.py       # Earnings data
│   │   ├── options_iv_service.py     # Options & volatility
│   │   └── feature_service.py        # ML features
│   ├── models.py             # Pydantic models & schemas
│   ├── config.py             # Configuration management
│   └── scheduler.py          # Auto-backfill scheduler
├── tests/                    # Test suite (400+ tests)
├── database/                 # SQL migrations
├── dashboard/                # Frontend dashboard
├── docs/                     # Complete documentation
├── config/                   # Configuration files
└── scripts/                  # Utility & backfill scripts
```

---

## Project Status

| Component | Status | Details |
|-----------|--------|---------|
| Core API | ✅ Complete | All endpoints production-ready |
| Market Data | ✅ Complete | 60+ symbols with OHLCV data |
| Multi-Timeframe | ✅ Complete | 7 timeframes (5m-1w) with per-symbol config |
| Analytics | ✅ Complete | Earnings, sentiment, options, IV, features |
| API Key Management | ✅ Complete | Full CRUD with audit logging |
| Authentication | ✅ Complete | Middleware-based validation |
| Observability | ✅ Complete | Structured logging, metrics, alerts |
| Testing | ✅ Complete | 400+ tests, 100% pass rate |
| Caching | ✅ Complete | Query-level TTL caching |
| Performance | ✅ Complete | Connection pooling, async/await |
| Documentation | ✅ Complete | Comprehensive docs with examples |
| Deployment | ✅ Complete | Docker Compose, Kubernetes-ready |

---

## Quick Stats

| Metric | Value |
|--------|-------|
| **API Endpoints** | 40+ |
| **Tests** | 400+ passing |
| **Pass Rate** | 100% ✅ |
| **Supported Timeframes** | 7 (5m, 15m, 30m, 1h, 4h, 1d, 1w) |
| **Symbols** | 60+ (stocks, ETFs, crypto) |
| **Response Time** | <100ms (cached) |
| **Database** | PostgreSQL with TimescaleDB |
| **Code Coverage** | Comprehensive |

---

## Technology Stack

**Backend**
- Python 3.11+ with FastAPI
- PostgreSQL with TimescaleDB
- Async/await with asyncio
- Polygon.io API integration

**Monitoring & Observability**
- Structured JSON logging
- Real-time metrics collection
- Alert management (log, email)
- Performance monitoring

**Testing & Quality**
- pytest (400+ tests)
- Async test support
- Comprehensive mocking
- Full coverage of critical paths

**Deployment**
- Docker & Docker Compose
- Kubernetes-ready
- Environment-based configuration
- Health checks & metrics endpoints

---

## Development

### Running Tests

```bash
# All tests (400+ passing)
pytest tests/ -v

# Specific test file
pytest tests/test_phase_7_timeframe_api.py -v

# With coverage report
pytest tests/ --cov=src --cov-report=html

# Run tests via API
curl http://localhost:8000/api/v1/tests/run
```

### Project Structure

The codebase follows a clean, modular architecture:

- **Services**: Business logic is abstracted into services (auth, caching, metrics)
- **Middleware**: Request/response processing (authentication, observability)
- **Models**: Pydantic schemas for type safety and validation
- **Clients**: External integrations (Polygon.io)
- **Database**: SQL migrations and persistence layer

See [Architecture](/docs/development/ARCHITECTURE.md) for detailed design patterns.

---

## Configuration

All configuration is environment-based:

```bash
# Core API
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your-password
DB_NAME=market_data

# External APIs
POLYGON_API_KEY=your-polygon-key

# Scheduler
BACKFILL_SCHEDULE_HOUR=0
BACKFILL_SCHEDULE_MINUTE=0

# Observability
LOG_LEVEL=INFO

# Alerts (optional)
ALERT_EMAIL_ENABLED=false
SMTP_SERVER=smtp.gmail.com
ALERT_FROM_EMAIL=your-email@gmail.com
```

See [Installation Guide](/docs/getting-started/INSTALLATION.md) for full configuration details.

---

## Support & Getting Help

1. **Documentation**: Start with the [Documentation Index](INDEX.md)
2. **API Examples**: See [Quick Reference](/docs/reference/QUICK_REFERENCE.md)
3. **Issues**: Check [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md)
4. **FAQ**: Browse [Frequently Asked Questions](/docs/reference/FAQ.md)
5. **Interactive Docs**: Visit `http://localhost:8000/docs` when running

---

## Status & Last Updates

| Item | Status |
|------|--------|
| **Last Updated** | November 15, 2025 |
| **Current Version** | 2.0.0 |
| **Production Ready** | Yes ✅ |
| **All Tests Passing** | Yes (100%) ✅ |
| **Test Count** | 400+ |
| **Dashboard** | Enhanced with bulk operations ✅ |
| **Backfill System** | Master backfill with feature enrichment ✅ |
| **Multi-Timeframe** | 7 timeframes (5m, 15m, 30m, 1h, 4h, 1d, 1w) ✅ |

---

## See Also

- [Complete Documentation Index](INDEX.md)
- [Installation Guide](/docs/getting-started/INSTALLATION.md)
- [API Endpoints Reference](/docs/api/ENDPOINTS.md)
- [Development Status](/docs/development/DEVELOPMENT_STATUS.md)
