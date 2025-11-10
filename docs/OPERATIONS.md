# Operations & Maintenance Guide

Day-to-day operational procedures, monitoring, and maintenance tasks.

---

## Daily Operations

### Morning Health Check (2-3 min)

First thing every morning, verify system is healthy:

```bash
# Check API is responding
curl http://localhost:8000/health | jq '.'

# Check database metrics
curl http://localhost:8000/api/v1/status | jq '.database'

# Expected output:
# - status: "healthy"
# - scheduler_running: true
# - latest_data: Recent trading date
# - validation_rate_pct: >95%
```

### Check Dashboard

```bash
# Open in browser
http://localhost:8000/dashboard
```

Look for:
- ✅ Green health badge
- ✅ Scheduler running
- ✅ Validation rate >95%
- ⚠️ Any yellow/red alerts (investigate if present)
- ⚠️ Data staleness (should be recent trading day)

### Review Logs (Optional, 5 min)

```bash
# Check for errors in last hour
docker-compose logs api | grep -i error | tail -20

# Check backfill activity
docker-compose logs api | grep -i backfill | tail -10

# If errors found, investigate and escalate if needed
```

---

## Weekly Operations

### Weekly Backup Verification (5 min)

Every Monday, verify backups ran successfully:

```bash
# Check backup file was created (should be from Sunday 3 AM)
ls -lh /mnt/external-backup/market-data-backups/ | tail -5

# Expected: Most recent file should be from Sunday, <200MB

# Verify backup size is reasonable
du -h /mnt/external-backup/market-data-backups/
# Expected: Total <2GB (last 12 backups)
```

### Weekly Disk Space Check (2 min)

```bash
# Check system disk
df -h /

# Check backup drive
df -h /mnt/external-backup/

# Alert if <20% free space on either drive
```

### Weekly Log Review (5 min)

```bash
# Check for any recurring errors
docker-compose logs api | tail -1000 | grep -i error | wc -l

# If many errors, investigate
docker-compose logs api | grep -i error | head -10

# Check for rate limit warnings
docker-compose logs api | grep -i "rate limit"
```

---

## Monthly Operations

### Monthly Data Quality Spot-Check (15 min)

Compare database data against Yahoo Finance:

```bash
# Query API for a symbol
curl "http://localhost:8000/api/v1/historical/AAPL?start=2025-10-01&end=2025-10-31" | jq '.data[0:3]'

# Compare manually with Yahoo Finance (https://finance.yahoo.com)
# Pick 3-5 dates and compare prices
# Expected: Match within 0.2%

# If mismatch >1%, investigate data source
```

### Monthly Test Restore from Backup (10 min)

Critical: Verify backups are usable:

```bash
# Create temporary test database
docker exec timescaledb createdb market_data_test

# Restore from latest backup
BACKUP_FILE=$(ls -t /mnt/external-backup/market-data-backups/*.sql.gz | head -1)
docker exec -i timescaledb gunzip -c $BACKUP_FILE | \
  psql -U postgres -d market_data_test

# Verify restore succeeded
docker exec timescaledb psql -U postgres -d market_data_test -c "SELECT COUNT(*) FROM market_data;"

# Expected: Should return record count (e.g., 18000+)

# Cleanup
docker exec timescaledb dropdb market_data_test

echo "✅ Restore test passed"
```

### Monthly Gap Anomaly Review (10 min)

Review what gap detection found:

```bash
# Query gap-flagged records
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT symbol, time, close, gap_detected FROM market_data WHERE gap_detected = TRUE ORDER BY time DESC LIMIT 10;"

# Investigate any recent gaps
# - Stock splits typically show 50%+ gap
# - Market halts show unusual gaps
# - Data corruption shows random gaps

# Document any findings for future reference
```

### Monthly Database Optimization (5 min)

```bash
# Rebuild indexes (if query performance degraded)
docker exec timescaledb psql -U postgres -d market_data -c "REINDEX DATABASE market_data;" &

# Analyze query plans (if slow queries detected)
docker exec timescaledb psql -U postgres -d market_data -c \
  "ANALYZE market_data;"

# Note: REINDEX can be slow; run during off-hours if needed
```

