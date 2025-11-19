"""Multi-source client with fallback logic"""

import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import asyncio

from src.clients.polygon_client import PolygonClient
from src.clients.yahoo_client import YahooFinanceClient
from src.services.validation_service import ValidationService

logger = logging.getLogger(__name__)


class MultiSourceClient:
    """
    Multi-source OHLCV client with validation-driven fallback.
    
    Tier 1: Polygon.io (primary, paid)
    Tier 2: Yahoo Finance (secondary, free fallback)
    Tier 3: Alpha Vantage (tertiary, for archives)
    
    Fallback triggers:
    - Polygon timeout → Try Yahoo
    - Polygon rate limited → Wait then retry, then Yahoo
    - Polygon returns bad quality → Try Yahoo, compare
    - All else fails → Return empty with note
    
    All data tagged with source for audit trail.
    """
    
    def __init__(
        self,
        polygon_api_key: str,
        validation_service: ValidationService = None,
        enable_fallback: bool = True,
        fallback_threshold: float = 0.85
    ):
        """
        Initialize multi-source client.
        
        Args:
            polygon_api_key: Polygon.io API key
            validation_service: Optional validation service for quality checks
            enable_fallback: Whether to enable fallback sources
            fallback_threshold: Quality score threshold to trigger fallback (0.0-1.0)
        """
        self.polygon = PolygonClient(polygon_api_key)
        self.yahoo = YahooFinanceClient()
        self.validation_service = validation_service or ValidationService()
        self.enable_fallback = enable_fallback
        self.fallback_threshold = fallback_threshold
        
        # Stats
        self.stats = {
            'polygon_primary': 0,
            'yahoo_fallback': 0,
            'both_failed': 0,
            'fallback_better': 0,
            'primary_better': 0,
            'equal': 0
        }
    
    async def fetch_range(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
        is_crypto: bool = False,
        validate: bool = False,
        use_fallback: bool = None
    ) -> Tuple[List[Dict], str]:
        """
        Fetch OHLCV data with optional fallback.
        
        Tries primary source first, falls back to secondary if needed.
        
        Args:
            symbol: Stock ticker or crypto pair
            timeframe: Candle timeframe ('1d', '1h', '5m', etc.)
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
            is_crypto: Whether symbol is crypto
            validate: Whether to validate and trigger fallback on poor quality
            use_fallback: Force fallback (override enable_fallback setting)
        
        Returns:
            Tuple of (candles, source) where source is 'polygon', 'yahoo', or None
            candles: List of OHLCV dicts in Polygon format (millisecond timestamps)
            source: Which source provided the data
        
        Example:
            candles, source = await client.fetch_range('AAPL', '1d', '2025-01-01', '2025-01-31')
            print(f"Got {len(candles)} candles from {source}")
        """
        use_fallback = use_fallback if use_fallback is not None else self.enable_fallback
        
        # Try primary source
        primary_candles, primary_quality = await self._try_polygon(
            symbol, timeframe, start, end, is_crypto, validate
        )
        
        if primary_candles:
            # Primary succeeded
            if validate and primary_quality < self.fallback_threshold and use_fallback:
                # Quality is poor, try fallback
                logger.info(f"Primary quality {primary_quality:.2f} < {self.fallback_threshold}, trying fallback")
                fallback_candles, fallback_quality = await self._try_yahoo(
                    symbol, timeframe, start, end, is_crypto, validate
                )
                
                if fallback_candles:
                    # Compare and use better
                    better = self._compare_sources(
                        symbol, primary_candles, fallback_candles,
                        primary_quality, fallback_quality
                    )
                    
                    if better == 'fallback':
                        self.stats['fallback_better'] += 1
                        return fallback_candles, 'yahoo'
                    elif better == 'primary':
                        self.stats['primary_better'] += 1
                        return primary_candles, 'polygon'
                    else:  # equal
                        self.stats['equal'] += 1
                        return primary_candles, 'polygon'  # Prefer primary on tie
            
            # Primary is good, use it
            self.stats['polygon_primary'] += 1
            return primary_candles, 'polygon'
        
        # Primary failed, try fallback
        if use_fallback:
            logger.info(f"Primary source failed for {symbol}, trying Yahoo fallback")
            fallback_candles, _ = await self._try_yahoo(
                symbol, timeframe, start, end, is_crypto, validate
            )
            
            if fallback_candles:
                self.stats['yahoo_fallback'] += 1
                return fallback_candles, 'yahoo'
        
        # All sources failed
        logger.error(f"All sources failed for {symbol}")
        self.stats['both_failed'] += 1
        return [], None
    
    async def _try_polygon(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
        is_crypto: bool,
        validate: bool
    ) -> Tuple[List[Dict], float]:
        """
        Try to fetch from Polygon.
        
        Returns:
            Tuple of (candles, quality_score)
            quality_score is 1.0 if validate=False, else calculated from ValidationService
        """
        try:
            candles = await self.polygon.fetch_range(
                symbol, timeframe, start, end, is_crypto
            )
            
            if not candles:
                logger.debug(f"Polygon returned empty for {symbol}")
                return [], 0.0
            
            # Validate if requested
            if validate:
                quality = self._calculate_quality(candles)
                return candles, quality
            else:
                return candles, 1.0  # Assume good if not validating
        
        except asyncio.TimeoutError:
            logger.warning(f"Polygon timeout for {symbol}")
            return [], 0.0
        except Exception as e:
            logger.warning(f"Polygon fetch failed for {symbol}: {e}")
            return [], 0.0
    
    async def _try_yahoo(
        self,
        symbol: str,
        timeframe: str,
        start: str,
        end: str,
        is_crypto: bool,
        validate: bool
    ) -> Tuple[List[Dict], float]:
        """
        Try to fetch from Yahoo Finance.
        
        Returns:
            Tuple of (candles, quality_score)
        """
        try:
            # Note: Yahoo doesn't handle all timeframes well, 1d is best
            if timeframe != '1d':
                logger.warning(f"Yahoo Finance fallback for {symbol}: intraday data ({timeframe}) may be unreliable")
            
            candles = await self.yahoo.fetch_range(
                symbol, start, end, timeframe, is_crypto
            )
            
            if not candles:
                logger.debug(f"Yahoo returned empty for {symbol}")
                return [], 0.0
            
            # Validate if requested
            if validate:
                quality = self._calculate_quality(candles)
                return candles, quality
            else:
                return candles, 1.0
        
        except Exception as e:
            logger.warning(f"Yahoo fetch failed for {symbol}: {e}")
            return [], 0.0
    
    def _calculate_quality(self, candles: List[Dict]) -> float:
        """
        Calculate average quality score for a list of candles.
        
        Returns: Average quality score (0.0-1.0)
        """
        if not candles:
            return 0.0
        
        qualities = []
        for candle in candles:
            quality_score, _ = self.validation_service.validate_candle(
                symbol='',  # Not used for quality calculation
                candle=candle
            )
            qualities.append(quality_score)
        
        return sum(qualities) / len(qualities) if qualities else 0.0
    
    def _compare_sources(
        self,
        symbol: str,
        primary_candles: List[Dict],
        fallback_candles: List[Dict],
        primary_quality: float,
        fallback_quality: float
    ) -> str:
        """
        Compare two data sources and determine which is better.
        
        Returns: 'primary', 'fallback', or 'equal'
        """
        # If quality difference is large, use better one
        quality_diff = fallback_quality - primary_quality
        
        if quality_diff > 0.05:  # Fallback at least 5% better
            logger.info(f"Fallback quality ({fallback_quality:.2f}) > primary ({primary_quality:.2f}) for {symbol}")
            return 'fallback'
        elif quality_diff < -0.05:  # Primary at least 5% better
            logger.info(f"Primary quality ({primary_quality:.2f}) > fallback ({fallback_quality:.2f}) for {symbol}")
            return 'primary'
        else:  # Within 5%, consider equal
            logger.info(f"Sources roughly equal for {symbol}: primary={primary_quality:.2f}, fallback={fallback_quality:.2f}")
            return 'equal'
    
    async def close(self):
        """Close all connections"""
        await self.yahoo.close()
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        total = sum(self.stats.values())
        return {
            **self.stats,
            'total_fetches': total,
            'polygon_rate': f"{self.stats['polygon_primary'] / total * 100:.1f}%" if total > 0 else "0%",
            'yahoo_rate': f"{self.stats['yahoo_fallback'] / total * 100:.1f}%" if total > 0 else "0%",
            'failure_rate': f"{self.stats['both_failed'] / total * 100:.1f}%" if total > 0 else "0%"
        }
