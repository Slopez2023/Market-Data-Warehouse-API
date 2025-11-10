#!/usr/bin/env python3
"""
Manual backfill script for historical data.
Fetches 5+ years of data for major US stocks.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

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

# Default symbols to backfill
DEFAULT_SYMBOLS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    "TSLA", "META", "NFLX", "AMD", "INTC",
    "PYPL", "SQ", "CRM", "ADBE", "MU"
]

# Backfill date range (5 years of data)
END_DATE = datetime.utcnow().date()
START_DATE = END_DATE - timedelta(days=365*5)


async def backfill_symbol(
    symbol: str,
    polygon_client: PolygonClient,
    validation_service: ValidationService,
    db_service: DatabaseService,
    start_date: datetime.date,
    end_date: datetime.date
) -> tuple[int, int]:
    """
    Backfill data for a single symbol.
    
    Returns:
        (inserted_count, failed_count)
    """
    try:
        logger.info(f"Backfilling {symbol}: {start_date} to {end_date}")
        
        # Fetch from Polygon
        candles = await polygon_client.fetch_daily_range(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
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
        inserted = db_service.insert_ohlcv_batch(symbol, candles, metadata_list)
        
        # Log backfill result
        db_service.log_backfill(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            inserted,
            True,
            None
        )
        
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


async def main():
    """Run backfill for all symbols"""
    # Initialize services
    polygon_api_key = os.getenv("POLYGON_API_KEY")
    db_password = os.getenv("DB_PASSWORD", "password")
    # Use Docker port-mapped database on 5433
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "5433")
    database_url = os.getenv("DATABASE_URL", f"postgresql://postgres:{db_password}@{db_host}:{db_port}/market_data")
    
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY not set in environment")
        return
    
    polygon_client = PolygonClient(polygon_api_key)
    validation_service = ValidationService()
    db_service = DatabaseService(database_url)
    
    logger.info(f"Starting backfill for {len(DEFAULT_SYMBOLS)} symbols")
    logger.info(f"Date range: {START_DATE} to {END_DATE}")
    logger.info("-" * 60)
    
    total_inserted = 0
    total_failed = 0
    
    # Backfill each symbol
    for symbol in DEFAULT_SYMBOLS:
        inserted, failed = await backfill_symbol(
            symbol,
            polygon_client,
            validation_service,
            db_service,
            START_DATE,
            END_DATE
        )
        total_inserted += inserted
        total_failed += failed
    
    logger.info("-" * 60)
    logger.info(f"Backfill complete!")
    logger.info(f"Total records inserted: {total_inserted}")
    logger.info(f"Failed symbols: {total_failed}/{len(DEFAULT_SYMBOLS)}")
    
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
