# Symbol Management

Complete guide to managing market symbols in the Market Data API.

---

## Overview

Symbols represent tradeable assets in the system:
- **Stocks**: AAPL, MSFT, GOOGL, etc.
- **Crypto**: BTC, ETH, SOL, etc.

Each symbol has:
- Unique identifier
- Asset class (stock/crypto)
- Active status
- Backfill status
- Statistics

---

## Symbol Structure

```json
{
  "id": "symbol_uuid",
  "symbol": "AAPL",
  "asset_class": "stock",
  "active": true,
  "timeframes": ["1h", "1d"],
  "backfill_status": "completed",
  "data_points": 2000,
  "date_range": {
    "start": "2024-01-01",
    "end": "2025-11-10"
  },
  "last_updated": "2025-11-10T14:00:00Z"
}
```

---

## Timeframe Configuration

Each symbol can have multiple timeframes configured for data collection:

### Supported Timeframes
- `5m` — 5-minute candles (intraday)
- `15m` — 15-minute candles (intraday)
- `30m` — 30-minute candles (intraday)
- `1h` — Hourly candles (intraday)
- `4h` — 4-hour candles (intraday)
- `1d` — Daily candles (default)
- `1w` — Weekly candles

### Default Configuration
New symbols are created with `['1h', '1d']` timeframes by default.

### Update Timeframes

```bash
curl -X PUT http://localhost:8000/api/v1/admin/symbols/AAPL/timeframes \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "timeframes": ["5m", "1h", "4h", "1d"]
  }'
```

Response:
```json
{
  "symbol": "AAPL",
  "asset_class": "stock",
  "active": true,
  "timeframes": ["5m", "1h", "4h", "1d"],
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T14:30:00Z"
}
```

### Python Example
```python
import requests

api_key = "your-api-key"
headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
body = {"timeframes": ["5m", "1h", "1d"]}

response = requests.put(
    "http://localhost:8000/api/v1/admin/symbols/AAPL/timeframes",
    headers=headers,
    json=body
)
symbol = response.json()
print(f"Updated {symbol['symbol']} with timeframes: {symbol['timeframes']}")
```

---

## Asset Classes

### Stock
Trade on traditional stock exchanges:
- US Stocks: AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, etc.
- ETFs: SPY, QQQ, IVV, etc.

### Crypto
Digital assets and cryptocurrencies:
- Bitcoin: BTC, BTC-USD
- Ethereum: ETH, ETH-USD
- Altcoins: SOL, DOGE, SHIB, etc.

---

## Adding Symbols

### Via API

**Requires**: Admin API key

```bash
export API_KEY="mdw_your_key_here"

# Add a stock
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "asset_class": "stock"
  }'

# Add cryptocurrency
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "asset_class": "crypto"
  }'
```

Response:
```json
{
  "status": "success",
  "data": {
    "id": "symbol_uuid",
    "symbol": "AAPL",
    "asset_class": "stock",
    "active": true,
    "backfill_status": "pending",
    "created_at": "2025-11-10T14:00:00Z"
  }
}
```

### Python Example

```python
import requests

api_key = "mdw_your_key_here"
headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

# Add symbol
response = requests.post(
    "http://localhost:8000/api/v1/admin/symbols",
    headers=headers,
    json={"symbol": "AAPL", "asset_class": "stock"}
)

symbol = response.json()["data"]
print(f"Created symbol: {symbol['symbol']}")
```

---

## Listing Symbols

### Get All Symbols

```bash
curl http://localhost:8000/api/v1/symbols
```

Response:
```json
{
  "status": "success",
  "data": [
    {
      "symbol": "AAPL",
      "asset_class": "stock",
      "active": true
    },
    {
      "symbol": "MSFT",
      "asset_class": "stock",
      "active": true
    },
    {
      "symbol": "BTC",
      "asset_class": "crypto",
      "active": true
    }
  ]
}
```

### Get Symbols with Details

