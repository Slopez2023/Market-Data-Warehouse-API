# API Endpoints Reference

**Interactive Docs:** http://localhost:8000/docs  
**Alternative Docs:** http://localhost:8000/redoc

## Health & Status (4 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (no auth required) |
| GET | `/api/v1/status` | API status with database metrics |
| GET | `/api/v1/symbols` | List all tracked symbols |
| GET | `/api/v1/symbols/detailed` | Symbols with detailed stats |

## Market Data (3 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/historical/{symbol}` | Historical OHLCV data |
| GET | `/{symbol}/candles` | Candles (alias for historical) |
| GET | `/{symbol}` | Symbol info |

**Example:**
```bash
curl "http://localhost:8000/api/v1/historical/AAPL?timeframe=1d&start=2025-01-01&end=2025-12-31&limit=10"
```

## Features & Enrichment (5 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/features/quant/{symbol}` | AI-ready quant features (technical indicators) |
| GET | `/api/v1/features/composite/{symbol}` | Composite multi-source features |
| GET | `/api/v1/features/importance` | Feature importance rankings |
| POST | `/api/v1/enrich` | Trigger manual enrichment |
| POST | `/api/v1/enrichment/trigger` | Alternative enrichment trigger |

**Status (requires table fix):**
```bash
GET /api/v1/enrichment/status/{symbol}      # ⚠️  Schema issue - being fixed
GET /api/v1/enrichment/metrics              # ⚠️  Schema issue - being fixed
GET /api/v1/enrichment/dashboard/overview   # ⚠️  Schema issue - being fixed
GET /api/v1/enrichment/dashboard/metrics    # ⚠️  Schema issue - being fixed
GET /api/v1/enrichment/dashboard/health     # ⚠️  Schema issue - being fixed
GET /api/v1/enrichment/history              # ⚠️  Schema issue - being fixed
```

## Data Quality (1 endpoint)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/data/quality/{symbol}` | Data quality report |

**Example:**
```bash
curl "http://localhost:8000/api/v1/data/quality/AAPL?days=7"
```

## Backfill & Jobs (4 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/backfill` | Trigger master backfill job |
| GET | `/api/v1/backfill/status/{job_id}` | Get backfill job status |
| GET | `/api/v1/backfill/recent` | List recent backfill jobs |
| GET | `/api/v1/admin/scheduler-health` | Scheduler health & freshness |

**Example:**
```bash
curl -X POST http://localhost:8000/api/v1/backfill \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["AAPL", "MSFT"],
    "start_date": "2025-01-01",
    "end_date": "2025-12-31",
    "timeframes": ["1d", "1h"]
  }'
```

## Admin (14 endpoints)

### Symbols Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/symbols` | List tracked symbols (requires API key) |
| GET | `/api/v1/admin/symbols/{symbol}` | Get symbol details |
| POST | `/api/v1/admin/symbols` | Add new symbol |
| PUT | `/api/v1/admin/symbols/{symbol}` | Update symbol |
| PUT | `/api/v1/admin/symbols/{symbol}/timeframes` | Update timeframes |
| DELETE | `/api/v1/admin/symbols/{symbol}` | Remove symbol |

### API Keys
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/api-keys` | List API keys (requires auth) |
| GET | `/api/v1/admin/api-keys/{key_id}` | Get API key details |
| GET | `/api/v1/admin/api-keys/{key_id}/audit` | API key audit log |
| POST | `/api/v1/admin/api-keys` | Create new API key |
| PUT | `/api/v1/admin/api-keys/{key_id}` | Update API key |
| DELETE | `/api/v1/admin/api-keys/{key_id}` | Revoke API key |

### Monitoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/features/staleness` | Feature staleness report |
| GET | `/api/v1/admin/scheduler/execution-history` | Scheduler execution history |

## Observability (2 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/observability/metrics` | System metrics |
| GET | `/api/v1/observability/alerts` | Active alerts |

## Performance (3 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/performance/summary` | Performance summary |
| GET | `/api/v1/performance/cache` | Cache hit/miss stats |
| GET | `/api/v1/performance/queries` | Slow query log |

## Advanced Features (5 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/volatility/regime/{symbol}` | Volatility regime analysis |
| GET | `/api/v1/sentiment/{symbol}` | Sentiment analysis |
| GET | `/api/v1/sentiment/compare` | Compare sentiment across symbols |
| GET | `/api/v1/earnings/{symbol}` | Earnings data |
| GET | `/api/v1/earnings/{symbol}/summary` | Earnings summary |
| GET | `/api/v1/earnings/upcoming` | Upcoming earnings |
| GET | `/api/v1/news/{symbol}` | News & events |
| GET | `/api/v1/options/iv/{symbol}` | Options implied volatility |

## Dashboard & Static (4 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard` | Dashboard homepage |
| GET | `/dashboard/` | Dashboard (with trailing slash) |
| GET | `/dashboard/index.html` | Dashboard HTML |
| GET | `/dashboard/{filename}` | Dashboard static files |

## Testing (2 endpoints)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/tests/run` | Run system tests |
| POST | `/api/v1/tests/run` | Trigger test suite |

## Metrics (1 endpoint)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/metrics` | API metrics (requests, latency, etc.) |

---

## Known Issues & Missing Tables

### Broken Endpoints (Schema Mismatch)
These endpoints fail because `enrichment_status` table doesn't exist:
- `/api/v1/enrichment/status/{symbol}`
- `/api/v1/enrichment/metrics`
- `/api/v1/enrichment/dashboard/*`
- `/api/v1/enrichment/history`

**Status:** Features are computed inline in `market_data` table. Dedicated enrichment_status table planned in next release.

**Workaround:** Use `/api/v1/data/quality/{symbol}` for quality metrics instead.

---

## Authentication

### API Key Header
Most admin/sensitive endpoints require:
```bash
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8000/api/v1/admin/symbols
```

### Public Endpoints (No Auth)
- `/health`
- `/api/v1/status`
- `/api/v1/symbols`
- `/api/v1/historical/{symbol}`
- `/dashboard/*`

---

## Query Parameters

### Common Parameters

**timeframe** - Candlestick interval
```
1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
```

**start/end** - Date range
```
Format: YYYY-MM-DD
Example: start=2025-01-01&end=2025-12-31
```

**limit** - Max records to return
```
Default: 500, Max: 10,000
```

**days** - Historical days to analyze
```
Default: 7, Max: 365
```

---

## Response Format

All responses use JSON. Example:
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "data": [...],
  "count": 222,
  "timestamp": "2025-11-20T00:15:44Z"
}
```

---

## Rate Limiting

- **Free tier (Polygon):** 5 requests/minute
- **API responses:** Immediate, no rate limiting on wrapper
- **Backfill jobs:** Queued, respects Polygon rate limits

---

## Troubleshooting

### Feature endpoints return 404
→ Run `python backfill_features.py` to compute features

### Admin endpoints require API key
→ Use `/api/v1/admin/api-keys` to create one first

### Enrichment endpoints error
→ Known schema issue, use `/api/v1/data/quality/{symbol}` instead

### Data is stale
→ Check `/api/v1/admin/scheduler-health` to verify scheduler is running
