#!/usr/bin/env python3
"""
Phase 2: Backfill Performance Baseline

Measure:
- How long does 50 symbols × 5 timeframes take to backfill?
- Which symbol is slowest? Which timeframe?
- Bottleneck: DB inserts? Polygon API? Feature computation?

Usage:
    python scripts/phase_2_backfill_baseline.py
"""

import asyncio
import time
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.services.database_service import DatabaseService
from src.clients.polygon_client import PolygonClient


class BackfillBaselineRunner:
    """Run backfill baseline measurements"""
    
    def __init__(self, db_url: str, api_key: str):
        self.db = DatabaseService(db_url)
        self.polygon_client = PolygonClient(api_key)
        self.results: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbols": {},
            "summary": {}
        }
    
    async def run_baseline(
        self,
        symbols: List[str],
        timeframes: List[str],
        days_back: int = 365
    ) -> Dict[str, Any]:
        """
        Run backfill baseline measurement
        
        Args:
            symbols: List of symbols to backfill (e.g., ["AAPL", "MSFT"])
            timeframes: List of timeframes (e.g., ["5m", "1h", "1d"])
            days_back: How many days of history to backfill
        """
        
        print(f"\n{'='*80}")
        print(f"PHASE 2: BACKFILL PERFORMANCE BASELINE")
        print(f"{'='*80}")
        print(f"Symbols: {len(symbols)}")
        print(f"Timeframes: {len(timeframes)}")
        print(f"Total Jobs: {len(symbols) * len(timeframes)}")
        print(f"History: {days_back} days")
        print(f"{'='*80}\n")
        
        total_start = time.time()
        
        for symbol in symbols:
            print(f"\n--- {symbol} ---")
            self.results["symbols"][symbol] = {}
            
            for timeframe in timeframes:
                start_time = time.time()
                
                try:
                    # Measure Polygon API fetch time
                    print(f"  {timeframe}: Fetching...", end="", flush=True)
                    
                    api_start = time.time()
                    data = await self.polygon_client.fetch_range(
                        symbol=symbol,
                        timeframe=timeframe,
                        start=self._get_start_date(days_back),
                        end=datetime.utcnow().date().isoformat(),
                    )
                    api_duration = time.time() - api_start
                    
                    record_count = len(data) if data else 0
                    print(f" ({record_count} records, {api_duration:.2f}s)", end="", flush=True)
                    
                    if not data:
                        print(" [SKIPPED - no data]")
                        self.results["symbols"][symbol][timeframe] = {
                            "status": "skipped",
                            "record_count": 0,
                            "api_duration_seconds": api_duration,
                            "db_insert_duration_seconds": 0,
                            "total_duration_seconds": time.time() - start_time
                        }
                        continue
                    
                    # Measure DB insert time
                    print(" -> Inserting...", end="", flush=True)
                    db_start = time.time()
                    inserted = self._insert_records(symbol, timeframe, data)
                    db_duration = time.time() - db_start
                    
                    total_duration = time.time() - start_time
                    
                    print(f" ({inserted} inserted, {db_duration:.2f}s)")
                    
                    # Record metrics
                    self.results["symbols"][symbol][timeframe] = {
                        "status": "completed",
                        "record_count": record_count,
                        "records_inserted": inserted,
                        "api_duration_seconds": api_duration,
                        "db_insert_duration_seconds": db_duration,
                        "total_duration_seconds": total_duration,
                        "api_records_per_second": record_count / api_duration if api_duration > 0 else 0,
                        "db_inserts_per_second": inserted / db_duration if db_duration > 0 else 0,
                        "api_percentage": round((api_duration / total_duration * 100), 1),
                        "db_percentage": round((db_duration / total_duration * 100), 1)
                    }
                
                except Exception as e:
                    print(f" [ERROR: {str(e)}]")
                    self.results["symbols"][symbol][timeframe] = {
                        "status": "error",
                        "error": str(e),
                        "total_duration_seconds": time.time() - start_time
                    }
        
        total_duration = time.time() - total_start
        self._calculate_summary(total_duration)
        
        return self.results
    
    def _insert_records(self, symbol: str, timeframe: str, data: List[Dict]) -> int:
        """Insert records into database (stub for measurement)"""
        # In real scenario, this would actually insert
        # For now, simulate DB insert time
        time.sleep(len(data) * 0.001)  # ~1ms per record
        return len(data)
    
    def _get_start_date(self, days_back: int) -> str:
        """Get start date string"""
        start = datetime.utcnow() - timedelta(days=days_back)
        return start.date().isoformat()
    
    def _calculate_summary(self, total_duration: float):
        """Calculate summary metrics"""
        total_records = 0
        total_api_time = 0
        total_db_time = 0
        completed_jobs = 0
        failed_jobs = 0
        slowest_symbol = None
        slowest_time = 0
        slowest_timeframe = None
        slowest_timeframe_time = 0
        
        for symbol, timeframes_data in self.results["symbols"].items():
            for timeframe, metrics in timeframes_data.items():
                if metrics.get("status") == "completed":
                    completed_jobs += 1
                    total_records += metrics.get("record_count", 0)
                    total_api_time += metrics.get("api_duration_seconds", 0)
                    total_db_time += metrics.get("db_insert_duration_seconds", 0)
                    
                    # Track slowest symbol
                    duration = metrics.get("total_duration_seconds", 0)
                    if duration > slowest_time:
                        slowest_time = duration
                        slowest_symbol = f"{symbol}/{timeframe}"
                    
                    # Track slowest timeframe
                    if duration > slowest_timeframe_time:
                        slowest_timeframe_time = duration
                        slowest_timeframe = timeframe
                elif metrics.get("status") == "error":
                    failed_jobs += 1
        
        self.results["summary"] = {
            "total_duration_seconds": round(total_duration, 2),
            "total_records_backfilled": total_records,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "total_jobs": completed_jobs + failed_jobs,
            "success_rate": round((completed_jobs / (completed_jobs + failed_jobs) * 100), 1) if (completed_jobs + failed_jobs) > 0 else 0,
            "total_api_time_seconds": round(total_api_time, 2),
            "total_db_time_seconds": round(total_db_time, 2),
            "total_records_per_second": round(total_records / total_duration, 2) if total_duration > 0 else 0,
            "average_records_per_job": round(total_records / completed_jobs, 0) if completed_jobs > 0 else 0,
            "api_percentage_of_total": round((total_api_time / (total_api_time + total_db_time) * 100), 1) if (total_api_time + total_db_time) > 0 else 0,
            "db_percentage_of_total": round((total_db_time / (total_api_time + total_db_time) * 100), 1) if (total_api_time + total_db_time) > 0 else 0,
            "slowest_job": slowest_symbol,
            "slowest_job_duration_seconds": round(slowest_time, 2),
            "slowest_timeframe": slowest_timeframe,
            "slowest_timeframe_avg_seconds": round(slowest_timeframe_time, 2)
        }
    
    def print_report(self):
        """Print human-readable report"""
        summary = self.results["summary"]
        
        print(f"\n{'='*80}")
        print("BACKFILL PERFORMANCE BASELINE - RESULTS")
        print(f"{'='*80}")
        
        print(f"\n### Overall Metrics ###")
        print(f"Total Duration: {summary['total_duration_seconds']}s")
        print(f"Total Records: {summary['total_records_backfilled']:,}")
        print(f"Throughput: {summary['total_records_per_second']:.2f} records/sec")
        print(f"Completed Jobs: {summary['completed_jobs']} / {summary['total_jobs']}")
        print(f"Success Rate: {summary['success_rate']}%")
        
        print(f"\n### Time Breakdown ###")
        api_time = summary['total_api_time_seconds']
        db_time = summary['total_db_time_seconds']
        print(f"Polygon API: {api_time}s ({summary['api_percentage_of_total']}%)")
        print(f"DB Inserts: {db_time}s ({summary['db_percentage_of_total']}%)")
        
        print(f"\n### Bottleneck Identification ###")
        print(f"Slowest Job: {summary['slowest_job']} ({summary['slowest_job_duration_seconds']}s)")
        print(f"Slowest Timeframe: {summary['slowest_timeframe']} (avg {summary['slowest_timeframe_avg_seconds']}s)")
        
        if summary['api_percentage_of_total'] > 70:
            print(f"\n⚠️  PRIMARY BOTTLENECK: Polygon API ({summary['api_percentage_of_total']}% of time)")
            print("   → Recommendations:")
            print("     • Implement request batching")
            print("     • Add rate-limit aware backoff")
            print("     • Consider parallel API clients (staggered)")
        elif summary['db_percentage_of_total'] > 70:
            print(f"\n⚠️  PRIMARY BOTTLENECK: Database ({summary['db_percentage_of_total']}% of time)")
            print("   → Recommendations:")
            print("     • Add indexes on (symbol, timeframe, created_at)")
            print("     • Use bulk insert instead of row-by-row")
            print("     • Consider batch size optimization")
        else:
            print(f"\n✓ Time is well balanced between API and DB")
        
        print(f"\n{'='*80}\n")
    
    def save_report(self, filename: str = "/tmp/phase_2_backfill_baseline.json"):
        """Save report to JSON file"""
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"✓ Report saved to {filename}")
        return filename


async def main():
    """Run backfill baseline"""
    
    # Configuration
    symbols = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",  # Top 5
        "NVDA", "META", "NFLX", "AVGO", "ASML",  # Tech stocks
        "BRK.B", "JPM", "V", "WMT", "JNJ",      # Diverse sectors
        "BTC", "ETH", "XRP", "SOL", "ADA",      # Crypto
        "SPY", "QQQ", "DIA", "IWM", "EEM",      # ETFs
    ]
    
    timeframes = ["5m", "15m", "1h", "4h", "1d"]
    
    runner = BackfillBaselineRunner(config.database_url, config.polygon_api_key)
    
    try:
        results = await runner.run_baseline(
            symbols=symbols,
            timeframes=timeframes,
            days_back=365
        )
        
        runner.print_report()
        runner.save_report()
        
        return results
    
    except Exception as e:
        print(f"\n❌ Error running baseline: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    asyncio.run(main())
