# Dashboard Enrichment Monitoring - Quick Start

## Access the Dashboard

```
http://localhost:8000/dashboard/
```

## What You'll See

### 1. **Enrichment Status** (Top Section)
Shows the daily enrichment job status:
- 🟢 **Status**: Running or Stopped
- 📅 **Last Run**: When enrichment last executed
- 📍 **Next Run**: When enrichment will run next (typically 1:30 AM UTC daily)
- ✓ **Success Rate**: Percentage of successful enrichment jobs
- 📊 **Symbols Enriched**: Count of processed symbols
- ⚡ **Avg Time**: Average seconds per enrichment job

### 2. **Pipeline Metrics** (Middle Section)
Three cards showing data flow:

#### Fetch Pipeline
- Total fetches made
- % successful
- Average response time (ms)
- Total records fetched from Polygon API

#### Compute Pipeline
- Total feature computations
- % successful
- Average computation time (ms)
- Total features calculated (technical indicators, etc.)

#### Data Quality
- Validation rate %
- Quality score (0-1)
- Completeness rate %
- Count of healthy symbols

### 3. **System Health** (Bottom Section)
Four health indicators:
- 🟢 **Scheduler**: Is the enrichment scheduler running?
- 🟢 **Database**: Can we connect to PostgreSQL?
- 🟢 **API Connectivity**: Can we reach Polygon API?
- ⚠️ **24h Failures**: How many jobs failed in last 24 hours?

Status colors:
- 🟢 Green = Healthy
- 🟡 Yellow = Degraded
- 🔴 Red = Critical

### 4. **Recent Enrichment Jobs** (Bottom Table)
Shows the 10 most recent enrichment fetch jobs:

| Column | Shows |
|--------|-------|
| Symbol | Which symbol was processed |
| Status | ✓ Success or ✗ Failed |
| Records Fetched | How many records pulled from Polygon |
| Records Inserted | How many actually stored in DB |
| Response Time | How long it took (ms) |
| Timestamp | When the job ran |

---

## How Data Gets There

```
Data Flow:
1. Scheduler runs enrichment job (daily @ 1:30 AM UTC)
2. For each symbol:
   a. Fetch OHLCV data from Polygon API → enrichment_fetch_log
   b. Compute technical indicators → enrichment_compute_log
   c. Update enrichment_status with results
3. Dashboard polls every 10 seconds
4. Displays real-time metrics and recent jobs
```

---

## What Each API Endpoint Provides

### `/api/v1/enrichment/dashboard/overview`
```json
{
  "scheduler_status": "running",
  "total_symbols": 45,
  "symbols_enriched": 40,
  "success_rate": 98.5,
  "last_run": "2024-11-14T01:30:00Z",
  "next_run": "2024-11-15T01:30:00Z",
  "avg_enrichment_time_seconds": 45.2
}
```

### `/api/v1/enrichment/dashboard/metrics`
```json
{
  "fetch_pipeline": {
    "total_jobs": 1250,
    "success_rate": 99.2,
    "avg_job_duration_seconds": 2.5,
    "total_records_fetched": 125000
  },
  "compute_pipeline": {
    "total_computations": 1250,
    "success_rate": 98.8,
    "total_features_computed": 12500
  },
  "data_quality": {
    "avg_validation_rate": 97.5,
    "avg_quality_score": 0.95,
    "avg_data_completeness": 98.2
  }
}
```

### `/api/v1/enrichment/dashboard/health`
```json
{
  "scheduler": "healthy",
  "database": "healthy",
  "api_connectivity": "healthy",
  "recent_failures_24h": 2,
  "symbol_health": {
    "healthy": 40,
    "warning": 3,
    "error": 2
  }
}
```

### `/api/v1/enrichment/history?limit=10`
```json
{
  "jobs": [
    {
      "symbol": "AAPL",
      "success": true,
      "records_fetched": 250,
      "records_inserted": 250,
      "response_time_ms": 145,
      "created_at": "2024-11-14T01:35:00Z"
    }
  ]
}
```

---

## Common Questions

