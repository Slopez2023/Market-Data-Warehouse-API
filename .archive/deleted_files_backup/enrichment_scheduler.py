"""
Phase 1g: Advanced Enrichment Scheduler with Error Recovery
Provides automatic enrichment scheduling with retry logic, monitoring, and status tracking.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.job import Job
import asyncpg

from src.services.data_enrichment_service import DataEnrichmentService
from src.services.structured_logging import StructuredLogger

logger = logging.getLogger(__name__)
slogger = StructuredLogger(__name__)


class EnrichmentJobStatus:
    """Track status of individual enrichment jobs"""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


class EnrichmentScheduler:
    """
    Advanced enrichment scheduler with APScheduler integration.
    
    Features:
    - Daily automatic enrichment for all tracked symbols
    - Per-symbol retry logic with exponential backoff
    - Parallel processing with configurable concurrency
    - Comprehensive error recovery and status tracking
    - Monitoring endpoints for health checks
    - Enrichment trigger backoff when API limits hit
    """
    
    def __init__(
        self,
        db_service,
        config,
        enrichment_hour: int = 1,
        enrichment_minute: int = 30,
        max_concurrent_symbols: int = 5,
        max_retries: int = 3,
        enable_daily_enrichment: bool = True
    ):
        """
        Initialize the enrichment scheduler.
        
        Args:
            db_service: DatabaseService instance
            config: AppConfig instance
            enrichment_hour: UTC hour for daily enrichment (0-23)
            enrichment_minute: Minute for daily enrichment (0-59)
            max_concurrent_symbols: Max symbols to process in parallel
            max_retries: Max retries per symbol on failure
            enable_daily_enrichment: Enable automatic daily enrichment
        """
        self.db = db_service
        self.config = config
        self.enrichment_service = DataEnrichmentService(db_service, config)
        
        self.enrichment_hour = enrichment_hour
        self.enrichment_minute = enrichment_minute
        self.max_concurrent_symbols = max_concurrent_symbols
        self.max_retries = max_retries
        self.enable_daily_enrichment = enable_daily_enrichment
        
        self.scheduler = AsyncIOScheduler()
        
        # Tracking state
        self.job_status: Dict[str, Dict] = {}  # symbol -> status, retry_count, etc.
        self.last_enrichment_time: Optional[datetime] = None
        self.last_enrichment_result: Optional[Dict] = None
        self.is_running = False
    
    def start(self) -> None:
        """Start the scheduler"""
        if self.scheduler.running:
            slogger.warning("Enrichment scheduler already running")
            return
        
        # Schedule daily enrichment
        if self.enable_daily_enrichment:
            trigger = CronTrigger(hour=self.enrichment_hour, minute=self.enrichment_minute)
            self.scheduler.add_job(
                self._daily_enrichment_job,
                trigger=trigger,
                id="daily_enrichment",
                name="Daily Data Enrichment",
                misfire_grace_time=3600  # Allow 1 hour grace period if missed
            )
            slogger.info(
                "daily_enrichment_scheduled",
                hour=self.enrichment_hour,
                minute=self.enrichment_minute
            )
        
        self.scheduler.start()
        self.is_running = True
        slogger.info("enrichment_scheduler_started")
    
    def stop(self) -> None:
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            slogger.info("enrichment_scheduler_stopped")
    
    async def trigger_enrichment_now(
        self,
        symbols: Optional[List[str]] = None,
        asset_class: Optional[str] = None
    ) -> Dict:
        """
        Manually trigger enrichment immediately.
        
        Args:
            symbols: Specific symbols to enrich (None = all active)
            asset_class: Filter to specific asset class
        
        Returns:
            Job result dict
        """
        slogger.info(
            "manual_enrichment_triggered",
            symbols=symbols,
            asset_class=asset_class
        )
        
        return await self._enrichment_job(
            symbols=symbols,
            asset_class=asset_class,
            manual_trigger=True
        )
    
    async def _daily_enrichment_job(self) -> None:
        """
        Main daily enrichment job.
        Scheduled to run once per day at configured time.
        """
        slogger.info("daily_enrichment_job_started")
        await self._enrichment_job(manual_trigger=False)
    
    async def _enrichment_job(
        self,
        symbols: Optional[List[str]] = None,
        asset_class: Optional[str] = None,
        manual_trigger: bool = False
    ) -> Dict:
        """
        Complete enrichment pipeline for tracked symbols.
        
        Args:
            symbols: Specific symbols to enrich
            asset_class: Filter by asset class
            manual_trigger: Whether this was manually triggered
        
        Returns:
            Results dict with success/failure stats
        """
        job_start = datetime.utcnow()
        
        results = {
            "job_id": None,
            "manual_trigger": manual_trigger,
            "started_at": job_start.isoformat(),
            "symbols_total": 0,
            "symbols_successful": 0,
            "symbols_failed": 0,
            "symbols_retried": 0,
            "total_records_inserted": 0,
            "total_records_updated": 0,
            "processing_symbols": {},
            "errors": []
        }
        
        try:
            # Load symbols to enrich
            symbols_to_enrich = await self._get_symbols_to_enrich(
                symbols=symbols,
                asset_class=asset_class
            )
            
            if not symbols_to_enrich:
                slogger.warning("no_symbols_to_enrich")
                results["error"] = "No symbols configured for enrichment"
                return results
            
            results["symbols_total"] = len(symbols_to_enrich)
            slogger.info("enrichment_job_loaded_symbols", count=len(symbols_to_enrich))
            
            # Process symbols with concurrency control
            await self._process_symbols_concurrent(
                symbols_to_enrich,
                results
            )
            
        except Exception as e:
            slogger.error("enrichment_job_error", error=str(e))
            results["errors"].append(str(e))
            return results
        
        finally:
            # Store results for monitoring
            self.last_enrichment_time = job_start
            self.last_enrichment_result = results
            
            duration = (datetime.utcnow() - job_start).total_seconds()
            results["completed_at"] = datetime.utcnow().isoformat()
            results["duration_seconds"] = duration
            
            slogger.info(
                "enrichment_job_completed",
                successful=results["symbols_successful"],
                failed=results["symbols_failed"],
                retried=results["symbols_retried"],
                duration=duration
            )
        
        return results
    
    async def _get_symbols_to_enrich(
        self,
        symbols: Optional[List[str]] = None,
        asset_class: Optional[str] = None
    ) -> List[Tuple[str, str, List[str]]]:
        """
        Get list of symbols to enrich.
        
        Returns:
            List of (symbol, asset_class, timeframes) tuples
        """
        try:
            conn = await asyncpg.connect(self.db.database_url)
            
            if symbols:
                # Filter by specific symbols
                query = """
                    SELECT symbol, asset_class, timeframes
                    FROM tracked_symbols
                    WHERE active = TRUE AND symbol = ANY($1)
                    ORDER BY symbol ASC
                """
                rows = await conn.fetch(query, symbols)
            elif asset_class:
                # Filter by asset class
                query = """
                    SELECT symbol, asset_class, timeframes
                    FROM tracked_symbols
                    WHERE active = TRUE AND asset_class = $1
                    ORDER BY symbol ASC
                """
                rows = await conn.fetch(query, asset_class)
            else:
                # Get all active symbols
                query = """
                    SELECT symbol, asset_class, timeframes
                    FROM tracked_symbols
                    WHERE active = TRUE
                    ORDER BY symbol ASC
                """
                rows = await conn.fetch(query)
            
            await conn.close()
            
            return [
                (row['symbol'], row['asset_class'], row['timeframes'] or ['1d'])
                for row in rows
            ]
        
        except Exception as e:
            slogger.error("failed_to_load_symbols", error=str(e))
            return []
    
    async def _process_symbols_concurrent(
        self,
        symbols_to_enrich: List[Tuple[str, str, List[str]]],
        results: Dict
    ) -> None:
        """
        Process symbols with concurrency control.
        
        Processes max_concurrent_symbols at a time to avoid overload.
        """
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent_symbols)
        
        async def process_with_semaphore(symbol_tuple):
            async with semaphore:
                await self._process_symbol_with_retry(symbol_tuple, results)
        
        # Create tasks for all symbols
        tasks = [
            process_with_semaphore(symbol_tuple)
            for symbol_tuple in symbols_to_enrich
        ]
        
        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _process_symbol_with_retry(
        self,
        symbol_tuple: Tuple[str, str, List[str]],
        results: Dict
    ) -> None:
        """
        Process single symbol with retry logic.
        """
        symbol, asset_class, timeframes = symbol_tuple
        
        # Initialize job status tracking
        if symbol not in self.job_status:
            self.job_status[symbol] = {
                "status": EnrichmentJobStatus.PENDING,
                "retry_count": 0,
                "last_error": None,
                "started_at": None,
                "completed_at": None
            }
        
        results["processing_symbols"][symbol] = {
            "status": "processing",
            "asset_class": asset_class,
            "timeframes": timeframes
        }
        
        retry_count = 0
        last_error = None
        
        while retry_count <= self.max_retries:
            try:
                # Update status
                self.job_status[symbol]["status"] = EnrichmentJobStatus.IN_PROGRESS
                self.job_status[symbol]["started_at"] = datetime.utcnow()
                
                slogger.info(
                    "enrichment_started",
                    symbol=symbol,
                    asset_class=asset_class,
                    attempt=retry_count + 1
                )
                
                # Calculate date range (last 365 days)
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=365)
                
                # Run enrichment
                enrichment_result = await self.enrichment_service.enrich_asset(
                    symbol=symbol,
                    asset_class=asset_class,
                    timeframes=timeframes,
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Check result
                if enrichment_result.get('success'):
                    # Success
                    results["symbols_successful"] += 1
                    results["total_records_inserted"] += enrichment_result.get('total_records_inserted', 0)
                    results["total_records_updated"] += enrichment_result.get('total_records_updated', 0)
                    
                    results["processing_symbols"][symbol] = {
                        "status": "completed",
                        "asset_class": asset_class,
                        "timeframes": timeframes,
                        "inserted": enrichment_result.get('total_records_inserted', 0),
                        "updated": enrichment_result.get('total_records_updated', 0)
                    }
                    
                    self.job_status[symbol]["status"] = EnrichmentJobStatus.COMPLETED
                    self.job_status[symbol]["completed_at"] = datetime.utcnow()
                    
                    slogger.info(
                        "enrichment_completed",
                        symbol=symbol,
                        inserted=enrichment_result.get('total_records_inserted', 0),
                        updated=enrichment_result.get('total_records_updated', 0)
                    )
                    return
                
                else:
                    # Enrichment returned failure
                    error_msg = enrichment_result.get('error', 'Unknown error')
                    raise Exception(f"Enrichment failed: {error_msg}")
            
            except Exception as e:
                last_error = str(e)
                slogger.warning(
                    "enrichment_error",
                    symbol=symbol,
                    attempt=retry_count + 1,
                    error=last_error
                )
                
                retry_count += 1
                
                if retry_count <= self.max_retries:
                    # Calculate exponential backoff: 2s, 4s, 8s
                    wait_time = 2 ** retry_count
                    slogger.info(
                        "enrichment_retry",
                        symbol=symbol,
                        attempt=retry_count + 1,
                        wait_seconds=wait_time
                    )
                    
                    self.job_status[symbol]["status"] = EnrichmentJobStatus.RETRY
                    self.job_status[symbol]["retry_count"] = retry_count
                    
                    await asyncio.sleep(wait_time)
                else:
                    # Max retries exceeded
                    results["symbols_failed"] += 1
                    results["processing_symbols"][symbol] = {
                        "status": "failed",
                        "asset_class": asset_class,
                        "timeframes": timeframes,
                        "error": last_error,
                        "attempts": retry_count
                    }
                    results["errors"].append(f"{symbol}: {last_error}")
                    
                    self.job_status[symbol]["status"] = EnrichmentJobStatus.FAILED
                    self.job_status[symbol]["last_error"] = last_error
                    self.job_status[symbol]["completed_at"] = datetime.utcnow()
                    
                    slogger.error(
                        "enrichment_failed",
                        symbol=symbol,
                        attempts=retry_count,
                        error=last_error
                    )
                    return
    
    async def get_job_status(self, symbol: Optional[str] = None) -> Dict:
        """
        Get status of enrichment jobs.
        
        Args:
            symbol: Get status for specific symbol (None = all)
        
        Returns:
            Status dict
        """
        if symbol:
            return self.job_status.get(symbol, {})
        return self.job_status
    
    async def get_scheduler_status(self) -> Dict:
        """
        Get overall scheduler status.
        
        Returns:
            Status dict with scheduler health
        """
        return {
            "running": self.is_running,
            "scheduler_running": self.scheduler.running,
            "last_enrichment_time": self.last_enrichment_time.isoformat() if self.last_enrichment_time else None,
            "last_enrichment_result": {
                "successful": self.last_enrichment_result.get("symbols_successful") if self.last_enrichment_result else None,
                "failed": self.last_enrichment_result.get("symbols_failed") if self.last_enrichment_result else None,
                "duration_seconds": self.last_enrichment_result.get("duration_seconds") if self.last_enrichment_result else None
            } if self.last_enrichment_result else None,
            "config": {
                "enrichment_hour": self.enrichment_hour,
                "enrichment_minute": self.enrichment_minute,
                "max_concurrent_symbols": self.max_concurrent_symbols,
                "max_retries": self.max_retries
            }
        }
    
    async def get_enrichment_metrics(self) -> Dict:
        """
        Get enrichment pipeline metrics.
        
        Returns:
            Comprehensive metrics dict
        """
        try:
            conn = await asyncpg.connect(self.db.database_url)
            
            # Fetch statistics from logs (last 24 hours)
            fetch_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_fetches,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_fetches,
                    AVG(source_response_time_ms) as avg_response_time_ms,
                    MAX(api_quota_remaining) as api_quota_remaining
                FROM enrichment_fetch_log
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            
            compute_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_computations,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_computations,
                    AVG(computation_time_ms) as avg_computation_time_ms
                FROM enrichment_compute_log
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            
            quality_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(DISTINCT symbol) as symbols_tracked,
                    AVG(validation_rate) as avg_validation_rate,
                    AVG(avg_quality_score) as avg_quality_score
                FROM data_quality_metrics
                WHERE metric_date > CURRENT_DATE - INTERVAL '7 days'
            """)
            
            await conn.close()
            
            return {
                "fetch_pipeline": {
                    "total_fetches": fetch_stats['total_fetches'] or 0,
                    "successful": fetch_stats['successful_fetches'] or 0,
                    "success_rate": round(
                        (fetch_stats['successful_fetches'] / fetch_stats['total_fetches'] * 100)
                        if fetch_stats['total_fetches'] else 0,
                        2
                    ),
                    "avg_response_time_ms": int(fetch_stats['avg_response_time_ms'] or 0),
                    "api_quota_remaining": fetch_stats['api_quota_remaining']
                },
                "compute_pipeline": {
                    "total_computations": compute_stats['total_computations'] or 0,
                    "successful": compute_stats['successful_computations'] or 0,
                    "success_rate": round(
                        (compute_stats['successful_computations'] / compute_stats['total_computations'] * 100)
                        if compute_stats['total_computations'] else 0,
                        2
                    ),
                    "avg_computation_time_ms": int(compute_stats['avg_computation_time_ms'] or 0)
                },
                "data_quality": {
                    "symbols_tracked": quality_stats['symbols_tracked'] or 0,
                    "avg_validation_rate": float(quality_stats['avg_validation_rate'] or 0),
                    "avg_quality_score": float(quality_stats['avg_quality_score'] or 0)
                }
            }
        
        except Exception as e:
            slogger.error("failed_to_get_enrichment_metrics", error=str(e))
            return {}
