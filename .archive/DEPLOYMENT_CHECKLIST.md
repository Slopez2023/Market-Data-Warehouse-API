# Market Data API - Proxmox Deployment Checklist

**Target:** Deploy to OptiPlex 3060 running Proxmox Debian 12  
**Timeline:** Week 3-4 (Early December 2025)

---

## Pre-Deployment (1-2 hours)

### 1. Proxmox VM Preparation
- [ ] Proxmox VM created (Debian 12)
- [ ] Network connectivity verified (can ping gateway)
- [ ] External USB backup drive available and formatted
- [ ] Sufficient disk space confirmed (`df -h /` shows > 100GB free)
- [ ] SSH access working (`ssh user@proxmox-vm`)

### 2. Update System Packages
```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```
- [ ] System updated and restarted
- [ ] No broken dependencies

### 3. Install Docker & Dependencies
```bash
sudo apt install -y docker.io docker-compose git curl postgresql-client
sudo usermod -aG docker $USER
```
- [ ] Docker version: `docker --version` (expected: ≥ 24.0)
- [ ] Docker Compose version: `docker-compose --version` (expected: ≥ 2.0)
- [ ] Docker daemon running: `docker ps` (no errors)
- [ ] User added to docker group (no `sudo` required)

---

## Application Deployment (1-2 hours)

### 4. Clone & Setup Project
```bash
cd /opt
sudo git clone <YOUR_REPO_URL> market-data-api
sudo chown -R $USER:$USER market-data-api
cd market-data-api
```
- [ ] Repository cloned to `/opt/market-data-api`
- [ ] Ownership set to unprivileged user
- [ ] All files readable and scripts executable

### 5. Configure Environment
```bash
cp .env.example .env
nano .env  # Edit with your Polygon API key and database password
```

**Required .env variables:**
```
POLYGON_API_KEY=<your_key>
DB_PASSWORD=<strong_password>
DATABASE_URL=postgresql://postgres:<password>@timescaledb:5432/market_data
LOG_LEVEL=INFO
```

- [ ] `.env` file created with real values
- [ ] POLYGON_API_KEY set (not placeholder)
- [ ] DB_PASSWORD is strong (≥12 characters)
- [ ] `.env` file permissions: `chmod 600 .env` (readable only by owner)

### 6. Build Docker Image
```bash
cd /opt/market-data-api
docker-compose build
```
- [ ] Build completed without errors
- [ ] Image size reasonable (~500MB)
- [ ] Build logs show successful pip install

### 7. Start Services
```bash
docker-compose up -d
```
- [ ] Both containers started: `docker-compose ps` shows 2 running
- [ ] Database initialized (TimescaleDB shows "Up")
- [ ] API started (fastapi shows "Up")

### 8. Verify Initial Connectivity
```bash
# Wait 10 seconds for services to be ready
sleep 10

# Test database connection
curl http://localhost:8000/health | jq '.'

# Expected response:
# {
#   "status": "healthy",
#   "timestamp": "2025-12-XX...",
#   "scheduler_running": true
# }
```

- [ ] Health endpoint responds with `"status": "healthy"`
- [ ] Scheduler is running (`"scheduler_running": true`)
- [ ] API logs show successful startup (no errors)

---

## Systemd Integration (30 minutes)

### 9. Install Systemd Service
```bash
sudo cp /opt/market-data-api/market-data-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable market-data-api
sudo systemctl start market-data-api
```

- [ ] Service file copied to `/etc/systemd/system/`
- [ ] Daemon reloaded: `sudo systemctl daemon-reload` (no errors)
- [ ] Service enabled: `sudo systemctl is-enabled market-data-api` (returns "enabled")
- [ ] Service started: `sudo systemctl status market-data-api` (shows "active (exited)")

### 10. Test Auto-Start on Reboot
```bash
# Stop the service
sudo systemctl stop market-data-api

# Verify containers stopped
docker-compose ps  # Should show nothing or "Exited"

# Start the service
sudo systemctl start market-data-api

# Verify containers restarted
docker-compose ps  # Should show 2 "Up"
```

- [ ] Service stops containers properly
- [ ] Service starts containers properly
- [ ] Services come up in correct order (DB before API)
- [ ] API is healthy after service restart: `curl http://localhost:8000/health`

