# Validation Repair Guide

## Overview

The `repair_unvalidated_data.py` script identifies all records in the database with `validated=FALSE` and re-runs them through the full validation pipeline, updating their quality scores and validation flags.

## Problem Statement

**Current State:**
- Backfilled data enters database with `validated=FALSE, quality_score=0.0`
- No process re-validates these records after insertion
- Over time, accumulates unvalidated data that should be validated or flagged

**Why This Happens:**
- `insert_ohlcv_backfill()` in `database_service.py` intentionally skips validation during bulk import (performance)
- Validation is normally done in the scheduler on live data fetch
- Historical backfill data never gets the validation treatment

## What This Script Does

### Validation Pipeline (Per Candle)

For each unvalidated record, the script:

1. **OHLCV Constraints Check**
   - Verifies: `High >= max(Open, Close)`
   - Verifies: `Low <= min(Open, Close)`
   - Verifies: All prices > 0
   - Deducts 0.5 from quality score if violated

2. **Price Movement Anomaly Check**
   - Flags moves > 500% in a single day
   - Detects stock splits, halts, data corruption
   - Deducts 0.3 from quality score

3. **Gap Detection** (Previous Close Comparison)
   - Calculates gap % from previous candle's close
   - Flags gaps > 10% (except normal Monday opens)
   - Indicates possible splits, halts, or data issues
   - Deducts 0.2 from quality score

4. **Volume Anomaly Detection**
   - Compares to median volume for symbol/timeframe
   - High anomaly: > 10x median (possible flash crash)
   - Low anomaly: < 10% median (possible delisting)
   - Deducts 0.1-0.15 from quality score

### Final Validation Decision

- **Validated:** Quality score >= 0.85 (default threshold)
- **Rejected:** Quality score < 0.85 (flagged for review)
- All metadata stored: quality_score, validation_notes, gap_detected, volume_anomaly

## Usage

### Basic Usage

```bash
# Repair all unvalidated records (all symbols, all timeframes)
python repair_unvalidated_data.py

# Preview changes without updating database
python repair_unvalidated_data.py --dry-run

# Repair only first 1000 records (for testing)
python repair_unvalidated_data.py --limit 1000
```

### Targeted Repair

```bash
# Repair specific symbols only
python repair_unvalidated_data.py --symbols AAPL,BTC,SPY

# Repair specific timeframes only
python repair_unvalidated_data.py --timeframes 1d,1h

# Repair specific symbols AND timeframes
python repair_unvalidated_data.py --symbols AAPL,BTC --timeframes 1d,1h
```

### Advanced Options

```bash
# Control batch update size (default: 100)
python repair_unvalidated_data.py --batch-size 250

# Change quality threshold for validation (default: 0.85)
python repair_unvalidated_data.py --quality-threshold 0.80

# Save report to JSON file
python repair_unvalidated_data.py --output repair_report.json

# Full dry-run with detailed output
python repair_unvalidated_data.py --dry-run --limit 5000 --output dry_run_report.json
```

## Output Report

The script generates a summary report with:

```json
{
  "timestamp": "2025-11-19T15:30:45.123456",
  "dry_run": false,
  "duration_seconds": 245.67,
  "total_unvalidated_found": 45000,
  "records_processed": 45000,
  "records_validated": 42150,
  "records_rejected": 2850,
  "validation_rate": 93.7,
  "quality_score_stats": {
    "average": 0.91,
    "min": 0.0,
    "max": 1.0
  },
  "symbols_processed": ["AAPL", "BTC", "SPY", ...],
  "timeframes_processed": ["1d", "1h", "5m"],
  "error_count": 0,
  "errors": []
}
```

**Key Metrics:**
- **validation_rate**: % of records that passed quality threshold (goal: 95%+)
- **quality_score_stats**: Distribution of quality scores
- **error_count**: Database update failures (should be 0)

## Recommended Process

### Phase 1: Dry Run (Assessment)

```bash
# See how many records need repair
python repair_unvalidated_data.py --dry-run

# Or test on subset
python repair_unvalidated_data.py --dry-run --limit 5000 --output phase1_assessment.json
```

Expected output shows:
- Total unvalidated records
- Estimated validation rate
- Any errors or edge cases

### Phase 2: Targeted Repair (High-Priority Symbols)

```bash
# Repair your most important symbols first
python repair_unvalidated_data.py --symbols AAPL,MSFT,GOOGL --output phase2_blue_chips.json
```

Monitor:
- Validation rate (should be 90%+)
- Quality score distribution
- Error count (should be 0)

### Phase 3: Full Repair

```bash
# Run full repair (may take 10-30 min depending on data size)
python repair_unvalidated_data.py --output full_repair_report.json

# Monitor with increased batch size for speed
python repair_unvalidated_data.py --batch-size 500 --output full_repair_report.json
```

### Phase 4: Post-Repair Verification

```sql
-- Check validation distribution
SELECT 
    validated,
    COUNT(*) as count,
    ROUND(AVG(quality_score)::numeric, 2) as avg_quality,
    MIN(quality_score) as min_quality,
    MAX(quality_score) as max_quality
FROM market_data
GROUP BY validated;

-- Check for any remaining 0-quality records
SELECT COUNT(*) as zero_quality_count
FROM market_data
WHERE quality_score = 0.0;

-- Check validation notes for patterns
SELECT 
    validation_notes,
    COUNT(*) as count
FROM market_data
WHERE validated = FALSE
GROUP BY validation_notes
ORDER BY count DESC
LIMIT 10;
```

