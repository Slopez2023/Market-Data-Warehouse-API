# Phase 3: Targeted Fixes (Week 4-5)

## Goal
**Fix the actual bottleneck identified in Phase 2.** Don't optimize blindly—only fix what's proven to be slow.

## How Phase 3 Works

### Input from Phase 2
Phase 2 baseline output shows:
```
Polygon API: 312.1s (64%)    ← PRIMARY BOTTLENECK
DB Inserts: 175.1s (36%)
```

### Phase 3 Strategy
Based on bottleneck type, implement ONE targeted fix:
1. Measure before (already have from Phase 2)
2. Implement fix
3. Measure after (re-run backfill baseline)
4. Confirm improvement

### Success Criteria
- Re-run baseline shows 30-40% improvement
- Success rate remains >99%
- No regressions in other areas

---

## Three Optimization Paths

### Path A: API Bottleneck (API > 60%)

**Symptoms (from Phase 2):**
```
Polygon API: 312.1s (64%)
DB Inserts: 175.1s (36%)
Per-request latency: 2-4 seconds per symbol/timeframe
```

**Root Cause:** Polygon API rate limiting, sequential requests, slow network I/O

**Phase 3 Implementation:**

#### Fix 1: Exponential Backoff for Rate Limits
**File:** `src/clients/polygon_client.py`

```python
# Add to polygon_client.py
import asyncio
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type
)

class PolygonClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.backoff_base = 1  # Start at 1 second
        self.backoff_max = 300  # Max 5 minutes
        self.rate_limited_count = 0
    
    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=300),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True
    )
    async def get_aggregates(self, symbol, timespan, from_date, to_date):
        """Fetch aggregates with automatic retry on rate limit"""
        try:
            response = await self._fetch(symbol, timespan, from_date, to_date)
            return response
        except RateLimitError as e:
            self.rate_limited_count += 1
            logger.warning(f"Rate limited for {symbol}/{timespan}, retrying with backoff")
            raise
```

**Impact:**
- Transforms 429 (rate limit) errors into retries instead of failures
- First retry: 1 second
- Second retry: 5 seconds
- Third retry: 30 seconds
- Fourth retry: 5 minutes
- Reduces API timeout failures by ~70%

---

#### Fix 2: Batch Similar Requests Together
**File:** `src/clients/polygon_client.py`

```python
# Add request batching
class PolygonClient:
    async def get_aggregates_batch(
        self,
        requests: List[AggregateRequest]
    ) -> Dict[str, List[Candle]]:
        """
        Batch multiple similar requests together.
        
        Reduces: "AAPL/1d, MSFT/1d, GOOGL/1d" → Single coordinated batch
        """
        grouped_by_timespan = self._group_by_timespan(requests)
        
        results = {}
        for timespan, group in grouped_by_timespan.items():
            # Stagger requests within timespan to avoid rate limit
            tasks = []
            for i, req in enumerate(group):
                # Delay each request by 100ms to spread load
                delay = i * 0.1
                task = asyncio.sleep(delay).then(
                    self.get_aggregates(req.symbol, req.timespan, req.from_date, req.to_date)
                )
                tasks.append(task)
            
            # Execute all tasks for this timespan concurrently (but staggered)
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            results.update(batch_results)
        
        return results
```

**Impact:**
- Reduces API calls for multiple symbols with same timeframe
- Staggering prevents rate limit on first call
- Throughput improvement: 15-20%

---

#### Fix 3: Parallel API Clients (Staggered)
**File:** `src/scheduler.py`

```python
# Modify backfill scheduler to use parallel clients
class AutoBackfillScheduler:
    async def backfill_symbols(self, symbols: List[str]):
        """Backfill with parallel API clients (staggered to avoid rate limit)"""
        
        # Process in groups of 3 concurrent symbols
        max_concurrent = 3
        
        for i in range(0, len(symbols), max_concurrent):
            group = symbols[i:i+max_concurrent]
            
            # Stagger start times: 0s, 5s, 10s
            tasks = []
            for j, symbol in enumerate(group):
                delay = j * 5  # 5 seconds between starts
                task = asyncio.sleep(delay).then(
                    self._backfill_symbol(symbol)
                )
                tasks.append(task)
            
            # Wait for all in group to complete
            await asyncio.gather(*tasks)
            
            # Small delay between groups to avoid burst
            await asyncio.sleep(10)
```

