# Multi-Source Data Strategy: Design & Implementation Plan

## Executive Summary

You're asking about two complementary features:
1. **Free data source fallback** - Use free APIs when Polygon fails
2. **Validation-driven retry** - If data validates poorly, fetch from alternate source

This document analyzes the approach, costs, tradeoffs, and provides a professional implementation plan.

## Current State

**Primary Source:** Polygon.io
- ✅ Excellent data quality
- ✅ Covers stocks + crypto + options
- ❌ Paid (though you likely have API key)
- ✅ Rate limit: 150 req/min (sufficient)

**Data Flow:** `Polygon → Validation → Database`

**Problem:** When Polygon has gaps or poor data, no fallback mechanism exists.

## Viable Free Data Sources

### Option 1: **Alpha Vantage** (Recommended for stocks)
```
Coverage: US stocks only
Quality: Good (institutional data)
Cost: FREE (500 req/day) + PAID ($49/mo)
Rate Limit: 5 req/min (free tier)
Latency: ~2-3 seconds per request
Data Types: OHLCV, Intraday (1m-60m), Daily
```
**Pros:**
- Daily data generally matches Polygon
- Free tier sufficient for backfill
- Well-documented API
- No auth complexity

**Cons:**
- Slow rate limit (5 req/min)
- Intraday is limited
- CSV output format requires parsing
- Can't use for primary (too slow)

### Option 2: **Yahoo Finance** (Good for quick fixes)
```
Coverage: Stocks + Crypto + ETFs
Quality: Good (widely used)
Cost: FREE (unlimited)
Rate Limit: Reasonable (~100-200 req/min detected)
Latency: <1 second per request
Data Types: OHLCV, Daily + Intraday (1m data)
```
**Pros:**
- Free and unlimited
- Good data quality
- Fast enough for fallback
- Python client well-maintained (`yfinance`)
- Covers stocks, crypto, ETFs

**Cons:**
- Unofficial API (no SLA)
- Can get rate-limited if hammered
- Less reliable than paid APIs
- May occasionally return stale data

### Option 3: **IEX Cloud** (Enterprise-grade fallback)
```
Coverage: US stocks only
Quality: Excellent (financial pro data)
Cost: $25-100/mo
Rate Limit: Depends on plan
Latency: <500ms
Data Types: OHLCV, News, Fundamentals
```
**Pros:**
- Excellent stability
- Professional-grade API
- Good documentation

**Cons:**
- Requires payment (not truly free)
- Overkill if just fallback
- More complex auth

## Recommended Strategy

### **Hybrid Multi-Tier Approach**

```
┌─ Backfill/Live Data ─────────────┐
│                                  │
│  Try Polygon (Primary)           │
│  ├─ Success + Valid? → Use it   │
│  ├─ Rate Limited? → Wait/Retry  │
│  ├─ Timeout? → Try Yahoo        │
│  ├─ Poor Quality? → Try Yahoo   │
│  └─ Fail? → Try Alpha Vantage   │
│                                  │
└──────────────────────────────────┘
```

### **Tier System**

| Tier | Source | Use Case | Priority |
|------|--------|----------|----------|
| 1 | Polygon | Primary, real-time | Highest |
| 2 | Yahoo Finance | Fast fallback, daily | Medium |
| 3 | Alpha Vantage | Slow fallback, archives | Low |

### **When to Use Each**

```
Scenario 1: Live Data (Scheduler)
  → Try Polygon
  → If rate limited → Wait + Retry Polygon
  → If timeout → Try Yahoo
  → If fails → Mark as failed, alert

Scenario 2: Backfill (Initial)
  → Use Polygon (faster, don't need fallback)
  → If gap detected → Validate from Yahoo
  
Scenario 3: Validation Repair (Unvalidated records)
  → If quality < 0.85 → Fetch from Yahoo as confirmation
  → Compare both sources
  → Use better one, note source
```

## Implementation Approach

### Phase 1: Build Yahoo Finance Client

Create `src/clients/yahoo_client.py`:

