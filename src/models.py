"""Pydantic models for request/response validation"""

from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from src.config import ALLOWED_TIMEFRAMES, DEFAULT_TIMEFRAMES


class OHLCVData(BaseModel):
    """Single OHLCV candle"""
    time: datetime
    symbol: str
    timeframe: str = "1d"
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
    
    @validator('timeframe')
    def validate_timeframe(cls, v):
        """Validate timeframe is allowed"""
        if v not in ALLOWED_TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {v}. Allowed: {ALLOWED_TIMEFRAMES}")
        return v
    
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


class TrackedSymbol(BaseModel):
    """Tracked symbol in database"""
    id: int
    symbol: str
    asset_class: str
    active: bool
    timeframes: List[str] = DEFAULT_TIMEFRAMES
    date_added: Optional[datetime] = None
    last_backfill: Optional[datetime] = None
    backfill_status: str = "pending"
    
    @validator('timeframes')
    def validate_timeframes(cls, v):
        """Validate that all timeframes are allowed"""
        if not v:
            raise ValueError("At least one timeframe must be specified")
        invalid = [tf for tf in v if tf not in ALLOWED_TIMEFRAMES]
        if invalid:
            raise ValueError(f"Invalid timeframes: {invalid}. Allowed: {ALLOWED_TIMEFRAMES}")
        return v


class AddSymbolRequest(BaseModel):
    """Request to add a new symbol"""
    symbol: str = Field(..., min_length=1, max_length=20)
    asset_class: str = Field(default="stock", description="stock, crypto, etf, etc.")


class UpdateSymbolTimeframesRequest(BaseModel):
    """Request to update a symbol's configured timeframes"""
    timeframes: List[str] = Field(..., description="List of timeframes to fetch (e.g., ['1h', '1d', '4h'])")
    
    @validator('timeframes')
    def validate_timeframes(cls, v):
        """Validate that all timeframes are allowed"""
        if not v:
            raise ValueError("At least one timeframe must be specified")
        invalid = [tf for tf in v if tf not in ALLOWED_TIMEFRAMES]
        if invalid:
            raise ValueError(f"Invalid timeframes: {invalid}. Allowed: {ALLOWED_TIMEFRAMES}")
        # Remove duplicates and sort for consistency
        return sorted(list(set(v)))


class APIKeyResponse(BaseModel):
    """Response containing newly generated API key"""
    api_key: str = Field(..., description="Raw API key - save this, it won't be shown again")
    name: str
    created_at: datetime
    key_preview: str = Field(..., description="First 8 characters for reference")


class APIKeyMetadata(BaseModel):
    """Metadata about an API key"""
    id: int
    name: str
    active: bool
    created_at: datetime
    last_used: Optional[datetime] = None
    request_count: int


class APIKeyListResponse(BaseModel):
    """Response for listing API keys"""
    id: int
    name: str
    active: bool
    created_at: datetime
    last_used: Optional[datetime] = None
    request_count: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class APIKeyCreateResponse(BaseModel):
    """Response when creating a new API key"""
    id: int
    api_key: str = Field(..., description="Raw key - save this, it won't be shown again")
    key_preview: str = Field(..., description="First 12 characters for reference")
    name: str
    created_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AuditLogEntry(BaseModel):
    """Single audit log entry for API key usage"""
    id: int
    endpoint: str
    method: str
    status_code: int
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class APIKeyAuditResponse(BaseModel):
    """Response for API key audit log"""
    key_id: int
    entries: List[AuditLogEntry]
    total: int
    limit: int
    offset: int


class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key"""
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name for the key")


class UpdateAPIKeyRequest(BaseModel):
    """Request to update an API key status"""
    active: bool = Field(..., description="Whether the key should be active")
