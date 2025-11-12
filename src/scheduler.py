"""Daily auto-backfill scheduler using APScheduler"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from decimal import Decimal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncpg

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
            symbols: List of symbols to backfill (loaded from DB if not provided)
            schedule_hour: UTC hour to run backfill (0-23, default 2)
            schedule_minute: Minute to run backfill (0-59, default 0)
        """
        self.polygon_client = PolygonClient(polygon_api_key)
        self.db_service = DatabaseService(database_url)
        self.validation_service = ValidationService()
        self.database_url = database_url
        
        # Symbols are loaded from DB in start() method
        # Use provided list if given, otherwise empty (will be loaded from DB)
        self.symbols = symbols or []
        
        self.schedule_hour = schedule_hour
        self.schedule_minute = schedule_minute
        
        # APScheduler instance
        self.scheduler = AsyncIOScheduler()
    
    def start(self) -> None:
        """Start the scheduler"""
        if self.scheduler.running:
            logger.warning("Scheduler is already running")
            return
        
        # Load symbols from database if not already provided
        if not self.symbols:
            try:
                loop = asyncio.get_event_loop()
                self.symbols = loop.run_until_complete(self._load_symbols_from_db())
                logger.info(f"Loaded {len(self.symbols)} symbols from database")
            except Exception as e:
                logger.error(f"Failed to load symbols from database: {e}")
                self.symbols = []  # Start with empty list, will try again at first backfill
        
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
        
        # Log symbols by asset class
        stocks = [s for s, ac, _ in self.symbols if ac == "stock"]
        crypto = [s for s, ac, _ in self.symbols if ac == "crypto"]
        etfs = [s for s, ac, _ in self.symbols if ac == "etf"]
        
        if stocks:
            logger.info(f"Stocks ({len(stocks)}): {', '.join(stocks[:5])}{'...' if len(stocks) > 5 else ''}")
        if crypto:
            logger.info(f"Crypto ({len(crypto)}): {', '.join(crypto[:5])}{'...' if len(crypto) > 5 else ''}")
        if etfs:
            logger.info(f"ETFs ({len(etfs)}): {', '.join(etfs[:5])}{'...' if len(etfs) > 5 else ''}")
    
    def stop(self) -> None:
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    async def _load_symbols_from_db(self) -> List[tuple]:
        """
        Load active symbols from tracked_symbols table with asset class and timeframes.
        
        Returns:
            List of tuples (symbol, asset_class, timeframes) for active symbols
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            
            rows = await conn.fetch(
                "SELECT symbol, asset_class, timeframes FROM tracked_symbols WHERE active = TRUE ORDER BY symbol ASC"
            )
            
            await conn.close()
            
            # Return list of (symbol, asset_class, timeframes) tuples
            # timeframes is a PostgreSQL array, convert to list
            return [(row['symbol'], row['asset_class'], row['timeframes'] or ['1d']) for row in rows]
        
        except Exception as e:
            logger.error(f"Failed to load symbols from database: {e}")
            return []
    
    async def _update_symbol_backfill_status(
        self,
        symbol: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update backfill status for a symbol in the database.
        
        Args:
            symbol: Stock ticker
            status: Backfill status (pending, in_progress, completed, failed)
            error_message: Error message if status is failed
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            
            if error_message:
                await conn.execute(
                    """
                    UPDATE tracked_symbols
                    SET backfill_status = $1, backfill_error = $2, last_backfill = NOW()
                    WHERE symbol = $3
                    """,
                    status, error_message, symbol
                )
            else:
                await conn.execute(
                    """
                    UPDATE tracked_symbols
                    SET backfill_status = $1, backfill_error = NULL, last_backfill = NOW()
                    WHERE symbol = $2
                    """,
                    status, symbol
                )
            
            await conn.close()
            logger.debug(f"Updated {symbol} backfill status to {status}")
        
        except Exception as e:
            logger.warning(f"Failed to update backfill status for {symbol}: {e}")
    
    async def _backfill_job(self) -> None:
        """
        Main backfill job - runs daily.
        
        Fetches latest OHLCV for each symbol and validates.
        Handles both stocks and crypto.
        Tracks backfill status in database for each symbol.
        """
        global _last_backfill_result, _last_backfill_time
        
        # Reload symbols from database at start of each backfill
        try:
            self.symbols = await self._load_symbols_from_db()
            if not self.symbols:
                logger.warning("No active symbols found in database")
        except Exception as e:
            logger.error(f"Failed to reload symbols from database: {e}")
            # Continue with existing symbols if reload fails
        
        logger.info(f"Starting backfill job for {len(self.symbols)} symbols")
        _last_backfill_time = datetime.utcnow()
        
        results = {
            "success": 0,
            "failed": 0,
            "total_records": 0,
            "timestamp": _last_backfill_time.isoformat(),
            "symbols_processed": []
        }
        
        for symbol, asset_class, timeframes in self.symbols:
            try:
                # Update status: in_progress
                await self._update_symbol_backfill_status(symbol, "in_progress", None)
                
                # Run backfill for each configured timeframe
                total_for_symbol = 0
                for timeframe in timeframes:
                    records = await self._backfill_symbol(symbol, asset_class, timeframe)
                    total_for_symbol += records
                
                if total_for_symbol > 0:
                    results["success"] += 1
                    # Update status: completed
                    await self._update_symbol_backfill_status(symbol, "completed", None)
                else:
                    logger.warning(f"No records inserted for {symbol}")
                    await self._update_symbol_backfill_status(symbol, "completed", "No records inserted")
                
                results["total_records"] += total_for_symbol
                results["symbols_processed"].append({
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "timeframes": timeframes,
                    "records": total_for_symbol,
                    "status": "completed"
                })
                
            except Exception as e:
                logger.error(f"Backfill failed for {symbol}: {e}")
                results["failed"] += 1
                # Update status: failed with error message
                await self._update_symbol_backfill_status(symbol, "failed", str(e))
                results["symbols_processed"].append({
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "timeframes": timeframes,
                    "status": "failed",
                    "error": str(e)
                })
        
        _last_backfill_result = results
        
        logger.info(
            f"Backfill job complete: {results['success']} symbols successful, "
            f"{results['failed']} failed, {results['total_records']} records imported"
        )
    
    async def _backfill_symbol(self, symbol: str, asset_class: str = "stock", timeframe: str = "1d") -> int:
        """
        Backfill data for a single symbol and timeframe with retries.
        
        Fetches last N days and validates.
        Handles both stocks and crypto across multiple timeframes.
        
        Args:
            symbol: Stock ticker or crypto pair (e.g., AAPL, BTCUSD)
            asset_class: Type of asset (stock, crypto, etf)
            timeframe: Timeframe code (5m, 15m, 30m, 1h, 4h, 1d, 1w)
        
        Returns:
            Number of records inserted
        """
        # Default: fetch last 30 days (covers 20-22 trading days or ~720 hours)
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=30)
        
        logger.info(f"Backfilling {symbol} ({asset_class}) {timeframe}: {start_date} to {end_date}")
        
        # Use retry logic
        return await self._fetch_and_insert_with_retry(symbol, start_date, end_date, asset_class, timeframe)
    
    async def _fetch_and_insert_with_retry(self, symbol: str, start_date, end_date, asset_class: str = "stock", timeframe: str = "1d") -> int:
        """
        Fetch from Polygon and insert with exponential backoff retry logic.
        Supports multiple timeframes.
        """
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                return await self._fetch_and_insert(symbol, start_date, end_date, asset_class, timeframe)
            
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count < max_retries:
                    # Exponential backoff: 2s, 4s, 8s
                    wait_time = 2 ** retry_count
                    logger.warning(
                        f"Backfill failed for {symbol} {timeframe} (attempt {retry_count}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Backfill failed for {symbol} {timeframe} after {max_retries} attempts: {e}")
        
        # All retries exhausted
        self.db_service.log_backfill(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            0,
            False,
            f"Failed after {max_retries} retries ({timeframe}): {str(last_error)}"
        )
        return 0
    
    async def _fetch_and_insert(self, symbol: str, start_date, end_date, asset_class: str = "stock", timeframe: str = "1d") -> int:
        """
        Fetch from Polygon, validate, and insert into database.
        Handles both stocks and crypto across multiple timeframes.
        """
        try:
            # Fetch from Polygon based on asset class and timeframe
            if asset_class == "crypto":
                candles = await self.polygon_client.fetch_range(
                    symbol,
                    timeframe,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d')
                )
            else:
                # Handle stocks and ETFs with same endpoint
                candles = await self.polygon_client.fetch_range(
                    symbol,
                    timeframe,
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
                
                # Add timeframe to metadata
                meta['timeframe'] = timeframe
                
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
            
            # Insert into database with timeframe
            inserted = self.db_service.insert_ohlcv_batch(symbol, candles_to_insert, metadata_to_insert, timeframe)
            
            # Log backfill result
            self.db_service.log_backfill(
                symbol,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                inserted,
                True,
                f"Inserted {inserted}/{len(candles)} candles ({rejected_count} rejected) for {timeframe}"
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
