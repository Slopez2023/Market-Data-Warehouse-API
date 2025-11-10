# Phase 6: API Key Auth + Symbol Management - Implementation Plan

**Status**: Planning Phase  
**Date**: November 10, 2025  
**Scope**: Complete API key authentication and dynamic symbol management architecture

---

## Current State Review

### ✅ Already Implemented
1. **Database Schema** (`database/migrations/001_add_symbols_and_api_keys.sql`)
   - `tracked_symbols` table with full schema
   - `api_keys` table with SHA256 hashing
   - `api_key_audit` table for usage tracking
   - All necessary indexes in place

2. **Core Services**
   - `src/services/auth.py` - APIKeyService (complete)
     - Key generation with `mdw_` prefix format
     - Key validation with active status checking
     - Usage logging and audit trail
     - Static hash methods
   - `src/services/symbol_manager.py` - SymbolManager (complete)
     - CRUD operations for tracked symbols
     - Asset class support (stock, crypto, etf)
     - Backfill status tracking
     - Soft delete implementation

3. **Middleware** (`src/middleware/auth_middleware.py`)
   - APIKeyAuthMiddleware protecting `/api/v1/admin/*` endpoints
   - X-API-Key header validation
   - Request state injection with key metadata
   - Async usage logging

4. **API Endpoints** (in main.py)
   - `POST /api/v1/admin/symbols` - Add symbol
   - `GET /api/v1/admin/symbols` - List symbols
   - `GET /api/v1/admin/symbols/{symbol}` - Get symbol info
   - `PUT /api/v1/admin/symbols/{symbol}` - Update symbol status
   - `DELETE /api/v1/admin/symbols/{symbol}` - Deactivate symbol

5. **Models** (`src/models.py`)
   - TrackedSymbol model
   - AddSymbolRequest model
   - APIKeyResponse model
   - APIKeyMetadata model

6. **Integration** (main.py)
   - Auth service initialization
   - Symbol manager initialization
   - Middleware registration
   - All endpoints properly integrated

7. **Unit Tests** (`tests/test_auth.py`)
   - API key generation tests
   - Hash determinism tests
   - Format validation tests

---

## What's Missing / Needs Work

### Critical Items
1. **Database Initialization**
   - Migration runner not yet in place
   - Tables may not be created in deployment
   - No seed data for initial admin key

2. **API Key Management Endpoints** (Missing)
   - No endpoint to list API keys
   - No endpoint to generate new API keys (admin only)
   - No endpoint to revoke keys
   - No endpoint to view audit logs

3. **Scheduler Refactoring** (Partial)
   - `_load_symbols_from_db()` method exists but needs verification
   - Should load only active symbols
   - Error handling on empty symbol list

4. **Crypto Support** (Polygon client only)
   - Need to verify Polygon crypto endpoints work
   - Test with BTC, ETH, etc.
   - Verify asset_class filtering in scheduler

5. **Test Coverage** (Incomplete)
   - No auth middleware tests
   - No symbol manager database tests
   - No integration tests for admin endpoints
   - No crypto symbol tests

6. **Documentation** (Missing)
   - API key management guide
   - Deployment guide with DB initialization
   - Crypto symbol setup instructions
   - Admin endpoint examples

---

## Implementation Plan

### Phase 6.1: Database & Initialization (2-3 hours)
**Goal**: Ensure tables exist and system is ready for auth

#### Tasks
1. **Create migration runner** (`src/services/migration_service.py`)
   - Read and execute .sql files in order
   - Track migration history
   - Handle idempotency (IF NOT EXISTS)
   - Log execution

2. **Create bootstrap script** (`scripts/bootstrap_db.py`)
   - Apply all migrations
   - Generate initial admin API key
   - Seed core symbols (AAPL, MSFT, GOOGL, etc.)
   - Verify tables exist

3. **Update main.py startup**
   - Call migration runner at startup
   - Log schema version
   - Fail gracefully if tables missing

