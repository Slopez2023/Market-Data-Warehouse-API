# Multi-Source Integration Guide

## Files Created

```
src/clients/
├── yahoo_client.py           # Yahoo Finance fallback client
└── multi_source_client.py    # Orchestrator with fallback logic

MULTI_SOURCE_STRATEGY.md       # Strategy & design decisions
MULTI_SOURCE_INTEGRATION.md    # This file - implementation guide
```

## Quick Start: Use Multi-Source in Your Code

### Option 1: Direct Replacement (Simple)

Replace Polygon in your scheduler:

```python
# OLD CODE (scheduler.py)
from src.clients.polygon_client import PolygonClient
polygon = PolygonClient(api_key)
candles = await polygon.fetch_range(symbol, timeframe, start, end)

# NEW CODE (with fallback)
from src.clients.multi_source_client import MultiSourceClient
client = MultiSourceClient(polygon_api_key=api_key, enable_fallback=True)
candles, source = await client.fetch_range(symbol, timeframe, start, end)
logger.info(f"Got data from {source}")  # 'polygon' or 'yahoo'
```

### Option 2: With Validation-Driven Fallback (Recommended)

```python
from src.clients.multi_source_client import MultiSourceClient
from src.services.validation_service import ValidationService

validator = ValidationService()
client = MultiSourceClient(
    polygon_api_key=api_key,
    validation_service=validator,
    enable_fallback=True,
    fallback_threshold=0.85  # If quality < 0.85, try Yahoo
)

# Will automatically fallback if Polygon quality is poor
candles, source = await client.fetch_range(
    symbol='AAPL',
    timeframe='1d',
    start='2025-01-01',
    end='2025-01-31',
    validate=True  # Enable quality-based fallback
)

print(f"Fetched from {source}")  # Tells you which source was used
```

## Integration Points

### 1. Scheduler (src/scheduler.py)

**Current Code:**
```python
class EnrichmentScheduler:
    def __init__(self, polygon_api_key: str, ...):
        self.polygon_client = PolygonClient(polygon_api_key)
    
    async def fetch_latest_candles(self, symbol: str, timeframe: str):
        candles = await self.polygon_client.fetch_range(...)
```

**With Multi-Source:**
```python
from src.clients.multi_source_client import MultiSourceClient

class EnrichmentScheduler:
    def __init__(self, polygon_api_key: str, ...):
        self.data_client = MultiSourceClient(
            polygon_api_key=polygon_api_key,
            enable_fallback=True
        )
    
    async def fetch_latest_candles(self, symbol: str, timeframe: str):
        candles, source = await self.data_client.fetch_range(
            symbol=symbol,
            timeframe=timeframe,
            start=start_date,
            end=end_date,
            validate=False  # Live data, just get it fast
        )
        
        if not candles:
            logger.error(f"Failed to fetch {symbol} from all sources")
        else:
            logger.info(f"Fetched {symbol} from {source}")
            # Insert as normal
```

### 2. Master Backfill (master_backfill.py)

**With Quality-Based Fallback:**
```python
from src.clients.multi_source_client import MultiSourceClient
from src.services.validation_service import ValidationService

class MasterBackfiller:
    def __init__(self, database_url, polygon_api_key):
        validator = ValidationService()
        self.data_client = MultiSourceClient(
            polygon_api_key=polygon_api_key,
            validation_service=validator,
            enable_fallback=True,
            fallback_threshold=0.85
        )
    
    async def backfill_symbol_timeframe(self, symbol, timeframe, start, end):
        """Backfill with fallback if quality is poor"""
        candles, source = await self.data_client.fetch_range(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            is_crypto=self.is_crypto(symbol),
            validate=True  # Check quality, trigger fallback if needed
        )
        
        if candles:
            logger.info(f"Backfilled {symbol} from {source}")
            # Insert into database, tracking source
```

### 3. Validation Repair (repair_unvalidated_data.py)

**With Source Comparison:**
```python
from src.clients.multi_source_client import MultiSourceClient

class UnvalidatedDataRepairer:
    def __init__(self, database_url, polygon_api_key):
        self.data_client = MultiSourceClient(
            polygon_api_key=polygon_api_key,
            enable_fallback=True
        )
    
    async def repair_record(self, record):
        """Re-validate and optionally fetch from better source"""
        
        # First validate existing data
        quality_primary = validate(record)
        
        # If poor quality, try alternate source
        if quality_primary < 0.85:
            candles, source = await self.data_client.fetch_range(
                symbol=record['symbol'],
                timeframe=record['timeframe'],
                start=record['time'].date().isoformat(),
                end=record['time'].date().isoformat(),
                validate=True
            )
            
            if candles:
                quality_alt = validate(candles[0])
                
                if quality_alt > quality_primary:
                    logger.info(f"Using {source} data for {record['symbol']} (quality: {quality_alt})")
                    # Update record with alternate source data
                    update_record(record, candles[0], source)
        
        # Save to database
        await update_db(record)
```

