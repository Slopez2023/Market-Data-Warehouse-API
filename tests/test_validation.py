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
