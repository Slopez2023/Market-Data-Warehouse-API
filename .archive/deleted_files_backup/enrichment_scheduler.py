"""Enrichment scheduler for periodic data enrichment."""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import asyncio
import uuid
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.services.data_enrichment_service import DataEnrichmentService
from src.services.structured_logging import StructuredLogger

logger = logging.getLogger(__name__)
slogger = StructuredLogger(__name__)


class EnrichmentScheduler:
    """Scheduler for periodic enrichment of market data."""
    
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
        Initialize enrichment scheduler.
        
        Args:
            db_service: Database service instance
            config: Configuration object
            enrichment_hour: Hour of day to run enrichment (0-23)
            enrichment_minute: Minute of hour to run enrichment
            max_concurrent_symbols: Maximum symbols to enrich concurrently
            max_retries: Maximum retry attempts for failed enrichments
            enable_daily_enrichment: Whether to enable daily enrichment schedule
        """
        self.db = db_service
        self.config = config
        self.enrichment_hour = enrichment_hour
        self.enrichment_minute = enrichment_minute
        self.max_concurrent_symbols = max_concurrent_symbols
        self.max_retries = max_retries
        self.enable_daily_enrichment = enable_daily_enrichment
        
        self.scheduler = AsyncIOScheduler()
        self.enrichment_service = None
        self.is_running = False
        self.is_paused = False
        
        # Tracking
        self.last_run_time: Optional[datetime] = None
        self.next_run_time: Optional[datetime] = None
        self.job_history: Dict[str, Dict] = {}
        
        logger.info(
            "EnrichmentScheduler initialized",
            extra={
                "hour": enrichment_hour,
                "minute": enrichment_minute,
                "max_concurrent": max_concurrent_symbols,
                "max_retries": max_retries
            }
        )
    
    def start(self) -> None:
        """Start the enrichment scheduler."""
        try:
            # Initialize enrichment service
            self.enrichment_service = DataEnrichmentService(
                db_service=self.db,
                config=self.config
            )
            
            # Schedule daily enrichment if enabled
            if self.enable_daily_enrichment:
                self.scheduler.add_job(
                    self._run_enrichment,
                    CronTrigger(
                        hour=self.enrichment_hour,
                        minute=self.enrichment_minute
                    ),
                    id='daily_enrichment',
                    name='Daily Enrichment'
                )
                logger.info(
                    f"Daily enrichment scheduled for {self.enrichment_hour:02d}:{self.enrichment_minute:02d} UTC"
                )
            
            # Start scheduler
            self.scheduler.start()
            self.is_running = True
            self.is_paused = False
            
            slogger.info("Enrichment scheduler started")
            
        except Exception as e:
            logger.error(f"Failed to start enrichment scheduler: {e}")
            raise
    
    def stop(self) -> None:
        """Stop the enrichment scheduler."""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown()
                self.is_running = False
                logger.info("Enrichment scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping enrichment scheduler: {e}")
    
    def pause(self) -> None:
        """Pause enrichment scheduler (don't remove jobs)."""
        self.is_paused = True
        logger.info("Enrichment scheduler paused")
    
    def resume(self) -> None:
        """Resume enrichment scheduler."""
        self.is_paused = False
        logger.info("Enrichment scheduler resumed")
    
    async def _run_enrichment(self) -> None:
        """Run enrichment cycle for all tracked symbols."""
        if self.is_paused:
            logger.info("Enrichment scheduler is paused, skipping run")
            return
        
        job_id = str(uuid.uuid4())
        self.last_run_time = datetime.utcnow()
        self.next_run_time = self.last_run_time + timedelta(days=1)
        
        try:
            slogger.info(
                "Enrichment cycle started",
                extra={'job_id': job_id}
            )
            
            # Get list of tracked symbols
            symbols = self._get_tracked_symbols()
            
            if not symbols:
                logger.info("No symbols to enrich")
                return
            
            # Process symbols in concurrent batches
            results = []
            for i in range(0, len(symbols), self.max_concurrent_symbols):
                batch = symbols[i:i + self.max_concurrent_symbols]
                batch_tasks = [
                    self._enrich_symbol_with_retry(symbol)
                    for symbol in batch
                ]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                results.extend(batch_results)
            
            # Log results
            successful = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'success')
            failed = sum(1 for r in results if isinstance(r, dict) and r.get('status') == 'failed')
            
            slogger.info(
                "Enrichment cycle completed",
                extra={
                    'job_id': job_id,
                    'successful': successful,
                    'failed': failed,
                    'total': len(results)
                }
            )
            
            # Store job history
            self.job_history[job_id] = {
                'started_at': self.last_run_time,
                'completed_at': datetime.utcnow(),
                'symbols_processed': len(symbols),
                'successful': successful,
                'failed': failed
            }
            
        except Exception as e:
            logger.error(f"Enrichment cycle failed: {e}", extra={'job_id': job_id})
    
    async def _enrich_symbol_with_retry(self, symbol: str, retry_count: int = 0) -> Dict:
        """Enrich a single symbol with retry logic."""
        try:
            if not self.enrichment_service:
                raise RuntimeError("Enrichment service not initialized")
            
            result = await self.enrichment_service.enrich_symbol(
                symbol=symbol,
                asset_class='stock',  # TODO: Get from tracked_symbols
                timeframes=['1d'],  # TODO: Get from tracked_symbols
            )
            
            return {
                'symbol': symbol,
                'status': 'success' if not result.get('errors') else 'failed',
                'errors': result.get('errors', [])
            }
            
        except Exception as e:
            if retry_count < self.max_retries:
                logger.warning(
                    f"Enrichment failed for {symbol}, retrying ({retry_count + 1}/{self.max_retries}): {e}"
                )
                # Exponential backoff
                await asyncio.sleep(2 ** retry_count)
                return await self._enrich_symbol_with_retry(symbol, retry_count + 1)
            else:
                logger.error(f"Enrichment failed for {symbol} after {self.max_retries} retries: {e}")
                return {
                    'symbol': symbol,
                    'status': 'failed',
                    'error': str(e)
                }
    
    def _get_tracked_symbols(self) -> List[str]:
        """Get list of tracked symbols from database."""
        try:
            session = self.db.SessionLocal()
            try:
                from sqlalchemy import text
                
                symbols = session.execute(
                    text("SELECT symbol FROM tracked_symbols ORDER BY symbol")
                ).fetchall()
                
                return [s[0] for s in symbols] if symbols else []
            finally:
                session.close()
        except Exception as e:
            logger.error(f"Error getting tracked symbols: {e}")
            return []
    
    async def trigger_enrichment(
        self,
        symbols: List[str],
        asset_class: str = 'stock',
        timeframes: Optional[List[str]] = None
    ) -> str:
        """
        Manually trigger enrichment for specific symbols.
        
        Args:
            symbols: List of symbols to enrich
            asset_class: Asset class (stock, crypto, etc.)
            timeframes: Timeframes to enrich
            
        Returns:
            Job ID for tracking
        """
        if self.is_paused:
            raise RuntimeError("Enrichment scheduler is paused")
        
        job_id = str(uuid.uuid4())
        
        try:
            if not self.enrichment_service:
                raise RuntimeError("Enrichment service not initialized")
            
            if not symbols:
                logger.warning("No symbols provided to trigger_enrichment")
                return job_id
            
            tasks = [
                self.enrichment_service.enrich_symbol(
                    symbol=s,
                    asset_class=asset_class,
                    timeframes=timeframes or ['1d']
                )
                for s in symbols
            ]
            
            # Store job history before running
            self.job_history[job_id] = {
                'started_at': datetime.utcnow(),
                'symbols': symbols,
                'status': 'running'
            }
            
            slogger.info(
                "Enrichment triggered manually",
                extra={
                    'job_id': job_id,
                    'symbols': symbols,
                    'count': len(symbols)
                }
            )
            
            # Run enrichments concurrently in background (no await needed)
            asyncio.create_task(self._run_enrichment_batch(job_id, tasks))
            
            return job_id
            
        except Exception as e:
            logger.error(f"Error triggering enrichment: {e}", extra={'job_id': job_id})
            raise
    
    async def _run_enrichment_batch(self, job_id: str, tasks: List) -> None:
        """Run a batch of enrichment tasks and track results."""
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful = sum(1 for r in results if isinstance(r, dict) and not r.get('errors'))
            failed = sum(1 for r in results if isinstance(r, dict) and r.get('errors'))
            
            self.job_history[job_id].update({
                'status': 'completed',
                'completed_at': datetime.utcnow(),
                'successful': successful,
                'failed': failed
            })
            
            slogger.info(
                "Manual enrichment batch completed",
                extra={
                    'job_id': job_id,
                    'successful': successful,
                    'failed': failed
                }
            )
        except Exception as e:
            logger.error(f"Error running enrichment batch {job_id}: {e}")
            self.job_history[job_id].update({
                'status': 'failed',
                'error': str(e),
                'completed_at': datetime.utcnow()
            })
    
    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get status of a specific enrichment job."""
        return self.job_history.get(job_id)
    
    def get_all_jobs(self, limit: int = 50) -> List[Dict]:
        """Get recent enrichment jobs."""
        # Return most recent jobs
        jobs = list(self.job_history.values())
        return jobs[-limit:] if limit else jobs
