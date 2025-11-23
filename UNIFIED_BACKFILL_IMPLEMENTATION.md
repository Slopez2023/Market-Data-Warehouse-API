# Unified Backfill Implementation

## Overview

This implementation consolidates all backfill logic into a single code path using `master_backfill.py` as the orchestrator. The problem it solves:

**Before:** Website had `backfill_worker.py` (simplified, no validation/gap detection) while CLI used `master_backfill.py` (comprehensive with validation/gaps/retries). This created two divergent code paths and risk of using the wrong approach.

**After:** Single unified orchestrator wraps `master_backfill.py`, ensuring both website and CLI use identical logic:
- Gap detection & data validation
- Retry logic for failed gaps
- Quality scoring
- Parallel processing with rate limiting
- Full audit trail

## Architecture

### Components

1. **BackfillOrchestrator** (`src/services/backfill_orchestrator.py`)
   - Wraps master_backfill.py CLI
   - Triggers subprocess with proper arguments
   - Parses results from master_backfill_results.json
   - Handles audit logging
   - Single point of truth for backfill logic

2. **Unified API Endpoint** (`main.py`)
   - `POST /api/v1/backfill` - new unified endpoint
   - Calls BackfillOrchestrator.trigger_backfill()
   - Returns job_id for polling progress
   - Clear messaging that gap detection is enabled

3. **Deprecated BackfillWorker** (`src/services/backfill_worker.py`)
   - Raises NotImplementedError with migration instructions
   - Prevents accidental use of old simplified logic
   - Guides developers to use orchestrator

4. **Audit Logging** (new migration)
   - Table: `backfill_audit_log`
   - Tracks who triggered backfill, when, for what symbols
   - Records success/failure with details
   - Queries available at `/api/v1/backfill/audit` (future)

## Implementation Details

### Flow: Website Backfill Request

```
POST /api/v1/backfill
  ↓
unified_backfill() endpoint handler
  ↓
BackfillOrchestrator.trigger_backfill()
  ↓
  1. Audit log: backfill_started
  2. Build master_backfill.py command
  3. Execute as subprocess
  4. Parse results from /tmp/master_backfill_results.json
  5. Audit log: backfill_completed (with stats)
  ↓
Return {job_id, status, results}
```

### Flow: CLI Backfill Request

```
python master_backfill.py --symbols AAPL --timeframes 1d
  ↓
MasterBackfiller.run()
  ↓
  1. Load symbols from database
  2. Stage 1: Backfill OHLCV (calls backfill_ohlcv.py)
  3. Stage 2: Detect gaps
  4. Stage 3: Retry gaps with exponential backoff
  5. Save results to /tmp/master_backfill_results.json
  ↓
✓ Complete with gap detection + validation
```

**Both paths use identical logic after reaching master_backfill.py**

## Migration Path for Existing Code

### Old Code (Deprecated)

```python
# Before: Used simplified backfill_worker
from src.services import backfill_worker
from src.services.backfill_worker import init_backfill_worker

# This is now deprecated and will raise NotImplementedError
init_backfill_worker(db, data_client)
backfill_worker.enqueue_backfill_job(...)
```

### New Code (Unified)

```python
# After: Use orchestrator for both API and CLI
from src.services.backfill_orchestrator import init_backfill_orchestrator, get_backfill_orchestrator

# Initialize in main.py startup
init_backfill_orchestrator(database_url, polygon_api_key)

# Use in endpoint handler
orchestrator = get_backfill_orchestrator()
result = await orchestrator.trigger_backfill(
    symbols=["AAPL", "MSFT"],
    timeframes=["1d"],
    days=365
)
```

## API Changes

### New Unified Endpoint

**POST /api/v1/backfill**

Request:
```json
{
  "symbols": ["AAPL", "GOOGL"],
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "timeframes": ["1d", "1h", "5m"]
}
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "symbols": ["AAPL", "GOOGL"],
  "timeframes": ["1d", "1h", "5m"],
  "message": "Backfill orchestrated via master_backfill.py (gap detection + validation enabled)",
  "check_status": "/api/v1/backfill/status/550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-11-21T10:31:00Z"
}
```

### Polling Endpoint (Unchanged)

**GET /api/v1/backfill/status/{job_id}**

Returns current status, progress, and results.

