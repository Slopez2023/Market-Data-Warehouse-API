# Market Data API - Documentation Index

**Status:** Production Ready (Phase 6.5 Complete)  
**Last Updated:** November 10, 2025

---

## Start Here

1. **[README.md](README.md)** — Overview, quick start, features (5 min)
2. **[DEPLOYMENT.md](DEPLOYMENT.md)** — How to run locally or in Docker (5 min)
3. **[docs/README.md](docs/README.md)** — Full documentation structure

---

## Documentation Structure

```
├── README.md                          ← PROJECT OVERVIEW & QUICK START
├── DEPLOYMENT.md                      ← HOW TO RUN THE APP
├── INDEX.md                           ← THIS FILE
└── docs/                              ← FULL DOCUMENTATION
    ├── getting-started/               ← Setup & installation
    │   ├── INSTALLATION.md
    │   ├── QUICKSTART.md
    │   └── SETUP_GUIDE.md
    ├── api/                           ← API reference
    │   ├── ENDPOINTS.md
    │   ├── AUTHENTICATION.md
    │   ├── SYMBOLS.md
    │   └── CRYPTO.md
    ├── operations/                    ← Running & monitoring
    │   ├── DEPLOYMENT.md
    │   ├── MONITORING.md
    │   ├── PERFORMANCE.md
    │   └── TROUBLESHOOTING.md
    ├── development/                   ← Developer guide
    │   ├── ARCHITECTURE.md
    │   ├── TESTING.md
    │   └── CONTRIBUTING.md
    ├── observability/                 ← Logging & metrics
    ├── architecture/                  ← System design
    ├── reference/                     ← Quick reference & FAQ
    ├── phases/                        ← Phase completion docs
    └── QUICK_REFERENCE.md             ← Cheat sheet
```

---

## Quick Navigation by Task

### I want to get the app running
→ **[DEPLOYMENT.md](DEPLOYMENT.md)** (5 min)

### I need the full setup guide
→ **[docs/getting-started/INSTALLATION.md](docs/getting-started/INSTALLATION.md)**

### I need API documentation
→ **[docs/api/ENDPOINTS.md](docs/api/ENDPOINTS.md)**

### I need to deploy to production
→ **[docs/operations/DEPLOYMENT.md](docs/operations/DEPLOYMENT.md)**

### I need to monitor the system
→ **[docs/operations/MONITORING.md](docs/operations/MONITORING.md)**

### I'm developing and need to understand the codebase
→ **[docs/development/ARCHITECTURE.md](docs/development/ARCHITECTURE.md)**

### I need performance tuning info
→ **[docs/operations/PERFORMANCE.md](docs/operations/PERFORMANCE.md)**

### I have a problem
→ **[docs/operations/TROUBLESHOOTING.md](docs/operations/TROUBLESHOOTING.md)**

---

## Key Stats

| Metric | Value |
|--------|-------|
| Total Tests | 347 |
| Pass Rate | 100% |
| API Endpoints | 25+ |
| Supported Symbols | 15+ stocks + crypto |
| Status | Production Ready ✅ |

---

## Project Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1-5 | Testing, Error Handling, Observability, Performance | ✅ Complete |
| 6.1 | Database Initialization | ✅ Complete |
| 6.2 | API Key Management | ✅ Complete |
| 6.3 | Symbol Management | ✅ Complete |
| 6.4 | Comprehensive Tests | ✅ Complete |
| 6.5 | Crypto Support | ✅ Complete |
| 6.6 | Documentation | 🚀 In Progress |

See `.phases/` directory for phase completion details.

---

## Technology Stack

- **API:** FastAPI (Python 3.11)
- **Database:** PostgreSQL with TimescaleDB
- **Data:** Polygon.io
- **Deployment:** Docker & Docker Compose
- **Testing:** pytest (347 tests)
- **Monitoring:** JSON logging, metrics, alerts

---

## Key Endpoints

Once running at `http://localhost:8000`:

- `GET /health` — API health check
- `GET /docs` — Interactive API documentation
- `GET /api/v1/status` — Full system status
- `GET /api/v1/metrics` — Monitoring data
- `GET /dashboard/` — Web UI

---

## Support

**Have a question?**
1. Check [docs/reference/FAQ.md](docs/reference/FAQ.md)
2. See [docs/operations/TROUBLESHOOTING.md](docs/operations/TROUBLESHOOTING.md)
3. Review [DEPLOYMENT.md](DEPLOYMENT.md) for setup issues

**Is documentation wrong or unclear?** Update it and commit. Documentation is canonical.

---

## Archived Documentation

Historical documents are in `.archive/` and `.phases/`:
- Week-by-week progress notes
- Deployment checklists
- Dashboard implementation docs
- Phase completion summaries

**Current operations should reference only the files listed above.**
