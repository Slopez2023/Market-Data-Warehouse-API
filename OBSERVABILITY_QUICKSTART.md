# Observability Quick Start

## TL;DR

Your API now has:
- ✅ Structured JSON logging with trace IDs
- ✅ Automatic metrics collection (request count, errors, response times)
- ✅ Alert system with email support
- ✅ Monitoring endpoints at `/api/v1/observability/`

## Check Your Observability Right Now

```bash
# System health and request metrics
curl http://localhost:8000/api/v1/observability/metrics

# Recent alerts
curl http://localhost:8000/api/v1/observability/alerts
```

## Response Examples

### Metrics Endpoint

```json
{
  "health_status": "healthy",
  "summary": {
    "total_requests": 2543,
    "error_rate_pct": 0.47,
    "avg_response_time_ms": 52.34,
    "requests_last_hour": 145
  }
}
```

### Alerts Endpoint

```json
{
  "count": 3,
  "alerts": [
    {
      "type": "high_error_rate",
      "severity": "warning",
      "title": "High Error Rate Detected",
      "message": "Error rate is 8.5%"
    }
  ]
}
```

## Enable Email Alerts (Optional)

Add to your `.env` file:

```bash
ALERT_EMAIL_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
ALERT_FROM_EMAIL=your-email@gmail.com
ALERT_FROM_PASSWORD=your-app-password
ALERT_TO_EMAILS=ops@company.com,dev@company.com
```

For Gmail:
1. Enable 2-factor authentication
2. Create an [App Password](https://myaccount.google.com/apppasswords)
3. Use the app password in `ALERT_FROM_PASSWORD`

## View Logs

Logs are now JSON-formatted. Each request gets a trace ID for correlation:

```bash
# Watch logs
docker logs -f market-data-api

# Example log output
{
  "timestamp": "2025-11-10T15:30:45.123456",
  "level": "INFO",
  "message": "GET /api/v1/historical/AAPL",
  "trace_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "extra": {
    "method": "GET",
    "status": 200,
    "duration_ms": 45.23
  }
}
```

## Key Metrics Explained

| Metric | What It Means |
|--------|---------------|
| `total_requests` | All requests since API started |
| `error_rate_pct` | Percentage of requests with errors (0-100) |
| `avg_response_time_ms` | Average time per request in milliseconds |
| `health_status` | System status: healthy, degraded, critical, idle |
| `requests_last_hour` | Traffic in the last 60 minutes |

## Alert Thresholds

Default thresholds (triggered automatically):

| Alert Type | Threshold |
|------------|-----------|
| High Error Rate | > 10% error rate |
| Data Staleness | Data older than 24 hours |
| Scheduler Failure | Scheduler stops or fails |
| API Errors | Any unhandled exception |

## Using Trace IDs

Every request automatically gets a trace ID. Use it to track requests:

```bash
# In your client code, include the trace ID header
curl -H "X-Trace-ID: my-custom-id" http://localhost:8000/api/v1/status

# The API will return it in the response header
X-Trace-ID: my-custom-id

# And include it in all logs for that request
```

## Monitoring Best Practices

### 1. Daily Check
```bash
curl http://localhost:8000/api/v1/observability/metrics | jq '.health_status'
```

### 2. Monitor Endpoint with Tools
```bash
# Uptime monitoring
monitor GET http://localhost:8000/health every 5 minutes

# Detailed health check
monitor GET http://localhost:8000/api/v1/observability/metrics every 1 minute
```

### 3. Set Up Log Aggregation
Tools like Datadog, ELK Stack, or Papertrail can ingest your JSON logs:
- They're already formatted as JSON
- Include trace IDs for correlation
- Ready for production use

### 4. Create Dashboards
With the observability endpoints, you can build dashboards showing:
- Request volume over time
- Error rates by endpoint
- Response time trends
- Alert history

## Testing Observability

```bash
# Start the API
python main.py

# In another terminal, simulate traffic
for i in {1..100}; do
  curl http://localhost:8000/api/v1/status
done

# Check metrics
curl http://localhost:8000/api/v1/observability/metrics | jq .

# Simulate an error
curl "http://localhost:8000/api/v1/historical/INVALID?start=2025-01-01&end=2025-01-02"

# Check alerts (should have new alert)
curl http://localhost:8000/api/v1/observability/alerts | jq .
```

## Next Steps

1. **Set up monitoring** for `/api/v1/observability/metrics` endpoint
2. **Configure email alerts** if you want notifications
3. **Integrate with your log system** (Datadog, ELK, Papertrail, etc.)
4. **Create dashboards** to visualize metrics over time
5. **Plan load testing** with baseline metrics

## Troubleshooting

**Q: Logs look different than before?**
A: They're now JSON-formatted for better tooling integration. Same information, better structure.

**Q: How do I aggregate logs across multiple instances?**
A: Use a log aggregation tool (Datadog, ELK, etc.) that supports JSON logs. They'll automatically parse the structure.

**Q: How long are metrics kept?**
A: 24 hours by default. Metrics are in-memory, so they reset on API restart.

**Q: What if I want persistent metrics?**
A: Export to Prometheus, InfluxDB, or other metrics systems. See `OBSERVABILITY.md` for integration patterns.

---

**Deployed**: November 10, 2025  
**Status**: ✅ Production Ready
