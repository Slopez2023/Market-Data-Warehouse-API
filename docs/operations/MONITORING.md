# Observability & Monitoring Guide

## Overview

The Market Data API now includes comprehensive observability features:
- **Structured Logging**: JSON-formatted logs with trace IDs for request correlation
- **Metrics Collection**: Request counts, error rates, response times per endpoint
- **Alert Management**: Configurable alerts sent via logs or email

Deployed to production on November 10, 2025.

---

## Structured Logging

### Features

- **JSON Format**: All logs output as JSON for easy parsing by log aggregation tools
- **Trace IDs**: Every request gets a unique trace ID for correlation across services
- **Extra Context**: Additional metadata automatically included in logs

### Example Log Output

```json
{
  "timestamp": "2025-11-10T15:30:45.123456",
  "level": "INFO",
  "logger": "src.middleware",
  "message": "GET /api/v1/historical/AAPL",
  "trace_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "extra": {
    "method": "GET",
    "endpoint": "/api/v1/historical/AAPL",
    "status": 200,
    "duration_ms": 45.23
  }
}
```

### Using Structured Logger

```python
from src.services.structured_logging import StructuredLogger

logger = StructuredLogger(__name__)

# Simple log
logger.info("Processing backfill")

# Log with extra context
logger.info("Backfill completed", extra={
    "symbols": 15,
    "records_inserted": 1250,
    "duration_seconds": 23.5,
})

# Error with exception
try:
    # some operation
except Exception as e:
    logger.error("Backfill failed", extra={
        "symbols": symbols,
    }, exc_info=True)
```

### Trace ID Usage

Trace IDs are automatically generated for each request. To use trace IDs in custom code:

```python
from src.services.structured_logging import get_trace_id, set_trace_id

# Get current trace ID
current_trace_id = get_trace_id()

# Set custom trace ID (useful when correlating with external systems)
set_trace_id("my-custom-trace-id")
```

---

## Metrics Collection

### Overview

The API automatically collects metrics for every request and error.

### Available Metrics

**Per-Request:**
- Endpoint path
- HTTP method
- Status code
- Response duration (ms)
- Trace ID

**Per-Error:**
- Error type
- Error message
- Endpoint
- Timestamp
- Trace ID

**Aggregated (24-hour retention):**
- Total request count
- Total error count
- Error rate (%)
- Average response time
- Requests/errors in last hour
- Per-endpoint statistics

### Metrics Endpoints

#### 1. GET `/api/v1/observability/metrics`

Get current system metrics and health status.

**Response:**
```json
{
  "timestamp": "2025-11-10T15:30:45.123456",
  "health_status": "healthy",
  "summary": {
    "total_requests": 2543,
    "total_errors": 12,
    "error_rate_pct": 0.47,
    "avg_response_time_ms": 52.34,
    "requests_last_hour": 145,
    "errors_last_hour": 1
  },
  "endpoints": {
    "GET /api/v1/historical/{symbol}": {
      "requests": 1850,
      "errors": 5,
      "avg_duration_ms": 65.23,
      "status_codes": {
        "200": 1845,
        "404": 5
      }
    },
    "GET /health": {
      "requests": 523,
      "errors": 0,
      "avg_duration_ms": 2.15,
      "status_codes": {
        "200": 523
      }
    }
  },
  "error_summary": {
    "HTTPException": 5,
    "ValueError": 2,
    "ConnectionError": 5
  }
}
```

**Health Status Values:**
- `healthy`: Error rate < 5%, recent activity
- `degraded`: Error rate 5-10%
- `critical`: Error rate > 10%
- `idle`: No requests in last hour

#### 2. GET `/api/v1/observability/alerts`

Get recent alert history.

**Query Parameters:**
- `limit`: Number of alerts to return (1-1000, default: 100)

**Response:**
```json
{
  "timestamp": "2025-11-10T15:30:45.123456",
  "count": 3,
  "alerts": [
    {
      "type": "high_error_rate",
      "severity": "warning",
      "title": "High Error Rate Detected",
      "message": "Error rate is 8.5% (threshold: 10%)",
      "timestamp": "2025-11-10T15:15:00.000000",
      "metadata": {
        "error_rate_pct": 8.5,
        "request_count": 235,
        "threshold": 10
      }
    }
  ]
}
```

---

## Alert Management

### Overview

Alerts are triggered automatically based on system health metrics. You can configure:
- Where alerts are sent (logs, email, etc.)
- Alert thresholds
- Alert recipients

### Alert Types

| Type | Trigger | Default Severity |
|------|---------|------------------|
| `high_error_rate` | Error rate > threshold | Warning/Critical |
| `database_offline` | Cannot connect to DB | Critical |
| `scheduler_failed` | Scheduler not running | Critical |
| `data_staleness` | Data older than threshold | Warning |
| `api_timeout` | Request throws exception | Warning |

### Alert Thresholds

Default thresholds (configurable):

```python
alert_manager.set_threshold("error_rate_pct", 10.0)
alert_manager.set_threshold("data_staleness_hours", 24)
alert_manager.set_threshold("api_timeout_seconds", 30)
```

### Alert Handlers

#### Log Handler (Always Enabled)

Alerts are automatically logged as structured JSON.

```json
{
  "timestamp": "2025-11-10T15:30:45.123456",
  "level": "WARNING",
  "logger": "src.services.alerting",
  "message": "[high_error_rate] High Error Rate Detected: Error rate is 8.5% (threshold: 10%)",
  "trace_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "extra": {
    "alert_metadata": {
      "error_rate_pct": 8.5,
      "request_count": 235,
      "threshold": 10
    }
  }
}
```

#### Email Handler (Optional)

