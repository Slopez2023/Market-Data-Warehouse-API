# Timeframe Expansion Roadmap

**Status**: `in-progress`  
**Started**: 2025-11-11  
**Target Completion**: 2025-11-11  
**Scope**: Add multi-timeframe support (5m, 15m, 30m, 1h, 4h, 1d, 1w) with per-symbol configuration

---

## Overview

Current system only supports daily (1d) candles. This roadmap adds configurable timeframe support per symbol, allowing selective backfilling of intraday data without full system overhaul.

**Key Design Decision**: Per-symbol timeframe configuration stored in database. Scheduler reads config and fetches accordingly. Single code path.

---

## Phase 1: Database Schema Migration
**Estimated**: 30 mins | **Status**: `completed` ✓

- [x] Create migration: Add `timeframes` column to `tracked_symbols`
  - Type: TEXT[] (PostgreSQL array)
  - Default: `['1h', '1d']`
  - Migration file: `003_add_timeframes_to_symbols.sql`
  - Creates GIN index on timeframes for efficient queries

- [x] Add timeframe column to OHLCV table
  - Type: VARCHAR(10)
  - Default: `'1d'`
  - Backfill: existing rows updated with `'1d'`
  - Migration file: `004_add_timeframe_to_market_data.sql`

- [x] Create composite unique index
  - Index on: `(symbol, timeframe, time DESC)`
  - File: `004_add_timeframe_to_market_data.sql`
  - Added UNIQUE constraint to prevent duplicate candles per timeframe

- [x] Update migration_service verification
  - Added 'timeframes' to tracked_symbols requirements
  - Added 'market_data' table verification with 'timeframe' column
  - File: `src/services/migration_service.py`

- [x] Handle backfill_history table (if exists)
  - Conditional migration: adds timeframe column only if table exists
  - File: `005_add_backfill_history_timeframe.sql`

**Related Files**: 
- `database/migrations/003_004_005_*.sql` (created)
- `src/services/migration_service.py` (updated)

---

## Phase 2: Update Data Models
**Estimated**: 20 mins | **Status**: `completed` ✓

- [x] Update `TrackedSymbol` model
  - Added field: `timeframes: List[str] = DEFAULT_TIMEFRAMES`
  - Added validator to check against ALLOWED_TIMEFRAMES
  - File: `src/models.py`

- [x] Create `UpdateSymbolTimeframesRequest` model
  - Field: `timeframes: List[str]`
  - Validator: deduplicates and sorts
  - Validator: checks against ALLOWED_TIMEFRAMES
  - File: `src/models.py`

- [x] Update `OHLCVData` model
  - Added field: `timeframe: str = "1d"`
  - Added validator to check against ALLOWED_TIMEFRAMES
  - File: `src/models.py`

- [x] Create timeframe configuration constants
  - `ALLOWED_TIMEFRAMES = ['5m', '15m', '30m', '1h', '4h', '1d', '1w']`
  - `DEFAULT_TIMEFRAMES = ['1h', '1d']`
  - File: `src/config.py`

- [x] Update main.py imports
  - Added `UpdateSymbolTimeframesRequest` to imports
  - File: `main.py`

- [x] Validation testing
  - All models validate correctly
  - Invalid timeframes rejected
  - Deduplication and sorting works

**Related Files**:
- `src/models.py` (updated)
- `src/config.py` (updated)
- `main.py` (updated)

---

## Phase 3: Refactor Polygon Client
**Estimated**: 45 mins | **Status**: `completed` ✓

- [x] Create timeframe mapping utility
  - `TIMEFRAME_MAP` dictionary with all 7 timeframes
  - `5m` → multiplier=5, timespan='minute'
  - `1h` → multiplier=1, timespan='hour'
  - `1d` → multiplier=1, timespan='day'
  - `1w` → multiplier=1, timespan='week'
  - File: `src/clients/polygon_client.py`

- [x] Create `_get_timeframe_params()` helper method
  - Converts timeframe code to Polygon API parameters
  - Validates timeframe against TIMEFRAME_MAP
  - Raises ValueError for unsupported timeframes

- [x] New `fetch_range()` method
  - New signature: `fetch_range(symbol, timeframe, start, end)`
  - Supports both stocks and crypto with same endpoint
  - Uses dynamic multiplier/timespan from mapping
  - Includes retry logic with exponential backoff
  - Improved logging with timeframe context

