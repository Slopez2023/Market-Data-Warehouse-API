# API Endpoints Reference

Complete documentation of all Market Data API endpoints.

---

## API Overview

**Base URL (Local):** `http://localhost:8000`  
**Base URL (Production):** `http://<your-proxmox-ip>:8000`  
**Authentication:** None (trusted LAN only)  
**Rate Limits:** None (internal use)  
**Response Format:** JSON

---

## Endpoint: GET /health

Health check endpoint. Use this to verify the API is running.

### Purpose
Quick system health check. Returns status, timestamp, and scheduler state.

### Request
```bash
curl http://localhost:8000/health
```

### Response (200 OK)
```json
{
  "status": "healthy",
  "timestamp": "2025-11-09T16:30:45.123456",
  "scheduler_running": true
}
```

### Status Codes
- **200 OK** — API is healthy and responding
- **500 Internal Server Error** — Something is wrong (check logs)

### When to Use
- Verify API is up before making requests
- Monitor endpoint health
- Dashboard auto-calls this every 10 seconds

### Example (Python)
```python
import requests

response = requests.get("http://localhost:8000/health")
if response.status_code == 200:
    data = response.json()
    print(f"Status: {data['status']}")
    print(f"Scheduler running: {data['scheduler_running']}")
```

### Example (JavaScript)
```javascript
fetch('http://localhost:8000/health')
  .then(r => r.json())
  .then(data => {
    console.log(`API Status: ${data.status}`);
    console.log(`Scheduler: ${data.scheduler_running ? 'Running' : 'Stopped'}`);
  });
```

---

## Endpoint: GET /api/v1/status

System monitoring endpoint. Returns database metrics and data quality indicators.

### Purpose
Get real-time system status including database health, validation rates, and scheduler state.

### Request
```bash
curl http://localhost:8000/api/v1/status
```

### Response (200 OK)
```json
{
  "api_version": "1.0.0",
  "status": "healthy",
  "database": {
    "symbols_available": 18,
    "latest_data": "2025-11-08T00:00:00",
    "total_records": 18373,
    "validation_rate_pct": 99.7
  },
  "data_quality": {
    "records_with_gaps_flagged": 57,
    "scheduler_status": "running",
    "last_backfill": "check symbol_status table"
  }
}
```

### Response Fields Explained

**api_version**  
Current API version (1.0.0)

**status**  
Overall system status: "healthy" or "error"

**database.symbols_available**  
Number of unique stock symbols in database. Increases as backfill runs for new symbols.

**database.latest_data**  
Most recent candle timestamp in database. Shows data freshness. Should be recent trading day.

**database.total_records**  
Total number of OHLCV candles in database. Grows daily with backfill.

**database.validation_rate_pct**  
Percentage of candles with quality_score ≥ 0.85 (validated).  
- **>95%** = Good (expected)
- **90-95%** = Acceptable
- **<90%** = Review data quality

**data_quality.records_with_gaps_flagged**  
Count of candles with gap_detected=true (potential stock splits, anomalies).  
Usually <1% of total records. Review flagged records for anomalies.

**data_quality.scheduler_status**  
"running" or "stopped". Auto-backfill job status.  
Should be "running" for production.

### Status Codes
- **200 OK** — Status returned successfully
- **500 Internal Server Error** — Database query failed (check logs)

### Query Parameters
None

### When to Use
- Monitor system health (dashboard calls every 10s)
- Track validation rate trends
- Verify backfill is completing
- Debug data quality issues

### Example (Python)
```python
import requests
import json

response = requests.get("http://localhost:8000/api/v1/status")
status = response.json()

print(f"Symbols: {status['database']['symbols_available']}")
print(f"Records: {status['database']['total_records']:,}")
print(f"Validation Rate: {status['database']['validation_rate_pct']}%")
print(f"Latest Data: {status['database']['latest_data']}")

# Alert if validation rate is low
if status['database']['validation_rate_pct'] < 90:
    print("⚠️ WARNING: Low validation rate detected!")
```

### Example (JavaScript)
```javascript
fetch('http://localhost:8000/api/v1/status')
  .then(r => r.json())
  .then(status => {
    console.log(`Database has ${status.database.total_records.toLocaleString()} records`);
    console.log(`Latest data: ${status.database.latest_data}`);
    console.log(`Validation rate: ${status.database.validation_rate_pct}%`);
  });
```

---

## Endpoint: GET /api/v1/historical/{symbol}

