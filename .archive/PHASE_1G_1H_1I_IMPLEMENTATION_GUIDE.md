# Phase 1g, 1h, 1i Implementation Guide

## Quick Start

### 1. Files Added

**Phase 1g: Enrichment Scheduler**
- `src/services/enrichment_scheduler.py` - Main scheduler service

**Phase 1h: Enrichment UI Dashboard**
- `src/routes/enrichment_ui.py` - Dashboard endpoints

**Phase 1i: Production Hardening**
- `src/services/resilience_manager.py` - Resilience patterns

**Tests**
- `tests/test_phase_1g_scheduler.py` - Scheduler tests
- `tests/test_phase_1i_resilience.py` - Resilience tests

**Documentation**
- `PHASE_1G_1H_1I_COMPLETION.md` - Complete feature documentation

### 2. Integration in main.py

Already integrated:
- Enrichment scheduler initialization in lifespan startup
- Enrichment UI router mounted
- Resilience manager registered with circuit breaker and rate limiter
- Proper shutdown handling for scheduler

### 3. Test the Implementation

```bash
# Run Phase 1g tests
pytest tests/test_phase_1g_scheduler.py -v

# Run Phase 1i tests  
pytest tests/test_phase_1i_resilience.py -v

# Run all enrichment tests
pytest tests/test_phase_1*.py -v
```

### 4. Start the Application

```bash
# Set environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/db"
export POLYGON_API_KEY="your_api_key"

# Run the application
python main.py
```

### 5. Test Endpoints

```bash
# Check scheduler health
curl http://localhost:8000/api/v1/enrichment/dashboard/health

# Get overview
curl http://localhost:8000/api/v1/enrichment/dashboard/overview

# Trigger enrichment
curl -X POST http://localhost:8000/api/v1/enrichment/trigger

# Check metrics
curl http://localhost:8000/api/v1/enrichment/dashboard/metrics
```

---

## Feature Overview

### Phase 1g: Enrichment Scheduler

**What it does:**
- Automatically enriches all tracked symbols on a daily schedule
- Processes multiple symbols in parallel (configurable)
- Handles failures with exponential backoff retry logic
- Tracks job status and provides monitoring hooks

**Configuration:**
```python
EnrichmentScheduler(
    db_service=db,
    config=config,
    enrichment_hour=1,              # Daily at 1 AM UTC
    enrichment_minute=30,           # 1:30 AM UTC
    max_concurrent_symbols=5,       # Process 5 in parallel
    max_retries=3,                  # Retry failed symbols 3 times
    enable_daily_enrichment=True    # Enable automatic scheduling
)
```

**Key Methods:**
- `scheduler.start()` - Start the scheduler
- `scheduler.stop()` - Stop the scheduler
- `await scheduler.trigger_enrichment_now()` - Manual trigger
- `await scheduler.get_scheduler_status()` - Get status
- `await scheduler.get_job_status(symbol)` - Get symbol status
- `await scheduler.get_enrichment_metrics()` - Get metrics

### Phase 1h: Enrichment UI Dashboard

**What it does:**
- Provides REST API endpoints for dashboard visualization
- Displays real-time enrichment progress
- Shows metrics and health status
- Allows manual control (pause/resume/trigger)

**Key Endpoints:**
- `GET /api/v1/enrichment/dashboard/overview` - Full dashboard
- `GET /api/v1/enrichment/dashboard/metrics` - Real-time metrics
- `GET /api/v1/enrichment/dashboard/health` - Health status
- `POST /api/v1/enrichment/trigger` - Manual trigger
- `GET /api/v1/enrichment/pause` - Pause scheduler
- `GET /api/v1/enrichment/resume` - Resume scheduler
- `GET /api/v1/enrichment/history` - Job history

### Phase 1i: Production Hardening

**What it does:**
- Implements circuit breaker pattern for API resilience
- Rate limiting to prevent API quota exhaustion
- Exponential backoff retry policy
- Bulkhead isolation for resource protection

