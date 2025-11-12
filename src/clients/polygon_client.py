"""Polygon.io API client for US stocks and crypto"""

import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Timeframe to Polygon API mapping
TIMEFRAME_MAP = {
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
    - Intraday: 5m, 15m, 30m, 1h, 4h
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
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str
    ) -> List[Dict]:
        """
        Fetch OHLCV data for a symbol and timeframe from Polygon.
        
        Supports both stocks and crypto with same method.
        
        Returns list of candles:
        [{'t': timestamp_ms, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume, 'n': count}]
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL') or crypto pair (e.g., 'BTCUSD')
            timeframe: Timeframe code (e.g., '1h', '5m', '1d', '1w')
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
        
        Returns:
            List of OHLCV candles
        
        Raises:
            ValueError: If API error, rate limit, or invalid timeframe
        """
        # Get timeframe parameters
        tf_params = self._get_timeframe_params(timeframe)
        multiplier = tf_params['multiplier']
        timespan = tf_params['timespan']
        
        # v2 endpoint pattern: /v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start}/{end}
        url = f"{self.base_url}/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start}/{end}"
        
        params = {
            "apiKey": self.api_key,
            "sort": "asc",
            "limit": 50000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    
                    if response.status == 429:
                        logger.warning(f"Rate limited (429) for {symbol} ({timeframe}) - {start} to {end}")
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
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
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
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
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
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
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
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
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
