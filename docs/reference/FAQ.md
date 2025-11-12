# Frequently Asked Questions (FAQ)

## General Questions

### What is the Market Data API?
The Market Data API is a production-ready, enterprise-grade service that provides validated market data for stocks, ETFs, and cryptocurrencies. It includes advanced analytics, multi-timeframe support, and comprehensive observability.

### Is it production-ready?
**Yes, absolutely.** All 400+ tests pass with 100% success rate. The system has been designed and tested for production use with proper error handling, monitoring, and observability.

### What data sources does it use?
The API integrates with **Polygon.io** for real-time and historical market data. We validate and enrich this data with quality scoring, anomaly detection, and consistency checks.

### Does it support cryptocurrency?
**Yes.** The API fully supports cryptocurrency data (Bitcoin, Ethereum, and 20+ other cryptocurrencies) with the same OHLCV and analytics features as stocks.

---

## API & Data

### How many symbols are supported?
Currently **60+ symbols** including:
- 20+ stocks (AAPL, MSFT, GOOGL, etc.)
- 20+ cryptocurrencies (BTC, ETH, SOL, etc.)
- 20+ ETFs (SPY, QQQ, DIA, etc.)

You can add more symbols via the admin API.

### What timeframes are available?
**7 timeframes supported:**
- 5m (5-minute)
- 15m (15-minute)
- 30m (30-minute)
- 1h (1-hour)
- 4h (4-hour)
- 1d (1-day)
- 1w (1-week)

Each symbol can be configured with different timeframes independently.

### How far back does historical data go?
Depends on the symbol and Polygon.io availability. Typically:
- Stocks: 20+ years
- ETFs: 5-20 years
- Crypto: 5-10 years

Query the API with different date ranges to test availability.

### How fresh is the data?
- **Real-time stocks**: Updated during market hours (real-time)
- **Daily data**: Updated after market close
- **Crypto data**: Updated 24/7 as the markets trade

The scheduler automatically backfills data at configured intervals (default: daily at 00:00 UTC).

### Can I query raw OHLCV data?
Yes, use the historical endpoint:
```bash
curl "http://localhost:8000/api/v1/historical/AAPL?timeframe=1d&start=2024-01-01&end=2024-12-31"
```

### What does "validated_only" mean?
When `validated_only=true`, the API filters to candles with quality_score >= min_quality. This ensures you get high-quality data. Set to `false` to get all data including lower-quality candles.

---

## Authentication & Security

### How do I authenticate?
Use API key via the `X-API-Key` header:
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/admin/...
```

### How do I create an API key?
First, you need an initial admin key configured in your environment. Then:
```bash
curl -X POST "http://localhost:8000/api/v1/admin/api-keys" \
  -H "X-API-Key: your-admin-key" \
  -d '{"name": "my-app"}'
```

### Can I revoke API keys?
Yes, delete them via:
```bash
curl -X DELETE "http://localhost:8000/api/v1/admin/api-keys/{key_id}" \
  -H "X-API-Key: your-admin-key"
```

### Is the API key logged?
Yes. All API key operations (create, update, delete, use) are logged for audit purposes. Query audit logs:
```bash
curl "http://localhost:8000/api/v1/admin/api-keys/{key_id}/audit" \
  -H "X-API-Key: your-admin-key"
```

### What's included in the audit log?
- Operation type (create, update, delete, used)
- Timestamp
- Actor (which key performed the action)
- Status (success/failure)
- Changes made

---

## Performance & Optimization

### How fast are responses?
Typically **<100ms** for cached queries, **100-500ms** for uncached queries.

### Is caching enabled?
Yes, automatic query caching with:
- Default TTL: 300 seconds (5 minutes)
- Hit rate: 40-60% for typical usage patterns

### How can I see cache statistics?
```bash
curl http://localhost:8000/api/v1/performance/cache
```

### Can I customize cache TTL?
Currently no, but you can configure it in environment variables. See [Configuration](/docs/getting-started/INSTALLATION.md#configuration).

### What if a query is slow?
1. Check cache stats: `curl http://localhost:8000/api/v1/performance/cache`
2. Review query logs: `docker logs -f market_data_api`
3. Check database metrics: `curl http://localhost:8000/api/v1/status`
4. See [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md)

---

## Deployment & Infrastructure

### Can I run this locally?
**Yes.** See [Installation Guide](/docs/getting-started/INSTALLATION.md) - Docker Compose handles all setup.

### Can I run this in production?
**Yes.** The system is production-ready. See [Deployment Guide](/docs/operations/DEPLOYMENT.md).

### What database is required?
PostgreSQL 13+ with TimescaleDB extension for time-series optimization.

