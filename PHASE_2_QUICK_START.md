# Phase 2: Quick Start Guide

## Setup

1. **Ensure API is running:**
```bash
python main.py
# or
uvicorn main:app --reload
```

2. **Ensure database is initialized:**
```bash
pytest tests/test_phase_1_monitoring.py -v  # Run Phase 1 tests first
```

3. **Have API key ready:**
```bash
export POLYGON_API_KEY="your_key_here"
```

---

## Run Phase 2 Tests

### 1. Load Tests (30 minutes)

**Test cached symbol performance:**
```bash
pytest tests/test_phase_2_validation.py::test_load_single_symbol_cached -v -s
```

Expected output:
```
LOAD TEST: Cached Symbol (AAPL 1d)
============================================================
Total Requests: 100
Successful: 100
Success Rate: 100.0%
Avg Response Time: 245.3ms
P50: 230ms | P95: 480ms | P99: 650ms
Throughput: 18.4 req/sec
Total Duration: 5.43s
```

**Test mixed symbols:**
```bash
pytest tests/test_phase_2_validation.py::test_load_uncached_symbols -v -s
```

**Test with variable limits:**
```bash
pytest tests/test_phase_2_validation.py::test_load_variable_limits -v -s
```

**Test with variable timeframes:**
```bash
pytest tests/test_phase_2_validation.py::test_load_variable_timeframes -v -s
```

**Run all at once:**
```bash
pytest tests/test_phase_2_validation.py -k "load" -v -s
```

---

### 2. RTO/RPO Definition (5 minutes)

```bash
pytest tests/test_phase_2_validation.py::test_rto_rpo_requirements -v -s
```

Expected output:
```
RTO/RPO DEFINITION - Market Data API
================================================================================

### Feature Staleness Thresholds ###

FRESH:
  Threshold: 1 hours
  Action: Return with timestamp

AGING:
  Threshold: 6 hours
  Action: Return with staleness warning

STALE:
  Threshold: 24 hours
  Action: Return with stale warning + cache lifespan

MISSING:
  Threshold: None hours
  Action: Return 404 with explanation, trigger manual enrichment

### RTO by Failure Type ###

SCHEDULER_CRASH:
  RTO: 5 minutes
  Procedure: Systemd auto-restart on failure

POLYGON_API_RATE_LIMIT:
  RTO: 30 minutes
  Procedure: Implement exponential backoff (1s, 5s, 30s, 5m)

DATABASE_CONNECTION_LOSS:
  RTO: 2 minutes
  Procedure: Automatic reconnect with exponential backoff

FEATURE_COMPUTATION_FAILURE:
  RTO: 1 minutes
  Procedure: Skip failed symbol, log error, continue with next

### RPO by Symbol Criticality ###

CRITICAL_SYMBOLS:
  Acceptable Staleness: 1 hours
  Backfill Frequency: Every 15 minutes

STANDARD_SYMBOLS:
  Acceptable Staleness: 4 hours
  Backfill Frequency: Every hour

LOW_PRIORITY_SYMBOLS:
  Acceptable Staleness: 24 hours
  Backfill Frequency: Daily

✓ RTO/RPO document saved to /tmp/rto_rpo_definition.json
```

Output file saved to: `/tmp/rto_rpo_definition.json`

---

### 3. Backfill Performance Baseline (2-5 hours depending on data)

```bash
python scripts/phase_2_backfill_baseline.py
```

