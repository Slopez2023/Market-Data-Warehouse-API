# Timeframes Configuration Guide

## Current Status

### What's Being Pulled
Currently, the system is configured to pull data for **only 2 timeframes**:
- **1h** (1 hour)
- **1d** (1 day)

This applies to:
- ✅ All 20 stocks (AAPL, MSFT, GOOGL, etc.)
- ✅ All 22 crypto assets (BTC-USD, ETH-USD, etc.)
- ✅ All 20 ETFs (SPY, QQQ, etc.)

### Available Timeframes (Not Currently Used)
The system technically supports but **is NOT pulling**:
- 5m (5 minutes) ❌
- 15m (15 minutes) ❌
- 30m (30 minutes) ❌
- 4h (4 hours) ❌
- 1w (1 week) ❌

## Database Configuration

### Current Tracked Symbols
```sql
SELECT symbol, asset_class, timeframes FROM tracked_symbols LIMIT 5;

 symbol | asset_class | timeframes
--------+-------------+------------
 AAPL   | stock       | {1h,1d}
 MSFT   | stock       | {1h,1d}
 BTC-USD| crypto      | {1h,1d}
 ETH-USD| crypto      | {1h,1d}
 SPY    | etf         | {1h,1d}
```

## How Timeframes Are Fetched

### Backfill Process Flow
```python
For each symbol:
  For each configured timeframe:
    Fetch data from Polygon.io
    Validate data
    Insert into database

# Example: BTC-USD with {1h, 1d}
Fetch BTC-USD 1h data → Insert to DB
Fetch BTC-USD 1d data → Insert to DB
```

### Code Reference (src/scheduler.py)
```python
for symbol, asset_class, timeframes in self.symbols:
    for timeframe in timeframes:  # Iterates through [1h, 1d]
        records = await self._backfill_symbol(symbol, asset_class, timeframe)
```

## How to Change Timeframes

### Option 1: For All Symbols (Global Update)
```sql
-- Update all symbols to use more timeframes
UPDATE tracked_symbols
SET timeframes = ARRAY['5m', '15m', '30m', '1h', '4h', '1d', '1w'];

-- Verify
SELECT symbol, timeframes FROM tracked_symbols LIMIT 5;
```

### Option 2: For Specific Asset Classes
```sql
-- Update only crypto to have more timeframes
UPDATE tracked_symbols
SET timeframes = ARRAY['5m', '15m', '30m', '1h', '4h', '1d', '1w']
WHERE asset_class = 'crypto';

-- Update only stocks
UPDATE tracked_symbols
SET timeframes = ARRAY['1h', '4h', '1d']
WHERE asset_class = 'stock';

-- Leave ETFs as-is
-- (no update needed)
```

### Option 3: For Specific Symbols
```sql
-- Update just Bitcoin
UPDATE tracked_symbols
SET timeframes = ARRAY['5m', '15m', '30m', '1h', '4h', '1d', '1w']
WHERE symbol = 'BTC-USD';

-- Update just Apple
UPDATE tracked_symbols
SET timeframes = ARRAY['1h', '4h', '1d']
WHERE symbol = 'AAPL';
```

### Option 4: Via API (if admin endpoint available)
```bash
# Add new timeframe to existing symbol
curl -X PUT http://localhost:8000/api/v1/admin/symbols/BTC-USD/timeframes \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{"timeframes": ["5m", "15m", "30m", "1h", "4h", "1d", "1w"]}'
```

## Performance Impact

### Data Volume Increase
```
Current (2 timeframes):
- Stocks: 20 symbols × 2 timeframes = 40 backfill jobs
- Crypto: 22 symbols × 2 timeframes = 44 backfill jobs
- ETFs:   20 symbols × 2 timeframes = 40 backfill jobs
- Total:                              124 backfill jobs

If all timeframes added (7 total):
- Stocks: 20 symbols × 7 timeframes = 140 backfill jobs
- Crypto: 22 symbols × 7 timeframes = 154 backfill jobs
- ETFs:   20 symbols × 7 timeframes = 140 backfill jobs
- Total:                              434 backfill jobs
```

### Storage Requirements
```
Assumptions:
- 30 days of data per timeframe per symbol
- ~30 candles per timeframe per symbol per month

Current (2 timeframes):
- 60 symbols × 2 timeframes × 30 candles = 3,600 records
- Estimated: ~0.5 MB

All timeframes (7 total):
- 60 symbols × 7 timeframes × 30 candles = 12,600 records
- Estimated: ~1.5 MB
```

