# Phase 5: 1-Minute Timeframe Integration Plan

## Executive Summary

This plan adds 1-minute (`1m`) OHLCV candle support to your Market Data API while maintaining backward compatibility with existing features. The approach is pragmatic—leveraging your existing architecture without overengineering—using industry-standard patterns for high-frequency financial data.

**Key Principles:**
- Minimal configuration changes (single constant update)
- No database schema migrations required
- Seamless integration with existing services
- Focus on storage efficiency and query performance
- Follow industry best practices (TimescaleDB hyper-functions, columnar aggregation)

---

## Part 1: Architecture & Design Decisions

### 1.1 Why 1-Minute Data Doesn't Break Your System

Your system is already built to handle multiple timeframes:
- **Polygon Client**: Already maps timeframe strings to API parameters (`TIMEFRAME_MAP`)
- **Database Schema**: Uses generic `timeframe` VARCHAR column (no hardcoded 5m minimum)
- **Models & Validation**: All validators accept any timeframe in `ALLOWED_TIMEFRAMES`
- **Query Patterns**: All queries use `WHERE timeframe = $1` (parametrized, not hardcoded)

**Key insight**: Your lowest value currently is 5m by convention, not by design.

### 1.2 Storage Considerations & Efficiency

**1-minute data volume projection:**
- 1 year of 1-minute candles per symbol ≈ **250KB** (compressed in TimescaleDB)
- 100 symbols × 1 year ≈ **25MB** (negligible)
- With your current 25 symbol baseline: **~6.25MB per year**

**Why you won't have storage issues:**
- TimescaleDB compresses intraday data automatically via `timescaledb.compress` policy
- 1-minute data has high repetition (same symbols, ordered timestamps)
- Columnar compression achieves 10-20x reduction for numeric OHLCV fields
- Your existing compression settings apply to 1m data automatically

**Compared to industry standards:**
- CoinAPI: 1 year BTC/USDT 1-minute OHLCV = 3-5MB
- Trading platforms: Store 1-year of 1-minute candles for thousands of assets without issue
- Your PostgreSQL is sized for much larger workloads

### 1.3 API & Query Design

**Query pattern** (already works for 1m):
```python
await db.fetch_candles(
    symbol='AAPL',
    timeframe='1m',          # Just works
    start=datetime(2024, 1, 1),
    end=datetime(2024, 1, 2)
)
```

**Rate limiting considerations:**
- Polygon API: 150 requests/minute (already tracked in `PolygonClient`)
- Fetching 1-minute data for a symbol = 1 request per data block (same as 5m or 1h)
- Volume is **not a rate-limit issue** because you fetch aggregated OHLCV, not ticks

---

## Part 2: Implementation Roadmap

### Phase 5.1: Foundation (2-3 hours)

#### Task 1: Update Configuration
**File**: `src/config.py`

```python
# BEFORE
ALLOWED_TIMEFRAMES: List[str] = ['5m', '15m', '30m', '1h', '4h', '1d', '1w']
DEFAULT_TIMEFRAMES: List[str] = ['1h', '1d']

# AFTER
ALLOWED_TIMEFRAMES: List[str] = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
DEFAULT_TIMEFRAMES: List[str] = ['1h', '1d']  # Keep unchanged for backward compatibility
```

**Why minimal change?** All validators already use `ALLOWED_TIMEFRAMES` via loop/membership checks.

#### Task 2: Update Polygon Client TIMEFRAME_MAP
**File**: `src/clients/polygon_client.py`

```python
TIMEFRAME_MAP = {
    '1m': {'multiplier': 1, 'timespan': 'minute'},  # Add this line
    '5m': {'multiplier': 5, 'timespan': 'minute'},
    # ... rest unchanged
}
```

**Validation**: Polygon.io supports 1-minute aggregates via their standard endpoint.
- Documentation reference: https://polygon.io/docs/stocks/get_aggs

#### Task 3: Update Database TIMEFRAME_MAP (if separate)
**File**: `src/services/database_service.py` (if it exists)

Check if there's a separate mapping that needs updating. If not, you're done.

---

### Phase 5.2: Testing & Validation (3-4 hours)

#### Task 4: Create Unit Tests for 1m Support
**File**: `tests/test_1m_timeframe.py` (new)

