# Backfill Endpoint Fix: 400 Bad Request Error

## Problem

Dashboard backfill submission was returning **HTTP 400 Bad Request** when submitting with 40+ symbols:

```
POST http://localhost:8000/api/v1/backfill?symbols=TEST&symbols=AAPL&...&symbols=XLE
400 (Bad Request)
```

**Root Cause:** URL query parameters have length limits. With 42+ symbols + dates + timeframes, the URL exceeded the limit, causing the server to reject the request.

## Solution

Changed the backfill endpoint from **query parameters** to **JSON request body**:

### Before (Query Parameters)
```javascript
// Dashboard sent:
fetch('/api/v1/backfill?' + params.toString(), {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' }
})

// URL became too long:
/api/v1/backfill?symbols=TEST&symbols=AAPL&...&symbols=XLE&start_date=2025-10-18&...
```

### After (JSON Body)
```javascript
// Dashboard now sends:
fetch('/api/v1/backfill', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    symbols: ['TEST', 'AAPL', ..., 'XLE'],
    start_date: '2025-10-18',
    end_date: '2025-11-17',
    timeframes: ['5m', '15m', '1h', '1d']
  })
})
```

## Changes Made

### 1. API Endpoint (`main.py`)
- Changed from query parameters to JSON body request
- Uses `BackfillRequest` Pydantic model
- Validation handled by Pydantic (cleaner code)

### 2. Pydantic Model (`src/models.py`)
- New `BackfillRequest` model with validators
- Validates:
  - 1-100 symbols per request
  - YYYY-MM-DD date format
  - Start date < end date
  - Default timeframes: `['1d']`

### 3. Dashboard Script (`dashboard/script.js`)
- Updated `submitBackfill()` function
- Changed from URL query params to JSON body
- Same validation logic, cleaner implementation

## Validation Results

✅ All tests passed:
- 42 symbols accepted (real-world scenario)
- 100 symbols (maximum) accepted
- 101+ symbols rejected
- Invalid date formats rejected
- Invalid date ranges rejected
- Default timeframes work correctly

## API Endpoint Specification

**POST** `/api/v1/backfill`

**Request Body (JSON):**
```json
{
  "symbols": ["AAPL", "GOOGL", "TSLA", ...],
  "start_date": "2025-01-01",
  "end_date": "2025-12-31",
  "timeframes": ["5m", "15m", "1h", "1d"]
}
```

**Parameters:**
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `symbols` | `string[]` | Yes | 1-100 symbols |
| `start_date` | `string` | Yes | Format: YYYY-MM-DD |
| `end_date` | `string` | Yes | Format: YYYY-MM-DD, must be > start_date |
| `timeframes` | `string[]` | No | Default: `["1d"]` |

**Response (200 OK):**
```json
{
  "job_id": "uuid-string",
  "status": "queued",
  "symbols_count": 42,
  "symbols": ["AAPL", "GOOGL", ..., "..."],
  "date_range": {
    "start": "2025-10-18",
    "end": "2025-11-17"
  },
  "timeframes": ["5m", "15m", "1h", "1d"],
  "timestamp": "2025-11-17T12:00:00"
}
```

**Error (400 Bad Request):**
```json
{
  "detail": "Validation error: [error details]"
}
```

## Files Modified

| File | Changes |
|------|---------|
| `main.py` | Changed endpoint to accept JSON body with BackfillRequest model |
| `src/models.py` | Added BackfillRequest with validation |
| `dashboard/script.js` | Updated submitBackfill() to use JSON body |
| `test_backfill_request.py` | New validation tests |

## Testing

Run validation tests:
```bash
python test_backfill_request.py
```

Expected output: **ALL TESTS PASSED ✅**

## Backward Compatibility

The endpoint only supports JSON body requests now. Query parameters are no longer supported (they were causing the 400 error anyway).

## Deployment

1. ✅ Code changes implemented
2. ✅ Validation tests pass
3. ✅ Files compile without errors
4. Ready for deployment to production

When deploying:
- Dashboard automatically uses new JSON body format
- No database changes required
- No configuration changes required
- No breaking changes to other endpoints

## FAQ

**Q: Can I still use query parameters?**
A: No, the endpoint now only accepts JSON body to avoid URL length limits.

**Q: What's the maximum number of symbols?**
A: 100 symbols per request (enforced by Pydantic validation).

**Q: What timeframes are supported?**
A: All configured timeframes: `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1w`

**Q: What if I get validation errors?**
A: Check the error message in the response - it will tell you exactly what's wrong (symbol count, date format, etc.)