### API Request Impact
```
Current backfill (2 timeframes):
- ~124 API requests per backfill
- Estimated: 30-45 seconds execution time

All timeframes (7 total):
- ~434 API requests per backfill
- Estimated: 2-3 minutes execution time

Rate limit: 150 requests/minute
Safe level: ~75 requests at startup
```

## Recommended Configurations

### Minimal (Current) ✅
```
Timeframes: [1h, 1d]
Use Case: Daily monitoring
Storage: ~0.5 MB
Time: 30-45 seconds
Polygon Cost: Low
```

### Moderate (Recommended)
```
Timeframes: [1h, 4h, 1d, 1w]
Use Case: Day/swing trading analysis
Storage: ~1.0 MB
Time: 1-2 minutes
Polygon Cost: Moderate
```

### Comprehensive (Maximum)
```
Timeframes: [5m, 15m, 30m, 1h, 4h, 1d, 1w]
Use Case: Detailed technical analysis
Storage: ~1.5 MB
Time: 2-3 minutes
Polygon Cost: High
```

## Implementation Steps

### To Add More Timeframes:

1. **Connect to database**
```bash
docker exec market_data_postgres psql -U postgres -d market_data
```

2. **Check current config**
```sql
SELECT symbol, asset_class, timeframes FROM tracked_symbols LIMIT 10;
```

3. **Update timeframes**
```sql
UPDATE tracked_symbols
SET timeframes = ARRAY['5m', '15m', '30m', '1h', '4h', '1d', '1w'];
```

4. **Verify update**
```sql
SELECT symbol, timeframes FROM tracked_symbols WHERE symbol = 'BTC-USD';
```

5. **Restart backfill** (optional - next scheduled run will use new config)
```bash
# Next backfill will automatically use new timeframes
# Or trigger manually via API if endpoint exists
```

## Crypto-Specific Considerations

### Why Crypto Uses Same Timeframes as Stocks
- **24/7 Trading**: Crypto trades 24/7, so 1h and 1d are most meaningful
- **Volatility**: Higher volatility makes frequent data pulls less critical
- **API Cost**: Additional timeframes increase API costs
- **Storage**: Limited benefit for 5m-30m data in 24/7 market

### Crypto Advantages with More Timeframes
```
✓ 5m: Perfect for algorithmic trading and bots
✓ 15m: Ideal for swing trading entries/exits
✓ 30m: Good for momentum trading
✓ 1h: Daily trading positions
✓ 4h: Position trading analysis
✓ 1d: Trend following
✓ 1w: Long-term trend identification
```

## Monitoring

### Check Current Backfill Status
```sql
SELECT symbol, asset_class, timeframes 
FROM tracked_symbols 
WHERE asset_class = 'crypto'
ORDER BY symbol;
```

### View Data Points Per Symbol
```sql
SELECT symbol, timeframe, COUNT(*) as record_count
FROM market_data
GROUP BY symbol, timeframe
ORDER BY symbol, timeframe;
```

### Check Backfill Logs
```bash
docker logs market_data_api | grep "Backfilling"
```

## FAQ

### Q: Will adding timeframes break existing data?
**A:** No. New timeframes will add new records. Existing 1h and 1d data is preserved.

### Q: How often will new timeframes be backfilled?
**A:** Daily at the scheduled time (default 2 AM UTC), same as current timeframes.

### Q: Can I have different timeframes per symbol?
**A:** Yes, use the "Option 3" approach above to set per-symbol timeframes.

### Q: Will the dashboard display all timeframes?
**A:** Currently the dashboard shows which timeframes exist, but analysis would need updates to utilize new timeframes.

### Q: How do I revert to just 1h and 1d?
**A:** Use the same UPDATE SQL command but with `ARRAY['1h', '1d']`.

## Summary

- **Current**: Pulling 1h and 1d data for all symbols
- **Crypto Fix**: ✅ Now working with normalized symbols
- **Timeframes**: Can be expanded via database UPDATE
- **Recommended**: Keep 1h/1d + 4h for most use cases
- **Data Volume**: Acceptable even with all 7 timeframes

---

**Last Updated**: 2025-11-12  
**Status**: Currently configured for 1h and 1d  
**Recommendation**: Expand to [1h, 4h, 1d, 1w] for balanced analysis
