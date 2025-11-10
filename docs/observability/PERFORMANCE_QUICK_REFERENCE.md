# Performance Monitoring Quick Reference

## TL;DR

Three new endpoints for performance visibility:

```bash
# Check system health and recommendations
curl http://localhost:8000/api/v1/performance/summary

# View cache effectiveness
curl http://localhost:8000/api/v1/performance/cache

# View query performance stats
curl http://localhost:8000/api/v1/performance/queries
```

---

## Performance Endpoints

### 1. Summary (Recommended Starting Point)
```
GET /api/v1/performance/summary
```

Returns overall performance health with actionable recommendations.

**Example Response:**
```json
{
  "timestamp": "2025-11-10T15:30:45.123456",
  "cache": {
    "size": 145,
    "hit_rate_pct": 79.0,
    "hits": 2345,
    "misses": 623
  },
  "performance": {
    "total_queries": 750,
    "avg_duration_ms": 125.4,
    "p95_duration_ms": 456.7,
    "error_rate_pct": 1.07
  },
  "bottlenecks": [
    {
      "query_type": "complex_filter",
      "avg_slow_ms": 567.8,
      "slow_count": 25
    }
  ],
  "recommendations": [
    "Cache hit rate is good at 79%",
    "P99 response time is 890.1ms - consider database optimization"
  ]
}
```

### 2. Cache Statistics
```
GET /api/v1/performance/cache
```

**Metrics:**
- `size` - Current number of cached items
- `hit_rate_pct` - Percentage of cache hits (aim for 70%+)
- `hits` / `misses` - Total hit and miss counts
- `max_size` - Maximum cache capacity
- `default_ttl_seconds` - Time-to-live for cache entries

**Good Indicators:**
- Hit rate > 70% = effective caching
- Hit rate < 30% = consider increasing TTL or cache size

### 3. Query Performance
```
GET /api/v1/performance/queries?query_type=historical_fetch
```

**Metrics:**
- `mean_ms`, `median_ms` - Average and median response time
- `p95_ms`, `p99_ms` - 95th and 99th percentile (tail latency)
- `min_ms`, `max_ms` - Range
- `error_rate_pct` - Percentage of failed queries

**Health Thresholds:**
| Metric | Green | Yellow | Red |
|--------|-------|--------|-----|
| Avg Response | < 100ms | 100-300ms | > 300ms |
| P95 | < 200ms | 200-500ms | > 500ms |
| P99 | < 400ms | 400-800ms | > 800ms |
| Error Rate | < 1% | 1-5% | > 5% |

---

## Load Testing

### Run Full Load Test Suite
```bash
python scripts/load_test_runner.py
```

Tests:
1. **Baseline** - Standard endpoints with 100 req/worker
2. **Historical Data** - High-volume data queries
3. **Sustained** - 30-second continuous load
4. **Spike** - Sudden load increase measurement

### Interpret Results
```
SUCCESS RATE: 99%+ is healthy
RESPONSE TIME: Match baseline metrics
THROUGHPUT: Expected ~100-500 req/s per worker
```

---

## Common Scenarios

### Problem: High Response Times
```bash
# Check bottlenecks
curl http://localhost:8000/api/v1/performance/summary | jq '.bottlenecks'

# Identify slowest query types
curl http://localhost:8000/api/v1/performance/queries | jq '.bottlenecks | .[0]'

# Solutions:
# 1. Optimize slow queries (database indexes)
# 2. Implement caching for expensive queries
# 3. Scale connection pool
```

### Problem: Low Cache Hit Rate
```bash
# Check cache statistics
curl http://localhost:8000/api/v1/performance/cache | jq '.cache.hit_rate_pct'

# Solutions:
# 1. Increase cache TTL (default 300s)
# 2. Increase cache size (default 1000 entries)
# 3. Review query patterns
```

### Problem: High Error Rate
```bash
# Check error details
curl http://localhost:8000/api/v1/performance/queries | jq '.stats'

# Solutions:
# 1. Review logs for error patterns
# 2. Check database connectivity
# 3. Verify input validation
```

---

## Using Cache in Code

```python
from src.services.caching import get_query_cache

cache = get_query_cache()

# Store a result
await cache.set("historical_data", data, ttl=600, symbol="AAPL")

# Retrieve from cache
cached = await cache.get("historical_data", symbol="AAPL")

# Check effectiveness
stats = cache.stats()
print(f"Hit rate: {stats['hit_rate_pct']}%")

# Clear specific namespace
await cache.invalidate("historical_data")
```

---

## Using Performance Monitor

```python
from src.services.performance_monitor import get_performance_monitor
import time

monitor = get_performance_monitor()

# Record a query
start = time.time()
result = db.query()
duration = (time.time() - start) * 1000

await monitor.record_query("my_query", duration, symbol="AAPL")

# Get statistics
stats = await monitor.get_stats()
bottlenecks = await monitor.get_bottlenecks(threshold_ms=200)
```

---

## Best Practices

### Monitoring
- ✅ Check `/api/v1/performance/summary` daily
- ✅ Review bottlenecks weekly
- ✅ Compare metrics month-over-month
- ✅ Act on recommendations

### Caching
- ✅ Aim for 70%+ hit rate
- ✅ Set TTL based on data freshness needs
- ✅ Monitor cache size (adjust if > 80% full)
- ✅ Invalidate cache after data updates

### Load Testing
- ✅ Run baseline tests monthly
- ✅ Test before deployments
- ✅ Monitor spike recovery time
- ✅ Track throughput trends

---

## Alert Thresholds

Set up alerts for:
- **P99 Response > 500ms** - Database optimization needed
- **Error Rate > 5%** - Investigate failures
- **Cache Hit Rate < 50%** - Adjust cache configuration
- **High Load Spike** - Scale resources if sustained

---

## Support

For detailed information, see:
- `PHASE_5_COMPLETE.md` - Full technical documentation
- `PERFORMANCE_QUICK_REFERENCE.md` - This guide
- `OBSERVABILITY.md` - Logging and alerts