---

## Backup Setup (30 minutes)

### 11. Mount External Backup Drive
```bash
# Identify the drive
lsblk

# Mount it
sudo mount /dev/sdb1 /mnt/external-backup

# Verify
ls -la /mnt/external-backup
```

- [ ] External drive identified
- [ ] Drive mounted at `/mnt/external-backup`
- [ ] Directory is readable and writable
- [ ] At least 50GB free space on backup drive

### 12. Make Mount Persistent
```bash
# Get UUID
sudo blkid | grep sdb1

# Edit fstab
sudo nano /etc/fstab

# Add line:
# UUID=XXXX /mnt/external-backup ext4 defaults,nofail 0 2

# Test persistence
sudo umount /mnt/external-backup
sudo mount -a
ls -la /mnt/external-backup
```

- [ ] Drive UUID identified
- [ ] fstab entry added
- [ ] Mount persists after `mount -a`
- [ ] Survives test reboot

### 13. Setup Backup Script
```bash
# Create backup directory
mkdir -p /mnt/external-backup/market-data-backups

# Make backup script executable
chmod +x /opt/market-data-api/backup.sh

# Test manual backup
/opt/market-data-api/backup.sh

# Verify backup created
ls -lh /mnt/external-backup/market-data-backups/
```

- [ ] Backup directory created
- [ ] Manual backup completes without errors
- [ ] Backup file created (size > 10MB indicates real data)
- [ ] Backup file is valid: `gzip -t /path/to/backup.sql.gz` (no errors)

### 14. Create Cron Job
```bash
# Edit crontab
crontab -e

# Add line (Sunday 3 AM):
0 3 * * 0 /opt/market-data-api/backup.sh

# Verify
crontab -l
```

- [ ] Cron entry added for Sunday 3 AM
- [ ] Crontab shows the new entry
- [ ] `/var/log/market-data-api-backup.log` exists after next scheduled time

---

## Production Data Load (1-2 hours)

### 15. Monitor Initial Backfill
The scheduler automatically starts backfilling at the next 2 AM UTC window. Monitor progress:

```bash
# Watch scheduler activity
docker-compose logs -f api | grep -i backfill

# Or use the monitoring script
./monitor.sh
```

- [ ] Scheduler logs show backfill starting
- [ ] First backfill completes without errors
- [ ] Database begins storing records

### 16. Verify Data Quality
```bash
# Check status endpoint
curl http://localhost:8000/api/v1/status | jq '.database'

# Expected:
# {
#   "symbols_available": 15,
#   "latest_data": "2025-12-XX",
#   "total_records": 15000,
#   "validation_rate_pct": 97.5
# }
```

- [ ] `symbols_available` > 0 (data loaded)
- [ ] `validation_rate_pct` ≥ 95%
- [ ] `latest_data` is today or yesterday (recent)
- [ ] `total_records` > 1000

### 17. Spot-Check Sample Data
```bash
# Query recent AAPL data
curl "http://localhost:8000/api/v1/historical/AAPL?start=2025-11-01&end=2025-12-01" | jq '.data[0:3]'

# Verify structure:
# - symbol, time, open, high, low, close, volume
# - quality_score > 0.85
# - validated = true
```

- [ ] API returns valid OHLCV data
- [ ] Prices are reasonable (within 10% of spot)
- [ ] Volume is non-zero and reasonable
- [ ] Quality scores are high (≥ 0.85)

---

## Monitoring & Alerting (Optional)

### 18. Setup Monitoring (Optional)
```bash
# Make monitor script executable
chmod +x /opt/market-data-api/monitor.sh

# Run monitoring dashboard
./monitor.sh
```

- [ ] Monitor script runs without errors
- [ ] Shows container status, API health, database metrics
- [ ] Displays scheduler status and next backfill time

### 19. Create Daily Health Check Cron (Optional)
```bash
# Create health check script
cat > /opt/market-data-api/health-check.sh << 'EOF'
#!/bin/bash
HEALTH=$(curl -s http://localhost:8000/health | jq -r '.status')
if [ "$HEALTH" != "healthy" ]; then
    echo "ALERT: Market Data API is not healthy!" | mail -s "API Health Alert" admin@example.com
fi
EOF

chmod +x /opt/market-data-api/health-check.sh

# Add to crontab (every 6 hours)
crontab -e
# 0 */6 * * * /opt/market-data-api/health-check.sh
```