### Can I scale horizontally?
Yes, the system is designed to be stateless:
- Multiple API workers via `API_WORKERS` config
- Horizontal database scaling with read replicas
- Stateless scheduler design

### Does it support Kubernetes?
Yes, the Docker image is Kubernetes-ready. See [Deployment Guide](/docs/operations/DEPLOYMENT.md#kubernetes).

### What about high availability?
Configure:
- Multiple API instances (load balanced)
- Database with replication & failover
- Persistent volumes for data

---

## Monitoring & Observability

### How do I monitor the system?
Several options:
1. **Status endpoint**: `curl http://localhost:8000/api/v1/status`
2. **Metrics endpoint**: `curl http://localhost:8000/api/v1/metrics`
3. **Dashboard**: Visit `http://localhost:3001`
4. **Logs**: `docker logs -f market_data_api`

### Can I set up email alerts?
Yes, configure in environment:
```bash
ALERT_EMAIL_ENABLED=true
SMTP_SERVER=smtp.gmail.com
ALERT_FROM_EMAIL=alerts@company.com
ALERT_TO_EMAILS=ops@company.com,dev@company.com
```

### What metrics are collected?
- Request count, latency, errors
- Cache hit rate
- Database connection pool status
- Scheduler status and backfill results
- Data quality metrics

### How do I view metrics?
```bash
# Real-time metrics
curl http://localhost:8000/api/v1/observability/metrics

# Performance summary
curl http://localhost:8000/api/v1/performance/summary

# Cache stats
curl http://localhost:8000/api/v1/performance/cache
```

---

## Testing & Development

### How many tests does it have?
**400+ tests** with 100% pass rate.

### Can I run tests locally?
Yes:
```bash
pytest tests/ -v
```

### Can I run tests via the API?
Yes:
```bash
curl http://localhost:8000/api/v1/tests/run
```

### How do I write new tests?
See [Testing Guide](/docs/development/TESTING.md).

### What's the test coverage?
100% coverage on critical paths. Coverage reports in `htmlcov/`:
```bash
pytest tests/ --cov=src --cov-report=html
```

---

## Troubleshooting

### Docker won't start
Check logs:
```bash
docker-compose logs
```

See [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md#docker-issues).

### No data is being returned
1. Verify symbols are tracked: `curl http://localhost:8000/api/v1/symbols/detailed`
2. Check backfill status: `curl http://localhost:8000/api/v1/metrics`
3. Check database: `docker exec -it market_data_db psql -U postgres -d market_data -c "SELECT COUNT(*) FROM ohlcv;"`

See [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md).

### Database connection errors
1. Check docker is running: `docker ps`
2. Check logs: `docker-compose logs market_data_db`
3. Verify DB_PASSWORD in .env
4. Check port 5432 isn't blocked

### API key authentication failing
1. Verify X-API-Key header is set
2. Check key exists: `curl http://localhost:8000/api/v1/admin/api-keys -H "X-API-Key: your-admin-key"`
3. Check key status in database
4. Verify key format (no spaces, correct case)

### Scheduler not running
1. Check status: `curl http://localhost:8000/api/v1/metrics`
2. Check logs: `docker logs -f market_data_api | grep -i scheduler`
3. Verify POLYGON_API_KEY is set
4. Check backfill history table

See full [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md).

---

## Advanced Questions

### How does multi-timeframe data aggregation work?
Each symbol's data is stored at multiple timeframes in the database. When you query a timeframe, you get the pre-aggregated candles for that timeframe. No aggregation happens at query time.

### Can I use this for machine learning?
Yes! Use the `/api/v1/features/composite/{symbol}` endpoint to get ML-ready feature vectors combining:
- Dividend metrics
- Earnings beat rates and surprises
- News sentiment
- Volatility regime
- IV metrics

### Does it support real-time subscriptions?
Not currently. This API is REST-based. For real-time, make frequent polling requests or implement WebSocket separately.

### Can I customize data validation?
Yes, see [Data Validation](/docs/features/DATA_VALIDATION.md).

### How is data consistency maintained?
- Automated validation on ingestion
- Consistency checks across timeframes
- Gap detection and flagging
- Transaction support for multi-step operations

---

## Support

**Still have questions?**
1. Check [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md)
2. Review [API Reference](/docs/api/ENDPOINTS.md)
3. See [Architecture](/docs/development/ARCHITECTURE.md) for design details
4. Review [Quick Reference](/docs/reference/QUICK_REFERENCE.md) for examples

**Getting started?**
- [Installation Guide](/docs/getting-started/INSTALLATION.md)
- [Quick Start](/docs/getting-started/QUICKSTART.md)
- [README](../../README.md)
