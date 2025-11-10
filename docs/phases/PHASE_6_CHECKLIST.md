# Phase 6: Implementation Checklist

**Status**: Planning Complete - Ready to Start Implementation  
**Target Completion**: 1-2 weeks  
**Estimated Effort**: 20-25 hours

---

## Pre-Implementation Verification

### ✓ Database Setup
- [ ] Verify migration SQL file exists: `database/migrations/001_add_symbols_and_api_keys.sql`
- [ ] Verify tables can be created (test locally)
- [ ] Check if tables already exist in production DB
- [ ] Document any existing data that needs migration

**Command to check**:
```bash
psql $DATABASE_URL -c "SELECT * FROM api_keys LIMIT 1" 2>/dev/null || echo "Table doesn't exist"
psql $DATABASE_URL -c "SELECT * FROM tracked_symbols LIMIT 1" 2>/dev/null || echo "Table doesn't exist"
```

### ✓ Current Implementation Check
- [ ] Verify `src/services/auth.py` is complete
- [ ] Verify `src/services/symbol_manager.py` is complete
- [ ] Verify `src/middleware/auth_middleware.py` exists
- [ ] Verify main.py has all imports and initializations
- [ ] Check if existing tests pass: `pytest tests/test_auth.py -v`

**Commands**:
```bash
wc -l src/services/auth.py              # Should be ~192 lines
wc -l src/services/symbol_manager.py    # Should be ~278 lines
grep "init_auth_service" main.py        # Should exist
pytest tests/test_auth.py -v            # Should pass
```

### ✓ Schema Verification
- [ ] Confirm migration file has all needed tables
- [ ] Confirm indexes are correct
- [ ] Confirm foreign keys are set up

**Expected Tables**:
- `api_keys` - API key storage
- `api_key_audit` - Usage audit log
- `tracked_symbols` - Symbol tracking

---

## Phase 6.1: Database Initialization System

### 6.1.1: Create Migration Service
- [ ] Create `src/services/migration_service.py`
  - [ ] `run_migrations(db_url)` - Execute all .sql files
  - [ ] `verify_schema(db_url)` - Check tables exist
  - [ ] Handle idempotency
  - [ ] Log results

**File Structure**:
```python
class MigrationService:
    async def run_migrations(self, db_url: str) -> bool:
        """Read and execute SQL files in order"""
    
    async def verify_schema(self, db_url: str) -> Dict[str, bool]:
        """Check that all required tables exist"""
    
    async def get_migration_history(self, db_url: str) -> List[str]:
        """Get list of executed migrations"""
```

**Tests needed**: 8 tests
- [ ] Test migration execution
- [ ] Test idempotency (run twice)
- [ ] Test schema verification
- [ ] Test with missing tables
- [ ] Test with existing tables
- [ ] Test error handling
- [ ] Test migration history
- [ ] Test concurrent migrations

### 6.1.2: Create Bootstrap Script
- [ ] Create `scripts/bootstrap_db.py`
  - [ ] Run migrations
  - [ ] Verify schema
  - [ ] Generate initial admin key
  - [ ] Seed core symbols
  - [ ] Print summary

**File Structure**:
```python
async def bootstrap_database():
    """Initialize database for first-time use"""
    # 1. Run migrations
    # 2. Verify schema
    # 3. Generate admin key
    # 4. Seed symbols
    # 5. Print results

if __name__ == "__main__":
    asyncio.run(bootstrap_database())
```

**Usage**:
```bash
python scripts/bootstrap_db.py
# Output:
# ✓ Migrations applied
# ✓ Schema verified
# ✓ Initial API key: mdw_abc123...
# ✓ Symbols seeded: 15 total
```

**Tests needed**: 6 tests
- [ ] Test bootstrap on fresh DB
- [ ] Test bootstrap on existing DB
- [ ] Test key generation
- [ ] Test symbol seeding
- [ ] Test error recovery
- [ ] Test idempotency

### 6.1.3: Update Startup Logic
- [ ] Modify `main.py` lifespan
  - [ ] Call migration runner at startup
  - [ ] Verify schema before starting
  - [ ] Log schema version
  - [ ] Handle migration errors gracefully

**Changes needed**:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Running database migrations...")
    await migration_service.run_migrations(config.database_url)
    
    schema_ok = await migration_service.verify_schema(config.database_url)
    if not schema_ok:
        logger.error("Schema verification failed")
        raise RuntimeError("Database schema not ready")
    
    # ... rest of startup