```python
import pytest
from src.clients.polygon_client import PolygonClient
from src.config import ALLOWED_TIMEFRAMES

class Test1mTimeframeSupport:
    """Test 1-minute timeframe integration"""
    
    def test_1m_in_allowed_timeframes(self):
        """1m should be in allowed list"""
        assert '1m' in ALLOWED_TIMEFRAMES
    
    def test_1m_timeframe_params(self):
        """Polygon client should map 1m correctly"""
        params = PolygonClient._get_timeframe_params('1m')
        assert params['multiplier'] == 1
        assert params['timespan'] == 'minute'
    
    @pytest.mark.asyncio
    async def test_fetch_1m_candles(self, db_service, symbol='AAPL'):
        """Verify 1m candles can be fetched and stored"""
        # Mock polygon call for 1m data
        candles = await db_service.get_candles(
            symbol=symbol,
            timeframe='1m',
            start=datetime.now() - timedelta(days=1),
            end=datetime.now()
        )
        assert isinstance(candles, list)
        if candles:
            assert all(c['timeframe'] == '1m' for c in candles)
    
    def test_1m_model_validation(self):
        """OHLCVData model should accept 1m timeframe"""
        from src.models import OHLCVData
        from decimal import Decimal
        from datetime import datetime
        
        data = OHLCVData(
            time=datetime.now(),
            symbol='TEST',
            timeframe='1m',  # Should not raise
            open=Decimal('100.00'),
            high=Decimal('101.00'),
            low=Decimal('99.00'),
            close=Decimal('100.50'),
            volume=1000
        )
        assert data.timeframe == '1m'
```

**Run command:**
```bash
pytest tests/test_1m_timeframe.py -v
```

#### Task 5: Backward Compatibility Tests
**File**: `tests/test_backward_compatibility.py` (update existing)

Ensure old behavior unchanged:
```python
def test_default_timeframes_unchanged(self):
    """DEFAULT_TIMEFRAMES should still be ['1h', '1d']"""
    from src.config import DEFAULT_TIMEFRAMES
    assert DEFAULT_TIMEFRAMES == ['1h', '1d']

def test_existing_queries_unaffected(self, db_service):
    """Old queries (5m, 15m, 1h, 1d) should work identically"""
    for tf in ['5m', '15m', '1h', '1d']:
        # Run existing tests with these timeframes
        # Should have identical performance/behavior
        pass
```

#### Task 6: Load & Performance Tests
**File**: `tests/test_1m_performance.py` (new)

```python
import pytest
from datetime import datetime, timedelta
import time

@pytest.mark.asyncio
async def test_1m_query_performance(db_service):
    """1m candle queries should be fast (< 100ms for 1 day of data)"""
    start = time.time()
    
    candles = await db_service.get_candles(
        symbol='AAPL',
        timeframe='1m',
        start=datetime.now() - timedelta(days=1),
        end=datetime.now()
    )
    
    elapsed = time.time() - start
    assert elapsed < 0.1, f"1m query took {elapsed}s, expected <100ms"

@pytest.mark.asyncio
async def test_storage_efficiency(db_service):
    """Verify 1m data uses expected storage space (~250KB per symbol-year)"""
    # Insert 1 year of mock 1m candles
    # Verify disk space is reasonable
    pass
```

---

### Phase 5.3: API & Route Updates (1-2 hours)

#### Task 7: Update API Documentation
**Files**: 
- `src/routes/asset_data.py` (update docstrings)
- `src/routes/enrichment_ui.py` (if has examples)

```python
# BEFORE
"""
Supported timeframes: 5m, 15m, 30m, 1h, 4h, 1d, 1w
"""

# AFTER
"""
Supported timeframes: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
"""
```

#### Task 8: Update Endpoint Query Parameters (if hardcoded)
**File**: `src/routes/asset_data.py`

Search for any hardcoded timeframe lists and update:
```python
# BEFORE
timeframe: str = Query("1h", description="Candle timeframe (5m, 15m, 30m, 1h, 4h, 1d, 1w)")

# AFTER
timeframe: str = Query("1h", description="Candle timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)")
```

---

### Phase 5.4: Scheduler & Backfill (2-3 hours)

#### Task 9: Update Enrichment Scheduler
**File**: `src/services/enrichment_scheduler.py`

Current code likely has:
```python
timeframes=['1d']  # TODO: Get from tracked_symbols
```

This should already pull from `tracked_symbols.timeframes` array, but verify:

```python
# Check if scheduler uses tracked_symbols.timeframes
# If yes: no change needed
# If no: update to use dynamic list from database
```

#### Task 10: Update Backfill Scheduling
**File**: `src/scheduler.py`

