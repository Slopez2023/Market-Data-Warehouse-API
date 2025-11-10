"""Tests for validation service"""

import pytest
from decimal import Decimal

from src.services.validation_service import ValidationService


@pytest.fixture
def validation_service():
    return ValidationService()


class TestOHLCVConstraints:
    """Test OHLCV constraint validation"""
    
    def test_valid_ohlcv(self, validation_service):
        """Test valid OHLCV candle"""
        candle = {
            't': 1700000000000,
            'o': Decimal('150.00'),
            'h': Decimal('152.50'),
            'l': Decimal('149.50'),
            'c': Decimal('151.00'),
            'v': 1000000
        }
        
        quality, meta = validation_service.validate_candle('AAPL', candle)
        
        assert quality >= 0.85
        assert meta['validated'] is True
    
    def test_high_less_than_open(self, validation_service):
        """Test invalid: high < open"""
        candle = {
            't': 1700000000000,
            'o': Decimal('150.00'),
            'h': Decimal('149.00'),  # Less than open - invalid
            'l': Decimal('145.00'),
            'c': Decimal('148.00'),
            'v': 1000000
        }
        
        quality, meta = validation_service.validate_candle('AAPL', candle)
        
        assert quality < 0.85
        assert meta['validated'] is False
    
    def test_low_greater_than_close(self, validation_service):
        """Test invalid: low > close"""
        candle = {
            't': 1700000000000,
            'o': Decimal('150.00'),
            'h': Decimal('152.00'),
            'l': Decimal('151.00'),  # Greater than close - invalid
            'c': Decimal('151.00'),
            'v': 1000000
        }
        
        quality, meta = validation_service.validate_candle('AAPL', candle)
        
        assert quality < 0.85
        assert meta['validated'] is False
    
    def test_zero_price(self, validation_service):
        """Test invalid: zero price"""
        candle = {
            't': 1700000000000,
            'o': Decimal('0.00'),  # Zero - invalid
            'h': Decimal('152.00'),
            'l': Decimal('145.00'),
            'c': Decimal('150.00'),
            'v': 1000000
        }
        
        quality, meta = validation_service.validate_candle('AAPL', candle)
        
        assert quality < 0.85
        assert meta['validated'] is False


class TestPriceMove:
    """Test price move anomaly detection"""
    
    def test_reasonable_move(self, validation_service):
        """Test reasonable single-day price move"""
        candle = {
            't': 1700000000000,
            'o': Decimal('100.00'),
            'h': Decimal('110.00'),
            'l': Decimal('99.00'),
            'c': Decimal('105.00'),  # 5% move - reasonable
            'v': 1000000
        }
        
        quality, meta = validation_service.validate_candle('AAPL', candle)
        
        assert quality >= 0.85
        assert meta['validated'] is True
    
    def test_extreme_move(self, validation_service):
        """Test extreme price move (>500%)"""
        candle = {
            't': 1700000000000,
            'o': Decimal('100.00'),
            'h': Decimal('600.00'),
            'l': Decimal('99.00'),
            'c': Decimal('550.00'),  # 550% move - extreme
            'v': 1000000
        }
        
        quality, meta = validation_service.validate_candle('AAPL', candle)
        
        assert quality < 0.85
        assert 'extreme_price_move' in meta['validation_notes']


class TestVolumeAnomaly:
    """Test volume anomaly detection"""
    
    def test_normal_volume(self, validation_service):
        """Test normal volume"""
        candle = {
            't': 1700000000000,
            'o': Decimal('150.00'),
            'h': Decimal('152.00'),
            'l': Decimal('149.00'),
            'c': Decimal('151.00'),
            'v': 1000000  # Normal volume
        }
        
        quality, meta = validation_service.validate_candle(
            'AAPL', 
            candle,
            median_volume=1000000
        )
        
        assert meta['volume_anomaly'] is False
    
    def test_high_volume_anomaly(self, validation_service):
        """Test volume spike (10x median)"""
        candle = {
            't': 1700000000000,
            'o': Decimal('150.00'),
            'h': Decimal('152.00'),
            'l': Decimal('149.00'),
            'c': Decimal('151.00'),
            'v': 15000000  # 15x median
        }
        
        quality, meta = validation_service.validate_candle(
            'AAPL',
            candle,
            median_volume=1000000
        )
        
        assert meta['volume_anomaly'] is True
        assert 'volume_anomaly_high' in meta['validation_notes']


class TestMedianVolume:
    """Test median volume calculation"""
    
    def test_median_odd_count(self, validation_service):
        """Test median with odd number of values"""
        candles = [
            {'v': 100}, {'v': 200}, {'v': 300}, {'v': 400}, {'v': 500}
        ]
        
        median = validation_service.calculate_median_volume(candles)
        assert median == 300
    
    def test_median_even_count(self, validation_service):
        """Test median with even number of values"""
        candles = [
            {'v': 100}, {'v': 200}, {'v': 300}, {'v': 400}
        ]
        
        median = validation_service.calculate_median_volume(candles)
        assert median == 250  # (200 + 300) / 2
    
    def test_median_empty_list(self, validation_service):
        """Test median with empty candle list"""
        median = validation_service.calculate_median_volume([])
        assert median == 0
    
    def test_median_single_candle(self, validation_service):
        """Test median with single candle"""
        candles = [{'v': 500}]
        median = validation_service.calculate_median_volume(candles)
        assert median == 500
    
    def test_median_excludes_zero_volume(self, validation_service):
        """Test that zero-volume candles are excluded from median"""
        candles = [
            {'v': 0}, {'v': 100}, {'v': 200}, {'v': 300}, {'v': 0}
        ]
        median = validation_service.calculate_median_volume(candles)
        assert median == 200  # Only [100, 200, 300]


