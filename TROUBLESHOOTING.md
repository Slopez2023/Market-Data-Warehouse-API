# Dashboard Backfill - Troubleshooting Guide

## Quick Start

```bash
# 1. Ensure database is running
psql postgresql://market_user:changeMe123@localhost:5432/market_data -c "SELECT 1"

# 2. Run migrations to create tables
python -c "from dotenv import load_dotenv; load_dotenv(); from src.services.migrations import run_migrations; from src.config import config; run_migrations(config.database_url); print('✓ Migrations OK')"

# 3. Start the API server
python main.py
# or: uvicorn main:app --reload

# 4. Open dashboard
# http://localhost:8000/

# 5. Test validation script first
python validate_backfill.py
```

---

## Common Issues & Fixes

### Issue 1: Database Connection Error
**Error**: `(psycopg2.OperationalError) could not connect to server`

**Fix**:
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# If not running, start it (macOS):
brew services start postgresql

# Verify connection string in .env
cat .env | grep DATABASE_URL

# Test connection directly
psql postgresql://market_user:changeMe123@localhost:5432/market_data -c "SELECT 1"
```

---

### Issue 2: Migrations Don't Run
**Error**: `Migration runner failed`, tables don't exist

**Fix**:
```bash
# Run migrations manually first
python -c "from dotenv import load_dotenv; load_dotenv(); \
from src.services.migrations import run_migrations; \
from src.config import config; \
run_migrations(config.database_url); \
print('✓ Done')"

# Verify tables exist
psql postgresql://market_user:changeMe123@localhost:5432/market_data -c \
  "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'backfill%'"

# Should show:
# backfill_jobs
# backfill_job_progress
```

---

### Issue 3: API Won't Start
**Error**: `ImportError: cannot import name 'run_migrations'`

**Fix**:
```bash
# Verify file exists
ls -la src/services/migrations.py

# Check syntax
python -m py_compile src/services/migrations.py

# Try importing directly
python -c "from src.services.migrations import run_migrations; print('✓ Import OK')"
```

---

### Issue 4: Dashboard Loads But Backfill Button Does Nothing
**Check Browser Console** (F12 → Console tab):

```javascript
// Test API connectivity
fetch('http://localhost:8000/health')
  .then(r => r.json())
  .then(d => console.log('API OK:', d))
  .catch(e => console.error('API FAIL:', e))

// Test backfill endpoint
fetch('http://localhost:8000/api/v1/backfill?symbols=AAPL&start_date=2024-01-01&end_date=2024-01-31&timeframes=1h', 
  {method: 'POST', headers: {'Content-Type': 'application/json'}})
  .then(r => r.json())
  .then(d => console.log('Backfill response:', d))
  .catch(e => console.error('Backfill error:', e))
```

**If API returns error about "Backfill worker not initialized"**:
- The worker initializes during API startup in `lifespan()`
- Check logs for: `Backfill worker initialized`
- May need to restart the API

---

### Issue 5: Backfill Modal Won't Open
**Error**: Modal stays closed when clicking button

**Fix - Check Browser Console for errors**:
```javascript
// Manually trigger backfill modal
openBackfillModal()

// If error, check function exists
typeof openBackfillModal  // Should be 'function'
```

**If function doesn't exist**:
- Reload page (Ctrl+Shift+R / Cmd+Shift+R)
- Check script.js loaded: Network tab → script.js
- Check for JavaScript errors in Console tab

---

### Issue 6: Can't Submit Backfill - No Response
**Check Network Tab** (F12 → Network):

1. Click "Start Backfill"
2. Look for POST request to `/api/v1/backfill`
3. Click it, check Response tab

**If no request appears**:
- Validation error (check for red banner above table)
- JavaScript error (check Console tab)

**If request fails (red):**
- Check Response tab for error message
- Common: "No symbols selected", "Invalid dates", "No timeframes selected"

**If request succeeds (200) but nothing happens:**
- Check if `job_id` returned in response
- Check progress modal appears (should be automatic)

---

### Issue 7: Progress Modal Doesn't Update
**Symptom**: Modal shows but progress bar stays at 0%

**Check**:
```javascript
// See if polling is happening
// Open Console, then click "Start Backfill"
// Look for logs like: "Backfill job enqueued"

// Manually check job status
fetch('http://localhost:8000/api/v1/backfill/status/YOUR_JOB_ID')
  .then(r => r.json())
  .then(d => console.log(d))