---

## Quarterly Operations

### Quarterly Performance Review (30 min)

```bash
# Database size growth
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT pg_size_pretty(pg_database_size('market_data'));"

# Check if growth is as expected
# Expected: ~20GB for 500 stocks × 5 years

# Query performance
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;"

# If slow queries, consider optimization

# Compression ratio
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT chunk_schema, chunk_name, is_compressed, \
          pg_size_pretty(range_end - range_start) as time_range
   FROM timescaledb_information.chunks LIMIT 10;"
```

### Quarterly Symbol List Expansion (15 min)

Add new symbols to backfill:

```bash
# Edit scheduler config
nano /opt/market-data-api/src/scheduler.py

# Find BACKFILL_SYMBOLS and add new symbols
BACKFILL_SYMBOLS = [
    "AAPL", "MSFT", ..., "NEWSTOCK1", "NEWSTOCK2"
]

# Restart API
docker-compose restart api

# Verify new symbols appear in dashboard after next backfill
```

### Quarterly Docker Image Update (20 min)

Update base images if patches available:

```bash
# Pull latest base images
docker pull python:3.11-slim
docker pull timescale/timescaledb:latest-pg15

# Rebuild API image
docker-compose build --no-cache

# Test locally first, then restart
docker-compose restart api

# Verify health
curl http://localhost:8000/health
```

### Quarterly Backup Drive Rotation (15 min)

Rotate backup storage media (USB drive):

```bash
# Plug in new drive
# Mount it
sudo mount /dev/sdX1 /mnt/external-backup-new

# Verify old backups are on new drive
ls -lh /mnt/external-backup-new/market-data-backups/

# Update fstab if keeping new drive
sudo nano /etc/fstab

# Keep both drives rotating for redundancy
```

---

## Common Maintenance Tasks

### Add a New Symbol to Backfill

```bash
# 1. Edit scheduler
nano src/scheduler.py

# 2. Find BACKFILL_SYMBOLS list and add symbol:
BACKFILL_SYMBOLS = [
    "AAPL", "MSFT", "NEWSTOCK", ...  # Add here
]

# 3. Restart API
docker-compose restart api

# 4. Verify in dashboard (next backfill, or check /api/v1/symbols)
curl http://localhost:8000/api/v1/symbols | grep NEWSTOCK
```

### Change Backfill Schedule

```bash
# 1. Edit .env
nano .env

# 2. Change time:
BACKFILL_SCHEDULE_HOUR=3   # Change to 3 AM UTC instead of 2 AM
BACKFILL_SCHEDULE_MINUTE=30

# 3. Restart API
docker-compose restart api

# 4. Verify in logs next scheduled time
```

### Change Dashboard Refresh Rate

```bash
# 1. Edit dashboard script
nano dashboard/script.js

# 2. Find REFRESH_INTERVAL and change:
REFRESH_INTERVAL: 15000,  // 15 seconds instead of 10

# 3. Save and reload dashboard in browser
```

### Scale API Workers (for High Load)

```bash
# 1. Check current worker count (default 4)
grep "workers" docker-compose.yml

# 2. Edit docker-compose.yml
nano docker-compose.yml

# 3. Change workers command:
command: uvicorn main:app --host 0.0.0.0 --port 8000 --workers 8

# 4. Restart API
docker-compose restart api

# 5. Monitor performance
docker stats  # Watch CPU/memory usage
```

### Restart Services (if hung or slow)

```bash
# Restart just API
docker-compose restart api

# Restart just database
docker-compose restart timescaledb

# Restart both
docker-compose restart

# Check status
docker-compose ps
```

### View Service Status

```bash
# Using Docker Compose
docker-compose ps

# Using systemd (production)
sudo systemctl status market-data-api

# Check if service auto-starts on reboot
sudo systemctl is-enabled market-data-api

# Enable auto-start (if disabled)
sudo systemctl enable market-data-api
```

---

## Monitoring Dashboard

### Access Dashboard
```
http://localhost:8000/dashboard
```

### Metrics Explained

