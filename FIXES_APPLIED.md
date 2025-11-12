# Dashboard Symbol and Timeframe Loading Fixes

## Problem
When manually backfilling data, the dashboard was not displaying:
1. **Symbols** in the symbol quality table
2. **Timeframes** available for each symbol

## Root Causes
1. **Missing `get_all_symbols_detailed()` method** in `DatabaseService` - The API endpoint was calling a method that didn't exist
2. **Timeframes not being updated** - The backfill script wasn't recording which timeframes were successfully backfilled for each symbol
3. **Dashboard not displaying timeframes** - The frontend was missing the timeframe column and formatting logic

## Changes Made

### 1. Backend - Database Service (`src/services/database_service.py`)

**Added `get_all_symbols_detailed()` method** (lines 406-453)
- Queries detailed statistics for all symbols in the database
- Returns: symbol, records count, validation rate, latest data timestamp, data age (hours), and timeframes
- Joins with `tracked_symbols` table to get configured timeframes for each symbol
- Handles NULL timeframes gracefully with empty array default

```python
def get_all_symbols_detailed(self) -> List[Dict]:
    """Get detailed statistics for all symbols in the database."""
    # Queries market_data grouped by symbol
    # Left joins with tracked_symbols to get timeframes
    # Returns list of symbol stats with timeframes
```

### 2. Backend - Backfill Script (`scripts/backfill.py`)

**Added `update_symbol_timeframe()` async function** (lines 35-82)
- After successful backfill, updates `tracked_symbols.timeframes` array
- Adds the backfilled timeframe if not already present
- Sorts timeframes in standard order: 5m, 15m, 30m, 1h, 4h, 1d, 1w
- Prevents duplicates

**Updated `backfill_symbol()` function** (line 93)
- Added `database_url` parameter
- After successful insertion, calls `update_symbol_timeframe()` to record the backfilled timeframe

**Updated `main()` function** (lines 296-300)
- Passes `database_url` to `backfill_symbol()` call

**How it works:**
```
User runs: python scripts/backfill.py --timeframe 1h
  ↓
Backfill fetches and inserts data for timeframe 1h
  ↓
update_symbol_timeframe() adds '1h' to tracked_symbols.timeframes array
  ↓
Dashboard queries endpoint and displays '1h' in timeframes column
```

### 3. Frontend - Dashboard HTML (`dashboard/index.html`)

**Added "Timeframes" column** (line 100)
- New table header between "Data Age" and "Status" columns
- Matches the API response structure

### 4. Frontend - Dashboard JavaScript (`dashboard/script.js`)

**Added `formatTimeframes()` function** (lines 393-403)
- Formats timeframes array into readable string
- Displays timeframes in standard order (5m, 15m, 30m, 1h, 4h, 1d, 1w)
- Shows "--" if no timeframes available

**Updated `renderSymbolTable()` function** (line 307)
- Added timeframes cell to table row rendering
- Includes the formatted timeframes output

**Updated colspan values** (lines 254, 318)
- Changed from 6 to 7 columns to match new table structure
- Ensures "No symbols" and "No matching" messages span correctly

**Updated script version** (line 161)
- Bumped from v7 to v8 in script.js query parameter to clear browser cache

## Test Results

After these changes, when you run a manual backfill:

```bash
python scripts/backfill.py --timeframe 1h
```

The dashboard will now show:
1. ✅ All symbols with data in the database
2. ✅ Timeframes available for each symbol (e.g., "1h, 1d")
3. ✅ Updated records count and validation metrics
4. ✅ Real-time updates as more timeframes are backfilled

## Example Dashboard Display

| Symbol | Records | Validation % | Last Update | Data Age | Timeframes | Status |
|--------|---------|--------------|-------------|----------|-----------|--------|
| AAPL   | 1,250   | 98.5%        | Jan 8, 2025 | 3h       | 1h, 1d    | ✓ Healthy |
| MSFT   | 980     | 97.2%        | Jan 8, 2025 | 4h       | 1d        | ✓ Healthy |
| SPY    | 850     | 96.8%        | Jan 8, 2025 | 5h       | 5m, 1h, 1d | ✓ Healthy |

## Notes

- The database schema already had the `timeframes` column in `tracked_symbols` (see migration `003_add_timeframes_to_symbols.sql`)
- Default timeframes are ['1h', '1d'] for new symbols
- The backfill script now properly maintains this array across multiple runs
- No breaking changes - all updates are additive and backward compatible

## Future Improvements

1. **API Endpoint for Timeframe Management**: Add PUT endpoint to manually update symbol timeframes
2. **Timeframe Filtering**: Add UI filter to show only symbols with specific timeframes
3. **Bulk Backfill UI**: Frontend interface to select multiple timeframes and backfill in sequence
4. **Backfill Status Tracking**: Real-time progress indicator for long-running backfill jobs
