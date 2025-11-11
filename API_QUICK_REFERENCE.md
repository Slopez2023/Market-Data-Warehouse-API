# Market Data API - Quick Reference Guide

## Quick Start

### Running the Docker Stack
```bash
docker-compose up -d
```

### Checking Container Status
```bash
docker-compose ps
docker logs market_data_api
docker logs market_data_postgres
```

### Testing All APIs
```bash
python api_test_suite.py
```

---

## API Endpoints Overview

### Health & Status (No Auth Required)
```
GET  /                           → Root info
GET  /health                     → Health check
GET  /api/v1/status             → Detailed system status
GET  /api/v1/metrics            → Scheduler & backfill metrics
```

### Data Retrieval (No Auth Required)
```
GET  /api/v1/symbols                                          → List available symbols
GET  /api/v1/historical/{symbol}?start=YYYY-MM-DD&end=YYYY-MM-DD  → Historical OHLCV data

Optional Parameters:
  - validated_only=true/false    → Filter to validated records only (default: true)
  - min_quality=0.0-1.0          → Minimum quality score filter (default: 0.85)
```

### Observability (No Auth Required)
```
GET  /api/v1/observability/metrics                 → Request/error metrics
GET  /api/v1/observability/alerts?limit=100       → Recent alerts
```

### Performance Monitoring (No Auth Required)
```
GET  /api/v1/performance/cache                     → Cache statistics
GET  /api/v1/performance/queries?query_type=      → Query performance
GET  /api/v1/performance/summary                   → Overall performance
```

### Admin Endpoints (X-API-Key Header Required)
```
GET    /api/v1/admin/symbols                      → List tracked symbols
POST   /api/v1/admin/symbols                      → Add new symbol
GET    /api/v1/admin/symbols/{symbol}             → Get symbol info
PUT    /api/v1/admin/symbols/{symbol}?active=    → Update symbol status
DELETE /api/v1/admin/symbols/{symbol}             → Deactivate symbol

GET    /api/v1/admin/api-keys                     → List API keys
POST   /api/v1/admin/api-keys                     → Create new key
GET    /api/v1/admin/api-keys/{key_id}/audit      → Get audit log
PUT    /api/v1/admin/api-keys/{key_id}            → Update key status
DELETE /api/v1/admin/api-keys/{key_id}            → Delete key
```

---

## Example Requests

### Get Current Status
```bash
curl http://localhost:8000/api/v1/status | python -m json.tool
```

### Fetch Historical Data
```bash
curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-01-01&end=2024-01-31" \
  | python -m json.tool
```

### Get Validated Data Only
```bash
curl "http://localhost:8000/api/v1/historical/MSFT?start=2024-01-01&end=2024-01-31&validated_only=true" \
  | python -m json.tool
```

### Filter by Quality Score
```bash
curl "http://localhost:8000/api/v1/historical/GOOGL?start=2024-01-01&end=2024-01-31&min_quality=0.95" \
  | python -m json.tool
```

### Get Observability Metrics
```bash
curl http://localhost:8000/api/v1/observability/metrics | python -m json.tool
```

### Get Recent Alerts
```bash
curl "http://localhost:8000/api/v1/observability/alerts?limit=50" | python -m json.tool
```

### Check Cache Performance
```bash
curl http://localhost:8000/api/v1/performance/cache | python -m json.tool
```

---

## Debugging

### View API Logs
```bash
docker logs -f market_data_api
```

### View Database Logs
```bash
docker logs -f market_data_postgres
```

### Access Database Shell
```bash
docker exec -it market_data_postgres psql -U market_user -d market_data
```

### Check Database Records
```bash
docker exec market_data_postgres psql -U market_user -d market_data \
  -c "SELECT COUNT(*) as total FROM market_data;"
```

### Check Tracked Symbols
```bash
docker exec market_data_postgres psql -U market_user -d market_data \
  -c "SELECT symbol, COUNT(*) FROM market_data GROUP BY symbol ORDER BY count DESC LIMIT 20;"
```

### Monitor API Health
```bash
while true; do
  curl -s http://localhost:8000/health | python -m json.tool
  sleep 5
done
```

---

## Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad Request (invalid parameters) |
| 401 | Unauthorized (missing/invalid API key) |
| 404 | Not Found (symbol has no data) |
| 422 | Unprocessable Entity (validation error) |
| 500 | Server Error |

---

## Common Issues & Solutions

### Issue: "Symbol not found (404)"
**Solution:** The symbol either doesn't exist in the database or has no data for the requested date range. Check available symbols with:
```bash
curl http://localhost:8000/api/v1/symbols | python -m json.tool
```

### Issue: "No data found for date range"
**Solution:** Try a broader date range. Data is only available for trading days. Check latest data:
```bash
curl http://localhost:8000/api/v1/status | python -m json.tool
```

### Issue: "Invalid date format"
**Solution:** Use YYYY-MM-DD format for start/end parameters:
```bash
# Wrong: /api/v1/historical/AAPL?start=01/01/2024&end=12/31/2024
# Correct:
curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-01-01&end=2024-12-31"
```

### Issue: "Admin endpoint returns 401"
**Solution:** Add valid X-API-Key header (or create one via admin endpoint):
```bash
curl -H "X-API-Key: your-api-key-here" \
  http://localhost:8000/api/v1/admin/symbols
```

### Issue: "Connection refused"
**Solution:** Ensure containers are running:
```bash
docker-compose ps
docker-compose restart
```

---

## Performance Tips

1. **Use date ranges wisely:** Smaller ranges = faster queries
2. **Enable caching:** API automatically caches with 5-minute TTL
3. **Use validated_only filter:** Reduces data scanning
4. **Batch requests:** Multiple requests are OK, but consider rate limits
5. **Monitor metrics:** Check `/api/v1/observability/metrics` for performance insights

---

## Container Information

### Port Mappings
- **API:** http://localhost:8000
- **Dashboard:** http://localhost:3001
- **Database:** localhost:5432

### Credentials (from .env)
```
POSTGRES_USER: postgres
POSTGRES_DB: market_data
DB_USER: market_user
```

### Useful Commands
```bash
# Rebuild containers
docker-compose down && docker-compose up -d

# View all logs
docker-compose logs -f

# Stop all containers
docker-compose down

# Remove volumes (WARNING: deletes data)
docker-compose down -v

# Run test suite
python api_test_suite.py
```

---

## API Response Format

All successful responses are JSON with this structure:
```json
{
  "field1": "value1",
  "field2": "value2",
  "timestamp": "2025-11-11T15:00:00Z"
}
```

Error responses:
```json
{
  "detail": "Error message explaining what went wrong"
}
```

---

## Rate Limiting

- **No explicit rate limits** configured in API
- **Backfill scheduler:** Runs daily at 02:00 UTC
- **Cache TTL:** 5 minutes (300 seconds)
- **Database connections:** 4 workers handling concurrent requests

---

## Support & Documentation

- **API Docs:** http://localhost:8000/docs (Swagger UI)
- **OpenAPI Schema:** http://localhost:8000/openapi.json
- **Dashboard:** http://localhost:3001
- **Debug Report:** See DOCKER_DEBUG_REPORT.md

---

**Last Updated:** 2025-11-11
**Version:** 1.0.0
**Status:** Production Ready ✓