**Health Status** (top-left badge)
- 🟢 Green (Healthy) — API responding, scheduler running
- 🟡 Yellow (Warning) — Validation rate <90% or data stale
- 🔴 Red (Critical) — API not responding or scheduler stopped

**Database Metrics** (top row)
- Symbols available — Count of stock tickers
- Total Records — Count of OHLCV candles
- Validation Rate % — Percentage passing quality checks (goal: >95%)

**Data Freshness** (top row)
- Latest Data — Timestamp of most recent candle (should be today)

**Gaps Flagged** (top row)
- Count of candles flagged for anomalies (normal: <1%)

**Scheduler Status** (right side)
- Running — Auto-backfill is active
- Stopped — Backfill job failed or stopped

**Symbol Quality Grid** (bottom)
- Green rows — High quality data (>0.95)
- Yellow rows — Flagged anomalies (0.85-0.95)
- Red rows — Poor quality (<0.85)

---

## Alerts & Responses

### Alert: Low Validation Rate (<90%)

**What it means:**  
Many candles failing quality checks.

**Common causes:**
- Data source issue (Polygon API degradation)
- Network timeout during backfill
- New symbol with incomplete data

**Response:**
1. Check logs: `docker-compose logs api | grep -i validation`
2. Check Polygon status: https://status.polygon.io
3. Verify API key still valid
4. Test one symbol manually: `curl "https://api.polygon.io/v1/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-31?apiKey=$POLYGON_API_KEY"`
5. If resolved, no action needed (will recover next backfill)

### Alert: Data Stale (>24 Hours Old)

**What it means:**  
No backfill completed since yesterday.

**Common causes:**
- Backfill job failed
- Scheduler not running
- Database connection error

**Response:**
1. Check scheduler status: `curl http://localhost:8000/health | jq '.scheduler_running'`
2. Check logs: `docker-compose logs api | grep -i scheduler`
3. If scheduler stopped, restart API: `docker-compose restart api`
4. Monitor next backfill (should complete within 30 min)
5. If still failing, check database: `docker-compose ps timescaledb`

### Alert: Scheduler Stopped

**What it means:**  
Auto-backfill job is not running.

**Common causes:**
- API container crashed
- Scheduler exception
- Database unreachable

**Response:**
1. Check container status: `docker-compose ps`
2. Check API logs: `docker-compose logs api | tail -50`
3. Restart API: `docker-compose restart api`
4. Verify scheduler restarted: `curl http://localhost:8000/health`
5. If still failing, check database: `docker-compose logs timescaledb`

### Alert: API Not Responding

**What it means:**  
API health check failing or API container down.

**Common causes:**
- API container crashed
- Port 8000 blocked
- Database connection lost

**Response:**
1. Check container: `docker-compose ps api`
2. If down, restart: `docker-compose up -d api`
3. Check logs: `docker-compose logs api | tail -50`
4. Check port: `lsof -i :8000`
5. Verify database: `docker-compose ps timescaledb`

---

## Performance Tuning

### Check Database Query Performance

```bash
# View slowest queries
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# If any query >1000ms, investigate
# Most queries should be <100ms
```

### Monitor Real-Time Resource Usage

```bash
# Live container stats
docker stats --no-stream

# Expected for healthy system:
# API: <500MB memory, <10% CPU
# Database: <1GB memory, <20% CPU
```

### Optimize Slow Queries

```bash
# Analyze query plan
docker exec timescaledb psql -U postgres -d market_data -c \
  "EXPLAIN ANALYZE SELECT * FROM market_data WHERE symbol='AAPL' LIMIT 100;"

# Look for "Seq Scan" (bad) vs "Index Scan" (good)
# If Seq Scan, indexes may be missing or stale

# Rebuild indexes
docker exec timescaledb psql -U postgres -d market_data -c \
  "REINDEX TABLE market_data;"
```

---

## Backup & Disaster Recovery

### Manual Backup

```bash
# Run backup script
/opt/market-data-api/backup.sh

# Or manually:
docker exec timescaledb pg_dump -U postgres market_data | \
  gzip > /mnt/external-backup/market_data_$(date +%Y%m%d_%H%M%S).sql.gz
```

### List Recent Backups

