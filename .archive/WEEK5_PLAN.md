# Week 5: Production Deployment & Monitoring Setup

**Start Date:** November 9, 2025  
**Target Completion:** November 16, 2025  
**Goal:** Deploy to Proxmox, load production data, establish monitoring

---

## Day 1-2: VM Preparation & Docker Setup

### Prerequisites Check
- [ ] Proxmox VM created (Debian 12, 8GB RAM minimum)
- [ ] Network connectivity verified
- [ ] SSH access working
- [ ] 100GB+ free disk space available

### Docker Installation
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose git curl postgresql-client
sudo usermod -aG docker $USER
# Log out and back in for group changes
docker --version  # Should be ≥24.0
docker-compose --version  # Should be ≥2.0
```

### Checklist
- [ ] Docker installed and running
- [ ] Docker Compose v2+ working
- [ ] PostgreSQL client tools installed
- [ ] User in docker group (no sudo for docker commands)

---

## Day 3: Application Deployment

### Clone Repository
```bash
cd /opt
sudo git clone https://github.com/Slopez2023/Market-Data-Warehouse-API.git market-data-api
sudo chown -R $USER:$USER market-data-api
cd market-data-api
```

### Configure Environment
```bash
cp .env.example .env
# Edit .env with:
# - POLYGON_API_KEY (from Polygon.io account)
# - DB_PASSWORD (strong password, ≥12 chars)
# - DATABASE_URL=postgresql://postgres:PASSWORD@timescaledb:5432/market_data
# - LOG_LEVEL=INFO
chmod 600 .env
```

### Build & Start Services
```bash
docker-compose build
docker-compose up -d
docker-compose ps  # Verify 2 containers running
sleep 10

# Test connectivity
curl http://localhost:8000/health | jq '.'
```

### Checklist
- [ ] Repository cloned to `/opt/market-data-api`
- [ ] `.env` configured with real API key
- [ ] Docker image built successfully
- [ ] Both containers running (timescaledb + api)
- [ ] Health endpoint responding

---

## Day 4: Initial Data Load

### Run Backfill
```bash
# SSH into API container
docker-compose exec api bash

# Run backfill for 15 primary symbols
python backfill.py

# Expected output:
# Processing: AAPL, MSFT, GOOGL, AMZN, NVDA...
# Should take 5-15 minutes depending on API rate limits
```

### Verify Data Loaded
```bash
# Check database directly
docker-compose exec timescaledb psql -U postgres -d market_data \
  -c "SELECT symbol, COUNT(*) as candles FROM market_data GROUP BY symbol ORDER BY candles DESC LIMIT 15;"

# Check API status endpoint
curl http://localhost:8000/api/v1/status | jq '.'
```

### Expected Results
- 15+ symbols loaded
- 15,000+ total candles in database
- Validation rate >95%
- Latest date recent (within last trading day)

### Checklist
- [ ] Backfill completed without errors
- [ ] Database contains data for 15+ symbols
- [ ] Validation rate ≥95%
- [ ] Status endpoint shows correct metrics

---

## Day 5: Systemd Service Setup

### Create Systemd Service
```bash
sudo cp market-data-api.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/market-data-api.service
sudo systemctl daemon-reload
```

### Edit Service File (if needed)
```bash
sudo nano /etc/systemd/system/market-data-api.service
# Ensure WorkingDirectory=/opt/market-data-api
# Ensure User=<your_username>
```

### Enable & Test Service
```bash
# Start the service
sudo systemctl start market-data-api

# Enable auto-start on reboot
sudo systemctl enable market-data-api

# Check status
sudo systemctl status market-data-api

# View logs
sudo journalctl -u market-data-api -f  # Follow logs
```

### Checklist
- [ ] Service file installed and loaded
- [ ] Service starts without errors
- [ ] Service set to auto-start on reboot
- [ ] Logs showing scheduler running
- [ ] Endpoints responding (health, status, historical)

---

## Day 6: Monitoring & Verification

### Create Monitoring Script
```bash
# Create ~/monitor-api.sh
cat > ~/monitor-api.sh << 'EOF'
#!/bin/bash
# Monitor Market Data API health and performance

API_URL="http://localhost:8000"
LOG_FILE="$HOME/api-monitor.log"

check_health() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Health Check" >> $LOG_FILE
    curl -s $API_URL/health | jq '.' >> $LOG_FILE
}

check_status() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Status Check" >> $LOG_FILE
    curl -s $API_URL/api/v1/status | jq '.' >> $LOG_FILE
}

check_database() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Database Check" >> $LOG_FILE
    docker-compose -f /opt/market-data-api/docker-compose.yml exec timescaledb \
      psql -U postgres -d market_data \
      -c "SELECT COUNT(*) as total_candles FROM market_data;" >> $LOG_FILE
}

