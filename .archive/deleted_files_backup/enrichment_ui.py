"""
Phase 1h: Enrichment UI - Dashboard and Control Endpoints
Provides REST API for enrichment dashboard with real-time metrics and controls.
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import Optional, List
import logging

router = APIRouter(prefix="/api/v1/enrichment", tags=["enrichment-ui"])
logger = logging.getLogger(__name__)

# Will be initialized by main.py
_enrichment_scheduler = None


def init_enrichment_ui(enrichment_scheduler):
    """Initialize the enrichment UI with scheduler instance"""
    global _enrichment_scheduler
    _enrichment_scheduler = enrichment_scheduler


# ============================================================================
# ENRICHMENT DASHBOARD ENDPOINTS
# ============================================================================


@router.get("/dashboard/overview")
async def get_dashboard_overview():
    """
    GET /api/v1/enrichment/dashboard/overview
    
    Get comprehensive enrichment dashboard overview with all key metrics.
    
    Returns:
        {
            "scheduler": {
                "running": true,
                "last_enrichment_time": "2024-11-13T01:30:00Z",
                "next_enrichment_time": "2024-11-14T01:30:00Z"
            },
            "last_job": {
                "started_at": "2024-11-13T01:30:00Z",
                "completed_at": "2024-11-13T02:15:00Z",
                "duration_seconds": 2700,
                "successful": 42,
                "failed": 1,
                "retried": 2
            },
            "metrics": {
                "fetch_pipeline": {...},
                "compute_pipeline": {...},
                "data_quality": {...}
            },
            "job_queue": [
                {
                    "symbol": "AAPL",
                    "status": "completed",
                    "retry_count": 0
                },
                ...
            ]
        }
    """
    if not _enrichment_scheduler:
        raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
    
    try:
        scheduler_status = await _enrichment_scheduler.get_scheduler_status()
        metrics = await _enrichment_scheduler.get_enrichment_metrics()
        job_status = await _enrichment_scheduler.get_job_status()
        
        # Calculate next enrichment time
        next_enrichment = None
        if scheduler_status.get("running"):
            last_time = scheduler_status.get("last_enrichment_time")
            if last_time:
                from dateutil.parser import parse
                last_dt = parse(last_time)
                from datetime import timedelta
                next_enrichment = (last_dt + timedelta(days=1)).isoformat()
        
        # Format job queue
        job_queue = [
            {
                "symbol": symbol,
                "status": status.get("status"),
                "retry_count": status.get("retry_count", 0),
                "last_error": status.get("last_error")
            }
            for symbol, status in job_status.items()
        ]
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "scheduler": {
                "running": scheduler_status.get("running"),
                "last_enrichment_time": scheduler_status.get("last_enrichment_time"),
                "next_enrichment_time": next_enrichment
            },
            "last_job": {
                "started_at": _enrichment_scheduler.last_enrichment_result.get("started_at") if _enrichment_scheduler.last_enrichment_result else None,
                "completed_at": _enrichment_scheduler.last_enrichment_result.get("completed_at") if _enrichment_scheduler.last_enrichment_result else None,
                "duration_seconds": _enrichment_scheduler.last_enrichment_result.get("duration_seconds") if _enrichment_scheduler.last_enrichment_result else None,
                "successful": _enrichment_scheduler.last_enrichment_result.get("symbols_successful") if _enrichment_scheduler.last_enrichment_result else None,
                "failed": _enrichment_scheduler.last_enrichment_result.get("symbols_failed") if _enrichment_scheduler.last_enrichment_result else None,
                "retried": _enrichment_scheduler.last_enrichment_result.get("symbols_retried") if _enrichment_scheduler.last_enrichment_result else None
            } if _enrichment_scheduler.last_enrichment_result else None,
            "metrics": metrics,
            "job_queue": job_queue[:20]  # Show top 20 jobs
        }
    
    except Exception as e:
        logger.error(f"Error getting dashboard overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/job-status/{symbol}")
async def get_job_status(symbol: str):
    """
    GET /api/v1/enrichment/dashboard/job-status/{symbol}
    
    Get detailed status for a specific symbol's enrichment job.
    
    Returns:
        {
            "symbol": "AAPL",
            "status": "completed|failed|in_progress|pending|retry",
            "retry_count": 0,
            "last_error": null,
            "started_at": "2024-11-13T01:30:00Z",
            "completed_at": "2024-11-13T01:35:00Z"
        }
    """
    if not _enrichment_scheduler:
        raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
    
    try:
        job_status = await _enrichment_scheduler.get_job_status(symbol=symbol.upper())
        
        if not job_status:
            return {
                "symbol": symbol.upper(),
                "status": "not_found",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        return {
            "symbol": symbol.upper(),
            **job_status,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting job status for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/metrics")
async def get_enrichment_dashboard_metrics():
    """
    GET /api/v1/enrichment/dashboard/metrics
    
    Get enrichment pipeline metrics for dashboard visualization.
    
    Returns:
        {
            "fetch_pipeline": {
                "total_fetches": 1250,
                "successful": 1240,
                "success_rate": 99.2,
                "avg_response_time_ms": 245,
                "api_quota_remaining": 450
            },
            "compute_pipeline": {
                "total_computations": 1240,
                "successful": 1235,
                "success_rate": 99.6,
                "avg_computation_time_ms": 12
            },
            "data_quality": {
                "symbols_tracked": 45,
                "avg_validation_rate": 98.5,
                "avg_quality_score": 0.93
            }
        }
    """
    if not _enrichment_scheduler:
        raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
    
    try:
        metrics = await _enrichment_scheduler.get_enrichment_metrics()
        metrics["timestamp"] = datetime.utcnow().isoformat()
        return metrics
    
    except Exception as e:
        logger.error(f"Error getting enrichment metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/health")
async def get_scheduler_health():
    """
    GET /api/v1/enrichment/dashboard/health
    
    Get detailed scheduler health status.
    
    Returns:
        {
            "running": true,
            "health_status": "healthy|warning|critical",
            "issues": [],
            "config": {...}
        }
    """
    if not _enrichment_scheduler:
        raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
    
    try:
        status = await _enrichment_scheduler.get_scheduler_status()
        
        # Determine health based on status
        issues = []
        health_status = "healthy"
        
        if not status.get("running"):
            health_status = "critical"
            issues.append("Scheduler is not running")
        
        if not status.get("scheduler_running"):
            health_status = "critical"
            issues.append("APScheduler not running")
        
        if status.get("last_enrichment_result"):
            failed = status["last_enrichment_result"]["failed"]
            if failed and failed > 0:
                health_status = "warning"
                issues.append(f"Last job had {failed} failed symbols")
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "health_status": health_status,
            "running": status.get("running"),
            "scheduler_running": status.get("scheduler_running"),
            "last_enrichment_time": status.get("last_enrichment_time"),
            "issues": issues,
            "config": status.get("config", {})
        }
    
    except Exception as e:
        logger.error(f"Error getting scheduler health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENRICHMENT CONTROL ENDPOINTS
# ============================================================================


@router.post("/trigger")
async def trigger_enrichment(
    symbols: Optional[List[str]] = Query(None, description="Symbols to enrich"),
    asset_class: Optional[str] = Query(None, description="Asset class filter (stock|crypto|etf)")
):
    """
    POST /api/v1/enrichment/trigger
    
    Manually trigger enrichment for specific symbols or all active symbols.
    
    Query Parameters:
        symbols: List of symbols to enrich (e.g., ?symbols=AAPL&symbols=MSFT)
        asset_class: Filter by asset class (stock, crypto, etf)
    
    Returns:
        {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "started_at": "2024-11-13T10:31:00Z",
            "symbols_to_process": 10,
            "status": "queued"
        }
    """
    if not _enrichment_scheduler:
        raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
    
    try:
        # Normalize symbols to uppercase
        if symbols:
            symbols = [s.upper() for s in symbols]
        
        # Trigger enrichment
        result = await _enrichment_scheduler.trigger_enrichment_now(
            symbols=symbols,
            asset_class=asset_class
        )
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "triggered",
            "symbols_to_process": result.get("symbols_total"),
            "manual_trigger": True,
            "result_summary": {
                "successful": result.get("symbols_successful"),
                "failed": result.get("symbols_failed"),
                "duration_seconds": result.get("duration_seconds")
            }
        }
    
    except Exception as e:
        logger.error(f"Error triggering enrichment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_enrichment_history(
    limit: int = Query(10, ge=1, le=100, description="Number of jobs to return")
):
    """
    GET /api/v1/enrichment/history?limit=10
    
    Get historical enrichment job results.
    
    Returns:
        {
            "jobs": [
                {
                    "started_at": "2024-11-13T01:30:00Z",
                    "completed_at": "2024-11-13T02:15:00Z",
                    "duration_seconds": 2700,
                    "successful": 42,
                    "failed": 1,
                    "total_records_inserted": 1250,
                    "total_records_updated": 850
                },
                ...
            ]
        }
    """
    if not _enrichment_scheduler:
        raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
    
    try:
        # For now, return the last result
        # In production, this would query from a history table in the database
        history = []
        if _enrichment_scheduler.last_enrichment_result:
            history.append({
                "started_at": _enrichment_scheduler.last_enrichment_result.get("started_at"),
                "completed_at": _enrichment_scheduler.last_enrichment_result.get("completed_at"),
                "duration_seconds": _enrichment_scheduler.last_enrichment_result.get("duration_seconds"),
                "successful": _enrichment_scheduler.last_enrichment_result.get("symbols_successful"),
                "failed": _enrichment_scheduler.last_enrichment_result.get("symbols_failed"),
                "total_records_inserted": _enrichment_scheduler.last_enrichment_result.get("total_records_inserted"),
                "total_records_updated": _enrichment_scheduler.last_enrichment_result.get("total_records_updated")
            })
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(history),
            "jobs": history[:limit]
        }
    
    except Exception as e:
        logger.error(f"Error getting enrichment history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pause")
async def pause_enrichment():
    """
    GET /api/v1/enrichment/pause
    
    Pause the enrichment scheduler.
    """
    if not _enrichment_scheduler:
        raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
    
    try:
        _enrichment_scheduler.stop()
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "paused",
            "message": "Enrichment scheduler paused. Manual triggers will still work."
        }
    except Exception as e:
        logger.error(f"Error pausing scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resume")
async def resume_enrichment():
    """
    GET /api/v1/enrichment/resume
    
    Resume the enrichment scheduler.
    """
    if not _enrichment_scheduler:
        raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
    
    try:
        _enrichment_scheduler.start()
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "resumed",
            "message": "Enrichment scheduler resumed"
        }
    except Exception as e:
        logger.error(f"Error resuming scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))
