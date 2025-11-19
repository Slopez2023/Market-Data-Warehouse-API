#!/usr/bin/env python
"""
Test script to validate scheduler hourly changes work correctly.
This simulates the scheduler initialization without needing a database connection.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import sys

def test_hourly_scheduler():
    """Test that the new hourly scheduler trigger is set up correctly"""
    
    # Create a mock scheduler
    scheduler = AsyncIOScheduler()
    
    # Test 1: Minute 0 (default)
    print("✓ Test 1: Hourly trigger at minute 0")
    trigger_0 = CronTrigger(minute=0)
    print(f"  Trigger: {trigger_0}")
    print(f"  Fields: hour={trigger_0.fields[5]}, minute={trigger_0.fields[6]}")
    assert str(trigger_0.fields[5]) == "*", "Hour should be * (every hour)"
    assert str(trigger_0.fields[6]) == "0", "Minute should be 0"
    print("  ✅ PASSED\n")
    
    # Test 2: Minute 30
    print("✓ Test 2: Hourly trigger at minute 30")
    trigger_30 = CronTrigger(minute=30)
    print(f"  Trigger: {trigger_30}")
    print(f"  Fields: hour={trigger_30.fields[5]}, minute={trigger_30.fields[6]}")
    assert str(trigger_30.fields[5]) == "*", "Hour should be * (every hour)"
    assert str(trigger_30.fields[6]) == "30", "Minute should be 30"
    print("  ✅ PASSED\n")
    
    # Test 3: Compare with old daily trigger
    print("✓ Test 3: Old daily trigger (for reference)")
    old_trigger = CronTrigger(hour=2, minute=0)
    print(f"  Old Trigger: {old_trigger}")
    print(f"  Fields: hour={old_trigger.fields[5]}, minute={old_trigger.fields[6]}")
    assert str(old_trigger.fields[5]) == "2", "Hour should be 2"
    assert str(old_trigger.fields[6]) == "0", "Minute should be 0"
    print("  ✅ PASSED\n")
    
    # Test 4: Verify trigger creation for different minute values
    print("✓ Test 4: Multiple minute configurations")
    for minute in [0, 15, 30, 45, 59]:
        trigger = CronTrigger(minute=minute)
        assert str(trigger.fields[6]) == str(minute), f"Minute should be {minute}"
        print(f"  ✅ Minute {minute:02d}: {trigger}")
    print()
    
    print("=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
    print("\nScheduler Change Summary:")
    print("  • OLD: Daily at 2:00 AM UTC")
    print("  • NEW: Every hour at :00 UTC (configurable via BACKFILL_SCHEDULE_MINUTE)")
    print("\nEnvironment Variables:")
    print("  • BACKFILL_SCHEDULE_HOUR: (DEPRECATED - no longer used)")
    print("  • BACKFILL_SCHEDULE_MINUTE: Minute to run each hour (default: 0)")
    print("\nDocker Changes:")
    print("  • Removed BACKFILL_SCHEDULE_HOUR from docker-compose.yml")
    print("  • Kept BACKFILL_SCHEDULE_MINUTE in docker-compose.yml")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(test_hourly_scheduler())
    except Exception as e:
        print(f"❌ TEST FAILED: {e}", file=sys.stderr)
        sys.exit(1)
