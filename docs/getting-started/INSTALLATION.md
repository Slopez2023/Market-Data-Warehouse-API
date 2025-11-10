# Installation & Deployment Guide

Complete step-by-step setup for local development and production deployment.

---

## Quick Start (Local Development)

Get running in 3 minutes:

```bash
# 1. Clone repository
git clone <your-repo> market-data-api
cd market-data-api

# 2. Copy environment template
cp .env.example .env

# 3. Edit .env and add your Polygon API key
nano .env
# Set: POLYGON_API_KEY=your_key_here

# 4. Start services
docker-compose up -d

# 5. Verify it works
curl http://localhost:8000/health

# 6. Access dashboard
# Open browser: http://localhost:8000/dashboard

# 7. View API docs
# Open browser: http://localhost:8000/docs

# 8. Stop services
docker-compose down
```

**That's it.** Local development is ready.

---

## Prerequisites

### For Local Development
- **Docker Desktop** (macOS/Windows) or **Docker + Docker Compose** (Linux)
- **Polygon.io API Key** (free or paid, link below)
- **Disk Space:** ~2GB for initial database + images
- **RAM:** 4GB+ available

### For Production (Proxmox/Linux)
- **Debian 12 Linux VM** (2+ CPU cores, 4GB+ RAM)
- **Polygon.io API Key** (Starter tier: $29.99/mo recommended)
- **Disk Space:** ~20GB for 500 stocks × 5 years
- **External Backup Drive** (USB, optional but recommended)
- **SSH Access** to VM

### Get Polygon API Key
1. Visit https://polygon.io
2. Sign up (free tier available: 5 calls/min)
3. Dashboard → API Keys
4. Copy your API key

---

## Local Development Setup (5-10 Minutes)

### Step 1: Install Docker

**macOS:**
```bash
# Using Homebrew
brew install docker docker-compose

# Or download Docker Desktop:
# https://www.docker.com/products/docker-desktop
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install -y docker.io docker-compose
sudo usermod -aG docker $USER
# Log out and back in for permissions to take effect
```

**Windows:**
Download Docker Desktop from https://www.docker.com/products/docker-desktop

### Step 2: Verify Installation
```bash
docker --version
docker-compose --version
```

### Step 3: Clone & Setup Project
```bash
# Clone repository
git clone <your-repo> market-data-api
cd market-data-api

# Copy environment template
cp .env.example .env

# Edit with your Polygon API key
nano .env
# Add: POLYGON_API_KEY=<your-key>
# Keep: DB_PASSWORD=password (default is fine for local dev)
```

### Step 4: Build & Start
```bash
# Build Docker image
docker-compose build

# Start services
docker-compose up -d

# Wait 10 seconds for database to initialize
sleep 10

# Verify services are healthy
docker-compose ps
# Both should show "Up" status

# Check API health
curl http://localhost:8000/health
```

**Expected output:**
```json
{"status": "healthy", "timestamp": "...", "scheduler_running": true}
```

### Step 5: Access Dashboard & API
```bash
# Dashboard (real-time monitoring)
# Browser: http://localhost:8000/dashboard

# API interactive docs
# Browser: http://localhost:8000/docs

# Test an endpoint
curl http://localhost:8000/api/v1/status | jq '.'

# Query historical data (after first backfill runs)
curl "http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31" | jq '.count'
```

### Step 6: Monitor Logs
```bash
# Watch API logs
docker-compose logs -f api

# Watch database logs
docker-compose logs -f timescaledb

# Both
docker-compose logs -f
```

### Step 7: Stop Services
```bash
docker-compose down
```

---

## Production Deployment (Proxmox/Linux)

Complete step-by-step guide for production setup.

**Estimated Time:** 45 minutes first-time setup

### Prerequisites Checklist
- [ ] Proxmox VM with Debian 12
- [ ] SSH access working
- [ ] Polygon API key obtained
- [ ] External backup drive available
- [ ] Network connectivity verified

---

## Step 1: Prepare the VM (5 min)

SSH into your Proxmox VM:
```bash
ssh user@proxmox-vm-ip
```

Update system:
```bash
sudo apt update
sudo apt upgrade -y
```

---

## Step 2: Install Docker (5 min)

```bash
# Install dependencies
sudo apt install -y \
  apt-transport-https \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  git

# Add Docker repository
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group (avoid sudo)
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker-compose --version
```

