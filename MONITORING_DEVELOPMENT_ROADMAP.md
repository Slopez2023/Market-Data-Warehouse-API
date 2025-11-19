# Observation Monitoring - Development Roadmap

## Current Status
The monitoring section displays fallback data from `/api/v1/status` endpoint when dedicated endpoints are unavailable.

## Missing API Endpoints (Required for Full Functionality)

The dashboard expects these endpoints that don't currently exist:

### 1. **Enrichment Overview** ⚠️ MISSING
```
GET /api/v1/enrichment/dashboard/overview
```
**Purpose:** Current state of enrichment scheduler and operations  
**Expected Response:**
```json
{
  "scheduler_status": "running|stopped",
  "last_run": "2024-11-19T10:30:00Z",
  "next_run": "2024-11-19T11:00:00Z",
  "success_rate": 98.5,
  "symbols_enriched": 45,
  "total_symbols": 60,
  "avg_enrichment_time_seconds": 12.3
}
```
**Dependencies:**
- Query `enrichment_fetch_log` table for last run time
- Query scheduler state
- Calculate success rate from logs

---

### 2. **Dashboard Metrics** ⚠️MISSING
```
GET /api/v1/enrichment/dashboard/metrics
```
**Purpose:** Comprehensive pipeline and quality metrics  
**Expected Response:**
```json
{
  "fetch_pipeline": {
    "total_jobs": 1250,
    "success_rate": 99.2,
    "avg_job_duration_seconds": 0.245,
    "total_records_fetched": 125000
  },
  "compute_pipeline": {
    "total_computations": 1240,
    "success_rate": 99.6,
    "avg_computation_time_ms": 12,
    "total_features_computed": 50000
  },
  "data_quality": {
    "avg_validation_rate": 98.5,
    "avg_quality_score": 0.93,
    "avg_data_completeness": 97.8
  },
  "symbol_health": {
    "healthy": 55,
    "warning": 4,
    "critical": 1
  },
  "last_24h": {
    "records_fetched": 5000,
    "features_computed": 2000
  }
}
```
**Dependencies:**
- Parse `enrichment_fetch_log` table
- Parse computation logs
- Calculate data quality from candle records
- Symbol status from `symbol_health` tracking

---

### 3. **Health Dashboard** ⚠️ MISSING
```
GET /api/v1/enrichment/dashboard/health
```
**Purpose:** System component health status  
**Expected Response:**
```json
{
  "scheduler": "healthy|degraded|critical",
  "database": "healthy|degraded|critical",
  "api_connectivity": "healthy|degraded|critical",
  "recent_failures_24h": 3,
  "last_health_check": "2024-11-19T10:35:00Z"
}
```
**Dependencies:**
- Connection pool health checks
- Scheduler state monitoring
- API connectivity tests
- Error log analysis (last 24h)

---

### 4. **Enrichment History/Jobs** ⚠️ MISSING
```
GET /api/v1/enrichment/history?limit=10
```
**Purpose:** Recent enrichment job results  
**Expected Response:**
```json
{
  "jobs": [
    {
      "symbol": "AAPL",
      "status": "success|failed",
      "records_fetched": 250,
      "records_inserted": 250,
      "response_time_ms": 1250,
      "created_at": "2024-11-19T10:30:00Z"
    }
  ]
}
```
**Dependencies:**
- Query `enrichment_fetch_log` table
- Join with symbol data
- Order by timestamp descending

---

## Existing Endpoints (Partially Useful)

✅ **GET /api/v1/enrichment/metrics** - Exists but full format unclear
- Partially covers fetch & compute pipeline data
- May need enhancement for dashboard format

✅ **GET /api/v1/status** - Exists
- Basic database metrics
- Scheduler status
- Used as fallback in dashboard

✅ **GET /api/v1/observability/metrics** - Exists (may be useful)
- Could contain performance data

---

## Implementation Priority

### Phase 1 (Critical)
1. ✅ Dashboard fallback logic (COMPLETED)
2. `GET /api/v1/enrichment/dashboard/overview` - Track scheduler state
3. `GET /api/v1/enrichment/dashboard/metrics` - Pipeline metrics

### Phase 2 (Important)
4. `GET /api/v1/enrichment/dashboard/health` - System health
5. `GET /api/v1/enrichment/history` - Recent jobs

### Phase 3 (Enhancement)
6. Real-time job tracking via WebSocket or Server-Sent Events (SSE)
7. Historical metrics charts and trends
8. Alert integration with monitoring section

---

## Database Tables Available

- `enrichment_fetch_log` - Fetch operation logs with timing
- `symbol_health` - Symbol status tracking (if exists)
- `candle_record` - OHLCV data for quality metrics
- `backfill_history` - Backfill operation logs

---

## Monitoring Section Coverage

| Section | Status | Depends On |
|---------|--------|-----------|
| Enrichment Status | 🟡 Fallback | overview endpoint |
| Fetch Pipeline | 🟡 Fallback | metrics endpoint |
| Compute Pipeline | 🟡 Fallback | metrics endpoint |
| Data Quality | 🟡 Fallback | metrics endpoint |
| Recent Jobs | ❌ Empty | history endpoint |
| System Health | 🟡 Fallback | health endpoint |

---

## Quick Implementation Guide

Each endpoint should:
1. Check if enrichment_fetch_log exists and has recent data
2. Return 200 with empty data if no logs found (don't 404)
3. Include cache headers for dashboard freshness
4. Run periodic aggregation job to pre-calculate metrics (recommended)

Example for overview:
```python
@app.get("/api/v1/enrichment/dashboard/overview")
async def enrichment_overview():
    session = db.SessionLocal()
    try:
        # Get last enrichment job from log
        last_job = session.query(EnrichmentFetchLog)\
            .order_by(EnrichmentFetchLog.created_at.desc())\
            .first()
        
        # Calculate stats from recent logs (last 24h)
        # Return structured response
    finally:
        session.close()
```
