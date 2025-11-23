"""
Market Data API Client
A production-ready, thread-safe client for interacting with the Market Data Warehouse API.

Usage:
    from market_data_client import MarketDataClient
    
    client = MarketDataClient(
        api_url="http://localhost:8000",
        api_key="mdw_your_key_here"
    )
    
    data = client.get_historical_data("AAPL", timeframe="1d", start="2024-01-01", end="2024-12-31")
    print(data["data"])
"""

import os
import logging
import time
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import wraps
import json


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ========================= EXCEPTIONS =========================

class MarketDataClientError(Exception):
    """Base exception for Market Data Client"""
    pass


class AuthenticationError(MarketDataClientError):
    """Raised when API key is invalid or missing"""
    pass


class RateLimitError(MarketDataClientError):
    """Raised when API rate limit is exceeded"""
    pass


class ValidationError(MarketDataClientError):
    """Raised when request parameters are invalid"""
    pass


class APIConnectionError(MarketDataClientError):
    """Raised when connection to API fails"""
    pass


class APIError(MarketDataClientError):
    """Raised when API returns an error response"""
    pass


# ========================= DATA MODELS =========================

@dataclass
class Candle:
    """Single OHLCV candle"""
    time: str
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str
    validated: bool
    quality_score: float
    validation_notes: Optional[str] = None
    gap_detected: bool = False
    volume_anomaly: bool = False
    fetched_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Feature:
    """Quant feature record with computed indicators"""
    time: str
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    return_1d: float
    volatility_20: float
    volatility_50: float
    atr: float
    rolling_volume_20: int
    volume_ratio: float
    rolling_mean_10: float
    rolling_slope_10: float
    structure_label: str
    trend_direction: str
    volatility_regime: str
    trend_regime: str
    compression_regime: str
    quality_score: float
    validated: bool
    features_computed_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class HistoricalDataResponse:
    """Response from historical data endpoint"""
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    count: int
    data: List[Dict[str, Any]]
    
    @property
    def candles(self) -> List[Candle]:
        """Parse candles from response data"""
        return [Candle(**c) for c in self.data]


@dataclass
class QuantFeaturesResponse:
    """Response from quant features endpoint"""
    symbol: str
    timeframe: str
    records_returned: int
    date_range: Dict[str, str]
    features: List[Dict[str, Any]]
    timestamp: str
    
    @property
    def parsed_features(self) -> List[Feature]:
        """Parse features from response data"""
        return [Feature(**f) for f in self.features]


# ========================= RETRY DECORATOR =========================

