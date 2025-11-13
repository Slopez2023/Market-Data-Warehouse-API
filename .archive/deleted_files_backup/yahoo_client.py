"""
Yahoo Finance API Client
Fallback data source for stocks and ETFs
Public API - no authentication required
"""

import aiohttp
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from decimal import Decimal
import logging

from src.services.structured_logging import StructuredLogger


class YahooClient:
    """Async Yahoo Finance client for stock/ETF data"""
    
    BASE_URL = "https://query1.finance.yahoo.com"
    
    # Yahoo Finance symbol format (ticker as-is)
    KNOWN_SYMBOLS = {
        'AAPL': 'AAPL',
        'MSFT': 'MSFT',
        'GOOGL': 'GOOGL',
        'AMZN': 'AMZN',
        'TSLA': 'TSLA',
        'BRK.B': 'BRK.B',
        'META': 'META',
        'NVDA': 'NVDA',
        'JPM': 'JPM',
    }
    
    # Interval mapping for Yahoo
    INTERVAL_MAPPING = {
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1h',
        '1d': '1d',
        '1wk': '1wk',
        '1mo': '1mo'
    }
    
    def __init__(self, timeout: int = 10):
        """
        Initialize Yahoo Finance client
        
        Args:
            timeout: Request timeout in seconds
        """
        self.logger = StructuredLogger(__name__)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_historical(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data from Yahoo Finance
        
        Args:
            symbol: Yahoo Finance symbol (e.g., 'AAPL')
            start_date: Start date
            end_date: End date
            interval: Timeframe ('1d', '1wk', '1mo', or intraday)
            
        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        if interval not in self.INTERVAL_MAPPING:
            self.logger.warning(
                "yahoo_unsupported_interval",
                symbol=symbol,
                interval=interval
            )
            return pd.DataFrame()
        
        try:
            # Yahoo Finance API endpoint
            params = {
                'symbols': symbol,
                'range': self._calculate_range(start_date, end_date),
                'interval': self.INTERVAL_MAPPING[interval],
                'includePrePost': 'false',
                'events': 'div|splits|earnings',
                'corsDomain': 'finance.yahoo.com',
                '.tsrc': 'finance'
            }
            
            url = f"{self.BASE_URL}/v10/finance/quoteSummary/{symbol}"
            
            # Use alternative endpoint for historical data
            url = f"{self.BASE_URL}/v8/finance/chart/{symbol}"
            params_chart = {
                'period1': int(start_date.timestamp()),
                'period2': int(end_date.timestamp()),
                'interval': self.INTERVAL_MAPPING[interval],
                'events': 'div|splits'
            }
            
            async with self.session.get(
                url,
                params=params_chart,
                timeout=self.timeout,
                headers={'User-Agent': 'Mozilla/5.0'}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(
                        "yahoo_historical_error",
                        symbol=symbol,
                        status=response.status,
                        error=error_text[:200]
                    )
                    return pd.DataFrame()
                
                data = await response.json()
                
                # Parse Yahoo Finance response
                if 'chart' not in data or 'result' not in data['chart']:
                    self.logger.warning(
                        "yahoo_no_data",
                        symbol=symbol
                    )
                    return pd.DataFrame()
                
                result = data['chart']['result'][0]
                
                if 'timestamp' not in result or 'indicators' not in result:
                    return pd.DataFrame()
                
                timestamps = result['timestamp']
                quotes = result['indicators']['quote'][0]
                
                # Build DataFrame
                df = pd.DataFrame({
                    'timestamp': pd.to_datetime(timestamps, unit='s', utc=True),
                    'open': pd.to_numeric(quotes.get('open', []), errors='coerce'),
                    'high': pd.to_numeric(quotes.get('high', []), errors='coerce'),
                    'low': pd.to_numeric(quotes.get('low', []), errors='coerce'),
                    'close': pd.to_numeric(quotes.get('close', []), errors='coerce'),
                    'volume': pd.to_numeric(quotes.get('volume', []), errors='coerce')
                })
                
                # Remove rows with NaN in critical columns
                df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
                
                if df.empty:
                    return df
                
                self.logger.info(
                    "yahoo_historical_fetched",
                    symbol=symbol,
                    interval=interval,
                    records=len(df)
                )
                
                return df
        
        except asyncio.TimeoutError:
            self.logger.warning(
                "yahoo_historical_timeout",
                symbol=symbol
            )
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(
                "yahoo_historical_exception",
                symbol=symbol,
                error=str(e)
            )
            return pd.DataFrame()
    
    async def validate_symbol(self, symbol: str) -> bool:
        """
        Validate if symbol exists on Yahoo Finance
        
        Args:
            symbol: Yahoo Finance symbol
            
        Returns:
            True if symbol is valid, False otherwise
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            # Try to fetch quote data
            url = f"{self.BASE_URL}/v10/finance/quoteSummary/{symbol}"
            params = {
                'modules': 'price'
            }
            
            async with self.session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=5),
                headers={'User-Agent': 'Mozilla/5.0'}
            ) as response:
                return response.status == 200
        
        except Exception as e:
            self.logger.warning(
                "yahoo_validate_symbol_error",
                symbol=symbol,
                error=str(e)
            )
            return False
    
    def map_symbol(self, base_symbol: str) -> Optional[str]:
        """
        Map user symbol to Yahoo Finance symbol format
        
        Args:
            base_symbol: User-provided symbol
            
        Returns:
            Yahoo Finance symbol or None if not found
        """
        return self.KNOWN_SYMBOLS.get(base_symbol.upper())
    
    def _calculate_range(self, start_date: datetime, end_date: datetime) -> str:
        """
        Calculate range string for Yahoo Finance API
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Range string ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
        """
        days = (end_date - start_date).days
        
        if days <= 1:
            return '1d'
        elif days <= 5:
            return '5d'
        elif days <= 30:
            return '1mo'
        elif days <= 90:
            return '3mo'
        elif days <= 180:
            return '6mo'
        elif days <= 365:
            return '1y'
        elif days <= 730:
            return '2y'
        elif days <= 1825:
            return '5y'
        else:
            return '10y'


# Import asyncio for timeout handling
import asyncio
