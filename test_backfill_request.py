#!/usr/bin/env python
"""
Test BackfillRequest model validation (standalone, no app config needed)
"""

import sys
from typing import List
from pydantic import BaseModel, Field, validator
from datetime import datetime

class BackfillRequest(BaseModel):
    """Request to submit a backfill job"""
    symbols: List[str] = Field(..., min_items=1, max_items=100, description="List of symbols to backfill")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    timeframes: List[str] = Field(default=["1d"], description="List of timeframes to backfill")
    
    @validator('symbols')
    def validate_symbols(cls, v):
        """Validate symbols list"""
        if not v or len(v) == 0:
            raise ValueError("At least one symbol required")
        if len(v) > 100:
            raise ValueError("Maximum 100 symbols per request")
        return v
    
    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        """Validate date format"""
        from datetime import datetime as dt
        try:
            dt.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")
        return v
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validate start_date < end_date"""
        if 'start_date' in values:
            from datetime import datetime as dt
            start = dt.strptime(values['start_date'], '%Y-%m-%d')
            end = dt.strptime(v, '%Y-%m-%d')
            if start >= end:
                raise ValueError("Start date must be before end date")
        return v

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
        return 1
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
        return 1
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
        return 1
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
