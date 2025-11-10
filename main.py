"""FastAPI application for Market Data Warehouse"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import config
from src.scheduler import AutoBackfillScheduler, get_last_backfill_result, get_last_backfill_time
from src.services.database_service import DatabaseService
from src.models import (
    HealthResponse, StatusResponse, AddSymbolRequest, TrackedSymbol,
    APIKeyListResponse, APIKeyCreateResponse, AuditLogEntry, APIKeyAuditResponse,
    CreateAPIKeyRequest, UpdateAPIKeyRequest
)
from src.services.structured_logging import setup_structured_logging, StructuredLogger, get_trace_id
from src.services.metrics import init_metrics, get_metrics_collector
from src.services.alerting import init_alert_manager, get_alert_manager, AlertType, AlertSeverity, LogAlertHandler, EmailAlertHandler
from src.middleware.observability_middleware import ObservabilityMiddleware
from src.middleware.auth_middleware import APIKeyAuthMiddleware
from src.services.caching import init_query_cache, get_query_cache
from src.services.performance_monitor import init_performance_monitor, get_performance_monitor
from src.services.auth import init_auth_service, get_auth_service
from src.services.symbol_manager import init_symbol_manager, get_symbol_manager
from src.services.migration_service import init_migration_service, get_migration_service

# Setup structured logging
setup_structured_logging(config.log_level)
logger = StructuredLogger(__name__)

# Log configuration summary
config.log_summary()

# Initialize services
db = DatabaseService(config.database_url)
scheduler = AutoBackfillScheduler(
    polygon_api_key=config.polygon_api_key,
    database_url=config.database_url,
    schedule_hour=config.backfill_schedule_hour,
    schedule_minute=config.backfill_schedule_minute
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.
    Handles startup and shutdown.
    """
    # Startup
    logger.info("Starting Market Data API")
    logger.info("Observability initialized", extra={
        "structured_logging": True,
        "metrics_tracking": True,
        "alerting": True,
    })
    logger.info("Scheduler configured", extra={
        "schedule": f"{config.backfill_schedule_hour:02d}:{config.backfill_schedule_minute:02d} UTC daily"
    })
    
    # Run database migrations
    logger.info("Running database migrations...")
    try:
        migration_service = init_migration_service(config.database_url)
        if not await migration_service.run_migrations():
            logger.error("Database migrations failed")
            raise RuntimeError("Database migrations failed")
        logger.info("Database migrations completed successfully")
    except Exception as e:
        logger.error("Migration initialization failed", extra={"error": str(e)})
        raise RuntimeError(f"Failed to initialize database: {str(e)}")
    
    # Verify schema
    logger.info("Verifying database schema...")
    try:
        schema_status = await migration_service.verify_schema()
        all_valid = all(schema_status.values())
        if not all_valid:
            logger.error("Schema verification failed", extra={"status": schema_status})
            raise RuntimeError("Database schema verification failed")
        logger.info("Schema verification passed")
    except Exception as e:
        logger.error("Schema verification failed", extra={"error": str(e)})
        raise RuntimeError(f"Schema verification failed: {str(e)}")
    
    # Test database connection
    try:
        metrics = db.get_status_metrics()
        logger.info("Database connected", extra={
            "symbols": metrics.get("symbols_available", 0),
            "total_records": metrics.get("total_records", 0),
        })
    except Exception as e:
        logger.warning("Could not connect to database", extra={"error": str(e)})
    
    # Start scheduler
    try:
        scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error("Failed to start scheduler", extra={"error": str(e)})
    
    logger.info("App startup complete")
    yield
    
    # Shutdown
    logger.info("Shutting down Market Data API")
    if scheduler.scheduler.running:
        scheduler.stop()
    logger.info("App shutdown complete")


app = FastAPI(
    title="Market Data API",
    description="Validated US stock OHLCV warehouse. Single source of truth for research and analysis.",
    version="1.0.0",
    lifespan=lifespan
)

# Initialize observability services
init_metrics(retention_hours=24)
init_query_cache(max_size=1000, default_ttl=300)
init_performance_monitor(window_hours=24)
alert_manager = init_alert_manager()

