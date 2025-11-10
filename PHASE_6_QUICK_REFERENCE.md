# Phase 6 Quick Reference Guide

**Quick lookup for Phase 6 implementation details**

---

## Current Status Summary

| Component | Status | Location | Lines |
|-----------|--------|----------|-------|
| APIKeyService | ✅ Complete | `src/services/auth.py` | 192 |
| SymbolManager | ✅ Complete | `src/services/symbol_manager.py` | 278 |
| AuthMiddleware | ✅ Complete | `src/middleware/auth_middleware.py` | 88 |
| DB Schema | ✅ Complete | `database/migrations/001_add_symbols_and_api_keys.sql` | 48 |
| Symbol Endpoints | ✅ Complete | `main.py` (lines 466-631) | 166 |
| API Key Endpoints | ❌ Missing | - | - |
| Migration Service | ❌ Missing | - | - |
| Bootstrap Script | ❌ Missing | - | - |
| Tests | 🟡 5% | `tests/test_auth.py` | 50 |

---

## Implementation Road Map

### Phase 6.1: Database Init (6 hours)
**What**: Create migration runner and bootstrap script

**Files to create**:
1. `src/services/migration_service.py` (~100 lines)
   - `run_migrations(db_url)` - Execute SQL files
   - `verify_schema(db_url)` - Check tables exist
   - `get_migration_history(db_url)` - Track migrations

2. `scripts/bootstrap_db.py` (~100 lines)
   - Run migrations
   - Generate admin key
   - Seed core symbols
   - Print summary

**Modifications**:
- Update `main.py` lifespan to call migration runner

**Tests**: 14 tests total

---

### Phase 6.2: API Key Management (8 hours)
**What**: Add endpoints for key lifecycle management

**Methods to add to APIKeyService**:
```python
async def create_api_key(name: str) → dict
async def list_api_keys(active_only=False) → List[dict]
async def get_audit_log(key_id: int, limit=100) → List[dict]
async def revoke_key(key_id: int) → bool
async def restore_key(key_id: int) → bool
async def delete_key(key_id: int) → bool
```

**Endpoints to create** (in main.py):
```
POST   /api/v1/admin/api-keys              → Create key
GET    /api/v1/admin/api-keys              → List keys
GET    /api/v1/admin/api-keys/{id}/audit   → View audit log
PUT    /api/v1/admin/api-keys/{id}         → Revoke/restore
DELETE /api/v1/admin/api-keys/{id}         → Delete key
```

**Models to add** (in src/models.py):
```python
class APIKeyListResponse(BaseModel): ...
class AuditLogEntry(BaseModel): ...
class CreateAPIKeyRequest(BaseModel): ...
```

**Tests**: 44 tests total

---

### Phase 6.3: Symbol Enhancements (5.5 hours)
**What**: Verify scheduler loads symbols, add tracking

**What to verify** (in src/scheduler.py):
- `_load_symbols_from_db()` loads only active symbols
- Error handling for empty list
- Loads at startup

**What to add**:
- Set backfill_status='in_progress' before backfill
- Set backfill_status='completed' on success
- Set backfill_status='failed' + error message on failure
- Update last_backfill timestamp

**Endpoint enhancements**:
- Add record_count to response
- Add date_range to response
- Add validation_rate to response

**Tests**: 18 tests total

---

### Phase 6.4: Comprehensive Testing (4 hours)
**What**: Write 130+ tests for all components

**Test files to create**:
1. `tests/test_auth_middleware.py` (40 tests)
   - Path matching, header validation, key validation
   - Error responses, metadata injection, logging

2. `tests/test_symbol_manager_db.py` (35 tests)
   - CRUD operations, validation, constraints
   - Asset class, backfill tracking, soft delete

3. `tests/test_admin_endpoints.py` (40 tests)
   - Symbol endpoints, API key endpoints
   - Auth, validation, errors, concurrency

4. `tests/test_crypto_support.py` (15 tests)
   - Add crypto symbols, backfill crypto
   - Data validation, mixed assets