**Available Patterns:**
```python
resilience = get_resilience_manager()

# Circuit breaker
cb = resilience.register_circuit_breaker("polygon_api")

# Rate limiter
rl = resilience.register_rate_limiter("enrichment", rate=100)

# Retry policy
rp = resilience.register_retry_policy("enrichment")

# Bulkhead
bh = resilience.register_bulkhead("enrichment", max_concurrent=10)
```

---

## Architecture

### Data Flow

```
1. Daily Schedule (1:30 AM UTC)
   ↓
2. EnrichmentScheduler._daily_enrichment_job()
   ├─ Load active symbols from DB
   ├─ Create semaphore for concurrency control
   └─ Enqueue all symbols for processing
   ↓
3. _process_symbols_concurrent() [max 5 parallel]
   ├─ For each symbol:
   │  ├─ Initialize job status
   │  ├─ Call DataEnrichmentService.enrich_asset()
   │  ├─ Handle success/failure
   │  └─ Update job status
   └─ Track aggregate results
   ↓
4. Error Recovery Loop
   ├─ If failed: retry with exponential backoff
   │  ├─ Attempt 1: Retry immediately
   │  ├─ Attempt 2: Wait 2s
   │  ├─ Attempt 3: Wait 4s
   │  └─ Attempt 4: Wait 8s
   └─ After 3 retries: mark as failed
   ↓
5. Dashboard APIs Query Results
   ├─ /dashboard/overview → job_status + metrics
   ├─ /dashboard/metrics → fetch/compute/quality stats
   └─ /dashboard/health → scheduler status
```

### Job State Machine

```
PENDING
  ↓
IN_PROGRESS ←→ RETRY (on failure, up to 3 times)
  ↓
COMPLETED (success)
  OR
FAILED (after 3 retries)
```

### Resilience Flow

```
API Call
  ↓
Rate Limiter Check
  ├─ If limited: reject with backoff
  └─ If allowed: continue
  ↓
Circuit Breaker Check
  ├─ CLOSED: allow request
  ├─ OPEN: reject immediately
  └─ HALF_OPEN: test request
  ↓
Bulkhead Check
  ├─ If slots available: execute with timeout
  └─ If full: queue or reject
  ↓
Retry Policy
  ├─ If success: return result
  └─ If failure: retry with exponential backoff
```

---

## Configuration Options

### Enrichment Scheduler

```python
# In config or environment
enrichment_schedule_hour = 1        # UTC hour (0-23)
enrichment_schedule_minute = 30     # Minute (0-59)

# In scheduler initialization
max_concurrent_symbols = 5          # Parallel processing
max_retries = 3                     # Failure retries
enable_daily_enrichment = True      # Enable auto schedule
```

### Resilience Manager

```python
# Circuit Breaker
failure_threshold = 0.5             # 50% failure rate
recovery_timeout = 60               # Try recovery after 60s

# Rate Limiter
rate = 100                          # Requests per interval
interval = 60                       # Interval in seconds
burst = 150                         # Max tokens

# Retry Policy
max_retries = 3                     # Maximum retries
initial_delay = 1.0                 # Start delay in seconds
max_delay = 60.0                    # Maximum delay in seconds
backoff_multiplier = 2.0            # Exponential growth factor

# Bulkhead
max_concurrent = 10                 # Max concurrent operations
timeout = 300                       # Operation timeout in seconds
```

---

## Monitoring & Observability

### Logging

The scheduler logs key events:
```
enrichment_scheduler_started
enrichment_job_started
enrichment_symbol_started
enrichment_completed
enrichment_failed
enrichment_job_completed
```

Each log includes:
- Timestamp
- Symbol (where applicable)
- Attempt number (for retries)
- Duration (for completed jobs)
- Error message (if failed)

### Metrics Available

