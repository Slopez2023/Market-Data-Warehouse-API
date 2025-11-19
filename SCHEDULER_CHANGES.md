# Scheduler Change: Daily → Hourly

## Summary
The backfill scheduler has been changed from **daily (2 AM UTC)** to **hourly execution**.

## Changes Made

### 1. Core Scheduler Changes (`src/scheduler.py`)
- ✅ Changed from daily cron trigger to hourly cron trigger
- ✅ Removed `schedule_hour` from CronTrigger (now runs every hour)
- ✅ Kept `schedule_minute` for configurable minute within each hour
- ✅ Updated job ID: `daily_backfill` → `hourly_backfill`
- ✅ Updated job name: `Daily OHLCV Backfill` → `Hourly OHLCV Backfill`
- ✅ Added `is_running()` method to check scheduler status

### 2. Configuration Changes (`src/config.py`)
- ✅ Marked `BACKFILL_SCHEDULE_HOUR` as deprecated in description
- ✅ Updated logging to show "Every hour at :MM UTC" instead of "HH:MM UTC daily"
- ✅ Kept validation for backward compatibility (accepts but doesn't use hour)

### 3. Docker Changes (`docker-compose.yml`)
- ✅ Removed `BACKFILL_SCHEDULE_HOUR: 2` from environment variables
- ✅ Kept `BACKFILL_SCHEDULE_MINUTE: 0` for per-hour timing

## Environment Variables

| Variable | Old Behavior | New Behavior | Default |
|----------|--------------|--------------|---------|
| `BACKFILL_SCHEDULE_HOUR` | Set UTC hour (0-23) | Ignored/Deprecated | 2 |
| `BACKFILL_SCHEDULE_MINUTE` | Set minute (0-59) | Run at this minute every hour | 0 |

## Examples

### Default Configuration (Every hour at :00 UTC)
```bash
# No need to set BACKFILL_SCHEDULE_HOUR
export BACKFILL_SCHEDULE_MINUTE=0
```

### Custom Configuration (Every hour at :30 UTC)
```bash
export BACKFILL_SCHEDULE_MINUTE=30
```

## Docker Compose

**Before:**
```yaml
environment:
  BACKFILL_SCHEDULE_HOUR: 2
  BACKFILL_SCHEDULE_MINUTE: 0
```

**After:**
```yaml
environment:
  BACKFILL_SCHEDULE_MINUTE: 0
```

## Testing

Run the scheduler test validation:
```bash
python test_scheduler_changes.py
```

Expected output: ✅ ALL TESTS PASSED

## Rollback

If needed to revert to daily scheduling:
```python
# In src/scheduler.py, line 109
# Change from:
trigger = CronTrigger(minute=self.schedule_minute)

# To:
trigger = CronTrigger(hour=self.schedule_hour, minute=self.schedule_minute)
```

## Next Steps

1. ✅ Code changes verified
2. ✅ Docker config updated
3. ⏳ Test in Docker environment (requires Docker daemon)
4. ⏳ Deploy to production

## Files Modified

- `src/scheduler.py` - Hourly trigger logic
- `src/config.py` - Deprecated hour parameter, updated logging
- `docker-compose.yml` - Removed BACKFILL_SCHEDULE_HOUR
- `test_scheduler_changes.py` - New validation test