# Initialize auth and symbol management services
init_auth_service(config.database_url)
init_symbol_manager(config.database_url)

# Add log alert handler
alert_manager.add_handler(LogAlertHandler(logger))

# Add email alert handler if configured
if os.getenv("ALERT_EMAIL_ENABLED", "false").lower() == "true":
    try:
        email_handler = EmailAlertHandler(
            smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            sender_email=os.getenv("ALERT_FROM_EMAIL", ""),
            sender_password=os.getenv("ALERT_FROM_PASSWORD", ""),
        )
        # Add recipients from comma-separated env var
        recipients = os.getenv("ALERT_TO_EMAILS", "").split(",")
        for email in recipients:
            if email.strip():
                email_handler.add_recipient(email.strip())
        if email_handler.recipients:
            alert_manager.add_handler(email_handler)
            logger.info("Email alerts enabled")
    except Exception as e:
        logger.warning("Failed to configure email alerts", extra={"error": str(e)})

# Add middleware
app.add_middleware(APIKeyAuthMiddleware)
app.add_middleware(ObservabilityMiddleware)

# Mount dashboard (if it exists)
dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard")
if os.path.isdir(dashboard_path):
    app.mount("/dashboard", StaticFiles(directory=dashboard_path, html=True), name="dashboard")
    logger.info("Dashboard mounted at /dashboard")


