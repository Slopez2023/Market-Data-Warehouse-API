#!/usr/bin/env python3
"""
Backfill OHLCV - Historical price and volume data.
Backfills standard candlestick data for all active symbols from tracked_symbols table.
Can be parameterized via CLI flags to filter symbols, set date ranges, and choose timeframe.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
import argparse
from dotenv import load_dotenv
import asyncpg

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clients.polygon_client import PolygonClient
from src.services.validation_service import ValidationService
from src.services.database_service import DatabaseService

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default backfill date range (5 years of data)
END_DATE = datetime.utcnow().date()
START_DATE = END_DATE - timedelta(days=365*5)


async def update_symbol_timeframe(database_url: str, symbol: str, timeframe: str) -> bool:
    """
    Update tracked_symbols to include the backfilled timeframe.
    
    Args:
        database_url: Database connection string
        symbol: Stock ticker
        timeframe: Timeframe that was backfilled (e.g., '1d', '1h')
    
    Returns:
        True if successfully updated, False otherwise
    """
    try:
        conn = await asyncpg.connect(database_url)
        
        # Get current timeframes
        row = await conn.fetchrow(
            "SELECT timeframes FROM tracked_symbols WHERE symbol = $1",
            symbol
        )
        
        if not row:
            await conn.close()
            return False
        
        current_timeframes = list(row['timeframes']) if row['timeframes'] else []
        
        # Add timeframe if not already present
        if timeframe not in current_timeframes:
            current_timeframes.append(timeframe)
            # Sort for consistency
            current_timeframes = sorted(
                current_timeframes,
                key=lambda x: (['5m', '15m', '30m', '1h', '4h', '1d', '1w'].index(x))
            )
            
            await conn.execute(
                "UPDATE tracked_symbols SET timeframes = $1 WHERE symbol = $2",
                current_timeframes,
                symbol
            )
            logger.info(f"Updated {symbol} timeframes to: {current_timeframes}")
        
        await conn.close()
        return True
    
    except Exception as e:
        logger.error(f"Error updating timeframes for {symbol}: {e}")
        return False


async def backfill_symbol(
    symbol: str,
    polygon_client: PolygonClient,
    validation_service: ValidationService,
    db_service: DatabaseService,
    start_date: datetime.date,
    end_date: datetime.date,
    timeframe: str = '1d',
    database_url: str = None
) -> tuple[int, int]:
    """
    Backfill data for a single symbol.
    
    Args:
        symbol: Stock/crypto symbol
        polygon_client: Polygon API client
        validation_service: Validation service
        db_service: Database service
        start_date: Start date for backfill
        end_date: End date for backfill
        timeframe: Timeframe (default '1d'). Supported: 5m, 15m, 30m, 1h, 4h, 1d, 1w
    
    Returns:
        (inserted_count, failed_count)
    """
    try:
        logger.info(f"Backfilling {symbol} ({timeframe}): {start_date} to {end_date}")
        
        # Fetch from Polygon
        candles = await polygon_client.fetch_range(
        symbol,
        timeframe,
        start=start_date.strftime('%Y-%m-%d'),
        end=end_date.strftime('%Y-%m-%d')
        )
        
        if not candles:
            logger.warning(f"No data returned for {symbol}")
            db_service.log_backfill(
                symbol,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                0,
                False,
                "No data returned from Polygon"
            )
            return 0, 1
        
        logger.info(f"Fetched {len(candles)} candles for {symbol}")
        
        # Calculate median volume for anomaly detection
        median_vol = validation_service.calculate_median_volume(candles)
        
        # Validate each candle
        from decimal import Decimal
        metadata_list = []
        prev_close = None
        
        for candle in candles:
            _, meta = validation_service.validate_candle(
                symbol,
                candle,
                prev_close=Decimal(str(prev_close)) if prev_close is not None else None,
                median_volume=median_vol if median_vol > 0 else None
            )
            metadata_list.append(meta)
            prev_close = candle.get('c')
        
        # Insert into database
        inserted = db_service.insert_ohlcv_batch(symbol, candles, metadata_list, timeframe)
        
        # Log backfill result
        db_service.log_backfill(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            inserted,
            True,
            None
        )
        
        # Update tracked_symbols to record that this timeframe was successfully backfilled
        await update_symbol_timeframe(database_url, symbol, timeframe)
        
        logger.info(f"✓ Successfully backfilled {inserted} records for {symbol}")
        return inserted, 0
    
    except Exception as e:
        logger.error(f"✗ Error backfilling {symbol}: {e}")
        db_service.log_backfill(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            0,
            False,
            str(e)
        )
        return 0, 1


def _parse_args():
    parser = argparse.ArgumentParser(description="Backfill historical data for tracked symbols")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated list of symbols to backfill (e.g. AAPL,MSFT,SPY). If omitted, backfills all active symbols from database"
    )
    parser.add_argument(
        "--start",
        type=str,
        default=START_DATE.strftime("%Y-%m-%d"),
        help="Start date (YYYY-MM-DD). Defaults to ~5 years ago"
    )
    parser.add_argument(
        "--end",
        type=str,
        default=END_DATE.strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD). Defaults to today (UTC)"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="1d",
        help="Timeframe: 5m, 15m, 30m, 1h, 4h, 1d (default), 1w"
    )
    return parser.parse_args()


async def fetch_active_symbols(database_url: str) -> list[str]:
    """Fetch all active symbols from tracked_symbols table"""
    try:
        conn = await asyncpg.connect(database_url)
        rows = await conn.fetch(
            "SELECT symbol FROM tracked_symbols WHERE active = TRUE ORDER BY symbol"
        )
        await conn.close()
        return [row['symbol'] for row in rows]
    except Exception as e:
        logger.error(f"Error fetching symbols from database: {e}")
        return []


async def main():
    """Run backfill for requested symbols"""
    args = _parse_args()
    try:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(args.end, "%Y-%m-%d").date()
    except ValueError:
        logger.error("Invalid --start or --end date. Use YYYY-MM-DD format.")
        return

    if start_dt > end_dt:
        logger.error("Start date must be <= end date")
        return

    # Get database URL - prefer explicit DATABASE_URL env var
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Fallback: construct from individual components
        db_user = os.getenv("DB_USER", "market_user")
        db_password = os.getenv("DB_PASSWORD", "changeMe123")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/market_data"
    
    # Determine which symbols to backfill
    if args.symbols:
        # User provided explicit symbols
        requested_symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        # Fetch from database
        logger.info("Fetching active symbols from database...")
        requested_symbols = await fetch_active_symbols(database_url)
    
    if not requested_symbols:
        logger.error("No symbols to backfill. Initialize symbols first with: python scripts/init_symbols.py")
        return
    
    # Validate timeframe
    if args.timeframe not in ['5m', '15m', '30m', '1h', '4h', '1d', '1w']:
        logger.error(f"Invalid timeframe: {args.timeframe}. Must be one of: 5m, 15m, 30m, 1h, 4h, 1d, 1w")
        return
    
    polygon_api_key = os.getenv("POLYGON_API_KEY")
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY not set in environment")
        return
    
    polygon_client = PolygonClient(polygon_api_key)
    validation_service = ValidationService()
    db_service = DatabaseService(database_url)
    
    logger.info(f"Starting backfill for {len(requested_symbols)} symbols")
    logger.info(f"Timeframe: {args.timeframe}")
    logger.info(f"Date range: {start_dt} to {end_dt}")
    logger.info("-" * 60)
    
    total_inserted = 0
    total_failed = 0
    
    # Backfill each symbol
    for symbol in requested_symbols:
        inserted, failed = await backfill_symbol(
            symbol,
            polygon_client,
            validation_service,
            db_service,
            start_dt,
            end_dt,
            args.timeframe,
            database_url
        )
        total_inserted += inserted
        total_failed += failed
    
    logger.info("-" * 60)
    logger.info(f"Backfill complete!")
    logger.info(f"Total records inserted: {total_inserted}")
    logger.info(f"Failed symbols: {total_failed}/{len(requested_symbols)}")
    
    # Print status
    logger.info("-" * 60)
    metrics = db_service.get_status_metrics()
    logger.info(f"Database status:")
    logger.info(f"  Symbols: {metrics.get('symbols_available', 0)}")
    logger.info(f"  Total records: {metrics.get('total_records', 0):,}")
    logger.info(f"  Validated records: {metrics.get('validated_records', 0):,}")
    logger.info(f"  Validation rate: {metrics.get('validation_rate_pct', 0):.1f}%")
    logger.info(f"  Latest data: {metrics.get('latest_data')}")


if __name__ == "__main__":
    asyncio.run(main())
