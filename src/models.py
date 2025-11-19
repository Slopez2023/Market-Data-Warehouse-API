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


class BackfillRequest(BaseModel):
    """Request to submit a backfill job"""
    symbols: List[str] = Field(..., min_items=1, max_items=100, description="List of symbols to backfill")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    timeframes: List[str] = Field(default=["1d"], description="List of timeframes to backfill")
    
    @validator('symbols')
    def validate_symbols(cls, v):
        """Validate symbols list"""
        if not v or len(v) == 0:
            raise ValueError("At least one symbol required")
        if len(v) > 100:
            raise ValueError("Maximum 100 symbols per request")
        return v
    
    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        """Validate date format"""
        from datetime import datetime as dt
        try:
            dt.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")
        return v
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validate start_date < end_date"""
        if 'start_date' in values:
            from datetime import datetime as dt
            start = dt.strptime(values['start_date'], '%Y-%m-%d')
            end = dt.strptime(v, '%Y-%m-%d')
            if start >= end:
                raise ValueError("Start date must be before end date")
        return v


class BackfillJobDetail(BaseModel):
    """Details of a single symbol-timeframe backfill"""
    symbol: str
    timeframe: str
    status: str = "pending"
    records_fetched: int = 0
    records_inserted: int = 0
    duration_seconds: Optional[int] = None


class BackfillJobStatus(BaseModel):
    """Response for backfill job status"""
    job_id: str
    status: str
    progress_pct: int = 0
    symbols_completed: int = 0
    symbols_total: int
    current_symbol: Optional[str] = None
    current_timeframe: Optional[str] = None
    total_records_fetched: int = 0
    total_records_inserted: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    error: Optional[str] = None
    details: List[BackfillJobDetail] = []
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class BackfillJobResponse(BaseModel):
    """Response when submitting a backfill job"""
    job_id: str
    status: str = "queued"
    symbols_count: int
    symbols: List[str]
    date_range: dict
    timeframes: List[str]
    timestamp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
