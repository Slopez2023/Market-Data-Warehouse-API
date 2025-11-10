# Market Data Warehouse API

**Production-Ready | Enterprise Grade | 359 Tests | 100% Pass Rate** ✅

A comprehensive market data API serving stocks and cryptocurrency data from Polygon.io with authentication, performance optimization, and observability.

---

## Quick Start

Get up and running in 5 minutes:

```bash
# 1. Clone and setup
git clone <repo>
cd MarketDataAPI
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
export DATABASE_URL="postgresql://user:pass@localhost:5432/marketdata"
export POLYGON_API_KEY="your_api_key"

# 4. Start the application
python main.py
```

API available at: `http://localhost:8000`  
Dashboard available at: `http://localhost:3000`

For detailed setup, see [Installation Guide](/docs/getting-started/INSTALLATION.md)

---

## Documentation

### Getting Started
- [**Installation**](/docs/getting-started/INSTALLATION.md) - Setup instructions
- [**Quick Setup**](/docs/getting-started/SETUP_GUIDE.md) - Configuration guide
- [**5-Minute Quickstart**](/docs/getting-started/QUICKSTART.md) - Fastest way to get running

### API Reference
- [**Endpoints**](/docs/api/ENDPOINTS.md) - Complete API reference
- [**Authentication**](/docs/api/AUTHENTICATION.md) - API key management
- [**Symbols**](/docs/api/SYMBOLS.md) - Symbol management and filtering
- [**Crypto**](/docs/api/CRYPTO.md) - Cryptocurrency symbols and endpoints

### Operations
- [**Deployment**](/docs/operations/DEPLOYMENT.md) - Production deployment
- [**Monitoring**](/docs/operations/MONITORING.md) - Observability & monitoring
- [**Performance**](/docs/operations/PERFORMANCE.md) - Performance tuning
- [**Troubleshooting**](/docs/operations/TROUBLESHOOTING.md) - Common issues

### Development
- [**Architecture**](/docs/development/ARCHITECTURE.md) - System design
- [**Contributing**](/docs/development/CONTRIBUTING.md) - Development workflow
- [**Testing**](/docs/development/TESTING.md) - Test suite & best practices

### Reference
- [**Quick Reference**](/docs/reference/QUICK_REFERENCE.md) - Command cheat sheet
- [**FAQ**](/docs/reference/FAQ.md) - Frequently asked questions
- [**Glossary**](/docs/reference/GLOSSARY.md) - Terms and definitions

---

## Key Features

✅ **Market Data**
- Real-time and historical data from Polygon.io
- Support for 15+ US stocks
- Full cryptocurrency support (Bitcoin, Ethereum, etc.)
- OHLCV (Open, High, Low, Close, Volume) data

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

**Overall**: ✅ Production Ready (All Phases 1-6.6 Complete)

---

## Quick Stats

| Metric | Value |
|--------|-------|
| Total Tests | 359 passing |
| Pass Rate | 100% ✅ |
| Code Coverage | Comprehensive |
| Supported Symbols | 15+ stocks + crypto |
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
# All tests
pytest tests/ -v

# Specific phase
pytest tests/test_phase_6_4.py tests/test_phase_6_5.py -v

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

**Last Updated**: November 10, 2025  
**Current Version**: Phase 6.6 Complete - All Tests Passing  
**Test Status**: 359/359 tests passing (100%) ✅  
**Production Ready**: Yes ✅

For detailed development status, see [Development Status](/docs/reference/DEVELOPMENT_STATUS.md)