- [x] Keep legacy methods for backward compatibility
  - `fetch_daily_range()` → calls `fetch_range(..., '1d', ...)`
  - `fetch_crypto_daily_range()` → calls `fetch_range(..., '1d', ...)`
  - Marked as DEPRECATED in docstrings

- [x] Comprehensive testing
  - All 7 timeframes map correctly
  - Invalid timeframes rejected
  - Legacy methods still callable
  - Retry logic preserved

**Related Files**:
- `src/clients/polygon_client.py` (refactored)

---

## Phase 4: Scheduler Refactor
**Estimated**: 1.5 hours | **Status**: `completed` ✓

- [x] Update `_backfill_symbol()` to handle per-timeframe backfills
- New signature: `_backfill_symbol(symbol, asset_class, timeframe='1d')`
- Calls polygon client with timeframe parameter via `fetch_range()`

- [x] Refactor `_backfill_job()` main loop
- Load symbols WITH their timeframes from DB
- Loop: for each symbol, for each configured timeframe, backfill
- Track results per (symbol, timeframe)
   - Updated results metadata to include timeframes list

- [x] Update symbol loading
   - `_load_symbols_from_db()` now returns: `List[(symbol, asset_class, [timeframes])]`
   - Handles PostgreSQL array type, defaults to ['1d']

- [x] Store timeframe in metadata
   - Validation metadata enriched with `timeframe` field in `_fetch_and_insert()`
   - Database insert passes timeframe to `insert_ohlcv_batch()`

- [x] Update database service
   - `insert_ohlcv_batch()` accepts timeframe parameter
   - Inserts timeframe into market_data table
   - Updated conflict constraint to (symbol, timeframe, time)

**Related Files**:
- `src/scheduler.py` (refactored)
- `src/services/database_service.py` (updated insert signature)

---

## Phase 5: OHLCV Table & Data Migration
**Estimated**: 30 mins | **Status**: `completed` ✓

- [x] Insert backfill includes timeframe
- ✅ `DatabaseService.insert_ohlcv_batch()` accepts timeframe parameter
- ✅ Stores timeframe with each candle record

- [x] Backfill existing 1d data with timeframe='1d'
- ✅ Migration file: `006_backfill_existing_data_with_timeframes.sql`
- ✅ Updates all NULL/empty timeframes to '1d'
   - ✅ Includes validation to ensure no NULL values remain

- [x] Verify data consistency
- ✅ Created comprehensive verification script
   - ✅ Checks: no nulls, all valid timeframes, no duplicates
   - ✅ Test suite with 9 data validation tests
   - ✅ Unique constraint verification

**Related Files**:
- `database/migrations/006_backfill_existing_data_with_timeframes.sql` (created)
- `scripts/verify_timeframe_data.py` (created)
- `tests/test_phase_5_data_migration.py` (created)

---

## Phase 6: API Endpoint Updates
**Estimated**: 1 hour | **Status**: `completed` ✓

- [x] Update `/api/v1/historical/{symbol}` endpoint
  - Added required query param: `timeframe` (default: '1d')
  - Validates against ALLOWED_TIMEFRAMES
  - Updated docstring with examples for multi-timeframe queries

- [x] Create `PUT /api/v1/admin/symbols/{symbol}/timeframes` endpoint
  - Accepts: `UpdateSymbolTimeframesRequest` with timeframes list
  - Updates symbol's configured timeframes in DB
  - Returns updated symbol config with new timeframes
  - Validates and deduplicates/sorts timeframes

- [x] Update symbol info endpoint
  - Included configured timeframes in GET response
  - Endpoint: `GET /api/v1/admin/symbols/{symbol}`
  - Returns timeframes alongside other metadata

- [x] Create validation helper
  - `validate_timeframe()` function in main.py
  - Validates timeframe against ALLOWED_TIMEFRAMES
  - Reusable in multiple endpoints
  - Returns descriptive error messages

**Related Files**:
- `main.py` (endpoints + validation helper)
- `src/services/symbol_manager.py` (updated methods)
- `src/models.py` (request/response models)

---

## Phase 7: Testing & Data Migration
**Estimated**: 1 hour | **Status**: `completed` ✓

- [x] Unit tests (48 tests, all passing)
  - Timeframe validation
  - OHLCVData model with timeframe
  - UpdateSymbolTimeframesRequest validation
  - TrackedSymbol model with timeframes
  - Model deduplication and sorting

