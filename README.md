# Market Data Warehouse API

**Production-Ready | Enterprise Grade | 359 Tests | 100% Pass Rate** ✅

A comprehensive market data API serving stocks and cryptocurrency data from Polygon.io with authentication, performance optimization, and observability.

---

## Quick Start

Get up and running in 5 minutes with Docker Compose:

```bash
# 1. Clone and setup
git clone <repo>
cd MarketDataAPI

# 2. Configure environment
cp .env.example .env
# Edit .env with your POLYGON_API_KEY and DB_PASSWORD

# 3. Start all services (PostgreSQL, API, Dashboard)
docker-compose up
```

**Services available at:**
- **API**: `http://localhost:8000`
- **Dashboard**: `http://localhost:3001`
- **Database**: `localhost:5432`

All services are managed together via Docker Compose. See [Installation Guide](/docs/getting-started/INSTALLATION.md) for detailed setup.

---

## Documentation

**📘 [Complete Documentation Index](INDEX.md)** ← Start here for organized docs

Quick links:
- [Installation & Setup](/docs/getting-started/INSTALLATION.md)
- [API Reference](/docs/api/ENDPOINTS.md)
- [Deployment](/docs/operations/DEPLOYMENT.md)
- [Troubleshooting](/docs/operations/TROUBLESHOOTING.md)
- [FAQ](/docs/reference/FAQ.md)

---

## Key Features

✅ **Market Data**
- Real-time and historical data from Polygon.io
- Support for 15+ US stocks
- Full cryptocurrency support (Bitcoin, Ethereum, etc.)
- OHLCV (Open, High, Low, Close, Volume) data
- **Multi-timeframe support** (5m, 15m, 30m, 1h, 4h, 1d, 1w)
- **Per-symbol timeframe configuration** - Configure different timeframes for each symbol
- **Historical data queries by timeframe** - Query `/api/v1/historical/{symbol}?timeframe=1h`
- **Admin endpoints** - `PUT /api/v1/admin/symbols/{symbol}/timeframes` to manage timeframes

✅ **Authentication & Security**
- API key management with CRUD operations
- Audit logging for all API key operations
- Rate limiting and request validation
- Middleware-based request authentication

✅ **Performance**
- Query result caching with TTL
- Connection pool optimization
- Performance monitoring with bottleneck detection
- Load testing framework included

✅ **Observability**
- Structured JSON logging with trace IDs
- Metrics collection (requests, errors, latency)
- Alert management with configurable thresholds
- Real-time monitoring endpoints

✅ **Data Quality**
- Automatic validation of market data
- Anomaly detection (price/volume spikes)
- Data consistency checks
- Quality scoring system

✅ **Enterprise Grade**
- 359 comprehensive tests (100% pass rate)
- Retry logic with exponential backoff
- Circuit breaker pattern
- Full async/await implementation

---

## Project Status

| Phase | Component | Status | Tests |
|-------|-----------|--------|-------|
| 1 | Testing Framework | ✅ Complete | 50 |
| 2 | Error Handling & Quality | ✅ Complete | 88 |
| 3 | Deployment | ✅ Complete | - |
| 4 | Observability | ✅ Complete | 29 |
| 5 | Performance & Load Testing | ✅ Complete | 13 |
| 6.1 | Database Initialization | ✅ Complete | 10 |
| 6.2 | API Key Management | ✅ Complete | 70 |
| 6.3 | Symbol Management | ✅ Complete | 19 |
| 6.4 | Comprehensive Tests | ✅ Complete | 124 |
| 6.5 | Crypto Support | ✅ Complete | 24 |
| 6.6 | Documentation | ✅ Complete | - |
| 7 | Multi-Timeframe Support | ✅ Complete | 114 |

**Overall**: ✅ Production Ready (All Phases 1-7 Complete, 473 Tests Passing)

---

## Quick Stats

| Metric | Value |
|--------|-------|
| Total Tests | 473 passing |
| Pass Rate | 100% ✅ |
| Code Coverage | Comprehensive |
| Supported Symbols | 15+ stocks + crypto |
| Supported Timeframes | 7 (5m, 15m, 30m, 1h, 4h, 1d, 1w) |
| API Endpoints | 25+ |
| Database Records | 18,359+ |
| Response Time | <100ms (cached) |

---

## Technology Stack

**Backend**
- Python 3.x with FastAPI
- PostgreSQL with TimescaleDB
- Polygon.io API integration

**Monitoring**
- Structured logging (JSON)
- Real-time metrics collection
- Alert management system

**Testing**
- pytest (359 tests, 100% passing)
- Async test support
- Comprehensive mocking

**Deployment**
- Docker & Docker Compose
- Kubernetes-ready
- Environment-based configuration

---

## Development

### Run Tests
```bash
# All tests (473 passing)
pytest tests/ -v

# Specific phase (e.g., timeframe tests)
pytest tests/test_phase_7_timeframe_api.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### Project Structure
```
├── src/                 # Application code
├── tests/               # Test suite (359 tests, 100% passing)
├── docs/                # Documentation
├── database/            # SQL migrations
├── config/              # Configuration
├── scripts/             # Utility scripts
└── infrastructure/      # Docker & deployment
```

See [Project Structure](/docs/development/ARCHITECTURE.md) for details.

---

## Support

- **Documentation**: See `/docs/` directory
- **Issues**: Check [Troubleshooting](/docs/operations/TROUBLESHOOTING.md)
- **FAQ**: See [Frequently Asked Questions](/docs/reference/FAQ.md)
- **Development**: See [Contributing Guide](/docs/development/CONTRIBUTING.md)

---

## Status

**Last Updated**: November 11, 2025  
**Current Version**: Phase 7 Complete - Multi-Timeframe Support  
**Test Status**: 473/473 tests passing (100%) ✅  
**Production Ready**: Yes ✅

For complete documentation, see [INDEX.md](INDEX.md)  
For detailed development status, see [Development Status](/docs/development/DEVELOPMENT_STATUS.md)
