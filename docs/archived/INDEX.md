# Market Data Warehouse API - Complete Documentation Index

**Last Updated:** November 15, 2025 | **Version:** 2.0.0

---

## 📋 Getting Started

Start here to understand the project and get running:

1. **[README.md](README.md)** - Project overview, quick start, and key features
2. **[Installation Guide](/docs/getting-started/INSTALLATION.md)** - Setup and configuration
3. **[Quick Reference](/docs/reference/QUICK_REFERENCE.md)** - Common commands and API calls

---

## 📊 Core Features

### Market Data & Timeframes
- **[Multi-Timeframe Guide](/docs/features/TIMEFRAME_EXPANSION.md)** - 7 timeframes per symbol
- **[Symbols Management](/docs/api/SYMBOLS.md)** - Add, update, and configure symbols
- **[Crypto Support](/docs/api/CRYPTO.md)** - Cryptocurrency data endpoints
- **[Data Schema](/docs/reference/DATA_SOURCES.md)** - OHLCV data structure

### Analytics & Enrichment
- **[Earnings Data](/docs/features/EARNINGS.md)** - Historical earnings with beat rates
- **[News & Sentiment](/docs/features/SENTIMENT.md)** - News sentiment analysis
- **[Options & Volatility](/docs/features/OPTIONS_IV.md)** - Options Greeks and IV
- **[Technical Features](/docs/features/TECHNICAL_FEATURES.md)** - ML-ready feature vectors

### Backfill & Data Management
- **[Master Backfill](/docs/operations/MASTER_BACKFILL.md)** - Primary OHLCV backfill with gap detection
- **[Feature Enrichment](/docs/operations/FEATURE_ENRICHMENT.md)** - Technical indicator computation
- **[Backfill Architecture](/BACKFILL_ARCHITECTURE.md)** - Design and implementation details

---

## 🔐 Security & Management

### Authentication & Authorization
- **[API Authentication](/docs/api/AUTHENTICATION.md)** - API key validation and management
- **[API Key Management](/docs/operations/API_KEY_MANAGEMENT.md)** - CRUD operations and audit logging

### Admin Operations
- **[Symbol Management](/docs/api/SYMBOLS.md)** - Admin endpoints for symbol config
- **[Audit Logging](/docs/operations/AUDIT_LOGGING.md)** - Complete audit trail of operations

---

## 📡 API Reference

### API Endpoints
- **[Full Endpoint Reference](/docs/api/ENDPOINTS.md)** - All 40+ endpoints documented
- **[API Examples](/docs/reference/QUICK_REFERENCE.md)** - Real-world usage examples

### Data Models
- **[Response Schemas](/docs/api/README.md)** - Pydantic models and validation

---

## 🎯 Operations & Monitoring

### Deployment & Infrastructure
- **[Deployment Guide](/docs/operations/DEPLOYMENT.md)** - Docker, Kubernetes, production setup
- **[Troubleshooting](/docs/operations/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Performance Tuning](/docs/operations/PERFORMANCE.md)** - Optimization techniques

### Observability
- **[Monitoring Guide](/docs/operations/MONITORING.md)** - Health checks, metrics, alerting
- **[Observability Index](/docs/observability/OBSERVABILITY_INDEX.md)** - Logging, tracing, metrics
- **[Observability Quickstart](/docs/observability/OBSERVABILITY_QUICKSTART.md)** - Get started with observability

### Performance & Analysis
- **[Performance Monitoring](/docs/operations/PERFORMANCE.md)** - Query analysis and bottleneck detection
- **[Cache Performance](/docs/observability/PERFORMANCE_QUICK_REFERENCE.md)** - Cache hit rates and optimization

---

## 🏗️ Architecture & Development

### System Design
- **[Architecture Overview](/docs/development/ARCHITECTURE.md)** - System design patterns
- **[Architecture Review](/docs/architecture/ARCHITECTURE_REVIEW.md)** - In-depth architectural analysis
- **[Tech Stack](/docs/reference/TECH_STACK.md)** - Technology choices and justification

### Development
- **[Contributing Guide](/docs/development/CONTRIBUTING.md)** - Development workflow
- **[Testing Guide](/docs/development/TESTING.md)** - Running and writing tests
- **[Development Status](/docs/development/DEVELOPMENT_STATUS.md)** - Feature completion status

