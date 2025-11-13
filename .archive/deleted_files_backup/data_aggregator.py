"""
Data Aggregator Service
Unified interface for fetching from multiple data sources with fallback logic
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio

from src.clients.polygon_client import PolygonClient
from src.clients.binance_client import BinanceClient
from src.clients.yahoo_client import YahooClient
from src.services.structured_logging import StructuredLogger
from src.services.circuit_breaker import get_circuit_breaker


class DataAggregator:
    """Unified data aggregator with multi-source support and fallback"""
    
    # Symbol mapping across sources
    SYMBOL_MAPPING = {
        'BTC': {
            'polygon': 'BTCUSD',
            'binance': 'BTCUSDT',
            'yahoo': 'BTC-USD'
        },
        'ETH': {
            'polygon': 'ETHUSD',
            'binance': 'ETHUSDT',
            'yahoo': 'ETH-USD'
        },
        'AAPL': {
            'polygon': 'AAPL',
            'binance': None,
            'yahoo': 'AAPL'
        },
        'MSFT': {
            'polygon': 'MSFT',
            'binance': None,
            'yahoo': 'MSFT'
        },
    }
    
    # Default source priority per asset class
    SOURCE_PRIORITY = {
        'stock': ['polygon', 'yahoo'],
        'crypto': ['binance', 'polygon', 'yahoo'],
        'etf': ['polygon', 'yahoo']
    }
    
    def __init__(self, config=None):
        """
        Initialize Data Aggregator
        
        Args:
            config: AppConfig instance
        """
        self.config = config
        self.polygon = PolygonClient(config.polygon_api_key if config else None)
        self.binance = BinanceClient(config)
        self.yahoo = YahooClient()
        self.logger = StructuredLogger(__name__)
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        source_priority: Optional[List[str]] = None
    ) -> Dict:
        """
        Fetch OHLCV from best available source with fallback
        
        Args:
            symbol: User symbol (e.g., 'BTC', 'AAPL')
            asset_class: 'stock', 'crypto', or 'etf'
            timeframe: '5m', '1h', '1d', etc.
            start_date: Start datetime
            end_date: End datetime
            source_priority: List of sources to try in order
            
        Returns:
            Dict with keys:
            {
                'success': bool,
                'source': str,
                'symbol': str,
                'candles': DataFrame,
                'metadata': {
                    'records_fetched': int,
                    'fetch_time_ms': int,
                    'quality_score': float
                },
                'error': str (if failed)
            }
        """
        if source_priority is None:
            source_priority = self.SOURCE_PRIORITY.get(asset_class, ['polygon', 'yahoo'])
        
        result = {
            'success': False,
            'source': None,
            'symbol': symbol,
            'asset_class': asset_class,
            'candles': pd.DataFrame(),
            'metadata': {},
            'error': None
        }
        
        for source in source_priority:
            self.logger.info(
                "data_aggregator_fetching",
                symbol=symbol,
                asset_class=asset_class,
                source=source
            )
            
            try:
                # Get source-specific symbol mapping
                source_symbol = self._map_symbol(symbol, source)
                
                if not source_symbol:
                    self.logger.warning(
                        "symbol_not_available",
                        symbol=symbol,
                        source=source
                    )
                    continue
                
                # Fetch from source
                import time
                start_time = time.time()
                
                if source == 'polygon':
                    candles = await self._fetch_polygon(
                        source_symbol, timeframe, start_date, end_date
                    )
                elif source == 'binance':
                    candles = await self._fetch_binance(
                        source_symbol, timeframe, start_date, end_date
                    )
                elif source == 'yahoo':
                    candles = await self._fetch_yahoo(
                        source_symbol, timeframe, start_date, end_date
                    )
                else:
                    continue
                
                fetch_time_ms = int((time.time() - start_time) * 1000)
                
                if candles.empty:
                    self.logger.warning(
                        "no_data_from_source",
                        symbol=symbol,
                        source=source
                    )
                    continue
                
                # Validate data quality
                quality_score = self._validate_candles(candles)
                
                if quality_score < 0.7:
                    self.logger.warning(
                        "low_quality_data",
                        symbol=symbol,
                        source=source,
                        quality_score=quality_score
                    )
                    continue
                
                # Success
                result['success'] = True
                result['source'] = source
                result['candles'] = candles
                result['metadata'] = {
                    'records_fetched': len(candles),
                    'fetch_time_ms': fetch_time_ms,
                    'quality_score': quality_score,
                    'source_symbol': source_symbol
                }
                
                self.logger.info(
                    "data_aggregator_success",
                    symbol=symbol,
                    source=source,
                    records=len(candles),
                    fetch_time_ms=fetch_time_ms
                )
                
                return result
            
            except Exception as e:
                self.logger.warning(
                    "fetch_source_error",
                    symbol=symbol,
                    source=source,
                    error=str(e)[:100]
                )
                continue
        
        # All sources failed
        result['error'] = f"Could not fetch data for {symbol} from any source"
        self.logger.error(
            "data_aggregator_failed",
            symbol=symbol,
            asset_class=asset_class,
            attempted_sources=source_priority
        )
        
        return result
    
    async def fetch_crypto_microstructure(
        self,
        symbol: str,
        timeframe: str
    ) -> Dict:
        """
        Fetch Binance-specific crypto microstructure metrics
        
        Args:
            symbol: Binance symbol (e.g., 'BTCUSDT')
            timeframe: Timeframe
            
        Returns:
            Dict with crypto-specific fields
        """
        try:
            # Get current metrics
            open_interest = await self.binance.get_open_interest(symbol)
            funding_rate = await self.binance.get_funding_rate(symbol)
            
            # Get liquidation data for period
            now = datetime.utcnow()
            period_start = now - timedelta(hours=1)
            
            liquidations = await self.binance.get_liquidation_data(
                symbol, period_start, now
            )
            
            return {
                'success': True,
                'open_interest': open_interest,
                'funding_rate': funding_rate,
                'liquidations_long': liquidations.get('long'),
                'liquidations_short': liquidations.get('short'),
                'taker_buy_volume': None,  # Requires full klines data
                'taker_sell_volume': None
            }
        
        except Exception as e:
            self.logger.error(
                "crypto_microstructure_error",
                symbol=symbol,
                error=str(e)
            )
            
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _fetch_polygon(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch from Polygon with circuit breaker"""
        breaker = get_circuit_breaker('polygon-api')
        
        async def fetch():
            return await self.polygon.get_aggs(
                symbol=symbol,
                timeframe=self._convert_timeframe('polygon', timeframe),
                start_date=start_date,
                end_date=end_date
            )
        
        return await breaker.call(fetch) or pd.DataFrame()
    
    async def _fetch_binance(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch from Binance with circuit breaker"""
        breaker = get_circuit_breaker('binance-api')
        
        async def fetch():
            return await self.binance.get_klines(
                symbol=symbol,
                interval=timeframe,
                start_time=start_date,
                end_time=end_date
            )
        
        return await breaker.call(fetch) or pd.DataFrame()
    
    async def _fetch_yahoo(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch from Yahoo Finance with circuit breaker"""
        breaker = get_circuit_breaker('yahoo-api')
        
        async def fetch():
            return await self.yahoo.get_historical(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=timeframe
            )
        
        return await breaker.call(fetch) or pd.DataFrame()
    
    def _map_symbol(self, user_symbol: str, source: str) -> Optional[str]:
        """Map user symbol to source-specific format"""
        user_symbol = user_symbol.upper()
        
        if user_symbol not in self.SYMBOL_MAPPING:
            return user_symbol  # Return as-is if not mapped
        
        mapping = self.SYMBOL_MAPPING[user_symbol]
        return mapping.get(source)
    
    def _convert_timeframe(self, source: str, timeframe: str) -> str:
        """Convert timeframe to source-specific format"""
        # For now, most sources use the same format
        return timeframe
    
    def _validate_candles(self, candles: pd.DataFrame) -> float:
        """
        Validate candle data quality
        
        Returns:
            Quality score 0-1.0
        """
        if candles.empty:
            return 0.0
        
        score = 1.0
        
        # Check for required columns
        required = ['open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in candles.columns:
                return 0.0
        
        # Check for NaN values
        nan_count = candles[required].isna().sum().sum()
        if nan_count > 0:
            score -= (nan_count / (len(candles) * len(required))) * 0.3
        
        # Check OHLC relationships
        invalid_candles = 0
        for idx, row in candles.iterrows():
            if (row['high'] < row['low'] or
                row['high'] < row['open'] or
                row['high'] < row['close'] or
                row['low'] > row['open'] or
                row['low'] > row['close'] or
                row['volume'] < 0):
                invalid_candles += 1
        
        if invalid_candles > 0:
            score -= (invalid_candles / len(candles)) * 0.3
        
        # Check for extreme outliers (±100% moves)
        if len(candles) > 1:
            returns = (candles['close'] / candles['close'].shift(1) - 1).abs()
            outliers = (returns > 1.0).sum()
            if outliers > 0:
                score -= (outliers / len(returns)) * 0.1
        
        return max(0.0, score)
