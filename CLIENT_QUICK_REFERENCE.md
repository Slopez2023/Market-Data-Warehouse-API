# Market Data Client - Quick Reference

**One-Page Cheat Sheet for Daily Use**

## Setup (First Time Only)

```bash
# 1. Copy files
cp market_data_client.py your_project/
cp client_env.example your_project/.env

# 2. Edit .env
MARKET_DATA_API_URL=http://localhost:8000
MARKET_DATA_API_KEY=mdw_your_key_here

# 3. Install
pip install requests python-dotenv
```

## Initialize Client

```python
from market_data_client import MarketDataClient

# From environment
client = MarketDataClient()

# Or explicit
client = MarketDataClient(
    api_url="http://localhost:8000",
    api_key="mdw_your_key_here"
)

# Use as context manager
with MarketDataClient() as client:
    data = client.get_historical_data(...)
```

## Get Data (Core Methods)

### Historical OHLCV
```python
data = client.get_historical_data(
    symbol="AAPL",              # Required: "AAPL", "BTC", etc
    timeframe="1d",             # Optional: 5m, 15m, 30m, 1h, 4h, 1d, 1w
    start="2024-01-01",         # Required: YYYY-MM-DD
    end="2024-12-31",           # Required: YYYY-MM-DD
    validated_only=True,        # Optional: true/false
    min_quality=0.85            # Optional: 0.0-1.0
)

print(f"Count: {data.count}")
for c in data.candles:
    print(f"{c.time}: {c.close} (vol={c.volume})")
```

### Quant Features (AI-Ready)
```python
features = client.get_quant_features(
    symbol="AAPL",              # Required
    timeframe="1d",             # Optional
    start="2024-01-01",         # Optional
    end="2024-12-31",           # Optional
    limit=500                   # Optional: 1-10000
)

for f in features.parsed_features:
    print(f"{f.time}: vol={f.volatility_20:.4f}, trend={f.trend_direction}")
```

### Data Quality
```python
quality = client.get_data_quality(
    symbol="AAPL",              # Required
    days=7                      # Optional: 1-365
)

print(f"Validation: {quality['summary']['avg_validation_rate']}%")
print(f"Quality: {quality['summary']['avg_quality_score']}")
```

### Status & Health
```python
status = client.get_status()        # Full API status
symbols = client.get_symbols()      # Available symbols
healthy = client.health_check()     # Boolean: is API up?
```

## Timeframes

| Code | Period    |
|------|-----------|
| 5m   | 5 min     |
| 15m  | 15 min    |
| 30m  | 30 min    |
| 1h   | 1 hour    |
| 4h   | 4 hours   |
| 1d   | 1 day     |
| 1w   | 1 week    |

## Error Handling

```python
from market_data_client import (
    ValidationError,      # Bad parameters
    AuthenticationError,  # Invalid key
    RateLimitError,       # Rate limited
    APIConnectionError,   # Connection failed
)

try:
    data = client.get_historical_data(...)
except ValidationError as e:
    print(f"Bad request: {e}")
except AuthenticationError as e:
    print(f"Auth failed: {e}")
except RateLimitError as e:
    print(f"Rate limited: {e}")
    time.sleep(60)
except APIConnectionError as e:
    print(f"Connection error: {e}")
```

## Common Patterns

### Batch Symbols
```python
for symbol in ["AAPL", "MSFT", "BTC"]:
    try:
        data = client.get_historical_data(symbol, timeframe="1d", start="2024-01-01", end="2024-12-31")
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
print(df)
```

### Retry with Backoff
```python
import time

for attempt in range(5):
    try:
        data = client.get_historical_data(...)
        break
    except APIConnectionError as e:
        if attempt == 4:
            raise
        wait = 2 ** attempt
        print(f"Retry in {wait}s...")
        time.sleep(wait)
```

### Filter High Quality
```python
data = client.get_historical_data("AAPL", timeframe="1d", start="2024-01-01", end="2024-12-31")
high_quality = [c for c in data.candles if c.quality_score > 0.95 and not c.volume_anomaly]
```

## Features (Quant Indicators)

Returned by `get_quant_features()`:

```
return_1d           Daily return percentage
volatility_20       20-period volatility
volatility_50       50-period volatility
atr                 Average True Range
rolling_volume_20   20-period avg volume
volume_ratio        Current/average volume
structure_label     bullish/bearish/range
trend_direction     up/down/neutral
volatility_regime   low/medium/high
trend_regime        uptrend/downtrend/ranging
compression_regime  compressed/expanded
quality_score       0.0-1.0 (higher is better)
validated           Quality passed threshold
```

## Candle Fields

```
time                ISO timestamp
symbol              Ticker symbol
timeframe           Candle timeframe
open, high, low, close   OHLC prices
volume              Trading volume
source              Data source (polygon, yahoo, etc)
validated           Quality passed
quality_score       0.0-1.0
gap_detected        True if gap found
volume_anomaly      True if anomaly found
fetched_at          Fetch timestamp
```

## Configuration

### Environment Variables
```bash
MARKET_DATA_API_URL=http://localhost:8000
MARKET_DATA_API_KEY=mdw_your_key_here
MARKET_DATA_API_TIMEOUT=30
MARKET_DATA_API_VERIFY_SSL=true
```

### Constructor Args
```python
MarketDataClient(
    api_url=...,           # API base URL
    api_key=...,           # Auth key
    timeout=30,            # Request timeout (seconds)
    max_retries=3,         # Retry attempts
    backoff_factor=0.5,    # Retry backoff (seconds)
    verify_ssl=True        # SSL verification
)
```

## Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
# Now see detailed logs of all requests
```

## Close Client

```python
client.close()  # Or use context manager for auto-close
```

## Troubleshooting

| Error | Solution |
|-------|----------|
| `APIConnectionError` | Check API URL and port, verify API is running |
| `AuthenticationError` | Check API key in MARKET_DATA_API_KEY |
| `ValidationError` | Check timeframe format (lowercase: "1d"), dates format (YYYY-MM-DD) |
| `RateLimitError` | Wait 60s, reduce request frequency |
| `Timeout` | Increase timeout: `MarketDataClient(timeout=60)` |

## Get Status

```python
status = client.get_status()
print(f"Symbols: {status['database']['symbols_available']}")
print(f"Validation: {status['database']['validation_rate_pct']}%")
print(f"Scheduler: {status['data_quality']['scheduler_status']}")
```

## List Symbols

```python
symbols = client.get_symbols()
print(f"Available: {symbols['symbols_available']}")
print(f"Latest: {symbols['latest_data']}")
```

---

## More Help

- **Full Docs**: See `MARKET_DATA_CLIENT_DOCS.md`
- **Examples**: See `MARKET_DATA_CLIENT_DOCS.md` Usage section
- **README**: See `CLIENT_README.md`

**Version**: 1.0.0 | **Last Updated**: 2025-11-21