check_disk() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Disk Usage" >> $LOG_FILE
    df -h | head -3 >> $LOG_FILE
}

check_services() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Service Status" >> $LOG_FILE
    sudo systemctl status market-data-api | head -10 >> $LOG_FILE
}

# Run all checks
check_health
check_status
check_database
check_disk
check_services

echo "---" >> $LOG_FILE
EOF

chmod +x ~/monitor-api.sh
```

### Setup Cron Job
```bash
# Schedule monitoring every 6 hours (2 AM, 8 AM, 2 PM, 8 PM UTC)
crontab -e

# Add these lines:
0 2,8,14,20 * * * /home/$USER/monitor-api.sh
# Or for every hour:
0 * * * * /home/$USER/monitor-api.sh
```

### Manual Verification
```bash
# Run health check
curl http://localhost:8000/health

# Check status with metrics
curl http://localhost:8000/api/v1/status | jq '.symbols_available, .validation_rate, .gap_detection_results'

# Query sample data
curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-11-01&end=2024-11-07" | jq '.data[:3]'

# Check system resources
free -h  # Memory
df -h /  # Disk
top -b -n1 | head -15  # CPU
```

### Checklist
- [ ] Monitoring script created and executable
- [ ] Cron job configured for periodic checks
- [ ] Manual health check passing
- [ ] Status endpoint showing correct metrics
- [ ] Historical data queries working
- [ ] System resources healthy

---

## Day 7: Backup & Auto-Backfill Verification

### Test Backup Procedure
```bash
# Run backup script
./backup.sh

# Verify backup created
ls -lh backups/
```

### Schedule Weekly Backup
```bash
# Add to crontab (Sunday 3 AM UTC)
crontab -e
# Add:
0 3 * * 0 /opt/market-data-api/backup.sh
```

### Verify Auto-Backfill Scheduling
```bash
# Check scheduler logs
tail -f /opt/market-data-api/logs/api.log | grep -i "backfill\|scheduler"

# Should see messages at 2 AM UTC daily
```

### Production Readiness Verification
```bash
# All endpoints working?
curl http://localhost:8000/  # Root endpoint with docs links
curl http://localhost:8000/health  # Should return healthy
curl http://localhost:8000/api/v1/status  # Should show metrics
curl http://localhost:8000/api/v1/symbols  # Should list symbols

# Database healthy?
docker-compose exec timescaledb psql -U postgres -d market_data \
  -c "SELECT * FROM symbol_status LIMIT 5;"

# Logs clean?
tail -20 /opt/market-data-api/logs/api.log | grep -i error
```

### Checklist
- [ ] Backup script runs successfully
- [ ] Backup file created with reasonable size (>100KB)
- [ ] Backup cron job scheduled (Sunday 3 AM)
- [ ] Scheduler running messages visible in logs
- [ ] All API endpoints responding correctly
- [ ] Database queries responsive
- [ ] No errors in recent logs
- [ ] System ready for production use

---

## Success Criteria

- ✅ Proxmox VM configured with Docker
- ✅ Application deployed and running
- ✅ 15+ symbols with 5+ years historical data
- ✅ All endpoints responding
- ✅ Validation rate ≥95%
- ✅ Systemd service auto-starts on reboot
- ✅ Monitoring cron job configured
- ✅ Weekly backups scheduled
- ✅ Auto-backfill runs daily at 2 AM UTC
- ✅ No errors in logs

---

## Monitoring Dashboard (Optional Enhancement)

For real-time monitoring, can create:
1. Simple HTML dashboard showing latest metrics
2. Prometheus exporter for time-series metrics
3. Grafana dashboard connected to TimescaleDB

Reference: see MONITORING_SETUP.md (Week 5 optional)

---

## Rollback Plan

If issues occur:

### Quick Rollback
```bash
# Stop services
docker-compose down

# Restore from backup
./backup.sh --restore backups/latest.sql.gz

# Restart
docker-compose up -d
```

### Full VM Rollback
```bash
# Use Proxmox snapshot created before deployment
# Access Proxmox UI → VM → Snapshots → Restore
```

---

## Notes

- Scheduler runs at **02:00 UTC daily** (8 PM EST / 5 PM PST)
- All timestamps stored in UTC
- Backups stored in `backups/` directory
- Logs at `/opt/market-data-api/logs/api.log`
- Database credentials in `.env` (never commit!)

---

## Contact & Documentation

- README.md - Overview and API usage
- DEPLOYMENT.md - Detailed deployment guide
- QUICK_REFERENCE.md - Common commands
- PERFORMANCE_TEST_RESULTS.md - Performance metrics
