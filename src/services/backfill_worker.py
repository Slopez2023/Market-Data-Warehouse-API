"""Background worker for processing backfill jobs."""

import asyncio
import logging
from typing import List
from datetime import datetime
from sqlalchemy import text

logger = logging.getLogger(__name__)


class BackfillWorker:
    """Processes backfill jobs in the background."""
    
    def __init__(self, db_service, polygon_service):
        self.db = db_service
        self.polygon = polygon_service
    
    async def process_job(self, job_id: str, symbols: List[str], 
                         start_date: str, end_date: str, 
                         timeframes: List[str]):
        """Process a backfill job asynchronously."""
        session = self.db.SessionLocal()
        try:
            # Mark job as running
            session.execute(text("""
                UPDATE backfill_jobs 
                SET status = 'running', started_at = NOW()
                WHERE id = :job_id
            """), {"job_id": job_id})
            session.commit()
            
            logger.info(f"Starting backfill job {job_id}")
            
            total_combinations = len(symbols) * len(timeframes)
            completed = 0
            
            for symbol in symbols:
                for timeframe in timeframes:
                    try:
                        logger.info(f"Processing {symbol} {timeframe} ({completed+1}/{total_combinations})")
                        
                        # Update current processing
                        session.execute(text("""
                            UPDATE backfill_jobs 
                            SET current_symbol = :symbol, current_timeframe = :timeframe
                            WHERE id = :job_id
                        """), {
                            "job_id": job_id,
                            "symbol": symbol,
                            "timeframe": timeframe
                        })
                        session.commit()
                        
                        # Create progress record
                        session.execute(text("""
                            INSERT INTO backfill_job_progress (job_id, symbol, timeframe, status, started_at)
                            VALUES (:job_id, :symbol, :timeframe, 'running', NOW())
                            ON CONFLICT (job_id, symbol, timeframe) DO UPDATE SET 
                                status = 'running', started_at = NOW()
                        """), {
                            "job_id": job_id,
                            "symbol": symbol,
                            "timeframe": timeframe
                        })
                        session.commit()
                        
                        # Fetch OHLCV data from Polygon
                        candles = await self.polygon.fetch_candles(
                            symbol=symbol,
                            timeframe=timeframe,
                            start_date=start_date,
                            end_date=end_date
                        )
                        
                        records_fetched = len(candles)
                        
                        # Insert into database
                        records_inserted = await self.db.insert_ohlcv_backfill(
                            symbol=symbol,
                            timeframe=timeframe,
                            candles=candles
                        )
                        
                        # Update progress record
                        session.execute(text("""
                            UPDATE backfill_job_progress 
                            SET status = 'completed', 
                                records_fetched = :records_fetched,
                                records_inserted = :records_inserted,
                                completed_at = NOW(),
                                duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER
                            WHERE job_id = :job_id AND symbol = :symbol AND timeframe = :timeframe
                        """), {
                            "job_id": job_id,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "records_fetched": records_fetched,
                            "records_inserted": records_inserted
                        })
                        
                        # Update parent job totals
                        session.execute(text("""
                            UPDATE backfill_jobs 
                            SET total_records_fetched = total_records_fetched + :records_fetched,
                                total_records_inserted = total_records_inserted + :records_inserted
                            WHERE id = :job_id
                        """), {
                            "job_id": job_id,
                            "records_fetched": records_fetched,
                            "records_inserted": records_inserted
                        })
                        
                        session.commit()
                        logger.info(f"Completed {symbol} {timeframe}: {records_inserted} records")
                        
                    except Exception as e:
                        logger.error(f"Error processing {symbol} {timeframe}: {e}")
                        
                        # Mark as failed
                        session.execute(text("""
                            UPDATE backfill_job_progress 
                            SET status = 'failed', 
                                error_message = :error,
                                completed_at = NOW(),
                                duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER
                            WHERE job_id = :job_id AND symbol = :symbol AND timeframe = :timeframe
                        """), {
                            "job_id": job_id,
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "error": str(e)
                        })
                        session.commit()
                    
                    finally:
                        completed += 1
                        # Update progress percentage
                        progress_pct = int((completed / total_combinations) * 100)
                        session.execute(text("""
                            UPDATE backfill_jobs 
                            SET progress_pct = :progress_pct
                            WHERE id = :job_id
                        """), {
                            "job_id": job_id,
                            "progress_pct": progress_pct
                        })
                        session.commit()
            
            # Mark job as completed
            session.execute(text("""
                UPDATE backfill_jobs 
                SET status = 'completed', completed_at = NOW(), progress_pct = 100
                WHERE id = :job_id
            """), {"job_id": job_id})
            session.commit()
            
            logger.info(f"Backfill job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Critical error in backfill job {job_id}: {e}")
            session.execute(text("""
                UPDATE backfill_jobs 
                SET status = 'failed', error_message = :error, completed_at = NOW()
                WHERE id = :job_id
            """), {
                "job_id": job_id,
                "error": str(e)
            })
            session.commit()
        
        finally:
            session.close()


# Global worker instance
_backfill_worker = None


def init_backfill_worker(db_service, polygon_service):
    """Initialize the backfill worker."""
    global _backfill_worker
    _backfill_worker = BackfillWorker(db_service, polygon_service)
    logger.info("Backfill worker initialized")


def enqueue_backfill_job(job_id: str, symbols: List[str], 
                        start_date: str, end_date: str, 
                        timeframes: List[str]):
    """Enqueue a backfill job for processing in background."""
    if not _backfill_worker:
        raise RuntimeError("Backfill worker not initialized")
    
    # Schedule as a background task (non-blocking)
    asyncio.create_task(
        _backfill_worker.process_job(job_id, symbols, start_date, end_date, timeframes)
    )
    logger.info(f"Backfill job {job_id} enqueued")
