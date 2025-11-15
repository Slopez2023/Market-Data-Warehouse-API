# Troubleshooting Guide

Common issues and solutions for the Market Data API.

---

## Table of Contents

- [Docker & Deployment Issues](#docker--deployment-issues)
- [Database Issues](#database-issues)
- [API Issues](#api-issues)
- [Data Issues](#data-issues)
- [Performance Issues](#performance-issues)
- [Authentication Issues](#authentication-issues)
- [Monitoring & Logging](#monitoring--logging)

---

## Docker & Deployment Issues

### Docker won't start

**Symptoms**: `docker-compose up` fails or containers crash

**Solutions**:

```bash
# 1. Check logs
docker-compose logs -f

# 2. Verify Docker is running
docker ps

# 3. Check ports are available
lsof -i :8000  # Check port 8000
lsof -i :5432  # Check port 5432

# 4. Clean up and restart
docker-compose down -v
docker-compose build --no-cache
docker-compose up

# 5. Check disk space
docker system df
docker system prune  # Clean up unused resources
```

### Container exits immediately

**Symptoms**: `docker logs` shows brief output then container stops

**Solutions**:

```bash
# Check the exact error
docker-compose logs market_data_api

# Common causes:
# 1. Port already in use - change port in docker-compose.yml
# 2. Environment variables missing - check .env file
# 3. Database not ready - wait longer before API starts

# Add depends_on with condition (docker-compose v2.1+)
services:
  market_data_api:
    depends_on:
      market_data_db:
        condition: service_healthy
```

### Out of memory

**Symptoms**: Container killed with OOMKilled

**Solutions**:

```bash
# Check memory usage
docker stats market_data_api

# Set memory limits in docker-compose.yml
services:
  market_data_api:
    deploy:
      resources:
        limits:
          memory: 2G

# Or reduce cache size in .env
QUERY_CACHE_MAX_SIZE=1000
```

### Permission denied errors

**Symptoms**: `permission denied` when accessing files or ports

**Solutions**:

```bash
# Running Docker without sudo (Linux)
sudo usermod -aG docker $USER
newgrp docker

# Port below 1024 requires root (Linux)
# Change to port >= 1024 or use sudo
API_PORT=8000  # Use ports >= 1024

# Docker volume permission issues
docker exec -u root market_data_api chown -R app:app /app
```

---

## Database Issues

### Database connection refused

**Symptoms**: `psycopg2.OperationalError: could not connect to server`

**Solutions**:

```bash
# 1. Check database is running
docker-compose ps market_data_db

# 2. Check database logs
docker-compose logs market_data_db

# 3. Verify environment variables
echo $DB_HOST $DB_PORT $DB_USER $DB_PASSWORD

# 4. Test connection manually
docker exec market_data_db psql -U postgres -h localhost -c "SELECT 1;"

# 5. Check firewall
# Allow port 5432 from Docker bridge network
```

### Database not initializing

**Symptoms**: API starts but database is empty

**Solutions**:

```bash
# 1. Check schema was created
docker exec market_data_db psql -U postgres -d market_data -c "\dt"

# 2. Run migrations manually
docker-compose exec market_data_api python -c "
from src.services.migration_service import init_migration_service
import asyncio
migration_service = init_migration_service('postgresql://...')
asyncio.run(migration_service.run_migrations())
"

# 3. Check migration logs
docker-compose logs market_data_api | grep -i migration
```

### Database disk full

**Symptoms**: `ERROR: could not extend relation` or write errors

**Solutions**:

```bash
# Check disk usage
docker exec market_data_db df -h

# Check PostgreSQL object sizes
docker exec market_data_db psql -U postgres -d market_data -c "
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) 
FROM pg_tables 
ORDER BY pg_total_relation_size DESC;"

# Cleanup old data (if applicable)
docker exec market_data_db psql -U postgres -d market_data -c "
DELETE FROM ohlcv WHERE timestamp < NOW() - INTERVAL '2 years';
VACUUM ANALYZE;"

# Increase volume size in docker-compose.yml
# Or migrate to larger external database
```

### Slow queries

**Symptoms**: API responses timeout or are very slow

**Solutions**:

```bash
# Check slow queries
docker exec market_data_db psql -U postgres -d market_data -c "
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
SELECT query, calls, mean_time, max_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;"

# Check missing indexes
docker exec market_data_db psql -U postgres -d market_data -c "
SELECT * FROM pg_stat_user_indexes 
WHERE idx_scan = 0;"

# Add indexes if needed
docker exec market_data_db psql -U postgres -d market_data -c "
CREATE INDEX idx_ohlcv_symbol_timeframe ON ohlcv(symbol, timeframe, timestamp);
ANALYZE ohlcv;"

# Check table statistics are up-to-date
docker exec market_data_db psql -U postgres -d market_data -c "ANALYZE;"
```

### Connection pool exhausted

**Symptoms**: `too many connections` errors

**Solutions**:

```bash
# Check active connections
docker exec market_data_db psql -U postgres -d market_data -c "SELECT count(*) FROM pg_stat_activity;"

# View connection consumers
docker exec market_data_db psql -U postgres -d market_data -c "
SELECT usename, count(*) FROM pg_stat_activity GROUP BY usename;"

# Increase pool size
DB_POOL_SIZE=20  # in .env (default is 20)

# Restart API to apply
docker-compose restart market_data_api

# Kill long-running connections (if needed)
docker exec market_data_db psql -U postgres -d market_data -c "
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' AND query_start < NOW() - INTERVAL '1 hour';"
```

---

## API Issues

### API not responding (503 Service Unavailable)

**Symptoms**: `curl http://localhost:8000/` returns error

**Solutions**:

```bash
# 1. Check if container is running
docker-compose ps market_data_api

# 2. Check logs
docker-compose logs -f market_data_api

# 3. Check health endpoint
curl http://localhost:8000/health

# 4. Check port binding
docker port market_data_api

# 5. Restart service
docker-compose restart market_data_api
```

### 404 Not Found on valid endpoints

**Symptoms**: `GET /api/v1/historical/AAPL` returns 404

**Solutions**:

```bash
# 1. Verify endpoint exists
curl http://localhost:8000/docs  # Check Swagger UI

# 2. Check for typos
# /api/v1/historical vs /api/v1/Historical (case sensitive)

# 3. Verify API version
curl http://localhost:8000/api/v1/status

# 4. Check symbol exists
curl http://localhost:8000/api/v1/symbols

# 5. Restart API
docker-compose restart market_data_api
```

### 400 Bad Request

**Symptoms**: Request returns 400 with error message

**Solutions**:

```bash
# Check request format
# Common issues:
# - Missing required query parameters: ?start=YYYY-MM-DD&end=YYYY-MM-DD
# - Invalid date format: Must be YYYY-MM-DD
# - Invalid timeframe: Must be one of 5m, 15m, 30m, 1h, 4h, 1d, 1w
# - Invalid JSON in POST body

# Correct example:
curl "http://localhost:8000/api/v1/historical/AAPL?timeframe=1d&start=2024-01-01&end=2024-12-31"

# Check request with verbose output
curl -v "http://localhost:8000/api/v1/historical/AAPL?timeframe=1d&start=2024-01-01&end=2024-12-31"
```

### 500 Internal Server Error

**Symptoms**: API returns 500 error

**Solutions**:

```bash
# 1. Check logs for error details
docker-compose logs market_data_api | tail -50

# 2. Check specific error
curl -v http://localhost:8000/api/v1/status

# 3. Check database connection
curl http://localhost:8000/api/v1/status | jq '.database'

# 4. Check for recent code changes
git log --oneline -5

# 5. Rollback if needed
git revert HEAD
docker-compose build
docker-compose up

# 6. Check Polygon API key
# Error about invalid API key → verify POLYGON_API_KEY in .env

# 7. Restart cleanly
docker-compose down
docker-compose up --build
```

### Timeout errors

**Symptoms**: Requests timeout or take 30+ seconds

**Solutions**:

```bash
# 1. Check database response time
curl http://localhost:8000/api/v1/performance/queries

# 2. Check cache performance
curl http://localhost:8000/api/v1/performance/cache

# 3. Identify slow queries
docker-compose logs market_data_api | grep "duration_ms"

# 4. Increase timeout (in client code)
# httpx.Client(timeout=60.0)

# 5. Optimize query (see Performance Issues section)
```

---

## Data Issues

### No data returned for a symbol

**Symptoms**: Query returns empty results

**Solutions**:

```bash
# 1. Check symbol is tracked
curl http://localhost:8000/api/v1/symbols/detailed | jq '.symbols[] | select(.symbol=="AAPL")'

# 2. Check date range
# Data might not exist for requested dates - try wider range
curl "http://localhost:8000/api/v1/historical/AAPL?start=2020-01-01&end=2024-12-31"

# 3. Check timeframe is configured
curl http://localhost:8000/api/v1/symbols/detailed | jq '.symbols[] | select(.symbol=="AAPL") | .timeframes'

# 4. Check data in database
docker exec market_data_db psql -U postgres -d market_data -c "
SELECT COUNT(*) FROM ohlcv WHERE symbol = 'AAPL' AND timeframe = '1d';"

# 5. Check backfill status
curl http://localhost:8000/api/v1/metrics | jq '.last_backfill'

# 6. Manually trigger backfill
# Edit scheduler to run immediately
docker-compose exec market_data_api python -c "
from src.clients.polygon_client import PolygonClient
client = PolygonClient('<API_KEY>')
# Manually call backfill
"
```

### Data quality is low

**Symptoms**: quality_score is consistently low (<0.85)

**Solutions**:

```bash
# 1. Check quality distribution
docker exec market_data_db psql -U postgres -d market_data -c "
SELECT symbol, AVG(quality_score) as avg_quality, COUNT(*) 
FROM ohlcv 
GROUP BY symbol 
ORDER BY avg_quality;"

# 2. Investigate validation issues
# Check validation rules in src/services/data_validation.py

# 3. Check Polygon data quality
# May be issue with source data - verify with Polygon.io

# 4. Adjust quality thresholds if needed
# For accepted lower quality: ?min_quality=0.75
curl "http://localhost:8000/api/v1/historical/AAPL?min_quality=0.75"
```

### Data gaps detected

**Symptoms**: Data is missing for certain dates/times

**Solutions**:

```bash
# 1. Check for gaps in database
docker exec market_data_db psql -U postgres -d market_data -c "
SELECT symbol, timeframe, COUNT(*) as count, 
  MAX(timestamp) - MIN(timestamp) as date_range
FROM ohlcv 
WHERE symbol = 'AAPL' AND timeframe = '1d'
GROUP BY symbol, timeframe;"

# 2. Identify gap locations
docker exec market_data_db psql -U postgres -d market_data -c "
SELECT timestamp, 
  LEAD(timestamp) OVER (ORDER BY timestamp) - timestamp as gap
FROM ohlcv 
WHERE symbol = 'AAPL' AND timeframe = '1d'
HAVING LEAD(timestamp) OVER (ORDER BY timestamp) - timestamp > INTERVAL '1 day';"

# 3. Trigger backfill for missing dates
# Update backfill_history to reprocess those dates
# Or manually call backfill endpoint

# 4. Check Polygon API for data availability
# May be legitimate gaps (weekends, market closures)
```

### Stale data

**Symptoms**: Last data point is days old

**Solutions**:

```bash
# 1. Check backfill scheduler status
curl http://localhost:8000/api/v1/metrics | jq '.scheduler'

# 2. Check last backfill time
curl http://localhost:8000/api/v1/metrics | jq '.last_backfill'

# 3. Check backfill history
docker exec market_data_db psql -U postgres -d market_data -c "
SELECT * FROM backfill_history ORDER BY start_time DESC LIMIT 5;"

# 4. Check for backfill errors
docker-compose logs market_data_api | grep -i backfill

# 5. Verify Polygon API key
# Invalid key → no data will be fetched

# 6. Manually trigger backfill
# Call backfill endpoint or restart scheduler
docker-compose restart market_data_api

# 7. Check scheduler configuration
echo "BACKFILL_SCHEDULE_HOUR=$BACKFILL_SCHEDULE_HOUR"
echo "BACKFILL_SCHEDULE_MINUTE=$BACKFILL_SCHEDULE_MINUTE"
```

---

## Performance Issues

### Slow API responses

**Symptoms**: API responses take >1 second

**Solutions**:

```bash
# 1. Check cache hit rate
curl http://localhost:8000/api/v1/performance/cache | jq '.hit_rate'

# 2. Check if query uses cache
curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-01-01&end=2024-12-31" -v
# Look for: X-Cache-Hit header

# 3. Widen date range query slowly
# Narrow ranges may not benefit from cache

# 4. Check database performance
curl http://localhost:8000/api/v1/performance/summary

# 5. Reduce result size
# Filter by quality: &min_quality=0.9
# Shorter date range

# 6. Scale up resources
# Increase API_WORKERS
# Increase database connections
# Add more RAM
```

### High CPU usage

**Symptoms**: CPU is at 100% constantly

**Solutions**:

```bash
# 1. Check what's consuming CPU
docker top market_data_api

# 2. Check for runaway processes
docker-compose logs market_data_api | head -20

# 3. Identify bottleneck
curl http://localhost:8000/api/v1/performance/summary

# 4. Reduce concurrent requests
# Implement rate limiting on client side

# 5. Check for infinite loops in code
git log --oneline -5

# 6. Increase resources
API_WORKERS=2  # Reduce to avoid overload
```

### High memory usage

**Symptoms**: Docker container using >2GB RAM

**Solutions**:

```bash
# 1. Check memory details
docker stats market_data_api

# 2. Reduce cache size
QUERY_CACHE_MAX_SIZE=500  # Default 1000

# 3. Reduce metrics retention
# Edit init_metrics() retention_hours parameter

# 4. Check for memory leaks
# Monitor over time
watch -n 5 'docker stats market_data_api'

# 5. Reduce data retention
# Archive old OHLCV records to separate table
docker exec market_data_db psql -U postgres -d market_data -c "
CREATE TABLE ohlcv_archive AS 
SELECT * FROM ohlcv WHERE timestamp < NOW() - INTERVAL '1 year';
DELETE FROM ohlcv WHERE timestamp < NOW() - INTERVAL '1 year';"
```

### Network latency

**Symptoms**: External API calls are slow

**Solutions**:

```bash
# 1. Check Polygon API status
curl https://api.polygon.io/v1/status

# 2. Test connection
ping polygon.io
curl -w "@curl-format.txt" https://api.polygon.io/

# 3. Check DNS resolution
nslookup polygon.io

# 4. Test from container
docker-compose exec market_data_api ping polygon.io

# 5. Add retry logic (already implemented)
# Check backoff configuration
```

---

## Authentication Issues

### API key authentication failing

**Symptoms**: `401 Unauthorized` for admin endpoints

**Solutions**:

```bash
# 1. Verify X-API-Key header is set
curl -H "X-API-Key: wrong-key" http://localhost:8000/api/v1/admin/symbols

# 2. Check API key exists
# List all keys (need valid key)
curl http://localhost:8000/api/v1/admin/api-keys \
  -H "X-API-Key: <valid-key>"

# 3. Check key format (UUID)
# Should be 36 characters with hyphens

# 4. Check key is active
# (Look for 'active' or 'revoked' field in key info)

# 5. Create new key if needed
curl -X POST http://localhost:8000/api/v1/admin/api-keys \
  -H "X-API-Key: <admin-key>" \
  -d '{"name":"test-key"}'

# 6. Check logs for auth errors
docker-compose logs market_data_api | grep -i auth
```

### Public endpoints also requiring auth

**Symptoms**: `/api/v1/symbols` requires authentication

**Solutions**:

```bash
# 1. This is expected behavior
# Only /api/v1/admin/* endpoints require auth
# Public endpoints don't need X-API-Key

# 2. Try without header
curl http://localhost:8000/api/v1/symbols

# 3. If still fails, check middleware
# Review src/middleware/auth_middleware.py
```

---

## Monitoring & Logging

### Can't see logs

**Symptoms**: `docker-compose logs` is empty or not working

**Solutions**:

```bash
# 1. Check logs with different options
docker-compose logs -f market_data_api  # Follow logs
docker-compose logs --tail=50 market_data_api  # Last 50 lines
docker-compose logs market_data_api 2>&1  # Include stderr

# 2. Direct Docker logs
docker logs market_data_api

# 3. Check container is running
docker-compose ps

# 4. Change log level
LOG_LEVEL=DEBUG  # More verbose logs
docker-compose restart market_data_api

# 5. Check /var/log (if running directly, not Docker)
tail -f /var/log/market_data_api.log
```

### Metrics endpoint returns nothing

**Symptoms**: `/api/v1/metrics` returns empty or invalid data

**Solutions**:

```bash
# 1. Check endpoint is working
curl http://localhost:8000/api/v1/metrics

# 2. Check metrics were initialized
# Happens in main.py startup

# 3. Make some requests first
# Metrics only show after activity
curl http://localhost:8000/api/v1/symbols  # Generate metrics
curl http://localhost:8000/api/v1/metrics

# 4. Check logs for metric errors
docker-compose logs market_data_api | grep -i metric
```

### Alert notifications not working

**Symptoms**: Alerts aren't being sent

**Solutions**:

```bash
# 1. Check alerts are enabled
echo $ALERT_EMAIL_ENABLED
echo $SMTP_SERVER

# 2. Check email config
# ALERT_FROM_EMAIL must be valid
# ALERT_FROM_PASSWORD must be correct
# ALERT_TO_EMAILS must be valid

# 3. Test email sending manually
docker-compose exec market_data_api python -c "
import smtplib
try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('your-email', 'your-password')
    print('Email config valid')
except Exception as e:
    print(f'Email config error: {e}')
"

# 4. Check for alert conditions
# Alerts only trigger when thresholds are exceeded

# 5. View alert history
curl http://localhost:8000/api/v1/observability/alerts | jq '.recent_alerts'
```

---

## Getting More Help

1. **Check Logs**: `docker-compose logs -f market_data_api`
2. **Review Status**: `curl http://localhost:8000/api/v1/status`
3. **Check FAQ**: [Frequently Asked Questions](/docs/reference/FAQ.md)
4. **Review Docs**: [Complete Documentation Index](/INDEX.md)
5. **Check Architecture**: [Architecture Overview](/docs/development/ARCHITECTURE.md)

---

## Reporting Issues

When reporting issues, include:
- Docker version: `docker --version`
- Output of: `docker-compose ps`
- Recent logs: `docker-compose logs -f --tail=100`
- Configuration (sanitized): `.env` values
- Steps to reproduce
- Expected vs actual behavior