Admin-only endpoint with full details:

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/admin/symbols?include_inactive=false"
```

Response:
```json
{
  "status": "success",
  "data": [
    {
      "id": "symbol_uuid",
      "symbol": "AAPL",
      "asset_class": "stock",
      "active": true,
      "backfill_status": "completed",
      "data_points": 2000,
      "date_range": {
        "start": "2024-01-01",
        "end": "2025-11-10"
      },
      "last_updated": "2025-11-10T14:00:00Z"
    }
  ]
}
```

### Get Specific Symbol

```bash
# Public endpoint
curl http://localhost:8000/api/v1/symbols/AAPL

# Admin endpoint with details (includes timeframes)
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v1/admin/symbols/AAPL
```

Response:
```json
{
  "symbol": "AAPL",
  "asset_class": "stock",
  "active": true,
  "timeframes": ["1h", "1d"],
  "first_trade_date": "2023-01-01",
  "created_at": "2025-11-11T10:00:00Z",
  "updated_at": "2025-11-11T14:30:00Z"
}
```

### Filter by Asset Class

```bash
# Get only stocks
curl "http://localhost:8000/api/v1/symbols?asset_class=stock"

# Get only crypto
curl "http://localhost:8000/api/v1/symbols?asset_class=crypto"
```

---

## Updating Symbols

### Update Active Status

```bash
curl -X PUT http://localhost:8000/api/v1/admin/symbols/{symbol_id} \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"active": false}'
```

### Update Timeframes

```bash
curl -X PUT http://localhost:8000/api/v1/admin/symbols/{symbol}/timeframes \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"timeframes": ["5m", "1h", "1d", "1w"]}'
```

**Note:** Timeframes are automatically deduplicated and sorted. Scheduler will backfill all configured timeframes daily.

### Update Backfill Status

The system automatically tracks backfill progress:
- `pending` - Waiting to be backfilled
- `in_progress` - Currently backfilling
- `completed` - Backfill finished
- `failed` - Backfill encountered error

View status:
```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/admin/symbols?show_backfill_status=true"
```

---

## Symbol Statistics

### Get Symbol Stats

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/admin/symbols/stats"
```

Response:
```json
{
  "status": "success",
  "data": {
    "total_symbols": 15,
    "active_symbols": 14,
    "by_asset_class": {
      "stock": 12,
      "crypto": 3
    },
    "backfill_status": {
      "completed": 12,
      "in_progress": 2,
      "pending": 1,
      "failed": 0
    },
    "total_data_points": 45000,
    "coverage": {
      "complete": 12,
      "partial": 2,
      "incomplete": 1
    }
  }
}
```

---

## Deleting Symbols

### Soft Delete

Deactivate a symbol (data preserved):

```bash
curl -X DELETE http://localhost:8000/api/v1/admin/symbols/{symbol_id} \
  -H "X-API-Key: $API_KEY"
```

**Note**: Data is preserved and symbol can be reactivated.

---

## Available Symbols

### Pre-loaded Symbols

On bootstrap, these symbols are created:

**Stocks** (12):
- AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA
- META, NFLX, AMD, INTC, PYPL, SQ

**Crypto** (3):
- BTC, ETH, SOL

**Other**:
- ROKU, MSTR, SOFI

### Adding More Symbols

Create new symbols as needed:

```bash
# Add a stock
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "IBM", "asset_class": "stock"}'

# Add crypto
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "DOGE", "asset_class": "crypto"}'
```

---

## Symbol Name Case

Symbols are normalized to uppercase:
- Input: `aapl` → Stored: `AAPL`
- Input: `Btc` → Stored: `BTC`
- Input: `ETH-USD` → Stored: `ETH-USD`

---

## Backfill Process

### Automatic Backfill

The scheduled job automatically backfills data:
1. Loads all active symbols from database
2. Fetches historical data from Polygon.io
3. Inserts into database
4. Updates backfill status
5. Runs daily at configured time

### Manual Trigger

Trigger backfill via API:

```bash
curl -X POST http://localhost:8000/api/v1/admin/backfill \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "BTC"]}'
```

---

## Error Handling

