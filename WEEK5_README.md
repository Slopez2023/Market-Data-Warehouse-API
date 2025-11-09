# Week 5: Production Deployment & Monitoring

**Status:** ✅ All documentation and infrastructure ready for deployment  
**Target Timeline:** 2-3 hours (Days 1-2 through Day 7)  
**Start Date:** November 9, 2025

---

## Quick Navigation

### I need to...

| Task | Document | Time |
|------|----------|------|
| Deploy ASAP | [DEPLOY_QUICKSTART.md](DEPLOY_QUICKSTART.md) | 2-3 hrs |
| See the full plan | [WEEK5_PLAN.md](WEEK5_PLAN.md) | 30 min read |
| Learn what's been built | [README.md](README.md) | 10 min |
| Setup monitoring | [MONITORING_SETUP.md](MONITORING_SETUP.md) | 10 min |
| Common commands | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Reference |
| See performance metrics | [PERFORMANCE_TEST_RESULTS.md](PERFORMANCE_TEST_RESULTS.md) | 15 min |
| Full deployment guide | [DEPLOYMENT.md](DEPLOYMENT.md) | 30 min |

---

## Week 5 At A Glance

### What Gets Done This Week
- Deploy to Proxmox VM with Docker
- Load 5+ years of historical data (15+ symbols)
- Setup systemd service for auto-start
- Configure automated monitoring
- Verify everything works in production

### What We Already Have
✅ Complete codebase  
✅ All features implemented  
✅ 32 tests (100% passing)  
✅ Docker setup ready  
✅ Systemd service template  
✅ Backup automation  
✅ Monitoring infrastructure  

### What Happens This Week
→ Move from development to production  
→ Test with real TimescaleDB instance  
→ Verify scheduler runs at 2 AM UTC daily  
→ Confirm backups working  
→ Setup 24/7 monitoring  

---

## Day-by-Day Breakdown

**Day 1-2: Infrastructure Setup (1 hour)**
- Install Docker & dependencies on Proxmox VM
- Verify network and disk space

**Day 3: Deploy Application (45 min)**
- Clone repo to `/opt/market-data-api`
- Configure environment variables
- Build Docker image
- Start TimescaleDB and API containers

**Day 4: Load Data (30 min)**
- Run backfill for 15 symbols
- Verify 15,000+ candles loaded
- Check validation rate ≥95%

**Day 5: Setup Service (15 min)**
- Install systemd service file
- Enable auto-start on reboot
- Verify scheduler is running

**Day 6: Monitoring (15 min)**
- Run `monitor-setup.sh`
- Configure cron jobs
- Test health checks

**Day 7: Final Verification (15 min)**
- Test backup procedure
- Verify auto-backfill
- Final production checks

**Total: 2.5-3 hours of active time**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Proxmox VM (Debian 12)               │
├──────────────────────────────────────────────────────────┤
│  Docker Services:                                        │
│  ┌──────────────────────┐      ┌─────────────────────┐ │
│  │  TimescaleDB         │      │  FastAPI (4 workers)│ │
│  │  - Port 5432         │◄────►│  - Port 8000        │ │
│  │  - market_data DB    │      │  - /health          │ │
│  │  - 18K+ candles      │      │  - /api/v1/status   │ │
│  │  - Hypertable        │      │  - /api/v1/hist...  │ │
│  └──────────────────────┘      └─────────────────────┘ │
│                                        ▲                 │
│                                        │                 │
│  Systemd Service (auto-start):         │                 │
│  ┌────────────────────────────────────┘                 │
│  │  APScheduler                                         │
│  │  - Daily backfill (2 AM UTC)                        │
│  │  - Auto-restart on failure                          │
│  └──────────────────────────────────────────────────────┘
│                                                          │
│  Cron Jobs:                                              │
│  - Hourly: Health check + metrics                       │
│  - Daily: Backfill (scheduler does this)                │
│  - Weekly: Backup (pg_dump)                            │
│  - Weekly: Summary report                               │
│                                                          │
│  Monitoring:                                             │
│  - ~/monitor-api.sh (health checks)                     │
│  - ~/api-monitor.log (metrics log)                      │
│  - scripts/dashboard.sh (live view)                     │
│  - scripts/weekly-summary.sh (reports)                  │
└──────────────────────────────────────────────────────────┘

External:
  ↑
  │ API Calls (Polygon.io)
  │ Rate limit: 5 calls/min (free tier)
  ↓
