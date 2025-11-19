# Clean Data Pipeline for AI Training

## Quick Start

```bash
# Step 1: Validate and repair unvalidated records (asset-aware)
docker exec market_data_api python repair_unvalidated_data.py --batch-size 5000

# Step 2: Export clean data for training
docker exec market_data_api python clean_data_export.py --output /tmp/data

# Step 3: Validate exported dataset
docker exec market_data_api python validate_clean_dataset.py --data-dir /tmp/data
```

## What Changed

### Phase 1: Asset-Aware Validation
- Crypto (BTC-USD, ETH-USD): Very lenient volume thresholds (0.1% median)
- Stocks (AAPL, MSFT): Strict volume thresholds (20% median)
- ETFs (SPY, QQQ): Medium thresholds (15% median)
- Gap detection: 30% for crypto, 15% for stocks, 12% for ETFs

**Result:** No more false "possible delisting" flags on crypto

### Phase 2: Clean Data Export
- Exports only validated records (quality_score >= 0.80)
- Detects data gaps
- Generates metadata JSON
- Ready for TCN/LSTM training

### Phase 3: Dataset Validation
- 100+ records per symbol/timeframe
- Max 5-day gaps (accounts for weekends)
- No null values
- Price continuity checks

## Implementation

All changes deployed live to Docker without rebuild:
- `src/services/validation_service.py` - Asset-aware validators
- `clean_data_export.py` - Export pipeline
- `validate_clean_dataset.py` - Quality checks
- `repair_unvalidated_data.py` - Optimized validation

## Command Reference

### Repair Data (choose one)

```bash
# All unvalidated records, fast
docker exec market_data_api python repair_unvalidated_data.py --batch-size 5000

# Specific symbols
docker exec market_data_api python repair_unvalidated_data.py --symbols AAPL,BTC-USD --batch-size 2000

# Specific timeframes
docker exec market_data_api python repair_unvalidated_data.py --timeframes 1d,1h --batch-size 2000

# Dry run (preview)
docker exec market_data_api python repair_unvalidated_data.py --limit 100 --dry-run
```

### Export Clean Data

```bash
# Export all validated symbols
docker exec market_data_api python clean_data_export.py --output /tmp/data

# Export specific symbols
docker exec market_data_api python clean_data_export.py --symbols AAPL,MSFT,BTC-USD --output /tmp/data

# Export specific timeframes
docker exec market_data_api python clean_data_export.py --timeframes 1d,1h --output /tmp/data
```

### Validate & Copy to Local

```bash
# Validate in container
docker exec market_data_api python validate_clean_dataset.py --data-dir /tmp/data

# Copy to local for training
docker cp market_data_api:/tmp/data ./training_data

# Or stream specific files
docker cp market_data_api:/tmp/data/AAPL_1d_clean.csv ./
```

## Data Quality Metrics

After running the pipeline, check:

```bash
# View export summary
docker exec market_data_api cat /tmp/data/EXPORT_METADATA.json

# Count files exported
docker exec market_data_api ls /tmp/data/*_clean.csv | wc -l

# Check file sizes
docker exec market_data_api du -sh /tmp/data/
```

## AI Training Usage

```python
import pandas as pd
from pathlib import Path

# Load single symbol
df = pd.read_csv('training_data/AAPL_1d_clean.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Features available:
# - timestamp, open, high, low, close, volume
# - quality_score, source

# For TCN training:
train_data = df[['open', 'high', 'low', 'close', 'volume']].values
timestamps = df['timestamp'].values

# For LSTM training:
import numpy as np
window_size = 30
X = np.array([train_data[i:i+window_size] for i in range(len(train_data)-window_size)])
y = train_data[window_size:]
```

## Next Steps

1. Run repair pipeline: `repair_unvalidated_data.py`
2. Export clean data: `clean_data_export.py`
3. Validate: `validate_clean_dataset.py`
4. Copy to local training environment
5. Use CSV files for model training
