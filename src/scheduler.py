"""Daily auto-backfill scheduler using APScheduler"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from decimal import Decimal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncpg

from src.clients.multi_source_client import MultiSourceClient
from src.services.validation_service import ValidationService
from src.services.database_service import DatabaseService
from src.quant_engine.quant_features import QuantFeatureEngine
import pandas as pd

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
        schedule_minute: int = 0,
        config=None,
        enrichment_enabled: bool = False,
        enrichment_hour: int = 1,
        enrichment_minute: int = 30,
        parallel_backfill: bool = True,
        max_concurrent_symbols: int = 3
    ):
        """
        Initialize scheduler.
        
        Args:
            polygon_api_key: Polygon.io API key
            database_url: Database connection string
            symbols: List of symbols to backfill (loaded from DB if not provided)
            schedule_hour: UTC hour to run backfill (0-23, default 2)
            schedule_minute: Minute to run backfill (0-59, default 0)
            config: AppConfig instance for enrichment service
            enrichment_enabled: Whether to enable data enrichment pipeline
            enrichment_hour: UTC hour to run enrichment (0-23, default 1)
            enrichment_minute: Minute to run enrichment (0-59, default 30)
            parallel_backfill: Phase 3 - Enable parallel symbol processing (default True)
            max_concurrent_symbols: Phase 3 - Max concurrent symbols to process (default 3)
        """
        self.data_client = MultiSourceClient(
            polygon_api_key=polygon_api_key,
            enable_fallback=True
        )
        self.db_service = DatabaseService(database_url)
        self.validation_service = ValidationService()
        self.database_url = database_url
        
        # Symbols are loaded from DB in start() method
        # Use provided list if given, otherwise empty (will be loaded from DB)
        self.symbols = symbols or []
        
        self.schedule_hour = schedule_hour
        self.schedule_minute = schedule_minute
        
        # Enrichment service setup
        self.enrichment_enabled = enrichment_enabled
        self.enrichment_hour = enrichment_hour
        self.enrichment_minute = enrichment_minute
        self.config = config
        self.enrichment_service: Optional[object] = None
        
        # Phase 3: Parallel backfill settings
        self.parallel_backfill = parallel_backfill
        self.max_concurrent_symbols = max_concurrent_symbols
        
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
        
        # Add enrichment job if enabled
        if self.enrichment_enabled:
            self._setup_enrichment_service()
            enrichment_trigger = CronTrigger(hour=self.enrichment_hour, minute=self.enrichment_minute)
            self.scheduler.add_job(
                self._enrichment_job,
                trigger=enrichment_trigger,
                id="daily_enrichment",
                name="Daily Data Enrichment"
            )
            logger.info(f"Enrichment pipeline scheduled for {self.enrichment_hour:02d}:{self.enrichment_minute:02d} UTC daily")
        
        # Phase 4: Add health monitoring job (runs every 6 hours)
        health_trigger = CronTrigger(hour='*/6')
        self.scheduler.add_job(
            self._health_monitoring_job,
            trigger=health_trigger,
            id="health_monitoring",
            name="Data Health Monitoring"
        )
        logger.info("Health monitoring job scheduled for every 6 hours")
        
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
    
    async def _backfill_symbols_parallel(self, symbols_data: List[tuple], max_concurrent: int = 3) -> Dict:
        """
        Phase 3: Parallel backfill with staggered requests.
        
        Instead of processing symbols sequentially, process multiple symbols in parallel
        with staggered delays to avoid rate limiting.
        
        Args:
            symbols_data: List of (symbol, asset_class, timeframes) tuples
            max_concurrent: Maximum number of concurrent backfills (default 3)
        
        Returns:
            Results dictionary with success/failed counts
        """
        results = {
            "success": 0,
            "failed": 0,
            "total_records": 0,
            "timestamp": datetime.utcnow().isoformat(),
            "symbols_processed": []
        }
        
        # Process symbols in groups of max_concurrent
        for i in range(0, len(symbols_data), max_concurrent):
            group = symbols_data[i:i+max_concurrent]
            logger.info(f"Processing symbol group {i//max_concurrent + 1} with {len(group)} symbols")
            
            # Create staggered tasks: 0s, 5s, 10s delays to avoid rate limit spike
            tasks = []
            for j, (symbol, asset_class, timeframes) in enumerate(group):
                delay = j * 5  # Stagger by 5 seconds
                
                # Create a task that sleeps first, then backfills
                async def staggered_backfill(sym, asset_cls, tfs, sleep_delay):
                    await asyncio.sleep(sleep_delay)
                    # Phase 4: Create backfill state for each symbol
                    exec_ids = []
                    
                    try:
                        await self._update_symbol_backfill_status(sym, "in_progress", None)
                        
                        total_for_symbol = 0
                        for timeframe in tfs:
                            # Create state record
                            try:
                                exec_id = self.db_service.create_backfill_state(
                                    symbol=sym,
                                    asset_class=asset_cls,
                                    timeframe=timeframe,
                                    status="pending"
                                )
                                exec_ids.append(exec_id)
                                
                                # Update to in_progress
                                self.db_service.update_backfill_state(exec_id, "in_progress")
                            except Exception as e:
                                logger.warning(f"Failed to create backfill state for {sym}/{timeframe}: {e}")
                            
                            records = await self._backfill_symbol(sym, asset_cls, timeframe)
                            total_for_symbol += records
                            
                            # Update state with results
                            if exec_ids:
                                self.db_service.update_backfill_state(
                                    exec_ids[-1],
                                    "completed" if records > 0 else "failed",
                                    records_inserted=records
                                )
                        
                        if total_for_symbol > 0:
                            results["success"] += 1
                            await self._update_symbol_backfill_status(sym, "completed", None)
                            # Track success
                            self.db_service.track_symbol_failure(sym, success=True)
                        else:
                            logger.warning(f"No records inserted for {sym}")
                            await self._update_symbol_backfill_status(sym, "completed", "No records")
                        
                        results["total_records"] += total_for_symbol
                        results["symbols_processed"].append({
                            "symbol": sym,
                            "asset_class": asset_cls,
                            "timeframes": tfs,
                            "records": total_for_symbol,
                            "status": "completed"
                        })
                        
                        return total_for_symbol
                    
                    except Exception as e:
                        logger.error(f"Backfill failed for {sym}: {e}")
                        results["failed"] += 1
                        await self._update_symbol_backfill_status(sym, "failed", str(e))
                        # Track failure
                        self.db_service.track_symbol_failure(sym, success=False)
                        
                        # Update all states to failed
                        for exec_id in exec_ids:
                            self.db_service.update_backfill_state(
                                exec_id,
                                "failed",
                                error_message=str(e)
                            )
                        
                        results["symbols_processed"].append({
                            "symbol": sym,
                            "asset_class": asset_cls,
                            "timeframes": tfs,
                            "status": "failed",
                            "error": str(e)
                        })
                        return 0
                
                task = staggered_backfill(symbol, asset_class, timeframes, delay)
                tasks.append(task)
            
            # Wait for all tasks in this group to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Small delay between groups to avoid burst
            if i + max_concurrent < len(symbols_data):
                logger.info("Pausing 10s between symbol groups to manage rate limits")
                await asyncio.sleep(10)
        
        return results
    
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
        
        logger.info(f"Starting backfill job for {len(self.symbols)} symbols (parallel={self.parallel_backfill})")
        _last_backfill_time = datetime.utcnow()
        
        # Create execution log entry
        execution_id = None
        try:
            execution_id = self.db_service.create_scheduler_execution_log(
                started_at=_last_backfill_time,
                total_symbols=len(self.symbols),
                status="running"
            )
        except Exception as e:
            logger.warning(f"Failed to create scheduler execution log: {e}")
        
        # Phase 3: Use parallel processing if enabled
        if self.parallel_backfill:
            logger.info(f"Using Phase 3 parallel backfill with max {self.max_concurrent_symbols} concurrent symbols")
            results = await self._backfill_symbols_parallel(self.symbols, self.max_concurrent_symbols)
        else:
            # Legacy sequential backfill
            logger.info("Using sequential backfill (Phase 3 parallel disabled)")
            results = {
                "success": 0,
                "failed": 0,
                "total_records": 0,
                "timestamp": _last_backfill_time.isoformat(),
                "execution_id": execution_id,
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
        
        # Update execution log with completion details
        if execution_id:
            try:
                self.db_service.update_scheduler_execution_log(
                    execution_id=execution_id,
                    completed_at=datetime.utcnow(),
                    successful_symbols=results["success"],
                    failed_symbols=results["failed"],
                    total_records_processed=results["total_records"],
                    status="completed" if results["failed"] == 0 else "completed_with_errors"
                )
            except Exception as e:
                logger.warning(f"Failed to update scheduler execution log: {e}")
        
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
            # Fetch from multi-source with fallback
            candles, source = await self.data_client.fetch_range(
                symbol,
                timeframe,
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                is_crypto=(asset_class == "crypto"),  # Pass asset class flag to normalize crypto symbols
                validate=False  # Live data, just get it fast
            )
            
            if not candles:
                logger.warning(f"No data returned from {source or 'any source'} for {symbol}")
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
            
            # Insert into database with timeframe and source
            inserted = self.db_service.insert_ohlcv_batch(symbol, candles_to_insert, metadata_to_insert, timeframe, source=source)
            
            # Generate quant features if insertion successful
            if inserted > 0:
                try:
                    quant_features_count = await self._compute_quant_features(symbol, timeframe)
                    logger.info(f"Computed quant features for {symbol} {timeframe}: {quant_features_count} records")
                except Exception as e:
                    logger.warning(f"Failed to compute quant features for {symbol} {timeframe}: {e}")
                    # Log failure for monitoring but don't fail the backfill
                    try:
                        self.db_service.log_feature_computation_failure(
                            symbol=symbol,
                            timeframe=timeframe,
                            error_message=str(e),
                            execution_id=execution_id
                        )
                    except Exception as log_error:
                        logger.debug(f"Failed to log feature computation failure: {log_error}")
            
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
    
    async def _compute_quant_features(self, symbol: str, timeframe: str) -> int:
        """
        Compute quant features for a symbol/timeframe and store in database.
        
        Args:
            symbol: Stock ticker
            timeframe: Candle timeframe
        
        Returns:
            Number of records with computed features
        """
        try:
            # Fetch recent OHLCV data (last 100 bars to capture all lookback periods)
            data = self.db_service.get_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start=(datetime.utcnow() - timedelta(days=100)).strftime('%Y-%m-%d'),
                end=datetime.utcnow().strftime('%Y-%m-%d'),
                validated_only=False,  # Include all records
                min_quality=0
            )
            
            if not data:
                logger.debug(f"No data found for {symbol} {timeframe} to compute features")
                return 0
            
            # Convert to DataFrame for feature computation
            df = pd.DataFrame([
                {
                    'time': pd.to_datetime(d['time']),
                    'open': float(d['open']),
                    'high': float(d['high']),
                    'low': float(d['low']),
                    'close': float(d['close']),
                    'volume': int(d['volume'])
                }
                for d in data
            ])
            
            # Compute quant features
            df_with_features = QuantFeatureEngine.compute(df)
            
            # Prepare features data for insertion
            features_data = []
            for idx, row in df_with_features.iterrows():
                features_data.append({
                    'time': row['time'],
                    'return_1d': float(row.get('return_1d', 0)),
                    'volatility_20': float(row.get('volatility_20', 0)),
                    'volatility_50': float(row.get('volatility_50', 0)),
                    'atr': float(row.get('atr', 0)),
                    'rolling_volume_20': int(row.get('rolling_volume_20', 0)),
                    'volume_ratio': float(row.get('volume_ratio', 1)),
                    'structure_label': str(row.get('structure_label', 'range')),
                    'trend_direction': str(row.get('trend_direction', 'neutral')),
                    'volatility_regime': str(row.get('volatility_regime', 'medium')),
                    'trend_regime': str(row.get('trend_regime', 'ranging')),
                    'compression_regime': str(row.get('compression_regime', 'expanded'))
                })
            
            # Store computed features in database
            updated = self.db_service.insert_quant_features(
                symbol=symbol,
                timeframe=timeframe,
                features_data=features_data
            )
            
            # Update summary table with latest features if any records updated
            if updated > 0 and features_data:
                latest_features = features_data[-1]  # Last computed record
                self.db_service.update_quant_feature_summary(
                    symbol=symbol,
                    timeframe=timeframe,
                    latest_record=latest_features
                )
            
            return updated
        
        except Exception as e:
            logger.error(f"Error computing quant features for {symbol} {timeframe}: {e}")
            raise
    
    def _setup_enrichment_service(self) -> None:
        """Initialize the data enrichment service - disabled"""
        logger.info("Enrichment service initialization disabled")
    
    async def _enrichment_job(self) -> None:
        """
        Main enrichment job - runs daily.
        
        Enriches all active symbols with computed features and stores in market_data_v2.
        Runs after backfill completes to ensure data is fresh.
        """
        if not self.enrichment_service:
            logger.error("Enrichment service not initialized")
            return
        
        # Reload symbols from database at start of each enrichment
        try:
            self.symbols = await self._load_symbols_from_db()
            if not self.symbols:
                logger.warning("No active symbols found in database for enrichment")
                return
        except Exception as e:
            logger.error(f"Failed to reload symbols for enrichment: {e}")
            return
        
        logger.info(f"Starting enrichment job for {len(self.symbols)} symbols")
        enrichment_start = datetime.utcnow()
        
        results = {
            "success": 0,
            "failed": 0,
            "total_records_inserted": 0,
            "total_records_updated": 0,
            "timestamp": enrichment_start.isoformat(),
            "symbols_processed": []
        }
        
        for symbol, asset_class, timeframes in self.symbols:
            try:
                # Calculate date range for enrichment (last 365 days)
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=365)
                
                # Run enrichment for all configured timeframes
                enrichment_result = await self.enrichment_service.enrich_asset(
                    symbol=symbol,
                    asset_class=asset_class,
                    timeframes=timeframes,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if enrichment_result['success']:
                    results["success"] += 1
                    results["total_records_inserted"] += enrichment_result['total_records_inserted']
                    results["total_records_updated"] += enrichment_result['total_records_updated']
                    
                    results["symbols_processed"].append({
                        "symbol": symbol,
                        "asset_class": asset_class,
                        "timeframes": timeframes,
                        "inserted": enrichment_result['total_records_inserted'],
                        "updated": enrichment_result['total_records_updated'],
                        "status": "completed"
                    })
                    logger.info(f"Enrichment completed for {symbol}: {enrichment_result['total_records_inserted']} inserted, {enrichment_result['total_records_updated']} updated")
                else:
                    results["failed"] += 1
                    results["symbols_processed"].append({
                        "symbol": symbol,
                        "asset_class": asset_class,
                        "timeframes": timeframes,
                        "status": "failed",
                        "error": enrichment_result.get('error', 'Unknown error')
                    })
                    logger.error(f"Enrichment failed for {symbol}: {enrichment_result.get('error')}")
            
            except Exception as e:
                logger.error(f"Enrichment exception for {symbol}: {e}")
                results["failed"] += 1
                results["symbols_processed"].append({
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "timeframes": timeframes,
                    "status": "failed",
                    "error": str(e)
                })
        
        enrichment_duration = (datetime.utcnow() - enrichment_start).total_seconds()
        logger.info(
            f"Enrichment job complete: {results['success']} symbols successful, "
            f"{results['failed']} failed, {results['total_records_inserted']} records inserted, "
            f"{results['total_records_updated']} updated in {enrichment_duration:.1f}s"
        )


    async def _health_monitoring_job(self) -> None:
        """
        Phase 4: Proactive health monitoring job - runs every 6 hours.
        
        Checks for:
        1. Data staleness (last update > 6 hours)
        2. Consecutive failures per symbol
        3. Data gaps and anomalies
        4. Triggers alerts for critical issues
        """
        logger.info("Starting health monitoring job")
        monitoring_start = datetime.utcnow()
        
        results = {
            "timestamp": monitoring_start.isoformat(),
            "stale_symbols": [],
            "failed_symbols": [],
            "anomalies_detected": 0,
            "alerts_triggered": 0
        }
        
        try:
            # Reload symbols for monitoring
            symbols_to_monitor = await self._load_symbols_from_db()
            
            # Check data staleness for each symbol
            for symbol, asset_class, timeframes in symbols_to_monitor:
                for timeframe in timeframes:
                    try:
                        # Query for latest data timestamp
                        conn = await asyncpg.connect(self.database_url)
                        latest = await conn.fetchval(
                            """
                            SELECT MAX(time) FROM market_data
                            WHERE symbol = $1 AND timeframe = $2
                            """,
                            symbol, timeframe
                        )
                        await conn.close()
                        
                        if latest:
                            staleness_hours = (datetime.utcnow() - latest).total_seconds() / 3600
                            
                            # Alert if stale for > 6 hours
                            if staleness_hours > 6:
                                results["stale_symbols"].append({
                                    "symbol": symbol,
                                    "timeframe": timeframe,
                                    "hours_stale": round(staleness_hours, 2),
                                    "last_update": latest.isoformat()
                                })
                                
                                # Log anomaly
                                self.db_service.detect_data_anomalies(
                                    symbol=symbol,
                                    check_gaps=False,
                                    check_outliers=False,
                                    check_staleness=True
                                )
                                
                                results["alerts_triggered"] += 1
                                logger.warning(
                                    f"Data staleness alert for {symbol}/{timeframe}: "
                                    f"stale for {staleness_hours:.1f} hours"
                                )
                    
                    except Exception as e:
                        logger.error(f"Error checking staleness for {symbol}/{timeframe}: {e}")
            
            # Check consecutive failure tracking
            conn = await asyncpg.connect(self.database_url)
            failed_symbols = await conn.fetch(
                """
                SELECT symbol, consecutive_failures, last_failure_at
                FROM symbol_failure_tracking
                WHERE consecutive_failures >= 3 AND alert_sent = FALSE
                ORDER BY consecutive_failures DESC
                """
            )
            await conn.close()
            
            for record in failed_symbols:
                results["failed_symbols"].append({
                    "symbol": record['symbol'],
                    "consecutive_failures": record['consecutive_failures'],
                    "last_failure": record['last_failure_at'].isoformat() if record['last_failure_at'] else None
                })
                
                # Send alert
                try:
                    conn = await asyncpg.connect(self.database_url)
                    await conn.execute(
                        """
                        UPDATE symbol_failure_tracking
                        SET alert_sent = TRUE, alert_sent_at = NOW()
                        WHERE symbol = $1
                        """,
                        record['symbol']
                    )
                    await conn.close()
                    
                    logger.error(
                        f"Failure alert for {record['symbol']}: "
                        f"{record['consecutive_failures']} consecutive failures"
                    )
                    results["alerts_triggered"] += 1
                
                except Exception as e:
                    logger.error(f"Failed to update alert status for {record['symbol']}: {e}")
            
            # Run anomaly detection
            try:
                anomalies = self.db_service.detect_data_anomalies(
                    check_gaps=True,
                    check_outliers=True,
                    check_staleness=False  # Already checked above
                )
                
                if anomalies and "total_anomalies" in anomalies:
                    results["anomalies_detected"] = anomalies["total_anomalies"]
                    
                    if anomalies["total_anomalies"] > 0:
                        logger.warning(f"Data anomalies detected: {anomalies['total_anomalies']}")
            
            except Exception as e:
                logger.error(f"Error detecting anomalies: {e}")
            
            duration = (datetime.utcnow() - monitoring_start).total_seconds()
            logger.info(
                f"Health monitoring complete: {len(results['stale_symbols'])} stale symbols, "
                f"{len(results['failed_symbols'])} failed symbols, "
                f"{results['alerts_triggered']} alerts triggered ({duration:.1f}s)"
            )
        
        except Exception as e:
            logger.error(f"Health monitoring job failed: {e}")


def get_last_backfill_result() -> Optional[Dict]:
    """Get last backfill result (for monitoring endpoint)"""
    return _last_backfill_result


def get_last_backfill_time() -> Optional[datetime]:
    """Get last backfill time (for monitoring endpoint)"""
    return _last_backfill_time
