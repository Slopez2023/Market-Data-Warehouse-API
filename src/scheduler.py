"""Daily auto-backfill scheduler using APScheduler"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.clients.polygon_client import PolygonClient
from src.services.validation_service import ValidationService
from src.services.database_service import DatabaseService

logger = logging.getLogger(__name__)


class AutoBackfillScheduler:
    """
    Automated daily backfill scheduler.
    
    Runs daily at configured time (default 2 AM UTC):
    1. Fetch latest OHLCV for configured symbols
    2. Validate candles
    3. Insert/update in database
    4. Log results
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
        logger.info(f"Starting backfill job for {len(self.symbols)} symbols")
        
        results = {
            "success": 0,
            "failed": 0,
            "total_records": 0
        }
        
        for symbol in self.symbols:
            try:
                records = await self._backfill_symbol(symbol)
                results["success"] += 1
                results["total_records"] += records
            except Exception as e:
                logger.error(f"Backfill failed for {symbol}: {e}")
                results["failed"] += 1
        
        logger.info(
            f"Backfill job complete: {results['success']} symbols successful, "
            f"{results['failed']} failed, {results['total_records']} records imported"
        )
    
    async def _backfill_symbol(self, symbol: str) -> int:
        """
        Backfill data for a single symbol.
        
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
            
            from decimal import Decimal
            for candle in candles:
                _, meta = self.validation_service.validate_candle(
                    symbol,
                    candle,
                    prev_close=Decimal(str(prev_close)) if prev_close is not None else None,
                    median_volume=median_vol if median_vol > 0 else None
                )
                metadata_list.append(meta)
                
                # Update prev_close for next iteration (store as is, convert in validate_candle)
                prev_close = candle.get('c')  # Close price
            
            # Insert into database
            inserted = self.db_service.insert_ohlcv_batch(symbol, candles, metadata_list)
            
            # Log backfill result
            self.db_service.log_backfill(
                symbol,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                inserted,
                True,
                None
            )
            
            logger.info(f"Successfully backfilled {inserted} records for {symbol}")
            return inserted
        
        except Exception as e:
            logger.error(f"Error backfilling {symbol}: {e}")
            self.db_service.log_backfill(
                symbol,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                0,
                False,
                str(e)
            )
            return 0
