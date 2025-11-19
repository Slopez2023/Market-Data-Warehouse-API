# Validation Repair - Quick Start

## TL;DR

You have unvalidated backfill data. This script fixes it in 3 steps:

```bash
# Step 1: Check current state (preview only, no DB changes)
python repair_unvalidated_data.py --dry-run

# Step 2: Fix the data (updates quality scores and validation flags)
python repair_unvalidated_data.py

# Step 3: Check results
python repair_unvalidated_data.py --output final_report.json
cat final_report.json | jq '.validation_rate'  # Should be 90%+
```

## What Gets Fixed

**Before:**
```
validated=FALSE, quality_score=0.0, validation_notes="Backfill data"
```

**After:**
```
validated=TRUE/FALSE, quality_score=0.87, validation_notes="price_move_ok;gap_ok;volume_ok"
```

## For Different Scenarios

### Just Want to Test?
```bash
python repair_unvalidated_data.py --dry-run --limit 1000
```

### Fix Only Your Most Important Stocks?
```bash
python repair_unvalidated_data.py --symbols AAPL,MSFT,GOOGL
```

### Fix Only Daily Data?
```bash
python repair_unvalidated_data.py --timeframes 1d
```

### Make It Faster (More Memory)?
```bash
python repair_unvalidated_data.py --batch-size 1000
```

### Save Results?
```bash
python repair_unvalidated_data.py --output my_report.json
```

## What You'll See

```
Timestamp: 2025-11-19T15:30:45.123456
Duration: 245.67s

Total Unvalidated Found: 45000
Records Processed: 45000
Records Validated: 42150      ← Good data (94%)
Records Rejected: 2850        ← Needs review (6%)

Quality Score: Average 0.91 (Range: 0.0 to 1.0)

Symbols Processed: AAPL, BTC, ETH, MSFT, ...
Timeframes Processed: 1d, 1h, 5m
Errors: 0
```

## What "Rejected" Means

Not bad data, just flagged:

- **Stock split detected** → normal, may need adjustment
- **Unusual volume** → earnings/expiration, or delisting
- **Large price move** → volatility event or data anomaly
- **Data constraint fail** → rare, actual error

All records stay in database with notes for manual review if needed.

## After Repair

Your API will automatically:
- Return only validated data (score >= 0.85) by default
- Flag anomalies in `validation_notes` field
- Keep all data (nothing deleted)

## If Something Goes Wrong

```bash
# Revert is easy - just run again with different threshold
python repair_unvalidated_data.py --quality-threshold 0.80

# Or check what failed
python repair_unvalidated_data.py --dry-run --output debug.json
cat debug.json | jq '.errors[]'
```

## FAQ

**How long does it take?**  
~5-10 min per 10k records  

**Will it lock my database?**  
No, runs in the background  

**Can I stop it?**  
Yes (Ctrl+C), it's safe to restart  

**Can I run while API is live?**  
Yes, but may be slower  

---

See `VALIDATION_REPAIR_GUIDE.md` for deep dive.