**Test commands**:
```bash
# All tests
pytest tests/ -v

# By file
pytest tests/test_auth_middleware.py -v
pytest tests/test_symbol_manager_db.py -v
pytest tests/test_admin_endpoints.py -v
pytest tests/test_crypto_support.py -v

# Coverage
pytest tests/ --cov=src --cov-report=html
```

**Target**: 95%+ coverage

---

### Phase 6.5: Crypto Support (2 hours)
**What**: Verify and test crypto symbols

**What to verify**:
- Polygon crypto endpoints exist
- BTC, ETH, SOL can be added
- Data format is handled correctly
- Backfill works with crypto

**What to test**:
- Add crypto symbol: BTC, ETH, SOL
- Backfill crypto data
- Data validation (crypto-specific)
- Mixed stock + crypto backfill

**Example**:
```python
# Add crypto symbol
await symbol_manager.add_symbol("BTC", "crypto")

# Backfill process handles crypto
if symbol_info['asset_class'] == 'crypto':
    endpoint = f"{symbol}USD"  # BTC -> BTCUSD
    result = await polygon_client.get_crypto_agg(endpoint)
else:
    result = await polygon_client.get_latest(symbol)
```

---

### Phase 6.6: Documentation (2 hours)
**What**: Write guides and examples

**Files to create**:
1. `PHASE_6_IMPLEMENTATION.md` (500 lines)
   - Architecture, components, flows, examples

2. `API_KEY_MANAGEMENT.md` (250 lines)
   - How to generate/revoke keys, best practices, examples

3. `CRYPTO_SYMBOLS.md` (200 lines)
   - Supported symbols, how to add, data availability

4. `DEPLOYMENT_WITH_AUTH.md` (250 lines)
   - Setup, migration, bootstrap, verification

**Update existing**:
- `DEVELOPMENT_STATUS.md` - Add Phase 6 section
- `main.py` docstrings - Document auth requirements

---

## Key Code Patterns

### API Key Validation
```python
# In middleware or endpoint
auth_service = get_auth_service()
is_valid, metadata = await auth_service.validate_api_key(api_key)

if is_valid:
    # Use metadata['id'], metadata['name'], etc.
    request.state.api_key_id = metadata['id']
else:
    # Return 401 Unauthorized
```

### Symbol Management
```python
# Get all active symbols
symbol_manager = get_symbol_manager()
symbols = await symbol_manager.get_all_symbols(active_only=True)

# Update symbol status
await symbol_manager.update_symbol_status(
    symbol,
    backfill_status='completed'
)

# Add new symbol (crypto)
result = await symbol_manager.add_symbol("BTC", "crypto")
```

### Database Queries
```python
# All use parameterized queries (asyncpg)
conn = await asyncpg.connect(db_url)

# SELECT
row = await conn.fetchrow("SELECT * FROM api_keys WHERE key_hash = $1", key_hash)
rows = await conn.fetch("SELECT * FROM tracked_symbols WHERE active = TRUE")

# INSERT
row = await conn.fetchrow(
    "INSERT INTO tracked_symbols (symbol, asset_class) VALUES ($1, $2) RETURNING *",
    symbol, asset_class
)

# UPDATE
await conn.execute(
    "UPDATE api_keys SET active = FALSE WHERE id = $1",
    key_id
)

await conn.close()
```

### Error Handling
```python
# In services
try:
    result = await some_operation()
    logger.info("Operation succeeded", extra={"key": value})
    return result
except ValueError as e:
    logger.warning("Operation failed (validation)", extra={"error": str(e)})
    raise
except Exception as e:
    logger.error("Operation failed (unexpected)", extra={"error": str(e)})
    raise

# In endpoints
try:
    result = await service_method()
    return result
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error("Endpoint error", extra={"error": str(e)})
    raise HTTPException(status_code=500, detail="Internal error")
```

### Testing Pattern
```python
@pytest.mark.asyncio
async def test_something():
    """Test description"""
    # Setup
    service = APIKeyService(database_url)
    
    # Execute
    result = await service.method()
    
    # Verify
    assert result is not None
    assert result.get('key') == expected_value
    logger.info("Test passed")
```

---

## Database Tables Reference