```python
class YahooFinanceClient:
    """Fallback client for stocks, crypto, and ETFs"""
    
    async def fetch_range(
        self,
        symbol: str,
        start: str,
        end: str,
        timeframe: str = '1d'
    ) -> List[Dict]:
        """Fetch OHLCV from Yahoo Finance"""
        # Returns same format as Polygon for compatibility
        # {t, o, h, l, c, v}
```

**Why:**
- Minimal async library needed (`yfinance` + `aiohttp`)
- Returns same data format
- Can drop in as fallback
- No API key needed

### Phase 2: Validation-Aware Retry Logic

Update backfill flow:

```python
async def fetch_with_fallback(
    symbol: str,
    timeframe: str,
    start: str,
    end: str,
    validate: bool = True
) -> Tuple[List[Dict], str]:  # Returns (candles, source)
    """
    Fetch data from primary, fallback to secondary if needed.
    
    Returns: (candles, source) where source is 'polygon', 'yahoo', or 'alpha'
    """
    
    # Try primary
    try:
        candles = await polygon.fetch_range(symbol, timeframe, start, end)
        if validate:
            quality = validate_candles(candles)
            if quality >= 0.85:
                return candles, 'polygon'
        else:
            return candles, 'polygon'
    except TimeoutError:
        logger.info(f"Polygon timeout for {symbol}, trying Yahoo")
    except RateLimitError as e:
        logger.info(f"Polygon rate limited, waiting then retrying")
        await asyncio.sleep(e.retry_after)
        # Retry polygon before fallback
    
    # Try secondary (Yahoo)
    try:
        logger.info(f"Fetching {symbol} from Yahoo Finance")
        candles = await yahoo.fetch_range(symbol, timeframe, start, end)
        return candles, 'yahoo'
    except Exception as e:
        logger.warning(f"Yahoo failed for {symbol}: {e}")
    
    # Try tertiary (Alpha Vantage) for stocks only
    if not is_crypto(symbol):
        try:
            logger.info(f"Fetching {symbol} from Alpha Vantage")
            candles = await alpha.fetch_range(symbol, start, end)
            return candles, 'alpha'
        except Exception as e:
            logger.error(f"Alpha Vantage failed for {symbol}: {e}")
    
    # All sources failed
    logger.error(f"All sources failed for {symbol}")
    return [], None
```

### Phase 3: Database Source Tracking

Update `market_data` table:

```sql
ALTER TABLE market_data 
ADD COLUMN source VARCHAR(20) DEFAULT 'polygon'  -- Already exists
ADD COLUMN source_quality NUMERIC(3,2) DEFAULT 0.0  -- NEW
ADD COLUMN fallback_source VARCHAR(20) DEFAULT NULL  -- NEW
ADD COLUMN fallback_quality NUMERIC(3,2) DEFAULT NULL  -- NEW
```

This lets you:
- Track which source provided data
- Compare quality across sources
- Detect patterns (e.g., "Yahoo always 5% higher on volume")

### Phase 4: Repair Script Enhancement

Update `repair_unvalidated_data.py`:

```python
async def repair_with_fallback(
    records: List[Dict],
    enable_fallback: bool = False
) -> Dict:
    """
    Re-validate records, falling back to alternate sources if needed.
    """
    
    for record in records:
        # First, validate existing data
        quality_primary = validate(record)
        
        if quality_primary < 0.85 and enable_fallback:
            # Fetch from alternate source
            symbol, timeframe = record['symbol'], record['timeframe']
            
            fallback_candles, source = await fetch_with_fallback(
                symbol, timeframe, record['time'], record['time'],
                validate=False
            )
            
            if fallback_candles:
                quality_fallback = validate(fallback_candles[0])
                
                # Use whichever is better
                if quality_fallback > quality_primary:
                    # Update record with fallback data
                    update_record(record, fallback_candles[0], source)
                    logger.info(f"Used fallback source for {symbol} (quality: {quality_fallback})")
        
        # Update database
        await update_db(record)
```

## Cost-Benefit Analysis

### Option A: **Polygon Only** (Current)
```
Costs:
  - Polygon API: $25-500/mo (depends on your plan)
  - None (have API key)

Reliability:
  - 99.9% uptime (AWS)
  - Excellent data quality
  - Good coverage (stocks + crypto)

Gaps:
  - If Polygon down → No data
  - If data bad → No recovery
```

