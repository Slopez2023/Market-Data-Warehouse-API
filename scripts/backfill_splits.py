#!/usr/bin/env python3
"""
Backfill historical stock splits for all symbols with resumable progress tracking.

Usage:
    python scripts/backfill_splits.py [--symbol AAPL] [--resume]

Features:
    - Fetches stock splits from Polygon API
    - Validates split data
    - Tracks backfill progress in database for resumability
    - Respects API rate limits (50 req/min)
    - Supports starting from last checkpoint
"""

import asyncio
import logging
import os
import sys
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from src.clients.polygon_client import PolygonClient
from src.services.database_service import DatabaseService
from src.services.dividend_split_service import DividendSplitService
from src.services.validation_service import ValidationService
from src.config import get_db_url, get_polygon_api_key

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Backfill settings
START_DATE = (datetime.utcnow() - timedelta(days=365*10)).date()  # 10 years
END_DATE = datetime.utcnow().date()
RATE_LIMIT_DELAY = 1.2  # seconds between requests (50 req/min)


async def fetch_splits_for_symbol(
    symbol: str,
    polygon_client: PolygonClient,
    start_date: datetime.date,
    end_date: datetime.date,
    validation_service: ValidationService
) -> tuple[list, int]:
    """
    Fetch and validate stock splits for a symbol.
    
    Returns:
        (validated_splits, skipped_count)
    """
    try:
        logger.info(f"Fetching stock splits for {symbol} ({start_date} to {end_date})")
        
        # Fetch from Polygon
        results = await polygon_client.fetch_stock_splits(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        logger.info(f"  Fetched {len(results)} split records for {symbol}")
        
        # Validate each split
        validated = []
        skipped = 0
        
        for split in results:
            is_valid, metadata = validation_service.validate_split(symbol, split)
            
            if is_valid:
                validated.append(split)
            else:
                logger.warning(
                    f"  {symbol}: Skipping invalid split - {metadata['validation_errors']}"
                )
                skipped += 1
        
        logger.info(f"  Validated {len(validated)}/{len(results)} splits for {symbol}")
        return validated, skipped
    
    except Exception as e:
        logger.error(f"  Error fetching splits for {symbol}: {e}")
        return [], 0


async def backfill_splits(
    symbols: list = None,
    resume: bool = False,
    symbol_override: str = None
) -> None:
    """
    Main backfill function.
    
    Args:
        symbols: List of symbols to backfill (if None, fetch from DB)
        resume: If True, skip already completed symbols
        symbol_override: Backfill only this symbol
    """
    db_url = get_db_url()
    api_key = get_polygon_api_key()
    
    if not api_key:
        logger.error("POLYGON_API_KEY not set")
        return
    
    polygon_client = PolygonClient(api_key)
    db_service = DatabaseService(db_url)
    div_service = DividendSplitService(db_service)
    validation_service = ValidationService()
    
    # Get symbols list
    if symbol_override:
        symbols = [symbol_override]
        logger.info(f"Backfilling single symbol: {symbol_override}")
    elif not symbols:
        try:
            # Get active stock symbols from database
            all_symbols = db_service.get_active_symbols(asset_class='stock')
            symbols = [s['symbol'] for s in all_symbols]
            logger.info(f"Found {len(symbols)} active stock symbols")
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            return
    
    if not symbols:
        logger.warning("No symbols to backfill")
        return
    
    # Filter out completed if resuming
    if resume:
        completed = div_service.get_completed_symbols('splits')
        symbols = [s for s in symbols if s not in completed]
        logger.info(f"Resuming: {len(symbols)} symbols remaining (skipped {len(completed)} completed)")
    
    logger.info("=" * 60)
    logger.info(f"Starting stock split backfill for {len(symbols)} symbols")
    logger.info(f"Date range: {START_DATE} to {END_DATE}")
    logger.info("=" * 60)
    
    total_inserted = 0
    total_skipped = 0
    total_validation_errors = 0
    
    for idx, symbol in enumerate(symbols, 1):
        # Check if already completed
        progress = div_service.get_backfill_progress('splits', symbol)
        if progress and progress['status'] == 'completed':
            logger.info(f"[{idx}/{len(symbols)}] {symbol}: Already completed, skipping")
            continue
        
        # Mark as in progress
        div_service.update_backfill_progress('splits', symbol, 'in_progress')
        
        try:
            # Fetch and validate
            validated, skipped = await fetch_splits_for_symbol(
                symbol,
                polygon_client,
                START_DATE,
                END_DATE,
                validation_service
            )
            
            if not validated:
                # Mark as completed even if no data
                div_service.update_backfill_progress('splits', symbol, 'completed')
                logger.info(f"[{idx}/{len(symbols)}] {symbol}: No split data")
                continue
            
            # Insert into database
            inserted, db_skipped = div_service.insert_splits_batch(symbol, validated)
            
            total_inserted += inserted
            total_skipped += skipped + db_skipped
            total_validation_errors += skipped
            
            # Mark as completed
            div_service.update_backfill_progress('splits', symbol, 'completed')
            logger.info(
                f"[{idx}/{len(symbols)}] {symbol}: ✓ Inserted {inserted}, "
                f"skipped {db_skipped} (validation errors: {skipped})"
            )
        
        except Exception as e:
            logger.error(f"[{idx}/{len(symbols)}] {symbol}: ✗ Error - {e}")
            div_service.update_backfill_progress(
                'splits',
                symbol,
                'failed',
                error_message=str(e)
            )
            total_skipped += 1
        
        # Respect rate limits
        await asyncio.sleep(RATE_LIMIT_DELAY)
    
    logger.info("=" * 60)
    logger.info("Stock split backfill complete!")
    logger.info(f"Total inserted: {total_inserted}")
    logger.info(f"Total skipped: {total_skipped}")
    logger.info(f"Validation errors: {total_validation_errors}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Backfill historical stock splits from Polygon API"
    )
    parser.add_argument(
        '--symbol',
        type=str,
        help='Backfill only this symbol (e.g., AAPL)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last checkpoint (skip completed symbols)'
    )
    
    args = parser.parse_args()
    
    # Run async backfill
    asyncio.run(backfill_splits(
        symbols=None,
        resume=args.resume,
        symbol_override=args.symbol
    ))


if __name__ == "__main__":
    main()