### api_keys
```sql
id (BIGSERIAL PRIMARY KEY)
key_hash (VARCHAR 64 UNIQUE) -- SHA256 hex
name (VARCHAR 100)
active (BOOLEAN)
created_at (TIMESTAMPTZ)
last_used (TIMESTAMPTZ)
last_used_endpoint (VARCHAR 200)
request_count (BIGINT)

Indexes:
- idx_api_keys_active ON api_keys(active)
- idx_api_keys_key_hash ON api_keys(key_hash)
```

### api_key_audit
```sql
id (BIGSERIAL PRIMARY KEY)
api_key_id (BIGINT FK) -- Foreign key to api_keys
endpoint (VARCHAR 200)
method (VARCHAR 10) -- GET, POST, etc.
status_code (INT)
timestamp (TIMESTAMPTZ)

Indexes:
- idx_api_key_audit_key_id ON api_key_audit(api_key_id)
- idx_api_key_audit_timestamp ON api_key_audit(timestamp DESC)
```

### tracked_symbols
```sql
id (BIGSERIAL PRIMARY KEY)
symbol (VARCHAR 20 UNIQUE)
asset_class (VARCHAR 20) -- 'stock', 'crypto', 'etf'
active (BOOLEAN)
date_added (TIMESTAMPTZ)
last_backfill (TIMESTAMPTZ)
backfill_status (VARCHAR 20) -- 'pending', 'in_progress', 'completed', 'failed'
backfill_error (TEXT)

Indexes:
- idx_tracked_symbols_active ON tracked_symbols(active)
- idx_tracked_symbols_asset_class ON tracked_symbols(asset_class)
- idx_tracked_symbols_symbol ON tracked_symbols(symbol)
```

---

## Common Commands

### Development
```bash
# Run specific test
pytest tests/test_auth.py::test_generate_api_key_format -v

# Run all tests with coverage
pytest tests/ --cov=src --cov-report=html

# Run tests matching pattern
pytest tests/ -k "test_api_key" -v

# Run with print output
pytest tests/ -v -s

# Run single file
pytest tests/test_admin_endpoints.py -v
```

### Database
```bash
# Check if tables exist
psql $DATABASE_URL -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"

# Check table schema
psql $DATABASE_URL -c "\d api_keys"
psql $DATABASE_URL -c "\d tracked_symbols"
psql $DATABASE_URL -c "\d api_key_audit"

# Query data
psql $DATABASE_URL -c "SELECT COUNT(*) FROM api_keys"
psql $DATABASE_URL -c "SELECT * FROM tracked_symbols WHERE active = TRUE"
```

### Application
```bash
# Start app
python main.py

# Test endpoint (no auth)
curl http://localhost:8000/health

# Test endpoint (with auth)
curl -H "X-API-Key: mdw_xxx" http://localhost:8000/api/v1/admin/symbols

# Generate API key locally
python -c "from src.services.auth import APIKeyService; print(APIKeyService.generate_api_key('test'))"
```

---

## Important URLs & Files

**Planning Documents**:
- `PHASE_6_PLAN.md` - Full plan (read first)
- `ARCHITECTURE_REVIEW.md` - Technical deep-dive
- `PHASE_6_CHECKLIST.md` - Implementation tasks
- `PHASE_6_SUMMARY.md` - Executive summary
- `PHASE_6_QUICK_REFERENCE.md` - This file

**Source Code**:
- `src/services/auth.py` - API key auth logic
- `src/services/symbol_manager.py` - Symbol CRUD
- `src/middleware/auth_middleware.py` - Request validation
- `src/models.py` - Pydantic models
- `main.py` - Endpoints and integration
- `src/scheduler.py` - Symbol loading

**Database**:
- `database/migrations/001_add_symbols_and_api_keys.sql` - Schema
- `database/sql/schema.sql` - Main schema

**Tests**:
- `tests/test_auth.py` - Auth tests (5 tests, 50 lines)
- `tests/test_auth_middleware.py` - To create (40 tests)
- `tests/test_symbol_manager_db.py` - To create (35 tests)
- `tests/test_admin_endpoints.py` - To create (40 tests)
- `tests/test_crypto_support.py` - To create (15 tests)

