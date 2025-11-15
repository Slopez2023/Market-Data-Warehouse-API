"""Polygon.io API client for US stocks and crypto"""

import aiohttp
import logging
import asyncio
import time
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Rate limiting: Polygon free tier = 150 req/min = 2.5 req/sec
_RATE_LIMIT_DELAY = 1.0 / 2.5  # ~0.4 seconds between requests
_last_request_time = 0.0
_request_lock = None

async def _get_request_lock():
    """Get or create the request lock"""
    global _request_lock
    if _request_lock is None:
        _request_lock = asyncio.Lock()
    return _request_lock

async def _rate_limit_wait():
    """Wait if necessary to maintain rate limit"""
    global _last_request_time
    lock = await _get_request_lock()
    async with lock:
        elapsed = time.time() - _last_request_time
        if elapsed < _RATE_LIMIT_DELAY:
            await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
        _last_request_time = time.time()

# Timeframe to Polygon API mapping
TIMEFRAME_MAP = {
    '1m': {'multiplier': 1, 'timespan': 'minute'},
    '5m': {'multiplier': 5, 'timespan': 'minute'},
    '15m': {'multiplier': 15, 'timespan': 'minute'},
    '30m': {'multiplier': 30, 'timespan': 'minute'},
    '1h': {'multiplier': 1, 'timespan': 'hour'},
    '4h': {'multiplier': 4, 'timespan': 'hour'},
    '1d': {'multiplier': 1, 'timespan': 'day'},
    '1w': {'multiplier': 1, 'timespan': 'week'},
}