4. **Testing**
   - Test migration idempotency
   - Test bootstrap with fresh DB
   - Test with existing tables

---

### Phase 6.2: API Key Management (3-4 hours)
**Goal**: Full lifecycle management for API keys

#### New Endpoints
1. **POST /api/v1/admin/api-keys**
   - Create new API key with name
   - Return raw key (only shown once)
   - Return key_preview (first 8 chars)
   - Store hash in database

2. **GET /api/v1/admin/api-keys**
   - List all API keys
   - Show: name, created_at, last_used, request_count, active status
   - Hide: actual key (never shown)

3. **GET /api/v1/admin/api-keys/{key_id}/audit**
   - Show audit log for specific key
   - Limit: 1000 most recent
   - Show: endpoint, method, status, timestamp

4. **PUT /api/v1/admin/api-keys/{key_id}**
   - Toggle active status (revoke/restore)
   - Optional: rotate key (generate new, retire old)

5. **DELETE /api/v1/admin/api-keys/{key_id}**
   - Hard delete API key
   - Keep audit logs for compliance

#### Implementation Details
- Add to `auth.py`: Methods for CRUD operations
- Add to models: APIKeyListResponse, AuditLogEntry
- Protect all endpoints with middleware (nested admin path)
- Pagination for audit logs

#### Testing
- Test key generation and hashing
- Test validation with valid/invalid keys
- Test revocation flow
- Test audit logging

---

### Phase 6.3: Symbol Management Enhancements (2-3 hours)
**Goal**: Full symbol lifecycle with crypto support

#### Enhancements
1. **Scheduler Refactoring**
   - Load only active symbols on startup
   - Reload list on each run
   - Handle empty symbol list gracefully
   - Log which symbols are backfilling

2. **Asset Class Support**
   - Add Polygon crypto endpoints
   - Map asset_class to correct API endpoint
   - Handle crypto-specific data differences

3. **Backfill Status Tracking**
   - Update status during backfill process
   - Track last_backfill timestamp
   - Store error messages on failure

4. **Symbol Endpoints Enhancement**
   - Add data statistics to GET endpoint
   - Show record count per symbol
   - Show data date range
   - Show validation rate

#### Testing
- Test loading symbols from DB
- Test with mixed asset classes
- Test with empty symbol list
- Test Polygon crypto endpoints
- Integration test: scheduler loads and processes symbols

---

### Phase 6.4: Complete Test Suite (3-4 hours)
**Goal**: 100% coverage of auth and symbol management

#### New Test Files
1. **tests/test_auth_middleware.py** (40 tests)
   - Protected path detection
   - Missing header handling
   - Valid/invalid key validation
   - Metadata injection
   - Usage logging
   - Error responses

2. **tests/test_symbol_manager_db.py** (30 tests)
   - Add symbol (success, duplicate, invalid)
   - Get symbol (found, not found)
   - List symbols (active only, all)
   - Update status (all fields)
   - Remove symbol (soft delete)
   - Asset class validation
   - Database constraints

3. **tests/test_api_key_management.py** (25 tests)
   - Generate API key
   - List API keys
   - View audit log
   - Revoke key
   - Delete key
   - Key rotation (if implemented)

4. **tests/test_admin_endpoints.py** (35 tests)
   - Integration tests for all admin endpoints
   - Auth header validation
   - Request/response validation
   - Error cases
   - Concurrent requests

#### Test Coverage Targets
- Auth service: 95%
- Symbol manager: 95%
- Middleware: 90%
- Admin endpoints: 90%

---

### Phase 6.5: Crypto Symbol Support (2-3 hours)
**Goal**: Full crypto asset class support

#### Implementation
1. **Polygon Crypto Endpoints**
   - Add crypto ticker endpoint in polygon_client.py
   - Map `asset_class='crypto'` to correct endpoint
   - Handle response format differences
   - Test with BTC, ETH, SOL, etc.