## Expected Results

### Typical Outcome

For a mature project with 1-2 years of backfilled data:

```
Total Unvalidated: ~50,000 records
Records Validated:  ~48,000 (96%)
Records Rejected:   ~2,000 (4%)

Quality Score Distribution:
- >= 0.95: 75% (excellent data)
- 0.85-0.95: 21% (good data with minor anomalies)
- 0.70-0.85: 3% (flags for review)
- < 0.70: 1% (corrupted or gap data)

Rejection Reasons (top):
1. Large gaps (stock splits): ~45%
2. Volume anomalies: ~35%
3. Extreme price moves: ~15%
4. OHLCV constraint violations: ~5%
```

### What "Rejected" Records Mean

Records with `validated=FALSE` after repair are **not bad data** - they're **flagged for review**:

- **Gap detected**: Stock split, halt, or corporate action
  - Review dividend/split history, apply adjustment if needed
  - May be intentionally kept "unvalidated" until adjusted

- **Volume anomaly**: Unusual trading activity
  - May indicate options expiration, short squeeze, earnings
  - Usually legitimate but worth monitoring

- **Price movement**: Large intraday move
  - Might be data error OR legitimate volatility event
  - Check against news/earnings dates

- **OHLCV constraints**: Data quality issue
  - Rare, but indicates Polygon API data error
  - Should be deleted or marked with warning

## Troubleshooting

### Script Runs Slowly

**Cause**: Loading full historical context for every symbol/timeframe

**Solutions**:
```bash
# Reduce scope
python repair_unvalidated_data.py --limit 5000 --timeframes 1d

# Increase batch size (more memory, fewer DB roundtrips)
python repair_unvalidated_data.py --batch-size 500

# Run in off-peak hours
```

### High Rejection Rate (< 85% validation)

**Possible Causes**:
1. **Quality threshold too strict** - Lower it slightly
   ```bash
   python repair_unvalidated_data.py --quality-threshold 0.80 --output debug_report.json
   ```

2. **Known data issues** - Check validation_notes
   ```sql
   SELECT validation_notes, COUNT(*) 
   FROM market_data 
   WHERE validated = FALSE 
   GROUP BY validation_notes 
   ORDER BY count DESC;
   ```

3. **Incorrect median volume calculation** - May indicate deleted/suspended assets

### Database Update Failures

**Check error log**:
```bash
# Review report for specific failures
python repair_unvalidated_data.py --output repair_errors.json

# Check which records failed
cat repair_errors.json | jq '.errors[]'
```

**Common causes**:
- Connection pool exhaustion → reduce batch size
- Unique constraint violations → check for duplicate timestamps
- Timestamp/data type mismatches → rare, may need manual fixing

## Integration with Scheduler

After repair, the scheduler will:

1. **Skip already-validated records** during daily updates
2. **Validate new candles** coming from live feeds
3. **Gradually improve validation scores** for edge cases

The scheduler queries use:
```sql
WHERE validated = TRUE  -- Only returns validated data
WHERE validated_only = True  -- API parameter for /data endpoints
```

This ensures consumers get high-quality data by default.

## FAQ

**Q: Will this delete any data?**
A: No, it only updates validation flags and quality scores. All OHLCV data is preserved.

**Q: Can I run this while API is live?**
A: Yes, but performance may be impacted. Recommended to run in off-peak hours.

**Q: What if quality threshold is wrong?**
A: Run again with different threshold - no harm, just updates same records.

**Q: How often should I run this?**
A: Once after initial backfill, then only if:
- You suspect data quality issues
- You've added new corporate event enrichment
- You notice unusual validation rates

**Q: Can I validate only certain timeframes?**
A: Yes, use `--timeframes 1d,1h` to target specific timeframes.

**Q: What's the difference between "validated" and "quality_score"?**
A: 
- **quality_score**: 0.0-1.0 actual score based on checks
- **validated**: boolean flag (TRUE if score >= threshold)

## Performance Notes

### Expected Runtime
- 10,000 records: ~5-10 minutes (25 records/sec)
- 50,000 records: ~25-50 minutes
- 100,000 records: ~50-100 minutes

### Resource Usage
- Memory: ~500MB baseline + 50-100MB per 10K records
- CPU: Single-threaded, uses 1-2 cores
- Database: 5-10 connection pool, ~50-100 IOPS

### Optimization Tips
```bash
# Faster for large datasets (more memory, fewer DB roundtrips)
python repair_unvalidated_data.py --batch-size 1000

# Parallel processing (run multiple instances on different symbols)
python repair_unvalidated_data.py --symbols AAPL,MSFT,GOOGL &
python repair_unvalidated_data.py --symbols AMZN,TSLA,META &
python repair_unvalidated_data.py --symbols NFLX,NVIDIA,INTEL &
```

## Next Steps

1. **Run dry-run** to understand current state
2. **Repair high-priority symbols** first
3. **Monitor quality distribution** to tune threshold if needed
4. **Update scheduler** if validation logic needs improvements
5. **Document results** for future reference
