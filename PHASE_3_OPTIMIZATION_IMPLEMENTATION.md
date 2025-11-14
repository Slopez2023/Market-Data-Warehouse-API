# Phase 3: Optimization Implementation Guide

## Status: IN PROGRESS

This document tracks the implementation of Phase 3 optimizations based on identified bottleneck: **API (64%)** vs DB (36%).

## Bottleneck Analysis (From Phase 2)
```
Polygon API: 312.1s (64%)    ← PRIMARY BOTTLENECK
DB Inserts: 175.1s (36%)
Total: 487.2s
```

### Root Causes
1. **Sequential API requests** - Processing one symbol at a time
2. **Rate limiting** - Polygon API limit of 150 req/min causes backoff delays
3. **Per-request overhead** - Network latency + API processing time

## Phase 3 Path A: API Optimization

### Fix 1: Enhanced Exponential Backoff for Rate Limits ✓
**Status:** IMPLEMENTING
**File:** `src/clients/polygon_client.py`

**Changes:**
- Upgrade retry strategy from `multiplier=1, min=2, max=10` to `multiplier=1, min=1, max=300`
- Increases max backoff from 10s to 5 minutes to handle rate limits better
- Adds rate limit tracking counter

**Expected Impact:** -12% latency (312.1s → 274.3s)

### Fix 2: Request Batching by Timeframe
**Status:** PENDING
**File:** `src/clients/polygon_client.py`
**File:** `src/scheduler.py`

**Objective:** Group multiple symbols with same timeframe, stagger requests to avoid rate limit spikes

**Expected Impact:** -10% latency (274.3s → 246.9s)

### Fix 3: Parallel Symbol Processing (Staggered)
**Status:** PENDING
**File:** `src/scheduler.py`

**Objective:** Instead of processing 1 symbol sequentially, process 3 symbols in parallel with 5s stagger

**Expected Impact:** -40-50% latency (246.9s → 124-148s)

## Implementation Progress

### Completed ✓
- [ ] Phase 2 baseline execution
- [ ] Bottleneck identification (API 64% confirmed)

### In Progress 🔄
- [ ] Fix 1: Enhanced exponential backoff
- [ ] Fix 2: Request batching
- [ ] Fix 3: Parallel processing

### Testing
- [ ] Unit tests for new retry logic
- [ ] Integration tests with rate limiting
- [ ] Performance benchmark (re-run Phase 2 baseline)

## Validation Strategy

### Before Optimization
```
Baseline: 487.2s total
API: 312.1s (64%)
DB: 175.1s (36%)
```

### After Each Fix
Will re-run Phase 2 baseline and track progression:
```
Expected progression:
Baseline:      487.2s
After Fix 1:   ~430s (12% improvement)
After Fix 2:   ~380s (22% improvement)  
After Fix 3:   ~240s (50% improvement)
Goal:          >30% improvement ✅
```

## Testing Commands

```bash
# Run Phase 2 baseline to measure progress
python scripts/phase_2_backfill_baseline.py

# Run unit tests
pytest tests/test_polygon_client.py -v

# Run integration tests
pytest tests/ -k "polygon" -v
```

## Rollback Plan

If any fix causes issues:
```bash
# Partial rollback
git revert <commit-hash>

# Or use feature flags
if config.ENABLE_PHASE3_FIX_N:
    use_new_code()
else:
    use_old_code()
```

## Success Criteria

- [x] Identified bottleneck (API 64%)
- [ ] Implement Fix 1 (exponential backoff)
- [ ] Implement Fix 2 (batching)
- [ ] Implement Fix 3 (parallel processing)
- [ ] Re-run baseline shows 30-40% improvement
- [ ] Success rate remains >99%
- [ ] No regressions in other areas
- [ ] CPU utilization stays <80%
- [ ] Memory usage stays <2GB

## Timeline

- Day 1: Fix 1 (exponential backoff) + Testing
- Day 2: Fix 2 (batching) + Testing
- Day 3: Fix 3 (parallel) + Testing
- Day 4: Full baseline run + Performance analysis
- Day 5: Documentation + Completion

## Next Steps

1. Implement enhanced exponential backoff in polygon_client.py
2. Add request batching logic to scheduler
3. Implement parallel symbol processing
4. Test each fix incrementally
5. Run full Phase 2 baseline to validate improvements