```

**Tests needed**: 3 tests
- [ ] Test successful startup
- [ ] Test migration failure handling
- [ ] Test schema verification failure

---

## Phase 6.2: API Key Management Endpoints

### 6.2.1: Extend APIKeyService
- [ ] Add `create_api_key(name)` → APIKeyResponse
- [ ] Add `list_api_keys()` → List[APIKeyMetadata]
- [ ] Add `get_api_key_audit(key_id, limit=100)` → List[AuditLog]
- [ ] Add `revoke_api_key(key_id)` → bool
- [ ] Add `restore_api_key(key_id)` → bool
- [ ] Add `delete_api_key(key_id)` → bool

**Methods to add** (~40 lines total):
```python
async def create_api_key(self, name: str) -> dict:
    """Generate and store new API key"""

async def list_api_keys(self, active_only: bool = False) -> List[dict]:
    """List all API keys with metadata"""

async def get_audit_log(self, key_id: int, limit: int = 100) -> List[dict]:
    """Get usage audit log for specific key"""

async def revoke_key(self, key_id: int) -> bool:
    """Deactivate key (don't delete)"""

async def restore_key(self, key_id: int) -> bool:
    """Reactivate key"""

async def delete_key(self, key_id: int) -> bool:
    """Permanently delete key"""
```

**Tests needed**: 20 tests
- [ ] Test create (success, duplicate name)
- [ ] Test list (with/without inactive)
- [ ] Test audit log (pagination, filtering)
- [ ] Test revoke (valid, already revoked)
- [ ] Test restore (valid, active)
- [ ] Test delete (with/without audit logs)
- [ ] Test error cases
- [ ] Test database constraints

### 6.2.2: Add Pydantic Models
- [ ] Update/add `APIKeyListResponse`
- [ ] Add `AuditLogEntry` model
- [ ] Add `APIKeyCreateResponse` model
- [ ] Add `APIKeyAuditResponse` model

**Models to add** (~20 lines total):
```python
class APIKeyListResponse(BaseModel):
    id: int
    name: str
    active: bool
    created_at: datetime
    last_used: Optional[datetime]
    request_count: int
    # Note: key_hash never included

class AuditLogEntry(BaseModel):
    id: int
    endpoint: str
    method: str
    status_code: int
    timestamp: datetime

class APIKeyCreateResponse(BaseModel):
    api_key: str  # Raw key, only shown once
    key_preview: str  # First 8 chars
    name: str
    created_at: datetime