---

## Step 3: Clone Repository (2 min)

```bash
# Navigate to /opt (standard location for applications)
cd /opt

# Clone repository (replace with your repo URL)
sudo git clone <YOUR_REPO_URL> market-data-api

# Fix permissions
sudo chown -R $USER:$USER market-data-api
cd market-data-api
```

---

## Step 4: Configure Environment (3 min)

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

Set these values:
```bash
# REQUIRED
POLYGON_API_KEY=<your-polygon-api-key>
DB_PASSWORD=<strong-password-here>

# Keep defaults or customize
DATABASE_URL=postgresql://postgres:password@timescaledb:5432/market_data
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
BACKFILL_SCHEDULE_HOUR=2
BACKFILL_SCHEDULE_MINUTE=0
```

Save (Ctrl+X, Y, Enter if using nano).

---

## Step 5: Build & Start Services (10 min)

```bash
# Build Docker image (takes ~5 min first time)
docker-compose build

# Start services
docker-compose up -d

# Wait for database to initialize
sleep 15

# Verify both services are running
docker-compose ps
```

Expected output:
```
NAME              COMMAND                STATUS
market-data-api-timescaledb-1    "docker-entrypoint.s…"   Up (healthy)
market-data-api-api-1            "uvicorn main:app…"      Up
```

---

## Step 6: Verify Installation (5 min)

```bash
# Test health endpoint
curl http://localhost:8000/health

# Check system status
curl http://localhost:8000/api/v1/status | jq '.'

# View logs (Ctrl+C to stop)
docker-compose logs -f api

# Check if scheduler is running (should see backfill messages)
# Wait a few seconds...
```

---

## Step 7: Setup Systemd Service (Auto-Start on Reboot)

Create service file:
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
User=<your-username>
WorkingDirectory=/opt/market-data-api

[Install]
WantedBy=multi-user.target
EOF
```

**Important:** Replace `<your-username>` with your actual username (e.g., `ubuntu`, `debian`).

Enable and start service:
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable on boot
sudo systemctl enable market-data-api

# Start service
sudo systemctl start market-data-api

# Check status
sudo systemctl status market-data-api

# Verify containers are running
docker-compose ps
```

Test auto-restart:
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

## Step 8: Setup Automated Backups (10 min)

### Mount External Backup Drive

```bash
# Identify the external drive
lsblk
# Find your USB drive (e.g., sdb1)

# Create mount point
sudo mkdir -p /mnt/external-backup

# Mount the drive (replace sdb1 with your device)
sudo mount /dev/sdb1 /mnt/external-backup

# Verify
ls -la /mnt/external-backup
```

### Make Mount Persistent

```bash
# Get UUID of external drive
sudo blkid | grep sdb1
# Copy the UUID

# Edit fstab
sudo nano /etc/fstab

# Add this line (replace UUID with actual UUID):
UUID=<your-uuid> /mnt/external-backup ext4 defaults,nofail 0 2

# Test it
sudo umount /mnt/external-backup
sudo mount -a
ls -la /mnt/external-backup
```

### Create Backup Script

```bash
sudo tee /opt/market-data-api/backup.sh > /dev/null << 'EOF'
#!/bin/bash

set -e

BACKUP_DIR="/mnt/external-backup/market-data-backups"
DB_NAME="market_data"
DB_HOST="timescaledb"
DB_USER="postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/var/log/market-data-api-backup.log"

mkdir -p $BACKUP_DIR

echo "[$(date)] Starting backup to $BACKUP_DIR" >> $LOG_FILE

# Get DB password from .env
if [ -f /opt/market-data-api/.env ]; then
    export $(grep DB_PASSWORD /opt/market-data-api/.env | xargs)
fi

# Backup using docker exec
docker exec -e PGPASSWORD=$DB_PASSWORD timescaledb pg_dump \
    -h localhost -U $DB_USER $DB_NAME | \
    gzip > $BACKUP_DIR/market_data_$TIMESTAMP.sql.gz

FILE_SIZE=$(du -h $BACKUP_DIR/market_data_$TIMESTAMP.sql.gz | cut -f1)
echo "[$(date)] Backup complete: $FILE_SIZE" >> $LOG_FILE

# Keep last 12 backups, delete older
cd $BACKUP_DIR
ls -t market_data_*.sql.gz 2>/dev/null | tail -n +13 | xargs -r rm -f

echo "[$(date)] Backup job finished" >> $LOG_FILE
EOF

# Make executable
sudo chmod +x /opt/market-data-api/backup.sh
```

