# Market Data API - Quick Reference

## Essential Commands

### Container Management
```bash
./docker-start.sh up          # Start all services
./docker-start.sh down        # Stop all services
./docker-start.sh status      # Check status & endpoints
./docker-start.sh logs        # Watch live logs
./docker-start.sh test        # Run health checks
./docker-start.sh clean       # Remove old containers
```

### API Endpoints (once running)
```bash
# Health check
curl http://localhost:8000/health

# System status
curl http://localhost:8000/api/v1/status | jq '.'

# Historical data
curl "http://localhost:8000/api/v1/historical/AAPL?start=2022-01-01&end=2023-12-31" | jq '.data[0]'

# Interactive docs
# Open in browser: http://localhost:8000/docs
```

### Database Operations
```bash
# Connect to database
PGPASSWORD=password psql -h localhost -U postgres -d market_data

# Query record count
docker exec timescaledb psql -U postgres -d market_data -c "SELECT COUNT(*) FROM market_data;"

# Check database size
docker exec timescaledb psql -U postgres -d market_data -c "SELECT pg_size_pretty(pg_database_size('market_data'));"

# View backfill history
docker exec timescaledb psql -U postgres -d market_data -c "SELECT * FROM backfill_history ORDER BY backfill_timestamp DESC LIMIT 5;"
```

### Monitoring & Logs
```bash
./monitor.sh                  # Real-time dashboard

# Container logs
docker-compose logs api
docker-compose logs timescaledb
docker-compose logs -f        # Follow all logs

# System logs
docker ps                     # List containers
docker stats                  # Live resource usage
docker system df              # Disk usage
```

### Backup & Restore
```bash
# Manual backup
/opt/market-data-api/backup.sh

# List backups
ls -lh /mnt/external-backup/market-data-backups/

# Restore from backup (will overwrite current database)
docker exec timescaledb psql -U postgres < /mnt/external-backup/market-data-backups/latest_backup.sql.gz
```

---

## Configuration

### Edit Environment
```bash
nano .env
# Key variables:
# POLYGON_API_KEY=your_key
# DB_PASSWORD=password
# DATABASE_URL=postgresql://postgres:password@timescaledb:5432/market_data
# BACKFILL_SCHEDULE_HOUR=2
```

### Change Scheduled Backfill Time
```bash
# Edit .env
BACKFILL_SCHEDULE_HOUR=2   # Change to desired hour (UTC)
BACKFILL_SCHEDULE_MINUTE=0

# Restart API container
docker-compose restart api
```

### Add More Symbols to Backfill
```bash
# Edit src/scheduler.py
nano src/scheduler.py

# Find BACKFILL_SYMBOLS and add more tickers:
BACKFILL_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META",
    "NFLX", "UBER", "AMD", "ADBE", "CRM", "INTC", "QCOM", "CSCO",
    # Add more here
]

# Restart API to apply changes
docker-compose restart api
```

---

## Deployment Checklist (Week 4)

### Pre-Deployment
```bash
# 1. Proxmox VM ready
ssh user@proxmox-vm "uname -a"

# 2. External backup drive available
ls /mnt/external-backup/

# 3. Have Polygon API key ready
echo $POLYGON_API_KEY
```

### Deployment Steps
```bash
# 1. Install Docker
sudo apt update && sudo apt install -y docker.io docker-compose

# 2. Clone repo
cd /opt && git clone <repo-url> market-data-api

# 3. Setup .env
cd market-data-api
cp .env.example .env
nano .env  # Add API key and password

# 4. Build & start
docker-compose build
docker-compose up -d
sleep 10
./docker-start.sh test

# 5. Install systemd service
sudo cp market-data-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable market-data-api

# 6. Setup backup
sudo cp backup.sh /opt/market-data-api/
sudo chmod +x /opt/market-data-api/backup.sh
(crontab -l 2>/dev/null; echo "0 3 * * 0 /opt/market-data-api/backup.sh") | crontab -

# 7. Verify
./docker-start.sh status
```

---

## Troubleshooting

### Services won't start
```bash
# Check logs
docker-compose logs

# Common issues:
# - Port 5432 or 8000 already in use: lsof -i :5432
# - Docker daemon not running: sudo systemctl start docker
# - Insufficient permissions: sudo usermod -aG docker $USER
```

### API not responding
```bash
# Check if container is running
docker-compose ps

# Check API logs
docker-compose logs api | head -50

# Common causes:
# - Database not ready (wait 20 seconds)
# - POLYGON_API_KEY not set
# - Port 8000 blocked by firewall
```

### Backfill not running
```bash
# Check if scheduler is running
curl http://localhost:8000/health | jq '.scheduler_running'

# Check logs for scheduler activity
docker-compose logs api | grep -i scheduler

# Common causes:
# - Invalid POLYGON_API_KEY
# - Database connection failed
# - Network unreachable to api.polygon.io
```