def retry_on_exception(max_retries: int = 3, backoff_factor: float = 0.5):
    """
    Decorator to retry function on transient failures.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Exponential backoff multiplier (seconds)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (APIConnectionError, requests.ConnectionError, requests.Timeout) as e:
                    if attempt == max_retries - 1:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    
                    wait_time = backoff_factor * (2 ** attempt)
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed, "
                        f"retrying in {wait_time}s: {e}"
                    )
                    time.sleep(wait_time)
            
        return wrapper
    return decorator


# ========================= MAIN CLIENT =========================

class MarketDataClient:
    """
    Production-ready client for Market Data Warehouse API.
    
    Features:
    - Automatic retry with exponential backoff
    - Connection pooling with keep-alive
    - Request/response validation
    - Comprehensive error handling
    - Thread-safe operations
    - Structured logging
    
    Args:
        api_url: Base API URL (e.g., "http://localhost:8000")
        api_key: API authentication key
        timeout: Request timeout in seconds (default: 30)
        max_retries: Maximum retry attempts (default: 3)
        backoff_factor: Retry backoff factor (default: 0.5)
        verify_ssl: Verify SSL certificates (default: True)
    
    Raises:
        AuthenticationError: If API key is invalid
        APIConnectionError: If unable to connect to API
    """
    
    # Allowed timeframes
    ALLOWED_TIMEFRAMES = {'5m', '15m', '30m', '1h', '4h', '1d', '1w'}
    
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        verify_ssl: bool = True
    ):
        """Initialize Market Data Client with configuration and session setup"""
        
        # Get from env if not provided
        self.api_url = api_url or os.getenv("MARKET_DATA_API_URL", "http://localhost:8000")
        self.api_key = api_key or os.getenv("MARKET_DATA_API_KEY")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.verify_ssl = verify_ssl
        
        # Validate required parameters
        if not self.api_key:
            raise AuthenticationError(
                "API key is required. Provide via api_key parameter "
                "or MARKET_DATA_API_KEY environment variable"
            )
        
        # Normalize API URL
        self.api_url = self.api_url.rstrip('/')
        
        # Create session with retry strategy
        self.session = self._create_session()
        
        # Test connection
        self._test_connection()
        
        logger.info(f"MarketDataClient initialized: {self.api_url}")
    
    def _create_session(self) -> requests.Session:
        """Create requests session with retry strategy and connection pooling"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _test_connection(self) -> None:
        """Test API connectivity without authentication"""
        try:
            response = self.session.get(
                f"{self.api_url}/health",
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            logger.info("API connection test successful")
        except requests.RequestException as e:
            raise APIConnectionError(f"Failed to connect to API at {self.api_url}: {e}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication"""
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "MarketDataClient/1.0"
        }
    
    def _validate_timeframe(self, timeframe: str) -> str:
        """Validate timeframe is in allowed list"""
        timeframe = timeframe.lower()
        if timeframe not in self.ALLOWED_TIMEFRAMES:
            raise ValidationError(
                f"Invalid timeframe: {timeframe}. "
                f"Allowed: {', '.join(sorted(self.ALLOWED_TIMEFRAMES))}"
            )
        return timeframe
    
    def _validate_date_format(self, date_str: str) -> str:
        """Validate date is in YYYY-MM-DD format"""
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except ValueError:
            raise ValidationError(
                f"Invalid date format: {date_str}. Use YYYY-MM-DD"
            )
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to API with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., "/api/v1/historical/AAPL")
            params: Query parameters
            json_data: JSON request body
        
        Returns:
            Response JSON as dictionary
        
        Raises:
            AuthenticationError: If API key is invalid (401)
            RateLimitError: If rate limited (429)
            ValidationError: If request is invalid (400)
            APIError: If server returns error (5xx)
            APIConnectionError: If connection fails
        """
        url = f"{self.api_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=self._get_headers(),
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            # Handle HTTP errors
            if response.status_code == 401:
                raise AuthenticationError("Invalid API key. Check MARKET_DATA_API_KEY")
            elif response.status_code == 403:
                raise AuthenticationError("API key forbidden. Access denied")
            elif response.status_code == 429:
                raise RateLimitError("Rate limit exceeded. Please retry later")
            elif response.status_code == 400:
                detail = response.json().get("detail", "Bad request")
                raise ValidationError(f"Invalid request: {detail}")
            elif response.status_code >= 500:
                raise APIError(f"Server error ({response.status_code}): {response.text}")
            elif response.status_code >= 400:
                raise APIError(f"API error ({response.status_code}): {response.text}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.ConnectionError as e:
            raise APIConnectionError(f"Connection failed: {e}")
        except requests.Timeout:
            raise APIConnectionError(f"Request timeout after {self.timeout}s")
        except requests.RequestException as e:
            raise APIError(f"Request failed: {e}")
    
    @retry_on_exception(max_retries=3)
    def get_historical_data(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: str = None,
        end: str = None,
        validated_only: bool = True,
        min_quality: float = 0.85
    ) -> HistoricalDataResponse:
        """
        Fetch historical OHLCV data for a symbol.
        
        Args:
            symbol: Stock/crypto ticker (e.g., "AAPL", "BTC")
            timeframe: Candle timeframe (5m, 15m, 30m, 1h, 4h, 1d, 1w) - default: 1d
            start: Start date in YYYY-MM-DD format (required)
            end: End date in YYYY-MM-DD format (required)
            validated_only: Only return validated candles (default: True)
            min_quality: Minimum quality score 0.0-1.0 (default: 0.85)
        
        Returns:
            HistoricalDataResponse with candles
        
        Raises:
            ValidationError: If parameters are invalid
            APIError: If request fails
        
        Example:
            >>> client = MarketDataClient()
            >>> data = client.get_historical_data(
            ...     "AAPL",
            ...     timeframe="1d",
            ...     start="2024-01-01",
            ...     end="2024-12-31"
            ... )
            >>> print(f"Got {data.count} candles")
            >>> for candle in data.candles:
            ...     print(f"{candle.time}: {candle.close}")
        """
        # Validate inputs
        symbol = symbol.upper()
        timeframe = self._validate_timeframe(timeframe)
        
        if not start or not end:
            raise ValidationError("start and end dates are required")
        
        start = self._validate_date_format(start)
        end = self._validate_date_format(end)
        
        if min_quality < 0 or min_quality > 1:
            raise ValidationError("min_quality must be between 0.0 and 1.0")
        
        params = {
            "timeframe": timeframe,
            "start": start,
            "end": end,
            "validated_only": validated_only,
            "min_quality": min_quality
        }
        
        response = self._make_request("GET", f"/api/v1/historical/{symbol}", params=params)
        
        return HistoricalDataResponse(
            symbol=response["symbol"],
            timeframe=response["timeframe"],
            start_date=response["start_date"],
            end_date=response["end_date"],
            count=response["count"],
            data=response["data"]
        )
    
    @retry_on_exception(max_retries=3)
    def get_quant_features(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 500
    ) -> QuantFeaturesResponse:
        """
        Fetch AI-ready quant features for a symbol.
        
        Features include:
        - Returns: return_1h, return_1d
        - Volatility: volatility_20, volatility_50, atr
        - Volume: rolling_volume_20, volume_ratio
        - Trend: rolling_mean_10, rolling_slope_10
        - Structure: structure_label, trend_direction, hh, hl, lh, ll
        - Regimes: volatility_regime, trend_regime, compression_regime
        
        Args:
            symbol: Stock/crypto ticker (e.g., "AAPL", "BTC")
            timeframe: Candle timeframe (5m, 15m, 30m, 1h, 4h, 1d, 1w) - default: 1d
            start: Optional start date in YYYY-MM-DD format
            end: Optional end date in YYYY-MM-DD format
            limit: Max records to return 1-10000 (default: 500)
        
        Returns:
            QuantFeaturesResponse with computed features
        
        Raises:
            ValidationError: If parameters are invalid
            APIError: If request fails
        
        Example:
            >>> client = MarketDataClient()
            >>> features = client.get_quant_features("MSFT", timeframe="1h")
            >>> print(f"Got {features.records_returned} feature records")
            >>> for feature in features.parsed_features:
            ...     print(f"{feature.time}: {feature.volatility_20:.4f}")
        """
        symbol = symbol.upper()
        timeframe = self._validate_timeframe(timeframe)
        
        if start:
            start = self._validate_date_format(start)
        if end:
            end = self._validate_date_format(end)
        
        if limit < 1 or limit > 10000:
            raise ValidationError("limit must be between 1 and 10000")
        
        params = {
            "timeframe": timeframe,
            "limit": limit
        }
        
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        
        response = self._make_request("GET", f"/api/v1/features/quant/{symbol}", params=params)
        
        return QuantFeaturesResponse(
            symbol=response["symbol"],
            timeframe=response["timeframe"],
            records_returned=response["records_returned"],
            date_range=response["date_range"],
            features=response["features"],
            timestamp=response["timestamp"]
        )
    
    @retry_on_exception(max_retries=3)
    def get_data_quality(
        self,
        symbol: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Fetch data quality report for a symbol.
        
        Returns quality metrics including:
        - Validation rate, quality score
        - Gaps and anomalies detected
        - Recent fetch logs with timing
        
        Args:
            symbol: Stock/crypto ticker
            days: Number of days to analyze (1-365, default: 7)
        
        Returns:
            Dictionary with quality report
        
        Raises:
            ValidationError: If parameters are invalid
            APIError: If request fails
        
        Example:
            >>> client = MarketDataClient()
            >>> quality = client.get_data_quality("AAPL", days=30)
            >>> print(f"Avg validation rate: {quality['summary']['avg_validation_rate']}%")
        """
        symbol = symbol.upper()
        
        if days < 1 or days > 365:
            raise ValidationError("days must be between 1 and 365")
        
        params = {"days": days}
        
        return self._make_request("GET", f"/api/v1/data/quality/{symbol}", params=params)
    
    @retry_on_exception(max_retries=3)
    def get_status(self) -> Dict[str, Any]:
        """
        Get overall API status and database metrics.
        
        Returns:
            Dictionary with API status, symbol count, validation rates
        
        Example:
            >>> client = MarketDataClient()
            >>> status = client.get_status()
            >>> print(f"Available symbols: {status['database']['symbols_available']}")
            >>> print(f"Validation rate: {status['database']['validation_rate_pct']}%")
        """
        return self._make_request("GET", "/api/v1/status")
    
    @retry_on_exception(max_retries=3)
    def get_symbols(self) -> Dict[str, Any]:
        """
        Get list of all available symbols.
        
        Returns:
            Dictionary with symbol count and latest data timestamp
        
        Example:
            >>> client = MarketDataClient()
            >>> symbols = client.get_symbols()
            >>> print(f"Total symbols: {symbols['symbols_available']}")
        """
        return self._make_request("GET", "/api/v1/symbols")
    
    def health_check(self) -> bool:
        """
        Check if API is healthy (no authentication required).
        
        Returns:
            True if API is healthy, False otherwise
        
        Example:
            >>> client = MarketDataClient()
            >>> if client.health_check():
            ...     print("API is up and running")
        """
        try:
            response = self.session.get(
                f"{self.api_url}/health",
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            return response.status_code == 200
        except:
            return False
    
    def close(self) -> None:
        """Close HTTP session and cleanup resources"""
        self.session.close()
        logger.info("MarketDataClient session closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# ========================= HELPER FUNCTIONS =========================

def create_client(
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> MarketDataClient:
    """
    Factory function to create a Market Data Client.
    
    Reads from environment variables if not provided:
    - MARKET_DATA_API_URL
    - MARKET_DATA_API_KEY
    
    Args:
        api_url: API base URL (optional)
        api_key: API authentication key (optional)
        **kwargs: Additional arguments passed to MarketDataClient
    
    Returns:
        Initialized MarketDataClient instance
    
    Example:
        >>> client = create_client()
        >>> data = client.get_historical_data("AAPL", start="2024-01-01", end="2024-12-31")
    """
    return MarketDataClient(api_url=api_url, api_key=api_key, **kwargs)