2. **Database Support**
   - Verify schema handles crypto symbols
   - Test with crypto tickers (BTCUSD, ETHGBP, etc.)
   - Track different asset classes separately

3. **Scheduler Integration**
   - Load crypto symbols from DB
   - Process crypto and stock symbols in same job
   - Handle different rate limits if needed

4. **Testing**
   - Test adding crypto symbols
   - Test backfill for crypto
   - Test data validation for crypto
   - Integration test with mixed assets

---

### Phase 6.6: Documentation (2 hours)
**Goal**: Complete deployment and usage guides

#### Documents to Create

1. **PHASE_6_IMPLEMENTATION.md** (400+ lines)
   - Architecture overview
   - Database schema explanation
   - Auth flow diagrams (if text-based)
   - API key best practices
   - Symbol management workflow

2. **API_KEY_MANAGEMENT.md** (200+ lines)
   - How to generate API keys
   - How to revoke keys
   - How to view usage/audit logs
   - Security best practices
   - Example curl commands

3. **CRYPTO_SYMBOLS.md** (150+ lines)
   - Supported crypto symbols
   - Asset class configuration
   - How to add new crypto symbol
   - Data availability notes
   - Rate limit considerations

4. **DEPLOYMENT_WITH_AUTH.md** (200+ lines)
   - Database initialization steps
   - Bootstrap script usage
   - Migration verification
   - Initial key generation
   - Post-deployment checklist

5. **Update DEVELOPMENT_STATUS.md**
   - Add Phase 6 section
   - Update test summary
   - Update integration points

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Request → APIKeyAuthMiddleware → Route Handler              │
│              ↓                                                │
│         X-API-Key Header                                      │
│              ↓                                                │
│      APIKeyService.validate_api_key()                        │
│              ↓                                                │
│         Database (api_keys table)                            │
│              ↓                                                │
│         Success/Fail → Response                              │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│ Admin Endpoints (Protected)                                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Symbol Management:                                          │
│  • POST /api/v1/admin/symbols - Add                          │
│  • GET /api/v1/admin/symbols - List                          │
│  • GET /api/v1/admin/symbols/{symbol} - Get                  │
│  • PUT /api/v1/admin/symbols/{symbol} - Update               │
│  • DELETE /api/v1/admin/symbols/{symbol} - Remove            │
│                                                               │
│  API Key Management:                                         │
│  • POST /api/v1/admin/api-keys - Generate                    │
│  • GET /api/v1/admin/api-keys - List                         │
│  • GET /api/v1/admin/api-keys/{id}/audit - Audit Log         │
│  • PUT /api/v1/admin/api-keys/{id} - Revoke/Restore          │
│  • DELETE /api/v1/admin/api-keys/{id} - Delete               │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│ Database Layer                                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Tables:                                                     │
│  • api_keys - Store hashed keys                              │
│  • api_key_audit - Track usage                               │
│  • tracked_symbols - Manage symbols                          │
│  • market_data - Historical OHLCV                            │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow Examples

### API Key Generation Flow
```
1. Admin calls POST /api/v1/admin/api-keys
2. Service generates random key (mdw_xxxxx)
3. Hash key with SHA256
4. Store hash in api_keys table
5. Return key + preview to admin (never shown again)
6. Log creation in audit
```

### Symbol Backfill Flow
```
1. Scheduler starts daily job
2. Load symbols from tracked_symbols WHERE active=TRUE
3. For each symbol:
   a. Get asset_class (stock, crypto, etc.)
   b. Call appropriate Polygon endpoint
   c. Validate candles
   d. Insert into market_data table
   e. Update symbol status + timestamp
4. Log results to backfill_history
5. Trigger alert if failures
```

### Request Authentication Flow
```
1. Client makes request with X-API-Key header
2. Middleware extracts header
3. Hash key with SHA256
4. Query api_keys table for hash
5. Check if key is active
6. If valid: Store metadata in request.state
7. Route handler processes request
8. After response: Log usage to api_key_audit
```