- [ ] Health check script created and executable
- [ ] Cron entry added
- [ ] Test alert mechanism

---

## Post-Deployment Validation

### 20. Full System Test
```bash
# 1. Test service restart
sudo systemctl restart market-data-api
sleep 10
curl http://localhost:8000/health | jq '.status'  # Should be "healthy"

# 2. Check database size
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT pg_size_pretty(pg_database_size('market_data'))"

# 3. Verify backup
/opt/market-data-api/backup.sh
ls -lh /mnt/external-backup/market-data-backups/ | tail -1

# 4. Test restore (to temporary database)
docker exec timescaledb createdb market_data_restore
docker exec timescaledb psql -d market_data_restore -U postgres < \
  /mnt/external-backup/market-data-backups/latest_backup.sql.gz
docker exec timescaledb psql -d market_data_restore -U postgres -c "SELECT COUNT(*) FROM market_data"
docker exec timescaledb dropdb market_data_restore
```

- [ ] Service restart successful
- [ ] Database size is growing (> 100MB expected)
- [ ] Backup completes successfully
- [ ] Backup file size is reasonable (> 50MB)
- [ ] Restore creates valid database (row count > 0)

### 21. Document System Configuration
Create `/opt/market-data-api/DEPLOYMENT_INFO.txt`:
```
Market Data API - Deployment Summary
====================================

Deployed: [DATE]
Server: OptiPlex 3060 / Proxmox
OS: Debian 12

API Location: http://localhost:8000
Documentation: http://localhost:8000/docs

Backup Location: /mnt/external-backup/market-data-backups
Backup Schedule: Sunday 3 AM (automated cron job)
Backup Retention: Last 12 weekly backups

Database: TimescaleDB (PostgreSQL 15)
Data Volume: /var/lib/docker/volumes/<name>/_data

Systemd Service: market-data-api
Status: systemctl status market-data-api
Logs: docker-compose logs

Scheduled Backfill: 2 AM UTC daily (via APScheduler)
Symbols: [List your symbols from src/scheduler.py]

Contact: [Your contact info]
```

- [ ] Deployment info documented
- [ ] Stored in project directory for reference

---

## Success Criteria

✅ All containers running and healthy  
✅ API responding on port 8000  
✅ Database connected and storing records  
✅ Scheduler running and backfilling daily  
✅ Backups automated and tested  
✅ Service auto-starts on Proxmox reboot  
✅ Data validation rate > 95%  
✅ Sample data spot-checked against Yahoo Finance  

---

## Common Issues & Solutions

### Issue: Docker daemon not running
```bash
# Solution: Start Docker
sudo systemctl start docker
sudo systemctl enable docker
```

### Issue: Port 5432 already in use
```bash
# Solution: Find and stop the conflicting service
sudo lsof -i :5432
sudo kill -9 <PID>
# Or change docker-compose.yml port mapping
```

### Issue: API not responding
```bash
# Solution: Check logs
docker-compose logs api
# Common cause: Database not ready, wait 20 seconds
sleep 20
curl http://localhost:8000/health
```

### Issue: Backfill not running
```bash
# Solution: Check scheduler logs
docker-compose logs api | grep -i scheduler
# Verify POLYGON_API_KEY in .env
```

### Issue: Backup script fails
```bash
# Solution: Check directory permissions
ls -la /mnt/external-backup/
chmod 755 /mnt/external-backup/market-data-backups
# Or check if database container is running
docker-compose ps timescaledb
```

---

## Next Steps (Week 4+)

1. Monitor first 7 days of automated backfills
2. Spot-check weekly data against Yahoo Finance
3. Expand symbol list in `src/scheduler.py` if needed
4. Setup optional monitoring dashboard
5. Plan Phase 2 features (crypto, indicators, etc.)

---

**Estimated Total Time:** 4-5 hours (can be done in one session)

**Success Indicator:** System runs autonomously with zero manual intervention. Backups complete automatically every Sunday at 3 AM. Data updates daily at 2 AM UTC.
