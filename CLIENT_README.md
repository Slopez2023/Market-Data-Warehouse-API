# Market Data Client - Get Started in 5 Minutes

A production-ready Python client for the Market Data Warehouse API with automatic retry, connection pooling, and comprehensive error handling.

## What You Get

✅ **Reliability**: Automatic retry with exponential backoff  
✅ **Performance**: Connection pooling & keep-alive  
✅ **Easy**: Simple one-liner queries  
✅ **Safe**: Comprehensive error handling  
✅ **Tested**: All endpoints verified  
✅ **Documented**: 100+ examples included

## Files

```
market_data_client.py          # Main client (copy this to your project)
MARKET_DATA_CLIENT_DOCS.md     # Full documentation
client_requirements.txt        # Python dependencies
client_env.example             # Environment template
test_client.py                 # Test suite (optional)
```

## Installation (1 minute)

### 1. Copy Files to Your Project
```bash
cp market_data_client.py /path/to/your/project/
cp client_env.example /path/to/your/project/.env
```

### 2. Install Dependencies
```bash
pip install -r client_requirements.txt
```

Or minimal install:
```bash
pip install requests python-dotenv
```

### 3. Configure
Edit `.env` file with your API credentials:
```bash
MARKET_DATA_API_URL=http://localhost:8000
MARKET_DATA_API_KEY=mdw_your_key_here
```

## Quick Start (30 seconds)

### Get Historical Data
```python
from market_data_client import MarketDataClient

client = MarketDataClient()  # Reads from .env

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

### Get AI Features
```python
features = client.get_quant_features("MSFT", timeframe="1h")

for f in features.parsed_features:
    print(f"{f.time}: volatility={f.volatility_20:.4f}, trend={f.trend_direction}")
```

### Check Data Quality
```python
quality = client.get_data_quality("AAPL", days=30)
print(f"Validation Rate: {quality['summary']['avg_validation_rate']}%")
```

## Common Patterns

### Pattern 1: Batch Processing
```python
symbols = ["AAPL", "MSFT", "GOOGL", "BTC", "ETH"]

for symbol in symbols:
    try:
        data = client.get_historical_data(
            symbol,
            timeframe="1d",
            start="2024-01-01",
            end="2024-12-31"
        )
        print(f"✓ {symbol}: {data.count} candles")
    except Exception as e:
        print(f"✗ {symbol}: {e}")
```

### Pattern 2: With Pandas
```python
import pandas as pd

data = client.get_historical_data("AAPL", timeframe="1d", start="2024-01-01", end="2024-12-31")
df = pd.DataFrame(data.data)
df['time'] = pd.to_datetime(df['time'])
df['returns'] = df['close'].pct_change()

print(df[['close', 'volume', 'returns']].head())
```

### Pattern 3: Error Handling
```python
from market_data_client import ValidationError, APIConnectionError, RateLimitError

try:
    data = client.get_historical_data("AAPL", ...)
except ValidationError as e:
    print(f"Bad parameters: {e}")
except RateLimitError as e:
    print(f"Rate limited, waiting...")
    time.sleep(60)
except APIConnectionError as e:
    print(f"Connection failed: {e}")
```

### Pattern 4: With Context Manager
```python
with MarketDataClient() as client:
    data = client.get_historical_data(...)
    features = client.get_quant_features(...)
# Automatically closes session
```

## API Reference

### Available Methods

```python
# Fetch OHLCV candles
data = client.get_historical_data(
    symbol="AAPL",           # Required
    timeframe="1d",          # Optional: 5m, 15m, 30m, 1h, 4h, 1d, 1w
    start="2024-01-01",      # Required: YYYY-MM-DD
    end="2024-12-31",        # Required: YYYY-MM-DD
    validated_only=True,     # Optional: filter to validated data
    min_quality=0.85         # Optional: quality threshold 0.0-1.0
)

# Fetch AI-ready quant features
features = client.get_quant_features(
    symbol="AAPL",           # Required
    timeframe="1d",          # Optional
    start="2024-01-01",      # Optional
    end="2024-12-31",        # Optional
    limit=500                # Optional: 1-10000
)

# Data quality report
quality = client.get_data_quality(
    symbol="AAPL",           # Required
    days=7                   # Optional: 1-365
)