### Option B: **Polygon + Yahoo Fallback** (Recommended)
```
Costs:
  - Polygon: $25-500/mo (existing)
  - Yahoo: $0 (free, no auth)
  - Implementation: ~4-6 hours

Reliability:
  - 99.95% (Polygon + Yahoo backup)
  - Falls back to free source if needed
  - Good for daily/intraday validation

Gaps:
  - Crypto less reliable on Yahoo
  - Intraday gaps possible
```

### Option C: **Polygon + Yahoo + Alpha Vantage** (Complete)
```
Costs:
  - Polygon: $25-500/mo (existing)
  - Yahoo: $0 (free)
  - Alpha Vantage: $0-49/mo
  - Implementation: ~8-12 hours

Reliability:
  - 99.99% (3 sources)
  - Good for archives/backfill
  - Handles all assets

Gaps:
  - Complex error handling
  - May have conflicting data
  - Overkill for most use cases
```

## Risk Assessment

### Data Quality Risk: **MEDIUM**
- Different sources = different methodologies
- Yahoo sometimes lags Polygon by 15+ minutes
- Alpha Vantage may have stale daily data

**Mitigation:**
- Always prefer Polygon (marked as primary)
- Only use fallback for validation purposes
- Log source in database for audit
- Compare sources when both available

### Complexity Risk: **MEDIUM**
- More code paths to test
- Need error handling for 3 sources
- Async concurrency gets tricky

**Mitigation:**
- Start with Yahoo only (simplest)
- Add Alpha Vantage later if needed
- Write comprehensive tests for fallback logic
- Use circuit breakers to avoid cascading failures

### API Rate Limit Risk: **LOW**
- Each source independent rate limit
- Polygon primary (you control)
- Yahoo free (reasonable limits)
- Alpha Vantage (throttled but ok)

**Mitigation:**
- Respect each API's rate limits
- Use exponential backoff
- Monitor rate limit headers
- Implement per-source rate limiters

## Honest Professional Assessment

### When This Makes Sense
✅ **Do this if:**
- You've experienced Polygon outages
- You have large unvalidated dataset needing repair
- You want confidence in data quality (cross-source validation)
- You're okay with moderate complexity increase
- You want redundancy for production stability

### When This is Overkill
❌ **Don't do this if:**
- Polygon is reliable enough for your use case
- You're just doing daily stock data (Polygon alone is fine)
- You have limited engineering resources
- Time-to-market is critical
- You need 100% data parity (different sources = different data)

### Recommendation
**Start with Yahoo fallback only** (Polygon + Yahoo):
- ~5 hours implementation
- Handles 90% of failure scenarios
- Minimal complexity increase
- Free (no additional costs)
- Easy to test and debug
- Can add Alpha Vantage later if needed

## Implementation Roadmap

### Week 1: Yahoo Client + Basic Fallback
```
Day 1-2: Build YahooFinanceClient
- async fetch_range() method
- Error handling
- Data format normalization

Day 3: Integrate into backfill flow
- Update master_backfill.py
- Add fallback parameter
- Test with dry-run

Day 4: Update repair script
- Add --enable-fallback flag
- Log source in results
- Test on subset
```

### Week 2: Testing + Monitoring
```
Day 5: Comprehensive tests
- Test fallback logic
- Test data comparison
- Test error scenarios

Day 6: Monitoring + Alerts
- Track source usage
- Monitor quality differences
- Alert on sustained failures

Day 7: Documentation + Deployment
- Document fallback behavior
- Update AGENTS.md
- Deploy to production
```

## Next Steps

1. **Decision**: Approve Polygon + Yahoo fallback approach?
2. **Build**: Create YahooFinanceClient
3. **Integrate**: Add to backfill and repair flows
4. **Test**: Comprehensive testing
5. **Deploy**: Monitor usage and quality

Would you like me to:
- ✅ Build the Yahoo Finance client
- ✅ Integrate into existing backfill flow
- ✅ Add fallback logic to repair script
- ✅ Create comprehensive tests
- Or adjust the strategy first?
