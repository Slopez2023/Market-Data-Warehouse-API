# Cryptocurrency Support

Complete guide to working with cryptocurrency symbols and endpoints in the Market Data API.

---

## Overview

The Market Data API includes full support for cryptocurrency data from Polygon.io.

**Supported Cryptocurrencies**:
- Bitcoin (BTC, BTC-USD)
- Ethereum (ETH, ETH-USD)
- Solana (SOL, SOL-USD)
- Dogecoin (DOGE, DOGE-USD)
- Shiba Inu (SHIB, SHIB-USD)
- And 100+ other cryptocurrencies

**Data Available**:
- OHLCV (Open, High, Low, Close, Volume)
- Real-time quotes
- Historical daily bars
- Intraday data (minute-by-minute)

---

## Cryptocurrency Symbols

### Format

Crypto symbols can be in multiple formats:
- `BTC` - Short format
- `BTC-USD` - Currency pair
- `BTC-USDT` - Stablecoin pair

All formats are supported and normalized automatically.

### Pre-loaded Cryptocurrencies

On bootstrap:
- BTC (Bitcoin)
- ETH (Ethereum)
- SOL (Solana)

Additional cryptocurrencies can be added via the API.

---

## Adding Cryptocurrency Symbols

### Via API

**Requires**: Admin API key

```bash
export API_KEY="mdw_your_key_here"

# Add Bitcoin
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC",
    "asset_class": "crypto"
  }'

# Add Ethereum
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETH",
    "asset_class": "crypto"
  }'

# Add alternative cryptocurrency
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "DOGE",
    "asset_class": "crypto"
  }'
```

### Batch Add Multiple Cryptos

```bash
for crypto in BTC ETH SOL DOGE SHIB XRP ADA MATIC; do
  curl -X POST http://localhost:8000/api/v1/admin/symbols \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"symbol\": \"$crypto\", \"asset_class\": \"crypto\"}"
done
```

---

## Fetching Cryptocurrency Data

### Get Crypto Daily Bars

```bash
curl "http://localhost:8000/api/v1/bars?symbol=BTC&limit=10"
```

Response:
```json
{
  "status": "success",
  "data": [
    {
      "symbol": "BTC",
      "timestamp": "2025-11-10T00:00:00Z",
      "open": 45250.50,
      "high": 45750.75,
      "low": 45100.00,
      "close": 45620.25,
      "volume": 1250000000,
      "vwap": 45500.50
    },
    {
      "symbol": "BTC",
      "timestamp": "2025-11-09T00:00:00Z",
      "open": 44800.00,
      "high": 45350.25,
      "low": 44750.00,
      "close": 45250.50,
      "volume": 1350000000,
      "vwap": 45050.25
    }
  ]
}
```

### Get Crypto Quotes

```bash
curl "http://localhost:8000/api/v1/quotes?symbol=BTC"
```

Response:
```json
{
  "status": "success",
  "data": {
    "symbol": "BTC",
    "bid": 45620.00,
    "ask": 45625.00,
    "bid_size": 2.5,
    "ask_size": 3.2,
    "timestamp": "2025-11-10T14:30:00Z"
  }
}
```

### Get Multiple Cryptocurrencies

```bash
# Get Bitcoin, Ethereum, and Solana
curl "http://localhost:8000/api/v1/bars?symbols=BTC,ETH,SOL&limit=5"
```

---

## Cryptocurrency Endpoints

### Available Crypto Endpoints

All endpoints work with both stocks and crypto:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/bars` | GET | Historical daily/intraday bars |
| `/api/v1/quotes` | GET | Real-time quotes |
| `/api/v1/tickers` | GET | Market snapshot |
| `/api/v1/symbols` | GET | List crypto symbols |

### Querying Crypto Only

Filter by asset class:

```bash
# Get only crypto symbols
curl "http://localhost:8000/api/v1/symbols?asset_class=crypto"

# Get crypto data
curl "http://localhost:8000/api/v1/bars?symbol=BTC&asset_class=crypto"
```

---

## Python Integration

### Basic Usage

```python
import requests
from datetime import datetime, timedelta

# Get Bitcoin data
response = requests.get(
    "http://localhost:8000/api/v1/bars",
    params={
        "symbol": "BTC",
        "limit": 10
    }
)

bars = response.json()["data"]
for bar in bars:
    print(f"{bar['timestamp']}: ${bar['close']}")
```

### Full Example

```python
import requests
import pandas as pd

