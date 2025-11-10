"""Polygon.io API client for US stocks"""

import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class PolygonClient:
    """
    Polygon.io API client for US stocks and crypto.
    
    Supports:
    - Stocks (daily aggregates)
    - Crypto (24h OHLCV in USD)
    
    Rate limit: 150 requests/minute (more than enough for daily backfill)
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io/v2"
        self.crypto_base_url = "https://api.polygon.io/v1"
    
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
        Fetch daily OHLCV from Polygon.
        
        Returns list of candles:
        [{'t': timestamp_ms, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume, 'n': count}]
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
        
        Raises:
            ValueError: If API error or rate limit
        """
        # v2 endpoint pattern: /v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start}/{end}
        url = f"{self.base_url}/aggs/ticker/{symbol}/range/1/day/{start}/{end}"
        
        params = {
            "apiKey": self.api_key,
            "sort": "asc",
            "limit": 50000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    
                    if response.status == 429:
                        logger.warning(f"Rate limited (429) for {symbol} - {start} to {end}")
                        raise ValueError("Rate limited (429) - too many requests")
                    
                    if response.status != 200:
                        logger.error(f"API error {response.status} for {symbol}")
                        raise ValueError(f"API returned status {response.status}")
                    
                    data = await response.json()
                    
                    # Check for API-level errors
                    if data.get("status") == "ERROR":
                        logger.warning(f"Polygon API error: {data.get('message')} for {symbol}")
                        return []
                    
                    # Extract results or return empty list
                    results = data.get("results", [])
                    logger.info(f"Fetched {len(results)} candles for {symbol} ({start} to {end})")
                    return results
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching {symbol}: {e}")
            raise ValueError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching {symbol}: {e}")
            raise
    
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
        Fetch crypto daily OHLCV from Polygon.
        
        Polygon crypto endpoint format: BTCUSD, ETHGBP, etc.
        
        Returns list of candles in same format as stocks.
        
        Args:
            symbol: Crypto pair (e.g., 'BTCUSD', 'ETHGBP')
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
        
        Raises:
            ValueError: If API error
        """
        # Crypto endpoint: /v1/open-close/{cryptoticker}/{date}
        # Need to fetch each day individually or use aggs
        # Use aggs endpoint for consistency: /v2/aggs/ticker/{cryptoticker}/range/{multiplier}/{timespan}/{start}/{end}
        
        url = f"{self.base_url}/aggs/ticker/{symbol}/range/1/day/{start}/{end}"
        
        params = {
            "apiKey": self.api_key,
            "sort": "asc",
            "limit": 50000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    
                    if response.status == 429:
                        logger.warning(f"Rate limited (429) for {symbol} - {start} to {end}")
                        raise ValueError("Rate limited (429) - too many requests")
                    
                    if response.status != 200:
                        logger.error(f"API error {response.status} for {symbol}")
                        raise ValueError(f"API returned status {response.status}")
                    
                    data = await response.json()
                    
                    if data.get("status") == "ERROR":
                        logger.warning(f"Polygon API error for {symbol}: {data.get('message')}")
                        return []
                    
                    results = data.get("results", [])
                    logger.info(f"Fetched {len(results)} crypto candles for {symbol} ({start} to {end})")
                    return results
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching crypto {symbol}: {e}")
            raise ValueError(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching crypto {symbol}: {e}")
            raise
    
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