Expected output:
```
Phase 2: BACKFILL PERFORMANCE BASELINE
================================================================================
Symbols: 25
Timeframes: 5
Total Jobs: 125
History: 365 days
================================================================================

--- AAPL ---
  5m: Fetching... (1234 records, 2.34s) -> Inserting... (1234 inserted, 1.23s)
  15m: Fetching... (312 records, 0.54s) -> Inserting... (312 inserted, 0.31s)
  1h: Fetching... (87 records, 0.19s) -> Inserting... (87 inserted, 0.09s)
  4h: Fetching... (22 records, 0.12s) -> Inserting... (22 inserted, 0.02s)
  1d: Fetching... (5 records, 0.08s) -> Inserting... (5 inserted, 0.01s)

--- MSFT ---
  5m: Fetching... (1198 records, 2.31s) -> Inserting... (1198 inserted, 1.19s)
  ...

================================================================================
BACKFILL PERFORMANCE BASELINE - RESULTS
================================================================================

### Overall Metrics ###
Total Duration: 487.23s (8.1 minutes)
Total Records: 125,432
Throughput: 257.4 records/sec
Completed Jobs: 125 / 125
Success Rate: 100.0%

### Time Breakdown ###
Polygon API: 312.1s (64%)
DB Inserts: 175.1s (36%)

### Bottleneck Identification ###
Slowest Job: AAPL/5m (4.57s)
Slowest Timeframe: 5m (avg 2.34s)

⚠️  PRIMARY BOTTLENECK: Polygon API (64% of time)
   → Recommendations:
     • Implement request batching
     • Add rate-limit aware backoff
     • Consider parallel API clients (staggered)

✓ Report saved to /tmp/phase_2_backfill_baseline.json
```

Output file saved to: `/tmp/phase_2_backfill_baseline.json`

---

## Interpret Results

### Load Test Analysis

**Good (P95 < 1 second):**
- System handles concurrent load well
- Caching is effective
- DB queries are efficient
- Proceed to Phase 3 (targeted optimization)

**Warning (P95 = 1-3 seconds):**
- System is strained under load
- Tail latency is concerning
- Phase 3 should focus on cache + indexes

**Critical (P95 > 3 seconds):**
- System struggling
- Consider adding read replicas
- Phase 3 should be more aggressive (Redis cache + batch endpoint)

### Backfill Baseline Analysis

**API > 60% of time:**
- Rate limit is bottleneck
- Fix: Exponential backoff + batch requests

**DB > 60% of time:**
- Query/insert is bottleneck
- Fix: Indexes + bulk insert + batch optimization

**Balanced (40-60% each):**
- Feature computation is bottleneck
- Fix: Profile + vectorize + parallel processing

---

## Phase 2 Checklist

- [ ] Load test: Cached symbol (100 concurrent requests)
- [ ] Load test: Mixed symbols (AAPL, MSFT, GOOGL)
- [ ] Load test: Variable limits (100, 500, 1000)
- [ ] Load test: Variable timeframes (5m, 15m, 1h, 4h, 1d)
- [ ] RTO/RPO document created
- [ ] Backfill baseline complete (25 symbols × 5 timeframes)
- [ ] Bottleneck identified (API vs DB vs Computation)
- [ ] Phase 3 priorities defined
- [ ] Results documented for Phase 3 planning

---

## Next Steps (Phase 3)

Once Phase 2 identifies the bottleneck:

1. **If API bottleneck:**
   - [ ] Implement exponential backoff for rate limits
   - [ ] Batch similar requests together
   - [ ] Add request queuing
   - [ ] Re-run baseline to measure improvement

2. **If DB bottleneck:**
   - [ ] Add indexes on (symbol, timeframe, features_computed_at)
   - [ ] Implement bulk insert
   - [ ] Test batch size optimization
   - [ ] Consider Redis caching for top 50 symbols

3. **If Computation bottleneck:**
   - [ ] Profile feature computation code
   - [ ] Optimize numpy/pandas operations
   - [ ] Consider vectorization improvements
   - [ ] Parallel processing per symbol

---

## Troubleshooting

**Load tests fail with connection errors:**
```bash
# Make sure API is running
python main.py
# and accessible at http://localhost:8000/health
```

**Backfill baseline has missing data:**
```bash
# Make sure database has some data
pytest tests/test_phase_1_monitoring.py::test_scheduler_health -v
```

**Polygon API rate limited:**
```bash
# Add exponential backoff to polygon_client.py
# (This is Phase 3 work, note it for planning)
```

---

## Save Results

All test results are automatically saved:

- Load test metrics: Printed to console
- RTO/RPO definition: `/tmp/rto_rpo_definition.json`
- Backfill baseline: `/tmp/phase_2_backfill_baseline.json`

Copy these files to version control:
```bash
cp /tmp/rto_rpo_definition.json docs/rto_rpo_definition.json
cp /tmp/phase_2_backfill_baseline.json docs/phase_2_backfill_baseline.json
git add docs/
git commit -m "Phase 2: Validation results"
```

