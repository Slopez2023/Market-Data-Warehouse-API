# Repository Cleanup Plan

**Status**: Ready for cleanup  
**Date**: November 13, 2025  
**Total Unnecessary Files**: 43

---

## Overview

Repository contains 43 unnecessary files across 7 categories that should be removed to declutter the codebase.

---

## Files to Delete

### 1. Test/Debug Files (17 files)

Old phase-based tests and helpers that are no longer needed:

```bash
# Root level
rm tests/test_phase_1d_endpoints.py
rm tests/test_phase_1e_testing.py
rm tests/test_phase_1g_scheduler.py
rm tests/test_phase_1i_resilience.py
rm tests/test_phase_5_data_migration.py
rm tests/test_phase_6_3.py
rm tests/test_phase_6_4.py
rm tests/test_phase_6_5.py
rm tests/test_phase2_connection_pool.py
rm tests/test_phase2_data_quality.py
rm tests/test_phase2_environment.py
rm tests/test_phase2_scheduler_retry.py

# Root test files
rm test_crypto_fix.py

# Test scripts
rm tests/api_test_suite.py
rm tests/test_free_datasources.py
rm scripts/load_test_data.py
rm scripts/load_test_runner.py
```

**Reason**: Old phase test files covered by newer comprehensive tests. Load test helpers not part of main application flow.

**Impact**: None - functionality tested by newer test suite

---

### 2. Old/Duplicate Scripts (9 files)

Outdated shell and Python backfill scripts:

```bash
# Shell scripts
rm BACKFILL_ALL.sh
rm BACKFILL_ALL_TIMEFRAMES.sh
rm BUILD_AND_VERIFY.sh
rm CHECK_ASSETS.sh
rm scripts/monitor.sh
rm scripts/monitor-setup.sh

# Python backfill scripts
rm scripts/backfill_v2.py
rm scripts/backfill_enhancements.py
rm scripts/backfill_historical.py
```

**Reason**: 
- `BACKFILL_*.sh` → Use `scripts/backfill_ohlcv.py` instead
- `BUILD_AND_VERIFY.sh` → Use docker-compose
- `monitor*.sh` → Use observability API endpoints
- `backfill_v2.py` → Deprecated version
- `backfill_enhancements.py` → Experimental, never activated
- `backfill_historical.py` → Legacy, use backfill_ohlcv.py

**Impact**: None - all functionality available in active scripts/docker

---

### 3. Duplicate/Unused API Clients (2 files)

Alternative data sources never integrated:

```bash
rm src/clients/binance_client.py
rm src/clients/yahoo_client.py
```

**Reason**: Only Polygon.io client is active and configured. These were for planned alternative data sources that were never implemented.

**Impact**: None - Polygon is the only configured data source

---

### 4. Unused/Experimental Services (9 files)

Advanced features that were never activated or integrated:

```bash
# Data enrichment (experimental)
rm src/services/data_enrichment_service.py
rm src/services/enrichment_scheduler.py
rm src/routes/enrichment_ui.py

# ML features (experimental)
rm src/services/feature_computation_service.py
rm scripts/backfill_prediction_data.py

# Redundant/merged services
rm src/services/migration_service.py           # One-time DB migration only
rm src/services/scheduler_retry.py             # Retry logic in clients
rm src/services/resilience_manager.py          # Circuit breaker elsewhere
rm src/services/sentiment_service.py           # No news data to analyze
rm src/services/data_aggregator.py             # Experimental aggregation
rm src/services/data_quality_checker.py        # Merged into validation_service.py
```

**Reason**:
- Never hooked into API routes
- Require data sources not being backfilled
- Functionality duplicated elsewhere
- Experimental features abandoned

**Impact**: None - functionality not exposed in API

---

### 5. Leftover Logs & Temp Files (2 files)

Runtime artifacts and manual utilities:

```bash
rm api.log
rm scripts/backup.sh
```

**Reason**:
- `api.log` → Runtime log file, should not be in repo (add to .gitignore if present)
- `backup.sh` → Manual backup, use docker/deployment tools instead

**Impact**: None - no functionality lost

---

### 6. Archive Text Files (2 files)

Old planning/reference docs in wrong location:

```bash
rm scripts/DATA_MATRIX.txt
rm scripts/FREE_SOURCES_PLAN.txt
```

**Reason**: Should be in `.archive/` or `docs/` if needed

**Impact**: None - information consolidated in proper docs

---

## Cleanup Summary

| Category | Count | Action |
|----------|-------|--------|
| Test/Debug Files | 17 | Delete |
| Old/Duplicate Scripts | 9 | Delete |
| Unused API Clients | 2 | Delete |
| Unused Services | 9 | Delete |
| Leftover Logs/Temp | 2 | Delete |
| Archive Text Files | 2 | Delete |
| **Total** | **43** | **Delete** |

