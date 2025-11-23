# Market Data API Client

Production-ready Python client for the Market Data Warehouse API.

## Installation

Copy `market_data_client.py` to your project and install dependencies:

```bash
pip install requests python-dotenv
```

## Setup

Create `.env` file with your credentials:

```
MARKET_DATA_API_URL=http://localhost:8000
MARKET_DATA_API_KEY=mdw_2ed1a9e0944f8c1a17b8d59a49a87e29b3529fbbeadaf6b5d3ec960ca7fba19a
```

## Quick Start

```python
from market_data_client import MarketDataClient

client = MarketDataClient()

# Get historical OHLCV data
data = client.get_historical_data(
    symbol="AAPL",
    timeframe="1d",
    start="2024-01-01",
    end="2024-12-31"
)

print(f"Got {data.count} candles")
for candle in data.candles:
    print(f"{candle.time}: {candle.close}")
```

## Core Methods

### Get Historical Data
```python
data = client.get_historical_data(
    symbol="AAPL",              # Required
    timeframe="1d",             # Optional: 5m, 15m, 30m, 1h, 4h, 1d, 1w
    start="2024-01-01",         # Required: YYYY-MM-DD
    end="2024-12-31",           # Required: YYYY-MM-DD
    validated_only=True,        # Optional: filter to validated data
    min_quality=0.85            # Optional: quality threshold 0.0-1.0
)
```

### Get Quant Features (AI Indicators)
```python
features = client.get_quant_features(
    symbol="AAPL",
    timeframe="1d",
    start="2024-01-01",
    end="2024-12-31",
    limit=500                   # Max 10000
)

for f in features.parsed_features:
    print(f"{f.time}: volatility={f.volatility_20:.4f}, trend={f.trend_direction}")
```

### Get Data Quality
```python
quality = client.get_data_quality(symbol="AAPL", days=7)
print(f"Validation: {quality['summary']['avg_validation_rate']}%")
```

### Status & Symbols
```python
status = client.get_status()        # API status and metrics
symbols = client.get_symbols()      # Available symbols count
healthy = client.health_check()     # API health check (bool)
```

## Error Handling

```python
from market_data_client import (
    ValidationError,        # Bad parameters
    AuthenticationError,    # Invalid API key
    RateLimitError,         # Rate limited
    APIConnectionError,     # Connection failed
)

try:
    data = client.get_historical_data("AAPL", timeframe="1d", start="2024-01-01", end="2024-12-31")
except ValidationError as e:
    print(f"Invalid request: {e}")
except AuthenticationError as e:
    print(f"Auth failed: {e}")
except RateLimitError as e:
    print(f"Rate limited, waiting...")
    time.sleep(60)
except APIConnectionError as e:
    print(f"Connection error: {e}")
```

## Common Patterns

### Batch Processing
```python
symbols = ["AAPL", "MSFT", "GOOGL", "BTC"]

for symbol in symbols:
    try:
        data = client.get_historical_data(
            symbol=symbol,
            timeframe="1d",
            start="2024-01-01",
            end="2024-12-31"
        )
        print(f"✓ {symbol}: {data.count} candles")
    except Exception as e:
        print(f"✗ {symbol}: {e}")
```

### With Pandas
```python
import pandas as pd

data = client.get_historical_data("AAPL", timeframe="1d", start="2024-01-01", end="2024-12-31")
df = pd.DataFrame(data.data)
df['time'] = pd.to_datetime(df['time'])
df['returns'] = df['close'].pct_change()

print(df[['close', 'volume', 'returns']].head())
```

### Context Manager (Auto Cleanup)
```python
with MarketDataClient() as client:
    data = client.get_historical_data(...)
    features = client.get_quant_features(...)
# Session automatically closed
```

## Configuration

### Environment Variables (Recommended)
```bash
MARKET_DATA_API_URL=http://localhost:8000
MARKET_DATA_API_KEY=mdw_your_key_here
MARKET_DATA_API_TIMEOUT=30
MARKET_DATA_API_VERIFY_SSL=true
```

### Constructor
```python
client = MarketDataClient(
    api_url="http://localhost:8000",
    api_key="mdw_your_key_here",
    timeout=30,
    max_retries=3,
    backoff_factor=0.5,
    verify_ssl=True
)
```

## Features

- **Automatic Retry**: 3 attempts with exponential backoff on failures
- **Connection Pooling**: Reuses HTTP connections for efficiency
- **Type Safety**: Full type hints throughout
- **Error Handling**: Specific exception types for different errors
- **Logging**: Structured logging for debugging
- **Thread-Safe**: Safe for concurrent use
- **No External Dependencies**: Only requires `requests`

## Quant Features Included

Returns from `get_quant_features()`:

- **Returns**: return_1h, return_1d
- **Volatility**: volatility_20, volatility_50, atr
- **Volume**: rolling_volume_20, volume_ratio
- **Structure**: structure_label, trend_direction
- **Regimes**: volatility_regime, trend_regime, compression_regime
- **Quality**: quality_score, validated

## Data Models