Fetch historical OHLCV data for a symbol with configurable timeframe.

### Purpose
Query validated historical candlestick data with selectable timeframes. Apply date range, quality filters, and validation status filters. Supports 7 timeframes: 5m, 15m, 30m, 1h, 4h, 1d, 1w.

### Request
```bash
curl "http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31&timeframe=1d"
```

### Request Parameters

**Path Parameter:**
- `symbol` (required) — Stock ticker (AAPL, MSFT, GOOGL, AMZN, etc.) or crypto (BTCUSD, ETHUSD, etc.)

**Query Parameters:**
- `start` (required) — Start date in format YYYY-MM-DD
- `end` (required) — End date in format YYYY-MM-DD
- `timeframe` (required) — Candle timeframe: `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, or `1w`
- `validated_only` (optional, default: true) — Filter to quality_score ≥ min_quality
- `min_quality` (optional, default: 0.85) — Minimum quality score (0.0-1.0)

### Response (200 OK)
```json
{
  "symbol": "AAPL",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "count": 252,
  "data": [
    {
      "time": "2023-01-03T00:00:00Z",
      "symbol": "AAPL",
      "open": 150.25,
      "high": 152.50,
      "low": 149.50,
      "close": 151.00,
      "volume": 50000000,
      "quality_score": 0.95,
      "validated": true,
      "gap_detected": false,
      "volume_anomaly": false
    },
    {
      "time": "2023-01-04T00:00:00Z",
      "symbol": "AAPL",
      "open": 151.10,
      "high": 153.20,
      "low": 150.80,
      "close": 152.50,
      "volume": 48000000,
      "quality_score": 1.0,
      "validated": true,
      "gap_detected": false,
      "volume_anomaly": false
    },
    ...
  ]
}
```

### Response Fields Explained

**symbol**  
The stock ticker you requested.

**start_date, end_date**  
The date range you requested.

**count**  
Number of candles returned (filtered by date range and quality parameters).

**data[].time**  
UTC timestamp of candle (market open, 00:00 UTC).

**data[].open, high, low, close**  
OHLC prices in USD.

**data[].volume**  
Trading volume (number of shares).

**data[].quality_score**  
0.0-1.0 rating:
- **0.85-1.0** = Passed all validation checks
- **0.5-0.85** = Flagged anomalies (gap or volume spike)
- **<0.5** = Failed validation (rarely returned if validated_only=true)

**data[].validated**  
Boolean: true if quality_score ≥ min_quality

**data[].gap_detected**  
Boolean: true if overnight gap >10% (non-weekend). Flags potential stock splits, halts.

**data[].volume_anomaly**  
Boolean: true if volume >10x median or <10% median.

### Status Codes
- **200 OK** — Data returned successfully
- **404 Not Found** — Symbol not in database or no data for date range
- **422 Unprocessable Entity** — Invalid parameters (missing required, bad format)
- **500 Internal Server Error** — Database query failed (check logs)

### Examples

**Example 1: Basic Query**
```bash
curl "http://localhost:8000/api/v1/historical/MSFT?start=2023-01-01&end=2023-12-31"
```

**Example 2: Last 30 Days**
```bash
curl "http://localhost:8000/api/v1/historical/GOOGL?start=2025-10-10&end=2025-11-09"
```

**Example 3: Exclude Anomalies (quality ≥ 0.95)**
```bash
curl "http://localhost:8000/api/v1/historical/TSLA?start=2023-01-01&end=2023-12-31&min_quality=0.95"
```

**Example 4: Include All Data (even low quality)**
```bash
curl "http://localhost:8000/api/v1/historical/NVDA?start=2023-01-01&end=2023-12-31&validated_only=false&min_quality=0.0"
```

### Example (Python - Pandas Integration)
```python
import requests
import pandas as pd
from datetime import datetime, timedelta

# Fetch last 1 year of AAPL data
end_date = datetime.now().strftime('%Y-%m-%d')
start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

response = requests.get(
    f"http://localhost:8000/api/v1/historical/AAPL",
    params={
        'start': start_date,
        'end': end_date,
        'validated_only': True,
        'min_quality': 0.85
    }
)

data = response.json()
df = pd.DataFrame(data['data'])
df['time'] = pd.to_datetime(df['time'])
df = df.set_index('time')