### Code Organization
- **[Project Structure](#-project-structure)** - Directory organization (see README)

---

## ✅ Project Phases & Milestones

### Phase Overview
- **Phase 1:** Core API with observability ✅
- **Phase 2:** Load testing & optimization ✅
- **Phase 3:** API improvements & performance ✅
- **Phase 4:** Multi-timeframe support ✅
- **Phase 5:** 1-minute candle support ✅
- **Phase 6:** Advanced analytics (earnings, sentiment, options) ✅
- **Phase 7:** Quality metrics and validation ✅

### Phase Documentation
- [Phase 1 Complete](/docs/phases/PHASE_1_COMPLETE.md)
- [Phase 2 Complete](/docs/phases/PHASE_2_COMPLETE.md)
- [Phase 4 Complete](/docs/phases/PHASE_4_COMPLETE.md)
- [Phase 6 Summary](/docs/phases/PHASE_6_SUMMARY.md)

---

## 📚 Reference & Learning

### Quick References
- **[Quick Reference](/docs/reference/QUICK_REFERENCE.md)** - Common commands
- **[Glossary](/docs/reference/GLOSSARY.md)** - Terminology
- **[FAQ](/docs/reference/FAQ.md)** - Frequently asked questions
- **[Data Sources](/docs/reference/DATA_SOURCES.md)** - Data provider information

### Setup & Configuration
- **[Configuration](/docs/getting-started/INSTALLATION.md#-configuration)** - Environment variables
- **[TIMEFRAMES_SETUP.md](/TIMEFRAMES_SETUP.md)** - Timeframe configuration

---

## 🔧 Tools & Scripts

### Database & Migrations
- **Location:** `/database/` - SQL migrations and schema
- **Service:** `src/services/migration_service.py` - Migration runner

### Backfill Scripts
- **`master_backfill.py`** - Master backfill coordinator
- **`backfill_features.py`** - Feature enrichment runner
- **`scripts/backfill_ohlcv.py`** - Core OHLCV backfill
- **`backfill_enrichment_data.py`** - Corporate events backfill
- **`scripts/phase_2_backfill_baseline.py`** - Performance baseline

### Utilities
- **Location:** `/scripts/` - Various utility scripts
- **Dashboard:** `/dashboard/` - Frontend files

---

## 📊 Dashboard

### Features
- Real-time data visualization
- Symbol management interface
- Backfill & enrichment controls
- Performance monitoring
- System status overview

### Access
- **Local:** `http://localhost:3001` (when running Docker)
- **Files:** `/dashboard/` (index.html, script.js, style.css)

---

## 🚀 Command Reference

### Local Development
```bash
# Run API locally
python main.py
# or
uvicorn main:app --reload

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

### Docker Operations
```bash
# Start all services
docker-compose up

# Rebuild images
docker-compose up --build

# Stop services
docker-compose down
```

### Backfill Operations
```bash
# Master backfill (all data)
python master_backfill.py

# Specific symbols
python master_backfill.py --symbols AAPL,BTC

# Feature enrichment
python backfill_features.py

# Specific timeframe
python scripts/backfill_ohlcv.py --timeframe 1m
```

---

## 📋 Standards & Best Practices

### Code Standards
Defined in [AGENTS.md](AGENTS.md):
- **Python:** Type hints, async/await, Pydantic models
- **Naming:** snake_case functions, UPPERCASE constants, CamelCase classes
- **Testing:** pytest with asyncio, comprehensive mocking
- **Documentation:** Docstrings for public functions/classes

### File Organization
- **Source Code:** `/src/` - Main application
- **Tests:** `/tests/` - Test suite
- **Database:** `/database/` - Migrations and schema
- **Documentation:** `/docs/` - All documentation
- **Scripts:** `/scripts/` - Utility scripts
- **Dashboard:** `/dashboard/` - Frontend files
- **Config:** `/config/` - Configuration files

---

## 📞 Support & Resources

### Documentation Structure
```
/docs/
├── api/                 # API reference
├── getting-started/     # Setup guides
├── features/            # Feature documentation
├── operations/          # Operations guides
├── development/         # Developer guides
├── architecture/        # Architecture docs
├── observability/       # Monitoring & logging
├── phases/              # Phase milestones
└── reference/           # Quick references
```

### Getting Help
1. Check the [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md)
2. Browse [FAQ](/docs/reference/FAQ.md)
3. Review [API Examples](/docs/reference/QUICK_REFERENCE.md)
4. Visit interactive API docs at `http://localhost:8000/docs`

---

## 🔄 Workflow & Procedures

### Common Tasks
- **Adding a Symbol:** See [Symbol Management](/docs/api/SYMBOLS.md)
- **Configuring Timeframes:** See [Timeframe Guide](/docs/features/TIMEFRAME_EXPANSION.md)
- **Running Backfill:** See [Master Backfill](/docs/operations/MASTER_BACKFILL.md)
- **Monitoring System:** See [Monitoring Guide](/docs/operations/MONITORING.md)
- **Deploying to Production:** See [Deployment Guide](/docs/operations/DEPLOYMENT.md)

---

## 📈 Project Status Summary

| Area | Status | Notes |
|------|--------|-------|
| **Core API** | ✅ Complete | 40+ endpoints, all production-ready |
| **Data Backfill** | ✅ Complete | Master backfill with gap detection |
| **Analytics** | ✅ Complete | Earnings, sentiment, options, IV |
| **Multi-Timeframe** | ✅ Complete | 7 timeframes with per-symbol config |
| **Testing** | ✅ Complete | 400+ tests, 100% pass rate |
| **Documentation** | ✅ Complete | Comprehensive docs with examples |
| **Deployment** | ✅ Complete | Docker, Docker Compose, Kubernetes-ready |
| **Observability** | ✅ Complete | Structured logging, metrics, alerts |

---

**For questions or issues, consult the appropriate documentation section above or check the [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md).**