```bash
ls -lh /mnt/external-backup/market-data-backups/ | tail -10
```

### Restore Specific Backup

```bash
# Stop API first
docker-compose stop api

# Restore database
docker exec -i timescaledb gunzip -c /mnt/external-backup/market-data-backups/market_data_TIMESTAMP.sql.gz | \
  psql -U postgres -d market_data

# Restart API
docker-compose start api
```

### Recovery Procedure (Complete System Failure)

```bash
# 1. Restore repository
cd /opt/market-data-api
git pull origin main

# 2. Restore .env if lost
# (Keep backup copy somewhere safe)

# 3. Stop services
docker-compose down

# 4. Restore database from backup
docker-compose up -d timescaledb
sleep 10

docker exec -i timescaledb gunzip -c /mnt/external-backup/market-data-backups/LATEST_BACKUP.sql.gz | \
  psql -U postgres -d market_data

# 5. Start API
docker-compose up -d api

# 6. Verify
curl http://localhost:8000/health

# 7. Check data
curl http://localhost:8000/api/v1/status | jq '.database'
```

---

## Useful Commands Reference

### Container Management
```bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart api

# Status
docker-compose ps

# Logs
docker-compose logs -f api
```

### Database Operations
```bash
# Connect to database
docker exec -it timescaledb psql -U postgres -d market_data

# Query record count
docker exec timescaledb psql -U postgres -d market_data -c "SELECT COUNT(*) FROM market_data;"

# Check database size
docker exec timescaledb psql -U postgres -d market_data -c "SELECT pg_size_pretty(pg_database_size('market_data'));"
```

### Monitoring
```bash
# Real-time dashboard
./monitor.sh

# Health check
curl http://localhost:8000/health

# Status
curl http://localhost:8000/api/v1/status

# Symbols list
curl http://localhost:8000/api/v1/symbols
```

### Backup/Restore
```bash
# Manual backup
./backup.sh

# View backup history
ls -lh /mnt/external-backup/market-data-backups/

# Test restore
docker exec -i timescaledb gunzip -c BACKUP.sql.gz | psql -U postgres -d market_data_test
```

### Systemd Service
```bash
# Status
sudo systemctl status market-data-api

# Start
sudo systemctl start market-data-api

# Stop
sudo systemctl stop market-data-api

# Restart
sudo systemctl restart market-data-api

# Enable on boot
sudo systemctl enable market-data-api

# View logs
sudo journalctl -u market-data-api -f
```

---

## Escalation Procedures

### When to Escalate

**Immediate Escalation Required:**
- API unresponsive for >5 min
- Database corruption detected
- Backup failures for >1 week
- Validation rate <50%

**Standard Response:**
- Check logs and system resources
- Attempt restart
- Review recent changes
- Document issue with logs
- Contact on-call if unresolved

---

## On-Call Duties

### Shift Start
1. Check dashboard for any alerts
2. Review logs from past 24 hours
3. Verify backups completed
4. Test manual endpoint query

### During Shift
1. Monitor dashboard (every few hours)
2. Respond to alerts
3. Document any issues
4. Keep runbooks updated

### Shift End
1. Final health check
2. Document any open issues
3. Leave notes for next shift
4. Verify no critical alerts

---

## Documentation Updates

Keep documentation current:

```bash
# After any configuration change
# Update .env.example if applicable
cp .env .env.example.new

# After any procedure change
# Update this file with new steps
nano OPERATIONS.md

# Commit changes
git add .
git commit -m "Docs: Update operations for [change]"
git push
```

---

## Support & Escalation

**For operational questions:**
- Check [README.md](README.md) for overview
- Check [API_ENDPOINTS.md](API_ENDPOINTS.md) for API reference
- Check [INSTALLATION.md](INSTALLATION.md) for deployment

**For emergencies:**
- Check logs: `docker-compose logs -f`
- Restart services: `docker-compose restart`
- Reach out to on-call engineer

**Best Practice:**
- Keep backups verified (monthly restore test)
- Monitor performance trends (monthly review)
- Update documentation after changes
- Test recovery procedures quarterly

---

**System is designed for minimal hands-on management. Most operations are automated.** ✅
