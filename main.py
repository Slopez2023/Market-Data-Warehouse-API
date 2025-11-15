"""FastAPI application for Market Data Warehouse"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Dict, List
import uuid

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Ensure .env variables are loaded when running locally
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional at runtime; uvicorn also auto-loads .env when available
    pass

from src.config import config, ALLOWED_TIMEFRAMES
from src.scheduler import AutoBackfillScheduler, get_last_backfill_result, get_last_backfill_time
from src.services.database_service import DatabaseService
from src.services.enrichment_scheduler import EnrichmentScheduler
from src.routes.enrichment_ui import init_enrichment_ui, router as enrichment_ui_router
from src.routes.asset_data import router as asset_router
from src.services.resilience_manager import init_resilience_manager
from src.models import (
    HealthResponse, StatusResponse, AddSymbolRequest, TrackedSymbol,
    APIKeyListResponse, APIKeyCreateResponse, AuditLogEntry, APIKeyAuditResponse,
    CreateAPIKeyRequest, UpdateAPIKeyRequest, UpdateSymbolTimeframesRequest
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
from src.services.backfill_worker import init_backfill_worker
from src.models import BackfillJobStatus, BackfillJobResponse

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

# Phase 1g: Enrichment Scheduler
enrichment_scheduler = None

# Phase 1i: Resilience Manager
resilience_manager = None


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
    
    # Phase 1g: Initialize Enrichment Scheduler
    global enrichment_scheduler, resilience_manager
    try:
        enrichment_scheduler = EnrichmentScheduler(
            db_service=db,
            config=config,
            enrichment_hour=getattr(config, 'enrichment_schedule_hour', 1),
            enrichment_minute=getattr(config, 'enrichment_schedule_minute', 30),
            max_concurrent_symbols=5,
            max_retries=3,
            enable_daily_enrichment=True
        )
        enrichment_scheduler.start()
        logger.info("Enrichment scheduler started")
        
        # Initialize UI endpoints with database service
        init_enrichment_ui(enrichment_scheduler, db)
        
    except Exception as e:
        logger.error("Failed to start enrichment scheduler", extra={"error": str(e)})
    
    # Phase 1i: Initialize Resilience Manager
    try:
        resilience_manager = init_resilience_manager()
        
        # Register circuit breaker for API calls
        resilience_manager.register_circuit_breaker(
            name="polygon_api",
            failure_threshold=0.5,
            recovery_timeout=60
        )
        
        # Register rate limiter
        resilience_manager.register_rate_limiter(
            name="enrichment_api",
            rate=100,
            interval=60,
            burst=150
        )
        
        logger.info("Resilience manager initialized")
    except Exception as e:
        logger.error("Failed to initialize resilience manager", extra={"error": str(e)})
    
    # Initialize Backfill Worker
    try:
        init_backfill_worker(db, scheduler.polygon_api)
        logger.info("Backfill worker initialized")
    except Exception as e:
        logger.error("Failed to initialize backfill worker", extra={"error": str(e)})
    
    logger.info("App startup complete")
    yield
    
    # Shutdown
    logger.info("Shutting down Market Data API")
    if scheduler.scheduler.running:
        scheduler.stop()
    
    if enrichment_scheduler and enrichment_scheduler.is_running:
        enrichment_scheduler.stop()
    
    logger.info("App shutdown complete")


app = FastAPI(
    title="Market Data API",
    description="Validated US stock OHLCV warehouse. Single source of truth for research and analysis.",
    version="1.0.0",
    lifespan=lifespan
)

# Initialize observability services BEFORE mounting dashboard
# This ensures FastAPI docs routes (/docs, /openapi.json) are registered first
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

# Add middleware (CORS must be added last to be processed first)
app.add_middleware(APIKeyAuthMiddleware)
app.add_middleware(ObservabilityMiddleware)

# Add CORS middleware last (processes requests first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 1h: Include enrichment UI router
app.include_router(enrichment_ui_router)

# Asset data routes
app.include_router(asset_router)

# Serve dashboard files explicitly (not as catch-all)
# This prevents StaticFiles from intercepting /docs and other API routes
dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard")

@app.api_route("/dashboard", methods=["GET", "HEAD"])
async def redirect_dashboard():
    """Redirect /dashboard to /dashboard/"""
    return RedirectResponse(url="/dashboard/", status_code=307)

@app.api_route("/dashboard/", methods=["GET", "HEAD"])
@app.api_route("/dashboard/index.html", methods=["GET", "HEAD"])
async def serve_dashboard_index():
    """Serve dashboard index.html"""
    index_path = os.path.join(dashboard_path, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Dashboard not found")

@app.api_route("/dashboard/{filename}", methods=["GET", "HEAD"])
async def serve_dashboard_file(filename: str):
    """Serve dashboard static files (CSS, JS, etc)"""
    # Prevent directory traversal
    if ".." in filename or filename.startswith("/"):
        raise HTTPException(status_code=403, detail="Access denied")
    
    file_path = os.path.join(dashboard_path, filename)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail=f"File not found: {filename}")

logger.info("Dashboard routes registered")


@app.get("/")
async def root():
    """Root endpoint - serves dashboard info"""
    # Check if Accept header prefers HTML (browser request)
    from fastapi import Request
    # Return JSON by default, browsers should navigate to /dashboard
    return JSONResponse({
        "name": "Market Data API",
        "version": "1.0.0",
        "description": "Validated OHLCV warehouse (stocks & crypto)",
        "dashboard": "/dashboard/index.html",
        "dashboard_direct": "/dashboard/",
        "docs": "/docs",
        "authentication": "X-API-Key header required for /api/v1/admin/* endpoints",
        "endpoints": {
            "health": "/health",
            "status": "/api/v1/status",
            "historical": "/api/v1/historical/{symbol}",
            "symbols": "/api/v1/symbols",
            "metrics": "/api/v1/metrics",
        }
    })


@app.options("/{full_path:path}")
async def preflight(full_path: str):
    """Handle CORS preflight requests"""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
        }
    )


@app.get("/health")
async def health():
    """System health check"""
    return JSONResponse(
        content={
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "scheduler_running": scheduler.scheduler.running
        },
        headers={
            "Access-Control-Allow-Origin": "*",
        }
    )


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
        
        return JSONResponse(
            content={
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
            },
            headers={
                "Access-Control-Allow-Origin": "*",
            }
        )
    
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


def validate_timeframe(timeframe: str) -> str:
    """
    Validate timeframe against allowed list.
    
    Args:
        timeframe: Timeframe code to validate
        
    Returns:
        timeframe: Valid timeframe (uppercase)
        
    Raises:
        ValueError: If timeframe is invalid
    """
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise ValueError(
            f"Invalid timeframe: {timeframe}. "
            f"Allowed: {', '.join(ALLOWED_TIMEFRAMES)}"
        )
    return timeframe


@app.get("/api/v1/historical/{symbol}")
async def get_historical_data(
    symbol: str,
    timeframe: str = Query("1d", description="Timeframe: 5m, 15m, 30m, 1h, 4h, 1d, 1w"),
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
    validated_only: bool = Query(True, description="Filter to validated candles only"),
    min_quality: float = Query(0.85, ge=0, le=1, description="Minimum quality score (0.0-1.0)")
):
    """
    Fetch historical OHLCV data for a symbol.
    
    Example:
    - GET /api/v1/historical/AAPL?timeframe=1d&start=2022-01-01&end=2023-12-31
    - GET /api/v1/historical/MSFT?timeframe=1h&start=2023-01-01&end=2023-12-31&validated_only=false
    - GET /api/v1/historical/BTC?timeframe=4h&start=2023-11-01&end=2023-11-30
    
    Parameters:
    - symbol: Stock ticker (e.g., AAPL, MSFT, SPY)
    - timeframe: Candle timeframe (5m, 15m, 30m, 1h, 4h, 1d, 1w) - default: 1d
    - start: Start date in YYYY-MM-DD format
    - end: End date in YYYY-MM-DD format
    - validated_only: If true, only return candles with quality_score >= min_quality
    - min_quality: Minimum quality score filter (0.0-1.0)
    
    Returns:
    - Array of OHLCV candles with validation metadata
    """
    try:
        # Validate timeframe
        try:
            timeframe = validate_timeframe(timeframe)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Validate date format
        try:
            datetime.strptime(start, "%Y-%m-%d")
            datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
        
        # Fetch data (filtered by timeframe)
        data = db.get_historical_data(
            symbol=symbol.upper(),
            timeframe=timeframe,
            start=start,
            end=end,
            validated_only=validated_only,
            min_quality=min_quality
        )
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol.upper()} timeframe={timeframe} ({start} to {end})"
            )
        
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
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


def calculate_symbol_status(symbol: dict) -> str:
    """
    Determine symbol health status based on validation rate and data age.
    
    Args:
        symbol: Dict with 'validation_rate', 'latest_data', 'data_age_hours'
    
    Returns:
        "healthy" | "warning" | "stale"
    """
    validation_rate = symbol.get("validation_rate", 0)
    data_age_hours = symbol.get("data_age_hours", float('inf'))
    
    # Stale: old data OR very low validation
    if data_age_hours > 72 or validation_rate < 85:
        return "stale"
    
    # Warning: moderately old OR moderate validation issues
    if data_age_hours > 24 or validation_rate < 95:
        return "warning"
    
    # Healthy: recent data AND good validation
    return "healthy"


@app.get("/api/v1/symbols/detailed")
async def get_symbols_detailed():
    """
    Get detailed statistics for all symbols in the database.
    
    Returns array of symbols with:
    - symbol: Ticker name
    - records: Total OHLCV records
    - validation_rate: Percentage of validated records (0-100)
    - latest_data: Most recent data timestamp
    - status: Health status (healthy/warning/stale)
    - data_age_hours: Hours since last update
    """
    try:
        # Get all symbols from database
        metrics = db.get_status_metrics()
        symbol_count = metrics.get("symbols_available", 0)
        
        if symbol_count == 0:
            return {
                "count": 0,
                "symbols": [],
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Query database for per-symbol stats
        symbols_data = db.get_all_symbols_detailed()
        
        # Enrich with status calculation
        for symbol in symbols_data:
            symbol["status"] = calculate_symbol_status(symbol)
        
        # Sort by symbol name
        symbols_data = sorted(symbols_data, key=lambda x: x["symbol"])
        
        return {
            "count": len(symbols_data),
            "timestamp": datetime.utcnow().isoformat(),
            "symbols": symbols_data
        }
    
    except Exception as e:
        logger.error("Detailed symbols query error", extra={"error": str(e)})
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
    - symbol: Ticker symbol
    - asset_class: Type of asset (stock, crypto, etf, etc.)
    - active: Whether symbol is actively being tracked
    - timeframes: List of configured timeframes being fetched
    - record_count: Number of OHLCV records in database
    - date_range: Start and end dates of available data
    - validation_rate: Percentage of validated records (0.0-1.0)
    - gaps_detected: Number of trading days with gaps
    
    Example:
        GET /api/v1/admin/symbols/AAPL
        Headers: X-API-Key: xxx
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
            "timeframes": result.get("timeframes", []),
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


@app.put("/api/v1/admin/symbols/{symbol}/timeframes", response_model=TrackedSymbol)
async def update_symbol_timeframes(symbol: str, request: UpdateSymbolTimeframesRequest):
    """
    Update configured timeframes for a symbol.
    
    Requires X-API-Key header.
    
    Updates which timeframes (5m, 15m, 30m, 1h, 4h, 1d, 1w) the scheduler will fetch
    for this symbol. Duplicates are removed and timeframes are sorted.
    
    Parameters:
    - symbol: Ticker symbol
    - timeframes: List of timeframes to fetch (e.g., ['1h', '1d', '4h'])
    
    Example:
        PUT /api/v1/admin/symbols/AAPL/timeframes
        Headers: X-API-Key: xxx
        Body: {"timeframes": ["1h", "4h", "1d"]}
    
    Returns:
    - Updated symbol configuration with new timeframes
    """
    try:
        symbol_manager = get_symbol_manager()
        
        # Verify symbol exists
        existing = await symbol_manager.get_symbol(symbol)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
        
        # Update timeframes in database
        result = await symbol_manager.update_symbol_timeframes(symbol, request.timeframes)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to update timeframes")
        
        logger.info("Symbol timeframes updated via API", extra={
            "symbol": symbol,
            "timeframes": request.timeframes
        })
        
        return result
    
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("Timeframe update validation failed", extra={"symbol": symbol, "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Symbol timeframe update error for {symbol}", extra={"error": str(e)})
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


import asyncio
import subprocess
import os


async def run_pytest():
    """Run pytest in a thread pool"""
    try:
        cwd = os.getcwd()
        logger.info(f"Running tests from cwd: {cwd}")
        
        def execute_tests():
            result = subprocess.run(
                [
                    "python", "-m", "pytest",
                    "tests/",
                    "-v",
                    "--tb=short",
                    "-q"
                ],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=180
            )
            return result.stdout, result.stderr, result.returncode
        
        # Run in thread pool to not block event loop
        test_output, test_errors, returncode = await asyncio.to_thread(execute_tests)
        
        # Parse the output to get summary
        lines = test_output.split('\n')
        summary_line = None
        for line in lines:
            if 'passed' in line or 'failed' in line or 'error' in line:
                if '==' in line:
                    summary_line = line
        
        return {
            "success": returncode == 0,
            "return_code": returncode,
            "summary": summary_line or "Tests completed",
            "output": test_output[-2000:] if test_output else "",
            "errors": test_errors[-1000:] if test_errors else "",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "return_code": -1,
            "summary": "Test execution timed out (3 minutes)",
            "output": "",
            "errors": "Tests took too long to complete",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Test execution error: {e}")
        return {
            "success": False,
            "return_code": -1,
            "summary": f"Error running tests: {str(e)}",
            "output": "",
            "errors": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@app.get("/api/v1/tests/run")
async def run_tests_get():
    """Run tests via GET request"""
    return await run_pytest()


@app.post("/api/v1/tests/run")
async def run_tests_post():
    """Run tests via POST request"""
    return await run_pytest()


@app.get("/api/v1/news/{symbol}")
async def get_news(
    symbol: str,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=500),
    sentiment_filter: str = Query(None, regex="^(bullish|bearish|neutral)$")
):
    """
    Get recent news for a symbol with optional sentiment filtering.
    
    Args:
        symbol: Stock ticker (e.g., AAPL)
        days: Look back this many days (default: 30, max: 365)
        limit: Maximum articles to return (default: 50, max: 500)
        sentiment_filter: Filter by 'bullish', 'bearish', or 'neutral' (optional)
    
    Returns:
        List of news articles with sentiment scores
    """
    try:
        from src.services.news_service import NewsService
        
        news_service = NewsService(db)
        articles = news_service.get_news_by_symbol(
            symbol=symbol,
            days=days,
            limit=limit,
            sentiment_filter=sentiment_filter
        )
        
        return {
            "symbol": symbol,
            "articles": articles,
            "count": len(articles),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching news: {str(e)}"
        )


@app.get("/api/v1/sentiment/{symbol}")
async def get_sentiment(
    symbol: str,
    days: int = Query(30, ge=1, le=365)
):
    """
    Get aggregated sentiment metrics for a symbol.
    
    Args:
        symbol: Stock ticker (e.g., AAPL)
        days: Lookback period in days (default: 30, max: 365)
    
    Returns:
        Sentiment aggregate with trend analysis
    """
    try:
        from src.services.news_service import NewsService
        
        news_service = NewsService(db)
        sentiment = news_service.get_sentiment_aggregate(
            symbol=symbol,
            days=days
        )
        
        return {
            **sentiment,
            "lookback_days": days,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching sentiment for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching sentiment: {str(e)}"
        )


@app.get("/api/v1/sentiment/compare")
async def compare_sentiment(
    symbols: str = Query(..., description="Comma-separated symbols (e.g., 'AAPL,MSFT,GOOGL')"),
    days: int = Query(30, ge=1, le=365)
):
    """
    Compare sentiment across multiple symbols.
    
    Args:
        symbols: Comma-separated ticker symbols
        days: Lookback period in days
    
    Returns:
        List of sentiment aggregates for comparison
    """
    try:
        from src.services.news_service import NewsService
        
        symbol_list = [s.strip().upper() for s in symbols.split(',')]
        news_service = NewsService(db)
        
        results = []
        for symbol in symbol_list:
            sentiment = news_service.get_sentiment_aggregate(symbol, days)
            results.append(sentiment)
        
        return {
            "symbols": symbol_list,
            "sentiments": results,
            "lookback_days": days,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error comparing sentiment: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error comparing sentiment: {str(e)}"
        )


# ===================== PHASE 3: EARNINGS & IV ENDPOINTS =====================

@app.get("/api/v1/earnings/{symbol}")
async def get_earnings(
    symbol: str,
    days: int = Query(365, ge=1, le=1825, description="Lookback days"),
    limit: int = Query(20, ge=1, le=100, description="Max records")
):
    """
    Get historical earnings records for a symbol with surprises.
    
    Args:
        symbol: Stock ticker (e.g., AAPL)
        days: Look back period (1-1825 days, default 365)
        limit: Max records to return (1-100)
    
    Returns:
        List of earnings with estimated vs actual, surprises
    """
    try:
        from src.services.earnings_service import EarningsService
        
        earnings_service = EarningsService(db)
        earnings = await earnings_service.get_earnings_by_symbol(
            symbol.upper(), days_back=days
        )
        
        return {
            "symbol": symbol.upper(),
            "earnings": earnings[:limit],
            "count": len(earnings[:limit]),
            "lookback_days": days,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching earnings: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching earnings: {str(e)}"
        )


@app.get("/api/v1/earnings/{symbol}/summary")
async def get_earnings_summary(
    symbol: str
):
    """
    Get aggregated earnings statistics.
    
    Returns:
        Summary of beat rates, average surprises, etc.
    """
    try:
        from src.services.earnings_service import EarningsService
        
        earnings_service = EarningsService(db)
        summary = await earnings_service.get_earnings_summary(symbol.upper())
        surprises = await earnings_service.get_earnings_surprises(
            symbol.upper()
        )
        
        return {
            "symbol": symbol.upper(),
            "summary": summary,
            "surprises": surprises,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching earnings summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching earnings summary: {str(e)}"
        )


@app.get("/api/v1/earnings/upcoming")
async def get_upcoming_earnings(
    symbols: str = Query(None, description="Comma-separated tickers (optional)"),
    days: int = Query(30, ge=1, le=90, description="Days ahead")
):
    """
    Get upcoming earnings announcements.
    
    Args:
        symbols: Optional comma-separated tickers (if None, returns all)
        days: Days ahead to look (1-90)
    
    Returns:
        List of upcoming earnings with times and estimates
    """
    try:
        from src.services.earnings_service import EarningsService
        
        earnings_service = EarningsService(db)
        symbol_list = (
            [s.strip().upper() for s in symbols.split(",")]
            if symbols else None
        )
        
        upcoming = await earnings_service.get_upcoming_earnings(
            days_ahead=days, symbols=symbol_list
        )
        
        return {
            "upcoming_earnings": upcoming,
            "count": len(upcoming),
            "lookback_days": days,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching upcoming earnings: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching upcoming earnings: {str(e)}"
        )


@app.get("/api/v1/options/iv/{symbol}")
async def get_options_iv(
    symbol: str,
    expiration: str = Query(None, description="Expiration date (YYYY-MM-DD)"),
    days: int = Query(30, ge=1, le=365, description="Lookback days")
):
    """
    Get options implied volatility data for a symbol.
    
    Args:
        symbol: Stock ticker
        expiration: Specific expiration (optional, latest if not provided)
        days: Lookback period
    
    Returns:
        Options chain with IV, Greeks, and pricing
    """
    try:
        from src.services.options_iv_service import OptionsIVService
        
        options_service = OptionsIVService(db)
        
        if expiration:
            chain = await options_service.get_chain_for_symbol(
                symbol.upper(), expiration
            )
        else:
            # Get latest expiration
            query = """
            SELECT DISTINCT expiration_date 
            FROM options_iv 
            WHERE symbol = $1 
            ORDER BY expiration_date ASC 
            LIMIT 1
            """
            result = await db.fetchrow(query, symbol.upper())
            if result:
                chain = await options_service.get_chain_for_symbol(
                    symbol.upper(), result["expiration_date"].isoformat()
                )
            else:
                chain = []
        
        return {
            "symbol": symbol.upper(),
            "expiration": expiration,
            "chain": chain,
            "count": len(chain),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching options IV: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching options IV: {str(e)}"
        )


@app.get("/api/v1/volatility/regime/{symbol}")
async def get_volatility_regime(
    symbol: str,
    date: str = Query(None, description="Quote date (YYYY-MM-DD), uses latest if not provided")
):
    """
    Get volatility regime classification for a symbol.
    
    Args:
        symbol: Stock ticker
        date: Specific date (optional)
    
    Returns:
        Regime ('very_low', 'low', 'normal', 'high', 'very_high'), IV metrics, HV comparison
    """
    try:
        from src.services.options_iv_service import OptionsIVService
        
        options_service = OptionsIVService(db)
        regime = await options_service.get_volatility_regime(
            symbol.upper(), date
        )
        
        if not regime:
            raise HTTPException(
                status_code=404,
                detail=f"No volatility regime data for {symbol}"
            )
        
        return {
            "symbol": symbol.upper(),
            "regime": regime,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching volatility regime: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching volatility regime: {str(e)}"
        )


@app.get("/api/v1/features/composite/{symbol}")
async def get_composite_features(
    symbol: str
):
    """
    Get composite feature vector for a symbol (ML features).
    
    Combines:
    - Dividend metrics
    - Earnings beat rates and surprises
    - News sentiment
    - Volatility regime
    - IV metrics
    
    Returns:
        Feature vector suitable for ML models
    """
    try:
        from src.services.feature_service import FeatureService
        
        feature_service = FeatureService(db)
        features = await feature_service.get_composite_features(symbol.upper())
        
        if not features:
            raise HTTPException(
                status_code=404,
                detail=f"No feature data available for {symbol}"
            )
        
        return {
            "symbol": symbol.upper(),
            "features": features,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching composite features: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching composite features: {str(e)}"
        )


@app.get("/api/v1/features/importance")
async def get_feature_importance():
    """
    Get feature importance weights for ML models.
    
    Returns:
        Dict of feature names to importance scores
    """
    try:
        from src.services.feature_service import FeatureService
        
        feature_service = FeatureService(db)
        importance = await feature_service.calculate_feature_importance([])
        
        return {
            "feature_importance": importance,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching feature importance: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching feature importance: {str(e)}"
        )


@app.on_event("startup")
async def startup_event():
    """Additional startup tasks if needed"""
    logger.info("Additional startup tasks completed")


@app.get("/api/v1/enrichment/status/{symbol}")
async def get_enrichment_status(symbol: str):
    """
    Get enrichment status and latest data quality metrics for a symbol.
    
    Args:
        symbol: Asset symbol
    
    Returns:
        Dict with enrichment status, data freshness, and quality metrics
    """
    try:
        # Get backfill status
        backfill_status = db.get_backfill_status(symbol, '1d')
        
        # Query latest data quality metrics
        session = db.SessionLocal()
        try:
            from sqlalchemy import text
            result = session.execute(
                text("""
                    SELECT symbol, asset_class, metric_date, validation_rate, 
                           avg_quality_score, data_completeness
                    FROM data_quality_metrics
                    WHERE symbol = :symbol
                    ORDER BY metric_date DESC
                    LIMIT 1
                """),
                {'symbol': symbol}
            ).first()
            
            quality_data = None
            if result:
                quality_data = {
                    'symbol': result[0],
                    'asset_class': result[1],
                    'metric_date': result[2].isoformat() if result[2] else None,
                    'validation_rate': float(result[3]) if result[3] else 0,
                    'avg_quality_score': float(result[4]) if result[4] else 0,
                    'data_completeness': float(result[5]) if result[5] else 0
                }
        finally:
            session.close()
        
        return {
            'symbol': symbol,
            'backfill_status': backfill_status,
            'quality_metrics': quality_data,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting enrichment status for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/enrichment/metrics")
async def get_enrichment_metrics():
    """
    Get overall enrichment pipeline metrics and performance statistics.
    
    Returns:
        Dict with fetch logs, computation stats, and health indicators
    """
    try:
        session = db.SessionLocal()
        try:
            from sqlalchemy import text, func
            
            # Fetch log stats (last 24 hours)
            fetch_stats = session.execute(
                text("""
                    SELECT COUNT(*) as total_fetches,
                           SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                           AVG(source_response_time_ms) as avg_response_time_ms,
                           MAX(api_quota_remaining) as quota_remaining
                    FROM enrichment_fetch_log
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)
            ).first()
            
            # Computation stats (last 24 hours)
            compute_stats = session.execute(
                text("""
                    SELECT COUNT(*) as total_computations,
                           SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                           AVG(computation_time_ms) as avg_time_ms
                    FROM enrichment_compute_log
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)
            ).first()
            
            # Overall data quality
            quality_stats = session.execute(
                text("""
                    SELECT COUNT(DISTINCT symbol) as symbols_tracked,
                           AVG(validation_rate) as avg_validation_rate,
                           AVG(avg_quality_score) as avg_quality_score
                    FROM data_quality_metrics
                    WHERE metric_date > CURRENT_DATE - INTERVAL '7 days'
                """)
            ).first()
        
        finally:
            session.close()
        
        return {
            'fetch_pipeline': {
                'total_fetches': fetch_stats[0] if fetch_stats[0] else 0,
                'successful': fetch_stats[1] if fetch_stats[1] else 0,
                'success_rate': (fetch_stats[1] / fetch_stats[0] * 100) if fetch_stats[0] else 0,
                'avg_response_time_ms': int(fetch_stats[2]) if fetch_stats[2] else 0,
                'api_quota_remaining': fetch_stats[3] if fetch_stats[3] else None
            },
            'compute_pipeline': {
                'total_computations': compute_stats[0] if compute_stats[0] else 0,
                'successful': compute_stats[1] if compute_stats[1] else 0,
                'success_rate': (compute_stats[1] / compute_stats[0] * 100) if compute_stats[0] else 0,
                'avg_computation_time_ms': int(compute_stats[2]) if compute_stats[2] else 0
            },
            'data_quality': {
                'symbols_tracked': quality_stats[0] if quality_stats[0] else 0,
                'avg_validation_rate': round(float(quality_stats[1]) if quality_stats[1] else 0, 2),
                'avg_quality_score': round(float(quality_stats[2]) if quality_stats[2] else 0, 2)
            },
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting enrichment metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/enrichment/trigger")
async def trigger_enrichment(
    symbol: str = Query(..., description="Symbol to enrich"),
    asset_class: str = Query('stock', description="Asset class (stock, crypto, etf)"),
    timeframes: List[str] = Query(['1d'], description="Timeframes to enrich")
):
    """
    Manually trigger enrichment for a specific symbol and timeframes.
    
    Args:
        symbol: Asset symbol
        asset_class: Asset class
        timeframes: List of timeframes to enrich
    
    Returns:
        Enrichment job result
    """
    try:
        from src.services.data_enrichment_service import DataEnrichmentService
        
        # Initialize enrichment service
        enrichment_service = DataEnrichmentService(db, config)
        
        # Calculate date range (last 365 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=365)
        
        # Run enrichment
        result = await enrichment_service.enrich_symbol(
            symbol=symbol,
            asset_class=asset_class,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            'job_id': result.get('job_id'),
            'symbol': result.get('symbol'),
            'asset_class': result.get('asset_class'),
            'success': result.get('success'),
            'total_inserted': result.get('total_records_inserted'),
            'total_updated': result.get('total_records_updated'),
            'timeframes': result.get('timeframes'),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error triggering enrichment for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/backfill")
async def bulk_backfill(
symbols: List[str] = Query(..., description="List of symbols to backfill"),
start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
timeframes: List[str] = Query(['1d'], description="Timeframes to backfill")
):
    """
    Trigger backfill for multiple symbols (non-blocking, returns immediately).

    Args:
        symbols: List of asset symbols
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        timeframes: List of timeframes to backfill

    Returns:
        Job info with ID and status
    """
    try:
        from datetime import datetime as dt
        from src.services.backfill_worker import enqueue_backfill_job

        # Validate inputs
        if not symbols:
            raise ValueError("At least one symbol required")
        if len(symbols) > 100:
            raise ValueError("Maximum 100 symbols per request")

        # Parse dates
        try:
            start = dt.strptime(start_date, '%Y-%m-%d')
            end = dt.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")

        if start > end:
            raise ValueError("Start date must be before end date")

        # Create job ID
        job_id = str(uuid.uuid4())

        # Create job record in database
        db.create_backfill_job(job_id, symbols, start_date, end_date, timeframes)

        # Queue the backfill task (runs in background)
        enqueue_backfill_job(job_id, symbols, start_date, end_date, timeframes)

        # Log the backfill request
        logger.info(f"Backfill job created: {len(symbols)} symbols, {len(timeframes)} timeframes",
                   extra={
                        'job_id': job_id,
                        'symbol_count': len(symbols),
                        'date_range': f"{start_date} to {end_date}",
                        'timeframes': timeframes
                    })

        return {
            'job_id': job_id,
            'status': 'queued',
            'symbols_count': len(symbols),
            'symbols': symbols[:10] + (['...'] if len(symbols) > 10 else []),
            'date_range': {'start': start_date, 'end': end_date},
            'timeframes': timeframes,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in bulk backfill: {e}", extra={'error': str(e)})
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/backfill/status/{job_id}")
async def get_backfill_status(job_id: str):
    """Get progress status of a backfill job."""
    try:
        status = db.get_backfill_job_status(job_id)
        
        if 'error' in status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return status
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting backfill status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/backfill/recent")
async def get_recent_backfill_jobs(limit: int = Query(10, ge=1, le=100)):
    """Get recent backfill jobs."""
    try:
        jobs = db.get_recent_backfill_jobs(limit)
        return {
            'jobs': jobs,
            'timestamp': datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting recent backfill jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/enrich")
async def bulk_enrich(
    symbols: List[str] = Query(..., description="List of symbols to enrich"),
    timeframe: str = Query('1h', description="Timeframe to enrich")
):
    """
    Trigger enrichment for multiple symbols.
    
    Args:
        symbols: List of asset symbols
        timeframe: Single timeframe to enrich
    
    Returns:
        Job info with ID and status
    """
    try:
        import uuid
        
        # Validate inputs
        if not symbols:
            raise ValueError("At least one symbol required")
        if len(symbols) > 100:
            raise ValueError("Maximum 100 symbols per request")
        
        # Create job ID
        job_id = str(uuid.uuid4())
        
        # Log the enrichment request
        logger.info(f"Bulk enrichment started: {len(symbols)} symbols, timeframe={timeframe}",
                   extra={
                       'job_id': job_id,
                       'symbol_count': len(symbols),
                       'timeframe': timeframe
                   })
        
        # In a production system, this would queue the job
        # For now, return immediate response
        return {
            'job_id': job_id,
            'status': 'queued',
            'symbols_count': len(symbols),
            'symbols': symbols[:10] + (['...'] if len(symbols) > 10 else []),
            'timeframe': timeframe,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in bulk enrichment: {e}", extra={'error': str(e)})
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/data/quality/{symbol}")
async def get_data_quality_report(
    symbol: str,
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze")
):
    """
    Get detailed data quality report for a symbol over the specified period.
    
    Args:
        symbol: Asset symbol
        days: Number of days to analyze (default: 7, max: 365)
    
    Returns:
        Dict with quality metrics, validation rates, and anomalies
    """
    try:
        session = db.SessionLocal()
        try:
            from sqlalchemy import text
            
            # Get quality metrics for the period
            quality_data = session.execute(
                text("""
                    SELECT metric_date, total_records, validated_records, validation_rate,
                           gaps_detected, anomalies_detected, avg_quality_score, data_completeness
                    FROM data_quality_metrics
                    WHERE symbol = :symbol
                    AND metric_date > CURRENT_DATE - INTERVAL ':days days'
                    ORDER BY metric_date DESC
                """),
                {'symbol': symbol, 'days': days}
            ).fetchall()
            
            # Get recent fetch logs
            fetch_logs = session.execute(
                text("""
                    SELECT symbol, source, timeframe, records_fetched, records_inserted,
                           source_response_time_ms, success, created_at
                    FROM enrichment_fetch_log
                    WHERE symbol = :symbol
                    AND created_at > NOW() - INTERVAL ':days days'
                    ORDER BY created_at DESC
                    LIMIT 20
                """),
                {'symbol': symbol, 'days': days}
            ).fetchall()
        
        finally:
            session.close()
        
        # Format quality data
        metrics = []
        for row in quality_data:
            metrics.append({
                'date': row[0].isoformat() if row[0] else None,
                'total_records': row[1],
                'validated_records': row[2],
                'validation_rate': float(row[3]) if row[3] else 0,
                'gaps_detected': row[4],
                'anomalies_detected': row[5],
                'avg_quality_score': float(row[6]) if row[6] else 0,
                'data_completeness': float(row[7]) if row[7] else 0
            })
        
        # Format fetch logs
        logs = []
        for row in fetch_logs:
            logs.append({
                'source': row[1],
                'timeframe': row[2],
                'records_fetched': row[3],
                'records_inserted': row[4],
                'response_time_ms': row[5],
                'success': row[6],
                'timestamp': row[7].isoformat() if row[7] else None
            })
        
        # Calculate summary stats
        if metrics:
            avg_validation_rate = sum(m['validation_rate'] for m in metrics) / len(metrics)
            avg_quality_score = sum(m['avg_quality_score'] for m in metrics) / len(metrics)
            total_gaps = sum(m['gaps_detected'] for m in metrics)
        else:
            avg_validation_rate = 0
            avg_quality_score = 0
            total_gaps = 0
        
        return {
            'symbol': symbol,
            'period_days': days,
            'summary': {
                'avg_validation_rate': round(avg_validation_rate, 2),
                'avg_quality_score': round(avg_quality_score, 2),
                'total_gaps_detected': total_gaps
            },
            'daily_metrics': metrics,
            'recent_fetch_logs': logs,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error getting quality report for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    """Additional shutdown tasks if needed"""
    logger.info("Additional shutdown tasks completed")


# ============================================================================
# PHASE 1D: ENRICHMENT REST API ENDPOINTS (4 COMPLETE ENDPOINTS)
# ============================================================================


@app.get("/api/v1/enrichment/status/{symbol}")
async def get_enrichment_status_endpoint(symbol: str):
    """
    GET /api/v1/enrichment/status/{symbol}
    
    Get enrichment status and latest data quality metrics for a symbol.
    
    Args:
        symbol: Asset symbol (e.g., AAPL, BTC)
    
    Returns:
        {
            "symbol": "AAPL",
            "asset_class": "stock",
            "status": "healthy|warning|stale|error",
            "last_enrichment_time": "2024-11-13T10:30:45Z",
            "data_age_seconds": 300,
            "records_available": 1250,
            "quality_score": 0.95,
            "validation_rate": 98.5,
            "timeframes_available": ["1d", "1h"],
            "next_enrichment": "2024-11-14T01:30:00Z",
            "error_message": null,
            "timestamp": "2024-11-13T10:31:00Z"
        }
    """
    try:
        session = db.SessionLocal()
        try:
            from sqlalchemy import text
            
            # Query enrichment status
            status = session.execute(
                text("""
                    SELECT symbol, asset_class, status, last_enrichment_time, 
                           data_age_seconds, records_available, quality_score, 
                           validation_rate, error_message
                    FROM enrichment_status
                    WHERE symbol = :symbol
                """),
                {'symbol': symbol.upper()}
            ).first()
            
            # Query available timeframes
            timeframes = session.execute(
                text("""
                    SELECT DISTINCT timeframe
                    FROM market_data
                    WHERE symbol = :symbol
                    ORDER BY timeframe
                """),
                {'symbol': symbol.upper()}
            ).fetchall()
            
            if not status:
                return {
                    'symbol': symbol.upper(),
                    'status': 'not_enriched',
                    'records_available': 0,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            return {
                'symbol': status[0],
                'asset_class': status[1],
                'status': status[2],
                'last_enrichment_time': status[3].isoformat() if status[3] else None,
                'data_age_seconds': status[4],
                'records_available': status[5],
                'quality_score': float(status[6]) if status[6] else None,
                'validation_rate': float(status[7]) if status[7] else None,
                'timeframes_available': [t[0] for t in timeframes],
                'next_enrichment': (status[3] + timedelta(days=1)).isoformat() if status[3] else None,
                'error_message': status[8],
                'timestamp': datetime.utcnow().isoformat()
            }
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error getting enrichment status for {symbol}: {e}", extra={'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/enrichment/metrics")
async def get_enrichment_metrics_endpoint():
    """
    GET /api/v1/enrichment/metrics
    
    Get overall enrichment pipeline metrics and performance statistics.
    
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
            },
            "backfill_progress": {
                "in_progress": 2,
                "completed": 43,
                "failed": 0,
                "pending": 0
            },
            "timestamp": "2024-11-13T10:31:00Z"
        }
    """
    try:
        session = db.SessionLocal()
        try:
            from sqlalchemy import text, func
            
            # Fetch log stats (last 24 hours)
            fetch_stats = session.execute(
                text("""
                    SELECT COUNT(*) as total_fetches,
                           SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                           AVG(source_response_time_ms) as avg_response_time_ms,
                           MAX(api_quota_remaining) as quota_remaining
                    FROM enrichment_fetch_log
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)
            ).first()
            
            # Computation stats (last 24 hours)
            compute_stats = session.execute(
                text("""
                    SELECT COUNT(*) as total_computations,
                           SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful,
                           AVG(computation_time_ms) as avg_time_ms
                    FROM enrichment_compute_log
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                """)
            ).first()
            
            # Overall data quality
            quality_stats = session.execute(
                text("""
                    SELECT COUNT(DISTINCT symbol) as symbols_tracked,
                           AVG(validation_rate) as avg_validation_rate,
                           AVG(avg_quality_score) as avg_quality_score
                    FROM data_quality_metrics
                    WHERE metric_date > CURRENT_DATE - INTERVAL '7 days'
                """)
            ).first()
            
            # Backfill progress
            backfill_stats = session.execute(
                text("""
                    SELECT status, COUNT(*) as count
                    FROM backfill_state
                    GROUP BY status
                """)
            ).fetchall()
            
            backfill_dict = {status[0]: status[1] for status in backfill_stats}
            
            total_fetches = fetch_stats[0] if fetch_stats[0] else 0
            successful_fetches = fetch_stats[1] if fetch_stats[1] else 0
            
            total_computes = compute_stats[0] if compute_stats[0] else 0
            successful_computes = compute_stats[1] if compute_stats[1] else 0
            
            return {
                'fetch_pipeline': {
                    'total_fetches': total_fetches,
                    'successful': successful_fetches,
                    'success_rate': round((successful_fetches / total_fetches * 100) if total_fetches > 0 else 0, 2),
                    'avg_response_time_ms': int(fetch_stats[2]) if fetch_stats[2] else 0,
                    'api_quota_remaining': fetch_stats[3] if fetch_stats[3] else None
                },
                'compute_pipeline': {
                    'total_computations': total_computes,
                    'successful': successful_computes,
                    'success_rate': round((successful_computes / total_computes * 100) if total_computes > 0 else 0, 2),
                    'avg_computation_time_ms': int(compute_stats[2]) if compute_stats[2] else 0
                },
                'data_quality': {
                    'symbols_tracked': quality_stats[0] if quality_stats[0] else 0,
                    'avg_validation_rate': round(float(quality_stats[1]) if quality_stats[1] else 0, 2),
                    'avg_quality_score': round(float(quality_stats[2]) if quality_stats[2] else 0, 2)
                },
                'backfill_progress': {
                    'in_progress': backfill_dict.get('in_progress', 0),
                    'completed': backfill_dict.get('completed', 0),
                    'failed': backfill_dict.get('failed', 0),
                    'pending': backfill_dict.get('pending', 0)
                },
                'timestamp': datetime.utcnow().isoformat()
            }
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error getting enrichment metrics: {e}", extra={'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/enrichment/trigger")
async def trigger_enrichment_endpoint(
    symbol: str = Query(..., description="Symbol to enrich"),
    asset_class: str = Query('stock', description="Asset class (stock, crypto, etf)"),
    timeframes: List[str] = Query(['1d'], description="Timeframes to enrich")
):
    """
    POST /api/v1/enrichment/trigger
    
    Manually trigger enrichment for a specific symbol and timeframes.
    
    Query Parameters:
        symbol: Asset symbol (required)
        asset_class: 'stock' | 'crypto' | 'etf' (default: 'stock')
        timeframes: List of timeframes (default: ['1d'])
    
    Returns:
        {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "symbol": "AAPL",
            "asset_class": "stock",
            "timeframes": ["1d", "1h"],
            "status": "queued",
            "total_records_to_process": 500,
            "estimated_duration_seconds": 45,
            "timestamp": "2024-11-13T10:31:00Z"
        }
    """
    try:
        from src.services.data_enrichment_service import DataEnrichmentService
        from datetime import timedelta
        
        # Validate inputs
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol required")
        
        if asset_class not in ['stock', 'crypto', 'etf']:
            raise HTTPException(status_code=400, detail="Invalid asset_class")
        
        invalid_timeframes = [tf for tf in timeframes if tf not in ALLOWED_TIMEFRAMES]
        if invalid_timeframes:
            raise HTTPException(status_code=400, detail=f"Invalid timeframes: {invalid_timeframes}")
        
        # Initialize enrichment service
        enrichment_service = DataEnrichmentService(db, config)
        
        # Calculate date range (last 365 days)
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=365)
        
        # Queue enrichment job
        job_id = str(uuid.uuid4())
        
        logger.info(
            "enrichment_job_triggered",
            job_id=job_id,
            symbol=symbol,
            asset_class=asset_class,
            timeframes=timeframes
        )
        
        # Run enrichment asynchronously (in background)
        # For now, return job queued response

        # Execute enrichment
        result = await enrichment_service.enrich_symbol(
            symbol=symbol,
            asset_class=asset_class,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date
        )

        # Run enrichment asynchronously (in background)
        return {
            'job_id': job_id,
            'symbol': symbol.upper(),
            'asset_class': asset_class,
            'timeframes': timeframes,
            'status': 'queued',
            'total_records_to_process': count,
            'estimated_duration_seconds': max(30, count // 100),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering enrichment: {e}", extra={'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/features/quant/{symbol}")
async def get_quant_features_endpoint(
    symbol: str,
    timeframe: str = Query("1d", description="Timeframe: 5m, 15m, 30m, 1h, 4h, 1d, 1w"),
    start: str = Query(None, description="Start date YYYY-MM-DD (optional)"),
    end: str = Query(None, description="End date YYYY-MM-DD (optional)"),
    limit: int = Query(500, ge=1, le=10000, description="Max records to return")
):
    """
    GET /api/v1/features/quant/{symbol}
    
    Fetch AI-ready quant features for a symbol.
    
    Returns OHLCV + computed features:
    - Returns: return_1h, return_1d
    - Volatility: volatility_20, volatility_50, atr
    - Volume: rolling_volume_20, volume_ratio
    - Structure: structure_label, trend_direction, hh, hl, lh, ll
    - Regimes: volatility_regime, trend_regime, compression_regime
    
    Example:
    - GET /api/v1/features/quant/AAPL?timeframe=1d
    - GET /api/v1/features/quant/MSFT?timeframe=1h&start=2024-01-01&end=2024-12-31&limit=1000
    
    Query Parameters:
        symbol: Asset ticker (e.g., AAPL, BTC)
        timeframe: Candle timeframe (5m, 15m, 30m, 1h, 4h, 1d, 1w) - default: 1d
        start: Optional start date YYYY-MM-DD
        end: Optional end date YYYY-MM-DD
        limit: Max records (1-10000, default: 500)
    
    Returns:
        {
            "symbol": "AAPL",
            "timeframe": "1d",
            "records_returned": 250,
            "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            "features": [
                {
                    "time": "2024-11-13T00:00:00Z",
                    "open": 234.56,
                    "high": 235.80,
                    "low": 234.12,
                    "close": 235.45,
                    "volume": 52341200,
                    "return_1d": 0.0082,
                    "volatility_20": 0.1823,
                    "volatility_50": 0.1756,
                    "atr": 2.34,
                    "rolling_volume_20": 48500000,
                    "volume_ratio": 1.08,
                    "structure_label": "bullish",
                    "trend_direction": "up",
                    "volatility_regime": "medium",
                    "trend_regime": "uptrend",
                    "compression_regime": "expanded",
                    "quality_score": 0.95,
                    "validated": true
                },
                ...
            ],
            "timestamp": "2024-11-13T10:31:00Z"
        }
    """
    try:
        # Validate timeframe
        try:
            timeframe = validate_timeframe(timeframe)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        # Validate date format if provided
        if start:
            try:
                datetime.strptime(start, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid start date format. Use YYYY-MM-DD"
                )
        
        if end:
            try:
                datetime.strptime(end, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid end date format. Use YYYY-MM-DD"
                )
        
        # Fetch quant features
        features = db.get_quant_features(
            symbol=symbol.upper(),
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit
        )
        
        if not features:
            raise HTTPException(
                status_code=404,
                detail=f"No quant features found for {symbol.upper()} timeframe={timeframe}. Data may not have been computed yet."
            )
        
        # Build date range
        date_range = {}
        if features:
            date_range["start"] = features[0].get("time", "").split("T")[0] if features[0].get("time") else None
            date_range["end"] = features[-1].get("time", "").split("T")[0] if features[-1].get("time") else None
        
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "records_returned": len(features),
            "date_range": date_range,
            "features": features,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching quant features for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/api/v1/data/quality/{symbol}")
async def get_data_quality_report_endpoint(
    symbol: str,
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze")
):
    """
    GET /api/v1/data/quality/{symbol}
    
    Get detailed data quality report for a symbol over the specified period.
    
    Path Parameters:
        symbol: Asset symbol
    
    Query Parameters:
        days: Number of days to analyze (1-365, default: 7)
    
    Returns:
        {
            "symbol": "AAPL",
            "period_days": 7,
            "summary": {
                "avg_validation_rate": 98.5,
                "avg_quality_score": 0.93,
                "total_gaps_detected": 2,
                "total_anomalies": 0
            },
            "daily_metrics": [
                {
                    "date": "2024-11-13",
                    "total_records": 180,
                    "validated_records": 177,
                    "validation_rate": 98.33,
                    "gaps_detected": 0,
                    "anomalies_detected": 0,
                    "avg_quality_score": 0.94,
                    "data_completeness": 0.99
                },
                ...
            ],
            "recent_fetch_logs": [
                {
                    "source": "polygon",
                    "timeframe": "1d",
                    "records_fetched": 5,
                    "records_inserted": 5,
                    "response_time_ms": 245,
                    "success": true,
                    "timestamp": "2024-11-13T01:30:45Z"
                },
                ...
            ],
            "timestamp": "2024-11-13T10:31:00Z"
        }
    """
    try:
        session = db.SessionLocal()
        try:
            from sqlalchemy import text
            
            # Get quality metrics for the period
            quality_data = session.execute(
                text("""
                    SELECT metric_date, total_records, validated_records, validation_rate,
                           gaps_detected, anomalies_detected, avg_quality_score, data_completeness
                    FROM data_quality_metrics
                    WHERE symbol = :symbol
                    AND metric_date > CURRENT_DATE - INTERVAL '1 day' * :days
                    ORDER BY metric_date DESC
                """),
                {'symbol': symbol.upper(), 'days': days}
            ).fetchall()
            
            # Get recent fetch logs
            fetch_logs = session.execute(
                text("""
                    SELECT symbol, source, timeframe, records_fetched, records_inserted,
                           source_response_time_ms, success, created_at
                    FROM enrichment_fetch_log
                    WHERE symbol = :symbol
                    AND created_at > NOW() - INTERVAL '1 day' * :days
                    ORDER BY created_at DESC
                    LIMIT 20
                """),
                {'symbol': symbol.upper(), 'days': days}
            ).fetchall()
            
            # Format quality data
            metrics = []
            total_gaps = 0
            total_anomalies = 0
            
            for row in quality_data:
                metrics.append({
                    'date': row[0].isoformat() if row[0] else None,
                    'total_records': row[1],
                    'validated_records': row[2],
                    'validation_rate': float(row[3]) if row[3] else 0,
                    'gaps_detected': row[4],
                    'anomalies_detected': row[5],
                    'avg_quality_score': float(row[6]) if row[6] else 0,
                    'data_completeness': float(row[7]) if row[7] else 0
                })
                total_gaps += row[4] or 0
                total_anomalies += row[5] or 0
            
            # Format fetch logs
            logs = []
            for row in fetch_logs:
                logs.append({
                    'source': row[1],
                    'timeframe': row[2],
                    'records_fetched': row[3],
                    'records_inserted': row[4],
                    'response_time_ms': row[5],
                    'success': row[6],
                    'timestamp': row[7].isoformat() if row[7] else None
                })
            
            # Calculate summary stats
            if metrics:
                avg_validation_rate = sum(m['validation_rate'] for m in metrics) / len(metrics)
                avg_quality_score = sum(m['avg_quality_score'] for m in metrics) / len(metrics)
            else:
                avg_validation_rate = 0
                avg_quality_score = 0
            
            return {
                'symbol': symbol.upper(),
                'period_days': days,
                'summary': {
                    'avg_validation_rate': round(avg_validation_rate, 2),
                    'avg_quality_score': round(avg_quality_score, 2),
                    'total_gaps_detected': total_gaps,
                    'total_anomalies': total_anomalies
                },
                'daily_metrics': metrics,
                'recent_fetch_logs': logs,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        finally:
            session.close()
    
    except Exception as e:
        logger.error(f"Error getting quality report for {symbol}: {e}", extra={'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))


# ========================= PHASE 1: SCHEDULER MONITORING =========================

@app.get("/api/v1/admin/scheduler-health")
async def get_scheduler_health():
    """
    Get scheduler health status and feature freshness overview.
    
    Returns:
    - last_execution: Details of last backfill run
    - stale_features_count: How many symbol/timeframes have stale features
    - recent_failures: Recent computation failures
    - total_symbols_monitored: Count of unique symbols with features
    """
    try:
        health = db.get_scheduler_health()
        
        return {
            "status": "healthy" if health.get("stale_features_count", 0) == 0 else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            **health
        }
    
    except Exception as e:
        logger.error(f"Error getting scheduler health: {e}", extra={'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/admin/features/staleness")
async def get_feature_staleness_report(limit: int = Query(50, ge=1, le=500)):
    """
    Get feature freshness report for monitoring dashboard.
    
    Shows which symbols/timeframes have stale features sorted by staleness.
    Useful for identifying data gaps and scheduler issues.
    
    Query params:
    - limit: Max results (1-500, default 50)
    
    Returns:
    - List of {symbol, timeframe, last_computed_at, staleness_seconds, status, data_point_count}
    """
    try:
        features = db.get_feature_staleness_report(limit=limit)
        
        # Categorize by status
        fresh = [f for f in features if f["status"] == "fresh"]
        aging = [f for f in features if f["status"] == "aging"]
        stale = [f for f in features if f["status"] == "stale"]
        missing = [f for f in features if f["status"] == "missing"]
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "summary": {
                "fresh_count": len(fresh),
                "aging_count": len(aging),
                "stale_count": len(stale),
                "missing_count": len(missing),
                "total_monitored": len(features)
            },
            "by_status": {
                "fresh": fresh,
                "aging": aging,
                "stale": stale,
                "missing": missing
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting feature staleness report: {e}", extra={'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/admin/scheduler/execution-history")
async def get_scheduler_execution_history(limit: int = Query(20, ge=1, le=100)):
    """
    Get recent scheduler execution history for auditing.
    
    Returns:
    - List of past executions with timing, symbol counts, success/failure rates
    """
    try:
        from sqlalchemy import text
        
        session = db.SessionLocal()
        
        results = session.execute(text("""
            SELECT execution_id, started_at, completed_at, duration_seconds,
                   total_symbols, successful_symbols, failed_symbols, 
                   total_records_processed, status, error_message
            FROM scheduler_execution_log
            ORDER BY started_at DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
        
        session.close()
        
        executions = [
            {
                "execution_id": str(r[0]),
                "started_at": r[1].isoformat(),
                "completed_at": r[2].isoformat() if r[2] else None,
                "duration_seconds": r[3],
                "total_symbols": r[4],
                "successful_symbols": r[5],
                "failed_symbols": r[6],
                "total_records_processed": r[7],
                "status": r[8],
                "error_message": r[9],
                "success_rate": round((r[5] / r[4] * 100), 1) if r[4] > 0 else 0
            }
            for r in results
        ]
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "executions": executions
        }
    
    except Exception as e:
        logger.error(f"Error getting execution history: {e}", extra={'error': str(e)})
        raise HTTPException(status_code=500, detail=str(e))



if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=config.api_host,
        port=config.api_port,
        workers=config.api_workers,
        log_level=config.log_level.lower()
    )
