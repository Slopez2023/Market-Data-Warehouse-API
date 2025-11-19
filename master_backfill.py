#!/usr/bin/env python3
"""
Master Backfill Orchestrator

Orchestrates complete OHLCV backfill with gap detection and retry logic.

Flow:
1. Load tracked symbols + configured timeframes
2. Backfill OHLCV data (3 concurrent symbols, respects rate limits)
3. Detect gaps (missing candles in date range)
4. Retry failed gaps with exponential backoff
5. Report completeness matrix

Usage:
    python master_backfill.py                    # All active symbols, all timeframes
    python master_backfill.py --symbols AAPL,BTC # Specific symbols
    python master_backfill.py --timeframes 1h,1d # Specific timeframes only
    python master_backfill.py --days 30          # 30 days history (default: 365)
"""

import asyncio
import subprocess
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
from pathlib import Path
import json
import asyncpg
import holidays

from dotenv import load_dotenv
from src.clients.multi_source_client import MultiSourceClient
from src.services.validation_service import ValidationService

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MasterBackfiller:
    """
    Orchestrates multi-timeframe OHLCV backfill with gap detection.
    """

    def __init__(
        self,
        database_url: str,
        polygon_api_key: str,
        max_concurrent_symbols: int = 3,
        days_history: int = 365,
        market_type: str = "US"
    ):
        """
        Initialize backfiller.

        Args:
            database_url: PostgreSQL connection string
            polygon_api_key: Polygon.io API key
            max_concurrent_symbols: Max concurrent symbols to process
            days_history: Days of historical data to fetch
            market_type: Market type for holidays (US, CRYPTO, etc.)
        """
        self.database_url = database_url
        self.polygon_api_key = polygon_api_key
        self.max_concurrent_symbols = max_concurrent_symbols
        self.days_history = days_history
        self.market_type = market_type
        
        # Initialize multi-source client with fallback
        self.data_client = MultiSourceClient(
            polygon_api_key=polygon_api_key,
            validation_service=ValidationService(),
            enable_fallback=True,
            fallback_threshold=0.85
        )
        
        # Load market holidays (US stock market)
        self.market_holidays = holidays.US() if market_type == "US" else None

        # Tracking
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbols_processed": {},
            "gaps_detected": {},
            "retry_results": {},
            "summary": {
                "total_symbols": 0,
                "successful": 0,
                "partial_failures": 0,
                "total_failures": 0,
                "total_candles_inserted": 0,
                "total_gaps_detected": 0,
                "total_gaps_retried": 0,
                "total_gaps_filled": 0,
            }
        }

    async def run(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None
    ) -> Dict:
        """
        Run complete backfill pipeline.

        Args:
            symbols: Specific symbols to backfill (None = all active)
            timeframes: Specific timeframes to backfill (None = all configured)

        Returns:
            Results dictionary
        """
        start_time = datetime.utcnow()
        logger.info("=" * 80)
        logger.info("MASTER BACKFILL ORCHESTRATOR STARTED")
        logger.info("=" * 80)

        try:
            # Load symbols and timeframes
            tracked_data = await self._load_tracked_symbols(symbols, timeframes)
            if not tracked_data:
                logger.error("No symbols to backfill")
                return self.results

            self.results["summary"]["total_symbols"] = len(tracked_data)
            logger.info(f"Loaded {len(tracked_data)} symbols")

            # Stage 1: Backfill OHLCV data
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 1: BACKFILLING OHLCV DATA")
            logger.info("=" * 80)
            await self._stage_1_backfill_ohlcv(tracked_data)

            # Stage 2: Detect gaps
            logger.info("\n" + "=" * 80)
            logger.info("STAGE 2: DETECTING GAPS")
            logger.info("=" * 80)
            await self._stage_2_detect_gaps(tracked_data)

            # Stage 3: Retry failed gaps
            if self.results["gaps_detected"]:
                logger.info("\n" + "=" * 80)
                logger.info("STAGE 3: RETRYING FAILED GAPS")
                logger.info("=" * 80)
                await self._stage_3_retry_gaps(tracked_data)

            # Print completeness matrix
            logger.info("\n" + "=" * 80)
            logger.info("DATA COMPLETENESS MATRIX")
            logger.info("=" * 80)
            self._print_completeness_matrix(tracked_data)

            # Final summary
            duration = (datetime.utcnow() - start_time).total_seconds()
            self._print_summary(duration)

            return self.results

        except Exception as e:
            logger.error(f"Backfill pipeline failed: {e}", exc_info=True)
            return self.results
        finally:
            # Save results to file
            await self._save_results()

    async def _load_tracked_symbols(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None
    ) -> List[Tuple[str, str, List[str]]]:
        """
        Load tracked symbols from database.

        Returns:
            List of (symbol, asset_class, timeframes) tuples
        """
        try:
            conn = await asyncpg.connect(self.database_url)

            query = "SELECT symbol, asset_class, timeframes FROM tracked_symbols WHERE active = TRUE"
            rows = await conn.fetch(query)
            await conn.close()

            result = []
            for row in rows:
                sym = row['symbol']

                # Filter by requested symbols if provided
                if symbols and sym not in symbols:
                    continue

                # Get timeframes (use provided or default to all configured)
                symbol_timeframes = list(row['timeframes']) if row['timeframes'] else ['1d']
                if timeframes:
                    symbol_timeframes = [tf for tf in symbol_timeframes if tf in timeframes]

                if symbol_timeframes:
                    result.append((sym, row['asset_class'], symbol_timeframes))

            return sorted(result)

        except Exception as e:
            logger.error(f"Failed to load symbols: {e}")
            return []

    async def _stage_1_backfill_ohlcv(self, tracked_data: List[Tuple]) -> None:
        """
        Stage 1: Backfill OHLCV data using backfill_ohlcv.py script.
        """
        # Process symbols in groups of max_concurrent
        for i in range(0, len(tracked_data), self.max_concurrent_symbols):
            group = tracked_data[i : i + self.max_concurrent_symbols]
            logger.info(f"\nProcessing symbol group {i // self.max_concurrent_symbols + 1}")

            tasks = []
            for symbol, asset_class, timeframes in group:
                task = self._backfill_symbol_ohlcv(symbol, asset_class, timeframes)
                tasks.append(task)

            # Run concurrent backfills
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for (symbol, _, _), result in zip(group, results):
                if isinstance(result, Exception):
                    logger.error(f"{symbol}: {result}")
                    self.results["symbols_processed"][symbol] = {
                        "status": "failed",
                        "error": str(result)
                    }
                else:
                    self.results["symbols_processed"][symbol] = result

            # Pause between groups to manage rate limits
            if i + self.max_concurrent_symbols < len(tracked_data):
                logger.info("Pausing 15s between groups for rate limiting...")
                await asyncio.sleep(15)

    async def _backfill_symbol_ohlcv(
        self,
        symbol: str,
        asset_class: str,
        timeframes: List[str]
    ) -> Dict:
        """
        Backfill OHLCV for single symbol across all timeframes.
        """
        result = {
            "symbol": symbol,
            "asset_class": asset_class,
            "timeframes": {},
            "status": "completed",
            "total_inserted": 0,
            "errors": []
        }

        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=self.days_history)

        for timeframe in timeframes:
            try:
                logger.info(f"  {symbol}/{timeframe}: backfilling...")

                # Call backfill_ohlcv.py as subprocess
                cmd = [
                    sys.executable,
                    "scripts/backfill_ohlcv.py",
                    "--symbols", symbol,
                    "--timeframe", timeframe,
                    "--start", start_date.isoformat(),
                    "--end", end_date.isoformat()
                ]

                # Set PYTHONPATH to include app root
                env = os.environ.copy()
                env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=os.path.dirname(os.path.abspath(__file__)),
                    env=env
                )

                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    logger.warning(f"  {symbol}/{timeframe}: failed - {error_msg[:100]}")
                    result["timeframes"][timeframe] = {
                        "status": "failed",
                        "error": error_msg[:200]
                    }
                    result["errors"].append(timeframe)
                else:
                    # Parse output to get inserted count (logging goes to stderr)
                    output = stderr.decode() if stderr else stdout.decode()
                    inserted = self._parse_backfill_output(output)
                    result["timeframes"][timeframe] = {
                        "status": "completed",
                        "inserted": inserted
                    }
                    result["total_inserted"] += inserted
                    logger.info(f"  {symbol}/{timeframe}: ✓ inserted {inserted}")

            except Exception as e:
                logger.error(f"  {symbol}/{timeframe}: {e}")
                result["timeframes"][timeframe] = {
                    "status": "failed",
                    "error": str(e)
                }
                result["errors"].append(timeframe)

        if result["errors"]:
            result["status"] = "partial_failure"
            self.results["summary"]["partial_failures"] += 1
        else:
            self.results["summary"]["successful"] += 1

        self.results["summary"]["total_candles_inserted"] += result["total_inserted"]
        return result

    async def _stage_2_detect_gaps(self, tracked_data: List[Tuple]) -> None:
        """
        Stage 2: Detect missing candles (gaps) in database.
        """
        try:
            conn = await asyncpg.connect(self.database_url)

            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=self.days_history)

            for symbol, asset_class, timeframes in tracked_data:
                symbol_gaps = {}

                for timeframe in timeframes:
                    # Query for gaps
                    gaps = await self._find_gaps_in_timeframe(
                        conn, symbol, timeframe, start_date, end_date
                    )

                    if gaps:
                        symbol_gaps[timeframe] = gaps
                        self.results["summary"]["total_gaps_detected"] += len(gaps)
                        logger.info(
                            f"{symbol}/{timeframe}: {len(gaps)} gap(s) detected"
                        )

                if symbol_gaps:
                    self.results["gaps_detected"][symbol] = symbol_gaps

            await conn.close()

        except Exception as e:
            logger.error(f"Gap detection failed: {e}")

    async def _find_gaps_in_timeframe(
        self,
        conn,
        symbol: str,
        timeframe: str,
        start_date,
        end_date
    ) -> List[Dict]:
        """
        Find date ranges with missing data for a symbol/timeframe.

        Returns:
            List of {"start": date, "end": date, "days": N} gaps
        """
        # Get expected dates (trading days for stocks, all days for crypto)
        expected_dates = self._get_expected_dates(start_date, end_date)

        # Get actual dates in database
        query = """
            SELECT DATE(time) as date
            FROM market_data
            WHERE symbol = $1 AND timeframe = $2 AND time >= $3 AND time <= $4
            GROUP BY DATE(time)
            ORDER BY date
        """
        rows = await conn.fetch(
            query,
            symbol,
            timeframe,
            start_date,
            end_date
        )

        actual_dates = {row['date'] for row in rows}

        # Find gaps
        gaps = []
        gap_start = None

        for expected_date in expected_dates:
            if expected_date not in actual_dates:
                if gap_start is None:
                    gap_start = expected_date
            else:
                if gap_start is not None:
                    gaps.append({
                        "start": gap_start.isoformat(),
                        "end": expected_date.isoformat(),
                        "days": (expected_date - gap_start).days
                    })
                    gap_start = None

        # Handle trailing gap
        if gap_start is not None:
            gaps.append({
                "start": gap_start.isoformat(),
                "end": expected_dates[-1].isoformat(),
                "days": (expected_dates[-1] - gap_start).days
            })

        return gaps

    def _get_expected_dates(self, start_date, end_date) -> List:
        """Get list of expected trading dates (weekdays excluding market holidays)"""
        dates = []
        current = start_date
        while current <= end_date:
            # Check if weekday (Monday=0, Friday=4)
            if current.weekday() < 5:
                # For US market, also exclude holidays
                if self.market_type == "US" and self.market_holidays and current in self.market_holidays:
                    logger.debug(f"Skipping {current}: {self.market_holidays.get(current)} (market closed)")
                    current += timedelta(days=1)
                    continue
                dates.append(current)
            current += timedelta(days=1)
        return dates

    async def _stage_3_retry_gaps(self, tracked_data: List[Tuple]) -> None:
        """
        Stage 3: Retry failed gaps with exponential backoff.
        """
        for symbol, asset_class, timeframes in tracked_data:
            if symbol not in self.results["gaps_detected"]:
                continue

            symbol_gaps = self.results["gaps_detected"][symbol]
            symbol_retries = {"status": "completed", "total_gaps_filled": 0}

            for timeframe, gaps in symbol_gaps.items():
                timeframe_retries = {"attempted": 0, "filled": 0}

                for gap in gaps:
                    timeframe_retries["attempted"] += 1

                    # Retry up to 2 times
                    for attempt in range(1, 3):
                        try:
                            logger.info(
                                f"  {symbol}/{timeframe}: "
                                f"retrying gap {gap['start']} to {gap['end']} "
                                f"(attempt {attempt}/2)..."
                            )

                            cmd = [
                                sys.executable,
                                "scripts/backfill_ohlcv.py",
                                "--symbols", symbol,
                                "--timeframe", timeframe,
                                "--start", gap['start'],
                                "--end", gap['end']
                            ]

                            # Set PYTHONPATH to include app root
                            env = os.environ.copy()
                            env['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))

                            process = await asyncio.create_subprocess_exec(
                                *cmd,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                                cwd=os.path.dirname(os.path.abspath(__file__)),
                                env=env
                            )

                            stdout, stderr = await process.communicate()

                            if process.returncode == 0:
                                # Parse from stderr where logging output goes
                                output = stderr.decode() if stderr else stdout.decode()
                                inserted = self._parse_backfill_output(output)
                                if inserted > 0:
                                    logger.info(
                                        f"  {symbol}/{timeframe}: ✓ gap filled "
                                        f"({inserted} candles)"
                                    )
                                    timeframe_retries["filled"] += 1
                                    break
                            else:
                                logger.warning(
                                    f"  {symbol}/{timeframe}: retry attempt {attempt} failed"
                                )

                            # Exponential backoff
                            await asyncio.sleep(2 ** attempt)

                        except Exception as e:
                            logger.warning(f"  Retry failed: {e}")

                symbol_retries[timeframe] = timeframe_retries
                symbol_retries["total_gaps_filled"] += timeframe_retries["filled"]

            self.results["retry_results"][symbol] = symbol_retries
            self.results["summary"]["total_gaps_retried"] += sum(
                symbol_retries[tf]["attempted"] for tf in symbol_gaps.keys()
            )
            self.results["summary"]["total_gaps_filled"] += symbol_retries[
                "total_gaps_filled"
            ]

    def _parse_backfill_output(self, output: str) -> int:
        """Extract inserted count from backfill_ohlcv.py output"""
        try:
            for line in output.split('\n'):
                # Look for patterns like "✓ Successfully backfilled 5 records for AAPL"
                if "Successfully backfilled" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if i > 0 and "backfilled" in parts[i-1]:
                            try:
                                return int(part)
                            except ValueError:
                                pass
            return 0
        except Exception:
            return 0

    def _print_completeness_matrix(self, tracked_data: List[Tuple]) -> None:
        """Print data completeness matrix"""
        timeframe_order = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']

        # Header
        header = f"{'Symbol':<10}"
        for tf in timeframe_order:
            header += f"  {tf:<4}"
        logger.info(header)
        logger.info("-" * (10 + (6 * len(timeframe_order))))

        # Rows
        for symbol, _, configured_timeframes in tracked_data:
            row = f"{symbol:<10}"
            for tf in timeframe_order:
                if tf not in configured_timeframes:
                    status = "  -  "
                elif symbol in self.results["gaps_detected"] and tf in self.results["gaps_detected"][symbol]:
                    status = "  ✗  "
                else:
                    status = "  ✓  "
                row += status
            logger.info(row)

    def _print_summary(self, duration: float) -> None:
        """Print final summary"""
        summary = self.results["summary"]
        logger.info("=" * 80)
        logger.info("BACKFILL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration:.1f}s")
        logger.info(f"Symbols Processed: {summary['total_symbols']}")
        logger.info(f"  Successful: {summary['successful']}")
        logger.info(f"  Partial Failures: {summary['partial_failures']}")
        logger.info(f"  Total Failures: {summary['total_failures']}")
        logger.info(f"Total Candles Inserted: {summary['total_candles_inserted']:,}")
        logger.info(f"Gaps Detected: {summary['total_gaps_detected']}")
        logger.info(f"Gaps Retried: {summary['total_gaps_retried']}")
        logger.info(f"Gaps Filled: {summary['total_gaps_filled']}")
        logger.info("=" * 80)

    async def _save_results(self) -> None:
        """Save results to JSON file"""
        try:
            results_file = "/tmp/master_backfill_results.json"
            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            logger.info(f"Results saved to {results_file}")
        except Exception as e:
            logger.warning(f"Failed to save results: {e}")


def _parse_args():
    """Parse command line arguments"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Master backfill orchestrator with gap detection"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbols (e.g., AAPL,BTC,SPY). Default: all active"
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        default=None,
        help="Comma-separated timeframes (e.g., 1m,1h,1d). Default: all configured"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Days of history to backfill (default: 365)"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=3,
        help="Max concurrent symbols (default: 3)"
    )

    return parser.parse_args()


async def main():
    """Main entry point"""
    args = _parse_args()

    database_url = os.getenv("DATABASE_URL")
    polygon_api_key = os.getenv("POLYGON_API_KEY")

    if not database_url or not polygon_api_key:
        logger.error("DATABASE_URL and POLYGON_API_KEY environment variables required")
        sys.exit(1)

    # Parse symbols and timeframes
    symbols = (
        [s.strip().upper() for s in args.symbols.split(",")]
        if args.symbols
        else None
    )
    timeframes = (
        [t.strip() for t in args.timeframes.split(",")]
        if args.timeframes
        else None
    )

    backfiller = MasterBackfiller(
        database_url=database_url,
        polygon_api_key=polygon_api_key,
        max_concurrent_symbols=args.max_concurrent,
        days_history=args.days
    )

    await backfiller.run(symbols=symbols, timeframes=timeframes)


if __name__ == "__main__":
    asyncio.run(main())
