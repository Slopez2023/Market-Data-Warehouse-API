# Quant Engine Quick Start Guide

## Overview

The Quant Feature Engine automatically generates 17 financial features from OHLCV data and makes them available via REST API.

## Quick API Usage

### Get Daily Features for AAPL
```bash
curl "http://localhost:8000/api/v1/features/quant/AAPL"
```

### Get Hourly Features with Date Range
```bash
curl "http://localhost:8000/api/v1/features/quant/AAPL?timeframe=1h&start=2024-01-01&end=2024-12-31&limit=1000"
```

### All Timeframes
- `5m` - 5 minute
- `15m` - 15 minute
- `30m` - 30 minute
- `1h` - 1 hour
- `4h` - 4 hour
- `1d` - 1 day (default)
- `1w` - 1 week

## Feature Categories

### Returns (3)
- `return_1h` - 1-hour return
- `return_1d` - Daily return
- `log_return` - Open-to-close return

### Volatility (3)
- `volatility_20` - 20-period annualized vol
- `volatility_50` - 50-period annualized vol
- `atr` - Average True Range (14-period)

### Volume (2)
- `rolling_volume_20` - 20-period average volume
- `volume_ratio` - Current vol / avg vol

### Market Structure (6)
- `hh` - Higher High (1 or 0)
- `hl` - Higher Low (1 or 0)
- `lh` - Lower High (1 or 0)
- `ll` - Lower Low (1 or 0)
- `trend_direction` - "up", "down", or "neutral"
- `structure_label` - "bullish", "bearish", or "range"

### Regimes (3)
- `volatility_regime` - "low", "medium", or "high"
- `trend_regime` - "uptrend", "downtrend", or "ranging"
- `compression_regime` - "compressed" or "expanded"

## Python Integration

```python
import requests
import pandas as pd

# Fetch features
response = requests.get(
    "http://localhost:8000/api/v1/features/quant/AAPL",
    params={"timeframe": "1d", "limit": 500}
)

data = response.json()
df = pd.DataFrame(data["features"])

# Use in ML model
features = ["volatility_20", "volume_ratio", "trend_regime"]
X = df[features]
y = df["return_1d"]

model.fit(X, y)
```

## Database Access (Advanced)

```python
from src.services.database_service import DatabaseService

db = DatabaseService(database_url)

# Get features directly
features = db.get_quant_features(
    symbol="AAPL",
    timeframe="1d",
    start="2024-01-01",
    end="2024-12-31",
    limit=500
)

# features is a list of dicts with OHLCV + all quant features
for record in features:
    print(record["time"], record["volatility_20"])
```

## Testing

Run tests to verify implementation:

```bash
# All quant tests
pytest tests/test_quant_*.py -v

# Specific test file
pytest tests/test_quant_features.py -v

# Single test
pytest tests/test_quant_features.py::TestQuantFeatureEngineBasics::test_compute_single_row -v
```

## Common Tasks

### Update Feature Computations
Features are computed automatically during backfill. To manually trigger:

```python
from src.scheduler import AutoBackfillScheduler

scheduler = AutoBackfillScheduler(api_key, db_url)
count = await scheduler._compute_quant_features("AAPL", "1d")
print(f"Computed {count} features")
```

### Query Features from Database
```python
from src.services.database_service import DatabaseService

db = DatabaseService(database_url)

# Get latest features for a symbol
features = db.get_quant_features(
    symbol="AAPL",
    timeframe="1d",
    limit=10  # Last 10 days
)

for record in features:
    volatility = record["volatility_20"]
    regime = record["volatility_regime"]
    print(f"{record['time']}: vol={volatility:.4f}, regime={regime}")
```

### Export Features to DataFrame
```python
response = requests.get(
    "http://localhost:8000/api/v1/features/quant/AAPL",
    params={"timeframe": "1d", "limit": 1000}
)

import pandas as pd
df = pd.DataFrame(response.json()["features"])
df.to_csv("aapl_features.csv", index=False)
```

## Troubleshooting

### No features returned (404 error)
**Cause:** Features haven't been computed yet for this symbol/timeframe

**Solution:** 
1. Wait for next scheduler run (default: daily at 02:00 UTC)
2. Or check logs: features are computed after OHLCV insertion

### Features for old dates missing
**Cause:** Backfill only computes recent data by default

**Solution:**
1. Check backfill window in config (default: last 2 years)
2. Features require minimum 50 bars for full computation

### Slow queries
**Cause:** Missing indexes or large limit

**Solution:**
1. Reduce limit (default 500 is optimal)
2. Use specific date range with `start` and `end`
3. Verify indexes exist: `\d market_data` in psql

## Performance Tips

1. **Limit records**: Use `limit=500` (default) instead of large numbers
2. **Date ranges**: Specify `start` and `end` for specific periods
3. **Caching**: Store frequently-requested data locally
4. **Batch requests**: Query multiple symbols in parallel
5. **Timeframe choice**: Lower timeframes (5m) have more data, higher computation

## Key Files

| File | Purpose |
|------|---------|
| `src/quant_engine/quant_features.py` | Feature computation engine |
| `src/services/database_service.py` | Database operations (quant methods) |
| `src/scheduler.py` | Automatic feature computation |
| `main.py` | REST API endpoint |
| `database/migrations/012_add_quant_features.sql` | Schema |

## Endpoints Reference

### GET /api/v1/features/quant/{symbol}

**Path Parameters:**
- `symbol` (required): Stock ticker or crypto symbol (e.g., AAPL, BTC)

**Query Parameters:**
- `timeframe` (optional): Chart timeframe (default: 1d)
- `start` (optional): Start date YYYY-MM-DD
- `end` (optional): End date YYYY-MM-DD
- `limit` (optional): Max records 1-10000 (default: 500)

**Response:**
```json
{
  "symbol": "AAPL",
  "timeframe": "1d",
  "records_returned": 250,
  "date_range": {
    "start": "2024-01-01",
    "end": "2024-12-31"
  },
  "features": [
    {
      "time": "2024-01-01T00:00:00Z",
      "open": 150.0,
      "high": 151.5,
      "low": 149.5,
      "close": 150.5,
      "volume": 50000000,
      "return_1d": 0.005,
      "volatility_20": 0.15,
      "volatility_50": 0.14,
      "atr": 1.5,
      "rolling_volume_20": 48000000,
      "volume_ratio": 1.04,
      "structure_label": "bullish",
      "trend_direction": "up",
      "volatility_regime": "medium",
      "trend_regime": "uptrend",
      "compression_regime": "expanded",
      "features_computed_at": "2024-01-01T02:30:00Z"
    }
  ],
  "timestamp": "2024-11-13T10:31:00Z"
}
```

## Additional Resources

- Full Implementation: `QUANT_ENGINE_IMPLEMENTATION.md`
- Completion Report: `QUANT_ENGINE_COMPLETION.md`
- Tests: `tests/test_quant_*.py`
- Configuration: `src/config.py`

## Support

For issues or questions:

1. Check test files for usage examples
2. Review docstrings in source code
3. Check logs for computation errors
4. Run test suite to verify installation

---

**Happy feature engineering! 🚀**
