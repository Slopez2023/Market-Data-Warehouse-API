#!/usr/bin/env python3
"""
Verification script for timeframe data consistency.

Checks:
1. No NULL values in timeframe column
2. All timeframes are valid (from ALLOWED_TIMEFRAMES)
3. No duplicate (symbol, timeframe, time) tuples
4. Sample data from each timeframe
5. Distribution of records by timeframe
"""

import asyncio
import os
import sys
from typing import Dict, List
import asyncpg

from src.config import ALLOWED_TIMEFRAMES


async def verify_timeframe_data(database_url: str) -> Dict[str, any]:
    """
    Verify timeframe data consistency in market_data table.
    
    Returns:
        Dictionary with verification results
    """
    results = {
        "timestamp": str(asyncio.get_event_loop().time()),
        "checks": {},
        "errors": [],
        "warnings": []
    }
    
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check 1: No NULL values in timeframe column
        print("✓ Check 1: Verifying no NULL timeframes...")
        null_count = await conn.fetchval(
            "SELECT COUNT(*) FROM market_data WHERE timeframe IS NULL"
        )
        results["checks"]["null_timeframes"] = {
            "status": "PASS" if null_count == 0 else "FAIL",
            "count": null_count
        }
        if null_count > 0:
            results["errors"].append(f"Found {null_count} records with NULL timeframe")
        
        # Check 2: No empty string timeframes
        print("✓ Check 2: Verifying no empty timeframes...")
        empty_count = await conn.fetchval(
            "SELECT COUNT(*) FROM market_data WHERE timeframe = ''"
        )
        results["checks"]["empty_timeframes"] = {
            "status": "PASS" if empty_count == 0 else "FAIL",
            "count": empty_count
        }
        if empty_count > 0:
            results["errors"].append(f"Found {empty_count} records with empty timeframe")
        
        # Check 3: All timeframes are valid
        print("✓ Check 3: Verifying all timeframes are valid...")
        invalid_timeframes = await conn.fetch(
            f"""
            SELECT DISTINCT timeframe FROM market_data 
            WHERE timeframe NOT IN ({','.join(f"'{tf}'" for tf in ALLOWED_TIMEFRAMES)})
            """
        )
        
        if invalid_timeframes:
            invalid_list = [row['timeframe'] for row in invalid_timeframes]
            results["checks"]["invalid_timeframes"] = {
                "status": "FAIL",
                "invalid": invalid_list
            }
            results["errors"].append(f"Found invalid timeframes: {invalid_list}")
        else:
            results["checks"]["invalid_timeframes"] = {
                "status": "PASS",
                "invalid": []
            }
        
        # Check 4: No duplicate (symbol, timeframe, time) tuples
        print("✓ Check 4: Verifying no duplicate (symbol, timeframe, time) tuples...")
        duplicates = await conn.fetch(
            """
            SELECT symbol, timeframe, time, COUNT(*) as count
            FROM market_data
            GROUP BY symbol, timeframe, time
            HAVING COUNT(*) > 1
            LIMIT 10
            """
        )
        
        if duplicates:
            results["checks"]["duplicate_candles"] = {
                "status": "FAIL",
                "count": len(duplicates),
                "samples": [
                    {
                        "symbol": row['symbol'],
                        "timeframe": row['timeframe'],
                        "time": str(row['time']),
                        "duplicates": row['count']
                    }
                    for row in duplicates
                ]
            }
            results["warnings"].append(f"Found {len(duplicates)} duplicate (symbol, timeframe, time) tuples")
        else:
            results["checks"]["duplicate_candles"] = {
                "status": "PASS",
                "count": 0
            }
        
        # Check 5: Distribution of records by timeframe
        print("✓ Check 5: Getting timeframe distribution...")
        distribution = await conn.fetch(
            """
            SELECT timeframe, COUNT(*) as count, COUNT(DISTINCT symbol) as symbols
            FROM market_data
            GROUP BY timeframe
            ORDER BY timeframe
            """
        )
        
        results["checks"]["timeframe_distribution"] = {
            "status": "PASS",
            "summary": {
                row['timeframe']: {
                    "records": row['count'],
                    "symbols": row['symbols']
                }
                for row in distribution
            }
        }
        
        # Check 6: Sample data from each timeframe
        print("✓ Check 6: Getting sample data from each timeframe...")
        sample_data = await conn.fetch(
            """
            SELECT DISTINCT ON (timeframe, symbol) 
                   symbol, timeframe, time, open, high, low, close, volume
            FROM market_data
            ORDER BY timeframe, symbol, time DESC
            LIMIT 5
            """
        )
        
        results["checks"]["sample_data"] = {
            "status": "PASS",
            "count": len(sample_data),
            "samples": [
                {
                    "symbol": row['symbol'],
                    "timeframe": row['timeframe'],
                    "time": str(row['time']),
                    "ohlc": f"{row['open']}/{row['high']}/{row['low']}/{row['close']}",
                    "volume": row['volume']
                }
                for row in sample_data
            ]
        }
        
        # Check 7: Total record count
        print("✓ Check 7: Getting total record count...")
        total_records = await conn.fetchval("SELECT COUNT(*) FROM market_data")
        results["checks"]["total_records"] = {
            "status": "PASS",
            "count": total_records
        }
        
        await conn.close()
        
        # Summary
        results["summary"] = {
            "total_checks": len(results["checks"]),
            "passed_checks": sum(1 for c in results["checks"].values() if c["status"] == "PASS"),
            "failed_checks": sum(1 for c in results["checks"].values() if c["status"] == "FAIL"),
            "errors": len(results["errors"]),
            "warnings": len(results["warnings"])
        }
        
    except Exception as e:
        results["errors"].append(f"Verification error: {str(e)}")
        results["summary"] = {
            "total_checks": 0,
            "passed_checks": 0,
            "failed_checks": 0,
            "errors": 1,
            "warnings": 0
        }
    
    return results


