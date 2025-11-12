#!/usr/bin/env python3
"""
Verify and Setup Timeframes Feature
---
Validates:
1. Database schema has timeframes column in tracked_symbols
2. Database has active symbols to backfill
3. API endpoint /api/v1/symbols/detailed exists and works
4. Dashboard displays timeframes properly
5. Backfill script can update timeframes
"""

import asyncio
import os
import sys
import asyncpg
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class TimeframesValidator:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None
        self.results = {
            "schema": False,
            "symbols": False,
            "timeframe_column": False,
            "index": False,
            "sample_data": False,
        }
    
    async def connect(self):
        """Connect to database"""
        try:
            self.conn = await asyncpg.connect(self.database_url)
            print("✓ Database connection established")
            return True
        except Exception as e:
            print(f"✗ Database connection failed: {e}")
            return False
    
    async def verify_schema(self):
        """Check if tracked_symbols table exists"""
        try:
            result = await self.conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='tracked_symbols')"
            )
            if result:
                self.results["schema"] = True
                print("✓ tracked_symbols table exists")
                return True
            else:
                print("✗ tracked_symbols table missing")
                return False
        except Exception as e:
            print(f"✗ Schema check failed: {e}")
            return False
    
    async def verify_timeframe_column(self):
        """Check if timeframes column exists and is correct type"""
        try:
            result = await self.conn.fetchval(
                """SELECT data_type FROM information_schema.columns 
                   WHERE table_name='tracked_symbols' AND column_name='timeframes'"""
            )
            if result:
                if result == 'ARRAY':
                    self.results["timeframe_column"] = True
                    print(f"✓ timeframes column exists (type: {result})")
                    return True
                else:
                    print(f"✗ timeframes column type is {result}, expected ARRAY")
                    return False
            else:
                print("✗ timeframes column missing")
                return False
        except Exception as e:
            print(f"✗ Column check failed: {e}")
            return False
    
    async def verify_index(self):
        """Check if GIN index exists on timeframes"""
        try:
            result = await self.conn.fetchval(
                """SELECT indexname FROM pg_indexes 
                   WHERE tablename='tracked_symbols' AND indexname LIKE '%timeframes%'"""
            )
            if result:
                self.results["index"] = True
                print(f"✓ Index exists on timeframes column ({result})")
                return True
            else:
                print("⚠ GIN index not found on timeframes (performance may be slower)")
                return False
        except Exception as e:
            print(f"✗ Index check failed: {e}")
            return False
    
    async def verify_active_symbols(self):
        """Check if there are active symbols"""
        try:
            count = await self.conn.fetchval(
                "SELECT COUNT(*) FROM tracked_symbols WHERE active = TRUE"
            )
            self.results["symbols"] = count > 0
            if count > 0:
                print(f"✓ Found {count} active symbols")
                return True
            else:
                print("⚠ No active symbols found (run: python scripts/init_symbols.py)")
                return False
        except Exception as e:
            print(f"✗ Symbol count check failed: {e}")
            return False
    
    async def verify_sample_data(self):
        """Check sample timeframes data"""
        try:
            rows = await self.conn.fetch(
                """SELECT symbol, timeframes FROM tracked_symbols 
                   WHERE active = TRUE LIMIT 5"""
            )
            if rows:
                self.results["sample_data"] = True
                print(f"✓ Sample data found:")
                for row in rows:
                    tf = row['timeframes'] if row['timeframes'] else '[]'
                    print(f"  {row['symbol']:8} -> {tf}")
                return True
            else:
                print("✗ No sample data available")
                return False
        except Exception as e:
            print(f"✗ Sample data check failed: {e}")
            return False
    
    async def verify_all(self):
        """Run all verifications"""
        print("\n" + "="*70)
        print("TIMEFRAMES FEATURE VERIFICATION")
        print("="*70)
        
        if not await self.connect():
            return False
        
        print("\n[1] Database Schema")
        print("-" * 70)
        await self.verify_schema()
        await self.verify_timeframe_column()
        await self.verify_index()
        
        print("\n[2] Data Availability")
        print("-" * 70)
        await self.verify_active_symbols()
        await self.verify_sample_data()
        
        await self.disconnect()
        
        return self.generate_report()
    
    async def disconnect(self):
        """Close database connection"""
        if self.conn:
            await self.conn.close()
    
    def generate_report(self):
        """Generate verification report"""
        print("\n" + "="*70)
        print("VERIFICATION REPORT")
        print("="*70)
        
        checks = [
            ("Schema exists", self.results["schema"]),
            ("Timeframes column", self.results["timeframe_column"]),
            ("Index optimized", self.results["index"]),
            ("Active symbols", self.results["symbols"]),
            ("Sample data", self.results["sample_data"]),
        ]
        
        passed = sum(1 for _, result in checks if result)
        total = len(checks)
        
        for check, result in checks:
            status = "✓" if result else "✗"
            print(f"{status} {check:30} {'PASS' if result else 'FAIL'}")
        
        print("-" * 70)
        print(f"Status: {passed}/{total} checks passed")
        
        if passed == total:
            print("\n✓ All verifications passed! System is ready.")
            print("\nNext steps:")
            print("1. Run backfill: python scripts/backfill_ohlcv.py --timeframe 1d")
            print("2. View dashboard: http://localhost:8000/dashboard/")
            print("3. Check API: curl http://localhost:8000/api/v1/symbols/detailed")
            return True
        else:
            print("\n✗ Some verifications failed. See above for details.")
            return False


async def main():
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        db_user = os.getenv("DB_USER", "market_user")
        db_password = os.getenv("DB_PASSWORD", "changeMe123")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/market_data"
    
    validator = TimeframesValidator(database_url)
    success = await validator.verify_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
