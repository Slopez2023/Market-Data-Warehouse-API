"""FastAPI application for Market Data Warehouse"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.config import config
from src.scheduler import AutoBackfillScheduler, get_last_backfill_result, get_last_backfill_time
from src.services.database_service import DatabaseService
from src.models import HealthResponse, StatusResponse

# Setup logging
logging.basicConfig(
    level=config.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
    logger.info(f"Scheduler configured: {backfill_hour:02d}:{backfill_minute:02d} UTC daily")
    
    # Test database connection
    try:
        metrics = db.get_status_metrics()
        logger.info(f"✓ Database connected: {metrics.get('symbols_available', 0)} symbols available")
    except Exception as e:
        logger.warning(f"⚠️  Could not connect to database: {e}")
    
    # Start scheduler
    try:
        scheduler.start()
        logger.info("✓ Scheduler started")
    except Exception as e:
        logger.error(f"✗ Failed to start scheduler: {e}")
    
    logger.info("✓ App startup complete\n")
    yield
    
    # Shutdown
    logger.info("Shutting down Market Data API")
    if scheduler.scheduler.running:
        scheduler.stop()
    logger.info("✓ App shutdown")


app = FastAPI(
    title="Market Data API",
    description="Validated US stock OHLCV warehouse. Single source of truth for research and analysis.",
    version="1.0.0",
    lifespan=lifespan
)

# Mount dashboard (if it exists)
dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard")
if os.path.isdir(dashboard_path):
    app.mount("/dashboard", StaticFiles(directory=dashboard_path, html=True), name="dashboard")
    logger.info("✓ Dashboard mounted at /dashboard")


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
        logger.error(f"Metrics endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Metrics query failed: {str(e)}")


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
        "description": "Validated US stock OHLCV warehouse",
        "dashboard": "/dashboard",
        "docs": "/docs",
        "endpoints": {
            "health": "/health",
            "status": "/api/v1/status",
            "historical": "/api/v1/historical/{symbol}",
            "symbols": "/api/v1/symbols",
            "metrics": "/api/v1/metrics"
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