Send alerts via email. Configure with environment variables:

```bash
ALERT_EMAIL_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
ALERT_FROM_EMAIL=your-email@gmail.com
ALERT_FROM_PASSWORD=your-app-password
ALERT_TO_EMAILS=ops@company.com,dev@company.com
```

### Custom Alerts

Trigger custom alerts in code:

```python
from src.services.alerting import get_alert_manager, AlertType, AlertSeverity
import asyncio

async def my_function():
    alert_manager = get_alert_manager()
    
    # Trigger custom alert
    await alert_manager.alert(
        alert_type=AlertType.CUSTOM,
        severity=AlertSeverity.WARNING,
        title="Custom Alert",
        message="Something interesting happened",
        metadata={
            "context": "value1",
            "details": "value2"
        }
    )

# In an async context:
asyncio.run(my_function())
```

### Built-in Alert Checks

Call these to trigger alerts based on current system state:

```python
alert_manager = get_alert_manager()

# Check error rate
await alert_manager.check_error_rate(
    error_rate_pct=8.5,
    request_count=235
)

# Check data staleness
await alert_manager.check_data_staleness(
    latest_data_age_hours=25.5
)

# Check scheduler health
await alert_manager.check_scheduler_health(
    is_running=True,
    last_run_age_hours=23.5
)
```

---

## Integration with Existing Endpoints

### Status Endpoint

GET `/api/v1/status` includes data quality metrics and database health.

### Scheduler Endpoint

GET `/api/v1/metrics` includes scheduler status and last backfill results.

### Combined Monitoring

Check overall system health:

```bash
# Get all metrics
curl http://localhost:8000/api/v1/metrics

# Get observability metrics
curl http://localhost:8000/api/v1/observability/metrics

# Get recent alerts
curl http://localhost:8000/api/v1/observability/alerts?limit=50
```

---

## Deployment

### Docker Environment

Add to `.env` file for email alerts:

```bash
# Logging
LOG_LEVEL=INFO

# Email Alerts (optional)
ALERT_EMAIL_ENABLED=false
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
ALERT_FROM_EMAIL=alerts@yourcompany.com
ALERT_FROM_PASSWORD=your-app-password
ALERT_TO_EMAILS=ops@yourcompany.com,dev@yourcompany.com
```

### Kubernetes/Cloud Deployment

Environment variables work the same. For secrets, use your platform's secret management:

```yaml
env:
  - name: ALERT_EMAIL_ENABLED
    value: "true"
  - name: ALERT_FROM_EMAIL
    valueFrom:
      secretKeyRef:
        name: api-secrets
        key: alert-email
  - name: ALERT_FROM_PASSWORD
    valueFrom:
      secretKeyRef:
        name: api-secrets
        key: alert-password
```

---

## Monitoring Best Practices

### 1. Regular Health Checks

Monitor these endpoints on an interval:
- `/health` - Basic liveness
- `/api/v1/observability/metrics` - Detailed health
- `/api/v1/observability/alerts` - Recent issues

### 2. Alert Thresholds

Adjust for your traffic patterns:
- High-volume API: 10-20% error threshold
- Low-volume API: 5% error threshold
- Always alert on database connectivity issues

### 3. Log Aggregation

Use a tool like ELK Stack, Datadog, or New Relic to:
- Aggregate JSON logs
- Search by trace ID
- Build dashboards
- Set up custom alerts

### 4. Metrics Export

Current metrics are in-memory. For persistent metrics:
- Export to Prometheus
- Use APM tool (Datadog, New Relic, etc.)
- Implement custom export to your metrics system

### 5. Trace ID Best Practices

- Pass `X-Trace-ID` header in requests to correlate with external systems
- Store trace IDs in logs and alerts
- Use trace IDs to debug multi-service issues

---

## Architecture

### Components

```
Request
  ↓
ObservabilityMiddleware
  ├─ Generate/capture trace ID
  ├─ Record timing
  ├─ Handle errors
  └─ Call endpoint
    ↓
MetricsCollector (thread-safe)
  ├─ Store request metrics
  ├─ Store error metrics
  └─ Clean up old metrics (24h retention)
    ↓
AlertManager (async)
  ├─ Check thresholds
  ├─ Create alerts
  └─ Notify handlers
    ├─ LogAlertHandler
    └─ EmailAlertHandler
```

### Thread Safety

- MetricsCollector uses locks for thread-safe operations
- AlertManager is async-safe
- StructuredLogger is thread-safe

---

## Troubleshooting

### Issue: Email alerts not sending

**Check:**
1. `ALERT_EMAIL_ENABLED=true` is set
2. SMTP credentials are correct
3. Firewall allows SMTP port (587 for Gmail)
4. Gmail requires "App Password" (not account password)

### Issue: High memory usage

**Check:**
- MetricsCollector retention period (default: 24h)
- Reduce with: `init_metrics(retention_hours=12)`
- Check alert history size

### Issue: Missing trace IDs in logs

**Check:**
- ObservabilityMiddleware is added to FastAPI app
- Logging configured with `setup_structured_logging()`
- No custom logging handlers overriding the format

---

## Performance Impact

- **Metrics Collection**: ~0.1ms per request
- **Alert Checking**: Async, no blocking
- **Memory**: ~50-100KB per 1000 requests (24h retention)

---

## Next Steps

1. **Set up log aggregation** (ELK, Datadog, etc.)
2. **Configure email alerts** for critical issues
3. **Create dashboard** for observability metrics
4. **Set up uptime monitoring** for `/health` endpoint
5. **Plan load testing** with metrics baseline

---

**Documentation Updated**: November 10, 2025
**Version**: 1.0.0
