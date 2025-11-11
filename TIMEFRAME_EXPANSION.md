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
**Estimated**: 20 mins | **Status**: `todo`

- [ ] Update `TrackedSymbol` model
  - Add field: `timeframes: List[str] = ['1h', '1d']`
  - File: `src/models.py`

- [ ] Create `UpdateSymbolTimeframesRequest` model
  - Field: `timeframes: List[str]`
  - Validation: check against allowed list

- [ ] Create `TimeframeConfig` constant/enum
  - Allowed: `['5m', '15m', '30m', '1h', '4h', '1d', '1w']`
  - Store in `src/config.py`

**Related Files**:
- `src/models.py`
- `src/config.py`

---

## Phase 3: Refactor Polygon Client
**Estimated**: 45 mins | **Status**: `todo`

- [ ] Create timeframe mapping utility
  - `5m` → multiplier=5, timespan='minute'
  - `1h` → multiplier=1, timespan='hour'
  - `1d` → multiplier=1, timespan='day'
  - `1w` → multiplier=1, timespan='week'
  - File: `src/clients/polygon_client.py`

- [ ] Refactor `fetch_daily_range()` → `fetch_range()`
  - New signature: `fetch_range(symbol, timeframe, start, end)`
  - Support both stocks and crypto
  - Keep retry logic

- [ ] Update both stock and crypto endpoints
  - Both use same aggs endpoint with dynamic timespan
  - Test with multiple timeframes

**Related Files**:
- `src/clients/polygon_client.py`

---

## Phase 4: Scheduler Refactor
**Estimated**: 1.5 hours | **Status**: `todo`

- [ ] Update `_backfill_symbol()` to handle per-timeframe backfills
  - New signature: `_backfill_symbol(symbol, asset_class, timeframe)`
  - Calls polygon client with timeframe parameter

- [ ] Refactor `_backfill_job()` main loop
  - Load symbols WITH their timeframes from DB
  - Loop: for each symbol, for each configured timeframe, backfill
  - Track results per (symbol, timeframe)

- [ ] Update symbol loading
  - `_load_symbols_from_db()` now returns: `List[(symbol, asset_class, [timeframes])]`

- [ ] Store timeframe in metadata
  - Validation metadata includes `timeframe` field
  - Database insert includes timeframe

**Related Files**:
- `src/scheduler.py`

---

## Phase 5: OHLCV Table & Data Migration
**Estimated**: 30 mins | **Status**: `todo`

- [ ] Insert backfill includes timeframe
  - Update `DatabaseService.insert_ohlcv_batch()` 
  - Accept timeframe parameter, store in records

- [ ] Backfill existing 1d data with timeframe='1d'
  - Migration script or database update query
  - Run once to populate timeframe column for existing data

- [ ] Verify data consistency
  - Query check: no nulls in timeframe column
  - Check unique constraint works

**Related Files**:
- `src/services/database_service.py`
- `database/migrations/`

---

## Phase 6: API Endpoint Updates
**Estimated**: 1 hour | **Status**: `todo`

- [ ] Update `/api/v1/historical/{symbol}` endpoint
  - Add required query param: `timeframe` (default or required?)
  - Validate against allowed timeframes
  - Update docstring with example: `?timeframe=1h&start=...&end=...`

- [ ] Create `PUT /api/v1/admin/symbols/{symbol}/timeframes` endpoint
  - Request body: `UpdateSymbolTimeframesRequest`
  - Updates symbol's configured timeframes in DB
  - Returns updated symbol config

- [ ] Update symbol info endpoint
  - Include configured timeframes in response
  - Endpoint: `GET /api/v1/admin/symbols/{symbol}`

- [ ] Create validation helper
  - Function to validate timeframe against allowed list
  - Reusable in multiple endpoints

**Related Files**:
- `main.py` (endpoints)
- `src/models.py` (request/response models)

---

## Phase 7: Testing & Data Migration
**Estimated**: 1 hour | **Status**: `todo`

- [ ] Unit tests
  - Polygon client timeframe mapping
  - Scheduler per-symbol-per-timeframe logic
  - Model validation

- [ ] Integration tests
  - Full backfill flow with multiple timeframes
  - API endpoint with timeframe parameter
  - Admin endpoint to update timeframes

- [ ] Run migrations in test environment
  - Verify schema changes
  - Verify backfill of existing data

- [ ] Manual testing
  - Backfill single symbol with multiple timeframes
  - Query API with different timeframes
  - Update symbol timeframes via admin endpoint

**Related Files**:
- `tests/test_integration.py`
- `conftest.py`

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
- [ ] Phase 2 started
- [ ] Phase 3 started
- [ ] Phase 4 started
- [ ] Phase 5 started
- [ ] Phase 6 started
- [ ] Phase 7 started
- [ ] All phases complete
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