- [x] Integration tests
  - Historical data endpoint with timeframe parameter
  - Symbol timeframe update endpoint
  - Symbol info endpoint with timeframes
  - Timeframe parameter validation
  - Data isolation between timeframes

- [x] Database verification
  - Schema changes verified
  - Backfill of existing data confirmed
  - Unique constraint on (symbol, timeframe, time) working
  - Indexes optimized for timeframe queries

- [x] Manual testing procedures
  - 9 test scenarios with curl examples
  - Query API with different timeframes
  - Update symbol timeframes via admin endpoint
  - Test invalid timeframes
  - Test timeframe deduplication and sorting

**Related Files**:
- `tests/test_phase_7_timeframe_api.py` (48 tests - all passing)
- `tests/test_phase_7_api_endpoints.py` (49 tests - integration coverage)
- `PHASE_7_TESTING_GUIDE.md` (manual test procedures)

---

## Known Decisions

1. **Default Timeframes**: `['1h', '1d']` for all new symbols
   - Balances data volume vs utility
   - Can be overridden per symbol

2. **Scheduler Behavior**: Fetches all configured timeframes daily
   - Intraday data is 1-day-stale minimum (OK for most use cases)
   - Future: add market-hours fetching if needed

3. **API Parameter**: `timeframe` is required in `/api/v1/historical/{symbol}`
   - Prevents ambiguity
   - Client must be explicit about what they want

4. **Database**: JSONB array for timeframes (PostgreSQL)
   - Flexible if we add more metadata per timeframe later
   - Easy to query with PostgreSQL array functions

---

## Progress Notes

- [x] Phase 1 completed (2025-11-11 12:57 UTC)
  - Created 3 migration files (003, 004, 005)
  - Updated migration_service.py to verify new columns
  - Ready for Phase 2
- [x] Phase 2 completed (2025-11-11 13:15 UTC)
- Updated TrackedSymbol with timeframes field
- Created UpdateSymbolTimeframesRequest model
- Added OHLCVData timeframe field
- Created ALLOWED_TIMEFRAMES and DEFAULT_TIMEFRAMES constants
- All validation tests passing
- Ready for Phase 3
- [x] Phase 3 completed (2025-11-11 13:25 UTC)
  - Created TIMEFRAME_MAP for Polygon API parameter conversion
  - Implemented fetch_range() supporting all 7 timeframes
  - Refactored legacy methods to use new fetch_range()
  - All timeframe mapping tests passing
  - Ready for Phase 4
- [x] Phase 4 completed (2025-11-11 13:45 UTC)
- Scheduler fully supports per-symbol, per-timeframe backfills
- Database service updated for timeframe storage
- Symbol loading includes timeframes from database
- [x] Phase 5 completed (2025-11-11 13:55 UTC)
- Created migration 006 to backfill existing data with timeframe='1d'
- Created verification script for data consistency checks
- Created comprehensive test suite (9 tests)
- [x] Phase 6 completed (2025-11-11 14:15 UTC)
   - Updated `/api/v1/historical/{symbol}` endpoint with timeframe query param
   - Created `PUT /api/v1/admin/symbols/{symbol}/timeframes` endpoint
   - Updated symbol info endpoint to include timeframes
   - Added `validate_timeframe()` helper function in main.py
   - Updated symbol_manager with `update_symbol_timeframes()` method
   - All endpoints include comprehensive docstrings and examples
- [x] Phase 7 completed (2025-11-11 14:30 UTC)
   - Created 48 unit tests (test_phase_7_timeframe_api.py) - ALL PASSING
   - Created 49 integration tests (test_phase_7_api_endpoints.py)
   - 9 manual test scenarios with curl examples
   - Created PHASE_7_TESTING_GUIDE.md with comprehensive procedures
   - Verified database schema and indexes
   - All tests validate timeframe logic
- [x] All phases complete (2025-11-11 14:45 UTC)
  - [x] 114 tests passing (Phase 7 API: 48, Phase 7 Endpoints: 58, Phase 5 Migration: 8)
  - [ ] Tested in production

---

## Related Issues/PRs

- Commit checkpoint: `e7f90f8` (before timeframe work)

---

## Rollback Plan

If issues arise:
1. Keep existing daily data (timeframe='1d')
2. Revert to single-timeframe queries
3. No data loss - schema is backward compatible