### Candle
```python
candle.time              # ISO timestamp
candle.symbol            # Stock/crypto ticker
candle.open, .high, .low, .close   # OHLC prices
candle.volume            # Trading volume
candle.validated         # Quality validated (bool)
candle.quality_score     # 0.0-1.0
candle.gap_detected      # Gap found (bool)
candle.volume_anomaly    # Anomaly detected (bool)
```

### Feature
```python
feature.time             # ISO timestamp
feature.open, .high, .low, .close   # OHLC
feature.volume           # Volume
feature.return_1d        # Daily return %
feature.volatility_20    # 20-period volatility
feature.atr              # Average true range
feature.trend_direction  # up/down/neutral
feature.volatility_regime # low/medium/high
feature.trend_regime     # uptrend/downtrend/ranging
feature.quality_score    # 0.0-1.0
```

## Supported Assets

Check available symbols:
```python
symbols = client.get_symbols()
print(f"Available: {symbols['symbols_available']}")  # 53+ symbols
```

Currently supported:
- **Stocks**: AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, etc.
- **Crypto**: BTC, ETH, SOL, XRP, ADA, DOGE, CARDANO, etc.
- **ETFs**: SPY, QQQ, IWM, EEM, GLD, TLT, etc.

## Timeframes

| Code | Period |
|------|--------|
| 5m   | 5 min  |
| 15m  | 15 min |
| 30m  | 30 min |
| 1h   | 1 hour |
| 4h   | 4 hours|
| 1d   | 1 day  |
| 1w   | 1 week |

## Troubleshooting

**Connection Error**
```
APIConnectionError: Failed to connect to API at http://localhost:8000
```
→ Check API is running and URL is correct

**Authentication Error**
```
AuthenticationError: Invalid API key
```
→ Check MARKET_DATA_API_KEY in .env

**Validation Error**
```
ValidationError: Invalid timeframe: 1D
```
→ Use lowercase: "1d" not "1D"

**Timeout**
```
APIConnectionError: Request timeout after 30s
```
→ Increase timeout: `MarketDataClient(timeout=60)`

**No Data Found**
```
HTTPException: No data found for AAPL
```
→ Check date range has data, try different timeframe

## Examples

### Example 1: Daily Stock Data
```python
client = MarketDataClient()

data = client.get_historical_data(
    "AAPL",
    timeframe="1d",
    start="2024-11-01",
    end="2024-11-30"
)

for candle in data.candles:
    print(f"{candle.time}: Close={candle.close} Vol={candle.volume}")
```

### Example 2: Hourly Crypto Data with Features
```python
features = client.get_quant_features(
    "BTC",
    timeframe="1h",
    limit=100
)

for f in features.parsed_features:
    if f.trend_direction == "up" and f.volatility_regime == "low":
        print(f"Opportunity at {f.time}: Low vol uptrend")
```

### Example 3: Data Quality Monitoring
```python
quality = client.get_data_quality("MSFT", days=30)
summary = quality['summary']

print(f"Validation Rate: {summary['avg_validation_rate']}%")
print(f"Quality Score: {summary['avg_quality_score']}")
print(f"Gaps Detected: {summary['total_gaps_detected']}")

if summary['total_gaps_detected'] > 5:
    print("Warning: Many gaps detected")
```

### Example 4: Check API Health
```python
if client.health_check():
    status = client.get_status()
    print(f"API Healthy")
    print(f"Symbols: {status['database']['symbols_available']}")
    print(f"Validation: {status['database']['validation_rate_pct']}%")
else:
    print("API is down")
```

## Performance Tips

1. **Reuse Client**: Create once, use multiple times
   ```python
   client = MarketDataClient()  # Create once
   for symbol in symbols:
       data = client.get_historical_data(symbol, ...)
   ```

2. **Batch Requests**: Request full date range at once
   ```python
   # Good: one request
   data = client.get_historical_data("AAPL", start="2024-01-01", end="2024-12-31")
   
   # Avoid: 12 requests
   for month in range(1, 13):
       data = client.get_historical_data("AAPL", start=f"2024-{month:02d}-01", ...)
   ```

3. **Use Appropriate Limits**
   ```python
   # Streaming: smaller limits
   features = client.get_quant_features("AAPL", limit=100)
   
   # Historical: larger limits
   features = client.get_quant_features("AAPL", limit=5000)
   ```

## API Endpoints Used

- `GET /health` - Health check
- `GET /api/v1/status` - API status
- `GET /api/v1/symbols` - Available symbols
- `GET /api/v1/historical/{symbol}` - OHLCV data
- `GET /api/v1/features/quant/{symbol}` - Quant features
- `GET /api/v1/data/quality/{symbol}` - Data quality report

## Support

If you encounter issues:

1. Check error message and type
2. Verify credentials in .env
3. Enable debug logging: `logging.basicConfig(level=logging.DEBUG)`
4. Check API status: `client.get_status()`
5. Run health check: `client.health_check()`

## License

See repository LICENSE

---

**Version**: 1.0.0  
**Status**: Production Ready  
**Last Updated**: November 21, 2025