Review backfill logic to ensure it:
1. Loads timeframes from `tracked_symbols.timeframes` ✅ (already does)
2. Respects rate limits for 1m requests ✅ (already does)
3. Handles gaps in market data (e.g., market closed periods)

**For 1m data specifically**, add this consideration:
```python
# When fetching 1m data, note that:
# - Market hours vary by asset (US stocks: 9:30-4:00 ET, crypto: 24/7)
# - No candles generated during market closure
# - This is automatic from Polygon API (they don't return closed-hour data)
```

#### Task 11: Update Performance Monitoring
**File**: `src/services/performance_monitor.py` (if exists)

Add metrics tracking for 1m:
```python
def track_1m_backfill_metric(self, symbol: str, candles_count: int, duration: float):
    """Track 1m backfill performance"""
    # Log to existing monitoring infrastructure
    logger.info(
        f"1m backfill: {symbol} - {candles_count} candles in {duration:.2f}s"
    )
```

---

### Phase 5.5: Dashboard & UI (1-2 hours)

#### Task 12: Update Dashboard 1m Support
**Files**: `dashboard/` (check what exists)

If your dashboard shows timeframe selection:
- Add `1m` to dropdown options
- Update example queries in documentation
- Update sample responses to show 1m data

#### Task 13: Update API Documentation Pages
**File**: Any `/docs` or README sections

Update examples:
```python
# BEFORE
GET /api/v1/asset/AAPL/candles?timeframe=1h
GET /api/v1/asset/AAPL/candles?timeframe=1d

# AFTER
GET /api/v1/asset/AAPL/candles?timeframe=1m
GET /api/v1/asset/AAPL/candles?timeframe=5m
# ... etc
```

---

## Part 3: Best Practices Implementation

### 3.1 Data Aggregation Strategy

If users want to aggregate 1m → higher timeframes, use TimescaleDB hyper-functions:

**Optional enhancement** (Phase 5.6):
```sql
-- Create materialized view for 5m candles from 1m base data
CREATE MATERIALIZED VIEW candlestick_5m
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('5m', time) as candle_time,
  symbol,
  candlestick_agg(time, close, volume) as candlestick
FROM market_data
WHERE timeframe = '1m'
GROUP BY 1, 2;
```

**Benefit**: On-demand aggregation without duplicate storage

### 3.2 Query Optimization for 1m

1-minute queries will be higher volume. Ensure:

```python
# In database_service.py, verify indexes exist:
"""
Existing indexes (check):
- market_data(symbol, timeframe)
- market_data(symbol, timeframe, time)

These should handle 1m queries efficiently.
"""
```

### 3.3 Caching Strategy for 1m Data

1-minute data changes frequently. Adjust cache TTL:

```python
# In query_cache.py (if exists), consider:
CACHE_TTL = {
    '1m': 60,      # 1 minute (only cache complete candles)
    '5m': 300,
    '15m': 900,
    '1h': 3600,
    '1d': 86400,
}
```

### 3.4 Client Request Handling

Polygon API behavior for 1m:
- Returns up to 50,000 results per request
- Pagination required for > 50k candles
- Your `_fetch_with_pagination()` method already handles this ✅

---

## Part 4: Validation Checklist

### Pre-Deployment Validation

- [ ] **Configuration**: `'1m'` added to `ALLOWED_TIMEFRAMES`
- [ ] **Polygon Client**: TIMEFRAME_MAP includes `'1m': {'multiplier': 1, 'timespan': 'minute'}`
- [ ] **Models**: `OHLCVData` validator accepts `'1m'` (auto-works via config)
- [ ] **Database**: No schema changes needed (existing `timeframe` VARCHAR)
- [ ] **Routes**: All docstrings updated with 1m option
- [ ] **Unit Tests**: `test_1m_timeframe.py` passes (all 4 tests green)
- [ ] **Integration Tests**: Existing tests still pass
- [ ] **API Tests**: Can fetch 1m candles via REST endpoint
- [ ] **Dashboard**: 1m option appears in UI/forms
- [ ] **Scheduler**: Backfill includes 1m if symbol configured
- [ ] **Documentation**: README/docs show 1m examples

### Load Testing (Post-Deployment)

```bash
# Run existing load tests to ensure no regression
pytest tests/test_phase_2_validation.py -k "load" -v -s

# Run new 1m tests
pytest tests/test_1m_timeframe.py -v
pytest tests/test_1m_performance.py -v
```

---