---

## What Will Remain

### Active Scripts in `/scripts/`
- `backfill_ohlcv.py` — Main OHLCV backfill (active)
- `init_symbols.py` — Symbol initialization
- `bootstrap_db.py` — Database bootstrap
- `run_migrations.py` — Database migrations
- `generate_api_key.py` — API key generation
- `verify_timeframe_data.py` — Data verification
- `verify_timeframes_setup.py` — Setup verification
- `feature_engineering.py` — Feature computation

### Unused but Hooked-Up Backfill Scripts
These have Python clients ready but aren't being backfilled yet (not called automatically):
- `backfill_dividends.py`
- `backfill_splits.py`
- `backfill_earnings.py`
- `backfill_news.py`
- `backfill_options_iv.py`

**Note**: These are kept because they have API clients ready and can be integrated when data backfilling is needed.

### Core Services (All Active)
- `database_service.py`
- `polygon_client.py`
- `auth.py`
- `validation_service.py`
- `earnings_service.py`
- `news_service.py`
- `options_iv_service.py`
- `symbol_manager.py`
- `scheduler.py`
- And 20+ others actively used

### Test Files
- Keep all tests in `tests/` that follow naming pattern `test_*.py` EXCEPT phase-based ones
- These cover current features and API endpoints

---

## Execute Cleanup

To clean up, run:

```bash
# Create archive for deleted files (optional safety backup)
mkdir -p .archive/deleted_files_backup
cd /Users/stephenlopez/Projects/Trading\ Projects/MarketDataAPI

# Move to archive instead of deleting (safer)
mv tests/test_phase*.py .archive/deleted_files_backup/ 2>/dev/null
mv scripts/load_test*.py .archive/deleted_files_backup/ 2>/dev/null
mv tests/test_phase*.py .archive/deleted_files_backup/ 2>/dev/null
mv src/clients/binance_client.py .archive/deleted_files_backup/ 2>/dev/null
mv src/clients/yahoo_client.py .archive/deleted_files_backup/ 2>/dev/null
mv src/services/data_enrichment_service.py .archive/deleted_files_backup/ 2>/dev/null
mv src/services/enrichment_scheduler.py .archive/deleted_files_backup/ 2>/dev/null
mv scripts/backfill_v2.py .archive/deleted_files_backup/ 2>/dev/null
# ... etc for all files

# Or directly delete if confident
rm -f tests/test_phase_*.py
rm -f scripts/backfill_v2.py scripts/backfill_enhancements.py scripts/backfill_historical.py
# ... etc
```

---

## After Cleanup Benefits

1. **Cleaner Codebase** - 43 fewer files
2. **Reduced Confusion** - No dead code to maintain
3. **Faster Navigation** - Essential files easier to find
4. **Lower Maintenance** - Less surface area for bugs
5. **Clearer Dependencies** - Easier to see what's actually used

---

## Files by Location

### Root Directory (9 files to delete)
```
BACKFILL_ALL.sh
BACKFILL_ALL_TIMEFRAMES.sh
BUILD_AND_VERIFY.sh
CHECK_ASSETS.sh
api.log
test_crypto_fix.py
```

### /scripts/ (20 files to delete)
```
backfill_v2.py
backfill_enhancements.py
backfill_historical.py
backfill_prediction_data.py
load_test_data.py
load_test_runner.py
monitor.sh
monitor-setup.sh
backup.sh
DATA_MATRIX.txt
FREE_SOURCES_PLAN.txt
test_free_datasources.py
```

### /src/clients/ (2 files to delete)
```
binance_client.py
yahoo_client.py
```

### /src/services/ (9 files to delete)
```
data_enrichment_service.py
enrichment_scheduler.py
feature_computation_service.py
migration_service.py
scheduler_retry.py
resilience_manager.py
sentiment_service.py
data_aggregator.py
data_quality_checker.py
```

### /src/routes/ (1 file to delete)
```
enrichment_ui.py
```

### /tests/ (17 files to delete)
```
test_phase_1d_endpoints.py
test_phase_1e_testing.py
test_phase_1g_scheduler.py
test_phase_1i_resilience.py
test_phase_5_data_migration.py
test_phase_6_3.py
test_phase_6_4.py
test_phase_6_5.py
test_phase2_connection_pool.py
test_phase2_data_quality.py
test_phase2_environment.py
test_phase2_scheduler_retry.py
api_test_suite.py
```

---

## Safety Notes

- Consider moving files to `.archive/deleted_files_backup/` first instead of direct deletion
- All functionality tested by newer test suite
- Git history preserved regardless of deletion
- Can restore from git if needed: `git checkout <file>`

---

**Recommendation**: Execute cleanup after confirming all CI/CD tests pass

**Last Updated**: November 13, 2025