---

## Success Checklist (Copy & Paste)

When each phase is done, check off:

### Phase 6.1
- [ ] Migration service created and working
- [ ] Bootstrap script created and tested
- [ ] main.py calls migration runner at startup
- [ ] Database tables verified
- [ ] 14 migration tests passing

### Phase 6.2
- [ ] APIKeyService extended with 6 new methods
- [ ] 5 new API endpoints implemented
- [ ] Pydantic models created
- [ ] 44 API key management tests passing

### Phase 6.3
- [ ] Scheduler loads symbols from database
- [ ] Backfill status tracking working
- [ ] Endpoints enhanced with stats
- [ ] 18 symbol management tests passing

### Phase 6.4
- [ ] 40 middleware tests passing
- [ ] 35 database tests passing
- [ ] 40 endpoint tests passing
- [ ] Overall coverage > 95%

### Phase 6.5
- [ ] Crypto endpoints verified
- [ ] 15 crypto tests passing
- [ ] BTC, ETH, SOL working

### Phase 6.6
- [ ] All 4 documentation files created
- [ ] DEVELOPMENT_STATUS.md updated
- [ ] Code examples working
- [ ] Deployment guide complete

---

## Time Tracking

Copy this to track your progress:

```
Phase 6.1 Database Init
- [ ] Migration service: ___ hours
- [ ] Bootstrap script: ___ hours  
- [ ] Main.py changes: ___ hours
- [ ] Tests: ___ hours
TOTAL: ___ / 6 hours

Phase 6.2 API Key Management
- [ ] Extend APIKeyService: ___ hours
- [ ] Add endpoints: ___ hours
- [ ] Pydantic models: ___ hours
- [ ] Tests: ___ hours
TOTAL: ___ / 8 hours

Phase 6.3 Symbol Enhancements
- [ ] Verify scheduler: ___ hours
- [ ] Backfill tracking: ___ hours
- [ ] Endpoint enhancements: ___ hours
- [ ] Tests: ___ hours
TOTAL: ___ / 5.5 hours

Phase 6.4 Comprehensive Testing
- [ ] Middleware tests: ___ hours
- [ ] Database tests: ___ hours
- [ ] Endpoint tests: ___ hours
- [ ] Crypto tests: ___ hours
TOTAL: ___ / 4 hours

Phase 6.5 Crypto Support
- [ ] Verification: ___ hours
- [ ] Testing: ___ hours
TOTAL: ___ / 2 hours

Phase 6.6 Documentation
- [ ] Implementation guide: ___ hours
- [ ] Other guides: ___ hours
TOTAL: ___ / 2 hours

GRAND TOTAL: ___ / 27.5 hours
```

---

## Troubleshooting

### Problem: Table already exists error
**Solution**: Migration system uses IF NOT EXISTS, should be fine

### Problem: API key validation failing
**Solution**: 
1. Check X-API-Key header present
2. Check key_hash matches what's in database
3. Check key is marked active=TRUE

### Problem: Tests failing
**Solution**:
1. Check database URL is correct
2. Check tables exist: `psql $DATABASE_URL -c "\dt"`
3. Run with `-v` and `-s` for more output
4. Check asyncio event loop setup in conftest.py

### Problem: Scheduler not loading symbols
**Solution**:
1. Check tracked_symbols table has data
2. Check symbols are active=TRUE
3. Check _load_symbols_from_db() method exists
4. Check logs for load errors

### Problem: Crypto backfill failing
**Solution**:
1. Check Polygon API key has crypto access
2. Check endpoint format (e.g., BTCUSD not BTC)
3. Check asset_class is 'crypto'
4. Check data format handling

---

## Final Notes

✅ **This is a well-structured project** with solid foundations.

✅ **You have clear next steps** in the planning documents.

✅ **No blocking issues** - everything can be implemented.

✅ **Timeline is realistic** - 20-25 hours of focused work.

✅ **You're ready to start** Phase 6.1 whenever you're ready.

Good luck! 🚀

---

**Reference Created**: November 10, 2025  
**Status**: Ready to Use  
**Last Updated**: November 10, 2025