print(df[['open', 'high', 'low', 'close', 'volume']].head())
print(f"Loaded {len(df)} candles for {data['symbol']}")
```

### Example (JavaScript - Chart.js)
```javascript
async function fetchAndPlot(symbol) {
  const response = await fetch(
    `http://localhost:8000/api/v1/historical/${symbol}?start=2023-01-01&end=2023-12-31`
  );
  const data = await response.json();

  // Extract close prices
  const closes = data.data.map(candle => parseFloat(candle.close));
  const times = data.data.map(candle => candle.time.split('T')[0]);

  // Plot with Chart.js, Plotly, etc.
  console.log(`Fetched ${data.count} candles for ${symbol}`);
  console.log(`Price range: $${Math.min(...closes).toFixed(2)} - $${Math.max(...closes).toFixed(2)}`);
}

fetchAndPlot('MSFT');
```

### Performance Notes
- Query latency: <100ms typical (TimescaleDB with index on symbol, time)
- Large date ranges (5+ years) may take 50-100ms
- Filtering by min_quality is efficient (index on validated)

---

## Endpoint: GET /api/v1/symbols

List all available symbols.

### Purpose
Get array of stock tickers available in database.

### Request
```bash
curl http://localhost:8000/api/v1/symbols
```

### Response (200 OK)
```json
{
  "symbols": [
    "AAPL",
    "AMZN",
    "GOOGL",
    "MSFT",
    "NVDA",
    "TSLA",
    ...
  ],
  "count": 18
}
```

### Response Fields
**symbols**  
Array of stock tickers available in database.

**count**  
Number of symbols (total count).

### Status Codes
- **200 OK** — Symbols returned
- **500 Internal Server Error** — Database query failed

### When to Use
- Discover what symbols are loaded
- Before querying `/api/v1/historical/{symbol}` (check symbol exists)
- Dashboard uses this to populate symbol grid

### Example (Python)
```python
import requests

response = requests.get("http://localhost:8000/api/v1/symbols")
symbols = response.json()['symbols']

print(f"Available symbols: {symbols}")
print(f"Total: {len(symbols)}")
```

### Example (JavaScript)
```javascript
fetch('http://localhost:8000/api/v1/symbols')
  .then(r => r.json())
  .then(data => {
    console.log(`${data.count} symbols available: ${data.symbols.join(', ')}`);
  });