Via `/api/v1/enrichment/dashboard/metrics`:
```json
{
  "fetch_pipeline": {
    "total_fetches": 1250,
    "successful": 1240,
    "success_rate": 99.2,
    "avg_response_time_ms": 245,
    "api_quota_remaining": 450
  },
  "compute_pipeline": {
    "total_computations": 1240,
    "successful": 1235,
    "success_rate": 99.6,
    "avg_computation_time_ms": 12
  },
  "data_quality": {
    "symbols_tracked": 45,
    "avg_validation_rate": 98.5,
    "avg_quality_score": 0.93
  }
}
```

### Health Checks

Via `/api/v1/enrichment/dashboard/health`:
- Scheduler running status
- Last enrichment time
- Failed symbol count
- System issues detected

---

## Troubleshooting

### Issue: Scheduler not starting

**Symptoms:** Enrichment not running at scheduled time

**Debug steps:**
1. Check logs for initialization errors
2. Verify `enable_daily_enrichment=True`
3. Check scheduler status: `GET /api/v1/enrichment/dashboard/health`
4. Verify database connection

**Solution:**
```bash
# Check status
curl http://localhost:8000/api/v1/enrichment/dashboard/health

# Manually trigger to test
curl -X POST http://localhost:8000/api/v1/enrichment/trigger
```

### Issue: Many symbols failing

**Symptoms:** High failure count in last job result

**Debug steps:**
1. Check specific symbol status: `GET /api/v1/enrichment/dashboard/job-status/{symbol}`
2. Check API quota: `GET /api/v1/enrichment/dashboard/metrics`
3. Check data quality: `GET /api/v1/data/quality/{symbol}`
4. Review logs for error patterns

**Solution:**
```bash
# Check which symbols failed
curl http://localhost:8000/api/v1/enrichment/dashboard/overview | jq '.processing_symbols[] | select(.status=="failed")'

# Check specific symbol
curl http://localhost:8000/api/v1/enrichment/dashboard/job-status/AAPL

# Check metrics
curl http://localhost:8000/api/v1/enrichment/dashboard/metrics
```

### Issue: Circuit breaker stuck open

**Symptoms:** All requests failing with "Circuit breaker is OPEN"

**Debug steps:**
1. Check circuit breaker status via resilience manager
2. Verify underlying API (Polygon) is working
3. Check failure rate from metrics

**Solution:**
```bash
# Wait for recovery timeout (60s by default)
# Or manually trigger enrichment which may reset it

# Check resilience status (needs custom endpoint - add to API)
# For now, restart app to reset circuit breakers
```

### Issue: Timeout errors

**Symptoms:** Enrichment jobs timing out

**Debug steps:**
1. Check database performance
2. Check API response times: `GET /api/v1/enrichment/dashboard/metrics`
3. Check system resources (CPU, memory)

**Solution:**
```python
# Increase timeout in BulkheadIsolation
bulkhead.timeout = 600  # 10 minutes instead of 5

# Reduce concurrent symbols to lower load
scheduler.max_concurrent_symbols = 3
```

---

## Performance Tuning

### Increase Throughput

```python
# Process more symbols in parallel
scheduler.max_concurrent_symbols = 10  # Instead of 5

# Risk: Higher memory usage and database load
```

### Reduce Resource Usage

```python
# Process fewer symbols in parallel
scheduler.max_concurrent_symbols = 2  # Instead of 5

# Trade-off: Longer overall enrichment duration
```

### Improve Reliability

```python
# More generous retry policy
retry_policy.max_retries = 5         # Instead of 3
retry_policy.max_delay = 300         # 5 minutes instead of 60s

# Trade-off: May take 30+ minutes on transient failures
```

### API Rate Limit Compliance

```python
# Check actual Polygon API limits
rate_limiter = resilience.register_rate_limiter(
    name="polygon",
    rate=5,             # 5 requests
    interval=60,        # Per minute (Polygon free tier)
    burst=10            # Allow small burst
)

# Adjust based on your API tier
```

---