## Configuration

### Enable/Disable Fallback

```python
# Option A: Always use fallback if primary fails
client = MultiSourceClient(polygon_api_key, enable_fallback=True)

# Option B: Primary only (current behavior)
client = MultiSourceClient(polygon_api_key, enable_fallback=False)

# Option C: Control per-request
candles, source = await client.fetch_range(
    symbol='AAPL',
    timeframe='1d',
    start='2025-01-01',
    end='2025-01-31',
    use_fallback=True  # Override enable_fallback setting
)
```

### Quality-Based Fallback

```python
# Fallback if quality < 0.85 (default)
client = MultiSourceClient(
    polygon_api_key,
    fallback_threshold=0.85
)

# More aggressive fallback (quality < 0.80)
client = MultiSourceClient(
    polygon_api_key,
    fallback_threshold=0.80
)

# Trigger fallback in request
candles, source = await client.fetch_range(
    ...,
    validate=True  # Calculate quality, trigger fallback if poor
)
```

## Data Format Compatibility

Both Polygon and Yahoo return data in the same format:

```python
{
    't': 1704067200000,  # Unix timestamp in milliseconds
    'o': 150.25,         # Open
    'h': 151.50,         # High
    'l': 150.10,         # Low
    'c': 150.99,         # Close
    'v': 50000000        # Volume
}
```

This means you can drop in `MultiSourceClient` as a replacement for `PolygonClient` with minimal code changes.

## Monitoring & Debugging

### Check Which Source is Being Used

```python
candles, source = await client.fetch_range(...)

if source == 'polygon':
    logger.info("Using primary source")
elif source == 'yahoo':
    logger.warning("Using fallback source")
else:
    logger.error("All sources failed")
```

### Monitor Fallback Usage

```python
# Get statistics
stats = client.get_stats()
print(stats)

# Output:
# {
#     'polygon_primary': 450,    # Used Polygon
#     'yahoo_fallback': 12,      # Had to fallback
#     'both_failed': 3,          # Complete failure
#     'fallback_better': 2,      # Fallback had better quality
#     'primary_better': 10,      # Primary was better
#     'equal': 5,                # Sources were equivalent
#     'total_fetches': 465,
#     'polygon_rate': '96.8%',
#     'yahoo_rate': '2.6%',
#     'failure_rate': '0.6%'
# }
```

### Log Source in Database

Add to your insert logic:

```python
# When inserting data
insert_ohlcv(
    symbol=symbol,
    candles=candles,
    metadata={...},
    source=source  # 'polygon', 'yahoo', or None
)

# Query to see source distribution
SELECT source, COUNT(*) 
FROM market_data 
GROUP BY source;

# Result:
# polygon | 452000
# yahoo   | 8500
# null    | 1200
```

## What to Monitor

### 1. Fallback Frequency
```
Expected: < 5% fallback rate
If higher: Polygon having issues, consider upgrading account or Yahoo becoming primary
```

### 2. Quality Differences
```python
# Compare quality scores by source
SELECT source, AVG(quality_score) as avg_quality
FROM market_data
GROUP BY source;

# Should be similar (within 5-10%)
# If Yahoo consistently better: Polygon data quality issue
# If Yahoo consistently worse: Polygon primary is right choice
```

### 3. Data Discrepancies
```python
# Check for large differences between sources on same candle
SELECT 
    p.symbol, p.time,
    p.close as polygon_close,
    y.close as yahoo_close,
    ABS(p.close - y.close) / p.close * 100 as pct_diff
FROM market_data p
JOIN market_data y 
    ON p.symbol = y.symbol 
    AND p.time = y.time
WHERE p.source = 'polygon' 
    AND y.source = 'yahoo'
    AND ABS(p.close - y.close) / p.close > 0.05  -- More than 5% difference
ORDER BY pct_diff DESC;
```

## Error Handling

The client handles common failures gracefully:

