"""Integration tests - Polygon client -> Validation -> Database simulation"""

import pytest
import asyncio
import os
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv

from src.clients.polygon_client import PolygonClient
from src.services.validation_service import ValidationService

load_dotenv()


@pytest.fixture
def polygon_client():
    api_key = os.getenv('POLYGON_API_KEY')
    return PolygonClient(api_key)


@pytest.fixture
def validation_service():
    return ValidationService()


class TestPolygonIntegration:
    """Test real Polygon API integration"""
    
    @pytest.mark.asyncio
    async def test_fetch_aapl_recent(self, polygon_client):
        """Fetch recent AAPL data from Polygon"""
        data = await polygon_client.fetch_daily_range('AAPL', '2024-11-01', '2024-11-07')
        
        assert data is not None
        assert len(data) > 0
        assert all('c' in candle for candle in data)  # Has close price
        assert all('v' in candle for candle in data)  # Has volume
    
    @pytest.mark.asyncio
    async def test_fetch_msft_recent(self, polygon_client):
        """Fetch recent MSFT data from Polygon"""
        data = await polygon_client.fetch_daily_range('MSFT', '2024-11-01', '2024-11-07')
        
        assert data is not None
        assert len(data) > 0
    
    @pytest.mark.asyncio
    async def test_polygon_to_validation_pipeline(self, polygon_client, validation_service):
        """Test full pipeline: Fetch -> Validate -> Score"""
        # Fetch data
        candles = await polygon_client.fetch_daily_range('AAPL', '2024-11-01', '2024-11-07')
        
        assert len(candles) > 0
        
        # Validate each candle
        median_vol = validation_service.calculate_median_volume(candles)
        
        validated_candles = []
        for candle in candles:
            quality, meta = validation_service.validate_candle(
                'AAPL',
                candle,
                median_volume=median_vol
            )
            
            assert 0 <= quality <= 1.0
            assert 'validated' in meta
            assert 'quality_score' in meta
            
            validated_candles.append({
                'candle': candle,
                'quality': quality,
                'metadata': meta
            })
        
        # Check that at least some candles passed validation
        validated_count = sum(1 for vc in validated_candles if vc['metadata']['validated'])
        assert validated_count > 0, "No candles passed validation"
        
        validation_rate = validated_count / len(validated_candles) * 100
        assert validation_rate >= 80.0, f"Validation rate too low: {validation_rate:.1f}%"


class TestValidationQuality:
    """Test validation quality scoring on real data"""
    
    @pytest.mark.asyncio
    async def test_validation_quality_distribution(self, polygon_client, validation_service):
        """Check quality score distribution on real data"""
        candles = await polygon_client.fetch_daily_range('MSFT', '2024-11-01', '2024-11-07')
        
        median_vol = validation_service.calculate_median_volume(candles)
        
        quality_scores = []
        for candle in candles:
            quality, _ = validation_service.validate_candle('MSFT', candle, median_volume=median_vol)
            quality_scores.append(quality)
        
        assert len(quality_scores) > 0
        
        # Check distribution
        avg_quality = sum(quality_scores) / len(quality_scores)
        assert avg_quality >= 0.85, f"Average quality too low: {avg_quality:.2f}"
        
        # Most candles should pass (quality >= 0.85)
        pass_count = sum(1 for q in quality_scores if q >= 0.85)
        pass_rate = pass_count / len(quality_scores) * 100
        
        print(f"\nQuality Distribution:")
        print(f"  Pass rate (>=0.85): {pass_rate:.1f}%")
        print(f"  Average quality: {avg_quality:.3f}")
        print(f"  Min quality: {min(quality_scores):.3f}")
        print(f"  Max quality: {max(quality_scores):.3f}")


class TestDataConsistency:
    """Test data consistency between sources"""
    
    @pytest.mark.asyncio
    async def test_polygon_data_format(self, polygon_client):
        """Verify Polygon data has expected format"""
        data = await polygon_client.fetch_daily_range('AAPL', '2024-11-05', '2024-11-05')
        
        assert len(data) > 0
        candle = data[0]
        
        # Required fields
        required_fields = ['t', 'o', 'h', 'l', 'c', 'v']
        for field in required_fields:
            assert field in candle, f"Missing required field: {field}"
        
        # Value types
        assert isinstance(candle['t'], (int, float))  # timestamp
        assert isinstance(candle['o'], (int, float))  # open
        assert isinstance(candle['c'], (int, float))  # close
        assert isinstance(candle['v'], (int, float))  # volume
        
        # Value ranges
        assert candle['h'] >= candle['l'], "High should be >= Low"
        assert candle['h'] >= max(candle['o'], candle['c']), "High should bracket prices"
        assert candle['l'] <= min(candle['o'], candle['c']), "Low should bracket prices"
        assert candle['o'] > 0 and candle['c'] > 0, "Prices should be positive"
        assert candle['v'] >= 0, "Volume should be non-negative"


# Run with: pytest tests/test_integration.py -v -s
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