## Testing

### Unit Tests

```bash
# Test scheduler alone
pytest tests/test_phase_1g_scheduler.py::TestScheduler -v

# Test resilience patterns
pytest tests/test_phase_1i_resilience.py::TestCircuitBreaker -v
```

### Integration Tests

```bash
# Test with real database
pytest tests/test_enrichment_integration.py -v

# Test dashboard endpoints
pytest tests/test_enrichment_dashboard.py -v
```

### Load Tests

```bash
# Test with 50 concurrent symbols
pytest tests/test_enrichment_load.py -v

# Benchmark performance
pytest tests/test_enrichment_benchmark.py --benchmark-only
```

### Manual Testing

```bash
# 1. Start application
python main.py

# 2. Check scheduler health
curl http://localhost:8000/api/v1/enrichment/dashboard/health

# 3. Trigger manual enrichment
curl -X POST http://localhost:8000/api/v1/enrichment/trigger?symbols=AAPL

# 4. Check job status
curl http://localhost:8000/api/v1/enrichment/dashboard/job-status/AAPL

# 5. Check metrics
curl http://localhost:8000/api/v1/enrichment/dashboard/metrics

# 6. Check overview
curl http://localhost:8000/api/v1/enrichment/dashboard/overview
```

---

## Migration Path

### From Old Scheduler (Phase 1d) to New (Phase 1g)

The new enrichment scheduler **complements** the existing backfill scheduler:

1. **AutoBackfillScheduler** (existing) - Handles daily OHLCV backfill
2. **EnrichmentScheduler** (new) - Handles feature computation and enrichment

Both run independently but in sequence for optimal performance:
```
2:00 AM - AutoBackfillScheduler runs (fetch latest data)
1:30 AM - EnrichmentScheduler runs (compute features)
```

### Monitoring Both Schedulers

```bash
# Check backfill status
GET /api/v1/metrics

# Check enrichment status
GET /api/v1/enrichment/dashboard/overview

# Both should show recent completion times
```

---

## Security Considerations

### Rate Limiting

The rate limiter protects against:
- API quota exhaustion
- DDoS-style attacks
- Resource exhaustion

**Configuration:**
```python
# Based on API tier
resilience.register_rate_limiter(
    name="polygon",
    rate=5,      # Polygon free tier limit
    interval=60,
    burst=10
)
```

### Circuit Breaker

The circuit breaker protects against:
- Cascading failures
- Thundering herd problem
- Resource exhaustion from retries

**Configuration:**
```python
resilience.register_circuit_breaker(
    name="polygon_api",
    failure_threshold=0.5,   # Open at 50% failure rate
    recovery_timeout=60      # Try recovery every 60s
)
```

### Bulkhead Isolation

The bulkhead protects against:
- Resource exhaustion
- Long-running operations blocking others
- Memory leaks from unbounded connections

**Configuration:**
```python
resilience.register_bulkhead(
    name="enrichment",
    max_concurrent=10,   # Limit concurrent operations
    timeout=300          # Timeout long operations
)
```

---

## Future Enhancements

### Phase 1j: Advanced Monitoring
- Prometheus metrics export
- Grafana dashboard templates
- Custom alerting rules
- PagerDuty integration

### Phase 1k: Performance Optimization
- Symbol batching
- Feature caching
- Async database operations
- Parallel timeframe processing

### Phase 1l: Web Dashboard
- Real-time React/Vue UI
- WebSocket updates
- Historical analytics
- Symbol management

### Phase 1m: Advanced Scheduling
- Multiple schedule profiles
- Time-based concurrency limits
- Priority queuing
- Adaptive scheduling based on load

---

## Support

For issues or questions:
1. Check `/api/v1/enrichment/dashboard/health` for current status
2. Review logs in application output
3. Check `/api/v1/enrichment/dashboard/overview` for details
4. Test specific symbols with `/api/v1/enrichment/dashboard/job-status/{symbol}`
