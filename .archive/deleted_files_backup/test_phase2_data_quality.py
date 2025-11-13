"""Phase 2.3: Tests for data quality checking"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from src.services.data_quality_checker import (
    DataQualityChecker, PriceAnomalyDetector
)


class TestDataQualityChecker:
    """Test suite for DataQualityChecker"""
    
    def test_empty_batch(self):
        """Test handling of empty candle batch"""
        checker = DataQualityChecker()
        
        is_valid, issues, warnings = checker.check_batch("AAPL", [])
        
        assert is_valid is False
        assert any("Empty" in i for i in issues)
    
    def test_valid_single_candle(self):
        """Test valid single candle"""
        checker = DataQualityChecker()
        
        candle = {
            'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0,
            'v': 1000000, 't': 1699507200000, 'T': 'AAPL', 'n': 10000
        }
        
        is_valid, issues, warnings = checker.check_batch("AAPL", [candle])
        
        assert is_valid is True
        assert len(issues) == 0
    
    def test_missing_fields(self):
        """Test detection of missing required fields"""
        checker = DataQualityChecker()
        
        incomplete_candle = {
            'o': 150.0,
            'h': 152.0
            # Missing l, c, v, t
        }
        
        is_valid, issues, warnings = checker.check_batch("AAPL", [incomplete_candle])
        
        assert is_valid is False
        assert any("missing" in i.lower() for i in issues)
    
    def test_invalid_high_low_constraint(self):
        """Test OHLCV constraint: high < max(O,C)"""
        checker = DataQualityChecker()
        
        bad_candle = {
            'o': 150.0, 'h': 149.0, 'l': 148.0, 'c': 151.0,
            'v': 1000000, 't': 1699507200000
        }
        
        is_valid, issues, warnings = checker.check_batch("AAPL", [bad_candle])
        
        assert is_valid is False
        assert any("High" in i for i in issues)
    
    def test_invalid_low_constraint(self):
        """Test OHLCV constraint: low > min(O,C)"""
        checker = DataQualityChecker()
        
        bad_candle = {
            'o': 150.0, 'h': 152.0, 'l': 151.0, 'c': 149.0,
            'v': 1000000, 't': 1699507200000
        }
        
        is_valid, issues, warnings = checker.check_batch("AAPL", [bad_candle])
        
        assert is_valid is False
        assert any("Low" in i for i in issues)
    
    def test_negative_price_detection(self):
        """Test detection of negative prices"""
        checker = DataQualityChecker()
        
        bad_candle = {
            'o': -150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0,
            'v': 1000000, 't': 1699507200000
        }
        
        is_valid, issues, warnings = checker.check_batch("AAPL", [bad_candle])
        
        assert is_valid is False
        assert any("negative" in i.lower() for i in issues)
    
    def test_zero_volume_detection(self):
        """Test detection of zero volume"""
        checker = DataQualityChecker()
        
        bad_candle = {
            'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0,
            'v': 0, 't': 1699507200000
        }
        
        is_valid, issues, warnings = checker.check_batch("AAPL", [bad_candle])
        
        assert is_valid is False
        assert any("volume" in i.lower() for i in issues)
    
    def test_negative_volume_detection(self):
        """Test detection of negative volume"""
        checker = DataQualityChecker()
        
        bad_candle = {
            'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0,
            'v': -1000, 't': 1699507200000
        }
        
        is_valid, issues, warnings = checker.check_batch("AAPL", [bad_candle])
        
        assert is_valid is False
        assert any("negative" in i.lower() for i in issues)
    
    def test_chronological_order_check(self):
        """Test that candles must be in chronological order"""
        checker = DataQualityChecker()
        
        candles = [
            {'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0, 'v': 1000000, 't': 1699600000},
            {'o': 151.0, 'h': 153.0, 'l': 150.0, 'c': 152.0, 'v': 1000000, 't': 1699500000}  # Earlier
        ]
        
        is_valid, issues, warnings = checker.check_batch("AAPL", candles)
        
        assert is_valid is False
        assert any("chronological" in i.lower() for i in issues)
    
    def test_duplicate_dates_detection(self):
        """Test detection of duplicate dates in batch"""
        checker = DataQualityChecker()
        
        candles = [
            {'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0, 'v': 1000000, 't': 1699500000},
            {'o': 151.0, 'h': 153.0, 'l': 150.0, 'c': 152.0, 'v': 1000000, 't': 1699500000}  # Duplicate
        ]
        
        is_valid, issues, warnings = checker.check_batch("AAPL", candles)
        
        assert is_valid is False
        assert any("Duplicate" in i for i in issues)
    
    def test_multiple_symbols_detection(self):
        """Test detection of multiple symbols in batch"""
        checker = DataQualityChecker()
        
        candles = [
            {'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0, 'v': 1000000, 't': 1699500000, 'T': 'AAPL'},
            {'o': 200.0, 'h': 202.0, 'l': 199.0, 'c': 201.0, 'v': 1000000, 't': 1699600000, 'T': 'MSFT'}
        ]
        
        is_valid, issues, warnings = checker.check_batch("AAPL", candles)
        
        assert is_valid is False
        assert any("symbol" in i.lower() for i in issues)
    
    def test_quality_score_calculation(self):
        """Test quality score calculation"""
        checker = DataQualityChecker()
        
        good_candle = {
            'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0,
            'v': 1000000, 't': 1699500000
        }
        
        score = checker.get_quality_score([good_candle])
        
        assert 0.0 <= score <= 1.0
        assert score > 0.8  # Good candle should have high score
    
    def test_quality_score_with_missing_fields(self):
        """Test quality score with incomplete data"""
        checker = DataQualityChecker()
        
        incomplete_candle = {
            'o': 150.0, 'h': 152.0
            # Missing l, c, v, t fields
        }
        
        score = checker.get_quality_score([incomplete_candle])
        
        # Score should be less than perfect (1.0)
        assert score < 1.0
        assert score > 0.0  # But still has some quality
    
    def test_summary_statistics(self):
        """Test summary statistics calculation"""
        checker = DataQualityChecker()
        
        good_candle = {
            'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0,
            'v': 1000000, 't': 1699500000
        }
        
        is_valid, issues, warnings = checker.check_batch("AAPL", [good_candle])
        
        summary = checker.summary()
        
        assert summary["checks_performed"] == 1
        assert summary["issues_found"] == 0
        assert summary["success_rate"] == 1.0
    
    def test_temporal_gap_detection(self):
        """Test detection of large temporal gaps"""
        checker = DataQualityChecker()
        
        # Create candles with 5-day gap
        candles = [
            {'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0, 'v': 1000000, 't': 1699500000000},
            {'o': 151.0, 'h': 153.0, 'l': 150.0, 'c': 152.0, 'v': 1000000, 't': 1699932000000}  # 5 days later
        ]
        
        is_valid, issues, warnings = checker.check_batch("AAPL", candles)
        
        # Should still be valid but with warning
        assert any("gap" in w.lower() for w in warnings)


class TestPriceAnomalyDetector:
    """Test suite for PriceAnomalyDetector"""
    
    def test_normal_gap(self):
        """Test normal price gap detection"""
        detector = PriceAnomalyDetector()
        
        prev_close = Decimal("150.00")
        current_open = Decimal("150.50")
        
        is_anomaly = detector.detect_spike(prev_close, current_open)
        
        assert is_anomaly is False  # 0.3% gap is normal
    
    def test_large_gap_detection(self):
        """Test detection of large price gap"""
        detector = PriceAnomalyDetector()
        
        prev_close = Decimal("100.00")
        current_open = Decimal("125.00")  # 25% gap
        
        is_anomaly = detector.detect_spike(prev_close, current_open, threshold_pct=20.0)
        
        assert is_anomaly is True
    
    def test_gap_threshold_boundary(self):
        """Test gap threshold boundary conditions"""
        detector = PriceAnomalyDetector()
        
        prev_close = Decimal("100.00")
        current_open = Decimal("120.00")  # Exactly 20% gap
        
        # Just above threshold (20.01%)
        is_anomaly = detector.detect_spike(prev_close, current_open, threshold_pct=19.9)
        assert is_anomaly is True
        
        # Just below actual gap percentage
        is_anomaly = detector.detect_spike(prev_close, current_open, threshold_pct=20.1)
        assert is_anomaly is False
    
    def test_zero_prev_close(self):
        """Test handling of zero previous close"""
        detector = PriceAnomalyDetector()
        
        prev_close = Decimal("0")
        current_open = Decimal("150.00")
        
        is_anomaly = detector.detect_spike(prev_close, current_open)
        
        # Should not raise error
        assert is_anomaly is False
    
    def test_intraday_range_normal(self):
        """Test normal intraday range"""
        detector = PriceAnomalyDetector()
        
        open_price = Decimal("150.00")
        close_price = Decimal("152.00")
        high = Decimal("154.00")
        low = Decimal("149.00")
        
        is_anomaly = detector.detect_intraday_range_anomaly(
            open_price, close_price, high, low, threshold_pct=30.0
        )
        
        assert is_anomaly is False  # Range is ~3.3%
    
    def test_intraday_range_anomaly(self):
        """Test detection of large intraday range"""
        detector = PriceAnomalyDetector()
        
        open_price = Decimal("100.00")
        close_price = Decimal("102.00")
        high = Decimal("140.00")  # Large range
        low = Decimal("98.00")
        
        is_anomaly = detector.detect_intraday_range_anomaly(
            open_price, close_price, high, low, threshold_pct=30.0
        )
        
        assert is_anomaly is True  # Range is 42%
    
    def test_reverse_split_detection(self):
        """Test detection of possible reverse stock split"""
        detector = PriceAnomalyDetector()
        
        prev_close = Decimal("10.00")
        current_open = Decimal("25.00")  # 150% increase - 2:1 split
        
        is_split = detector.detect_reverse_split(prev_close, current_open)
        
        assert is_split is True
    
    def test_reverse_split_no_split(self):
        """Test that normal moves don't trigger split detection"""
        detector = PriceAnomalyDetector()
        
        prev_close = Decimal("100.00")
        current_open = Decimal("110.00")  # 10% increase
        
        is_split = detector.detect_reverse_split(prev_close, current_open)
        
        assert is_split is False
    
    def test_anomaly_negative_prices(self):
        """Test handling of negative prices"""
        detector = PriceAnomalyDetector()
        
        # All methods should handle negative gracefully
        detector.detect_spike(Decimal("-100"), Decimal("-110"))
        detector.detect_intraday_range_anomaly(Decimal("-100"), Decimal("-105"), Decimal("-95"), Decimal("-110"))
        detector.detect_reverse_split(Decimal("-100"), Decimal("-150"))