### Q: Why do the metrics show 0 sometimes?
**A**: If enrichment hasn't run yet (or database is empty), metrics are 0. They populate after the first enrichment job runs.

### Q: How often does the dashboard update?
**A**: Every 10 seconds automatically. Click "Refresh Now" for immediate update.

### Q: Can I see enrichment status for a specific symbol?
**A**: Yes! Click on any symbol in the "Symbol Quality & Status" table to open the asset modal. The "Enrichment" tab shows symbol-specific enrichment data.

### Q: What does "Avg Time" mean?
**A**: Average seconds per enrichment job (fetch + compute combined).

### Q: What if the dashboard shows all zeros?
**A**: Check that:
1. Database has data (`Symbol Quality & Status` table shows symbols)
2. Enrichment scheduler is running (green status badge)
3. Try "Refresh Now" button

### Q: How do I debug a failing enrichment job?
**A**: 
1. Check the "Recent Enrichment Jobs" table for the failed job
2. Click on the symbol in the main symbol table
3. View "Enrichment" tab for detailed error messages

---

## What's Different Now

### Before ❌
```
✗ Only scheduler status shown
✗ No pipeline metrics visible
✗ No job history displayed
✗ No health indicators
✗ Enrichment data inaccessible
```

### Now ✅
```
✓ Full enrichment status visible
✓ All pipeline metrics displayed
✓ 10 recent jobs in table
✓ 4 health indicators
✓ Data quality scores
✓ Per-symbol enrichment details (via asset modal)
✓ Real-time updates every 10 seconds
```

---

## Troubleshooting

### Dashboard loads but shows all "--"
**Cause**: API endpoints not responding
**Fix**: 
1. Check API is running: `curl http://localhost:8000/health`
2. Check enrichment service initialized: Check main.py logs
3. Restart API if needed

### Some metrics show but others are blank
**Cause**: Particular endpoint not returning data
**Fix**: 
1. Check individual endpoints in browser console
2. Verify database tables exist
3. Check API logs for errors

### Numbers not updating
**Cause**: Auto-refresh disabled or API issue
**Fix**:
1. Click "Refresh Now" button
2. Check browser console for JS errors
3. Verify API connectivity

---

## Example Workflow

### Morning: Check System Health
1. Open dashboard
2. Verify all 4 health indicators are green
3. Check "Success Rate" is >95%

### After Enrichment Runs (1:30 AM UTC)
1. Check "Recent Enrichment Jobs" table
2. Verify last 10 jobs show ✓ Success
3. Check "Avg Time" is reasonable (~40-60 seconds)

### Debugging an Issue
1. Find failed job in table
2. Click symbol name to open asset modal
3. View enrichment error message
4. Check Polygon API quota if fetch failed
5. Check computation if compute failed

---

## Performance Notes

- Dashboard updates every 10 seconds (configurable)
- All API calls are parallel (not sequential)
- Typical load time: 1-2 seconds
- Uses browser caching for CSS/JS

---

## API Reference for Developers

### Fetch All Enrichment Data
```bash
curl http://localhost:8000/api/v1/enrichment/dashboard/overview
curl http://localhost:8000/api/v1/enrichment/dashboard/metrics
curl http://localhost:8000/api/v1/enrichment/dashboard/health
curl 'http://localhost:8000/api/v1/enrichment/history?limit=10'
```

### Query Specific Symbol
```bash
curl http://localhost:8000/api/v1/enrichment/dashboard/job-status/AAPL
```

### Recent Jobs with Filters
```bash
# All jobs
curl 'http://localhost:8000/api/v1/enrichment/history?limit=50'

# Only successful
curl 'http://localhost:8000/api/v1/enrichment/history?success=true&limit=50'

# Specific symbol
curl 'http://localhost:8000/api/v1/enrichment/history?symbol=AAPL&limit=50'
```

---

## Summary

✅ **Dashboard is fully functional**
- Real-time enrichment monitoring
- Live pipeline metrics
- Job queue visibility
- System health indicators
- Per-symbol details

All enrichment data is now accessible and actionable. 🎉