class TestGapDetection:
    """Test gap detection and weekend handling"""
    
    def test_normal_day_to_day(self, validation_service):
        """Test no gap on normal trading day"""
        from datetime import datetime
        candle = {
            't': datetime(2024, 11, 6, 9, 30).timestamp() * 1000,  # Wednesday
            'o': Decimal('100.00'),
            'h': Decimal('102.00'),
            'l': Decimal('99.00'),
            'c': Decimal('101.00'),
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle(
            'AAPL',
            candle,
            prev_close=Decimal('100.50')
        )
        # 0.5% gap is normal
        assert meta['gap_detected'] is False
    
    def test_large_gap_friday_to_monday(self, validation_service):
        """Test large gap from Friday close to Monday open (expected)"""
        from datetime import datetime
        candle = {
            't': datetime(2024, 11, 11, 9, 30).timestamp() * 1000,  # Monday
            'o': Decimal('110.00'),
            'h': Decimal('112.00'),
            'l': Decimal('109.00'),
            'c': Decimal('111.00'),
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle(
            'AAPL',
            candle,
            prev_close=Decimal('100.00')  # 10% gap
        )
        # Monday gaps are expected, shouldn't penalize
        assert meta['gap_detected'] is False
    
    def test_large_gap_mid_week(self, validation_service):
        """Test large gap mid-week (should be flagged)"""
        from datetime import datetime
        candle = {
            't': datetime(2024, 11, 7, 9, 30).timestamp() * 1000,  # Thursday
            'o': Decimal('115.00'),
            'h': Decimal('117.00'),
            'l': Decimal('114.00'),
            'c': Decimal('116.00'),
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle(
            'AAPL',
            candle,
            prev_close=Decimal('100.00')  # 15% gap
        )
        # Mid-week 15% gap should be flagged
        assert meta['gap_detected'] is True
        assert quality < 0.85


class TestHighLowConstraints:
    """Test edge cases for high/low bracket constraints"""
    
    def test_high_equals_max_price(self, validation_service):
        """Test when high exactly equals highest price"""
        candle = {
            't': 1700000000000,
            'o': Decimal('100.00'),
            'h': Decimal('110.00'),  # Equals max of O and C
            'l': Decimal('95.00'),
            'c': Decimal('110.00'),
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle('AAPL', candle)
        assert meta['validated'] is True
    
    def test_low_equals_min_price(self, validation_service):
        """Test when low exactly equals lowest price"""
        candle = {
            't': 1700000000000,
            'o': Decimal('100.00'),
            'h': Decimal('105.00'),
            'l': Decimal('95.00'),  # Equals min of O and C
            'c': Decimal('95.00'),
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle('AAPL', candle)
        assert meta['validated'] is True
    
    def test_all_prices_equal(self, validation_service):
        """Test when OHLC are all equal (valid, no move)"""
        candle = {
            't': 1700000000000,
            'o': Decimal('100.00'),
            'h': Decimal('100.00'),
            'l': Decimal('100.00'),
            'c': Decimal('100.00'),
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle('AAPL', candle)
        assert meta['validated'] is True


class TestNegativePrices:
    """Test handling of negative and zero prices"""
    
    def test_negative_close_price(self, validation_service):
        """Test invalid: negative close price"""
        candle = {
            't': 1700000000000,
            'o': Decimal('100.00'),
            'h': Decimal('102.00'),
            'l': Decimal('99.00'),
            'c': Decimal('-100.00'),  # Negative
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle('AAPL', candle)
        assert quality < 0.85
        assert meta['validated'] is False
    
    def test_negative_open_price(self, validation_service):
        """Test invalid: negative open price"""
        candle = {
            't': 1700000000000,
            'o': Decimal('-100.00'),  # Negative
            'h': Decimal('102.00'),
            'l': Decimal('99.00'),
            'c': Decimal('101.00'),
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle('AAPL', candle)
        assert quality < 0.85
        assert meta['validated'] is False


class TestErrorHandling:
    """Test exception handling and edge cases"""
    
    def test_missing_required_fields(self, validation_service):
        """Test candle with missing OHLCV fields"""
        candle = {'o': Decimal('100.00')}  # Missing h, l, c, v
        quality, meta = validation_service.validate_candle('AAPL', candle)
        # Should handle gracefully, but mark as failed
        assert quality < 0.85
    
    def test_invalid_price_types(self, validation_service):
        """Test candle with string prices that can't convert"""
        candle = {
            't': 1700000000000,
            'o': 'invalid',
            'h': '102.00',
            'l': '99.00',
            'c': '101.00',
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle('AAPL', candle)
        # Should handle gracefully
        assert quality == 0.0
        assert 'validation_exception' in (meta.get('validation_notes') or '')
    
    def test_null_prev_close_no_error(self, validation_service):
        """Test that None prev_close doesn't cause error"""
        candle = {
            't': 1700000000000,
            'o': Decimal('100.00'),
            'h': Decimal('102.00'),
            'l': Decimal('99.00'),
            'c': Decimal('101.00'),
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle(
            'AAPL',
            candle,
            prev_close=None
        )
        # Should work fine without prev_close
        assert meta['gap_detected'] is False
        assert meta['validated'] is True
    
    def test_zero_median_volume(self, validation_service):
        """Test with zero median volume (edge case)"""
        candle = {
            't': 1700000000000,
            'o': Decimal('100.00'),
            'h': Decimal('102.00'),
            'l': Decimal('99.00'),
            'c': Decimal('101.00'),
            'v': 1000000
        }
        quality, meta = validation_service.validate_candle(
            'AAPL',
            candle,
            median_volume=0
        )
        # Should not error, just skip volume check
        assert quality >= 0.85