def get_crypto_data(symbol, days=30):
    """Get crypto OHLCV data"""
    response = requests.get(
        "http://localhost:8000/api/v1/bars",
        params={
            "symbol": symbol,
            "limit": days
        }
    )
    
    data = response.json()["data"]
    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.set_index('timestamp')

def analyze_crypto(symbol):
    """Analyze crypto price data"""
    df = get_crypto_data(symbol, days=30)
    
    return {
        "symbol": symbol,
        "current_price": df['close'].iloc[-1],
        "daily_change": df['close'].pct_change().iloc[-1],
        "ma_7": df['close'].rolling(7).mean().iloc[-1],
        "ma_30": df['close'].rolling(30).mean().iloc[-1],
        "volatility": df['close'].pct_change().std(),
    }

# Analyze Bitcoin
btc_analysis = analyze_crypto("BTC")
print(f"Bitcoin: ${btc_analysis['current_price']}")
print(f"7-day MA: ${btc_analysis['ma_7']}")
print(f"30-day volatility: {btc_analysis['volatility']:.2%}")
```

---

## JavaScript Integration

### Fetch Crypto Data

```javascript
async function getCryptoData(symbol, limit = 10) {
  const response = await fetch(
    `http://localhost:8000/api/v1/bars?symbol=${symbol}&limit=${limit}`
  );
  const json = await response.json();
  return json.data;
}

async function main() {
  const btcData = await getCryptoData("BTC", 5);
  console.log("Bitcoin data:", btcData);
  
  btcData.forEach(bar => {
    console.log(`${bar.timestamp}: $${bar.close}`);
  });
}

main();
```

---

## Supported Cryptocurrencies

### Major Cryptocurrencies

| Symbol | Name | Status |
|--------|------|--------|
| BTC | Bitcoin | ✅ Supported |
| ETH | Ethereum | ✅ Supported |
| SOL | Solana | ✅ Supported |
| ADA | Cardano | ✅ Supported |
| XRP | Ripple | ✅ Supported |
| DOT | Polkadot | ✅ Supported |
| DOGE | Dogecoin | ✅ Supported |
| SHIB | Shiba Inu | ✅ Supported |

### Stablecoins

| Symbol | Name | Status |
|--------|------|--------|
| USDT | Tether | ✅ Supported |
| USDC | USD Coin | ✅ Supported |
| DAI | Dai | ✅ Supported |
| BUSD | Binance USD | ✅ Supported |

### 100+ More

Any cryptocurrency ticker available on Polygon.io is supported. Add via the API:

```bash
curl -X POST http://localhost:8000/api/v1/admin/symbols \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "YOUR_SYMBOL", "asset_class": "crypto"}'
```

---

## Data Quality for Crypto

### Characteristics

Crypto data differs from stock data:

| Aspect | Stocks | Crypto |
|--------|--------|--------|
| **Trading Hours** | Market hours | 24/7 |
| **Volume** | Daily | 24-hour |
| **Volatility** | Moderate | High |
| **Gaps** | Rare | Possible |
| **Liquidity** | Depends on stock | Depends on exchange |

### Handling Gaps

Crypto markets may have data gaps. The system handles this:

```python
import pandas as pd

def fill_crypto_gaps(df):
    """Fill missing data points"""
    df = df.set_index('timestamp').sort_index()
    df = df.resample('1D').ffill()  # Forward fill
    return df.reset_index()
```

---

## Crypto Trading Pairs

### Format Options

Crypto can be quoted in different pairs:

```bash
# Bitcoin in USD
curl "http://localhost:8000/api/v1/bars?symbol=BTC-USD"

# Bitcoin in USDT
curl "http://localhost:8000/api/v1/bars?symbol=BTC-USDT"

# Ethereum in USD
curl "http://localhost:8000/api/v1/bars?symbol=ETH-USD"
```

All formats return the same data, normalized to the base quote.

---

## Monitoring Crypto Data

### Check Crypto Symbol Status

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/admin/symbols?asset_class=crypto"
```

Response:
```json
{
  "status": "success",
  "data": [
    {
      "id": "symbol_uuid",
      "symbol": "BTC",
      "asset_class": "crypto",
      "active": true,
      "backfill_status": "completed",
      "data_points": 500,
      "date_range": {
        "start": "2024-01-01",
        "end": "2025-11-10"
      }
    }
  ]
}
```

### Get Crypto Statistics

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/admin/symbols/stats?asset_class=crypto"
```

---

## Performance with Crypto

### Caching

Crypto data is cached like stock data:

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/performance/cache-stats"
```