@app.get("/health", response_model=HealthResponse)
async def health():
    """System health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "scheduler_running": scheduler.scheduler.running
    }


@app.get("/api/v1/status")
async def get_status():
    """
    System monitoring endpoint.
    
    Returns:
    - Database metrics (symbols, records, validation rate)
    - Data quality metrics (gaps detected, anomalies)
    - Scheduler status
    """
    try:
        metrics = db.get_status_metrics()
        
        return {
            "api_version": "1.0.0",
            "status": "healthy",
            "database": {
                "symbols_available": metrics.get("symbols_available", 0),
                "latest_data": metrics.get("latest_data"),
                "total_records": metrics.get("total_records", 0),
                "validated_records": metrics.get("validated_records", 0),
                "validation_rate_pct": metrics.get("validation_rate_pct", 0)
            },
            "data_quality": {
                "records_with_gaps_flagged": metrics.get("records_with_gaps_flagged", 0),
                "scheduler_status": "running" if scheduler.scheduler.running else "stopped",
                "last_backfill": "check backfill_history table for details"
            }
        }
    
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@app.get("/api/v1/historical/{symbol}")
async def get_historical_data(
    symbol: str,
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
    validated_only: bool = Query(True, description="Filter to validated candles only"),
    min_quality: float = Query(0.85, ge=0, le=1, description="Minimum quality score (0.0-1.0)")
):
    """
    Fetch historical OHLCV data for a symbol.
    
    Example:
    - GET /api/v1/historical/AAPL?start=2022-01-01&end=2023-12-31
    - GET /api/v1/historical/MSFT?start=2023-01-01&end=2023-12-31&validated_only=false
    
    Parameters:
    - symbol: Stock ticker (e.g., AAPL, MSFT, SPY)
    - start: Start date in YYYY-MM-DD format
    - end: End date in YYYY-MM-DD format
    - validated_only: If true, only return candles with quality_score >= min_quality
    - min_quality: Minimum quality score filter (0.0-1.0)
    
    Returns:
    - Array of OHLCV candles with validation metadata
    """
    try:
        # Validate date format
        try:
            datetime.strptime(start, "%Y-%m-%d")
            datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
        
        # Fetch data
        data = db.get_historical_data(
            symbol=symbol.upper(),
            start=start,
            end=end,
            validated_only=validated_only,
            min_quality=min_quality
        )
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol.upper()} ({start} to {end})"
            )
        
        return {
            "symbol": symbol.upper(),
            "start_date": start,
            "end_date": end,
            "count": len(data),
            "data": data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/api/v1/symbols")
async def list_symbols():
    """
    List all symbols currently in the database.
    
    Returns:
    - Array of distinct symbols with basic stats (record count, date range)
    """
    try:
        metrics = db.get_status_metrics()
        
        return {
            "symbols_available": metrics.get("symbols_available", 0),
            "latest_data": metrics.get("latest_data"),
            "note": "For detailed symbol stats, query /api/v1/status"
        }
    
    except Exception as e:
        logger.error(f"Error listing symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/metrics")
async def get_metrics():
    """
    Monitoring endpoint - scheduler health and system metrics.
    
    Returns:
    - Scheduler status (running/stopped)
    - Last backfill time and results
    - Database metrics
    - System health summary
    """
    try:
        backfill_result = get_last_backfill_result()
        backfill_time = get_last_backfill_time()
        metrics = db.get_status_metrics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "scheduler": {
                "running": scheduler.scheduler.running,
                "schedule": f"{config.backfill_schedule_hour:02d}:{config.backfill_schedule_minute:02d} UTC daily"
            },
            "last_backfill": {
                "time": backfill_time.isoformat() if backfill_time else None,
                "successful_symbols": backfill_result.get("success") if backfill_result else None,
                "failed_symbols": backfill_result.get("failed") if backfill_result else None,
                "total_records_imported": backfill_result.get("total_records") if backfill_result else None
            },
            "database": {
                "symbols_available": metrics.get("symbols_available", 0),
                "total_records": metrics.get("total_records", 0),
                "validated_records": metrics.get("validated_records", 0),
                "validation_rate_pct": metrics.get("validation_rate_pct", 0),
                "latest_data": metrics.get("latest_data")
            },
            "health": {
                "api": "healthy" if scheduler.scheduler.running else "degraded",
                "database": "healthy" if metrics.get("total_records", 0) > 0 else "no_data"
            }
        }
    
    except Exception as e:
        logger.error("Metrics endpoint error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Metrics query failed: {str(e)}")


@app.get("/api/v1/observability/metrics")
async def get_observability_metrics():
    """
    Get request/error metrics and system health.
    
    Returns:
    - Request count and error rate
    - Average response times
    - Per-endpoint statistics
    - Error summary by type
    """
    try:
        metrics = get_metrics_collector()
        snapshot = metrics.get_snapshot()
        
        return {
            "timestamp": snapshot.timestamp,
            "health_status": snapshot.health_status,
            "summary": {
                "total_requests": snapshot.request_count,
                "total_errors": snapshot.error_count,
                "error_rate_pct": snapshot.error_rate_pct,
                "avg_response_time_ms": snapshot.avg_response_time_ms,
                "requests_last_hour": snapshot.requests_last_hour,
                "errors_last_hour": snapshot.errors_last_hour,
            },
            "endpoints": metrics.get_endpoint_stats(),
            "error_summary": metrics.get_error_summary(),
        }
    except Exception as e:
        logger.error("Observability metrics error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/observability/alerts")
async def get_alerts(limit: int = 100):
    """
    Get recent alerts.
    
    Parameters:
    - limit: Maximum number of alerts to return (default: 100, max: 1000)
    """
    try:
        if limit < 1 or limit > 1000:
            limit = 100
        
        alert_manager = get_alert_manager()
        alerts = alert_manager.get_alert_history(limit=limit)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "count": len(alerts),
            "alerts": alerts,
        }
    except Exception as e:
        logger.error("Alerts endpoint error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/performance/cache")
async def get_cache_stats():
    """
    Get query cache statistics.
    
    Returns:
    - Cache size and configuration
    - Hit/miss rates
    - Effectiveness metrics
    """
    try:
        cache = get_query_cache()
        stats = cache.stats()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cache": stats
        }
    except Exception as e:
        logger.error("Cache stats error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/performance/queries")
async def get_query_performance(query_type: str = None):
    """
    Get query performance statistics.
    
    Parameters:
    - query_type: Filter to specific query type (optional)
    
    Returns:
    - Min/max/mean/median/p95/p99 response times
    - Success rates
    - Error information
    """
    try:
        monitor = get_performance_monitor()
        stats = await monitor.get_stats(query_type=query_type)
        bottlenecks = await monitor.get_bottlenecks()
        query_types = await monitor.get_query_types()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "stats": stats,
            "bottlenecks": bottlenecks[:5],  # Top 5 bottlenecks
            "query_types": query_types
        }
    except Exception as e:
        logger.error("Query performance error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/performance/summary")
async def get_performance_summary():
    """
    Get comprehensive performance summary.
    
    Returns:
    - Cache effectiveness
    - Query performance overview
    - Bottlenecks
    - Recommendations
    """
    try:
        cache = get_query_cache()
        monitor = get_performance_monitor()
        
        cache_stats = cache.stats()
        perf_summary = await monitor.get_summary()
        bottlenecks = await monitor.get_bottlenecks()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "cache": cache_stats,
            "performance": perf_summary,
            "bottlenecks": bottlenecks[:5],
            "recommendations": generate_performance_recommendations(
                cache_stats, perf_summary, bottlenecks
            )
        }
    except Exception as e:
        logger.error("Performance summary error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ADMIN ENDPOINTS ====================
# These require X-API-Key header for authentication


@app.post("/api/v1/admin/symbols", response_model=TrackedSymbol)
async def add_symbol(request: AddSymbolRequest):
    """
    Add a new symbol to track.
    
    Requires X-API-Key header.
    
    Example:
        POST /api/v1/admin/symbols
        Headers: X-API-Key: xxx
        Body: {"symbol": "BTC", "asset_class": "crypto"}
    """
    try:
        symbol_manager = get_symbol_manager()
        result = await symbol_manager.add_symbol(request.symbol, request.asset_class)
        
        logger.info("Symbol added via API", extra={
            "symbol": request.symbol,
            "asset_class": request.asset_class
        })
        
        return result
    
    except ValueError as e:
        logger.warning("Symbol add failed", extra={"error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Symbol add error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/admin/symbols", response_model=list)
async def list_symbols(active_only: bool = True, include_stats: bool = False):
    """
    List all tracked symbols with optional statistics.
    
    Requires X-API-Key header.
    
    Parameters:
    - active_only: If true, only return active symbols (default: true)
    - include_stats: If true, include data statistics for each symbol (default: false)
    
    Example:
        GET /api/v1/admin/symbols?active_only=false
        GET /api/v1/admin/symbols?include_stats=true
        Headers: X-API-Key: xxx
    """
    try:
        symbol_manager = get_symbol_manager()
        symbols = await symbol_manager.get_all_symbols(active_only=active_only)
        
        # Add stats if requested
        if include_stats:
            for symbol in symbols:
                stats = db.get_symbol_stats(symbol["symbol"])
                symbol["stats"] = stats
        
        logger.info("Symbols listed via API", extra={
            "count": len(symbols),
            "active_only": active_only,
            "include_stats": include_stats
        })
        
        return symbols
    
    except Exception as e:
        logger.error("Symbol list error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/admin/symbols/{symbol}")
async def get_symbol_info(symbol: str):
    """
    Get info about a specific symbol with data statistics.
    
    Requires X-API-Key header.
    
    Returns symbol metadata plus stats:
    - record_count: Number of OHLCV records in database
    - date_range: Start and end dates of available data
    - validation_rate: Percentage of validated records (0.0-1.0)
    - gaps_detected: Number of trading days with gaps
    """
    try:
        symbol_manager = get_symbol_manager()
        result = await symbol_manager.get_symbol(symbol)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
        
        # Add statistics
        stats = db.get_symbol_stats(symbol)
        result["stats"] = stats
        
        logger.info("Symbol info retrieved via API", extra={
            "symbol": symbol,
            "record_count": stats.get("record_count", 0)
        })
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Symbol info error for {symbol}", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/admin/symbols/{symbol}")
async def update_symbol(symbol: str, active: bool = None):
    """
    Update a symbol's status.
    
    Requires X-API-Key header.
    
    Parameters:
    - active: Set to true/false to activate/deactivate
    
    Example:
        PUT /api/v1/admin/symbols/BTC?active=false
        Headers: X-API-Key: xxx
    """
    try:
        symbol_manager = get_symbol_manager()
        
        # Verify symbol exists
        existing = await symbol_manager.get_symbol(symbol)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
        
        # Update
        await symbol_manager.update_symbol_status(symbol, active=active)
        
        # Return updated info
        updated = await symbol_manager.get_symbol(symbol)
        
        logger.info("Symbol updated via API", extra={
            "symbol": symbol,
            "active": active
        })
        
        return updated
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Symbol update error for {symbol}", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/admin/symbols/{symbol}")
async def deactivate_symbol(symbol: str):
    """
    Deactivate (remove) a symbol from tracking.
    
    Requires X-API-Key header.
    
    Note: Historical data is NOT deleted, only tracking is stopped.
    
    Example:
        DELETE /api/v1/admin/symbols/OLDCOIN
        Headers: X-API-Key: xxx
    """
    try:
        symbol_manager = get_symbol_manager()
        
        # Verify symbol exists
        existing = await symbol_manager.get_symbol(symbol)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
        
        # Deactivate
        success = await symbol_manager.remove_symbol(symbol)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to deactivate symbol")
        
        logger.info("Symbol deactivated via API", extra={"symbol": symbol})
        
        return {
            "status": "success",
            "message": f"Symbol {symbol} deactivated",
            "data_retained": True
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Symbol deactivation error for {symbol}", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


# ==================== API KEY MANAGEMENT ENDPOINTS ====================
# These require X-API-Key header for authentication


@app.post("/api/v1/admin/api-keys", response_model=APIKeyCreateResponse)
async def create_api_key(request: CreateAPIKeyRequest):
    """
    Generate a new API key.
    
    Requires X-API-Key header (admin key).
    
    The returned api_key is shown only once. Save it securely.
    
    Example:
        POST /api/v1/admin/api-keys
        Headers: X-API-Key: xxx
        Body: {"name": "Production Key"}
    
    Response includes the raw api_key which will not be shown again.
    """
    try:
        auth_service = get_auth_service()
        result = await auth_service.create_api_key(request.name)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create API key")
        
        logger.info("API key created via admin endpoint", extra={
            "key_name": request.name,
            "key_id": result['id']
        })
        
        return APIKeyCreateResponse(**result)
    
    except Exception as e:
        logger.error("API key creation error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/admin/api-keys", response_model=list[APIKeyListResponse])
async def list_api_keys(active_only: bool = False):
    """
    List all API keys with metadata.
    
    Requires X-API-Key header (admin key).
    
    Parameters:
    - active_only: If true, only return active keys (default: false)
    
    Note: Raw key_hash is never returned. Use key_preview for reference.
    
    Example:
        GET /api/v1/admin/api-keys
        Headers: X-API-Key: xxx
    """
    try:
        auth_service = get_auth_service()
        keys = await auth_service.list_api_keys(active_only=active_only)
        
        logger.info("API keys listed via admin endpoint", extra={
            "count": len(keys),
            "active_only": active_only
        })
        
        return [APIKeyListResponse(**key) for key in keys]
    
    except Exception as e:
        logger.error("API key list error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/admin/api-keys/{key_id}/audit")
async def get_api_key_audit(key_id: int, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    """
    Get audit log entries for a specific API key.
    
    Requires X-API-Key header (admin key).
    
    Parameters:
    - key_id: ID of the API key
    - limit: Maximum number of results (default: 100, max: 1000)
    - offset: Number of results to skip (default: 0)
    
    Example:
        GET /api/v1/admin/api-keys/1/audit?limit=50&offset=0
        Headers: X-API-Key: xxx
    """
    try:
        auth_service = get_auth_service()
        entries = await auth_service.get_audit_log(key_id, limit=limit, offset=offset)
        
        logger.info("API key audit log accessed", extra={
            "key_id": key_id,
            "limit": limit,
            "offset": offset
        })
        
        return APIKeyAuditResponse(
            key_id=key_id,
            entries=[AuditLogEntry(**entry) for entry in entries],
            total=len(entries),
            limit=limit,
            offset=offset
        )
    
    except Exception as e:
        logger.error("Audit log fetch error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/v1/admin/api-keys/{key_id}")
async def update_api_key(key_id: int, request: UpdateAPIKeyRequest):
    """
    Update an API key's active status.
    
    Requires X-API-Key header (admin key).
    
    Parameters:
    - key_id: ID of the API key
    - active: Boolean to activate (true) or revoke (false)
    
    Example:
        PUT /api/v1/admin/api-keys/1
        Headers: X-API-Key: xxx
        Body: {"active": false}
    """
    try:
        auth_service = get_auth_service()
        
        if request.active:
            success = await auth_service.restore_key(key_id)
            action = "restored"
        else:
            success = await auth_service.revoke_key(key_id)
            action = "revoked"
        
        if not success:
            raise HTTPException(status_code=500, detail=f"Failed to update API key")
        
        logger.info(f"API key {action} via admin endpoint", extra={
            "key_id": key_id,
            "active": request.active
        })
        
        return {
            "status": "success",
            "message": f"API key {action}",
            "key_id": key_id,
            "active": request.active
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("API key update error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/admin/api-keys/{key_id}")
async def delete_api_key(key_id: int):
    """
    Permanently delete an API key and its audit logs.
    
    Requires X-API-Key header (admin key).
    
    Warning: This is permanent and cannot be undone.
    
    Parameters:
    - key_id: ID of the API key to delete
    
    Example:
        DELETE /api/v1/admin/api-keys/1
        Headers: X-API-Key: xxx
    """
    try:
        auth_service = get_auth_service()
        success = await auth_service.delete_key(key_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete API key")
        
        logger.info("API key deleted via admin endpoint", extra={"key_id": key_id})
        
        return {
            "status": "success",
            "message": "API key permanently deleted",
            "key_id": key_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("API key delete error", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))


def generate_performance_recommendations(cache_stats: Dict, perf_stats: Dict, bottlenecks: List) -> List[str]:
    """Generate performance improvement recommendations"""
    recommendations = []
    
    if cache_stats.get("hit_rate_pct", 0) < 50:
        recommendations.append("Cache hit rate is low - consider increasing TTL or adjusting query patterns")
    
    if perf_stats.get("error_rate_pct", 0) > 5:
        recommendations.append("Error rate exceeds 5% - investigate failing queries")
    
    if perf_stats.get("p99_duration_ms", 0) > 500:
        recommendations.append("P99 response time exceeds 500ms - consider database optimization")
    
    if bottlenecks:
        top_bottleneck = bottlenecks[0]
        recommendations.append(
            f"Slowest query type: {top_bottleneck.get('query_type')} "
            f"({top_bottleneck.get('avg_slow_ms')}ms avg)"
        )
    
    if not recommendations:
        recommendations.append("System is performing well - no immediate optimizations needed")
    
    return recommendations


@app.on_event("startup")
async def startup_event():
    """Additional startup tasks if needed"""
    logger.info("Additional startup tasks completed")


@app.on_event("shutdown")
async def shutdown_event():
    """Additional shutdown tasks if needed"""
    logger.info("Additional shutdown tasks completed")


# Root endpoint
@app.get("/")
async def root():
    """API documentation and status"""
    return {
        "name": "Market Data API",
        "version": "1.0.0",
        "description": "Validated OHLCV warehouse (stocks & crypto)",
        "dashboard": "/dashboard",
        "docs": "/docs",
        "authentication": "X-API-Key header required for /api/v1/admin/* endpoints",
        "endpoints": {
            "health": "/health",
            "status": "/api/v1/status",
            "historical": "/api/v1/historical/{symbol}",
            "symbols": "/api/v1/symbols",
            "metrics": "/api/v1/metrics",
            "observability_metrics": "/api/v1/observability/metrics",
            "observability_alerts": "/api/v1/observability/alerts",
            "performance_cache": "/api/v1/performance/cache",
            "performance_queries": "/api/v1/performance/queries",
            "performance_summary": "/api/v1/performance/summary"
        },
        "admin_endpoints": {
            "add_symbol": "POST /api/v1/admin/symbols",
            "list_symbols": "GET /api/v1/admin/symbols",
            "get_symbol": "GET /api/v1/admin/symbols/{symbol}",
            "update_symbol": "PUT /api/v1/admin/symbols/{symbol}",
            "remove_symbol": "DELETE /api/v1/admin/symbols/{symbol}"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=config.api_host,
        port=config.api_port,
        workers=config.api_workers,
        log_level=config.log_level.lower()
    )