## Audit Trail

### Audit Log Table

```sql
CREATE TABLE backfill_audit_log (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL,
    event VARCHAR(50) NOT NULL,     -- 'backfill_started', 'backfill_completed', etc.
    user_id VARCHAR(255),           -- Optional, from API key
    details JSONB,                  -- Symbols, timeframes, error messages, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Logged Events

- `backfill_started` - Backfill initiated
- `backfill_completed` - Backfill finished successfully
- `backfill_failed` - Subprocess returned error
- `backfill_error` - Exception during orchestration

### Example Queries

```sql
-- Track all backfills for a job
SELECT * FROM backfill_audit_log WHERE job_id = '...';

-- See latest backfill activities
SELECT * FROM backfill_audit_log ORDER BY created_at DESC LIMIT 20;

-- Audit by event type
SELECT event, COUNT(*) FROM backfill_audit_log GROUP BY event;
```

## Database Migrations

New migration: `017_backfill_audit_log.sql`

- Creates `backfill_audit_log` table
- Adds indexes on job_id, event, user_id, created_at
- Auto-run on next app startup via migration system

## Testing

### Unit Tests

```bash
# Basic functionality tests
python test_unified_backfill_simple.py

# Comprehensive tests (with mocking)
pytest test_unified_backfill.py -v
```

### Integration Testing

```bash
# Trigger through API
curl -X POST http://localhost:8000/api/v1/backfill \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL"], "timeframes": ["1d"]}'

# Check status
curl http://localhost:8000/api/v1/backfill/status/{job_id}

# Verify audit log
SELECT * FROM backfill_audit_log WHERE job_id = '{job_id}';
```

## Benefits

1. **Single Code Path** - No divergence between CLI and API
2. **Guaranteed Validation** - All backfills go through master_backfill.py
3. **Gap Detection** - Automatic detection and retry of missing data
4. **Audit Trail** - Full tracking of who triggered what and when
5. **No Accidental Simplification** - Old simplified worker is blocked with clear error message
6. **Future Extensibility** - Easy to add job queue (Redis/Celery) if needed

## Future Enhancements

1. **Job Queue (Optional)**
   - Add Redis/Celery for distributed backfills
   - `BackfillOrchestrator` would submit to queue instead of direct subprocess
   - Workers would execute master_backfill.py

2. **Audit API Endpoint**
   - `GET /api/v1/backfill/audit?job_id=...`
   - Query backfill_audit_log with filtering/pagination

3. **User Attribution**
   - Extract user_id from API key
   - Store in audit_log for full accountability

4. **Backfill Scheduling**
   - `POST /api/v1/backfill/schedule` for recurring backfills
   - Scheduler submits to orchestrator

## Troubleshooting

### "Backfill worker not initialized" Error

This means the startup didn't initialize the orchestrator. Check:
1. DATABASE_URL is set
2. POLYGON_API_KEY is set
3. App startup logs show "Backfill orchestrator initialized successfully"

### Old Code Raising NotImplementedError

You're using deprecated `backfill_worker`. Update to:
```python
from src.services.backfill_orchestrator import init_backfill_orchestrator, get_backfill_orchestrator
```

### Master Backfill Subprocess Failing

Check:
1. master_backfill.py exists
2. PYTHONPATH is set correctly in subprocess
3. Database is accessible from app process
4. Check /tmp/master_backfill_results.json for detailed output

## Files Changed/Created

### Created
- `src/services/backfill_orchestrator.py` - Main orchestrator implementation
- `database/migrations/017_backfill_audit_log.sql` - Audit logging schema
- `UNIFIED_BACKFILL_IMPLEMENTATION.md` - This documentation

### Modified
- `main.py` - Replaced backfill_worker with backfill_orchestrator
- `src/services/backfill_worker.py` - Deprecated with clear error message

### No Changes Needed
- `master_backfill.py` - Already the comprehensive implementation
- `scripts/backfill_ohlcv.py` - Used by master_backfill.py
- Other services - orchestrator is a drop-in replacement

## Summary

This implementation eliminates the divergent backfill code paths by making the orchestrator a thin wrapper around `master_backfill.py`. Both website and CLI now use identical logic, ensuring consistent gap detection, validation, and retry behavior. The audit log provides full accountability for all backfill operations.
