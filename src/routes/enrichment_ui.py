"""Enrichment UI REST API endpoints."""

import logging
from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timedelta
from typing import Optional, List
import uuid
from sqlalchemy import text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/enrichment", tags=["enrichment"])

# Global references
_enrichment_scheduler = None
_db_service = None


def init_enrichment_ui(enrichment_scheduler, db_service=None):
    """Initialize enrichment UI with scheduler and database references."""
    global _enrichment_scheduler, _db_service
    _enrichment_scheduler = enrichment_scheduler
    _db_service = db_service
    logger.info("Enrichment UI initialized with scheduler and database service")


@router.get("/dashboard/overview")
async def get_enrichment_dashboard_overview():
    """
    Get overall enrichment pipeline status and metrics.
    
    Returns:
        {
            "scheduler_status": "running",
            "total_symbols": 45,
            "symbols_enriched": 40,
            "symbols_pending": 5,
            "last_run": "2024-11-13T01:30:00Z",
            "next_run": "2024-11-14T01:30:00Z",
            "success_rate": 98.5,
            "avg_enrichment_time_seconds": 45
        }
    """
    try:
        if not _enrichment_scheduler or not _db_service:
            return {"status": "not_initialized"}
        
        session = _db_service.SessionLocal()
        try:
            # Get total symbols and their enrichment status
            symbol_stats = session.execute(text("""
                SELECT 
                    COUNT(*) as total_symbols,
                    SUM(CASE WHEN is_stale = false AND consecutive_failures = 0 THEN 1 ELSE 0 END) as healthy_symbols,
                    SUM(CASE WHEN consecutive_failures > 0 AND consecutive_failures < 3 THEN 1 ELSE 0 END) as warning_symbols,
                    SUM(CASE WHEN is_stale = true OR consecutive_failures >= 3 THEN 1 ELSE 0 END) as problem_symbols,
                    MAX(last_enriched_at) as latest_enrichment,
                    AVG(EXTRACT(EPOCH FROM (NOW() - last_enriched_at))) as avg_age_seconds
                FROM enrichment_status
                WHERE last_enriched_at IS NOT NULL
            """)).first()
            
            total_symbols = symbol_stats[0] or 0
            healthy_symbols = symbol_stats[1] or 0
            warning_symbols = symbol_stats[2] or 0
            problem_symbols = symbol_stats[3] or 0
            latest_enrichment = symbol_stats[4]
            avg_age_seconds = symbol_stats[5] or 0
            
            # Get fetch pipeline metrics (last 24 hours)
            fetch_metrics = session.execute(text("""
                SELECT 
                    COUNT(*) as total_fetches,
                    SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as successful_fetches,
                    SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed_fetches,
                    AVG(source_response_time_ms) as avg_response_time_ms,
                    SUM(records_fetched) as total_records_fetched,
                    SUM(records_inserted) as total_records_inserted
                FROM enrichment_fetch_log
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)).first()
            
            total_fetches = fetch_metrics[0] or 0
            successful_fetches = fetch_metrics[1] or 0
            failed_fetches = fetch_metrics[2] or 0
            avg_response_time_ms = fetch_metrics[3] or 0
            total_records_fetched = fetch_metrics[4] or 0
            total_records_inserted = fetch_metrics[5] or 0
            
            fetch_success_rate = (successful_fetches / total_fetches * 100) if total_fetches > 0 else 0
            
            # Get compute pipeline metrics (last 24 hours)
            compute_metrics = session.execute(text("""
                SELECT 
                    COUNT(*) as total_computations,
                    SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as successful_computations,
                    SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed_computations,
                    AVG(computation_time_ms) as avg_computation_time_ms,
                    SUM(features_computed) as total_features_computed
                FROM enrichment_compute_log
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)).first()
            
            total_computations = compute_metrics[0] or 0
            successful_computations = compute_metrics[1] or 0
            failed_computations = compute_metrics[2] or 0
            avg_computation_time_ms = compute_metrics[3] or 0
            total_features_computed = compute_metrics[4] or 0
            
            compute_success_rate = (successful_computations / total_computations * 100) if total_computations > 0 else 0
            
            # Calculate overall success rate
            total_jobs = total_fetches + total_computations
            total_successful = successful_fetches + successful_computations
            overall_success_rate = (total_successful / total_jobs * 100) if total_jobs > 0 else 0
            
            # Calculate average enrichment time (fetch + compute avg)
            avg_enrichment_time_ms = (avg_response_time_ms or 0) + (avg_computation_time_ms or 0)
            avg_enrichment_time_seconds = avg_enrichment_time_ms / 1000
            
            return {
                "scheduler_status": "running" if _enrichment_scheduler.is_running else "stopped",
                "total_symbols": total_symbols,
                "symbols_enriched": healthy_symbols,
                "symbols_warning": warning_symbols,
                "symbols_problem": problem_symbols,
                "last_run": _enrichment_scheduler.last_run_time.isoformat() if _enrichment_scheduler.last_run_time else None,
                "next_run": _enrichment_scheduler.next_run_time.isoformat() if _enrichment_scheduler.next_run_time else None,
                "latest_enrichment": latest_enrichment.isoformat() if latest_enrichment else None,
                "avg_symbol_age_seconds": int(avg_age_seconds),
                "success_rate": round(overall_success_rate, 2),
                "fetch_success_rate": round(fetch_success_rate, 2),
                "compute_success_rate": round(compute_success_rate, 2),
                "avg_enrichment_time_seconds": round(avg_enrichment_time_seconds, 2),
                "last_24h": {
                    "total_fetches": total_fetches,
                    "successful_fetches": successful_fetches,
                    "failed_fetches": failed_fetches,
                    "total_computations": total_computations,
                    "successful_computations": successful_computations,
                    "failed_computations": failed_computations,
                    "records_fetched": total_records_fetched,
                    "records_inserted": total_records_inserted,
                    "features_computed": total_features_computed
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting enrichment overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/job-status/{symbol}")
async def get_enrichment_job_status(symbol: str):
    """
    Get enrichment job status for a specific symbol.
    
    Returns:
        {
            "symbol": "AAPL",
            "status": "completed|running|failed|pending",
            "last_enrichment": "2024-11-13T01:30:00Z",
            "records_available": 250,
            "quality_score": 0.95,
            "validation_rate": 98.5,
            "last_fetch_success": true,
            "last_compute_success": true,
            "next_scheduled_run": "2024-11-14T01:30:00Z"
        }
    """
    try:
        if not _db_service:
            raise HTTPException(status_code=503, detail="Database service not initialized")
        
        session = _db_service.SessionLocal()
        try:
            symbol = symbol.upper()
            
            # Get current enrichment status
            status_row = session.execute(text("""
                SELECT 
                    symbol, last_enriched_at, data_freshness_seconds, is_stale, consecutive_failures, last_error
                FROM enrichment_status
                WHERE symbol = :symbol
            """), {"symbol": symbol}).first()
            
            if not status_row:
                return {
                    "symbol": symbol,
                    "status": "pending",
                    "message": "No enrichment data yet",
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Get recent fetch log for this symbol
            fetch_log = session.execute(text("""
                SELECT success, source_response_time_ms, records_fetched, records_inserted
                FROM enrichment_fetch_log
                WHERE symbol = :symbol
                ORDER BY created_at DESC
                LIMIT 1
            """), {"symbol": symbol}).first()
            
            last_fetch_success = fetch_log[0] if fetch_log else None
            last_fetch_time_ms = fetch_log[1] if fetch_log else 0
            records_fetched = fetch_log[2] if fetch_log else 0
            records_inserted = fetch_log[3] if fetch_log else 0
            
            # Get recent compute log for this symbol
            compute_log = session.execute(text("""
                SELECT success, computation_time_ms, features_computed
                FROM enrichment_compute_log
                WHERE symbol = :symbol
                ORDER BY created_at DESC
                LIMIT 1
            """), {"symbol": symbol}).first()
            
            last_compute_success = compute_log[0] if compute_log else None
            last_compute_time_ms = compute_log[1] if compute_log else 0
            features_computed = compute_log[2] if compute_log else 0
            
            # Get quality metrics
            quality_metrics = session.execute(text("""
                SELECT avg_quality_score, validation_rate, data_completeness
                FROM data_quality_metrics
                WHERE symbol = :symbol
                ORDER BY metric_date DESC
                LIMIT 1
            """), {"symbol": symbol}).first()
            
            quality_score = quality_metrics[0] if quality_metrics else status_row[5]
            validation_rate = quality_metrics[1] if quality_metrics else status_row[6]
            
            return {
                "symbol": symbol,
                "status": status_row[1],  # enrichment_status.status
                "last_enrichment": status_row[2].isoformat() if status_row[2] else None,
                "last_successful_enrichment": status_row[3].isoformat() if status_row[3] else None,
                "records_available": status_row[4],
                "quality_score": round(float(quality_score or 0), 2),
                "validation_rate": round(float(validation_rate or 0), 2),
                "data_age_seconds": status_row[8],
                "last_fetch_success": last_fetch_success,
                "last_fetch_time_ms": last_fetch_time_ms,
                "records_fetched": records_fetched,
                "records_inserted": records_inserted,
                "last_compute_success": last_compute_success,
                "last_compute_time_ms": last_compute_time_ms,
                "features_computed": features_computed,
                "error_message": status_row[7],
                "next_scheduled_run": (_enrichment_scheduler.next_run_time.isoformat() if _enrichment_scheduler and _enrichment_scheduler.next_run_time else None),
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/metrics")
async def get_enrichment_dashboard_metrics():
    """
    Get enrichment pipeline metrics for dashboard display.
    
    Returns:
        {
            "total_enrichment_jobs": 1250,
            "successful": 1240,
            "failed": 10,
            "success_rate": 99.2,
            "avg_job_duration_seconds": 45,
            "total_records_enriched": 125000,
            "api_calls_made": 2500,
            "api_quota_remaining": 450,
            "last_24h_jobs": 48,
            "last_24h_success": 47
        }
    """
    try:
        if not _db_service:
            raise HTTPException(status_code=503, detail="Database service not initialized")
        
        session = _db_service.SessionLocal()
        try:
            # Get all-time enrichment metrics
            all_time_metrics = session.execute(text("""
                SELECT 
                    COUNT(*) as total_jobs,
                    SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as successful_jobs,
                    SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed_jobs,
                    AVG(source_response_time_ms) as avg_response_time_ms,
                    SUM(records_fetched) as total_records_fetched,
                    SUM(records_inserted) as total_records_inserted,
                    COUNT(DISTINCT source) as unique_sources,
                    MAX(api_quota_remaining) as latest_quota_remaining
                FROM enrichment_fetch_log
            """)).first()
            
            total_jobs = all_time_metrics[0] or 0
            successful_jobs = all_time_metrics[1] or 0
            failed_jobs = all_time_metrics[2] or 0
            avg_response_time_ms = all_time_metrics[3] or 0
            total_records_fetched = all_time_metrics[4] or 0
            total_records_inserted = all_time_metrics[5] or 0
            unique_sources = all_time_metrics[6] or 0
            api_quota_remaining = all_time_metrics[7] or 0
            
            success_rate = (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0
            avg_job_duration_seconds = avg_response_time_ms / 1000
            
            # Get last 24h metrics
            last_24h_metrics = session.execute(text("""
                SELECT 
                    COUNT(*) as jobs_24h,
                    SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as successful_24h,
                    SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed_24h
                FROM enrichment_fetch_log
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)).first()
            
            jobs_24h = last_24h_metrics[0] or 0
            successful_24h = last_24h_metrics[1] or 0
            failed_24h = last_24h_metrics[2] or 0
            
            # Get data quality aggregates
            quality_agg = session.execute(text("""
                SELECT 
                    AVG(validation_rate) as avg_validation_rate,
                    AVG(avg_quality_score) as avg_quality_score,
                    SUM(gaps_detected) as total_gaps,
                    SUM(anomalies_detected) as total_anomalies,
                    AVG(data_completeness) as avg_completeness
                FROM data_quality_metrics
                WHERE metric_date >= CURRENT_DATE - INTERVAL '7 days'
            """)).first()
            
            avg_validation_rate = quality_agg[0] or 0
            avg_quality_score = quality_agg[1] or 0
            total_gaps = quality_agg[2] or 0
            total_anomalies = quality_agg[3] or 0
            avg_completeness = quality_agg[4] or 0
            
            # Get compute pipeline aggregate
            compute_agg = session.execute(text("""
                SELECT 
                    COUNT(*) as total_computations,
                    SUM(CASE WHEN success = true THEN 1 ELSE 0 END) as successful_computations,
                    SUM(CASE WHEN success = false THEN 1 ELSE 0 END) as failed_computations,
                    AVG(computation_time_ms) as avg_computation_time_ms,
                    SUM(features_computed) as total_features_computed
                FROM enrichment_compute_log
            """)).first()
            
            total_computations = compute_agg[0] or 0
            successful_computations = compute_agg[1] or 0
            failed_computations = compute_agg[2] or 0
            avg_computation_time_ms = compute_agg[3] or 0
            total_features_computed = compute_agg[4] or 0
            
            compute_success_rate = (successful_computations / total_computations * 100) if total_computations > 0 else 0
            
            return {
                "fetch_pipeline": {
                    "total_jobs": total_jobs,
                    "successful_jobs": successful_jobs,
                    "failed_jobs": failed_jobs,
                    "success_rate": round(success_rate, 2),
                    "avg_job_duration_seconds": round(avg_job_duration_seconds, 2),
                    "total_records_fetched": total_records_fetched,
                    "total_records_inserted": total_records_inserted,
                    "unique_sources": unique_sources,
                    "api_quota_remaining": api_quota_remaining
                },
                "compute_pipeline": {
                    "total_computations": total_computations,
                    "successful_computations": successful_computations,
                    "failed_computations": failed_computations,
                    "success_rate": round(compute_success_rate, 2),
                    "avg_computation_time_ms": round(avg_computation_time_ms, 2),
                    "total_features_computed": total_features_computed
                },
                "data_quality": {
                    "avg_validation_rate": round(float(avg_validation_rate or 0), 2),
                    "avg_quality_score": round(float(avg_quality_score or 0), 2),
                    "total_gaps_detected": total_gaps,
                    "total_anomalies_detected": total_anomalies,
                    "avg_data_completeness": round(float(avg_completeness or 0), 2)
                },
                "last_24h": {
                    "total_jobs": jobs_24h,
                    "successful_jobs": successful_24h,
                    "failed_jobs": failed_24h
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enrichment metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/health")
async def get_enrichment_scheduler_health():
    """
    Get health status of enrichment scheduler and dependencies.
    
    Returns:
        {
            "scheduler": "healthy|degraded|critical",
            "database": "healthy|degraded|critical",
            "api_connectivity": "healthy|degraded|critical",
            "last_successful_run": "2024-11-13T01:30:00Z",
            "symbol_health": {"healthy": 40, "warning": 3, "error": 2},
            "recent_failures": 0
        }
    """
    try:
        if not _enrichment_scheduler or not _db_service:
            return {"status": "not_initialized"}
        
        session = _db_service.SessionLocal()
        try:
            # Check database connectivity by running a simple query
            db_health = "healthy"
            try:
                session.execute(text("SELECT 1")).first()
            except Exception:
                db_health = "critical"
            
            # Get symbol health distribution
            symbol_health = session.execute(text("""
                SELECT 
                    status,
                    COUNT(*) as count
                FROM enrichment_status
                GROUP BY status
            """)).fetchall()
            
            health_dist = {
                "healthy": 0,
                "warning": 0,
                "error": 0,
                "stale": 0
            }
            
            for row in symbol_health:
                status = row[0]
                count = row[1]
                if status in health_dist:
                    health_dist[status] = count
            
            # Check recent failures (last 24 hours)
            recent_failures = session.execute(text("""
                SELECT COUNT(*) as failed_jobs
                FROM enrichment_fetch_log
                WHERE success = false 
                AND created_at > NOW() - INTERVAL '24 hours'
            """)).first()[0] or 0
            
            # Get recent successful run info
            last_success = session.execute(text("""
                SELECT MAX(created_at)
                FROM enrichment_fetch_log
                WHERE success = true
            """)).first()[0]
            
            # Determine overall scheduler health
            scheduler_status = "healthy"
            if _enrichment_scheduler.is_running:
                if recent_failures > 10:
                    scheduler_status = "degraded"
                elif recent_failures > 50:
                    scheduler_status = "critical"
            else:
                scheduler_status = "stopped"
            
            # Determine API connectivity based on recent success
            api_health = "healthy"
            if recent_failures > 0:
                api_health = "degraded" if recent_failures <= 5 else "critical"
            
            return {
                "scheduler": scheduler_status,
                "scheduler_running": _enrichment_scheduler.is_running,
                "database": db_health,
                "api_connectivity": api_health,
                "last_successful_run": last_success.isoformat() if last_success else None,
                "last_scheduled_run": _enrichment_scheduler.last_run_time.isoformat() if _enrichment_scheduler.last_run_time else None,
                "next_scheduled_run": _enrichment_scheduler.next_run_time.isoformat() if _enrichment_scheduler.next_run_time else None,
                "symbol_health": {
                    "healthy": health_dist["healthy"],
                    "warning": health_dist["warning"],
                    "error": health_dist["error"],
                    "stale": health_dist["stale"]
                },
                "recent_failures_24h": recent_failures,
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting scheduler health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_enrichment_history(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    success: Optional[bool] = Query(None, description="Filter by success status"),
    limit: int = Query(50, ge=1, le=1000, description="Number of records to return")
):
    """
    Get enrichment job history.
    
    Returns:
        {
            "jobs": [
                {
                    "id": 123,
                    "symbol": "AAPL",
                    "source": "polygon",
                    "success": true,
                    "created_at": "2024-11-13T01:30:00Z",
                    "records_fetched": 250,
                    "records_inserted": 250,
                    "response_time_ms": 145
                }
            ],
            "total_count": 150,
            "timestamp": "2024-11-13T10:31:00Z"
        }
    """
    try:
        if not _db_service:
            raise HTTPException(status_code=503, detail="Database service not initialized")
        
        session = _db_service.SessionLocal()
        try:
            # Build query with optional filters
            query = "SELECT id, symbol, source, success, created_at, records_fetched, records_inserted, source_response_time_ms FROM enrichment_fetch_log WHERE 1=1"
            params = {}
            
            if symbol:
                query += " AND symbol = :symbol"
                params["symbol"] = symbol.upper()
            
            if success is not None:
                query += " AND success = :success"
                params["success"] = success
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM enrichment_fetch_log WHERE 1=1"
            if symbol:
                count_query += " AND symbol = :symbol"
            if success is not None:
                count_query += " AND success = :success"
            
            total_count = session.execute(text(count_query), params).first()[0] or 0
            
            # Get paginated results
            query += " ORDER BY created_at DESC LIMIT :limit"
            params["limit"] = limit
            
            rows = session.execute(text(query), params).fetchall()
            
            jobs = []
            for row in rows:
                jobs.append({
                    "id": row[0],
                    "symbol": row[1],
                    "source": row[2],
                    "success": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                    "records_fetched": row[5],
                    "records_inserted": row[6],
                    "response_time_ms": row[7]
                })
            
            return {
                "jobs": jobs,
                "total_count": total_count,
                "limit": limit,
                "filters": {
                    "symbol": symbol,
                    "success": success
                },
                "timestamp": datetime.utcnow().isoformat()
            }
        finally:
            session.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting enrichment history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger")
async def trigger_enrichment_manually(
    symbol: Optional[str] = Query(None, description="Symbol to enrich"),
    asset_class: str = Query("stock", description="Asset class"),
    timeframes: List[str] = Query(["1d"], description="Timeframes to enrich (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)")
):
    """
    Manually trigger enrichment for symbols.
    
    Returns:
        {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "symbols": ["AAPL"],
            "status": "queued",
            "estimated_duration_seconds": 300,
            "timestamp": "2024-11-13T10:31:00Z"
        }
    """
    try:
        if not _enrichment_scheduler:
            raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
        
        job_id = str(uuid.uuid4())
        symbols = [symbol] if symbol else []
        
        logger.info(f"Enrichment triggered manually: job_id={job_id}, symbols={symbols}, timeframes={timeframes}")
        
        # Trigger enrichment asynchronously and store job ID
        if symbols:
            try:
                # Call trigger_enrichment which handles async execution
                job_id = await _enrichment_scheduler.trigger_enrichment(
                    symbols=symbols,
                    asset_class=asset_class,
                    timeframes=timeframes
                )
            except Exception as e:
                logger.error(f"Error triggering enrichment job: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to trigger enrichment: {str(e)}")
        
        return {
            "job_id": job_id,
            "symbols": symbols,
            "status": "queued",
            "estimated_duration_seconds": 300,
            "asset_class": asset_class,
            "timeframes": timeframes,
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering enrichment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pause")
async def pause_enrichment_scheduler():
    """
    Pause the enrichment scheduler.
    
    Returns:
        {
            "status": "paused",
            "paused_at": "2024-11-13T10:31:00Z"
        }
    """
    try:
        if not _enrichment_scheduler:
            raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
        
        _enrichment_scheduler.pause()
        
        return {
            "status": "paused",
            "paused_at": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing enrichment scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/resume")
async def resume_enrichment_scheduler():
    """
    Resume the enrichment scheduler.
    
    Returns:
        {
            "status": "running",
            "resumed_at": "2024-11-13T10:31:00Z",
            "next_run": "2024-11-14T01:30:00Z"
        }
    """
    try:
        if not _enrichment_scheduler:
            raise HTTPException(status_code=503, detail="Enrichment scheduler not initialized")
        
        _enrichment_scheduler.resume()
        
        return {
            "status": "running",
            "resumed_at": datetime.utcnow().isoformat(),
            "next_run": _enrichment_scheduler.next_run_time.isoformat() if _enrichment_scheduler.next_run_time else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming enrichment scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))
