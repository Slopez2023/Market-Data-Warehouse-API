"""
Unified Backfill Orchestrator

Wraps master_backfill.py CLI to provide a single backfill code path for both
CLI and API usage. This ensures all backfills use proper validation, gap detection,
and retry logic regardless of how they're triggered.

All backfills go through:
- OHLCV backfill with gap detection
- Validation & quality scoring
- Retry logic for failed gaps
- Audit logging
"""

import asyncio
import subprocess
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json
from sqlalchemy import text

logger = logging.getLogger(__name__)


class BackfillOrchestrator:
    """Orchestrates backfills using master_backfill.py"""
    
    def __init__(self, database_url: str, polygon_api_key: str):
        """Initialize orchestrator"""
        self.database_url = database_url
        self.polygon_api_key = polygon_api_key
        self.app_root = Path(__file__).parent.parent.parent
    
    async def trigger_backfill(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        days: int = 365,
        max_concurrent: int = 3,
        job_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict:
        """
        Trigger a master backfill with gap detection and retries.
        
        This method runs the master_backfill.py CLI as a subprocess, ensuring
        all backfills use the same comprehensive orchestrator logic.
        
        Args:
            symbols: Specific symbols (None = all active)
            timeframes: Specific timeframes (None = all configured)
            days: Days of history to backfill
            max_concurrent: Max concurrent symbols
            job_id: Optional job ID for tracking
            user_id: Optional user ID for audit trail
        
        Returns:
            Dict with job_id, status, and execution details
        """
        import uuid
        
        # Generate job ID if not provided
        if not job_id:
            job_id = str(uuid.uuid4())
        
        logger.info(
            f"Backfill orchestration started",
            extra={
                "job_id": job_id,
                "symbols": symbols,
                "timeframes": timeframes,
                "days": days,
                "user_id": user_id
            }
        )
        
        # Build master_backfill.py command
        cmd = [sys.executable, str(self.app_root / "master_backfill.py")]
        
        if symbols:
            cmd.extend(["--symbols", ",".join(symbols)])
        
        if timeframes:
            cmd.extend(["--timeframes", ",".join(timeframes)])
        
        cmd.extend(["--days", str(days)])
        cmd.extend(["--max-concurrent", str(max_concurrent)])
        
        # Set environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(self.app_root)
        
        try:
            # Record job start in audit log
            await self._audit_log(
                job_id=job_id,
                event="backfill_started",
                user_id=user_id,
                details={
                    "symbols": symbols,
                    "timeframes": timeframes,
                    "days": days,
                    "max_concurrent": max_concurrent
                }
            )
            
            # Run master_backfill.py as subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.app_root),
                env=env
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else stdout.decode()
                logger.error(
                    f"Backfill orchestration failed",
                    extra={
                        "job_id": job_id,
                        "error": error_msg[:500],
                        "return_code": process.returncode
                    }
                )
                
                # Record failure in audit log
                await self._audit_log(
                    job_id=job_id,
                    event="backfill_failed",
                    user_id=user_id,
                    details={
                        "error": error_msg[:1000],
                        "return_code": process.returncode
                    }
                )
                
                return {
                    "job_id": job_id,
                    "status": "failed",
                    "error": error_msg[:500],
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Parse results from master_backfill output
            results = await self._parse_backfill_results(job_id)
            
            # Record success in audit log
            await self._audit_log(
                job_id=job_id,
                event="backfill_completed",
                user_id=user_id,
                details=results
            )
            
            logger.info(
                f"Backfill orchestration completed",
                extra={"job_id": job_id, "results": results}
            )
            
            return {
                "job_id": job_id,
                "status": "completed",
                "results": results,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            logger.error(
                f"Backfill orchestration error: {e}",
                extra={"job_id": job_id, "error": str(e)},
                exc_info=True
            )
            
            # Record error in audit log
            await self._audit_log(
                job_id=job_id,
                event="backfill_error",
                user_id=user_id,
                details={"error": str(e)}
            )
            
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _parse_backfill_results(self, job_id: str) -> Dict:
        """
        Parse backfill results from master_backfill_results.json
        
        Returns:
            Dict with summary of backfill results
        """
        try:
            results_file = Path("/tmp/master_backfill_results.json")
            if not results_file.exists():
                return {"note": "Results file not found"}
            
            with open(results_file, 'r') as f:
                results = json.load(f)
            
            summary = results.get("summary", {})
            return {
                "symbols_processed": summary.get("total_symbols", 0),
                "successful": summary.get("successful", 0),
                "partial_failures": summary.get("partial_failures", 0),
                "total_candles_inserted": summary.get("total_candles_inserted", 0),
                "gaps_detected": summary.get("total_gaps_detected", 0),
                "gaps_filled": summary.get("total_gaps_filled", 0)
            }
        
        except Exception as e:
            logger.warning(f"Failed to parse backfill results: {e}")
            return {}
    
    async def _audit_log(
        self,
        job_id: str,
        event: str,
        user_id: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> None:
        """
        Log backfill event to audit table.
        
        Tracks:
        - Who triggered the backfill (user_id)
        - What symbols/timeframes
        - When it started/completed
        - Success/failure status
        """
        try:
            from src.services.database_service import DatabaseService
            
            db = DatabaseService(self.database_url)
            session = db.SessionLocal()
            
            try:
                session.execute(text("""
                    INSERT INTO backfill_audit_log 
                    (job_id, event, user_id, details, created_at)
                    VALUES (:job_id, :event, :user_id, :details, NOW())
                """), {
                    "job_id": job_id,
                    "event": event,
                    "user_id": user_id,
                    "details": json.dumps(details) if details else None
                })
                session.commit()
            finally:
                session.close()
        
        except Exception as e:
            logger.warning(f"Failed to audit log backfill event: {e}")


# Global instance
_orchestrator = None


def init_backfill_orchestrator(database_url: str, polygon_api_key: str) -> None:
    """Initialize the global backfill orchestrator"""
    global _orchestrator
    _orchestrator = BackfillOrchestrator(database_url, polygon_api_key)
    logger.info("Backfill orchestrator initialized")


def get_backfill_orchestrator() -> BackfillOrchestrator:
    """Get the global backfill orchestrator"""
    global _orchestrator
    if not _orchestrator:
        raise RuntimeError("Backfill orchestrator not initialized")
    return _orchestrator
