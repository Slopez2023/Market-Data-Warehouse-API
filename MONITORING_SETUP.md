# Monitoring Setup Guide

This guide covers setting up comprehensive monitoring for the Market Data API in production.

---

## Quick Setup

```bash
# Run the automated monitoring setup
bash /opt/market-data-api/monitor-setup.sh

# Follow prompts to configure cron jobs
bash /opt/market-data-api/scripts/setup-cron.sh

# View live dashboard
bash /opt/market-data-api/scripts/dashboard.sh
```

---

## Manual Monitoring

### Real-Time Health Check

```bash
# Check API health
curl http://localhost:8000/health | jq '.'

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2025-11-09T...",
#   "scheduler_running": true
# }
```

### API Metrics

```bash
# Get detailed status and metrics
curl http://localhost:8000/api/v1/status | jq '.'

# Key metrics to monitor:
# - symbols_available (should be ≥15)
# - validation_rate (should be ≥95%)
# - total_records (should be growing)
# - gap_detection_results (should be low)
# - latest_timestamp (should be recent)
```

### Historical Data Query

```bash
# Test data retrieval for a symbol
curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-11-01&end=2024-11-07" | jq '.data | length'

# Should return 5-6 candles (trading days)
```

### Database Inspection

```bash
# Connect to database
docker-compose exec timescaledb psql -U postgres -d market_data

# Check symbol status
SELECT symbol, last_updated, record_count FROM symbol_status ORDER BY last_updated DESC;

# Check for gaps
SELECT symbol, COUNT(*) as gaps FROM validation_log WHERE is_gap = true GROUP BY symbol;

# Check recent data
SELECT symbol, MAX(time) FROM market_data GROUP BY symbol ORDER BY MAX(time) DESC;
```

---

## Monitoring Checklist

### Daily Monitoring (5 minutes)

```bash
# Morning check - verify overnight backfill ran
curl http://localhost:8000/api/v1/status | jq '.latest_timestamp'

# Should be from previous trading day
```

### Weekly Monitoring (30 minutes)

```bash
# Run the automated monitoring script
~/monitor-api.sh

# Check the log
tail -100 ~/api-monitor.log

# Review weekly summary
bash /opt/market-data-api/scripts/weekly-summary.sh
```

### Monthly Review (1 hour)

1. **Data Quality**
   ```bash
   # Check validation rate trend
   tail -500 ~/api-monitor.log | grep "Validation Rate" | tail -30
   
   # Should be consistently ≥95%
   ```

2. **Database Health**
   ```bash
   # Check database size
   docker-compose exec timescaledb psql -U postgres -d market_data \
     -c "SELECT pg_size_pretty(pg_database_size('market_data')) as db_size;"
   
   # Check table compression
   SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename)) as size
   FROM pg_tables WHERE tableschema='public';
   ```

3. **Backup Verification**
   ```bash
   # List recent backups
   ls -lh /opt/market-data-api/backups/
   
   # Verify latest backup is recent (within 7 days)
   # Verify backup size >100KB (data was actually backed up)
   ```

4. **API Performance**
   ```bash
   # Test response times
   time curl http://localhost:8000/health > /dev/null
   time curl http://localhost:8000/api/v1/status > /dev/null
   
   # Should complete in <100ms and <1s respectively
   ```

---

## Automated Monitoring Setup

### 1. Install Monitoring Script

```bash
# Run setup script (creates all monitoring infrastructure)
bash /opt/market-data-api/monitor-setup.sh

# This creates:
# - ~/monitor-api.sh (main monitoring script)
# - ~/api-monitor.log (log file)
# - /opt/market-data-api/scripts/dashboard.sh
# - /opt/market-data-api/scripts/weekly-summary.sh
```

### 2. Configure Cron Jobs

```bash
# Interactive setup
bash /opt/market-data-api/scripts/setup-cron.sh

# Or manual cron setup
crontab -e

# Add these lines:

# Hourly monitoring check
0 * * * * ~/monitor-api.sh

# Weekly backup (Sunday 3 AM)
0 3 * * 0 /opt/market-data-api/backup.sh

# Weekly summary report (Friday 9 AM)
0 9 * * 5 /opt/market-data-api/scripts/weekly-summary.sh
```

