"""Asset data endpoints for dashboard"""

from fastapi import APIRouter, Query, HTTPException
from src.services.database_service import DatabaseService
from src.services.structured_logging import StructuredLogger
from src.config import config
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])
logger = StructuredLogger(__name__)

def get_db() -> DatabaseService:
    """Get database service instance"""
    return DatabaseService(config.database_url)

@router.get("/{symbol}")
async def get_asset_summary(symbol: str):
    """
    Get asset overview with all timeframes and enrichment status

    Args:
        symbol: Stock symbol (e.g., 'AAPL')

    Returns:
        Asset data including status, records by timeframe, enrichment status
    """
    db = get_db()

    try:
        # Get symbol stats
        stats = db.get_symbol_stats(symbol)
        if not stats or stats.get("total_records", 0) == 0:
            raise HTTPException(status_code=404, detail=f"No data found for symbol {symbol}")

        # Parse stats
        return {
            "symbol": symbol,
            "status": stats.get("status", "unknown"),
            "last_update": stats.get("latest_timestamp"),
            "total_records": stats.get("total_records", 0),
            "timeframes": stats.get("timeframes_summary", {}),
            "data_quality": {
                "validation_rate": stats.get("validation_rate", 0),
                "quality_score": stats.get("quality_score", 0),
                "health": "excellent" if stats.get("quality_score", 0) > 0.9 else "good"
            },
            "backfill_status": stats.get("backfill_status", "unknown")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting asset summary for {symbol}", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Error retrieving asset data")

@router.get("/{symbol}/candles")
async def get_asset_candles(
    symbol: str,
    timeframe: str = Query("1h"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get paginated candle data

    Args:
        symbol: Stock symbol
        timeframe: Candle timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
        limit: Number of candles to return (max 1000)
        offset: Pagination offset

    Returns:
        Paginated candles with OHLCV data
    """
    db = get_db()

    try:
        # Get historical data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Get candles using available method
        result = db.get_historical_data(
            symbol=symbol,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            timeframe=timeframe,
            limit=limit
        )

        if not result:
            raise HTTPException(status_code=404, detail=f"No candle data found for {symbol}/{timeframe}")

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "total_records": len(result),
            "candles": result,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": len(result)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting candles for {symbol}/{timeframe}", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Error retrieving candle data")

@router.get("/{symbol}/status")
async def get_asset_status(symbol: str):
    """
    Get current asset data status and freshness

    Args:
        symbol: Stock symbol

    Returns:
        Status information including freshness and backfill state
    """
    db = get_db()

    try:
        stats = db.get_symbol_stats(symbol)
        if not stats or stats.get("total_records", 0) == 0:
            raise HTTPException(status_code=404, detail=f"No data found for symbol {symbol}")

        # Get backfill status for common timeframes
        backfill_statuses = {}
        for tf in ['1m', '5m', '15m', '1h', '1d']:
            backfill_statuses[tf] = db.get_backfill_status(symbol, tf) or {"status": "unknown"}

        return {
            "symbol": symbol,
            "total_records": stats.get("total_records", 0),
            "last_update": stats.get("latest_timestamp"),
            "data_age_minutes": stats.get("data_age_minutes", 0),
            "status": stats.get("status", "unknown"),
            "backfill_status": backfill_statuses,
            "quality_metrics": {
                "validation_rate": stats.get("validation_rate", 0),
                "quality_score": stats.get("quality_score", 0)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for {symbol}", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail="Error retrieving status data")
