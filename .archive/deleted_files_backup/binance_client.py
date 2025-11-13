"""
Binance API Client
Fetches crypto market data and microstructure metrics from Binance
Public endpoints - no API key required for OHLCV data
"""

import aiohttp
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import logging

from src.config import AppConfig
from src.services.structured_logging import StructuredLogger


class BinanceClient:
    """Async Binance API client for crypto data"""
    
    # Binance API base URL
    BASE_URL = "https://fapi.binance.com"  # Futures API for funding rates, open interest
    SPOT_BASE_URL = "https://api.binance.com"  # Spot API for regular OHLCV
    
    # Public rate limits
    # Spot: 1200 requests per minute
    # Futures: 2400 requests per minute
    
    # Interval mapping
    INTERVAL_MAPPING = {
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '1h': '1h',
        '4h': '4h',
        '1d': '1d',
        '1w': '1w'
    }
    
    # Common crypto symbols
    CRYPTO_SYMBOLS = {
        'BTC': 'BTCUSDT',
        'ETH': 'ETHUSDT',
        'BNB': 'BNBUSDT',
        'XRP': 'XRPUSDT',
        'ADA': 'ADAUSDT',
        'SOL': 'SOLUSDT',
        'DOGE': 'DOGEUSDT',
        'AVAX': 'AVAXUSDT',
        'POLYGON': 'MATICUSDT',
        'LINK': 'LINKUSDT',
    }
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        Initialize Binance client
        
        Args:
            config: AppConfig instance (optional for public endpoints)
        """
        self.config = config
        self.api_key = config.binance_api_key if config else None
        self.api_secret = config.binance_api_secret if config else None
        self.logger = StructuredLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles from Binance Futures API
        
        Args:
            symbol: Binance symbol (e.g., 'BTCUSDT')
            interval: Timeframe ('5m', '1h', '1d', etc.)
            start_time: Start datetime
            end_time: End datetime
            limit: Max candles per request (max 1500)
            
        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        if interval not in self.INTERVAL_MAPPING:
            raise ValueError(f"Unsupported interval: {interval}")
        
        try:
            params = {
                'symbol': symbol,
                'interval': self.INTERVAL_MAPPING[interval],
                'limit': min(limit, 1500)
            }
            
            if start_time:
                params['startTime'] = int(start_time.timestamp() * 1000)
            if end_time:
                params['endTime'] = int(end_time.timestamp() * 1000)
            
            url = f"{self.BASE_URL}/fapi/v1/klines"
            
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(
                        "binance_klines_error",
                        symbol=symbol,
                        status=response.status,
                        error=error_text
                    )
                    return pd.DataFrame()
                
                data = await response.json()
                
                if not data:
                    return pd.DataFrame()
                
                # Parse response
                df = pd.DataFrame(data, columns=[
                    'timestamp', 'open', 'high', 'low', 'close', 'volume',
                    'close_time', 'quote_asset_volume', 'number_of_trades',
                    'taker_buy_base_volume', 'taker_buy_quote_volume', 'ignore'
                ])
                
                # Convert timestamp
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
                
                # Convert to numeric
                for col in ['open', 'high', 'low', 'close', 'volume']:
                    df[col] = pd.to_numeric(df[col])
                
                self.logger.info(
                    "binance_klines_fetched",
                    symbol=symbol,
                    interval=interval,
                    records=len(df)
                )
                
                return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        
        except asyncio.TimeoutError:
            self.logger.warning("binance_klines_timeout", symbol=symbol)
            return pd.DataFrame()
        except Exception as e:
            self.logger.error(
                "binance_klines_exception",
                symbol=symbol,
                error=str(e)
            )
            return pd.DataFrame()
    
    async def get_open_interest(
        self,
        symbol: str,
        period: str = '5m'
    ) -> Optional[Decimal]:
        """
        Get current open interest for perpetual contract
        
        Args:
            symbol: Binance symbol (e.g., 'BTCUSDT')
            period: Aggregation period ('5m', '15m', '30m', '1h')
            
        Returns:
            Open interest value as Decimal or None if failed
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            url = f"{self.BASE_URL}/fapi/v1/openInterest"
            params = {'symbol': symbol}
            
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                return Decimal(data.get('openInterest', 0))
        
        except Exception as e:
            self.logger.warning(
                "binance_open_interest_error",
                symbol=symbol,
                error=str(e)
            )
            return None
    
    async def get_funding_rate(
        self,
        symbol: str
    ) -> Optional[Decimal]:
        """
        Get current funding rate for perpetual contract
        
        Args:
            symbol: Binance symbol (e.g., 'BTCUSDT')
            
        Returns:
            Funding rate as Decimal or None if failed
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            url = f"{self.BASE_URL}/fapi/v1/fundingRate"
            params = {
                'symbol': symbol,
                'limit': 1
            }
            
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status != 200:
                    return None
                
                data = await response.json()
                if data and len(data) > 0:
                    return Decimal(data[0].get('fundingRate', 0))
                return None
        
        except Exception as e:
            self.logger.warning(
                "binance_funding_rate_error",
                symbol=symbol,
                error=str(e)
            )
            return None
    
    async def get_liquidation_data(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime
    ) -> Dict[str, Decimal]:
        """
        Get liquidation data for period
        
        Args:
            symbol: Binance symbol (e.g., 'BTCUSDT')
            start_time: Start datetime
            end_time: End datetime
            
        Returns:
            Dict with 'long' and 'short' liquidation volumes
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            url = f"{self.BASE_URL}/fapi/v1/allForceOrders"
            params = {
                'symbol': symbol,
                'startTime': int(start_time.timestamp() * 1000),
                'endTime': int(end_time.timestamp() * 1000),
                'limit': 1000
            }
            
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return {'long': Decimal(0), 'short': Decimal(0)}
                
                data = await response.json()
                
                long_volume = Decimal(0)
                short_volume = Decimal(0)
                
                for liquidation in data:
                    quantity = Decimal(liquidation.get('origQty', 0))
                    side = liquidation.get('side', '').upper()
                    
                    if side == 'BUY':  # Liquidated shorts
                        short_volume += quantity
                    elif side == 'SELL':  # Liquidated longs
                        long_volume += quantity
                
                return {
                    'long': long_volume,
                    'short': short_volume
                }
        
        except Exception as e:
            self.logger.warning(
                "binance_liquidation_data_error",
                symbol=symbol,
                error=str(e)
            )
            return {'long': Decimal(0), 'short': Decimal(0)}
    
    async def get_taker_volume(
        self,
        symbol: str,
        interval: str = '1h'
    ) -> Dict[str, Decimal]:
        """
        Get taker buy/sell volume from recent candles
        Uses the taker_buy_base_volume from klines
        
        Args:
            symbol: Binance symbol (e.g., 'BTCUSDT')
            interval: Timeframe for calculation
            
        Returns:
            Dict with 'buy' and 'sell' volumes
        """
        try:
            df = await self.get_klines(
                symbol=symbol,
                interval=interval,
                limit=100
            )
            
            if df.empty:
                return {'buy': Decimal(0), 'sell': Decimal(0)}
            
            # Note: Binance doesn't directly provide taker sell volume in klines
            # We estimate it as (total_volume - taker_buy_volume)
            # This is a limitation of the public API
            
            total_buy = Decimal(0)
            for record in df.itertuples():
                # We'll need to fetch the raw data with taker volumes
                pass
            
            # Return placeholder - should fetch from full klines data
            return {
                'buy': Decimal(0),
                'sell': Decimal(0)
            }
        
        except Exception as e:
            self.logger.warning(
                "binance_taker_volume_error",
                symbol=symbol,
                error=str(e)
            )
            return {'buy': Decimal(0), 'sell': Decimal(0)}
    
    def map_symbol(self, base_symbol: str) -> Optional[str]:
        """
        Map user symbol to Binance symbol format
        
        Args:
            base_symbol: User-provided symbol (e.g., 'BTC')
            
        Returns:
            Binance symbol (e.g., 'BTCUSDT') or None if not found
        """
        return self.CRYPTO_SYMBOLS.get(base_symbol.upper())
    
    async def validate_symbol(self, symbol: str) -> bool:
        """
        Check if symbol is tradeable on Binance Futures
        
        Args:
            symbol: Binance symbol (e.g., 'BTCUSDT')
            
        Returns:
            True if symbol exists, False otherwise
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            url = f"{self.BASE_URL}/fapi/v1/exchangeInfo"
            
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status != 200:
                    return False
                
                data = await response.json()
                symbols = [s['symbol'] for s in data.get('symbols', [])]
                
                return symbol in symbols
        
        except Exception as e:
            self.logger.warning(
                "binance_validate_symbol_error",
                symbol=symbol,
                error=str(e)
            )
            return False


# Import asyncio for timeout handling
import asyncio
