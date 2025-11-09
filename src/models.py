"""Pydantic models for request/response validation"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
from decimal import Decimal


class OHLCVData(BaseModel):
    """Single OHLCV candle"""
    time: datetime
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    source: str = "polygon"
    validated: bool = False
    quality_score: Decimal = Decimal("0.00")
    validation_notes: Optional[str] = None
    gap_detected: bool = False
    volume_anomaly: bool = False
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            datetime: lambda v: v.isoformat()
        }


class HistoricalDataResponse(BaseModel):
    """Response for historical data endpoint"""
    symbol: str
    start_date: str
    end_date: str
    count: int
    data: List[OHLCVData]


class StatusResponse(BaseModel):
    """Response for /api/v1/status endpoint"""
    api_version: str
    status: str
    database: dict
    data_quality: dict


class HealthResponse(BaseModel):
    """Response for /health endpoint"""
    status: str
    timestamp: str
    scheduler_running: bool