### Test Manual Backup

```bash
# Run backup script
/opt/market-data-api/backup.sh

# Check results
ls -lh /mnt/external-backup/market-data-backups/

# Expected: One .sql.gz file (50-200MB)
```

### Schedule Weekly Backup (Cron)

```bash
# Open crontab editor
crontab -e

# Add this line (Sunday 3 AM):
0 3 * * 0 /opt/market-data-api/backup.sh

# Verify
crontab -l
```

---

## Step 9: Monitor & Verify (5 min)

### Check System Health
```bash
# Health check
curl http://localhost:8000/health | jq '.'

# Status metrics
curl http://localhost:8000/api/v1/status | jq '.database'

# View logs
docker-compose logs -f api | head -20
```

### Verify Backfill is Running
```bash
# Check if scheduler is active
curl http://localhost:8000/health | jq '.scheduler_running'

# Should return: true

# Watch logs for backfill messages
docker-compose logs api | grep -i backfill
```

### Verify Backup is Working
```bash
# Check cron logs
sudo journalctl -u cron -n 20

# List backups
ls -lh /mnt/external-backup/market-data-backups/

# Should have at least one backup file
```

---

## Configuration

### Environment Variables

**Required:**
- `POLYGON_API_KEY` — Your Polygon.io API key
- `DB_PASSWORD` — Database password (use strong password for production)

**Optional (defaults shown):**
```bash
DATABASE_URL=postgresql://postgres:password@timescaledb:5432/market_data
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
BACKFILL_SCHEDULE_HOUR=2
BACKFILL_SCHEDULE_MINUTE=0
```

### Change Backfill Time

```bash
# Edit .env
nano /opt/market-data-api/.env

# Change BACKFILL_SCHEDULE_HOUR to desired UTC hour (0-23)
BACKFILL_SCHEDULE_HOUR=2
BACKFILL_SCHEDULE_MINUTE=0

# Restart API
docker-compose restart api
```

### Add More Symbols

```bash
# Edit scheduler configuration
nano /opt/market-data-api/src/scheduler.py

# Find BACKFILL_SYMBOLS list and add more tickers:
BACKFILL_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "TSLA", "META", "NFLX", "UBER", "AMD",
    # Add your symbols here
]

# Restart API
docker-compose restart api
```

---

## Troubleshooting

### Containers won't start

```bash
# Check detailed logs
docker-compose logs api
docker-compose logs timescaledb

# Check if Docker daemon is running
sudo systemctl status docker

# Check disk space
df -h

# Check if ports are already in use
sudo lsof -i :5432  # Database port
sudo lsof -i :8000  # API port
```

### Database connection failed

```bash
# Verify database is running and healthy
docker-compose ps timescaledb

# Test connection manually
docker exec timescaledb pg_isready -U postgres

# Check database password in .env matches docker-compose.yml
grep DB_PASSWORD /opt/market-data-api/.env
grep POSTGRES_PASSWORD docker-compose.yml
```

### Backfill not running

```bash
# Check scheduler status
curl http://localhost:8000/health | jq '.scheduler_running'

# Check logs for scheduler messages
docker-compose logs api | grep -i scheduler

# Verify API key is set
docker-compose exec api printenv | grep POLYGON_API_KEY

# Test Polygon API manually
curl "https://api.polygon.io/v1/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-31?apiKey=YOUR_KEY"
```

### Backup failed

```bash
# Check backup script permissions
ls -la /opt/market-data-api/backup.sh

# Run backup manually
/opt/market-data-api/backup.sh

# Check backup directory
ls -la /mnt/external-backup/market-data-backups/

# Check external drive is mounted
mount | grep external-backup

# Check disk space on backup drive
df -h /mnt/external-backup/
```

### API slow or unresponsive

```bash
# Check database query performance
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;"

# Increase API workers if CPU-bound
nano docker-compose.yml
# Change: uvicorn main:app --workers 8

# Or via environment
# Add to .env: API_WORKERS=8
# Then: docker-compose restart api

# Rebuild indexes
docker exec timescaledb psql -U postgres -d market_data -c "REINDEX DATABASE market_data;"
```