Polygon.io - OHLCV Data for 500+ stocks
```

---

## Success Criteria

By end of Week 5:

- ✅ Proxmox VM running with Docker
- ✅ Both containers healthy (timescaledb + api)
- ✅ 15+ symbols loaded with 5+ years history
- ✅ 15,000+ total candles in database
- ✅ Validation rate ≥95%
- ✅ All API endpoints responding
- ✅ Health check <100ms
- ✅ Status endpoint <1s
- ✅ Systemd service auto-starts
- ✅ Scheduler logs show 2 AM run
- ✅ Backup created successfully
- ✅ Monitoring cron jobs active
- ✅ Zero errors in production logs

---

## Files Overview

### Documentation
| File | Purpose | Length |
|------|---------|--------|
| DEPLOY_QUICKSTART.md | Fast deployment guide | 1 page |
| WEEK5_PLAN.md | Detailed 7-day schedule | 10 pages |
| DEPLOYMENT.md | Full walkthrough | 20 pages |
| MONITORING_SETUP.md | Monitoring infrastructure | 15 pages |
| QUICK_REFERENCE.md | Common commands | 10 pages |
| README.md | API overview & usage | 15 pages |
| PERFORMANCE_TEST_RESULTS.md | Benchmarks & metrics | 10 pages |

### Scripts
| File | Purpose |
|------|---------|
| monitor-setup.sh | Setup all monitoring (automated) |
| scripts/dashboard.sh | Live monitoring dashboard |
| scripts/weekly-summary.sh | Weekly report generator |
| backup.sh | Database backup (pg_dump) |
| backfill.py | Historical data loader |

### Configuration
| File | Purpose |
|------|---------|
| docker-compose.yml | Service definitions |
| Dockerfile | API container image |
| market-data-api.service | Systemd service |
| .env.example | Environment template |

---

## Key Resources

### Monitoring
Once deployed, you have:
- **Hourly checks** - API health & metrics
- **Live dashboard** - Real-time status
- **Daily logs** - Performance tracking
- **Weekly reports** - Trend analysis
- **Alert system** - Email/log on issues

### Backup & Recovery
- **Weekly backups** - pg_dump every Sunday 3 AM
- **Auto-restore** - Test scripts included
- **Retention** - Keep 4 weeks of backups
- **Disaster plan** - Full rollback documented

### Data Quality
- **99.7% validation** - OHLCV constraints checked
- **Gap detection** - Flags anomalies
- **Quality scoring** - 0-1.0 per candle
- **Yahoo Finance comparison** - 100% match on spot checks

---

## Common Issues & Solutions

### Docker Won't Install
```bash
sudo apt update
sudo apt install -y docker.io docker-compose
```

### Permission Denied on Docker
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

### Backfill Fails
```bash
# Check API key in .env
# Check Polygon API status (website)
# Check rate limits (5 calls/min free tier)
docker-compose logs api | grep -i error
```

### Database Won't Start
```bash
docker-compose logs timescaledb
# Check disk space: df -h /
# Check permissions: sudo chown -R $USER docker/
```

### API Not Responding
```bash
docker-compose ps
curl http://localhost:8000/health
# Check logs: docker-compose logs api
# Restart: docker-compose restart api
```

See [WEEK5_PLAN.md](WEEK5_PLAN.md) for full troubleshooting section.

---

## Next Steps After Deployment

### Daily (5 minutes)
```bash
# Check if overnight backfill ran
curl http://localhost:8000/api/v1/status | jq '.latest_timestamp'
```

### Weekly (15 minutes)
```bash
# Run automated monitoring
~/monitor-api.sh
# Review report
cat ~/api-monitor.log | tail -50
```

### Monthly (30 minutes)
```bash
# Trend analysis
bash scripts/weekly-summary.sh
# Database health check
docker-compose exec timescaledb psql -U postgres -d market_data -c "SELECT COUNT(*) FROM market_data;"
```

---

## Decision: Which Guide to Use?

**I have 30 minutes:**
→ Use [DEPLOY_QUICKSTART.md](DEPLOY_QUICKSTART.md)  
One-page guide with essential commands only

**I have 2-3 hours:**
→ Use [DEPLOY_QUICKSTART.md](DEPLOY_QUICKSTART.md) + [MONITORING_SETUP.md](MONITORING_SETUP.md)  
Deploy and setup monitoring in one go

**I want all the details:**
→ Read [WEEK5_PLAN.md](WEEK5_PLAN.md) first  
Then follow each day as written

**I need to troubleshoot:**
→ Check [QUICK_REFERENCE.md](QUICK_REFERENCE.md)  
Common commands and fixes

**I want to understand the system:**
→ Start with [README.md](README.md)  
Then read [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Contact Points

**Repository:**
https://github.com/Slopez2023/Market-Data-Warehouse-API

**Main Branch:**
All Week 5 files committed and ready to deploy

**API Endpoint (after deployment):**
http://localhost:8000/docs (interactive API docs)

---

## Success! What's Next?

After Week 5 deployment:

**Week 6:** Monitor production for 1-2 weeks, collect metrics
**Week 7:** Optimize based on real-world data, consider enhancements:
- Add more symbols
- Implement caching layer (Redis)
- Build analytics dashboard
- Setup Grafana for metrics
- Add data export endpoints

---

## Final Checklist Before Deploying

- [ ] Read DEPLOY_QUICKSTART.md (5 min)
- [ ] Review WEEK5_PLAN.md (15 min)
- [ ] Prepare Proxmox VM (30 min)
- [ ] Have Polygon API key ready
- [ ] Choose strong DB password
- [ ] Have 100GB+ disk space available
- [ ] Verify network connectivity

**Ready? Start with [DEPLOY_QUICKSTART.md](DEPLOY_QUICKSTART.md)** 🚀

---

*Last updated: November 9, 2025*  
*Project status: Production-ready*  
*Next phase: Deployment week*
