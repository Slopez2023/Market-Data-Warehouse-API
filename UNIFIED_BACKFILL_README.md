# Unified Backfill Implementation - README

## What's New

The backfill system has been unified to eliminate divergent code paths between website and CLI. All backfills now go through `BackfillOrchestrator` which wraps `master_backfill.py`.

**Before:**
- Website: Simple backfill (fetch + insert, no validation)
- CLI: Comprehensive backfill (gap detection + validation + retries)
- **Problem:** Two different approaches, risk of using the wrong one

**After:**
- Website: Uses master_backfill.py orchestrator
- CLI: Uses master_backfill.py directly
- **Solution:** Same logic, single code path, guaranteed validation

## Quick Start

### For API Users
```bash
# Trigger a backfill
curl -X POST http://localhost:8000/api/v1/backfill \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "MSFT"],
    "timeframes": ["1d", "1h"]
  }'

# Response:
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "message": "Backfill orchestrated via master_backfill.py (gap detection + validation enabled)"
}

# Check status
curl http://localhost:8000/api/v1/backfill/status/550e8400-e29b-41d4-a716-446655440000
```

### For CLI Users
```bash
# Nothing changes - still works the same
python master_backfill.py --symbols AAPL,MSFT --timeframes 1d,1h

# Now the website uses the same logic!
```

## Architecture

```
┌─────────────────────┐
│ Website Backfill    │
│ POST /api/v1/backfill
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ BackfillOrchestrator                │
│ (src/services/backfill_orchestrator) │
│ - Subprocess execution              │
│ - Result parsing                    │
│ - Audit logging                     │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│ master_backfill.py (unchanged)      │
│ - Gap detection                     │
│ - Validation & quality scoring      │
│ - Retry logic with exponential wait │
│ - Parallel processing               │
└──────────┬──────────────────────────┘
           │
           ▼
        Database
```

**Both CLI and API use the same master_backfill.py logic → No divergence**

## What's Different

### Old Backfill Worker (DEPRECATED)
```python
from src.services.backfill_worker import init_backfill_worker
# ✗ Will raise NotImplementedError
# Migration error message explains what to do instead
```

### New Backfill Orchestrator
```python
from src.services.backfill_orchestrator import init_backfill_orchestrator, get_backfill_orchestrator

# Initialize on startup (done automatically in main.py)
init_backfill_orchestrator(database_url, polygon_api_key)

# Use in your handler
orchestrator = get_backfill_orchestrator()
result = await orchestrator.trigger_backfill(
    symbols=["AAPL"],
    timeframes=["1d"],
    days=365
)
```

## Features

✓ **Gap Detection** - Automatically detects and retries missing data  
✓ **Validation** - Quality scoring and data validation built-in  
✓ **Audit Trail** - Full tracking in `backfill_audit_log` table  
✓ **Parallel Processing** - 3 concurrent symbols by default  
✓ **Rate Limiting** - Respects Polygon API rate limits  
✓ **Retry Logic** - Exponential backoff for failed gaps  
✓ **One Code Path** - Website and CLI use identical logic  

## Files Changed

### New
- `src/services/backfill_orchestrator.py` - Main implementation
- `database/migrations/017_backfill_audit_log.sql` - Audit schema
- Documentation files (3x)

### Modified
- `main.py` - Endpoint and startup changes
- `src/services/backfill_worker.py` - Marked as deprecated
- `AGENTS.md` - Updated guidelines

### Unchanged
- `master_backfill.py` - Still works as-is
- All other services and routes
- CLI behavior

## Verification

Run the verification script:
```bash
bash VERIFY_UNIFIED_BACKFILL.sh
```

Output should show all checks passing:
```
✓ Orchestrator exists
✓ Deprecated worker exists
✓ Audit log migration exists
✓ Full documentation exists
✓ All tests PASSED
✓✓✓ ALL VERIFICATION CHECKS PASSED ✓✓✓
```

## Documentation

- **UNIFIED_BACKFILL_IMPLEMENTATION.md** - Complete technical documentation
- **UNIFIED_BACKFILL_SUMMARY.md** - Executive summary
- **UNIFIED_BACKFILL_CHECKLIST.md** - Implementation checklist
- **AGENTS.md** - Updated with unified backfill info

## Testing

```bash
# Run simple tests
python test_unified_backfill_simple.py
# Output: ✓✓✓ All unified backfill tests passed

# Run comprehensive tests
pytest test_unified_backfill.py -v
```

## Deployment

1. Deploy the code
2. Run migrations (auto-runs: 017_backfill_audit_log.sql)
3. Restart API server
4. Test: `curl -X POST /api/v1/backfill`
5. Monitor: Check backfill_audit_log for events

## Audit Trail

Every backfill is logged to `backfill_audit_log`:

```sql
SELECT * FROM backfill_audit_log 
WHERE job_id = '550e8400-e29b-41d4-a716-446655440000';

-- Returns:
-- job_id: 550e8400-e29b-41d4-a716-446655440000
-- event: 'backfill_completed'
-- user_id: null (can be extracted from API key in future)
-- details: {"symbols": ["AAPL"], "total_candles_inserted": 250, ...}
-- created_at: 2024-11-21 10:31:00
```

## Troubleshooting

### "Backfill orchestrator not initialized"
- Check DATABASE_URL is set
- Check POLYGON_API_KEY is set
- Check app startup logs

### "NotImplementedError from backfill_worker"
- You're using deprecated code
- Switch to `BackfillOrchestrator`
- See UNIFIED_BACKFILL_IMPLEMENTATION.md for migration

### Subprocess fails
- Check master_backfill.py runs manually: `python master_backfill.py`
- Check PYTHONPATH is set
- Check /tmp/master_backfill_results.json for detailed output

## Future Enhancements

Optional additions (don't break current implementation):
- Redis/Celery job queue for distributed backfills
- Audit API endpoint for querying backfill history
- User attribution via API key parsing
- Backfill scheduling API

## Support

See documentation files for:
- Detailed architecture: UNIFIED_BACKFILL_IMPLEMENTATION.md
- API examples: UNIFIED_BACKFILL_SUMMARY.md
- Migration guidance: UNIFIED_BACKFILL_IMPLEMENTATION.md
- Checklist: UNIFIED_BACKFILL_CHECKLIST.md

## Summary

✓ Website backfill now uses master_backfill.py (same as CLI)  
✓ Gap detection and validation enabled on all backfills  
✓ Old simplified path is blocked with clear error message  
✓ Audit trail tracks all backfill activity  
✓ Ready for production deployment  

**You won't need to come back to this.**
