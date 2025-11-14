# Phase 2: Validation (Week 3)

## Goal
**Prove what's actually broken before fixing it.** Run load tests and performance baselines to identify bottlenecks quantitatively.

## Three Deliverables

### 1. Load Test Report
**What:** Simulate 100 concurrent requests to `/api/v1/features/quant/{symbol}?limit=500`

**Measure:**
- Response time (avg, p50, p95, p99, max)
- Success rate
- Throughput (requests/sec)
- CPU/memory impact
- Identify which timeframes/limits are slowest

**Test Scenarios:**
- **Cached Symbol:** 100 requests for AAPL (should be fast)
- **Uncached Mix:** 100 requests split between AAPL, MSFT, GOOGL
- **Variable Limits:** 100 requests with limit=100, 500, 1000 (measure impact)
- **Variable Timeframes:** 100 requests across 5m, 15m, 1h, 4h, 1d

**Run:**
```bash
# Run all load tests (requires API running)
pytest tests/test_phase_2_validation.py::test_load_single_symbol_cached -v -s
pytest tests/test_phase_2_validation.py::test_load_uncached_symbols -v -s
pytest tests/test_phase_2_validation.py::test_load_variable_limits -v -s
pytest tests/test_phase_2_validation.py::test_load_variable_timeframes -v -s
```

**Expected Metrics:**
- Avg response time: < 500ms (target)
- P95 latency: < 1000ms
- P99 latency: < 2000ms
- Success rate: > 99%
- Throughput: > 20 req/sec under load

**Output:** `load_test_report.json` with bottleneck analysis and recommendations

---

### 2. RTO/RPO Definition
**What:** Document acceptable data staleness, failure recovery procedures, and symbol criticality

#### Feature Staleness Thresholds

| Status | Threshold | Action |
|--------|-----------|--------|
| **Fresh** | < 1h | Return with timestamp |
| **Aging** | 1-6h | Return with warning: "features aging" |
| **Stale** | 6-24h | Return with warning: "last computed 12h ago" |
| **Missing** | Never | Return 404 + trigger manual enrichment |

#### RTO (Recovery Time Objective) by Failure Type

| Failure Type | RTO | Procedure | Fallback |
|---|---|---|---|
| **Scheduler Crash** | 5 min | Systemd auto-restart | Manual trigger via API |
| **Polygon API Rate Limit** | 30 sec | Exponential backoff (1s→5s→30s→5m) | Use cached data + warning |
| **DB Connection Loss** | 2 min | Auto-reconnect with backoff | Return cached + staleness warning |
| **Feature Computation Failure** | 1 sec | Skip symbol, log, continue | Return cached + error flag |

#### RPO (Recovery Point Objective) by Symbol Criticality

| Criticality | Symbols | Staleness | Frequency | Max Data Loss |
|---|---|---|---|---|
| **Critical** | SPY, QQQ, BTC, ETH | 1h | Every 15 min | 0 records |
| **Standard** | AAPL, MSFT, GOOGL, AMZN, TSLA | 4h | Every hour | 1h data |
| **Low Priority** | Others | 24h | Daily | 24h data |

#### Scheduler Recovery Procedures

**Normal Operation:**
- Run backfill at configured time daily (default: 01:30 UTC)
- Process all symbols with their configured timeframes
- Log execution with timestamp, success/failure counts

**After Scheduler Crash:**
1. Systemd restarts service (5-minute delay)
2. Service loads last checkpoint from `scheduler_execution_log`
3. Resume from checkpoint (skip already-processed symbols)
4. Continue for remaining symbols
5. Log recovery: "Resumed from checkpoint after crash"

**After Extended Downtime (> 6 hours):**
1. Manual trigger: `POST /api/v1/admin/backfill/trigger?force=true`
2. Backfill in priority order:
   - **Phase 1:** Critical symbols (SPY, QQQ, BTC, ETH) - all timeframes
   - **Phase 2:** Standard symbols (AAPL, MSFT, etc.) - all timeframes
   - **Phase 3:** Low-priority symbols - catch up overnight

**Monitoring & Alerts:**
- Alert if no successful backfill > 6 hours: `WARNING`
- Alert if > 20% symbol failures in single run: `CRITICAL` (page engineer)
- Alert if > 10% symbols missing features: `WARNING` (trigger manual enrichment)

**Run:**
```bash
# Generate RTO/RPO definition
pytest tests/test_phase_2_validation.py::test_rto_rpo_requirements -v -s
```

