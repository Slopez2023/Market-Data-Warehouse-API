# Market Data API - Deployment Guide

## Overview

This guide covers deploying the Market Data API to your Proxmox Debian 12 VM running on OptiPlex 3060.

**Architecture:**
- TimescaleDB (PostgreSQL 15) — time-series database
- FastAPI (uvicorn, 4 workers) — REST API
- APScheduler — Daily auto-backfill at 2 AM UTC
- Systemd service — Auto-start on reboot
- pg_dump — Weekly automated backups

---

## Prerequisites

**On Proxmox VM:**
- Debian 12 (or compatible Linux)
- Docker + Docker Compose v2
- Git (for cloning this repo)
- Python 3.11+ (for local testing, optional)
- External USB drive mounted for backups (optional but recommended)

---

## Step 1: Prepare the VM

### Install Docker & Dependencies

```bash
sudo apt update
sudo apt install -y \
  docker.io \
  docker-compose \
  git \
  curl \
  postgresql-client
```

### Enable Docker for your user (no sudo needed)

```bash
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

### Verify Installation

```bash
docker --version
docker-compose --version
```

---

## Step 2: Clone & Setup Project

```bash
cd /opt
sudo git clone <YOUR_REPO_URL> market-data-api
sudo chown -R $USER:$USER market-data-api
cd market-data-api
```

### Create .env file

```bash
# Copy template
cp .env.example .env

# Edit with your values
nano .env
```

**Required values to set:**
```
POLYGON_API_KEY=<your_polygon_api_key>
DB_PASSWORD=<strong_password_here>
DATABASE_URL=postgresql://postgres:<password>@timescaledb:5432/market_data
LOG_LEVEL=INFO
```

### Create logs directory

```bash
mkdir -p logs
```

---

## Step 3: Build & Start Services

### Build the API Docker image

```bash
cd /opt/market-data-api
docker-compose build
```

### Start both services

```bash
docker-compose up -d
```

### Verify services are healthy

```bash
# Check container status
docker-compose ps

# Both should show "Up" status

# Check logs
docker-compose logs -f api      # API logs
docker-compose logs -f timescaledb  # Database logs
```

### Test API endpoints

```bash
# Health check
curl http://localhost:8000/health

# System status
curl http://localhost:8000/api/v1/status

# Interactive docs
# Open in browser: http://localhost:8000/docs
```

---

## Step 4: Configure Systemd Service (Auto-Start on Reboot)

### Create service file

```bash
sudo tee /etc/systemd/system/market-data-api.service > /dev/null << 'EOF'
[Unit]
Description=Market Data API (TimescaleDB + FastAPI)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/docker-compose -f /opt/market-data-api/docker-compose.yml up -d
ExecStop=/usr/bin/docker-compose -f /opt/market-data-api/docker-compose.yml down
RemainAfterExit=yes
Restart=always
RestartSec=10
User=$USER
WorkingDirectory=/opt/market-data-api

[Install]
WantedBy=multi-user.target
EOF
```

### Enable and test the service

```bash
sudo systemctl daemon-reload
sudo systemctl enable market-data-api
sudo systemctl start market-data-api

# Verify it's running
sudo systemctl status market-data-api

# Check that containers started
docker-compose ps
```

### Test service restart (simulated reboot)

```bash
# Stop the service
sudo systemctl stop market-data-api

# Verify containers stopped
docker-compose ps  # Should be empty

# Start the service
sudo systemctl start market-data-api

# Verify containers restarted
docker-compose ps  # Should show 2 containers "Up"
```

---

## Step 5: Setup Automated Backups

### Mount external backup drive

```bash
# Plug in USB drive to Proxmox

# Identify the drive
lsblk  # Find your external USB drive (e.g., sdb1)

# Create mount point
sudo mkdir -p /mnt/external-backup

# Mount it
sudo mount /dev/sdb1 /mnt/external-backup

# Verify
ls -la /mnt/external-backup
```

### Make mount persistent

```bash
# Get UUID of external drive
sudo blkid | grep sdb1  # Copy the UUID

# Edit fstab
sudo nano /etc/fstab

# Add line (replace UUID):
UUID=your-uuid-here /mnt/external-backup ext4 defaults,nofail 0 2

# Test it
sudo umount /mnt/external-backup
sudo mount -a
ls -la /mnt/external-backup
```

### Create backup script

```bash
sudo tee /opt/market-data-api/backup.sh > /dev/null << 'EOF'
#!/bin/bash

set -e

BACKUP_DIR="/mnt/external-backup/market-data-backups"
DB_NAME="market_data"
DB_HOST="timescaledb"  # Docker service name
DB_USER="postgres"
DB_PASSWORD=${DB_PASSWORD}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/var/log/market-data-api-backup.log"

mkdir -p $BACKUP_DIR

echo "[$(date)] Starting backup to $BACKUP_DIR" >> $LOG_FILE

# Get DB password from .env
if [ -f /opt/market-data-api/.env ]; then
    export $(grep DB_PASSWORD /opt/market-data-api/.env | xargs)
fi

# Use docker exec to backup from container
docker exec -e PGPASSWORD=$DB_PASSWORD timescaledb pg_dump \
    -h localhost -U $DB_USER $DB_NAME | \
    gzip > $BACKUP_DIR/market_data_$TIMESTAMP.sql.gz

FILE_SIZE=$(du -h $BACKUP_DIR/market_data_$TIMESTAMP.sql.gz | cut -f1)
echo "[$(date)] Backup complete: $FILE_SIZE" >> $LOG_FILE

# Keep last 12 backups
cd $BACKUP_DIR
ls -t market_data_*.sql.gz 2>/dev/null | tail -n +13 | xargs -r rm -f