### Database connection failed
```bash
# Check if database is healthy
docker-compose ps timescaledb

# Test connection manually
docker exec timescaledb pg_isready -U postgres

# Check database password in .env matches docker-compose.yml
grep DB_PASSWORD .env
grep POSTGRES_PASSWORD docker-compose.yml
```

### Backup failed
```bash
# Check backup script permissions
ls -la backup.sh

# Test manually
./backup.sh

# Check backup directory
ls -la /mnt/external-backup/market-data-backups/

# Check disk space
df -h /mnt/external-backup/
```

---

## Performance & Optimization

### Check Database Performance
```bash
# View slowest queries
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;"

# Rebuild indexes
docker exec timescaledb psql -U postgres -d market_data -c "REINDEX DATABASE market_data;"

# Analyze query plans
docker exec timescaledb psql -U postgres -d market_data -c \
  "EXPLAIN ANALYZE SELECT * FROM market_data WHERE symbol='AAPL' LIMIT 100;"
```

### Monitor Resource Usage
```bash
# Real-time monitoring
./monitor.sh

# Or manual checks
docker stats

# Check disk compression (TimescaleDB compresses automatically)
docker exec timescaledb psql -U postgres -d market_data -c \
  "SELECT chunk_schema, chunk_name, is_compressed FROM timescaledb_information.chunks LIMIT 10;"
```

### Optimize API Performance
```bash
# Increase workers if CPU-bound
nano docker-compose.yml
# Change: uvicorn main:app --workers 8

# Or via .env
API_WORKERS=8
docker-compose restart api

# Test response time
time curl http://localhost:8000/api/v1/status
```

---

## Maintenance Schedule

### Daily (Automated)
- [x] Backfill runs at 2 AM UTC
- [x] Health check logs

### Weekly (Automated)
- [x] Backup runs Sunday 3 AM
- [x] Old backups pruned (keep last 12)

### Monthly (Manual)
- [ ] Review logs: `docker-compose logs | tail -1000 | grep ERROR`
- [ ] Spot-check data against Yahoo Finance
- [ ] Test restore from backup
- [ ] Review database size: `docker exec timescaledb psql -U postgres -d market_data -c "SELECT pg_size_pretty(pg_database_size('market_data'));"`

### Quarterly (Manual)
- [ ] Expand symbol list if needed
- [ ] Analyze query performance
- [ ] Update Docker images: `docker pull timescale/timescaledb:latest-pg15`
- [ ] Review storage capacity

---

## Common Use Cases

### Setup & First Run
```bash
cp .env.example .env
nano .env
./docker-start.sh up
sleep 10
./docker-start.sh status
```

### Monitor System Health
```bash
./monitor.sh
```

### Check Latest Data
```bash
curl http://localhost:8000/api/v1/status | jq '.database.latest_data'
```

### Query Historical Data
```bash
curl -s "http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31" | jq '.count'
```

### Verify Backup Completed
```bash
ls -lh /mnt/external-backup/market-data-backups/ | tail -1
```

### Test Restore Process
```bash
# Create temporary test database
docker exec timescaledb createdb market_data_test

# Restore latest backup
docker exec timescaledb psql -d market_data_test -U postgres < \
  /mnt/external-backup/market-data-backups/market_data_*.sql.gz

# Verify
docker exec timescaledb psql -d market_data_test -U postgres -c "SELECT COUNT(*) FROM market_data;"

# Cleanup
docker exec timescaledb dropdb market_data_test
```

### Completely Reset System
```bash
# DESTRUCTIVE - will delete all data
./docker-start.sh reset
```

---

## Documentation Map

| Document | Purpose | Audience |
|---|---|---|
| [README.md](README.md) | Quick start + API reference | Everyone |
| [PROJECT_IDEA.md](PROJECT_IDEA.md) | Full specification + architecture | Architects |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Step-by-step deployment guide | DevOps |
| [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) | Executable deployment checklist | Operators |
| [PROGRESS.md](PROGRESS.md) | Implementation status | Project managers |
| [WEEK3_SUMMARY.md](WEEK3_SUMMARY.md) | Week 3 deliverables | Technical leads |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | This file - everyday commands | Daily users |

---

## Key Contacts & Resources

**Polygon.io**
- API Docs: https://polygon.io/docs/stocks/get_aggs_ticker_range
- Status Page: https://status.polygon.io
- Support: support@polygon.io

**TimescaleDB**
- Docs: https://docs.timescale.com
- Community: https://github.com/timescale/timescaledb

**FastAPI**
- Docs: https://fastapi.tiangolo.com
- Tutorial: https://fastapi.tiangolo.com/tutorial/

**Docker**
- Docs: https://docs.docker.com
- Compose: https://docs.docker.com/compose

---

## Version Info

```
Last Updated: 2025-11-09
API Version: 1.0.0
Python: 3.11+
FastAPI: 0.104.1
TimescaleDB: Latest (PostgreSQL 15)
Docker: 28.5.0+
```

---

**Ready to deploy. Follow DEPLOYMENT_CHECKLIST.md for Week 4.**