---

## Maintenance

### View Logs
```bash
# All containers
docker-compose logs -f

# Just API
docker-compose logs -f api

# Just database
docker-compose logs -f timescaledb

# Last 50 lines
docker-compose logs api | tail -50
```

### Check Database Size
```bash
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT pg_size_pretty(pg_database_size('market_data'));"
```

### Backup & Restore

**Manual backup:**
```bash
/opt/market-data-api/backup.sh
```

**Restore from backup:**
```bash
# Stop API to avoid conflicts
docker-compose stop api

# Restore database
docker exec -i timescaledb psql -U postgres -d market_data < \
  /mnt/external-backup/market-data-backups/market_data_<TIMESTAMP>.sql.gz

# Restart API
docker-compose start api
```

### Update Application Code

```bash
cd /opt/market-data-api

# Pull latest changes
git pull origin main

# Rebuild image
docker-compose build

# Restart API
docker-compose up -d api
```

### Monitor Disk Usage

```bash
# Overall
df -h /

# Docker-specific
docker system df

# Database size
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT pg_size_pretty(pg_database_size('market_data'));"

# Prune old images/containers
docker system prune -a --volumes
```

---

## Helper Scripts

### docker-start.sh
Container management helper:
```bash
./docker-start.sh up          # Start all services
./docker-start.sh down        # Stop all services
./docker-start.sh status      # Check status & endpoints
./docker-start.sh logs        # Watch live logs
./docker-start.sh test        # Run health checks
./docker-start.sh clean       # Remove old containers
./docker-start.sh reset       # Complete reset (DESTRUCTIVE)
```

### backup.sh
Manual backup:
```bash
./backup.sh
```

### monitor.sh
Real-time monitoring dashboard:
```bash
./monitor.sh
```

---

## Security Considerations

### Current Security Posture
⚠️ **API has ZERO authentication** — Design assumes trusted LAN only.

- API bound to `0.0.0.0:8000` (all interfaces, local only)
- Database on `localhost:5432` (local only)
- No API key authentication
- No rate limiting

### For Production Use, Add:

1. **API Authentication**
   - Implement API key validation
   - Add JWT token support
   - Require authorization header

2. **TLS/HTTPS**
   - Reverse proxy (Nginx)
   - Self-signed certificate
   - Encrypt all traffic

3. **Rate Limiting**
   - Per-IP request limits
   - Prevent abuse
   - Slow down brute force

4. **Network Isolation**
   - Firewall rules (restrict to internal network only)
   - VPN access
   - Don't expose to internet

5. **Database Security**
   - Use strong password (random, 32+ chars)
   - Restrict database port access
   - Enable password authentication in PostgreSQL config

**For now, keep this on internal Proxmox network only.**

---

## Testing Installation

### Full Test Suite
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_validation.py

# Run with coverage
pytest --cov=src tests/
```

### Manual Endpoint Testing

```bash
# Health check
curl http://localhost:8000/health

# Status
curl http://localhost:8000/api/v1/status

# Symbols
curl http://localhost:8000/api/v1/symbols

# Historical data (after backfill runs)
curl "http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31"
```

---

## Next Steps

1. **Monitor first week** of auto-backfills
2. **Spot-check data quality** against Yahoo Finance
3. **Expand symbol list** in `src/scheduler.py` if needed
4. **Review logs** for any errors
5. **Test restore** from backup (monthly)
6. **Plan Phase 2** (indicators, crypto, FX)

---

## Support

For deployment issues:
1. Check logs: `docker-compose logs -f`
2. Verify configuration: `nano .env`
3. Check [README.md](README.md) for overview
4. Check [API_ENDPOINTS.md](API_ENDPOINTS.md) for API reference
5. Check [OPERATIONS.md](OPERATIONS.md) for day-to-day operations

---

## Quick Reference

| Task | Command |
|------|---------|
| Start services | `docker-compose up -d` |
| Stop services | `docker-compose down` |
| Check status | `docker-compose ps` |
| View logs | `docker-compose logs -f` |
| Health check | `curl http://localhost:8000/health` |
| Manual backup | `./backup.sh` |
| Service status | `sudo systemctl status market-data-api` |
| Edit config | `nano .env && docker-compose restart api` |

---

**Installation complete. System ready for production.** ✅
