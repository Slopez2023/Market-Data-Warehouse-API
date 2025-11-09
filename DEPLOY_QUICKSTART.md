# Deployment Quick Start

One-command deployment steps for Proxmox VM. Expected time: **2-3 hours**

---

## Prerequisites (30 minutes)

```bash
# On Proxmox VM (Debian 12)
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose git curl postgresql-client

# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

Verify:
```bash
docker --version  # Should be ≥24.0
docker-compose --version  # Should be ≥2.0
```

---

## Deploy (20 minutes)

```bash
# Clone and setup
cd /opt
sudo git clone https://github.com/Slopez2023/Market-Data-Warehouse-API.git market-data-api
sudo chown -R $USER:$USER market-data-api
cd market-data-api

# Configure environment
cp .env.example .env
nano .env
# Edit these:
# POLYGON_API_KEY=your_key_here
# DB_PASSWORD=strong_password_12chars_min
# DATABASE_URL=postgresql://postgres:strong_password_12chars_min@timescaledb:5432/market_data

# Build and start
docker-compose build
docker-compose up -d

# Wait for services
sleep 10

# Verify
curl http://localhost:8000/health | jq '.'
# Should show: {"status": "healthy", ...}
```

---

## Load Data (15-30 minutes)

```bash
# Run backfill for 15 symbols
docker-compose exec api python backfill.py

# Monitor progress (in another terminal)
docker-compose logs -f api | grep -i "aapl\|msft\|backfill"

# When done, verify
curl http://localhost:8000/api/v1/status | jq '.symbols_available, .total_records'
# Should show: 15+, 15000+
```

---

## Setup Service (5 minutes)

```bash
# Install systemd service
sudo cp market-data-api.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/market-data-api.service
sudo systemctl daemon-reload

# Start service
sudo systemctl start market-data-api
sudo systemctl enable market-data-api

# Verify
sudo systemctl status market-data-api
curl http://localhost:8000/health | jq '.scheduler_running'
# Should show: true
```

---

## Setup Monitoring (5 minutes)

```bash
# Create monitoring infrastructure
bash /opt/market-data-api/monitor-setup.sh

# Configure cron jobs
bash /opt/market-data-api/scripts/setup-cron.sh
# Answer prompts to add hourly monitoring + weekly backup

# View live dashboard
bash /opt/market-data-api/scripts/dashboard.sh
```

---

## Verify Production Readiness

```bash
# Health check
curl http://localhost:8000/health
# Expected: HTTP 200, scheduler_running: true

# API metrics
curl http://localhost:8000/api/v1/status | jq '.validation_rate'
# Expected: ≥95%

# Test data query
curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-11-01&end=2024-11-07" | jq '.data | length'
# Expected: 5+ candles

# System health
free -h | grep Mem  # Should have >2GB free
df -h / | tail -1   # Should have >50GB free
ps aux | grep -i "gunicorn\|uvicorn" | grep -v grep | wc -l
# Should show: 4+ worker processes

# Check logs
tail -20 /opt/market-data-api/logs/api.log | grep -i error
# Should be empty or minimal
```

---

## Daily Operations

### Morning Check (5 minutes)
```bash
# Verify overnight backfill
curl http://localhost:8000/api/v1/status | jq '.latest_timestamp'

# Check health
curl http://localhost:8000/health | jq '.status'
```

### Weekly Check (15 minutes)
```bash
# Run monitoring
~/monitor-api.sh

# Review weekly summary
bash /opt/market-data-api/scripts/weekly-summary.sh

# Check backup
ls -lh /opt/market-data-api/backups/ | head -3
```

### Monthly Check (30 minutes)
```bash
# Review trends
tail -200 ~/api-monitor.log | grep "Validation Rate"

# Database health
docker-compose exec timescaledb psql -U postgres -d market_data \
  -c "SELECT pg_size_pretty(pg_database_size('market_data')) as size;"

# Test restore (quarterly)
./backup.sh --test-restore
```

---

## Troubleshooting

### Service won't start
```bash
sudo systemctl status market-data-api
sudo journalctl -u market-data-api -n 50
docker-compose logs api
```

### No data in database
```bash
# Check backfill logs
docker-compose logs api | grep -i "backfill\|error"

# Manual backfill
docker-compose exec api python backfill.py

# Verify API key
docker-compose exec api python -c "import os; print(os.getenv('POLYGON_API_KEY'))"
```

### API not responding
```bash
docker-compose ps
docker-compose logs api
sudo systemctl restart market-data-api
```

### Disk full
```bash
du -sh /opt/market-data-api/backups/
# Remove old backups: ls -t backups/ | tail -n +5 | xargs -I {} rm backups/{}
```

---

## Key Endpoints

| Endpoint | Purpose | Example |
|----------|---------|---------|
| `/health` | Health check | `curl http://localhost:8000/health` |
| `/api/v1/status` | Metrics & stats | `curl http://localhost:8000/api/v1/status` |
| `/api/v1/symbols` | List available symbols | `curl http://localhost:8000/api/v1/symbols` |
| `/api/v1/historical/{symbol}` | Get candles | `curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-01-01&end=2024-01-31"` |
| `/docs` | API documentation | Open in browser: http://localhost:8000/docs |

---

## Expected Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Prerequisites | 30 min | ✓ Quick |
| Deploy | 20 min | ✓ Fast |
| Load Data | 15-30 min | ✓ One-time |
| Setup Service | 5 min | ✓ Fast |
| Setup Monitoring | 5 min | ✓ Fast |
| Verification | 10 min | ✓ Quick |
| **Total** | **2-3 hours** | ✅ Ready |

After deployment, daily operations are mostly automated. Just monitor!

---

## Files & Locations

```
/opt/market-data-api/
├── docker-compose.yml          # Service definitions
├── Dockerfile                  # API container image
├── market-data-api.service     # Systemd service
├── monitor-setup.sh            # Monitoring setup
├── backup.sh                   # Backup script
├── backfill.py                 # Data backfill
├── main.py                     # FastAPI application
├── logs/
│   └── api.log                 # Application logs
├── backups/                    # Backup files
├── sql/                        # Database schema
└── src/
    ├── clients/                # API clients
    ├── services/               # Business logic
    └── models/                 # Data models

~/ (home directory)
├── monitor-api.sh              # Monitoring script
├── api-monitor.log             # Monitoring logs
└── api-summary-*.txt           # Weekly reports

Logs & Monitoring:
- Application logs: /opt/market-data-api/logs/api.log
- Service logs: sudo journalctl -u market-data-api
- Monitoring logs: ~/api-monitor.log
```

---

## Additional Resources

- **WEEK5_PLAN.md** - Detailed day-by-day schedule
- **MONITORING_SETUP.md** - Complete monitoring guide
- **DEPLOYMENT.md** - Full deployment walkthrough
- **QUICK_REFERENCE.md** - Common commands
- **README.md** - API usage and features
- **PERFORMANCE_TEST_RESULTS.md** - Performance metrics

---

Ready? Start with prerequisites and follow the steps above!

Questions? Check the detailed guides or review logs.

Good luck! 🚀
