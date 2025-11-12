#!/usr/bin/env python3
"""
Backfill V2 - Comprehensive market data orchestrator.

Runs all backfill operations with selective skip options:
- OHLCV candles (multiple timeframes)
- News & sentiment analysis
- Earnings announcements
- Dividends
- Stock splits
- Options IV & chain data
- Adjusted OHLCV

Usage:
    python scripts/backfill_v2.py                    # Full backfill
    python scripts/backfill_v2.py --skip-news        # Skip news
    python scripts/backfill_v2.py --symbols AAPL,MSFT --timeframe 1h
"""

import asyncio
import logging
import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from typing import List
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Scripts directory
SCRIPTS_DIR = Path(__file__).parent

# Default date range (5 years)
END_DATE = datetime.utcnow().date()
START_DATE = END_DATE - timedelta(days=365*5)


def run_command(cmd: List[str], description: str) -> bool:
    """
    Run a backfill subprocess and track completion.
    
    Args:
        cmd: Command list to execute
        description: Human-readable description of the operation
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Starting: {description}")
        result = subprocess.run(cmd, check=True, capture_output=False)
        logger.info(f"✓ Completed: {description}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Failed: {description}")
        logger.error(f"Error: {e}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error in {description}: {e}")
        return False


def build_command(script: str, args: argparse.Namespace, skip_flags: List[str] = None) -> List[str]:
    """
    Build command with arguments.
    
    Args:
        script: Script filename
        args: Parsed command-line arguments
        skip_flags: List of skip flags to exclude
        
    Returns:
        Command list for subprocess
    """
    cmd = ["python", str(SCRIPTS_DIR / script)]
    
    if args.symbols:
        cmd.extend(["--symbols", args.symbols])
    
    if args.start:
        cmd.extend(["--start", args.start])
    
    if args.end:
        cmd.extend(["--end", args.end])
    
    if args.timeframe and script == "backfill_ohlcv.py":
        cmd.extend(["--timeframe", args.timeframe])
    
    if skip_flags:
        for flag in skip_flags:
            cmd.append(flag)
    
    return cmd


def main():
    parser = argparse.ArgumentParser(
        description="Backfill V2 - Comprehensive market data orchestrator"
    )
    
    # Core arguments
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbols (e.g., AAPL,MSFT). If omitted, backfills all active symbols"
    )
    
    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD). Default: ~5 years ago"
    )
    
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD). Default: today (UTC)"
    )
    
    parser.add_argument(
        "--timeframe",
        type=str,
        default="1d",
        choices=["5m", "15m", "30m", "1h", "4h", "1d", "1w"],
        help="OHLCV timeframe (default: 1d)"
    )
    
    # Skip flags
    parser.add_argument(
        "--skip-ohlcv",
        action="store_true",
        help="Skip OHLCV candles backfill"
    )
    
    parser.add_argument(
        "--skip-news",
        action="store_true",
        help="Skip news/sentiment backfill"
    )
    
    parser.add_argument(
        "--skip-earnings",
        action="store_true",
        help="Skip earnings backfill"
    )
    
    parser.add_argument(
        "--skip-dividends",
        action="store_true",
        help="Skip dividend backfill"
    )
    
    parser.add_argument(
        "--skip-splits",
        action="store_true",
        help="Skip stock split backfill"
    )
    
    parser.add_argument(
        "--skip-options",
        action="store_true",
        help="Skip options IV backfill"
    )
    
    parser.add_argument(
        "--skip-adjusted",
        action="store_true",
        help="Skip adjusted OHLCV backfill"
    )
    
    args = parser.parse_args()
    
    # Track results
    results = {}
    start_time = datetime.now()
    
    logger.info("=" * 80)
    logger.info("BACKFILL V2 - COMPREHENSIVE MARKET DATA")
    logger.info("=" * 80)
    
    if args.symbols:
        logger.info(f"Symbols: {args.symbols}")
    else:
        logger.info("Symbols: ALL ACTIVE")
    
    logger.info(f"Date Range: {args.start or START_DATE} to {args.end or END_DATE}")
    logger.info("=" * 80)
    
    # 1. OHLCV Candles
    if not args.skip_ohlcv:
        cmd = build_command("backfill_ohlcv.py", args)
        results["OHLCV"] = run_command(cmd, "OHLCV Candles")
    else:
        logger.info("⊘ Skipping: OHLCV Candles")
        results["OHLCV"] = None
    
    # 2. News & Sentiment
    if not args.skip_news:
        logger.warning("⚠ News/Sentiment backfill not yet available (dependencies pending)")
        logger.info("⊘ Skipping: News & Sentiment")
        results["News"] = None
    else:
        logger.info("⊘ Skipping: News & Sentiment")
        results["News"] = None
    
    # 3. Earnings
    if not args.skip_earnings:
        logger.warning("⚠ Earnings backfill not yet available (dependencies pending)")
        logger.info("⊘ Skipping: Earnings")
        results["Earnings"] = None
    else:
        logger.info("⊘ Skipping: Earnings")
        results["Earnings"] = None
    
    # 4. Dividends
    if not args.skip_dividends:
        logger.warning("⚠ Dividend backfill not yet available (dependencies pending)")
        logger.info("⊘ Skipping: Dividends")
        results["Dividends"] = None
    else:
        logger.info("⊘ Skipping: Dividends")
        results["Dividends"] = None
    
    # 5. Stock Splits
    if not args.skip_splits:
        logger.warning("⚠ Stock Split backfill not yet available (dependencies pending)")
        logger.info("⊘ Skipping: Stock Splits")
        results["Splits"] = None
    else:
        logger.info("⊘ Skipping: Stock Splits")
        results["Splits"] = None
    
    # 6. Options IV
    if not args.skip_options:
        logger.warning("⚠ Options IV backfill not yet available (dependencies pending)")
        logger.info("⊘ Skipping: Options IV")
        results["Options"] = None
    else:
        logger.info("⊘ Skipping: Options IV")
        results["Options"] = None
    
    # 7. Adjusted OHLCV (runs after dividends/splits)
    if not args.skip_adjusted:
        logger.warning("⚠ Adjusted OHLCV backfill not yet available (dependencies pending)")
        logger.info("⊘ Skipping: Adjusted OHLCV")
        results["Adjusted"] = None
    else:
        logger.info("⊘ Skipping: Adjusted OHLCV")
        results["Adjusted"] = None
    
    # Summary
    elapsed = datetime.now() - start_time
    logger.info("=" * 80)
    logger.info("BACKFILL V2 - SUMMARY")
    logger.info("=" * 80)
    
    success_count = sum(1 for v in results.values() if v is True)
    skip_count = sum(1 for v in results.values() if v is None)
    fail_count = sum(1 for v in results.values() if v is False)
    
    for name, result in results.items():
        if result is True:
            logger.info(f"✓ {name:20} - SUCCESS")
        elif result is False:
            logger.info(f"✗ {name:20} - FAILED")
        else:
            logger.info(f"⊘ {name:20} - SKIPPED")
    
    logger.info("=" * 80)
    logger.info(f"Total: {success_count} successful, {fail_count} failed, {skip_count} skipped")
    logger.info(f"Elapsed Time: {elapsed}")
    logger.info("=" * 80)
    
    # Exit with error if any failed
    if fail_count > 0:
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
