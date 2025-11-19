# Quick Reference Guide

## Two Systems Implemented

### 1. Validation Repair (Previous)
**Problem:** Backfilled data marked unvalidated, no way to fix it
**Solution:** `repair_unvalidated_data.py` - Re-validate all unvalidated records

```bash
# See what needs fixing
python repair_unvalidated_data.py --dry-run

# Fix it
python repair_unvalidated_data.py

# Check results
python repair_unvalidated_data.py --output report.json
```

**Files:**
- `repair_unvalidated_data.py` - Main script
- `VALIDATION_REPAIR_GUIDE.md` - Detailed guide
- `REPAIR_QUICKSTART.md` - Quick start

---

### 2. Multi-Source Fallback (New)
**Problem:** Single data source (Polygon), no fallback if it fails
**Solution:** Yahoo Finance fallback with validation-aware routing

```python
# Old code
candles = await polygon.fetch_range(symbol, timeframe, start, end)

# New code (drop-in replacement)
from src.clients.multi_source_client import MultiSourceClient
client = MultiSourceClient(polygon_api_key, enable_fallback=True)
candles, source = await client.fetch_range(symbol, timeframe, start, end)
```

**Files:**
- `src/clients/yahoo_client.py` - Yahoo client
- `src/clients/multi_source_client.py` - Multi-source orchestrator
- `MULTI_SOURCE_STRATEGY.md` - Strategy & design
- `MULTI_SOURCE_INTEGRATION.md` - Integration guide
- `MULTI_SOURCE_SUMMARY.md` - This summary

---

## When to Use Each

### Validation Repair
✅ **Use for:**
- Initial backfill cleanup
- Assessing data quality
- Fixing unvalidated records

❌ **Don't use for:**
- Real-time validation (use scheduler)
- Live data (use fallback client)

### Multi-Source Fallback
✅ **Use for:**
- Live scheduler (resilience)
- Backfill (quality assurance)
- Repair script (cross-validation)

❌ **Don't use for:**
- Single source is sufficient
- Performance-critical path (though minimal overhead)

---

## Integration Checklist

### Scheduler (EnrichmentScheduler)
```python
# Replace
self.polygon_client = PolygonClient(api_key)

# With
from src.clients.multi_source_client import MultiSourceClient
self.data_client = MultiSourceClient(api_key, enable_fallback=True)

# Replace
candles = await self.polygon_client.fetch_range(...)

# With
candles, source = await self.data_client.fetch_range(...)
```

### Backfill (master_backfill.py)
```python
# Same replacement as scheduler
# Enable validate=True for quality-aware fallback:
candles, source = await self.data_client.fetch_range(
    ...,
    validate=True
)
```

### Repair (repair_unvalidated_data.py)
```python
# Optional: Compare with alternate source
if quality < 0.85:
    fallback_candles, source = await self.data_client.fetch_range(...)
    # Use better one
```

---

## Key Metrics to Monitor

### Validation Repair
```
Metric                  Target      Red Flag
─────────────────────────────────────────────
Records validated       > 90%       < 85%
Average quality         > 0.88      < 0.80
Error count             0           > 0
```

### Multi-Source Fallback
```
Metric                  Target      Red Flag
─────────────────────────────────────────────
Polygon primary rate    > 95%       < 90%
Yahoo fallback rate     < 5%        > 10%
Failure rate            < 1%        > 5%
Quality difference      < 10%       > 20%
```

---

## Troubleshooting

### Validation Repair Issues

**Problem: Low validation rate (< 85%)**
```bash
# Check what's failing
python repair_unvalidated_data.py --output report.json
cat report.json | jq '.errors[]'

# Try lower threshold
python repair_unvalidated_data.py --quality-threshold 0.80
```

**Problem: Script running slowly**
```bash
# Increase batch size (more memory, faster)
python repair_unvalidated_data.py --batch-size 500

# Or limit scope
python repair_unvalidated_data.py --limit 10000
```

### Multi-Source Fallback Issues

**Problem: High fallback rate (> 5%)**
```python
# Check Polygon status
# Monitor Polygon API health
# Consider account upgrade

# Temporarily disable if needed
client = MultiSourceClient(api_key, enable_fallback=False)
```