### Response Times

Expected response times:
- **Cached**: <50ms
- **Uncached**: 100-500ms
- **Batch queries**: 200-1000ms

---

## Error Handling

### Symbol Not Found

```json
{
  "status": "error",
  "error": "Symbol not found",
  "code": "SYMBOL_001",
  "details": {"symbol": "INVALID"}
}
```

### No Data Available

```json
{
  "status": "error",
  "error": "No data available for this symbol",
  "code": "DATA_001",
  "details": {"symbol": "BTC", "reason": "backfill_pending"}
}
```

### Polygon.io Error

If Polygon.io service is unavailable:

```json
{
  "status": "error",
  "error": "External data provider error",
  "code": "PROVIDER_001",
  "details": {"message": "Service temporarily unavailable"}
}
```

---

## Common Use Cases

### Track Multiple Cryptocurrencies

```python
cryptos = ["BTC", "ETH", "SOL", "DOGE"]
for crypto in cryptos:
    data = get_crypto_data(crypto, days=7)
    print(f"{crypto}: ${data['close'].iloc[-1]}")
```

### Detect Trading Signals

```python
def rsi(prices, period=14):
    """Calculate Relative Strength Index"""
    deltas = prices.diff()
    seed = deltas[:period+1]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down
    return 100 - 100 / (1 + rs)

def detect_signal(symbol):
    df = get_crypto_data(symbol, days=30)
    rsi_value = rsi(df['close'])
    
    if rsi_value < 30:
        return f"{symbol} is oversold (RSI: {rsi_value:.1f})"
    elif rsi_value > 70:
        return f"{symbol} is overbought (RSI: {rsi_value:.1f})"
    return None

print(detect_signal("BTC"))
```

### Compare Crypto vs Stock Volatility

```python
def compare_volatility():
    stocks = get_crypto_data("AAPL", days=30)
    crypto = get_crypto_data("BTC", days=30)
    
    stock_vol = stocks['close'].pct_change().std()
    crypto_vol = crypto['close'].pct_change().std()
    
    return {
        "AAPL": stock_vol,
        "BTC": crypto_vol,
        "ratio": crypto_vol / stock_vol
    }

comparison = compare_volatility()
print(f"Crypto is {comparison['ratio']:.1f}x more volatile")
```

---

## Best Practices

### 1. Symbol Management
- Add only cryptocurrencies you plan to use
- Monitor backfill status
- Remove unused symbols periodically

### 2. Data Handling
- Handle 24/7 trading hours
- Account for high volatility
- Fill data gaps appropriately
- Validate data quality

### 3. Performance
- Use caching for frequently accessed symbols
- Batch requests when possible
- Monitor response times
- Implement exponential backoff for retries

### 4. Security
- Store API keys securely
- Monitor API usage in audit logs
- Use separate keys for different applications
- Rotate keys regularly

---

## Troubleshooting

### Crypto Data Not Available
1. Check symbol is added and active
2. Check backfill has completed
3. Verify Polygon.io has data
4. Check database connectivity
5. Review logs

### Symbols Not Appearing
1. Check asset_class filter
2. Symbol may be inactive
3. Backfill may be pending
4. Try refreshing

### Performance Issues
1. Check cache stats
2. Monitor query patterns
3. Consider pagination
4. Use asset class filters

---

## API Reference

### Add Crypto Symbol
```
POST /api/v1/admin/symbols
X-API-Key: <admin_key>
Content-Type: application/json

{
  "symbol": "BTC",
  "asset_class": "crypto"
}
```

### Get Crypto Data
```
GET /api/v1/bars?symbol=BTC&limit=10
```

### Get All Crypto Symbols
```
GET /api/v1/symbols?asset_class=crypto
X-API-Key: <admin_key>  [optional]
```

### Get Crypto Stats
```
GET /api/v1/admin/symbols/stats?asset_class=crypto
X-API-Key: <admin_key>
```

---

## Next Steps

- [Symbol Management](/docs/api/SYMBOLS.md) - Managing all symbols
- [Endpoints Reference](/docs/api/ENDPOINTS.md) - All available endpoints
- [Authentication Guide](/docs/api/AUTHENTICATION.md) - API key management
- [Deployment Guide](/docs/operations/DEPLOYMENT.md) - Production setup

---

**Status**: Production Ready ✅  
**Last Updated**: November 10, 2025  
**Tests Passing**: 24 (Crypto Support)
