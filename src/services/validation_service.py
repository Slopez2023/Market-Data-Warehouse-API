"""Data validation service for OHLCV candles"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, List
from decimal import Decimal

logger = logging.getLogger(__name__)


class ValidationService:
    """
    Validates OHLCV candles and detects anomalies.
    
    Checks:
    1. OHLCV constraints (high >= max(open,close), low <= min(open,close), prices > 0)
    2. Price movement anomalies (>500% single day move)
    3. Gap detection (splits, halts, data issues)
    4. Volume anomalies
    
    Returns quality_score (0.0-1.0) and flags for further review.
    """
    
    def __init__(self):
        self.max_price_move_pct = 500.0  # Reasonable intraday move threshold
        self.volume_anomaly_threshold_high = 10.0  # 10x median = anomaly
        self.volume_anomaly_threshold_low = 0.1  # <10% median = possible delisting
        self.gap_threshold_pct = 10.0  # Large gap flag threshold
    
    def validate_candle(
        self,
        symbol: str,
        candle: Dict,
        prev_close: Decimal = None,
        median_volume: int = None
    ) -> Tuple[float, Dict]:
        """
        Validate a single OHLCV candle.
        
        Args:
            symbol: Stock ticker
            candle: {time, open, high, low, close, volume}
            prev_close: Previous day's close (for gap detection)
            median_volume: Historical median volume (for anomaly detection)
        
        Returns:
            (quality_score: float, metadata: dict)
        """
        quality_score = 1.0
        validation_notes = []
        gap_detected = False
        volume_anomaly = False
        
        try:
            # Extract fields
            open_price = Decimal(str(candle.get('o', 0)))
            high_price = Decimal(str(candle.get('h', 0)))
            low_price = Decimal(str(candle.get('l', 0)))
            close_price = Decimal(str(candle.get('c', 0)))
            volume = int(candle.get('v', 0))
            
            # Check 1: OHLCV Constraints
            if not self._check_ohlcv_constraints(open_price, high_price, low_price, close_price):
                quality_score -= 0.5
                validation_notes.append("failed_ohlcv_constraints")
                logger.warning(f"{symbol}: OHLCV constraints violated (O={open_price}, H={high_price}, L={low_price}, C={close_price})")
            
            # Check 2: Price move anomaly (single day)
            if not self._check_price_move(open_price, close_price, high_price, low_price):
                quality_score -= 0.3
                validation_notes.append("extreme_price_move")
                logger.warning(f"{symbol}: Extreme price move detected")
            
            # Check 3: Gap detection (vs previous close)
            if prev_close is not None:
                gap_pct = self._calculate_gap_pct(prev_close, open_price)
                if gap_pct > self.gap_threshold_pct:
                    # Check if it's a weekend (normal, expected)
                    # Polygon timestamp is in milliseconds
                    ts = candle.get('t')
                    if isinstance(ts, str):
                        candle_time = datetime.fromisoformat(ts)
                    else:
                        # Assume milliseconds from Polygon API
                        candle_time = datetime.utcfromtimestamp(ts / 1000)
                    if not self._is_weekend_gap(candle_time):
                        gap_detected = True
                        quality_score -= 0.2
                        validation_notes.append(f"large_gap_{gap_pct:.1f}pct")
                        logger.info(f"{symbol}: Large gap detected ({gap_pct:.1f}%) - possible split/halt")
            
            # Check 4: Volume anomaly
            if median_volume is not None and volume > 0:
                volume_ratio = volume / median_volume if median_volume > 0 else 1.0
                
                if volume_ratio > self.volume_anomaly_threshold_high:
                    volume_anomaly = True
                    quality_score -= 0.1
                    validation_notes.append(f"volume_anomaly_high_{volume_ratio:.1f}x")
                    logger.info(f"{symbol}: High volume anomaly ({volume_ratio:.1f}x median)")
                
                elif volume_ratio < self.volume_anomaly_threshold_low:
                    volume_anomaly = True
                    quality_score -= 0.15
                    validation_notes.append(f"volume_anomaly_low_{volume_ratio:.2f}x")
                    logger.info(f"{symbol}: Low volume anomaly ({volume_ratio:.2f}x median) - possible delisting")
            
            # Clamp quality score to valid range
            quality_score = max(0.0, min(1.0, quality_score))
        
        except Exception as e:
            logger.error(f"Error validating candle for {symbol}: {e}")
            quality_score = 0.0
            validation_notes.append(f"validation_exception: {str(e)}")
        
        metadata = {
            "quality_score": round(quality_score, 2),
            "validated": quality_score >= 0.85,  # Validation threshold
            "validation_notes": ";".join(validation_notes) if validation_notes else None,
            "gap_detected": gap_detected,
            "volume_anomaly": volume_anomaly
        }
        
        return quality_score, metadata
    
    def _check_ohlcv_constraints(
        self,
        open_price: Decimal,
        high_price: Decimal,
        low_price: Decimal,
        close_price: Decimal
    ) -> bool:
        """Check strict OHLCV constraints"""
        try:
            # High must bracket all prices
            if high_price < max(open_price, close_price):
                return False
            
            # Low must bracket all prices
            if low_price > min(open_price, close_price):
                return False
            
            # No zero or negative prices
            if open_price <= 0 or close_price <= 0:
                return False
            
            # High >= Low (always)
            if high_price < low_price:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error in _check_ohlcv_constraints: {e}")
            return False
    
    def _check_price_move(self, open_price: Decimal, close_price: Decimal, high_price: Decimal = None, low_price: Decimal = None) -> bool:
        """Check for unreasonable single-day price move (>500%)"""
        try:
            if open_price <= 0:
                return False
            
            # Check close-to-open move
            move_pct = abs((close_price - open_price) / open_price) * 100
            if move_pct > self.max_price_move_pct:
                return False
            
            # Also check high-low range if provided
            if high_price is not None and low_price is not None and low_price > 0:
                range_pct = ((high_price - low_price) / low_price) * 100
                if range_pct > self.max_price_move_pct:
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Error in _check_price_move: {e}")
            return False
    
    def _calculate_gap_pct(self, prev_close, open_price: Decimal) -> float:
        """Calculate gap percentage from previous close to open"""
        try:
            # Ensure both are Decimal for comparison
            prev_close = Decimal(str(prev_close))
            open_price = Decimal(str(open_price))
            
            if prev_close <= 0:
                return 0.0
            gap = abs((open_price - prev_close) / prev_close) * 100
            return float(gap)
        except Exception as e:
            logger.error(f"Error in _calculate_gap_pct: {e}")
            return 0.0
    
    def _is_weekend_gap(self, candle_time: datetime) -> bool:
        """Check if gap is due to weekend (Friday close to Monday open)"""
        try:
            # Monday = 0, Sunday = 6
            weekday = candle_time.weekday()
            
            # If Monday and gap is expected, it's normal
            if weekday == 0:  # Monday
                return True
            
            return False
        except Exception as e:
            logger.error(f"Error in _is_weekend_gap: {e}")
            return False
    
    def calculate_median_volume(self, candles: List[Dict]) -> int:
        """Calculate median volume from list of candles"""
        try:
            if not candles:
                return 0
            
            volumes = sorted([int(c.get('v', 0)) for c in candles if c.get('v', 0) > 0])
            if not volumes:
                return 0
            
            mid = len(volumes) // 2
            if len(volumes) % 2 == 0:
                return int((volumes[mid - 1] + volumes[mid]) / 2)
            else:
                return volumes[mid]
        except Exception as e:
            logger.error(f"Error calculating median volume: {e}")
            return 0
    
    def validate_dividend(self, symbol: str, dividend: Dict) -> Tuple[bool, Dict]:
        """
        Validate dividend record from Polygon API.
        
        Args:
            symbol: Stock ticker
            dividend: Dividend dict from API
        
        Returns:
            (is_valid, metadata)
        """
        metadata = {
            'symbol': symbol,
            'validation_errors': [],
            'warnings': []
        }
        
        try:
            # Required fields
            ex_date = dividend.get('ex_dividend_date')
            amount = dividend.get('cash_amount')
            
            if not ex_date:
                metadata['validation_errors'].append("Missing ex_dividend_date")
            
            if amount is None:
                metadata['validation_errors'].append("Missing cash_amount")
            else:
                # Validate amount
                try:
                    amount_float = float(amount)
                    if amount_float < 0:
                        metadata['validation_errors'].append("Negative dividend amount")
                    if amount_float > 100:
                        metadata['warnings'].append(f"Unusually high dividend: ${amount_float}")
                except (ValueError, TypeError):
                    metadata['validation_errors'].append("Invalid cash_amount format")
            
            # Optional field validation
            pay_date = dividend.get('pay_date')
            record_date = dividend.get('record_date')
            
            # Sanity check: ex_date <= record_date <= pay_date
            if ex_date and record_date:
                if ex_date > record_date:
                    metadata['warnings'].append("ex_date > record_date (unusual)")
            
        except Exception as e:
            logger.error(f"Error validating dividend for {symbol}: {e}")
            metadata['validation_errors'].append(f"Validation exception: {str(e)}")
        
        is_valid = len(metadata['validation_errors']) == 0
        return is_valid, metadata
    
    def validate_split(self, symbol: str, split: Dict) -> Tuple[bool, Dict]:
        """
        Validate stock split record from Polygon API.
        
        Args:
            symbol: Stock ticker
            split: Stock split dict from API
        
        Returns:
            (is_valid, metadata)
        """
        metadata = {
            'symbol': symbol,
            'validation_errors': [],
            'warnings': []
        }
        
        try:
            # Required fields
            execution_date = split.get('execution_date')
            split_from = split.get('split_from')
            split_to = split.get('split_to')
            
            if not execution_date:
                metadata['validation_errors'].append("Missing execution_date")
            
            if split_from is None or split_to is None:
                metadata['validation_errors'].append("Missing split_from or split_to")
            else:
                # Validate split ratio
                try:
                    from_int = int(split_from)
                    to_int = int(split_to)
                    
                    if from_int <= 0 or to_int <= 0:
                        metadata['validation_errors'].append("split_from/split_to must be positive")
                    
                    # Sanity check: splits rarely exceed 100:1 or 1:100
                    ratio = to_int / from_int if from_int > 0 else 0
                    if ratio > 100 or ratio < 0.01:
                        metadata['warnings'].append(f"Unusual split ratio: {from_int}:{to_int}")
                
                except (ValueError, TypeError):
                    metadata['validation_errors'].append("Invalid split_from/split_to format")
        
        except Exception as e:
            logger.error(f"Error validating split for {symbol}: {e}")
            metadata['validation_errors'].append(f"Validation exception: {str(e)}")
        
        is_valid = len(metadata['validation_errors']) == 0
        return is_valid, metadata