```

**If status endpoint returns 404**:
- Job ID doesn't exist in database
- Check database: `SELECT id FROM backfill_jobs LIMIT 5`
- May mean job wasn't actually created

**If status is still "queued"**:
- Worker process hasn't started
- Check API logs for worker initialization
- Restart API: Stop (Ctrl+C), then `python main.py`

---

### Issue 8: Database Tables Exist But Still Get Errors
**Fix**:

```bash
# Drop and recreate tables
psql postgresql://market_user:changeMe123@localhost:5432/market_data << EOF
DROP TABLE IF EXISTS backfill_job_progress CASCADE;
DROP TABLE IF EXISTS backfill_jobs CASCADE;
EOF

# Re-run migrations
python -c "from dotenv import load_dotenv; load_dotenv(); \
from src.services.migrations import run_migrations; \
from src.config import config; \
run_migrations(config.database_url)"

# Verify
psql postgresql://market_user:changeMe123@localhost:5432/market_data -c \
  "SELECT * FROM backfill_jobs LIMIT 1"
```

---

### Issue 9: Symbols Not Persisting to Selection
**Fix**:

```javascript
// Check localStorage
localStorage.getItem('selected-symbols')
// Should show: ["AAPL","GOOGL"] or null

// Force clear
localStorage.removeItem('selected-symbols')

// Force save
localStorage.setItem('selected-symbols', JSON.stringify(['AAPL']))

// Reload
location.reload()
```

---

### Issue 10: API Logs Show No Activity
**Issue**: When you submit backfill, no logs appear

**Check API is actually running**:
```bash
# In API terminal, you should see:
# [timestamp] - INFO - Starting Market Data API
# [timestamp] - INFO - Migrations completed
# [timestamp] - INFO - Database connected
# [timestamp] - INFO - Scheduler started
# [timestamp] - INFO - Backfill worker initialized
```

**If you see "Backfill worker not initialized"**:
- Check import is in main.py line 41: `from src.services.migrations import run_migrations`
- Check migration call exists around line 83-86
- Look for error in startup: "Failed to initialize backfill worker"

**If backfill request doesn't log anything**:
- May be an error before logging
- Check response in browser Network tab
- May be validation error caught at route level

---

## Testing Checklist

Use this to systematically test each piece:

```bash
# 1. Database
[ ] psql connection works
[ ] backfill_jobs table exists
[ ] backfill_job_progress table exists

# 2. API
[ ] API starts without errors
[ ] /health endpoint responds
[ ] /api/v1/backfill route exists
[ ] Can POST to /api/v1/backfill (returns 200)

# 3. Dashboard
[ ] Page loads
[ ] Dashboard metrics appear
[ ] Symbols table populates
[ ] "Manual Backfill..." button clickable

# 4. Backfill Modal
[ ] Modal opens
[ ] Can enter symbols
[ ] Date defaults set
[ ] Timeframe checkboxes visible
[ ] "Start Backfill" submits

# 5. Job Processing
[ ] API returns job_id
[ ] Progress modal appears
[ ] Status updates from API
[ ] Job completes
[ ] Dashboard refreshes

# 6. Error Cases
[ ] Empty symbols shows error
[ ] Invalid dates shows error
[ ] No timeframe shows error
[ ] All errors auto-dismiss after 5s
```

---

## Debug Mode

Enable detailed logging:

**In main.py**, change:
```python
setup_structured_logging(config.log_level)
```

To:
```python
setup_structured_logging("DEBUG")
```

Then restart API and try backfill again. You'll see much more detail.

---

## Getting Help

If stuck, provide:

1. **Browser Console errors** (F12 → Console)
   ```bash
   # Copy-paste all red errors
   ```

2. **API server logs**
   ```bash
   # Copy-paste last 50 lines of output when starting python main.py
   ```

3. **Database check**
   ```bash
   psql postgresql://market_user:changeMe123@localhost:5432/market_data -c \
     "SELECT COUNT(*) FROM backfill_jobs; SELECT COUNT(*) FROM backfill_job_progress;"
   ```

4. **Network tab request/response**
   - Open F12 → Network
   - Submit backfill
   - Click POST /api/v1/backfill
   - Copy Response JSON

With those 4 things, we can diagnose almost any issue.

---

## Quick Reference: Files That Run at Startup

1. `main.py` - FastAPI app starts
   - Line 41: imports migrations
   - Line 83-86: runs migrations in lifespan()
   
2. `src/services/migrations.py` - creates tables
   - Reads `/database/*.sql` files
   - Executes each one
   
3. `src/services/backfill_worker.py` - initialized
   - `init_backfill_worker()` called
   
4. Dashboard loads `/dashboard/index.html`
   - Loads `/dashboard/script.js`
   - Starts auto-refresh (every 10 seconds)
   - Restores selected symbols from localStorage

If any of these fail, the system won't work properly.