```

**Tests needed**: 4 tests
- [ ] Test JSON encoding
- [ ] Test validation rules
- [ ] Test optional fields
- [ ] Test privacy (no key_hash in list response)

### 6.2.3: Create API Endpoints
- [ ] POST `/api/v1/admin/api-keys` - Generate key
- [ ] GET `/api/v1/admin/api-keys` - List keys
- [ ] GET `/api/v1/admin/api-keys/{id}/audit` - View audit log
- [ ] PUT `/api/v1/admin/api-keys/{id}` - Revoke/restore
- [ ] DELETE `/api/v1/admin/api-keys/{id}` - Delete key

**Endpoints to add** (~100 lines total):
```python
@app.post("/api/v1/admin/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(request: CreateAPIKeyRequest):
    """Generate new API key"""

@app.get("/api/v1/admin/api-keys", response_model=List[APIKeyListResponse])
async def list_api_keys(active_only: bool = False):
    """List all API keys"""

@app.get("/api/v1/admin/api-keys/{key_id}/audit")
async def get_audit_log(key_id: int, limit: int = 100):
    """Get usage audit log for key"""

@app.put("/api/v1/admin/api-keys/{key_id}")
async def update_api_key(key_id: int, active: bool = None):
    """Revoke or restore API key"""

@app.delete("/api/v1/admin/api-keys/{key_id}")
async def delete_api_key(key_id: int):
    """Permanently delete API key"""
```

**Tests needed**: 15 tests
- [ ] Test create endpoint (success, validation)
- [ ] Test list endpoint (with/without filter)
- [ ] Test audit endpoint (pagination, filtering)
- [ ] Test update endpoint (revoke, restore)
- [ ] Test delete endpoint (success, not found)
- [ ] Test auth (missing header, invalid key)
- [ ] Test error responses
- [ ] Test response formats

### 6.2.4: Integration Tests
- [ ] Test full flow: generate key → use key → revoke key
- [ ] Test audit trail: action → logged in audit
- [ ] Test permission: non-admin key can't access endpoints
- [ ] Test error cases: missing params, invalid IDs

**Integration tests needed**: 6 tests
- [ ] Full lifecycle test
- [ ] Audit trail test
- [ ] Permission test
- [ ] Concurrent operations
- [ ] Database consistency
- [ ] Error recovery

---

## Phase 6.3: Symbol Management Enhancements

### 6.3.1: Verify Scheduler Symbol Loading
- [ ] Check `_load_symbols_from_db()` implementation
- [ ] Verify loads only active symbols
- [ ] Verify error handling for empty list
- [ ] Add status updates during backfill

**What to verify**:
```bash
grep -A 20 "_load_symbols_from_db" src/scheduler.py
# Should return: List[str] of active symbols
# Should filter: WHERE active = TRUE
# Should handle: Empty list gracefully
```

**Tests needed**: 5 tests
- [ ] Test loading symbols
- [ ] Test filtering inactive
- [ ] Test empty list handling
- [ ] Test database error handling
- [ ] Test concurrent symbol updates

### 6.3.2: Add Backfill Status Tracking
- [ ] Update backfill job to set status
- [ ] Set `backfill_status='in_progress'` before
- [ ] Set `backfill_status='completed'` after success
- [ ] Set `backfill_status='failed'` and `backfill_error` on failure
- [ ] Update `last_backfill` timestamp

**Changes needed**:
```python
# In _backfill_job():
for symbol in self.symbols:
    # Set status to in_progress
    await symbol_manager.update_symbol_status(
        symbol, backfill_status='in_progress'
    )
    
    try:
        # Run backfill
        result = await self.polygon_client.fetch_latest(symbol)
        # Insert data
        # Set status to completed
        await symbol_manager.update_symbol_status(
            symbol, backfill_status='completed'
        )
    except Exception as e:
        # Set status to failed with error
        await symbol_manager.update_symbol_status(
            symbol,
            backfill_status='failed',
            backfill_error=str(e)
        )
```

**Tests needed**: 5 tests
- [ ] Test status progression
- [ ] Test error handling
- [ ] Test timestamp updates
- [ ] Test concurrent updates
- [ ] Test failure recovery

### 6.3.3: Enhance Symbol Endpoints
- [ ] Add record count to GET responses
- [ ] Add date range to GET responses
- [ ] Add validation rate to GET responses
- [ ] Add asset_class to responses

**Changes needed**:
```python
# GET /api/v1/admin/symbols/{symbol}
# Add to response:
{
    "id": 1,
    "symbol": "AAPL",
    "asset_class": "stock",
    "active": true,
    "date_added": "...",
    "last_backfill": "...",
    "backfill_status": "completed",
    
    # NEW:
    "stats": {
        "record_count": 252,
        "date_range": {
            "start": "2024-01-01",
            "end": "2024-12-31"
        },
        "validation_rate": 0.98,
        "gaps_detected": 2
    }
}
```

**Tests needed**: 4 tests
- [ ] Test enhanced response format
- [ ] Test with different symbols
- [ ] Test with crypto vs stock
- [ ] Test stats calculation

### 6.3.4: Verify Crypto Support
- [ ] Test adding crypto symbol (BTC, ETH)
- [ ] Test Polygon crypto endpoints
- [ ] Test data format handling
- [ ] Test backfill for crypto

**Tests needed**: 8 tests
- [ ] Test add crypto symbol
- [ ] Test list includes crypto
- [ ] Test Polygon crypto endpoint
- [ ] Test backfill crypto
- [ ] Test data validation (crypto-specific)
- [ ] Test error handling
- [ ] Test mixed asset classes
- [ ] Test crypto rate limits

---

## Phase 6.4: Comprehensive Test Suite

### 6.4.1: Middleware Tests (40 tests)
File: `tests/test_auth_middleware.py`

**Test Categories**:
- [ ] Path matching (protected/public routes)
- [ ] Header extraction (present/missing)
- [ ] Key validation (valid/invalid/inactive)
- [ ] Error responses (401, 403, 500)
- [ ] Request state injection
- [ ] Usage logging
- [ ] Concurrent requests
- [ ] Performance

**Test methods**:
```python
test_protected_path_detection
test_public_path_bypass
test_missing_header_returns_401
test_invalid_key_returns_401
test_inactive_key_returns_401
test_valid_key_passes_through
test_metadata_injected_in_state
test_usage_logged_asynchronously
test_header_case_insensitive
test_error_messages_generic
# ... more
```

### 6.4.2: Database Integration Tests (35 tests)
File: `tests/test_symbol_manager_db.py`

**Test Categories**:
- [ ] Add symbol (success, duplicate, validation)
- [ ] Get symbol (found, not found, case-insensitive)
- [ ] List symbols (all, active only, filtered)
- [ ] Update status (all fields, partial)
- [ ] Remove symbol (soft delete, data retention)
- [ ] Backfill tracking
- [ ] Error handling

**Test methods**:
```python
test_add_symbol_success
test_add_duplicate_symbol_fails
test_symbol_uppercase_stored
test_get_symbol_found
test_get_symbol_not_found
test_list_all_symbols
test_list_active_only
test_update_active_status
test_update_backfill_status
test_update_with_error_message
test_remove_symbol_soft_delete
test_historical_data_retained
test_duplicate_prevention
test_asset_class_stored
test_timestamp_fields
# ... more
```

### 6.4.3: Endpoint Integration Tests (40 tests)
File: `tests/test_admin_endpoints.py`

**Test Categories**:
- [ ] Symbol endpoints (CRUD, auth, validation)
- [ ] API key endpoints (generate, list, audit, revoke)
- [ ] Request/response formats
- [ ] Error cases
- [ ] Concurrent requests
- [ ] Performance

**Test methods**:
```python
# Symbol endpoints
test_post_symbol_success
test_post_symbol_unauthorized
test_post_symbol_duplicate
test_get_symbols_list
test_get_symbol_info
test_put_symbol_status
test_delete_symbol

# API key endpoints
test_create_api_key
test_list_api_keys
test_get_audit_log
test_revoke_key
test_restore_key
test_delete_key

# General
test_request_validation
test_response_format
test_error_responses
test_concurrent_requests
# ... more
```

### 6.4.4: Crypto Tests (15 tests)
File: `tests/test_crypto_support.py`

**Test Categories**:
- [ ] Add crypto symbol
- [ ] Backfill crypto data
- [ ] Data validation (crypto-specific)
- [ ] Polygon crypto endpoints
- [ ] Mixed asset classes

**Test methods**:
```python
test_add_btc_symbol
test_add_eth_symbol
test_crypto_asset_class
test_backfill_crypto
test_crypto_data_format
test_crypto_validation
test_mixed_symbols_backfill
test_crypto_rate_limits
test_polygon_crypto_endpoint
# ... more
```

### 6.4.5: Test Coverage Summary
**Target**: 130+ new tests, 95%+ code coverage

| Category | Tests | Target Coverage |
|----------|-------|-----------------|
| Middleware | 40 | 95% |
| Database | 35 | 95% |
| Endpoints | 40 | 90% |
| Crypto | 15 | 90% |
| **Total** | **130** | **92%** |

---

## Phase 6.5: Crypto Symbol Support

### 6.5.1: Verify Polygon Crypto Endpoints
- [ ] Check `src/clients/polygon_client.py` for crypto methods
- [ ] Test with live Polygon test API
- [ ] Document supported symbols
- [ ] Verify response format

**What to check**:
```python
# Check if methods exist:
polygon_client.get_crypto_ticker()
polygon_client.get_crypto_agg()

# Or if methods need to be added:
# Implement crypto endpoints in PolygonClient
```

### 6.5.2: Add Crypto Data Handling
- [ ] Add crypto validation rules
- [ ] Handle crypto-specific fields
- [ ] Map crypto to correct endpoint
- [ ] Test BTC, ETH, SOL, etc.

**Changes needed**:
```python
# In scheduler._backfill_job():
if symbol_info['asset_class'] == 'crypto':
    endpoint = f"{symbol}USD"  # BTC -> BTCUSD
    result = await self.polygon_client.get_crypto_agg(endpoint)
else:
    result = await self.polygon_client.get_latest(symbol)
```

### 6.5.3: Testing
- [ ] Test adding crypto symbols
- [ ] Test backfill with crypto
- [ ] Test data validation
- [ ] Test mixed crypto and stocks

---

## Phase 6.6: Documentation

### 6.6.1: Implementation Guide
File: `PHASE_6_IMPLEMENTATION.md` (~500 lines)

**Sections**:
- [ ] Architecture overview
- [ ] Component descriptions
- [ ] API key flow diagrams (text-based)
- [ ] Symbol management flow
- [ ] Database schema explanation
- [ ] Code examples
- [ ] Integration points

### 6.6.2: API Key Management Guide
File: `API_KEY_MANAGEMENT.md` (~250 lines)

**Sections**:
- [ ] Overview
- [ ] Generating keys (bootstrap vs endpoint)
- [ ] Using keys in requests
- [ ] Revoking/deleting keys
- [ ] Viewing audit logs
- [ ] Security best practices
- [ ] Troubleshooting
- [ ] Example curl commands

### 6.6.3: Crypto Symbols Guide
File: `CRYPTO_SYMBOLS.md` (~200 lines)

**Sections**:
- [ ] Supported symbols
- [ ] Adding crypto symbols
- [ ] Data availability
- [ ] Rate limiting
- [ ] Differences from stock data
- [ ] Example: Adding BTC/ETH
- [ ] Troubleshooting

### 6.6.4: Deployment Guide
File: `DEPLOYMENT_WITH_AUTH.md` (~250 lines)

**Sections**:
- [ ] Prerequisites
- [ ] Database setup
- [ ] Running migrations
- [ ] Bootstrap script
- [ ] Initial key generation
- [ ] Adding symbols
- [ ] Verification checklist
- [ ] Post-deployment tasks
- [ ] Monitoring

### 6.6.5: Update DEVELOPMENT_STATUS.md
- [ ] Add Phase 6 section
- [ ] Update test counts
- [ ] Update integration points
- [ ] Update production readiness

---

## Testing Strategy

### Test Pyramid (130 total tests)
```
                △
               /|\
              / | \
             /  |  \  E2E Tests (10)
            /   |   \
           /    |    \
          /_____|_____\
         /      |      \  Integration Tests (40)
        /       |       \
       /________|________\
      /         |         \ Unit Tests (80)
     /__________|__________\
```

### Running Tests
```bash
# All tests
pytest tests/ -v

# By category
pytest tests/test_auth.py tests/test_auth_middleware.py -v
pytest tests/test_symbol_manager_db.py tests/test_admin_endpoints.py -v
pytest tests/test_crypto_support.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific test
pytest tests/test_auth_middleware.py::test_protected_path_detection -v
```

### Coverage Targets
| Module | Target | Current |
|--------|--------|---------|
| auth.py | 95% | 10% |
| symbol_manager.py | 95% | 0% |
| auth_middleware.py | 90% | 0% |
| Admin endpoints | 90% | 0% |
| **Total** | **92%** | **2%** |

---

## Success Metrics

### Functional Requirements
- [ ] All API key CRUD endpoints working
- [ ] All symbol CRUD endpoints working
- [ ] Authentication middleware protecting admin routes
- [ ] Scheduler loading symbols from database
- [ ] Crypto symbols supported and tested
- [ ] Audit logging working for all API calls

### Code Quality
- [ ] All code follows project style
- [ ] No type errors
- [ ] No linting issues
- [ ] All docstrings present
- [ ] All error cases handled

### Test Coverage
- [ ] 130+ new tests
- [ ] 95%+ coverage of new code
- [ ] All existing tests still pass
- [ ] Integration tests passing

### Documentation
- [ ] Phase 6 guide complete
- [ ] API key management guide complete
- [ ] Crypto symbols guide complete
- [ ] Deployment guide complete
- [ ] All inline code comments present

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Schema migration fails | Low | High | Test migrations locally first |
| Key rotation breaks clients | Low | High | Design for multiple concurrent keys |
| Crypto data format differs | Medium | Medium | Test with Polygon API first |
| Performance degrades | Low | Medium | Cache key validation, load test |
| Missing test coverage | Medium | High | Comprehensive test plan above |
| Deployment issues | Low | Medium | Document all steps, test staging |

---

## Timeline Estimate

| Phase | Subtask | Hours | Status |
|-------|---------|-------|--------|
| 6.1 | Migration Service | 2 | Planned |
| 6.1 | Bootstrap Script | 1.5 | Planned |
| 6.1 | Startup Integration | 1 | Planned |
| 6.1 | Tests (6) | 1.5 | Planned |
| **6.1 Total** | | **6** | |
| 6.2 | APIKeyService Methods | 2 | Planned |
| 6.2 | Pydantic Models | 0.5 | Planned |
| 6.2 | API Endpoints | 2 | Planned |
| 6.2 | Tests (29) | 3 | Planned |
| **6.2 Total** | | **7.5** | |
| 6.3 | Scheduler Refactoring | 1.5 | Planned |
| 6.3 | Backfill Status | 1 | Planned |
| 6.3 | Endpoint Enhancement | 1 | Planned |
| 6.3 | Tests (18) | 2 | Planned |
| **6.3 Total** | | **5.5** | |
| 6.4 | Write Tests | 4 | Planned |
| **6.4 Total** | | **4** | |
| 6.5 | Crypto Support | 2 | Planned |
| **6.5 Total** | | **2** | |
| 6.6 | Documentation | 2 | Planned |
| **6.6 Total** | | **2** | |
| | **TOTAL** | **28** | |

**Timeline**: ~28 hours of work
- ~2 sessions of 8-10 hours
- Or ~4-5 sessions of 5-6 hours
- Or spread over 2 weeks with part-time work

---

## Next Actions (What to Do First)

### Immediate (Before Starting Code)
1. **Verify current state**
   ```bash
   cd /Users/stephenlopez/Projects/Trading\ Projects/MarketDataAPI
   
   # Check migration file exists
   ls -l database/migrations/001_add_symbols_and_api_keys.sql
   
   # Check if tables exist
   psql $DATABASE_URL -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
   
   # Run existing tests
   pytest tests/test_auth.py -v
   ```

2. **Document current state**
   - [ ] List current symbols in tracked_symbols
   - [ ] Check if api_keys table has any entries
   - [ ] Document any gaps

### Session 1: Foundation
1. **6.1 Database Initialization** (3 hours)
   - Create migration service
   - Create bootstrap script
   - Update startup logic
   - Write and run tests

2. **6.2.1 Extend APIKeyService** (2 hours)
   - Add CRUD methods
   - Write unit tests

### Session 2: Features
1. **6.2.2-6.2.3 API Endpoints** (3 hours)
   - Add Pydantic models
   - Create endpoints
   - Write endpoint tests

2. **6.3 Symbol Enhancements** (2 hours)
   - Verify scheduler
   - Add backfill status tracking
   - Write tests

### Session 3: Testing & Polish
1. **6.4 Complete Test Suite** (4 hours)
   - Write middleware tests
   - Write database tests
   - Write integration tests
   - Verify coverage

2. **6.5 Crypto Support** (2 hours)
   - Verify endpoints
   - Test crypto symbols
   - Integration test

### Session 4: Documentation
1. **6.6 Documentation** (2 hours)
   - Write guides
   - Create examples
   - Update status files

---

## Decision Points

**Before implementing**, clarify these**:

1. **Database Initialization**
   - Should bootstrap script run automatically at startup?
   - Should admin key be generated automatically or manually?
   - Should core symbols be seeded automatically?

2. **API Key Features**
   - Implement key rotation?
   - Implement key expiration?
   - Implement scopes/permissions?
   - Implement IP whitelisting?

3. **Symbol Management**
   - Should symbols be soft-deleted or hard-deleted?
   - Should historical data be retained after symbol deletion?
   - Should symbol list be cached or reloaded each time?

4. **Crypto Support**
   - What crypto symbols to support initially?
   - Should crypto be in same backfill job or separate?
   - Different rate limits for crypto?

5. **Audit Logging**
   - Keep all audit logs or archive old ones?
   - How long to retain audit logs?
   - Implement audit log encryption?

---

## Rollback Plan

If something breaks:

1. **Database Issues**
   - Drop tables and re-migrate
   - Restore from backup
   - Run migration_service.verify_schema()

2. **Code Issues**
   - Revert changes: `git revert <commit>`
   - Run tests to verify: `pytest tests/`
   - Restart app: `python main.py`

3. **Key Exposure**
   - Revoke exposed key immediately
   - Generate new admin key
   - Review audit log for usage
   - Notify users if needed

---

## Monitoring Plan

After deployment:

1. **Watch these metrics**
   - API key validation errors
   - Admin endpoint usage
   - Symbol management operations
   - Database query performance
   - Audit log growth

2. **Alerts to set up**
   - High number of failed auth attempts
   - Admin endpoint errors
   - Database connection issues
   - Migration failures
   - Audit table growth

3. **Health checks**
   - Run weekly: `pytest tests/ -v`
   - Monitor: API key validation latency
   - Monitor: Admin endpoint response times
   - Check: Audit log size

---

**Document Status**: Complete and ready for implementation  
**Last Updated**: November 10, 2025  
**Next Step**: Start Phase 6.1 - Database Initialization System