### 3. View Live Dashboard

```bash
# Start live monitoring dashboard
bash /opt/market-data-api/scripts/dashboard.sh

# Shows:
# - API health status
# - Current metrics (symbols, records, validation rate)
# - System resources (memory, disk)
# - Service status
# - Refreshes every 30 seconds
```

---

## Key Metrics to Track

### API Health (Every Hour)
- ✓ API responding to health endpoint
- ✓ No recent errors in logs
- ✓ Service status is "running"

### Data Quality (Every Day)
- ✓ Validation rate ≥95%
- ✓ Latest data is recent (within 1 trading day)
- ✓ Symbol count ≥15
- ✓ Total records increasing

### System Health (Every Day)
- ✓ Disk usage <80%
- ✓ Database size <10GB (for years of data)
- ✓ CPU load <50%
- ✓ Memory usage <70%

### Backups (Every Week)
- ✓ Backup file exists
- ✓ Backup size >100KB
- ✓ Backup is recent (within 7 days)
- ✓ Restore test passes quarterly

---

## Alert Conditions

Set up alerts if:

| Condition | Threshold | Action |
|-----------|-----------|--------|
| API unreachable | 2+ consecutive checks | Restart service |
| Validation rate drops | <90% | Check logs for API errors |
| Disk usage | >90% | Archive old data or expand |
| Backfill fails | Latest data >1 day old | Check API key / rate limits |
| High memory usage | >80% | Check for queries/memory leaks |
| Database error | Any error in logs | Check database health |

---

## Troubleshooting

### API Not Responding

```bash
# Check service status
sudo systemctl status market-data-api

# View recent logs
sudo journalctl -u market-data-api -n 50

# Try restarting
sudo systemctl restart market-data-api

# Check container logs
docker-compose logs api | tail -20
```

### Backfill Not Running

```bash
# Check scheduler logs
tail -50 /opt/market-data-api/logs/api.log | grep -i "backfill\|scheduler"

# Check cron logs
sudo journalctl -u cron | grep market-data

# Manual backfill test
docker-compose exec api python backfill.py
```

### Database Issues

```bash
# Check database connectivity
docker-compose exec timescaledb psql -U postgres -d market_data -c "SELECT 1;"

# Check database size
docker-compose exec timescaledb psql -U postgres -d market_data \
  -c "SELECT pg_size_pretty(pg_database_size('market_data'));"

# Check active connections
docker-compose exec timescaledb psql -U postgres -d market_data \
  -c "SELECT count(*) FROM pg_stat_activity;"
```

### High Disk Usage

```bash
# Check backup directory size
du -sh /opt/market-data-api/backups/

# Remove old backups (keep last 4 weeks)
ls -t /opt/market-data-api/backups/ | tail -n +5 | xargs -I {} rm /opt/market-data-api/backups/{}

# Check database growth
docker-compose exec timescaledb psql -U postgres -d market_data \
  -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

---

## External Monitoring (Optional)

For advanced monitoring, can integrate with:

### Prometheus + Grafana

1. Export API metrics to Prometheus format
2. Scrape metrics at `/metrics` endpoint
3. Create Grafana dashboard

### Datadog / New Relic

1. Add monitoring agent
2. Track API response times, error rates
3. Get automatic alerts

### Slack Integration

```bash
# Modify monitoring script to send Slack notifications
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"API Health: Healthy"}' \
  YOUR_SLACK_WEBHOOK_URL
```

---

## Monthly Maintenance Checklist

- [ ] Review monitoring logs for trends
- [ ] Verify backups are recent and working
- [ ] Check database size (should be <10GB for years of data)
- [ ] Verify API response times (health <100ms, status <1s)
- [ ] Check validation rate (should be ≥95%)
- [ ] Review error logs (should be minimal)
- [ ] Test backup restore (quarterly)
- [ ] Verify cron jobs are executing
- [ ] Check system resources (disk, memory, CPU)
- [ ] Update documentation if any changes made

---

## Documentation

- **DEPLOYMENT.md** - Initial deployment steps
- **WEEK5_PLAN.md** - Week 5 implementation plan
- **QUICK_REFERENCE.md** - Common commands
- **README.md** - API usage and overview