echo "[$(date)] Backup job finished (cleaned old backups)" >> $LOG_FILE
EOF

# Make it executable
sudo chmod +x /opt/market-data-api/backup.sh
```

### Create cron job (weekly Sunday 3 AM)

```bash
# Open crontab editor
crontab -e

# Add this line:
0 3 * * 0 /opt/market-data-api/backup.sh

# Verify
crontab -l
```

### Test backup manually

```bash
# Run backup script
/opt/market-data-api/backup.sh

# Check results
ls -lh /mnt/external-backup/market-data-backups/

# Expected: One .sql.gz file (~50-200MB for initial backfill)
```

---

## Step 6: Run Initial Backfill

The scheduler will automatically run every day at 2 AM UTC. For initial setup, run manually:

```bash
# View scheduler logs
docker-compose logs -f api | grep -i backfill

# Check current status
curl http://localhost:8000/api/v1/status | jq '.data_quality.scheduler_status'
```

The scheduler starts automatically when the API container starts. Monitor progress via logs:

```bash
# Watch API logs (includes scheduler output)
docker-compose logs -f api
```

---

## Step 7: Monitor & Verify

### Daily monitoring

```bash
# Check system health
curl http://localhost:8000/health | jq '.'

# Check data quality status
curl http://localhost:8000/api/v1/status | jq '.database'

# Expected: symbols_available increases daily, validation_rate_pct > 95%
```

### Check container health

```bash
# Ensure both containers are healthy
docker-compose ps

# If any container is unhealthy, check logs:
docker-compose logs timescaledb  # Database logs
docker-compose logs api          # API logs
```

### Verify backups are running

```bash
# Check cron job ran
cat /var/log/market-data-api-backup.log | tail -20

# Verify backup files exist
ls -lh /mnt/external-backup/market-data-backups/

# Test restore (monthly)
docker exec timescaledb pg_restore \
    -d market_data_test \
    -h localhost \
    -U postgres \
    < /mnt/external-backup/market-data-backups/latest_backup.sql.gz
```

---

## Troubleshooting

### Container won't start

```bash
# Check detailed logs
docker-compose logs api
docker-compose logs timescaledb

# Check disk space
df -h /

# Check if port 5432 or 8000 is already in use
sudo lsof -i :5432
sudo lsof -i :8000
```

### Database connection errors

```bash
# Verify database is running and healthy
docker-compose ps timescaledb

# Test connection manually
docker exec timescaledb \
    psql -U postgres -d market_data -c "SELECT COUNT(*) FROM market_data;"

# Check DATABASE_URL in .env matches docker-compose.yml
cat .env | grep DATABASE_URL
```

### Backfill not running

```bash
# Check scheduler is running
curl http://localhost:8000/health | jq '.scheduler_running'

# Check logs for scheduler messages
docker-compose logs -f api | grep -i scheduler

# Verify POLYGON_API_KEY is set
docker-compose exec api printenv | grep POLYGON_API_KEY
```

### Backups failing

```bash
# Check cron job status
sudo journalctl -u cron -n 50

# Test backup script manually
/opt/market-data-api/backup.sh

# Check backup directory permissions
ls -la /mnt/external-backup/market-data-backups/

# Verify external drive is mounted
mount | grep external-backup
```

---

## Maintenance

### Update the application code

```bash
cd /opt/market-data-api
git pull origin main
docker-compose build
docker-compose up -d api  # Restart just the API
```

### View real-time logs

```bash
# All containers
docker-compose logs -f

# Just API
docker-compose logs -f api

# Just database
docker-compose logs -f timescaledb
```

### Database backups

**Manual backup:**
```bash
/opt/market-data-api/backup.sh
```

**Restore from backup:**
```bash
# Stop API to avoid conflicts
docker-compose stop api

# Restore database
docker exec timescaledb psql -U postgres < /path/to/backup.sql.gz

# Restart API
docker-compose up -d api
```

### Check database size

```bash
docker exec timescaledb \
    psql -U postgres -d market_data -c \
    "SELECT 
        pg_size_pretty(pg_database_size('market_data')) as database_size,
        pg_size_pretty(sum(pg_total_relation_size(schemaname||'.'||tablename))) as tables_size
     FROM pg_tables WHERE schemaname = 'public';"
```

### Monitor disk usage

```bash
# Overall
df -h /

# Docker-specific
docker system df

# Prune old images/containers
docker system prune -a --volumes
```

---

## Security Notes

⚠️ **WARNING:** The API has ZERO authentication. It is designed for use on a **trusted LAN only**.

### Current Security Posture

- API bound to `0.0.0.0:8000` (all interfaces)
- Database accessible on `localhost:5432` (local only)
- No API key authentication
- No rate limiting

### For Production Use

Consider adding:

1. **API Authentication** (API key + JWT)
2. **TLS/HTTPS** (reverse proxy with Nginx)
3. **Rate Limiting** (per-IP request limits)
4. **Database Password** (use strong password in .env, change default)
5. **Firewall Rules** (restrict API access to trusted IPs)

For now, keep this on your internal Proxmox network.

---

## Next Steps (Week 4+)

1. **Monitor first week** of auto-backfills
2. **Spot-check data** against Yahoo Finance
3. **Test restore** from backup
4. **Expand symbols** in `BACKFILL_SYMBOLS` (src/scheduler.py)
5. **Plan Phase 2:** Multi-timeframe aggregates, crypto, FX

---

## Support

For issues:
1. Check logs: `docker-compose logs -f`
2. Test endpoints manually: `curl http://localhost:8000/health`
3. Verify .env configuration
4. Check /PROGRESS.md for implementation status

**Contact:** See README.md