**Output:** `RTO_RPO_DEFINITION.md` + `rto_rpo_definition.json` (machine-readable)

---

### 3. Backfill Performance Baseline
**What:** Time 50 symbols × 5 timeframes backfill to identify bottleneck

**Measure:**
- **Per Symbol/Timeframe:**
  - Records fetched from Polygon API
  - Records inserted into DB
  - API duration vs DB duration (which takes longer?)
  - Records/second throughput
  
- **Totals:**
  - API time: X seconds (Y% of total)
  - DB time: X seconds (Y% of total)
  - Slowest symbol
  - Slowest timeframe
  - Bottleneck identification

**Test Symbols (25):**
```
AAPL, MSFT, GOOGL, AMZN, TSLA  # Top 5 stocks
NVDA, META, NFLX, AVGO, ASML  # Tech stocks
BRK.B, JPM, V, WMT, JNJ       # Diverse sectors
BTC, ETH, XRP, SOL, ADA        # Crypto (5)
SPY, QQQ, DIA, IWM, EEM        # ETFs (5)
```

**Timeframes (5):**
```
5m, 15m, 1h, 4h, 1d
= 125 total jobs
```

**Run:**
```bash
# Run backfill baseline (requires API key)
python scripts/phase_2_backfill_baseline.py
```

**Expected Output:**
```
Phase 2: Backfill Performance Baseline
================================================================================
Total Duration: 487.23s
Total Records: 125,432
Throughput: 257.4 records/sec
Completed Jobs: 125 / 125 (Success Rate: 100%)

### Time Breakdown ###
Polygon API: 312.1s (64%)    ← BOTTLENECK
DB Inserts: 175.1s (36%)

### Bottleneck Identification ###
Slowest Job: AAPL/5m (4.82s)
Slowest Timeframe: 5m (avg 2.8s)

⚠️  PRIMARY BOTTLENECK: Polygon API (64% of time)
   → Recommendations:
     • Implement request batching
     • Add rate-limit aware backoff
     • Consider parallel API clients (staggered)
```

**Output:** `phase_2_backfill_baseline.json` with detailed breakdown

---

## Decision Matrix: Identify True Bottleneck

After running baseline, determine the bottleneck:

### If API > 60% of time:
```
Bottleneck: Polygon API Rate Limits
Evidence: API takes 2-3x longer than DB

Phase 3 Actions:
- Implement exponential backoff (backoff_base=1s, max=5m)
- Batch similar timeframe requests together
- Stagger backfill: process 5 symbols concurrently instead of sequential
- Implement circuit breaker: if rate limit, pause 5 minutes
```

### If DB > 60% of time:
```
Bottleneck: Database Query/Insert Performance
Evidence: DB inserts take 2-3x longer than API

Phase 3 Actions:
- Add indexes on (symbol, timeframe, features_computed_at)
- Use bulk insert instead of row-by-row insert
- Batch size optimization (test 100, 500, 1000 records per batch)
- Consider TimescaleDB hypertable partitioning by date
- Add Redis cache for hot symbols (top 50)
```

### If Balanced (< 60% either):
```
Bottleneck: Feature Computation Complexity
Evidence: Neither API nor DB is clearly slower

Phase 3 Actions:
- Profile feature computation code (volatility, momentum, structure)
- Check if numpy/pandas vectorization can be improved
- Consider parallel computation across symbols
- Look for N+1 query patterns in enrichment logic
```

---

## Acceptance Criteria

✓ Load test report generated with P95/P99 latencies  
✓ RTO/RPO document defines staleness thresholds and recovery procedures  
✓ Backfill baseline identifies primary bottleneck (API vs DB vs Computation)  
✓ Recommendations provided for Phase 3 optimization  
✓ All results saved to JSON for dashboard integration  

---

## Timeline

- **Monday:** Run load tests, analyze results
- **Tuesday:** Create RTO/RPO definition document
- **Wednesday:** Run backfill baseline, identify bottleneck
- **Thursday:** Compile results, create Phase 3 plan
- **Friday:** Review with team, finalize Phase 3 priorities

---

## Phase 3 Teaser

Once Phase 2 proves the bottleneck (e.g., "API is 70% of backfill time"), Phase 3 will implement targeted fixes:

- **If API:** Exponential backoff + batch requests + parallel clients
- **If DB:** Indexes + bulk insert + batch optimization
- **If Computation:** Profile & vectorize + parallel processing

**Before/After Metrics:** Re-run backfill baseline after each fix to prove improvement.