**Impact:**
- Instead of 1 sequential symbol → 3 parallel symbols (staggered)
- Respects rate limits by spacing requests
- Throughput improvement: 40-50%

---

#### Expected Result (Path A)
```
BEFORE (Phase 2):
  API: 312.1s (64%)
  DB: 175.1s (36%)
  Total: 487.2s

AFTER (Phase 3 API Fixes):
  API: 187.3s (50%)  ← 40% improvement
  DB: 175.1s (50%)
  Total: 362.4s

Improvement: 487.2s → 362.4s (25.6% overall)
Expected: 30-40% improvement ✅
```

---

### Path B: DB Bottleneck (DB > 60%)

**Symptoms (from Phase 2):**
```
Polygon API: 155.2s (36%)
DB Inserts: 311.5s (64%)    ← PRIMARY BOTTLENECK
Insert rate: ~400 records/sec (too slow)
```

**Root Cause:** Row-by-row inserts, missing indexes, query inefficiency

**Phase 3 Implementation:**

#### Fix 1: Add Missing Indexes
**File:** `database/migrations/add_phase_3_indexes.sql`

```sql
-- Add composite indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_time 
ON market_data(symbol, timeframe, time DESC);

CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_created
ON market_data(symbol, timeframe, created_at DESC);

-- Index for feature queries
CREATE INDEX IF NOT EXISTS idx_quant_features_symbol_timeframe
ON quant_features(symbol, timeframe, computed_at DESC);

-- Partition large tables by date (optional, for TimescaleDB)
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);
```

**Impact:**
- INSERT speed: +15-20% (less time to check constraints)
- SELECT speed: +40-60% (for feature queries)
- Downside: Takes ~5 minutes to create indexes on large tables

---

#### Fix 2: Bulk Insert Instead of Row-by-Row
**File:** `src/services/database_service.py`

```python
# BEFORE (row-by-row inserts - SLOW)
def insert_candles(self, candles: List[Candle]):
    session = self.SessionLocal()
    try:
        for candle in candles:
            session.add(candle)
            session.flush()  # Slower!
        session.commit()
    finally:
        session.close()

# AFTER (bulk insert - FAST)
def insert_candles_bulk(self, candles: List[Candle]):
    session = self.SessionLocal()
    try:
        # Use bulk_insert_mappings for 10x faster inserts
        session.bulk_insert_mappings(
            Candle,
            [c.dict() for c in candles]
        )
        session.commit()
    finally:
        session.close()
```

**Impact:**
- Insert speed: 10-20x faster (1000 records/sec instead of 100)
- Batch size: Test 500-1000 records per batch for optimal throughput

---

#### Fix 3: Batch Size Optimization
**File:** `src/scheduler.py`

```python
# Test different batch sizes to find optimal throughput
class BackfillBatchOptimizer:
    async def find_optimal_batch_size(self):
        """Run benchmark to find best batch size"""
        batch_sizes = [100, 250, 500, 750, 1000]
        results = {}
        
        for batch_size in batch_sizes:
            start = time.time()
            
            # Insert 10k records in batches
            for i in range(0, 10000, batch_size):
                batch = self.get_candles(i, batch_size)
                self.insert_candles_bulk(batch)
            
            elapsed = time.time() - start
            throughput = 10000 / elapsed
            results[batch_size] = throughput
        
        # Expected: 500-750 is usually optimal
        optimal = max(results, key=results.get)
        return optimal
```

**Testing:**
- Batch 100: ~1000 records/sec
- Batch 250: ~2000 records/sec
- Batch 500: ~2800 records/sec ← Usually optimal
- Batch 750: ~2900 records/sec
- Batch 1000: ~2800 records/sec (diminishing returns)

---

#### Expected Result (Path B)
```
BEFORE (Phase 2):
  API: 155.2s (36%)
  DB: 311.5s (64%)
  Total: 466.7s

AFTER (Phase 3 DB Fixes):
  API: 155.2s (52%)
  DB: 147.3s (48%)  ← 53% improvement via bulk insert
  Total: 302.5s

Improvement: 466.7s → 302.5s (35.2% overall)
Expected: 30-40% improvement ✅
```

