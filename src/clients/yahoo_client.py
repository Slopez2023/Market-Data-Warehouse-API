"""Yahoo Finance API client - Fallback source for OHLCV data"""

import aiohttp
import logging
import asyncio
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
import json

logger = logging.getLogger(__name__)

# Rate limiting for Yahoo Finance (estimated ~100-200 req/min)
_RATE_LIMIT_DELAY = 0.5  # ~2 requests per second
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


class YahooFinanceClient:
    """
    Yahoo Finance API client for stocks, crypto, and ETFs.
    
    Used as fallback when primary source (Polygon) fails or returns poor quality data.
    
    Supports:
    - US stocks (e.g., AAPL, MSFT)
    - Crypto (e.g., BTC-USD, ETH-USD)
    - ETFs (e.g., SPY, QQQ)
    
    Daily data quality: Good (matches institutional sources)
    Intraday data: Available but less reliable than Polygon
    Rate limit: ~100-200 req/min (estimated, unofficial)
    Cost: FREE
    
    Note: This is an unofficial API wrapper - no SLA. Use as fallback only.
    """
    
    def __init__(self):
        self.base_url = "https://query1.finance.yahoo.com/v10/finance/quoteSummary"
        self.chart_base_url = "https://query1.finance.yahoo.com/v10/finance/chart"
        self.session = None
        
        # Stats for monitoring
        self.request_count = 0
        self.failure_count = 0
        self.rate_limited_count = 0
    
    async def __aenter__(self):
        """Context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.session:
            await self.session.close()
    
    async def fetch_range(
        self,
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "1d",
        is_crypto: bool = False
    ) -> List[Dict]:
        """
        Fetch OHLCV data from Yahoo Finance.
        
        Returns data in same format as PolygonClient for compatibility:
        [{'t': timestamp_ms, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume}]
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL') or crypto (e.g., 'BTC-USD')
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
            timeframe: Candle timeframe ('1d' recommended, '1h'/'5m' available but unreliable)
            is_crypto: Whether symbol is crypto (auto-detected from symbol if not specified)
        
        Returns:
            List of OHLCV candles in millisecond timestamps
            Empty list if fetch fails
        
        Raises:
            ValueError: If arguments are invalid
            aiohttp.ClientError: If network error occurs
        """
        if not symbol or not start or not end:
            raise ValueError("symbol, start, and end are required")
        
        # Create session if needed
        if self.session is None:
            self.session = aiohttp.ClientSession()
        
        try:
            # Auto-detect crypto from symbol
            if is_crypto or '-' in symbol.upper() or symbol.upper() in ['BTC', 'ETH', 'XRP', 'ADA']:
                # Normalize crypto symbol
                if not symbol.endswith('-USD') and not symbol.endswith('-USDT'):
                    symbol = f"{symbol}-USD" if '-' not in symbol else symbol
            
            # Convert timeframe to Yahoo interval
            interval = self._timeframe_to_interval(timeframe)
            
            # Parse dates
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
            
            # Convert to Unix timestamps
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int(end_date.timestamp())
            
            # Fetch from Yahoo
            candles = await self._fetch_chart(
                symbol,
                start_timestamp,
                end_timestamp,
                interval
            )
            
            logger.info(f"Fetched {len(candles)} candles for {symbol} from Yahoo Finance")
            return candles
        
        except ValueError as e:
            logger.error(f"Invalid arguments for Yahoo Finance fetch: {e}")
            raise
        except Exception as e:
            logger.error(f"Error fetching {symbol} from Yahoo Finance: {e}")
            self.failure_count += 1
            return []
    
    async def _fetch_chart(
        self,
        symbol: str,
        start_timestamp: int,
        end_timestamp: int,
        interval: str
    ) -> List[Dict]:
        """
        Fetch chart data from Yahoo Finance API.
        
        Args:
            symbol: Ticker symbol
            start_timestamp: Start time as Unix timestamp
            end_timestamp: End time as Unix timestamp
            interval: Candle interval ('1d', '1h', '5m', etc.)
        
        Returns:
            List of OHLCV candles
        """
        await _rate_limit_wait()
        self.request_count += 1
        
        params = {
            'interval': interval,
            'period1': start_timestamp,
            'period2': end_timestamp
        }
        
        url = f"{self.chart_base_url}/{symbol}"
        
        try:
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 429:  # Rate limited
                    self.rate_limited_count += 1
                    logger.warning(f"Yahoo Finance rate limited for {symbol}")
                    raise aiohttp.ClientError("Rate limited by Yahoo Finance")
                
                if response.status != 200:
                    logger.warning(f"Yahoo Finance returned {response.status} for {symbol}")
                    raise aiohttp.ClientError(f"HTTP {response.status}")
                
                data = await response.json()
                
                # Parse response
                candles = self._parse_chart_response(data, symbol)
                return candles
        
        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching {symbol} from Yahoo Finance")
            raise aiohttp.ClientError("Timeout")
        except Exception as e:
            logger.error(f"Error fetching chart data for {symbol}: {e}")
            raise
    
    def _parse_chart_response(self, data: Dict, symbol: str) -> List[Dict]:
        """
        Parse Yahoo Finance chart response.
        
        Response format:
        {
            "chart": {
                "result": [{
                    "timestamp": [unix_ts, ...],
                    "indicators": {
                        "quote": [{
                            "open": [o, ...],
                            "high": [h, ...],
                            "low": [l, ...],
                            "close": [c, ...],
                            "volume": [v, ...]
                        }]
                    }
                }]
            }
        }
        """
        candles = []
        
        try:
            result = data.get('chart', {}).get('result', [])
            if not result:
                logger.warning(f"No result in Yahoo Finance response for {symbol}")
                return candles
            
            result = result[0]
            timestamps = result.get('timestamp', [])
            indicators = result.get('indicators', {}).get('quote', [])
            
            if not indicators:
                logger.warning(f"No indicators in Yahoo Finance response for {symbol}")
                return candles
            
            quote = indicators[0]
            opens = quote.get('open', [])
            highs = quote.get('high', [])
            lows = quote.get('low', [])
            closes = quote.get('close', [])
            volumes = quote.get('volume', [])
            
            # Build candles
            for i, timestamp in enumerate(timestamps):
                # Skip if any required field is None/null
                if (i >= len(opens) or opens[i] is None or
                    i >= len(highs) or highs[i] is None or
                    i >= len(lows) or lows[i] is None or
                    i >= len(closes) or closes[i] is None or
                    i >= len(volumes) or volumes[i] is None):
                    continue
                
                candle = {
                    't': int(timestamp * 1000),  # Convert to milliseconds (Polygon format)
                    'o': float(opens[i]),
                    'h': float(highs[i]),
                    'l': float(lows[i]),
                    'c': float(closes[i]),
                    'v': int(volumes[i])
                }
                
                # Basic validation
                if self._validate_candle(candle):
                    candles.append(candle)
                else:
                    logger.debug(f"Skipped invalid candle for {symbol}: {candle}")
            
            logger.debug(f"Parsed {len(candles)} valid candles for {symbol}")
            return candles
        
        except Exception as e:
            logger.error(f"Error parsing Yahoo Finance response for {symbol}: {e}")
            return candles
    
    @staticmethod
    def _validate_candle(candle: Dict) -> bool:
        """
        Validate OHLCV constraints.
        
        Args:
            candle: Candle dict with o, h, l, c, v
        
        Returns:
            True if valid, False otherwise
        """
        try:
            o = candle.get('o', 0)
            h = candle.get('h', 0)
            l = candle.get('l', 0)
            c = candle.get('c', 0)
            v = candle.get('v', 0)
            
            # Check basic constraints
            if h < max(o, c) or l > min(o, c):
                return False
            
            if h < l or o <= 0 or c <= 0:
                return False
            
            return True
        except Exception:
            return False
    
    @staticmethod
    def _timeframe_to_interval(timeframe: str) -> str:
        """
        Convert timeframe code to Yahoo Finance interval.
        
        Args:
            timeframe: Timeframe code (e.g., '1d', '1h', '5m')
        
        Returns:
            Yahoo Finance interval string
        
        Note: Only 1d is reliably accurate. Intraday data from Yahoo is less reliable
        than Polygon and should be used only as fallback.
        """
        mapping = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '1d': '1d',
            '1wk': '1wk',
            '1mo': '1mo'
        }
        
        interval = mapping.get(timeframe, '1d')
        
        if timeframe != '1d':
            logger.warning(f"Yahoo Finance intraday data ({timeframe}) is less reliable. Use Polygon for production.")
        
        return interval
    
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    def get_stats(self) -> Dict:
        """Get client statistics"""
        return {
            'request_count': self.request_count,
            'failure_count': self.failure_count,
            'rate_limited_count': self.rate_limited_count,
            'success_rate': (
                (self.request_count - self.failure_count) / self.request_count * 100
                if self.request_count > 0
                else 0.0
            )
        }
