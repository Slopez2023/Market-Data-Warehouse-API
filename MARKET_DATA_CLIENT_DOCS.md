# Market Data Client Documentation

Production-ready Python client for the Market Data Warehouse API. Designed for reliability, performance, and ease of use across multiple projects.

**Table of Contents**
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [Error Handling](#error-handling)
- [Data Models](#data-models)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Basic Setup (30 seconds)

```bash
# Create .env file
cat > .env << EOF
MARKET_DATA_API_URL=http://localhost:8000
MARKET_DATA_API_KEY=mdw_2ed1a9e0944f8c1a17b8d59a49a87e29b3529fbbeadaf6b5d3ec960ca7fba19a
EOF

# Copy client file
cp market_data_client.py your_project/
```

### 2. Use in Your Code

```python
from market_data_client import MarketDataClient

client = MarketDataClient()  # Reads from .env

# Get historical data
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

---

## Installation

### Requirements
```
Python 3.7+
requests>=2.28.0
python-dotenv (optional, for .env support)
```

### Setup

**Option 1: Copy File**
```bash
cp market_data_client.py /path/to/your/project/
```

**Option 2: Package (if distributed)**
```bash
pip install market-data-client
```

**Option 3: From Source**
```bash
git clone <repository>
cd market-data-client
pip install -r requirements.txt
```

---

## Configuration

### Environment Variables

The client reads from these environment variables (if not provided as arguments):

```bash
# Required
MARKET_DATA_API_KEY=mdw_your_key_here

# Optional (defaults shown)
MARKET_DATA_API_URL=http://localhost:8000
MARKET_DATA_API_TIMEOUT=30
MARKET_DATA_API_VERIFY_SSL=true
```

### Initialization Options

```python
from market_data_client import MarketDataClient

# Option 1: From environment variables
client = MarketDataClient()

# Option 2: Explicit parameters
client = MarketDataClient(
    api_url="http://localhost:8000",
    api_key="mdw_your_key_here"
)

# Option 3: With custom settings
client = MarketDataClient(
    api_url="http://api.example.com:8000",
    api_key="mdw_your_key_here",
    timeout=60,           # Request timeout (seconds)
    max_retries=5,        # Retry attempts on failure
    backoff_factor=0.5,   # Exponential backoff multiplier
    verify_ssl=True       # SSL certificate verification
)

# Option 4: Using factory function
from market_data_client import create_client
client = create_client()
```

---

## Usage Examples

### Example 1: Get Historical OHLCV Data

```python
from market_data_client import MarketDataClient

client = MarketDataClient()

# Fetch daily data
data = client.get_historical_data(
    symbol="AAPL",
    timeframe="1d",
    start="2024-01-01",
    end="2024-12-31",
    validated_only=True,
    min_quality=0.90
)

print(f"Symbol: {data.symbol}")
print(f"Timeframe: {data.timeframe}")
print(f"Candles: {data.count}")

# Access as list of Candle objects
for candle in data.candles:
    print(f"{candle.time}: O={candle.open:.2f} H={candle.high:.2f} "
          f"L={candle.low:.2f} C={candle.close:.2f} V={candle.volume}")

# Or raw dict data
for raw in data.data:
    print(raw)
```

### Example 2: Get AI-Ready Quant Features

```python
# Get computed technical indicators
features = client.get_quant_features(
    symbol="MSFT",
    timeframe="1h",
    start="2024-11-01",
    end="2024-11-30",
    limit=1000
)

print(f"Got {features.records_returned} feature records")

for feature in features.parsed_features:
    print(
        f"{feature.time}: "
        f"Close={feature.close:.2f} "
        f"Vol20={feature.volatility_20:.4f} "
        f"Trend={feature.trend_direction} "
        f"Regime={feature.volatility_regime}"
    )
```

### Example 3: Data Quality Monitoring

```python
# Check data quality for a symbol
quality = client.get_data_quality(symbol="BTC", days=30)

print(f"Symbol: {quality['symbol']}")
print(f"Analysis Period: {quality['period_days']} days")
print(f"Avg Validation Rate: {quality['summary']['avg_validation_rate']}%")
print(f"Avg Quality Score: {quality['summary']['avg_quality_score']}")
print(f"Gaps Detected: {quality['summary']['total_gaps_detected']}")

# Check validation rate per day
for metric in quality['daily_metrics']:
    print(f"{metric['date']}: {metric['validation_rate']:.1f}% validated")
```

### Example 4: System Status

```python
# Get API status and available symbols
status = client.get_status()

print(f"API Version: {status['api_version']}")
print(f"Status: {status['status']}")
print(f"Available Symbols: {status['database']['symbols_available']}")
print(f"Total Records: {status['database']['total_records']:,}")
print(f"Validation Rate: {status['database']['validation_rate_pct']:.1f}%")
print(f"Scheduler: {status['data_quality']['scheduler_status']}")

# List symbols
symbols = client.get_symbols()
print(f"Symbols available: {symbols['symbols_available']}")
```

### Example 5: Error Handling

```python
from market_data_client import (
    MarketDataClient,
    ValidationError,
    AuthenticationError,
    APIConnectionError,
    RateLimitError
)

client = MarketDataClient()

try:
    data = client.get_historical_data(
        symbol="AAPL",
        timeframe="1d",
        start="2024-01-01",
        end="2024-12-31"
    )
except ValidationError as e:
    print(f"Invalid parameters: {e}")
    # Fix parameters and retry
except AuthenticationError as e:
    print(f"Auth failed: {e}")
    # Check API key
except RateLimitError as e:
    print(f"Rate limited: {e}")
    # Wait and retry
except APIConnectionError as e:
    print(f"Connection failed: {e}")
    # Check API server
```

### Example 6: Context Manager

```python
# Automatic resource cleanup
with MarketDataClient() as client:
    data = client.get_historical_data(
        "AAPL",
        timeframe="1d",
        start="2024-01-01",
        end="2024-12-31"
    )
    print(f"Got {data.count} candles")
# Session automatically closed
```

### Example 7: Batch Processing

```python
symbols = ["AAPL", "MSFT", "GOOGL", "BTC", "ETH"]

client = MarketDataClient()

for symbol in symbols:
    try:
        data = client.get_historical_data(
            symbol=symbol,
            timeframe="1d",
            start="2024-11-01",
            end="2024-11-30"
        )
        print(f"{symbol}: {data.count} candles")
        
        # Process candles
        for candle in data.candles:
            if candle.volume_anomaly:
                print(f"  {candle.time}: Volume anomaly detected")
    
    except Exception as e:
        print(f"{symbol}: Error - {e}")
```

### Example 8: Integration with Pandas

```python
import pandas as pd
from market_data_client import MarketDataClient

client = MarketDataClient()

# Fetch data
data = client.get_historical_data(
    symbol="AAPL",
    timeframe="1d",
    start="2024-01-01",
    end="2024-12-31"
)

# Convert to DataFrame
df = pd.DataFrame(data.data)
df['time'] = pd.to_datetime(df['time'])
df.set_index('time', inplace=True)

print(df[['open', 'high', 'low', 'close', 'volume']].head())

# Calculate returns
df['returns'] = df['close'].pct_change()

# Find anomalies
anomalies = df[df['volume_anomaly'] == True]
print(f"Found {len(anomalies)} volume anomalies")
```

### Example 9: Health Monitoring

```python
import time
from market_data_client import MarketDataClient

client = MarketDataClient()

# Check API health
while True:
    if client.health_check():
        print("API is healthy")
        
        # Safe to make requests
        status = client.get_status()
        print(f"Validation Rate: {status['database']['validation_rate_pct']}%")
    else:
        print("API is down")
    
    time.sleep(60)
```

---

## API Reference

### MarketDataClient Class

Main client class for API interaction.

#### Constructor

```python
MarketDataClient(
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = 30,
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    verify_ssl: bool = True
)
```

**Parameters:**
- `api_url` (str): Base API URL. Reads from `MARKET_DATA_API_URL` env var if not provided
- `api_key` (str): API authentication key. Reads from `MARKET_DATA_API_KEY` env var if not provided
- `timeout` (int): Request timeout in seconds (default: 30)
- `max_retries` (int): Max retry attempts on transient failures (default: 3)
- `backoff_factor` (float): Exponential backoff multiplier for retries (default: 0.5)
- `verify_ssl` (bool): Verify SSL certificates (default: True)

**Raises:**
- `AuthenticationError`: If API key is missing or invalid
- `APIConnectionError`: If unable to connect to API

---

### Methods

#### `get_historical_data()`

Fetch OHLCV candles for a symbol and timeframe.

```python
def get_historical_data(
    symbol: str,
    timeframe: str = "1d",
    start: str = None,
    end: str = None,
    validated_only: bool = True,
    min_quality: float = 0.85
) -> HistoricalDataResponse
```

**Parameters:**
- `symbol` (str): Stock/crypto ticker (e.g., "AAPL", "BTC")
- `timeframe` (str): Candle timeframe (default: "1d")
  - Allowed: "5m", "15m", "30m", "1h", "4h", "1d", "1w"
- `start` (str): Start date in YYYY-MM-DD format (required)
- `end` (str): End date in YYYY-MM-DD format (required)
- `validated_only` (bool): Only return validated candles (default: True)
- `min_quality` (float): Minimum quality score 0.0-1.0 (default: 0.85)

**Returns:**
- `HistoricalDataResponse`: Contains symbol, timeframe, count, data list

**Raises:**
- `ValidationError`: If parameters are invalid
- `APIError`: If request fails

**Example:**
```python
data = client.get_historical_data(
    "AAPL",
    timeframe="1h",
    start="2024-01-01",
    end="2024-12-31"
)
for candle in data.candles:
    print(f"{candle.time}: {candle.close}")
```

---

#### `get_quant_features()`

Fetch AI-ready quant features (technical indicators) for a symbol.

```python
def get_quant_features(
    symbol: str,
    timeframe: str = "1d",
    start: Optional[str] = None,
    end: Optional[str] = None,
    limit: int = 500
) -> QuantFeaturesResponse
```

**Parameters:**
- `symbol` (str): Stock/crypto ticker
- `timeframe` (str): Candle timeframe (default: "1d")
- `start` (str): Optional start date YYYY-MM-DD
- `end` (str): Optional end date YYYY-MM-DD
- `limit` (int): Max records to return 1-10000 (default: 500)

**Returns:**
- `QuantFeaturesResponse`: Contains features list with computed indicators

**Features Included:**
- **Returns**: return_1h, return_1d
- **Volatility**: volatility_20, volatility_50, atr
- **Volume**: rolling_volume_20, volume_ratio
- **Structure**: structure_label, trend_direction
- **Regimes**: volatility_regime, trend_regime, compression_regime

**Example:**
```python
features = client.get_quant_features("MSFT", timeframe="1h", limit=1000)
for f in features.parsed_features:
    print(f"{f.time}: vol={f.volatility_20:.4f}, trend={f.trend_direction}")
```

---

#### `get_data_quality()`

Fetch data quality report for a symbol.

```python
def get_data_quality(
    symbol: str,
    days: int = 7
) -> Dict[str, Any]
```

**Parameters:**
- `symbol` (str): Stock/crypto ticker
- `days` (int): Analysis period in days, 1-365 (default: 7)

**Returns:**
- Dictionary with quality metrics and daily breakdowns

**Example:**
```python
quality = client.get_data_quality("AAPL", days=30)
print(f"Validation: {quality['summary']['avg_validation_rate']}%")
```

---

#### `get_status()`

Get overall API status and database metrics.

```python
def get_status() -> Dict[str, Any]
```

**Returns:**
- Dictionary with API version, status, symbol count, validation rates

**Example:**
```python
status = client.get_status()
print(f"Symbols: {status['database']['symbols_available']}")
```

---

#### `get_symbols()`

Get list of available symbols and latest data timestamp.

```python
def get_symbols() -> Dict[str, Any]
```

**Returns:**
- Dictionary with symbols_available count and latest_data timestamp

**Example:**
```python
symbols = client.get_symbols()
print(f"Available: {symbols['symbols_available']}")
```

---

#### `health_check()`

Check if API is healthy (no authentication required).

```python
def health_check() -> bool
```

**Returns:**
- `True` if API is healthy, `False` otherwise

**Example:**
```python
if client.health_check():
    print("API is up")
else:
    print("API is down")
```

---

#### `close()`

Close HTTP session and cleanup resources.

```python
def close() -> None
```

**Example:**
```python
client.close()
```

---

### Context Manager

Use with `with` statement for automatic cleanup:

```python
with MarketDataClient() as client:
    data = client.get_historical_data(...)
# Session automatically closed
```

---

## Error Handling

### Exception Hierarchy

```
MarketDataClientError (base)
├── AuthenticationError (API key invalid/missing)
├── ValidationError (Bad request parameters)
├── APIError (Server error response)
├── APIConnectionError (Connection failure)
└── RateLimitError (Rate limit exceeded)
```

### Handling Strategies

#### 1. Catch Specific Exceptions

```python
from market_data_client import (
    MarketDataClient,
    ValidationError,
    AuthenticationError,
    RateLimitError,
    APIConnectionError
)

client = MarketDataClient()

try:
    data = client.get_historical_data("AAPL", ...)
except ValidationError as e:
    # Fix request and retry
    print(f"Invalid request: {e}")
except AuthenticationError as e:
    # Check/update API key
    print(f"Auth failed: {e}")
except RateLimitError as e:
    # Wait and retry with backoff
    time.sleep(60)
    data = client.get_historical_data("AAPL", ...)
except APIConnectionError as e:
    # Check API server, retry later
    print(f"Connection failed: {e}")
```

#### 2. Automatic Retry with Backoff

```python
import time

def fetch_with_backoff(client, symbol, max_retries=5):
    for attempt in range(max_retries):
        try:
            return client.get_historical_data(
                symbol,
                timeframe="1d",
                start="2024-01-01",
                end="2024-12-31"
            )
        except (APIConnectionError, RateLimitError) as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
            print(f"Retry {attempt + 1}/{max_retries} in {wait}s...")
            time.sleep(wait)

data = fetch_with_backoff(client, "AAPL")
```

#### 3. Batch Processing with Error Recovery

```python
from market_data_client import APIConnectionError, ValidationError

symbols = ["AAPL", "MSFT", "GOOGL", "INVALID", "BTC"]
results = {}

for symbol in symbols:
    try:
        data = client.get_historical_data(
            symbol,
            timeframe="1d",
            start="2024-01-01",
            end="2024-12-31"
        )
        results[symbol] = data.count
        print(f"✓ {symbol}: {data.count} candles")
    except ValidationError as e:
        print(f"✗ {symbol}: Invalid ({e})")
    except APIConnectionError as e:
        print(f"⚠ {symbol}: Connection error (will retry)")
    except Exception as e:
        print(f"✗ {symbol}: {type(e).__name__}: {e}")

print(f"\nSuccessful: {len(results)}/{len(symbols)}")
```

---

## Data Models

### Candle

Represents a single OHLCV candle with validation metadata.

```python
@dataclass
class Candle:
    time: str                      # ISO timestamp
    symbol: str                    # Stock/crypto ticker
    timeframe: str                 # Candle timeframe (1d, 1h, etc)
    open: float                    # Open price
    high: float                    # High price
    low: float                     # Low price
    close: float                   # Close price
    volume: int                    # Trading volume
    source: str                    # Data source (polygon, yahoo, etc)
    validated: bool                # Quality validation passed
    quality_score: float           # Quality score 0.0-1.0
    validation_notes: Optional[str]  # Validation details
    gap_detected: bool             # Gap detected
    volume_anomaly: bool           # Volume anomaly detected
    fetched_at: Optional[str]      # Fetch timestamp
```

**Usage:**
```python
for candle in data.candles:
    print(f"{candle.time}: {candle.close}")
    print(f"  Validated: {candle.validated}")
    print(f"  Quality: {candle.quality_score}")
    if candle.volume_anomaly:
        print(f"  Warning: Anomalous volume")
```

---

### Feature

Quant feature record with computed technical indicators.

```python
@dataclass
class Feature:
    time: str                      # ISO timestamp
    symbol: str                    # Stock/crypto ticker
    timeframe: str                 # Candle timeframe
    open: float                    # OHLCV
    high: float
    low: float
    close: float
    volume: int
    
    # Returns
    return_1d: float               # Daily return
    
    # Volatility
    volatility_20: float           # 20-period volatility
    volatility_50: float           # 50-period volatility
    atr: float                     # Average True Range
    
    # Volume
    rolling_volume_20: int         # 20-period avg volume
    volume_ratio: float            # Current/avg volume
    
    # Structure
    structure_label: str           # bullish/bearish/range
    trend_direction: str           # up/down/neutral
    
    # Regimes
    volatility_regime: str         # low/medium/high
    trend_regime: str              # uptrend/downtrend/ranging
    compression_regime: str        # compressed/expanded
    
    # Quality
    quality_score: float           # 0.0-1.0
    validated: bool                # Quality validated
    features_computed_at: str      # Computation timestamp
```

**Usage:**
```python
for feature in features.parsed_features:
    # Use for ML/trading models
    if feature.volatility_regime == "low" and feature.trend_direction == "up":
        print("Low volatility uptrend - potentially tradeable")
    
    # Check data quality
    if feature.quality_score < 0.9:
        print("Warning: Low quality data")
```

---

### HistoricalDataResponse

Response container for historical data requests.

```python
@dataclass
class HistoricalDataResponse:
    symbol: str                    # Requested symbol
    timeframe: str                 # Requested timeframe
    start_date: str                # Start date YYYY-MM-DD
    end_date: str                  # End date YYYY-MM-DD
    count: int                     # Number of candles
    data: List[Dict[str, Any]]     # Raw candle data
    
    @property
    def candles(self) -> List[Candle]:
        """Parsed Candle objects"""
```

**Usage:**
```python
data = client.get_historical_data(...)
print(f"Got {data.count} {data.timeframe} candles")
print(f"Period: {data.start_date} to {data.end_date}")
for candle in data.candles:
    ...
```

---

### QuantFeaturesResponse

Response container for quant features requests.

```python
@dataclass
class QuantFeaturesResponse:
    symbol: str                    # Requested symbol
    timeframe: str                 # Requested timeframe
    records_returned: int          # Number of feature records
    date_range: Dict[str, str]     # {start, end} dates
    features: List[Dict[str, Any]] # Raw feature data
    timestamp: str                 # Response timestamp
    
    @property
    def parsed_features(self) -> List[Feature]:
        """Parsed Feature objects"""
```

**Usage:**
```python
features = client.get_quant_features(...)
print(f"Got {features.records_returned} records")
for feature in features.parsed_features:
    ...
```

---

## Advanced Features

### 1. Session Reuse

The client maintains a persistent HTTP session with connection pooling and keep-alive:

```python
client = MarketDataClient()  # Single session created

# Multiple requests reuse the same session
for symbol in symbols:
    data = client.get_historical_data(symbol, ...)
    # Efficient - reuses connections
```

### 2. Automatic Retry with Exponential Backoff

Transient failures are automatically retried:

```python
client = MarketDataClient(
    max_retries=5,        # Up to 5 attempts
    backoff_factor=0.5    # 0.5, 1.0, 2.0, 4.0, 8.0 seconds
)

# Automatically retries on:
# - Connection errors
# - Timeouts
# - 5xx server errors
data = client.get_historical_data(...)
```

### 3. Parameter Validation

All inputs are validated before sending to API:

```python
# Validates symbol, timeframe, dates, limits
try:
    data = client.get_historical_data(
        "AAPL",
        timeframe="invalid",    # Raises ValidationError
        start="01/01/2024",     # Raises ValidationError
        end="2024-12-31"
    )
except ValidationError as e:
    print(f"Invalid: {e}")
```

### 4. Custom Configuration

```python
client = MarketDataClient(
    api_url="https://api.example.com:8443",
    api_key="your_key",
    timeout=60,              # 60 second timeout
    max_retries=10,          # More retries for slow networks
    backoff_factor=1.0,      # Longer backoff
    verify_ssl=False         # For self-signed certificates
)
```

### 5. Logging

All operations are logged:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

client = MarketDataClient()
data = client.get_historical_data(...)
# See detailed logs of requests, retries, etc.
```

---

## Troubleshooting

### Connection Issues

**Problem:** `APIConnectionError: Failed to connect to API`

**Solutions:**
1. Check API is running: `curl http://localhost:8000/health`
2. Verify API URL: `client = MarketDataClient(api_url="http://correct:8000")`
3. Check firewall/network access
4. Increase timeout: `MarketDataClient(timeout=60)`

### Authentication Issues

**Problem:** `AuthenticationError: Invalid API key`

**Solutions:**
1. Verify API key: `echo $MARKET_DATA_API_KEY`
2. Check .env file: `cat .env`
3. Check key hasn't been revoked
4. Generate new key from API admin panel

### Timeout Issues

**Problem:** `APIConnectionError: Request timeout after 30s`

**Solutions:**
1. Increase timeout: `MarketDataClient(timeout=60)`
2. Reduce data range (large queries take longer)
3. Check API server performance
4. Try with smaller limit parameter

### Rate Limiting

**Problem:** `RateLimitError: Rate limit exceeded`

**Solutions:**
1. Implement request batching with delays
2. Use smaller limits per request
3. Implement exponential backoff (built-in)
4. Contact API provider for higher limits

### Data Issues

**Problem:** `No data found for symbol`

**Solutions:**
1. Check symbol is valid: `client.get_symbols()`
2. Check date range has data: `client.get_status()`
3. Try different timeframe: `timeframe="1d"` vs `"1h"`
4. Check `validated_only` parameter

### Validation Errors

**Problem:** `ValidationError: Invalid timeframe`

**Solutions:**
1. Check allowed timeframes: `client.ALLOWED_TIMEFRAMES`
2. Use format "1d" not "1D" (case-sensitive)
3. Valid: 5m, 15m, 30m, 1h, 4h, 1d, 1w
4. Check dates: use YYYY-MM-DD format

---

## Performance Tips

### 1. Batch Requests Efficiently

```python
# Good: Request once with full date range
data = client.get_historical_data(
    "AAPL",
    timeframe="1d",
    start="2024-01-01",
    end="2024-12-31"
)

# Avoid: Multiple requests for partial data
for month in range(1, 13):
    data = client.get_historical_data(...)  # 12 requests
```

### 2. Reuse Session

```python
client = MarketDataClient()  # Create once

# Reuse for multiple requests
for symbol in symbols:
    data = client.get_historical_data(symbol, ...)
    # Don't: create new client for each request
```

### 3. Filter Data Client-Side When Possible

```python
# Get all data at once, filter locally
data = client.get_historical_data(
    "AAPL",
    timeframe="1d",
    start="2024-01-01",
    end="2024-12-31"
)

# Filter on demand
high_volume = [c for c in data.candles if c.volume > 50000000]
high_quality = [c for c in data.candles if c.quality_score > 0.95]
```

### 4. Use Appropriate Limits

```python
# For streaming/real-time: smaller limits, more frequent
features = client.get_quant_features("AAPL", limit=100)

# For historical analysis: larger limits
features = client.get_quant_features("AAPL", limit=5000)
```

### 5. Cache Results

```python
from functools import lru_cache
import json

@lru_cache(maxsize=128)
def get_cached_data(symbol, date_range):
    return client.get_historical_data(
        symbol,
        timeframe="1d",
        start=date_range[0],
        end=date_range[1]
    )
```

---

## Support & Contribution

### Getting Help
- Check troubleshooting section above
- Review API status: `client.get_status()`
- Enable debug logging for detailed info
- Contact API support with error details

### Reporting Issues
When reporting issues, include:
1. Python version: `python --version`
2. Client version/file timestamp
3. Error message and stack trace
4. API response (if available)
5. Steps to reproduce

### Contributing
This is a reference implementation. Customize as needed for your use case:
- Add custom exception handlers
- Implement caching strategies
- Add metrics/monitoring
- Extend with domain-specific methods

---

## License

See repository LICENSE file.

---

## Version History

**1.0.0** (2025-11-21)
- Initial release
- Support for all API endpoints
- Automatic retry with exponential backoff
- Comprehensive error handling
- Context manager support
- Production-ready stability