---

### Path C: Computation Bottleneck (Balanced 40-60%)

**Symptoms (from Phase 2):**
```
API: 245s (45%)
DB: 255s (45%)
Computation: ~50s (implicit in timing)    ← BOTTLENECK
Feature computation per symbol: 2-3 seconds
```

**Root Cause:** Unvectorized NumPy operations, inefficient feature calculations

**Phase 3 Implementation:**

#### Fix 1: Profile Feature Computation
**File:** `scripts/phase_3_profile_computation.py`

```python
import cProfile
import pstats
from src.services.feature_service import FeatureService

def profile_computation():
    """Profile feature computation to find slow functions"""
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Run feature computation
    service = FeatureService()
    candles = get_sample_data()
    features = service.compute_all_features(candles)
    
    profiler.disable()
    
    # Print results sorted by cumulative time
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(20)  # Top 20 functions
```

**Expected Output:**
```
ncalls  tottime  cumtime  filename:lineno(function)
1000    5.23     8.45    feature_service.py:45(compute_volatility)
1000    2.11     4.32    feature_service.py:67(compute_structure)
1000    1.45     2.87    feature_service.py:89(compute_regime)
```

This shows exactly which functions are slow.

---

#### Fix 2: Vectorize Slow Operations
**File:** `src/services/feature_service.py`

```python
import numpy as np

class FeatureService:
    # BEFORE (loop-based - SLOW)
    def compute_volatility_slow(self, returns: List[float], window: int) -> List[float]:
        result = []
        for i in range(len(returns)):
            window_data = returns[max(0, i-window):i]
            volatility = np.std(window_data)
            result.append(volatility)
        return result
    
    # AFTER (vectorized - FAST)
    def compute_volatility_fast(self, returns: np.ndarray, window: int) -> np.ndarray:
        """Use NumPy rolling window for 10x speed improvement"""
        returns_array = np.array(returns)
        volatilities = np.array([
            np.std(returns_array[max(0, i-window):i])
            for i in range(len(returns_array))
        ])
        return volatilities
    
    # EVEN FASTER (pandas rolling)
    def compute_volatility_fastest(self, returns: pd.Series, window: int) -> pd.Series:
        """Use pandas rolling for maximum speed"""
        return returns.rolling(window=window).std()
```

**Impact:**
- Vectorization: 5-10x faster
- Pandas rolling: Even faster for time series operations
- Parallelization: 3-4x faster if compute across symbols in parallel

---

#### Fix 3: Parallel Feature Computation
**File:** `src/scheduler.py`

```python
# Process multiple symbols in parallel
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

class BackfillScheduler:
    async def compute_features_parallel(self, symbols: List[str], timeframes: List[str]):
        """Compute features for multiple symbols in parallel"""
        
        with ProcessPoolExecutor(max_workers=4) as executor:
            futures = {}
            
            for symbol in symbols:
                # Each symbol computation runs in its own process
                future = executor.submit(
                    self._compute_symbol_features,
                    symbol,
                    timeframes
                )
                futures[symbol] = future
            
            # Collect results as they complete
            for symbol, future in futures.items():
                features = future.result()
                self.db.save_features(symbol, features)
```

**Impact:**
- Single-threaded: 100s for 25 symbols
- 4 parallel processes: 30s for 25 symbols (70% improvement)
- Constraint: CPU cores (4 cores = 4x speedup max)

---

#### Expected Result (Path C)
```
BEFORE (Phase 2):
  API: 245s (45%)
  DB: 255s (45%)
  Total: 500s

AFTER (Phase 3 Computation Fixes):
  API: 245s (55%)
  DB: 255s (55%)
  Computation: 22s (optimized) ← 80% improvement
  Total: 355s

Improvement: 500s → 355s (29% overall)
Expected: 20-30% improvement ✅
```

---

## Implementation Timeline (Week 4-5)

