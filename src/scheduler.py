"""Daily auto-backfill scheduler using APScheduler"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from decimal import Decimal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.clients.polygon_client import PolygonClient
from src.services.validation_service import ValidationService
from src.services.database_service import DatabaseService

logger = logging.getLogger(__name__)

# Track backfill results for monitoring
_last_backfill_result: Optional[Dict] = None
_last_backfill_time: Optional[datetime] = None


class AutoBackfillScheduler:
    """
    Automated daily backfill scheduler.
    
    Runs daily at configured time (default 2 AM UTC):
    1. Fetch latest OHLCV for configured symbols
    2. Validate candles
    3. Insert/update in database
    4. Log results with automatic retry on failures
    """
    
    def __init__(
        self,
        polygon_api_key: str,
        database_url: str,
        symbols: List[str] = None,
        schedule_hour: int = 2,
        schedule_minute: int = 0
    ):
        """
        Initialize scheduler.
        
        Args:
            polygon_api_key: Polygon.io API key
            database_url: Database connection string
            symbols: List of symbols to backfill (default: major US stocks)
            schedule_hour: UTC hour to run backfill (0-23, default 2)
            schedule_minute: Minute to run backfill (0-59, default 0)
        """
        self.polygon_client = PolygonClient(polygon_api_key)
        self.db_service = DatabaseService(database_url)
        self.validation_service = ValidationService()
        
        # Default symbols if not provided
        self.symbols = symbols or [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
            "TSLA", "META", "NFLX", "AMD", "INTC",
            "PYPL", "SQUID", "CRM", "ADBE", "MU"
        ]
        
        self.schedule_hour = schedule_hour
        self.schedule_minute = schedule_minute
        
        # APScheduler instance
        self.scheduler = AsyncIOScheduler()
    
    def start(self) -> None:
        """Start the scheduler"""
        if self.scheduler.running:
            logger.warning("Scheduler is already running")
            return
        
        # Add backfill job with cron trigger
        trigger = CronTrigger(hour=self.schedule_hour, minute=self.schedule_minute)
        self.scheduler.add_job(
            self._backfill_job,
            trigger=trigger,
            id="daily_backfill",
            name="Daily OHLCV Backfill"
        )
        
        self.scheduler.start()
        logger.info(f"Scheduler started. Backfill scheduled for {self.schedule_hour:02d}:{self.schedule_minute:02d} UTC daily")
    
    def stop(self) -> None:
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    async def _backfill_job(self) -> None:
        """
        Main backfill job - runs daily.
        
        Fetches latest OHLCV for each symbol and validates.
        """
        global _last_backfill_result, _last_backfill_time
        
        logger.info(f"Starting backfill job for {len(self.symbols)} symbols")
        _last_backfill_time = datetime.utcnow()
        
        results = {
            "success": 0,
            "failed": 0,
            "total_records": 0,
            "timestamp": _last_backfill_time.isoformat()
        }
        
        for symbol in self.symbols:
            try:
                records = await self._backfill_symbol(symbol)
                if records > 0:
                    results["success"] += 1
                results["total_records"] += records
            except Exception as e:
                logger.error(f"Backfill failed for {symbol}: {e}")
                results["failed"] += 1
        
        _last_backfill_result = results
        
        logger.info(
            f"Backfill job complete: {results['success']} symbols successful, "
            f"{results['failed']} failed, {results['total_records']} records imported"
        )
    
    async def _backfill_symbol(self, symbol: str) -> int:
        """
        Backfill data for a single symbol with retries.
        
        Fetches last N trading days and validates.
        
        Args:
            symbol: Stock ticker
        
        Returns:
            Number of records inserted
        """
        # Default: fetch last 30 days (covers 20-22 trading days)
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)
        
        logger.info(f"Backfilling {symbol}: {start_date} to {end_date}")
        
        # Use retry logic
        return await self._fetch_and_insert_with_retry(symbol, start_date, end_date)
    
    async def _fetch_and_insert_with_retry(self, symbol: str, start_date, end_date) -> int:
        """
        Fetch from Polygon and insert with exponential backoff retry logic.
        """
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                return await self._fetch_and_insert(symbol, start_date, end_date)
            
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count < max_retries:
                    # Exponential backoff: 2s, 4s, 8s
                    wait_time = 2 ** retry_count
                    logger.warning(
                        f"Backfill failed for {symbol} (attempt {retry_count}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Backfill failed for {symbol} after {max_retries} attempts: {e}")
        
        # All retries exhausted
        self.db_service.log_backfill(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            0,
            False,
            f"Failed after {max_retries} retries: {str(last_error)}"
        )
        return 0
    
    async def _fetch_and_insert(self, symbol: str, start_date, end_date) -> int:
        """
        Fetch from Polygon, validate, and insert into database.
        """
        try:
            # Fetch from Polygon
            candles = await self.polygon_client.fetch_daily_range(
                symbol,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            if not candles:
                logger.warning(f"No data returned from Polygon for {symbol}")
                self.db_service.log_backfill(
                    symbol,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    0,
                    False,
                    "No data returned from Polygon"
                )
                return 0
            
            # Calculate median volume for anomaly detection
            median_vol = self.validation_service.calculate_median_volume(candles)
            
            # Validate each candle
            metadata_list = []
            prev_close = None
            rejected_count = 0
            
            for candle in candles:
                _, meta = self.validation_service.validate_candle(
                    symbol,
                    candle,
                    prev_close=Decimal(str(prev_close)) if prev_close is not None else None,
                    median_volume=median_vol if median_vol > 0 else None
                )
                
                # Only insert validated candles
                if meta['validated']:
                    metadata_list.append((candle, meta))
                else:
                    rejected_count += 1
                
                # Update prev_close for next iteration
                prev_close = candle.get('c')
            
            if not metadata_list:
                logger.warning(f"No valid candles for {symbol} ({rejected_count} rejected)")
                self.db_service.log_backfill(
                    symbol,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    0,
                    False,
                    f"All {rejected_count} candles rejected by validation"
                )
                return 0
            
            # Extract candles and metadata
            candles_to_insert = [c for c, _ in metadata_list]
            metadata_to_insert = [m for _, m in metadata_list]
            
            # Insert into database
            inserted = self.db_service.insert_ohlcv_batch(symbol, candles_to_insert, metadata_to_insert)
            
            # Log backfill result
            self.db_service.log_backfill(
                symbol,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                inserted,
                True,
                f"Inserted {inserted}/{len(candles)} candles ({rejected_count} rejected by validation)"
            )
            
            logger.info(
                f"Successfully backfilled {symbol}: {inserted} inserted, "
                f"{rejected_count} rejected ({inserted}/{len(candles)} valid)"
            )
            return inserted
        
        except Exception as e:
            logger.error(f"Error in _fetch_and_insert for {symbol}: {e}")
            raise


def get_last_backfill_result() -> Optional[Dict]:
    """Get last backfill result (for monitoring endpoint)"""
    return _last_backfill_result


def get_last_backfill_time() -> Optional[datetime]:
    """Get last backfill time (for monitoring endpoint)"""
    return _last_backfill_time
