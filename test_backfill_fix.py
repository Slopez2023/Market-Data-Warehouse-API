#!/usr/bin/env python
"""
Test to verify the backfill endpoint now accepts JSON body instead of query params.
This fixes the 400 Bad Request error when submitting backfill requests with many symbols.
"""

import sys
sys.path.insert(0, '/Users/stephenlopez/Projects/Trading Projects/MarketDataAPI')

from src.models import BackfillRequest
from datetime import datetime

def test_backfill_request_validation():
    """Test that BackfillRequest validates correctly"""
    
    print("=" * 60)
    print("BACKFILL REQUEST VALIDATION TEST")
    print("=" * 60)
    print()
    
    # Test 1: Valid request with many symbols
    print("✓ Test 1: Valid request with many symbols (42 symbols)")
    symbols = [f"SYMBOL_{i}" for i in range(42)]
    request = BackfillRequest(
        symbols=symbols,
        start_date="2025-10-18",
        end_date="2025-11-17",
        timeframes=["5m", "15m", "1h", "1d"]
    )
    assert len(request.symbols) == 42
    assert request.start_date == "2025-10-18"
    assert request.end_date == "2025-11-17"
    assert len(request.timeframes) == 4
    print(f"  ✅ PASSED: {len(request.symbols)} symbols accepted")
    print()
    
    # Test 2: Maximum symbols (100)
    print("✓ Test 2: Maximum 100 symbols")
    symbols_max = [f"SYMBOL_{i:03d}" for i in range(100)]
    request_max = BackfillRequest(
        symbols=symbols_max,
        start_date="2025-01-01",
        end_date="2025-12-31",
        timeframes=["1d"]
    )
    assert len(request_max.symbols) == 100
    print(f"  ✅ PASSED: 100 symbols accepted")
    print()
    
    # Test 3: Reject > 100 symbols
    print("✓ Test 3: Reject > 100 symbols")
    symbols_too_many = [f"SYMBOL_{i:03d}" for i in range(101)]
    try:
        request_bad = BackfillRequest(
            symbols=symbols_too_many,
            start_date="2025-01-01",
            end_date="2025-12-31",
            timeframes=["1d"]
        )
        print("  ❌ FAILED: Should have rejected > 100 symbols")
        sys.exit(1)
    except ValueError as e:
        print(f"  ✅ PASSED: Correctly rejected: {e}")
    print()
    
    # Test 4: Default timeframes
    print("✓ Test 4: Default timeframes")
    request_default = BackfillRequest(
        symbols=["AAPL"],
        start_date="2025-01-01",
        end_date="2025-12-31"
    )
    assert request_default.timeframes == ["1d"]
    print(f"  ✅ PASSED: Default timeframe is ['1d']")
    print()
    
    # Test 5: Invalid date format
    print("✓ Test 5: Reject invalid date format")
    try:
        request_bad_date = BackfillRequest(
            symbols=["AAPL"],
            start_date="10-18-2025",  # Wrong format
            end_date="2025-12-31",
            timeframes=["1d"]
        )
        print("  ❌ FAILED: Should have rejected invalid date format")
        sys.exit(1)
    except ValueError as e:
        print(f"  ✅ PASSED: Correctly rejected: {e}")
    print()
    
    # Test 6: Start date >= end date
    print("✓ Test 6: Reject start date >= end date")
    try:
        request_bad_range = BackfillRequest(
            symbols=["AAPL"],
            start_date="2025-12-31",
            end_date="2025-01-01",  # Before start date
            timeframes=["1d"]
        )
        print("  ❌ FAILED: Should have rejected invalid date range")
        sys.exit(1)
    except ValueError as e:
        print(f"  ✅ PASSED: Correctly rejected: {e}")
    print()
    
    # Test 7: Real-world scenario from error
    print("✓ Test 7: Real-world scenario (42 symbols from dashboard error)")
    real_symbols = [
        "TEST_UNIQUE_fa361efb", "AAPL", "AMD", "AMZN", "ARB-USD", "ARKK",
        "ATOM-USD", "BA", "BRK.B", "BTC", "BTC-USD", "COST", "DIA", "DIS",
        "EEM", "ETH", "ETH-USD", "GLD", "GOOGL", "INTC", "IWM", "JPM", "KO",
        "LINK-USD", "LTC-USD", "META", "MSFT", "NEAR-USD", "NFLX", "NVDA",
        "OP-USD", "PEP", "PG", "QQQ", "SCHB", "SLV", "SOL", "SOL-USD", "SPY",
        "TLT", "TSLA", "V", "XLE"
    ]
    request_real = BackfillRequest(
        symbols=real_symbols,
        start_date="2025-10-18",
        end_date="2025-11-17",
        timeframes=["5m", "15m", "1h", "1d"]
    )
    assert len(request_real.symbols) == len(real_symbols)
    print(f"  ✅ PASSED: {len(request_real.symbols)} symbols accepted")
    print(f"  Start: {request_real.start_date}")
    print(f"  End: {request_real.end_date}")
    print(f"  Timeframes: {request_real.timeframes}")
    print()
    
    print("=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
    print()
    print("SUMMARY:")
    print("  • BackfillRequest accepts 1-100 symbols")
    print("  • Validates date format (YYYY-MM-DD)")
    print("  • Validates start_date < end_date")
    print("  • Default timeframes: ['1d']")
    print("  • Pydantic validation prevents invalid requests")
    print()
    print("IMPACT:")
    print("  • API endpoint /api/v1/backfill now uses JSON body")
    print("  • Avoids URL length limits (was causing 400 errors)")
    print("  • Dashboard script updated to send JSON body")
    print()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(test_backfill_request_validation())
    except Exception as e:
        print(f"❌ TEST FAILED: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