async def main():
    """Run verification"""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://user:password@localhost:5432/market_data"
    )
    
    print("=" * 60)
    print("Market Data Timeframe Verification Script")
    print("=" * 60)
    print()
    
    results = await verify_timeframe_data(database_url)
    
    # Print results
    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)
    
    for check_name, check_result in results["checks"].items():
        status = check_result["status"]
        status_icon = "✓" if status == "PASS" else "✗"
        print(f"\n{status_icon} {check_name}: {status}")
        
        # Print check details based on type
        if check_name == "null_timeframes" or check_name == "empty_timeframes":
            print(f"  Records: {check_result['count']}")
        elif check_name == "invalid_timeframes":
            if check_result["invalid"]:
                print(f"  Invalid: {check_result['invalid']}")
        elif check_name == "duplicate_candles":
            print(f"  Duplicates: {check_result['count']}")
            for sample in check_result.get("samples", []):
                print(f"    - {sample['symbol']} {sample['timeframe']} @ {sample['time']}: {sample['duplicates']}x")
        elif check_name == "timeframe_distribution":
            for tf, dist in check_result["summary"].items():
                print(f"  {tf}: {dist['records']:>6} records across {dist['symbols']:>3} symbols")
        elif check_name == "sample_data":
            for sample in check_result.get("samples", []):
                print(f"  {sample['symbol']:>6} {sample['timeframe']:>3} {sample['time']:>19} OHLC: {sample['ohlc']:>20} Vol: {sample['volume']}")
        elif check_name == "total_records":
            print(f"  Total: {check_result['count']:,} records")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    summary = results["summary"]
    print(f"Total checks: {summary['total_checks']}")
    print(f"Passed: {summary['passed_checks']}")
    print(f"Failed: {summary['failed_checks']}")
    print(f"Errors: {summary['errors']}")
    print(f"Warnings: {summary['warnings']}")
    
    if results["errors"]:
        print("\n" + "=" * 60)
        print("ERRORS")
        print("=" * 60)
        for error in results["errors"]:
            print(f"✗ {error}")
    
    if results["warnings"]:
        print("\n" + "=" * 60)
        print("WARNINGS")
        print("=" * 60)
        for warning in results["warnings"]:
            print(f"⚠ {warning}")
    
    print("\n" + "=" * 60)
    
    # Exit code based on results
    if results["errors"]:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