class PolygonClient:
    """
    Polygon.io API client for US stocks and crypto.
    
    Supports multiple timeframes:
    - Intraday: 1m, 5m, 15m, 30m, 1h, 4h
    - Daily: 1d
    - Weekly: 1w
    
    Works with:
    - Stocks (daily aggregates and intraday)
    - Crypto (24h OHLCV in USD)
    
    Rate limit: 150 requests/minute
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io/v2"
        self.crypto_base_url = "https://api.polygon.io/v1"
        
        # Phase 3: Rate limit tracking for monitoring
        self.rate_limited_count = 0
        self.total_requests = 0
    
    @staticmethod
    def _get_timeframe_params(timeframe: str) -> Dict[str, any]:
        """
        Get Polygon API parameters for a given timeframe.
        
        Args:
            timeframe: Timeframe code (e.g., '1h', '5m', '1d')
        
        Returns:
            Dictionary with multiplier and timespan
        
        Raises:
            ValueError: If timeframe is not supported
        """
        if timeframe not in TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {list(TIMEFRAME_MAP.keys())}")
        return TIMEFRAME_MAP[timeframe]
    
    @staticmethod
    def _normalize_crypto_symbol(symbol: str, is_crypto: bool = False) -> str:
        """
        Normalize crypto symbols for Polygon API.
        
        Polygon crypto endpoint expects format like BTC (ticker only, no currency pair).
        This function converts:
        - BTC-USD → BTC
        - BTCUSD → BTC
        - BTC → BTC (already normalized)
        
        Args:
            symbol: Symbol (e.g., 'BTC-USD', 'BTCUSD', 'BTC')
            is_crypto: Whether this is a crypto symbol
            
        Returns:
            Normalized symbol for Polygon API
        """
        if is_crypto:
            # Remove any currency pair suffix
            # BTC-USD → BTC, BTCUSD → BTC
            symbol = symbol.split('-')[0]  # Remove -USD, -USDT, etc.
            
            # If still has USD/USDT suffix, remove it
            for suffix in ['USD', 'USDT', 'USDC', 'BUSD', 'GBP', 'EUR']:
                if symbol.endswith(suffix) and len(symbol) > len(suffix):
                    symbol = symbol[:-len(suffix)]
                    break
        
        return symbol
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=300)
    )
    async def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
        is_crypto: bool = False,
        adjusted: bool = False
    ) -> List[Dict]:
        """
        Fetch OHLCV data for a symbol and timeframe from Polygon.
        
        Supports both stocks and crypto with same method.
        
        Returns list of candles:
        [{'t': timestamp_ms, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume, 'n': count}]
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL') or crypto pair (e.g., 'BTC-USD', 'BTCUSD')
            timeframe: Timeframe code (e.g., '1h', '5m', '1d', '1w')
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
            is_crypto: Whether this is a crypto symbol (auto-detected if not specified)
        
        Returns:
            List of OHLCV candles
        
        Raises:
            ValueError: If API error, rate limit, or invalid timeframe
        """
        # Apply rate limiting
        await _rate_limit_wait()
        
        # Auto-detect crypto if not specified
        if not is_crypto:
            is_crypto = '-' in symbol or any(crypto in symbol.upper() for crypto in ['BTC', 'ETH', 'USDT', 'USDC'])
        
        # Normalize crypto symbols (BTC-USD → BTCUSD)
        normalized_symbol = self._normalize_crypto_symbol(symbol, is_crypto)
        
        # Get timeframe parameters
        tf_params = self._get_timeframe_params(timeframe)
        multiplier = tf_params['multiplier']
        timespan = tf_params['timespan']
        
        # v2 endpoint pattern: /v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start}/{end}
        url = f"{self.base_url}/aggs/ticker/{normalized_symbol}/range/{multiplier}/{timespan}/{start}/{end}"
        
        params = {
            "apiKey": self.api_key,
            "sort": "asc",
            "limit": 50000,
            "adjusted": str(adjusted).lower()
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                self.total_requests += 1
                async with session.get(url, params=params, timeout=30) as response:
                    
                    if response.status == 429:
                        self.rate_limited_count += 1
                        logger.warning(f"Rate limited (429) for {symbol} ({timeframe}) - Retry {self.rate_limited_count}")
                        raise ValueError("Rate limited (429) - too many requests")
                    
                    if response.status != 200:
                        logger.error(f"API error {response.status} for {symbol} ({timeframe})")
                        raise ValueError(f"API returned status {response.status}")
                    
                    data = await response.json()
                    
                    # Check for API-level errors
                    if data.get("status") == "ERROR":
                        logger.warning(f"Polygon API error for {symbol} ({timeframe}): {data.get('message')}")
                        return []
                    
                    # Extract results or return empty list
                    results = data.get("results", [])
                    logger.info(f"Fetched {len(results)} candles for {symbol} ({timeframe}) from {start} to {end}")
                    return results
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching {symbol} ({timeframe}): {e}")
            raise ValueError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching {symbol} ({timeframe}): {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=300)
    )
    async def fetch_daily_range(
        self,
        symbol: str,
        start: str,
        end: str
    ) -> List[Dict]:
        """
        Fetch daily OHLCV from Polygon (legacy method).
        
        DEPRECATED: Use fetch_range(symbol, '1d', start, end) instead.
        
        Returns list of candles:
        [{'t': timestamp_ms, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume, 'n': count}]
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
        
        Raises:
            ValueError: If API error or rate limit
        """
        return await self.fetch_range(symbol, '1d', start, end)
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=300)
    )
    async def fetch_crypto_daily_range(
        self,
        symbol: str,
        start: str,
        end: str
    ) -> List[Dict]:
        """
        Fetch crypto daily OHLCV from Polygon (legacy method).
        
        DEPRECATED: Use fetch_range(symbol, '1d', start, end) instead.
        
        Polygon crypto endpoint format: BTCUSD, ETHGBP, etc.
        
        Returns list of candles in same format as stocks.
        
        Args:
            symbol: Crypto pair (e.g., 'BTCUSD', 'ETHGBP')
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
        
        Returns:
            List of OHLCV candles
        
        Raises:
            ValueError: If API error
        """
        return await self.fetch_range(symbol, '1d', start, end)
    
    async def fetch_ticker_details(self, symbol: str) -> Optional[Dict]:
        """Get ticker details (name, type, etc.)"""
        # Use reference endpoint for ticker details
        url = f"https://api.polygon.io/v3/reference/tickers/{symbol}"
        
        params = {
            "apiKey": self.api_key
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("results")
                    return None
        except Exception as e:
            logger.error(f"Error fetching ticker details for {symbol}: {e}")
            return None
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=300)
    )
    async def fetch_dividends(
        self,
        symbol: str,
        start: str,
        end: str
    ) -> List[Dict]:
        """
        Fetch historical dividends for a stock.
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
        
        Returns:
            List of dividend records from Polygon API
        
        Raises:
            ValueError: If API error or rate limit
        """
        url = "https://api.polygon.io/v2/reference/dividends"
        
        params = {
            "ticker": symbol,
            "from": start,
            "to": end,
            "apiKey": self.api_key,
            "limit": 1000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    
                    if response.status == 429:
                        logger.warning(f"Rate limited (429) fetching dividends for {symbol}")
                        raise ValueError("Rate limited (429) - too many requests")
                    
                    if response.status != 200:
                        logger.error(f"API error {response.status} fetching dividends for {symbol}")
                        raise ValueError(f"API returned status {response.status}")
                    
                    data = await response.json()
                    
                    # Check for API-level errors
                    if data.get("status") == "ERROR":
                        logger.warning(f"Polygon API error for {symbol} dividends: {data.get('message')}")
                        return []
                    
                    results = data.get("results", [])
                    logger.info(f"Fetched {len(results)} dividends for {symbol} ({start} to {end})")
                    return results
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching dividends for {symbol}: {e}")
            raise ValueError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching dividends for {symbol}: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=300)
    )
    async def fetch_stock_splits(
        self,
        symbol: str,
        start: str,
        end: str
    ) -> List[Dict]:
        """
        Fetch historical stock splits for a stock.
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
        
        Returns:
            List of stock split records from Polygon API
        
        Raises:
            ValueError: If API error or rate limit
        """
        url = "https://api.polygon.io/v2/reference/splits"
        
        params = {
            "ticker": symbol,
            "from": start,
            "to": end,
            "apiKey": self.api_key,
            "limit": 1000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    
                    if response.status == 429:
                        logger.warning(f"Rate limited (429) fetching splits for {symbol}")
                        raise ValueError("Rate limited (429) - too many requests")
                    
                    if response.status != 200:
                        logger.error(f"API error {response.status} fetching splits for {symbol}")
                        raise ValueError(f"API returned status {response.status}")
                    
                    data = await response.json()
                    
                    # Check for API-level errors
                    if data.get("status") == "ERROR":
                        logger.warning(f"Polygon API error for {symbol} splits: {data.get('message')}")
                        return []
                    
                    results = data.get("results", [])
                    logger.info(f"Fetched {len(results)} splits for {symbol} ({start} to {end})")
                    return results
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching splits for {symbol}: {e}")
            raise ValueError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching splits for {symbol}: {e}")
            raise
    
    # Alias for backward compatibility
    async def fetch_splits(self, symbol: str, start: str, end: str) -> List[Dict]:
        """Alias for fetch_stock_splits for backward compatibility."""
        return await self.fetch_stock_splits(symbol, start, end)
    
    async def fetch_news(self, symbol: str, start: str, end: str) -> List[Dict]:
        """
        Fetch news articles for a symbol.
        
        Args:
            symbol: Stock ticker
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
        
        Returns:
            List of news articles from Polygon API
        """
        url = "https://api.polygon.io/v2/reference/news"
        
        params = {
            "ticker": symbol,
            "published_utc.gte": f"{start}T00:00:00Z",
            "published_utc.lte": f"{end}T23:59:59Z",
            "apiKey": self.api_key,
            "limit": 1000,
            "sort": "published_utc"
        }
        
        all_articles = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    
                    if response.status == 429:
                        logger.warning(f"Rate limited (429) fetching news for {symbol}")
                        return []
                    
                    if response.status != 200:
                        logger.error(f"API error {response.status} fetching news for {symbol}")
                        return []
                    
                    data = await response.json()
                    
                    if data.get("status") == "ERROR":
                        logger.warning(f"Polygon API error for {symbol} news: {data.get('message')}")
                        return []
                    
                    results = data.get("results", [])
                    logger.info(f"Fetched {len(results)} news articles for {symbol} ({start} to {end})")
                    return results
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching news for {symbol}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching news for {symbol}: {e}")
            return []
    
    async def fetch_earnings(self, symbol: str, start: str, end: str) -> List[Dict]:
        """
        Fetch earnings announcements for a symbol.
        
        Args:
            symbol: Stock ticker
            start: Start date (YYYY-MM-DD)
            end: End date (YYYY-MM-DD)
        
        Returns:
            List of earnings records from Polygon API
        """
        url = "https://api.polygon.io/v1/reference/financials"
        
        params = {
            "ticker": symbol,
            "apiKey": self.api_key,
            "limit": 1000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    
                    if response.status == 429:
                        logger.warning(f"Rate limited (429) fetching earnings for {symbol}")
                        return []
                    
                    if response.status != 200:
                        logger.error(f"API error {response.status} fetching earnings for {symbol}")
                        return []
                    
                    data = await response.json()
                    
                    if data.get("status") == "ERROR":
                        logger.warning(f"Polygon API error for {symbol} earnings: {data.get('message')}")
                        return []
                    
                    results = data.get("results", [])
                    logger.info(f"Fetched {len(results)} earnings records for {symbol} ({start} to {end})")
                    return results
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching earnings for {symbol}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching earnings for {symbol}: {e}")
            return []
    
    async def fetch_options_chain(self, symbol: str, date: datetime) -> Optional[Dict]:
        """
        Fetch options chain snapshot for a symbol on a specific date.
        
        Args:
            symbol: Stock ticker
            date: Date for options chain (datetime.date)
        
        Returns:
            Options chain data with current price, or None if not found
        """
        date_str = date.strftime('%Y-%m-%d')
        url = f"https://api.polygon.io/v3/snapshot/options/{symbol}"
        
        params = {
            "apiKey": self.api_key,
            "order": "desc",
            "limit": 10000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    
                    if response.status == 429:
                        logger.warning(f"Rate limited (429) fetching options for {symbol}")
                        return None
                    
                    if response.status == 404:
                        logger.info(f"No options chain found for {symbol}")
                        return None
                    
                    if response.status != 200:
                        logger.error(f"API error {response.status} fetching options for {symbol}")
                        return None
                    
                    data = await response.json()
                    
                    if data.get("status") == "ERROR":
                        logger.warning(f"Polygon API error for {symbol} options: {data.get('message')}")
                        return None
                    
                    results = data.get("results", {})
                    logger.info(f"Fetched options chain snapshot for {symbol}")
                    return results
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching options for {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching options for {symbol}: {e}")
            return None
