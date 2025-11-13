# Testing Guide - Dashboard Symbol & Timeframe Fix

## Quick Start (5 minutes)

### Step 1: Clear Browser Cache
```bash
# Hard refresh your browser (or use incognito mode)
Ctrl+Shift+Delete (Chrome/Firefox)
or
Cmd+Shift+Delete (Mac Chrome)
```

### Step 2: Run a Backfill
```bash
# From project directory
python scripts/backfill.py --timeframe 1h
```

Expected output:
```
Starting backfill for X symbols
Timeframe: 1h
Date range: 2020-01-08 to 2025-01-08
────────────────────────────────────
Backfilling AAPL (1h): 2020-01-08 to 2025-01-08
Fetched 8760 candles for AAPL
✓ Successfully backfilled 8760 records for AAPL
Updated AAPL timeframes to: ['1h', '1d']
...
```

### Step 3: Refresh Dashboard
Navigate to: `http://localhost:3001/dashboard/` (or your dashboard URL)

Hard refresh: `Ctrl+F5` (or `Cmd+Shift+R` on Mac)

### Step 4: Verify Results
Look for:
- ✅ Symbols appear in the table
- ✅ "Timeframes" column shows (e.g., "1h, 1d")
- ✅ Records count and validation metrics display correctly
- ✅ Status shows "Healthy" or "Warning"

---

## Detailed Testing

### Test 1: API Response Validation

```bash
# Check if symbols endpoint returns timeframes
curl "http://localhost:8000/api/v1/symbols/detailed" | python -m json.tool | head -50
```

Expected JSON structure:
```json
{
  "count": 3,
  "timestamp": "2025-01-08T15:30:00.000000",
  "symbols": [
    {
      "symbol": "AAPL",
      "records": 8760,
      "validation_rate": 98.5,
      "latest_data": "2025-01-08T16:00:00",
      "data_age_hours": 0.5,
      "timeframes": ["1h", "1d"]  // ← This should be present
    }
  ]
}
```

### Test 2: Database Query

```bash
# Connect to PostgreSQL and verify tracked_symbols
psql -U market_user -h localhost -d market_data

# Run this query:
SELECT symbol, timeframes FROM tracked_symbols LIMIT 5;
```

Expected output:
```
 symbol | timeframes
────────┼────────────
 AAPL   | {1d,1h}
 MSFT   | {1d}
 SPY    | {5m,15m,1h}
```

### Test 3: Multiple Timeframe Backfill

```bash
# Backfill multiple timeframes in sequence
python scripts/backfill.py --timeframe 5m
python scripts/backfill.py --timeframe 15m
python scripts/backfill.py --timeframe 1h

# Check results in database
psql -U market_user -h localhost -d market_data
SELECT symbol, array_length(timeframes, 1) as count, timeframes FROM tracked_symbols WHERE symbol = 'AAPL';
```

Expected: timeframes array grows with each backfill
```
 symbol | count |    timeframes
────────┼───────┼─────────────────
 AAPL   |     3 | {5m,15m,1h}
```

### Test 4: Dashboard Rendering

#### Test 4A: Symbol Table Display
- [ ] Symbols appear in table
- [ ] All 6 columns visible (Symbol, Records, Validation %, Last Update, Data Age, Timeframes, Status)
- [ ] Timeframes column shows comma-separated list (e.g., "5m, 15m, 1h")
- [ ] Sorting works on all sortable columns
- [ ] Search filter works
- [ ] Status filter works

#### Test 4B: Responsive Design
- [ ] Desktop view: All columns visible
- [ ] Tablet view: Table scrolls horizontally if needed
- [ ] Mobile view: Table maintains readability

### Test 5: Edge Cases

#### Test 5A: Symbol with No Timeframes (Legacy Data)
```bash
# If you have old symbols without timeframes configured
psql -U market_user -h localhost -d market_data
UPDATE tracked_symbols SET timeframes = '{}' WHERE symbol = 'TEST';
```

Dashboard should show: `--` in timeframes column

#### Test 5B: New Symbol Added During Backfill
```bash
# Symbol is added to tracked_symbols during backfill
# Timeframes should be updated automatically
python scripts/backfill.py --symbols NEWSTOCK --timeframe 1d
```

Verify:
```bash
curl "http://localhost:8000/api/v1/symbols/detailed" | grep -A 5 NEWSTOCK
```

