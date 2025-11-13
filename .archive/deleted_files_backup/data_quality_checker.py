"""Phase 2.3: Data sanity checks and quality validation"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """
    Performs comprehensive data quality checks on batches of candles.
    Catches anomalies, inconsistencies, and gaps before insertion.
    """
    
    def __init__(self):
        """Initialize quality checker"""
        self.checks_performed = 0
        self.issues_found = 0
    
    def check_batch(
        self,
        symbol: str,
        candles: List[Dict],
        prev_close: Optional[Decimal] = None
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Comprehensive quality check on a batch of candles.
        
        Args:
            symbol: Stock ticker
            candles: List of OHLCV candles
            prev_close: Previous day's close price
        
        Returns:
            Tuple of (is_valid, issues: List[str], warnings: List[str])
        """
        issues = []
        warnings = []
        
        if not candles:
            issues.append("Empty candle list")
            return False, issues, warnings
        
        # Check batch consistency
        issues.extend(self._check_batch_consistency(candles))
        
        # Check individual candles
        for i, candle in enumerate(candles):
            candle_issues = self._check_individual_candle(candle, i)
            issues.extend(candle_issues)
        
        # Check temporal consistency
        warnings.extend(self._check_temporal_consistency(symbol, candles))
        
        # Check data completeness
        missing = self._check_completeness(candles)
        if missing:
            issues.extend(missing)
        
        self.checks_performed += 1
        if issues:
            self.issues_found += 1
        
        is_valid = len(issues) == 0
        return is_valid, issues, warnings
    
    def _check_batch_consistency(self, candles: List[Dict]) -> List[str]:
        """Check consistency across batch"""
        issues = []
        
        if not candles:
            return issues
        
        # All candles should have same symbol
        symbols = set(c.get('T') for c in candles if 'T' in c)
        if len(symbols) > 1:
            issues.append(f"Multiple symbols in batch: {symbols}")
        
        # Check chronological order
        dates = []
        for candle in candles:
            if 't' in candle:
                try:
                    dates.append(int(candle['t']))
                except (ValueError, TypeError):
                    issues.append(f"Invalid timestamp: {candle.get('t')}")
        
        if dates and dates != sorted(dates):
            issues.append("Candles not in chronological order")
        
        # Check for duplicates
        date_set = set(dates)
        if len(date_set) < len(dates):
            issues.append(f"Duplicate dates found: {len(dates)} candles, {len(date_set)} unique")
        
        return issues
    
    def _check_individual_candle(self, candle: Dict, index: int) -> List[str]:
        """Check individual candle validity"""
        issues = []
        
        required_fields = ['o', 'h', 'l', 'c', 'v', 't']
        missing = [f for f in required_fields if f not in candle]
        if missing:
            issues.append(f"Candle {index}: missing fields {missing}")
            return issues
        
        try:
            o = Decimal(str(candle['o']))
            h = Decimal(str(candle['h']))
            l = Decimal(str(candle['l']))
            c = Decimal(str(candle['c']))
            v = Decimal(str(candle['v']))
        except (ValueError, TypeError, InvalidOperation):
            issues.append(f"Candle {index}: invalid price/volume types")
            return issues
        
        # OHLCV constraint checks
        if h < max(o, c):
            issues.append(f"Candle {index}: High ({h}) < max(Open, Close) ({max(o, c)})")
        
        if l > min(o, c):
            issues.append(f"Candle {index}: Low ({l}) > min(Open, Close) ({min(o, c)})")
        
        if any(p < 0 for p in [o, h, l, c]):
            issues.append(f"Candle {index}: negative price detected")
        
        if v < 0:
            issues.append(f"Candle {index}: negative volume")
        
        if v == 0:
            issues.append(f"Candle {index}: zero volume (likely invalid)")
        
        return issues
    
    def _check_temporal_consistency(self, symbol: str, candles: List[Dict]) -> List[str]:
        """Check time-based consistency"""
        warnings = []
        
        if len(candles) < 2:
            return warnings
        
        dates = []
        for candle in candles:
            if 't' in candle:
                try:
                    ts = int(candle['t']) / 1000  # Convert ms to seconds
                    dates.append(datetime.utcfromtimestamp(ts))
                except (ValueError, OSError):
                    continue
        
        if len(dates) < 2:
            return warnings
        
        # Check for large gaps (more than 3 business days)
        for i in range(1, len(dates)):
            gap_days = (dates[i] - dates[i-1]).days
            
            # Account for weekends
            if gap_days > 3:
                day_of_week = dates[i-1].weekday()
                if day_of_week == 4:  # Friday
                    # Friday to Monday gap is normal
                    if gap_days > 3:
                        warnings.append(f"Large gap: {gap_days} days between {dates[i-1].date()} and {dates[i].date()}")
                elif gap_days > 1:
                    warnings.append(f"Unexpected gap: {gap_days} days between {dates[i-1].date()} and {dates[i].date()}")
        
        return warnings
    
    def _check_completeness(self, candles: List[Dict]) -> List[str]:
        """Check data field completeness"""
        issues = []
        
        expected_fields = {'o', 'h', 'l', 'c', 'v', 't', 'n', 'vw'}
        
        for i, candle in enumerate(candles):
            actual_fields = set(candle.keys())
            
            # Check for null values in critical fields
            critical_fields = ['o', 'h', 'l', 'c', 'v']
            for field in critical_fields:
                if candle.get(field) is None:
                    issues.append(f"Candle {i}: null value in critical field '{field}'")
        
        return issues
    
    def get_quality_score(self, candles: List[Dict]) -> float:
        """
        Calculate overall quality score for batch (0.0-1.0).
        
        Score factors:
        - Presence of all expected fields
        - No anomalies detected
        - Data completeness
        """
        if not candles:
            return 0.0
        
        score = 1.0
        issues_count = 0
        
        for candle in candles:
            # Check field completeness
            expected_fields = {'o', 'h', 'l', 'c', 'v', 't'}
            missing = len(expected_fields - set(candle.keys())) / len(expected_fields)
            score -= missing * 0.1
            
            # Basic OHLCV checks
            try:
                h = Decimal(str(candle.get('h', 0)))
                l = Decimal(str(candle.get('l', 0)))
                o = Decimal(str(candle.get('o', 0)))
                c = Decimal(str(candle.get('c', 0)))
                
                if not (l <= min(o, c) and h >= max(o, c)):
                    issues_count += 1
            except (ValueError, TypeError, InvalidOperation):
                issues_count += 1
        
        # Penalize for anomalies
        if issues_count > 0:
            score -= (issues_count / len(candles)) * 0.2
        
        return max(0.0, min(1.0, score))
    
    def summary(self) -> Dict[str, int]:
        """Get summary of quality checks performed"""
        return {
            "checks_performed": self.checks_performed,
            "issues_found": self.issues_found,
            "success_rate": (
                (self.checks_performed - self.issues_found) / self.checks_performed
                if self.checks_performed > 0 else 0.0
            )
        }