---

## Success Criteria

### Functional
- [ ] API key CRUD fully implemented
- [ ] All admin endpoints protected and working
- [ ] Symbol management working with CRUD
- [ ] Scheduler loads symbols from DB on startup
- [ ] Crypto symbols can be added and backfilled
- [ ] Audit logging working for all API calls

### Testing
- [ ] 130+ new tests written (all categories)
- [ ] 100% of new code covered
- [ ] All existing tests still pass
- [ ] Integration tests for full flows

### Documentation
- [ ] Phase 6 implementation guide complete
- [ ] API key management guide complete
- [ ] Crypto support guide complete
- [ ] Deployment guide updated
- [ ] DEVELOPMENT_STATUS.md updated

### Deployment
- [ ] Migration system in place
- [ ] Bootstrap script working
- [ ] Fresh DB initialization verified
- [ ] Existing DB upgrade path verified

---

## Testing Strategy

### Unit Tests (70%)
- Auth service methods
- Symbol manager methods
- Key generation and hashing
- Data validation

### Integration Tests (20%)
- Middleware + auth service
- Admin endpoints + database
- Scheduler + symbol loading
- Full API request flows

### End-to-End Tests (10%)
- Bootstrap fresh database
- Generate API key
- Use key to call admin endpoint
- Verify audit logging
- Add crypto symbol
- Verify backfill includes crypto

---

## Risk Mitigation

### Risk: Schema already exists
**Mitigation**: Use IF NOT EXISTS in all migrations

### Risk: Key rotation breaks existing clients
**Mitigation**: Design endpoints to support multiple concurrent keys

### Risk: Crypto data format differs from stocks
**Mitigation**: Test with Polygon test API first, wrap differences in client

### Risk: Performance impact of loading symbols on startup
**Mitigation**: Cache in memory, reload on schedule or admin action

---

## Rollout Plan

1. **Local Development** (1 day)
   - Implement Phase 6.1-6.3
   - Run local tests
   - Manual testing of flows

2. **Integration Testing** (1 day)
   - Deploy to staging
   - Run full test suite
   - Load test auth system
   - Test with real Polygon API

3. **Documentation** (0.5 day)
   - Write guides
   - Create examples
   - Document troubleshooting

4. **Production Deployment** (0.5 day)
   - Run migrations
   - Generate initial admin key
   - Seed core symbols
   - Monitor for errors

---

## Estimated Timeline

| Phase | Duration | Start | End |
|-------|----------|-------|-----|
| 6.1: DB & Init | 3h | Day 1 | Day 1 PM |
| 6.2: Key Mgmt | 4h | Day 2 | Day 2 PM |
| 6.3: Symbols | 3h | Day 2 | Day 3 AM |
| 6.4: Tests | 4h | Day 3 | Day 3 PM |
| 6.5: Crypto | 3h | Day 4 | Day 4 AM |
| 6.6: Docs | 2h | Day 4 | Day 4 PM |
| **Total** | **~19 hours** | | |

---

## Next Steps

1. **Immediate**
   - Verify migration SQL files exist
   - Check if tables already exist in production
   - List current symbols in tracked_symbols table

2. **This Session**
   - Implement Phase 6.1 (DB initialization)
   - Implement Phase 6.2 (API key management endpoints)
   - Begin Phase 6.4 (tests)

3. **Follow-up Sessions**
   - Complete remaining tests
   - Implement crypto support
   - Write documentation
   - Deploy and validate

---

## Questions to Answer Before Starting

1. Is the database already initialized with the migration tables?
2. Are there any existing API keys in production that need migration?
3. What symbols are currently in the database?
4. Should initial admin key be generated in bootstrap or manually?
5. Any existing audit logging requirements beyond the basic implementation?
6. Preferred format for API key rotation (generate new + retire old, or replace)?

---

**Status**: Ready for Phase 6.1 Implementation  
**Owner**: Stephen Lopez  
**Last Updated**: November 10, 2025