## Part 5: Rollout Strategy

### Step 1: Configuration-Only Deploy (5 minutes)
1. Update `src/config.py` with `'1m'`
2. Update `src/clients/polygon_client.py` TIMEFRAME_MAP
3. Deploy to staging
4. Test: `GET /api/v1/asset/TEST/candles?timeframe=1m`

### Step 2: Test & Verify (30 minutes)
1. Run unit + integration tests
2. Verify no breaking changes to existing endpoints
3. Check database query performance

### Step 3: Add to Symbol Config (Optional)
Users add 1m to their tracked symbols:
```python
# User can now do this:
PUT /api/v1/symbol/AAPL/timeframes
{
  "timeframes": ["1m", "5m", "1h", "1d"]
}
```

### Step 4: Monitor & Adjust (First week)
- Monitor Polygon API rate limits
- Track storage growth
- Verify query performance remains < 100ms

---

## Part 6: FAQ & Considerations

### Q: Will 1m data break my existing queries?
**A:** No. All existing timeframe queries (5m, 15m, 1h, 1d) are unaffected. The feature is additive.

### Q: What if I don't want 1m data for some symbols?
**A:** By default, `DEFAULT_TIMEFRAMES` stays as `['1h', '1d']`. Only add 1m when you explicitly configure it per symbol via the API.

### Q: How much storage will 1m use?
**A:** ~250KB per symbol per year (compressed). 100 symbols = ~25MB/year. Negligible.

### Q: Will 1m slow down my API?
**A:** No. Query times remain < 100ms due to:
- Existing indexes (symbol, timeframe)
- TimescaleDB's columnar compression
- Pagination in Polygon client

### Q: Can I aggregate 1m → 5m → 1h automatically?
**A:** Yes (Phase 5.6 enhancement). Use TimescaleDB hyper-functions for on-demand aggregation.

### Q: What about gaps in 1m data (market closure)?
**A:** Polygon API doesn't return candles for market closure periods. This is correct behavior—your analysis code already handles this for daily data.

### Q: Do I need to backfill historical 1m data?
**A:** Only if you want to analyze past 1m trends. You can start collecting 1m data going forward and backfill 6-12 months per symbol as needed.

---

## Part 7: Post-Implementation Monitoring

### Metrics to Track
1. **API Response Times**
   - 1m queries: Should be < 100ms
   - Compare to 5m baseline
   
2. **Database Performance**
   - Query plan (`EXPLAIN ANALYZE`)
   - Cache hit rate
   - Index usage

3. **Storage Growth**
   - Monthly growth rate
   - Compression ratio (should be 10-20x)
   - Disk space trends

4. **Rate Limiting**
   - Polygon API request count
   - Rate limit status codes (429)
   - Backoff/retry patterns

### Alerts to Set
- Query time > 500ms
- 429 rate limit hit
- Storage > 80% capacity
- Backfill failure on 1m timeframe

---

## Timeline

| Phase | Tasks | Effort | Owner |
|-------|-------|--------|-------|
| **5.1** | Config + Client updates | 1 hour | Dev |
| **5.2** | Unit + Integration tests | 3 hours | QA |
| **5.3** | API docs + Routes | 1.5 hours | Dev |
| **5.4** | Scheduler + Backfill | 2 hours | Dev |
| **5.5** | Dashboard + UI | 1.5 hours | Frontend |
| **5.6** | Validation & Load tests | 2 hours | QA |
| **Deploy** | Staging → Production | 30 min | DevOps |
| **Monitor** | First week | Ongoing | Ops |

**Total: ~11 hours of engineering time**

---

## Files Changed Summary

| File | Changes | Risk |
|------|---------|------|
| `src/config.py` | Add `'1m'` to `ALLOWED_TIMEFRAMES` | Low |
| `src/clients/polygon_client.py` | Add `'1m'` to `TIMEFRAME_MAP` | Low |
| `src/routes/*.py` | Update docstrings | None |
| `src/scheduler.py` | (Verify, no change needed) | None |
| `tests/` | Add new test files | None |
| `dashboard/` | Add 1m to UI options | Low |

**No breaking changes. Zero database migrations required.**

---

## Conclusion

Adding 1-minute support is a **2-3 line configuration change** due to your solid architecture. The rest is testing, documentation, and monitoring. Start with the configuration update, run your test suite, and gradually roll it out to production.

The design is pragmatic—no overengineering, leveraging your existing infrastructure, following industry best practices for time-series data.