class PriceAnomalyDetector:
    """Detects price-based anomalies in trading data"""
    
    @staticmethod
    def detect_spike(prev_close: Decimal, current_open: Decimal, threshold_pct: float = 20.0) -> bool:
        """
        Detect if opening price has unusual gap from previous close.
        
        Args:
            prev_close: Previous day's closing price
            current_open: Current day's opening price
            threshold_pct: Threshold percentage for flagging (default 20%)
        
        Returns:
            True if spike detected
        """
        if prev_close <= 0:
            return False
        
        change_pct = abs((current_open - prev_close) / prev_close) * 100
        return change_pct > threshold_pct
    
    @staticmethod
    def detect_intraday_range_anomaly(
        open_price: Decimal,
        close_price: Decimal,
        high: Decimal,
        low: Decimal,
        threshold_pct: float = 30.0
    ) -> bool:
        """
        Detect if intraday range is unusually large.
        
        Args:
            open_price, close_price, high, low: OHLC values
            threshold_pct: Threshold for daily range relative to open (default 30%)
        
        Returns:
            True if anomaly detected
        """
        if open_price <= 0:
            return False
        
        range_pct = ((high - low) / open_price) * 100
        return range_pct > threshold_pct
    
    @staticmethod
    def detect_reverse_split(prev_close: Decimal, current_open: Decimal) -> bool:
        """
        Detect possible reverse stock split (price jump).
        
        A 2:1 reverse split would show ~100% price increase.
        """
        if prev_close <= 0:
            return False
        
        change_pct = ((current_open - prev_close) / prev_close) * 100
        return change_pct >= 100


# For typing support
from decimal import InvalidOperation