# System status
status = client.get_status()          # Returns API status and metrics
symbols = client.get_symbols()        # List available symbols
is_healthy = client.health_check()    # Check API health
```

## Error Handling

The client raises specific exceptions for different error types:

```python
from market_data_client import (
    ValidationError,       # Invalid parameters
    AuthenticationError,   # Bad API key
    RateLimitError,        # Rate limit exceeded
    APIConnectionError,    # Connection failed
    APIError               # Other API errors
)
```

All exceptions inherit from `MarketDataClientError`.

## Configuration

### Via Environment Variables
```bash
export MARKET_DATA_API_URL=http://localhost:8000
export MARKET_DATA_API_KEY=mdw_your_key_here
export MARKET_DATA_API_TIMEOUT=30
export MARKET_DATA_API_VERIFY_SSL=true
```

### Via Constructor
```python
client = MarketDataClient(
    api_url="http://api.example.com",
    api_key="mdw_your_key_here",
    timeout=60,
    max_retries=5,
    backoff_factor=0.5,
    verify_ssl=True
)
```

## Features

- **Automatic Retry**: 3 retries with exponential backoff on transient failures
- **Connection Pooling**: Reuses HTTP connections for better performance
- **Timeout Handling**: Configurable request timeouts (default: 30s)
- **Response Validation**: Validates data and gives clear error messages
- **Parameter Validation**: Validates inputs before sending to API
- **Comprehensive Logging**: Detailed logs for debugging
- **Context Manager**: Automatic resource cleanup
- **Data Models**: Typed response objects (Candle, Feature)
- **Thread-Safe**: Safe to use in multi-threaded applications

## Logging

Enable debug logging to see detailed request/response info:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
client = MarketDataClient()
data = client.get_historical_data(...)  # See detailed logs
```

## Performance Tips

1. **Reuse client**: Create once, use many times
   ```python
   client = MarketDataClient()  # Create once
   for symbol in symbols:
       data = client.get_historical_data(symbol, ...)
   ```

2. **Use appropriate limits**:
   ```python
   # For streaming: smaller limits
   features = client.get_quant_features(symbol, limit=100)
   
   # For historical: larger limits
   features = client.get_quant_features(symbol, limit=5000)
   ```

3. **Batch requests**:
   ```python
   # Good: one request with full date range
   data = client.get_historical_data("AAPL", start="2024-01-01", end="2024-12-31")
   
   # Avoid: multiple requests
   for month in range(1, 13):
       data = client.get_historical_data("AAPL", start=f"2024-{month:02d}-01", ...)
   ```

## Examples

See `MARKET_DATA_CLIENT_DOCS.md` for 9 detailed examples including:
- Basic usage
- Error handling
- Batch processing
- Pandas integration
- Health monitoring
- Data quality checks
- Custom configuration

## Troubleshooting

### Connection Error
```
APIConnectionError: Failed to connect to API at http://localhost:8000
```
→ Check API is running and URL is correct

### Authentication Error
```
AuthenticationError: Invalid API key
```
→ Check MARKET_DATA_API_KEY in .env

### Timeout Error
```
APIConnectionError: Request timeout after 30s
```
→ Increase timeout: `MarketDataClient(timeout=60)`

### Validation Error
```
ValidationError: Invalid timeframe: 1D. Allowed: 5m, 15m, 30m, 1h, 4h, 1d, 1w
```
→ Use lowercase timeframe: "1d" not "1D"

For more troubleshooting, see `MARKET_DATA_CLIENT_DOCS.md` → Troubleshooting section

## Next Steps

1. **Copy files** to your project
2. **Edit .env** with your API key
3. **Install requirements**: `pip install -r client_requirements.txt`
4. **Run examples** from MARKET_DATA_CLIENT_DOCS.md
5. **Integrate** into your application

## Full Documentation

See `MARKET_DATA_CLIENT_DOCS.md` for:
- Complete API reference
- 9+ detailed examples
- Error handling strategies
- Data models
- Performance optimization
- Advanced features
- Troubleshooting guide

## Support

For issues or questions:
1. Check troubleshooting section
2. Review MARKET_DATA_CLIENT_DOCS.md
3. Check API status: `client.get_status()`
4. Enable debug logging
5. Contact API support with error details

---

**Version**: 1.0.0  
**Last Updated**: 2025-11-21  
**Status**: ✅ Production Ready