```

---

## Endpoint: GET /dashboard

Interactive monitoring dashboard.

### Purpose
Real-time web UI showing system health, database metrics, symbol grid, and alerts.

### Access
```
Browser: http://localhost:8000/dashboard
```

### Features
- **6 Metric Cards** — Health, symbol count, record count, validation rate, gaps flagged, latest data
- **Status Badges** — Green (healthy), yellow (warning), red (critical)
- **Smart Alerts** — Low validation rate, data stale >24h, scheduler stopped, API unreachable
- **Symbol Quality Grid** — All symbols with row color-coded by quality
- **Auto-Refresh** — Updates every 10 seconds (configurable in script.js)
- **Mobile Responsive** — Works on desktop, tablet, phone
- **Dark Theme** — Professional appearance

### Data Sources
- Fetches `/health` every 10 seconds
- Fetches `/api/v1/status` every 10 seconds
- Displays most recent data in cards

### Browser Requirements
- Modern browser (Chrome, Firefox, Safari, Edge)
- JavaScript enabled
- No external dependencies (pure HTML5 + CSS3 + vanilla JS)

### Customization
See dashboard folder (index.html, style.css, script.js) for customization options.

---

## Interactive Documentation

### Swagger UI (Try-it-out)
```
http://localhost:8000/docs
```
- Interactive endpoint explorer
- Click "Try it out" to test endpoints
- See request/response examples
- Request body editor

### ReDoc (Read-only)
```
http://localhost:8000/redoc
```
- Alternative documentation view
- Clean, readable format
- Good for viewing documentation

Both auto-generated from FastAPI/OpenAPI.

---

## Data Models

### Candle Object
Single OHLCV bar for one day.

```json
{
  "time": "2023-01-03T00:00:00Z",
  "symbol": "AAPL",
  "open": 150.25,
  "high": 152.50,
  "low": 149.50,
  "close": 151.00,
  "volume": 50000000,
  "quality_score": 0.95,
  "validated": true,
  "gap_detected": false,
  "volume_anomaly": false
}
```

**Fields:**
- `time` (ISO 8601) — UTC timestamp of candle open
- `symbol` (string) — Stock ticker
- `open` (number) — Opening price USD
- `high` (number) — High price USD
- `low` (number) — Low price USD
- `close` (number) — Closing price USD
- `volume` (integer) — Trading volume (shares)
- `quality_score` (number 0-1) — Validation score
- `validated` (boolean) — quality_score ≥ min_quality
- `gap_detected` (boolean) — Overnight gap >10% flagged
- `volume_anomaly` (boolean) — Volume spike/drought flagged

### Status Response Object

```json
{
  "api_version": "1.0.0",
  "status": "healthy",
  "database": {
    "symbols_available": 18,
    "latest_data": "2025-11-08T00:00:00",
    "total_records": 18373,
    "validation_rate_pct": 99.7
  },
  "data_quality": {
    "records_with_gaps_flagged": 57,
    "scheduler_status": "running",
    "last_backfill": "check symbol_status table"
  }
}
```

### Historical Data Response Object

```json
{
  "symbol": "AAPL",
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "count": 252,
  "data": [
    { ... candle objects ... }
  ]
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "detail": "No data found for AAPL (2025-01-01 to 2025-12-31)"
}
```

### HTTP Status Codes

**200 OK**  
Request successful, data returned.

**400 Bad Request**  
Malformed request (usually from client error).

**404 Not Found**  
Resource not found (symbol doesn't exist, no data for date range).

**422 Unprocessable Entity**  
Validation error. Missing required parameter or invalid format.

Example:
```json
{
  "detail": [
    {
      "loc": ["query", "start"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**500 Internal Server Error**  
Server error (database connection failed, etc.). Check logs.

### How to Handle Errors (Python)
```python
import requests

try:
    response = requests.get(
        "http://localhost:8000/api/v1/historical/AAPL",
        params={"start": "2023-01-01", "end": "2023-12-31"}
    )
    response.raise_for_status()  # Raise on 4xx/5xx
    data = response.json()
    print(f"Loaded {data['count']} candles")

except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        print("Symbol not found")
    elif e.response.status_code == 422:
        print("Invalid parameters")
    else:
        print(f"Server error: {e.response.status_code}")
```

---

## Rate Limits & Quotas

**Current Limits (Internal Use):**
- No rate limiting
- No request quotas
- Unlimited API calls (design assumes internal LAN)

**Polygon.io Rate Limits (Data Source):**
- Free tier: 5 calls/min
- Starter tier ($29.99/mo): 150 calls/min
- Daily backfill uses ~10 calls/day (under any limit)

---

## Filtering & Querying

### Date Range Filtering
Any historical data query supports date ranges:
```bash
# Last 1 year
curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-11-09&end=2025-11-09"

# Specific month
curl "http://localhost:8000/api/v1/historical/MSFT?start=2023-01-01&end=2023-01-31"

# Single day (returns 1 candle if exists)
curl "http://localhost:8000/api/v1/historical/GOOGL?start=2023-01-03&end=2023-01-03"
```

### Quality Filtering
Filter by minimum quality score:
```bash
# Only perfect candles (0.95+)
curl "http://localhost:8000/api/v1/historical/TSLA?start=2023-01-01&end=2023-12-31&min_quality=0.95"

# All candles including anomalies
curl "http://localhost:8000/api/v1/historical/NVDA?start=2023-01-01&end=2023-12-31&validated_only=false&min_quality=0.0"

# Conservative quality threshold
curl "http://localhost:8000/api/v1/historical/AMZN?start=2023-01-01&end=2023-12-31&min_quality=0.9"
```

### Validation Status Filtering
```bash
# Validated candles only (default)
curl "http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31&validated_only=true"

# All candles (including flagged)
curl "http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31&validated_only=false"
```

### Performance Tips
- Narrow date ranges when possible (<6 months faster than 5 years)
- Use `validated_only=true` to filter out flagged anomalies quickly
- Index on (symbol, time DESC) makes queries fast regardless of date range
- Typical query: <100ms for any symbol, any date range

---

## Version Info

**API Version:** 1.0.0  
**Python:** 3.11+  
**FastAPI:** 0.104.1  
**OpenAPI Version:** 3.0.0

---

## Support

For API questions or issues:
1. Check [README.md](README.md) for overview
2. Check [INSTALLATION.md](INSTALLATION.md) for deployment
3. Check [OPERATIONS.md](OPERATIONS.md) for troubleshooting
4. View logs: `docker-compose logs -f api`
5. Try interactive docs: `http://localhost:8000/docs`