class TestDataQualityIntegration:
    """Integration tests for data quality checking"""
    
    def test_realistic_batch_processing(self):
        """Test with realistic batch of candles"""
        checker = DataQualityChecker()
        
        # Create realistic batch
        candles = [
            {'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0, 'v': 1000000, 't': 1699500000},
            {'o': 151.0, 'h': 153.0, 'l': 150.0, 'c': 152.0, 'v': 1100000, 't': 1699586400},
            {'o': 152.0, 'h': 154.0, 'l': 151.0, 'c': 153.0, 'v': 1200000, 't': 1699672800},
        ]
        
        is_valid, issues, warnings = checker.check_batch("AAPL", candles)
        
        assert is_valid is True
        assert len(issues) == 0
    
    def test_batch_with_warnings_still_valid(self):
        """Test that batch can be valid despite warnings"""
        checker = DataQualityChecker()
        
        # Valid but with weekend gap
        candles = [
            {'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0, 'v': 1000000, 't': 1699500000000},  # Friday
            {'o': 151.0, 'h': 153.0, 'l': 150.0, 'c': 152.0, 'v': 1100000, 't': 1699759200000},  # Monday
        ]
        
        is_valid, issues, warnings = checker.check_batch("AAPL", candles)
        
        # Should be valid
        assert is_valid is True
        assert len(issues) == 0