**Problem: Quality mismatch (Yahoo >> Polygon)**
```sql
-- Check data distribution
SELECT source, AVG(quality_score) 
FROM market_data 
GROUP BY source;

-- If Yahoo better, may indicate Polygon data issues
```

---

## Recommended Rollout

### Week 1: Testing
```bash
# Test validation repair
python repair_unvalidated_data.py --dry-run --limit 5000

# Test multi-source on dev
python -c "
import asyncio
from src.clients.multi_source_client import MultiSourceClient

async def test():
    client = MultiSourceClient('your_key', enable_fallback=True)
    candles, source = await client.fetch_range('AAPL', '1d', '2025-01-01', '2025-01-31')
    print(f'✓ Got {len(candles)} from {source}')

asyncio.run(test())
"
```

### Week 2: Integration
```python
# Add to scheduler
# Update master_backfill.py
# Add to repair_unvalidated_data.py
```

### Week 3: Monitoring
```bash
# Monitor metrics for 24-48 hours
# Check fallback rate, quality scores, errors
# If all good, declare success
```

---

## Commands Quick Reference

### Validation Repair
```bash
# Preview
python repair_unvalidated_data.py --dry-run

# Full repair
python repair_unvalidated_data.py

# Specific symbols
python repair_unvalidated_data.py --symbols AAPL,BTC

# Save results
python repair_unvalidated_data.py --output report.json

# Specific timeframes
python repair_unvalidated_data.py --timeframes 1d,1h

# First N records
python repair_unvalidated_data.py --limit 5000

# Faster processing
python repair_unvalidated_data.py --batch-size 1000
```

### Database Queries
```sql
-- Check validation distribution
SELECT validated, COUNT(*) as count, AVG(quality_score)
FROM market_data
GROUP BY validated;

-- Check source distribution
SELECT source, COUNT(*) as count, AVG(quality_score)
FROM market_data
GROUP BY source;

-- Find high-quality records
SELECT * FROM market_data 
WHERE quality_score >= 0.95
LIMIT 10;

-- Find unvalidated records
SELECT * FROM market_data 
WHERE validated = FALSE
LIMIT 10;
```

---

## Documentation Map

| Document | Purpose | When to Read |
|----------|---------|--------------|
| `VALIDATION_REPAIR_GUIDE.md` | Deep validation guide | Troubleshooting repair issues |
| `REPAIR_QUICKSTART.md` | Quick start for repair | Getting started with repair |
| `MULTI_SOURCE_STRATEGY.md` | Strategy & design | Understanding architecture |
| `MULTI_SOURCE_INTEGRATION.md` | Integration guide | Implementing fallback |
| `MULTI_SOURCE_SUMMARY.md` | Executive summary | Overview & decision-making |
| `QUICK_REFERENCE.md` | This file | Daily reference |
| `AGENTS.md` | Command reference | Finding commands |

---

## Support

**For validation repair issues:**
See `VALIDATION_REPAIR_GUIDE.md` section "Troubleshooting"

**For multi-source integration:**
See `MULTI_SOURCE_INTEGRATION.md` section "Error Handling"

**For strategy decisions:**
See `MULTI_SOURCE_STRATEGY.md` section "When This Makes Sense"

---

## Key Concepts

**Quality Score:** 0.0-1.0 rating of OHLCV data integrity
- Validated flag: TRUE if score >= 0.85
- Updated by: Validation repair script

**Source Column:** Tracks where data came from
- 'polygon': From Polygon.io (primary)
- 'yahoo': From Yahoo Finance (fallback)
- NULL: Failed to fetch from any source

**Fallback Trigger:** When to use Yahoo instead of Polygon
1. Polygon timeout
2. Polygon rate limited
3. Polygon returns poor quality (< 0.85)
4. Explicit request with `validate=True`

**Validation Threshold:** Quality score minimum for "validated" flag
- Default: 0.85
- Can be adjusted: `--quality-threshold 0.80`

---

## Notes

- Both systems are **non-destructive** (only update flags, never delete data)
- Both can be **resumed** if interrupted
- Both provide **detailed reporting** for monitoring
- Both are **production-ready** (no alpha/beta labels)

**Start with validation repair (simpler), then add fallback (more advanced).**