### Duplicate Symbol
```json
{
  "status": "error",
  "error": "Symbol already exists",
  "code": "SYMBOL_001",
  "details": {"symbol": "AAPL"}
}
```

### Invalid Asset Class
```json
{
  "status": "error",
  "error": "Invalid asset class",
  "code": "SYMBOL_002",
  "details": {"valid_classes": ["stock", "crypto"]}
}
```

### Symbol Not Found
```json
{
  "status": "error",
  "error": "Symbol not found",
  "code": "SYMBOL_003"
}
```

---

## Batch Operations

### Add Multiple Symbols

```bash
# Stock batch
for symbol in IBM F GM; do
  curl -X POST http://localhost:8000/api/v1/admin/symbols \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"symbol\": \"$symbol\", \"asset_class\": \"stock\"}"
done

# Crypto batch
for symbol in DOGE SHIB XRP; do
  curl -X POST http://localhost:8000/api/v1/admin/symbols \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"symbol\": \"$symbol\", \"asset_class\": \"crypto\"}"
done
```

### Get Batch Stats

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/admin/symbols/stats"
```

---

## API Reference

### Create Symbol
```
POST /api/v1/admin/symbols
X-API-Key: <admin_key>
Content-Type: application/json

{
  "symbol": "AAPL",
  "asset_class": "stock"
}
```

### List Symbols
```
GET /api/v1/symbols[?asset_class=stock|crypto]
```

### Get Symbol Details
```
GET /api/v1/admin/symbols/{symbol_id}
X-API-Key: <admin_key>
```

### Update Symbol
```
PUT /api/v1/admin/symbols/{symbol_id}
X-API-Key: <admin_key>
Content-Type: application/json

{
  "active": true|false
}
```

### Update Symbol Timeframes
```
PUT /api/v1/admin/symbols/{symbol}/timeframes
X-API-Key: <admin_key>
Content-Type: application/json

{
  "timeframes": ["5m", "15m", "30m", "1h", "4h", "1d", "1w"]
}
```

**Available timeframes:**
- `5m`, `15m`, `30m` — Intraday
- `1h`, `4h` — Intraday multi-hour
- `1d` — Daily (default)
- `1w` — Weekly

### Delete Symbol
```
DELETE /api/v1/admin/symbols/{symbol_id}
X-API-Key: <admin_key>
```

### Get Symbol Stats
```
GET /api/v1/admin/symbols/stats
X-API-Key: <admin_key>
```

---

## Best Practices

### 1. Symbol Selection
- Start with major symbols (AAPL, MSFT, etc.)
- Add crypto if needed (BTC, ETH)
- Only add symbols you'll actually use
- Monitor backfill status

### 2. Data Quality
- Check data points count
- Verify date ranges
- Review for gaps
- Monitor backfill status

### 3. Maintenance
- Deactivate unused symbols
- Review symbol list monthly
- Check backfill success rate
- Monitor for errors

### 4. Performance
- Too many symbols = slower backfill
- Use asset class filters
- Monitor query performance
- Archive old data periodically

---

## Troubleshooting

### Symbol Won't Backfill
1. Check symbol is active
2. Verify asset class is correct
3. Check Polygon.io has data for symbol
4. Check database connectivity
5. Review logs for errors

### Duplicate Symbol Error
1. Symbol already exists
2. Try different symbol or deactivate existing
3. Check case normalization

### No Data Points
1. Backfill may not have run yet
2. Polygon.io may not have historical data
3. Check backfill status and logs

---

## Next Steps

- [Cryptocurrency Guide](/docs/api/CRYPTO.md) - Crypto-specific symbols
- [Endpoints Reference](/docs/api/ENDPOINTS.md) - All symbol endpoints
- [Authentication Guide](/docs/api/AUTHENTICATION.md) - Admin key setup
- [Deployment Guide](/docs/operations/DEPLOYMENT.md) - Production setup

---

**Status**: Production Ready ✅  
**Last Updated**: November 10, 2025  
**Tests Passing**: 43 (Symbol Management + Crypto)