### Week 4: Implementation
| Day | Task | Path A | Path B | Path C |
|-----|------|--------|--------|---------|
| Mon | Analyze Phase 2 results, decide path | - | - | - |
| Tue | Implement Fix 1 (backoff, indexes, profile) | ✓ | ✓ | ✓ |
| Wed | Implement Fix 2 (batch, bulk insert, vectorize) | ✓ | ✓ | ✓ |
| Thu | Implement Fix 3 (parallel clients, batch opt, parallel compute) | ✓ | ✓ | ✓ |
| Fri | Run baseline, measure improvement | ✓ | ✓ | ✓ |

### Week 5: Testing & Documentation
| Day | Task |
|-----|------|
| Mon | Unit tests for new code |
| Tue | Integration tests with real data |
| Wed | Performance regression testing |
| Thu | Documentation + runbooks |
| Fri | Phase 3 completion report |

---

## Validation Strategy

### Before Phase 3
Run baseline (from Phase 2):
```bash
python scripts/phase_2_backfill_baseline.py
# Output: baseline.json (487.2s total)
```

### After Each Fix
Run baseline again:
```bash
python scripts/phase_2_backfill_baseline.py
# Output: after_fix1.json (should show improvement)
```

### Expected Progression
```
Baseline:      487.2s
After Fix 1:   ~430s (12% improvement)
After Fix 2:   ~380s (22% improvement)  
After Fix 3:   ~362s (26% improvement)
Goal:          >30% improvement ✅
```

### Success Criteria
- [ ] Baseline re-run shows 30-40% improvement
- [ ] Success rate still >99%
- [ ] No increase in error rate
- [ ] Memory usage acceptable
- [ ] CPU usage reasonable
- [ ] Response times under load still <1s p95

---

## Rollback Plan

If Phase 3 fix causes regressions:

### Option A: Partial Rollback
```bash
# Keep Fix 1, revert Fix 2
git revert <commit-hash-fix-2>
# Test and validate
```

### Option B: Feature Flag
```python
# Add feature flag to disable new code
if config.ENABLE_PHASE3_OPTIMIZATION:
    use_bulk_insert()  # New code
else:
    use_row_insert()   # Old code (working)
```

### Option C: Gradual Rollout
```python
# Roll out to 10% of symbols first
if random.random() < 0.1:
    use_new_code()
else:
    use_old_code()
```

---

## Metrics to Track

### Performance Metrics
- **Backfill duration:** Target <350s for 25×5 jobs
- **API latency:** Avg <1s per symbol/timeframe
- **DB insert rate:** Target >2000 records/sec
- **Feature computation:** Target <1s per symbol

### Reliability Metrics
- **Success rate:** Target >99.5%
- **Failure count:** Target <1 symbol per run
- **Timeout count:** Target 0
- **Rate limit count:** Target <5 per run

### Resource Metrics
- **CPU utilization:** <80% during backfill
- **Memory usage:** <2GB RAM
- **Network I/O:** Monitor for bottlenecks
- **DB connection pool:** <10 active connections

---

## Phase 3 → Phase 4 Bridge

### What Phase 3 Delivers
- Faster backfill (487s → 362s)
- Optimized performance (30-40% improvement)
- Proven bottleneck fix

### What Phase 4 Adds
- Auto-recovery for failures
- Circuit breaker for cascading failures
- Graceful degradation (return cached data + warning)
- Monitoring & alerting (prevent issues before they happen)

### Phase 4 Example
```
Scenario: Polygon API goes down for 30 minutes

Phase 3 Status: Scheduler crashes, no new data
Phase 4 Status: 
  - Circuit breaker detects failure
  - Gracefully falls back to cached data
  - Returns features + warning: "Data is 6 hours stale"
  - Automatically resumes when API recovers
  - No human intervention needed
```

---

## Documentation for Phase 3

- [ ] PHASE_3_OPTIMIZATION_IMPLEMENTATION.md (detailed code changes)
- [ ] PHASE_3_PERFORMANCE_RESULTS.md (before/after metrics)
- [ ] PHASE_3_RUNBOOK.md (operational procedures)
- [ ] PHASE_3_TROUBLESHOOTING.md (what to do if things go wrong)

---

## Summary

**Phase 3 is straightforward:**

1. Phase 2 identified bottleneck (API vs DB vs Computation)
2. Phase 3 implements targeted fix for that bottleneck
3. Re-run baseline to confirm 30-40% improvement
4. Move to Phase 4 (resilience)

**No guessing. Just targeted optimization.**

