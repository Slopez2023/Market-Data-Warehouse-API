# Agent Guidelines

## Multi-Source Data Strategy

**Two new sources (fallback):**
- Primary: Polygon.io (existing, paid)
- Fallback 1: Yahoo Finance (free, reliable for daily data)
- Fallback 2: Alpha Vantage (future, archival)

**Usage:**
- Triggered on Polygon timeout, rate limit, or poor data quality
- Data tagged with source for audit
- Quality-aware fallback (validates and compares)

**Files:**
- `MULTI_SOURCE_STRATEGY.md` - Design & architecture
- `MULTI_SOURCE_INTEGRATION.md` - Implementation guide
- `src/clients/yahoo_client.py` - Yahoo Finance client
- `src/clients/multi_source_client.py` - Orchestrator with fallback logic

**Integration:**
```python
# Drop-in replacement for PolygonClient
from src.clients.multi_source_client import MultiSourceClient

client = MultiSourceClient(polygon_api_key, enable_fallback=True)
candles, source = await client.fetch_range(symbol, timeframe, start, end)
# Returns: candles list, source ('polygon', 'yahoo', or None)
```

## Database Setup

```bash
# Initialize database with default trading symbols (60: 20 stocks + 20 crypto + 20 ETFs)
python scripts/init_symbols.py

# Initialize only first 10 symbols
python scripts/init_symbols.py --count 10

# Initialize only stocks and ETFs (exclude crypto)
python scripts/init_symbols.py --exclude-asset-type crypto

# Check which symbols exist without modifying database
python scripts/init_symbols.py --check-only

# Clear and reinitialize all symbols
python scripts/init_symbols.py --reset
```

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

## Master Backfill & Feature Enrichment (Current)

```bash
# Master backfill: OHLCV with gap detection & retry
python master_backfill.py                           # All symbols, all timeframes, full history
python master_backfill.py --symbols AAPL,BTC        # Specific symbols
python master_backfill.py --timeframes 1h,1d        # Specific timeframes
python master_backfill.py --days 30                 # Last 30 days only
python master_backfill.py --max-concurrent 5        # Change concurrency (default: 3)

# Feature enrichment: compute technical indicators
python backfill_features.py                         # All symbols, all timeframes
python backfill_features.py --symbols AAPL,BTC      # Specific symbols
python backfill_features.py --timeframes 1h,1d      # Specific timeframes
python backfill_features.py --days 365              # 1 year history (default: 365)
python backfill_features.py --max-concurrent 10     # Parallel enrichment (default: 5)

# Core OHLCV backfill (called by master_backfill.py, also standalone)
python scripts/backfill_ohlcv.py                    # Default: 1d, all symbols
python scripts/backfill_ohlcv.py --timeframe 1m     # 1-minute candles
python scripts/backfill_ohlcv.py --symbols AAPL     # Single symbol
python scripts/backfill_ohlcv.py --start 2024-01-01 --end 2024-01-31  # Date range

# Corporate events enrichment (dividends, earnings, splits)
python backfill_enrichment_data.py                  # Backfill all corporate events

# Data validation & repair: Re-validate unvalidated records (sets quality_score, validated flag)
python repair_unvalidated_data.py                   # All unvalidated records
python repair_unvalidated_data.py --dry-run         # Preview changes without updating DB
python repair_unvalidated_data.py --symbols AAPL    # Specific symbols only
python repair_unvalidated_data.py --timeframes 1d   # Specific timeframes only
python repair_unvalidated_data.py --limit 5000      # First N records only
python repair_unvalidated_data.py --batch-size 500  # Tuning: larger batch = faster but more memory
python repair_unvalidated_data.py --output report.json  # Save detailed report
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