```python
# Polygon timeout → Fallback to Yahoo
# Polygon rate limit → Wait then retry, then fallback
# Polygon returns empty → Try Yahoo
# Both fail → Return empty list with source=None
# Network timeout → Log and return empty

try:
    candles, source = await client.fetch_range(...)
    if not candles:
        logger.error(f"Failed to fetch data for {symbol}")
    else:
        # Process candles
except Exception as e:
    logger.error(f"Unexpected error: {e}")
```

## Performance Impact

### Request Latency
```
Polygon only:        ~200-500ms per request
Polygon + Yahoo:     ~200-500ms (no fallback needed, same as above)
Polygon + Yahoo*:    ~400-1000ms (if fallback triggered)
                     * Polygon times out, then Yahoo try

Recommendation: Fallback adds minimal overhead (only on failure cases)
```

### Database I/O
```
Unchanged - still inserting same data, just tracking source
Minimal additional storage for source column (already in schema)
```

### API Rate Limits
```
Polygon:  150 req/min limit (unchanged)
Yahoo:    ~100-200 req/min estimated (fallback only on failures)

Total effective limit: Polygon primary + Yahoo for failures only
Expected impact: <5% reduction in free API quota usage if fallback activated
```

## Testing

### Unit Tests
```bash
# Test Yahoo client directly
pytest tests/test_yahoo_client.py -v

# Test multi-source logic
pytest tests/test_multi_source_client.py -v

# Test fallback scenarios
pytest tests/test_multi_source_fallback.py -v
```

### Integration Test
```python
import asyncio
from src.clients.multi_source_client import MultiSourceClient
from src.services.validation_service import ValidationService

async def test_fallback():
    client = MultiSourceClient(
        polygon_api_key="your_key",
        validation_service=ValidationService(),
        enable_fallback=True
    )
    
    # Test with known good symbol
    candles, source = await client.fetch_range(
        symbol='AAPL',
        timeframe='1d',
        start='2024-01-01',
        end='2024-01-31',
        validate=True
    )
    
    assert candles, "Should get data"
    assert source in ['polygon', 'yahoo'], f"Invalid source: {source}"
    print(f"✓ Got {len(candles)} candles from {source}")
    
    # Check stats
    stats = client.get_stats()
    print(f"✓ Stats: {stats}")

asyncio.run(test_fallback())
```

## Rollout Strategy

### Phase 1: Testing (Week 1)
```bash
# Enable on development environment
python scripts/test_multi_source.py --symbol AAPL,MSFT,GOOGL
```

### Phase 2: Gradual Rollout (Week 2)
```python
# Enable fallback for backfill only
client = MultiSourceClient(
    polygon_api_key,
    enable_fallback=True  # Only backfill uses it
)

# Keep live scheduler on Polygon only
# This tests fallback logic without affecting live data
```

### Phase 3: Full Deployment (Week 3)
```python
# Enable everywhere
# Monitor fallback rate and quality metrics
```

### Rollback Plan
```python
# If issues, disable fallback immediately
client = MultiSourceClient(
    polygon_api_key,
    enable_fallback=False  # Back to Polygon only
)
```

## FAQ

**Q: Will Yahoo data cause quality issues?**
A: Not if used correctly. Data is only used when:
- Polygon fails/times out, OR
- Quality validation explicitly triggers fallback
Otherwise Polygon is primary.

**Q: What about data consistency?**
A: Sources are tracked in database. You can:
- Filter to Polygon only for consistency (`WHERE source='polygon'`)
- Compare quality differences
- Re-fetch from primary if needed

**Q: Does this require code changes?**
A: Minimal. `MultiSourceClient` has same interface as `PolygonClient`:
```python
# Old
candles = await polygon.fetch_range(symbol, timeframe, start, end)

# New (backwards compatible)
candles, source = await multi_source.fetch_range(symbol, timeframe, start, end)
```

**Q: What if Yahoo changes their API?**
A: Easy to replace. Abstract interface makes it simple:
```python
# Swap Yahoo for another source
class Alpha VantageClient:
    async def fetch_range(self, symbol, start, end, timeframe):
        # Same interface
        return candles

# Use it
client = MultiSourceClient(
    polygon_api_key=api_key,
    fallback_client=AlphaVantageClient()  # Pluggable
)
```

## Next Steps

1. ✅ Review strategy and design
2. ✅ Create Yahoo client
3. ✅ Create multi-source orchestrator
4. → Test on development environment
5. → Integrate into scheduler
6. → Integrate into backfill scripts
7. → Monitor metrics
8. → Document in API docs

Ready to implement?
