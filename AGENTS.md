# Agent Guidelines

## Build & Test Commands

```bash
# Run all tests
pytest tests/ -v

# Run single test file
pytest tests/test_phase_7_timeframe_api.py -v

# Run single test
pytest tests/test_phase_7_timeframe_api.py::TestTimeframeAPI::test_get_historical_data -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run async tests only
pytest tests/ -m asyncio -v

# Start API locally
python main.py
# or
uvicorn main:app --reload
```

## Phase 2: Validation Commands

```bash
# Run ALL load tests (4 scenarios: cached, uncached, variable limits, variable timeframes)
pytest tests/test_phase_2_validation.py -k "load" -v -s

# Run individual load tests
pytest tests/test_phase_2_validation.py::test_load_single_symbol_cached -v -s
pytest tests/test_phase_2_validation.py::test_load_uncached_symbols -v -s
pytest tests/test_phase_2_validation.py::test_load_variable_limits -v -s
pytest tests/test_phase_2_validation.py::test_load_variable_timeframes -v -s

# Generate RTO/RPO definition (creates /tmp/rto_rpo_definition.json)
pytest tests/test_phase_2_validation.py::test_rto_rpo_requirements -v -s

# Run backfill performance baseline (measures 25 symbols × 5 timeframes)
python scripts/phase_2_backfill_baseline.py
```

## Phase 3: Optimization Commands

```bash
# Run Phase 3 optimization tests (10 tests for API improvements)
pytest tests/test_phase_3_optimization.py -v

# Run specific Phase 3 test class
pytest tests/test_phase_3_optimization.py::TestPhase3RetryOptimization -v
pytest tests/test_phase_3_optimization.py::TestPhase3ParallelProcessing -v

# Run Phase 2 baseline again to measure Phase 3 improvements
python scripts/phase_2_backfill_baseline.py

# Monitor backfill with parallel processing enabled
python main.py  # Scheduler runs daily with parallel_backfill=True by default
```

## Architecture

**Tech Stack:** FastAPI (Python 3.11+), PostgreSQL/TimescaleDB, asyncio, Polygon.io API

**Core Structure:**
- `src/` - Main application code
- `src/services/` - Business logic (database, auth, caching, metrics, enrichment)
- `src/routes/` - API endpoint route handlers
- `src/models.py` - Pydantic schemas for validation/serialization
- `src/config.py` - Environment-based configuration
- `src/scheduler.py` - Background job scheduling
- `tests/` - pytest test suite (~400+ tests)
- `database/` - SQL migrations
- `dashboard/` - Static frontend files

**Key Services:** DatabaseService, AuthService, EnrichmentScheduler, PerformanceMonitor, QueryCache, StructuredLogger, AlertManager

## Code Style

**Python/Imports:** Use type hints, organize imports (stdlib → third-party → local), Pydantic BaseModel for schemas, async/await for I/O

**Naming:** snake_case for functions/variables, UPPERCASE for constants (ALLOWED_TIMEFRAMES), CamelCase for classes

**Validation:** Pydantic validators for models, error handling via HTTPException with detail messages, logger.error() for errors

**Formatting:** 4-space indentation, docstrings for public functions/classes, Config class for app configuration

**Testing:** pytest with asyncio support, use fixtures from conftest.py, mock external API calls, mark integration tests with @pytest.mark.integration