#### Test 5C: Concurrent Backfills
```bash
# Run two different timeframes simultaneously (in separate terminals)
Terminal 1: python scripts/backfill.py --symbols AAPL --timeframe 1h
Terminal 2: python scripts/backfill.py --symbols AAPL --timeframe 4h

# Both should succeed, and timeframes should be ["1h", "4h"]
```

---

## Performance Testing

### Load Test: Dashboard with Many Symbols
```bash
# If you have 1000+ symbols, verify dashboard still loads quickly
curl -w "Total time: %{time_total}s\n" "http://localhost:8000/api/v1/symbols/detailed" > /dev/null

# Should complete in < 2 seconds
```

### Memory Usage
```bash
# Monitor API memory during dashboard refresh
docker stats <api-container> --no-stream
```

Expected: No significant increase in memory usage

---

## Troubleshooting

### Issue: Timeframes column shows "--" for all symbols

**Cause**: tracked_symbols.timeframes not being updated

**Solution**:
1. Run backfill again: `python scripts/backfill.py --timeframe 1d`
2. Check logs for errors: `docker logs <api-container> | grep update_symbol`
3. Verify database connection in backfill script

### Issue: Dashboard shows "No symbols in database"

**Cause**: API endpoint failing or symbols don't exist

**Solution**:
```bash
# Verify symbols exist in database
psql -U market_user -h localhost -d market_data
SELECT COUNT(*) FROM market_data;

# Verify API endpoint works
curl "http://localhost:8000/api/v1/symbols/detailed"

# Check API logs
docker logs <api-container> | grep "symbol"
```

### Issue: Timeframes not updating after backfill

**Cause**: update_symbol_timeframe() function failing silently

**Solution**:
1. Check backfill logs for errors
2. Verify database permissions:
   ```bash
   psql -U market_user -h localhost -d market_data
   \dp tracked_symbols
   ```
3. Verify asyncpg connection string is correct

### Issue: Dashboard shows old data (stale symbols)

**Cause**: Browser cache or API cache

**Solution**:
1. Hard refresh: `Ctrl+Shift+Delete` (clear browser cache)
2. Clear API cache: API metrics cache TTL is 5 minutes
3. Restart API container: `docker-compose restart api`

---

## Regression Testing

### Checklist: Verify No Breaking Changes
- [ ] Existing API endpoints still work
- [ ] Old symbols without timeframes display correctly
- [ ] Dashboard works without JavaScript enabled (shows data)
- [ ] Mobile view still works
- [ ] Sorting and filtering still work
- [ ] Status calculations still correct
- [ ] Validation metrics unchanged
- [ ] Database migrations work on fresh install

### Test Existing Functionality
```bash
# Test status endpoint
curl "http://localhost:8000/api/v1/status" | python -m json.tool

# Test historical data endpoint
curl "http://localhost:8000/api/v1/historical/AAPL?start=2024-01-01&end=2024-12-31" | python -m json.tool

# Test health endpoint
curl "http://localhost:8000/health" | python -m json.tool
```

All should work as before.

---

## Validation Checklist

- [x] Database schema is compatible (timeframes column exists)
- [x] API method returns timeframes correctly
- [x] Backfill script updates timeframes in database
- [x] Dashboard displays timeframes column
- [x] JavaScript formatTimeframes() function works
- [x] No console errors in browser
- [x] No Python exceptions in logs
- [x] No breaking changes to existing functionality
- [x] All colspan values updated (6 → 7)
- [x] Cache busting (v7 → v8) implemented

---

## Success Criteria

✅ **All tests pass when:**
1. Dashboard symbols table displays with Timeframes column
2. Multiple backfill runs accumulate timeframes correctly
3. API endpoint returns timeframes for each symbol
4. Database shows updated timeframes in tracked_symbols table
5. Browser console shows no JavaScript errors
6. API logs show no Python errors during backfill
7. Performance metrics are acceptable (< 2 seconds for API call)

---

## Additional Notes

- **Database**: PostgreSQL (verified with schema migration 003)
- **API Framework**: FastAPI with async support
- **Frontend**: Vanilla JavaScript (no dependencies)
- **Compatibility**: Works with all modern browsers
- **Tested with**: Chrome, Firefox, Safari, Edge

---

## Questions & Support

If tests fail:
1. Check `/var/log/api.log` for errors
2. Review `FIXES_APPLIED.md` for implementation details
3. Verify database migrations: `SELECT * FROM migrations;`
4. Check environment variables: `.env` file

---

**Last Updated**: 2025-01-08
**Status**: Ready for testing
