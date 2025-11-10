"""Mock backfill test - simulates full pipeline without real database"""

import pytest
import asyncio
import os
from datetime import datetime
from dotenv import load_dotenv

from src.clients.polygon_client import PolygonClient
from src.services.validation_service import ValidationService

load_dotenv()


@pytest.mark.integration
class MockBackfillSimulator:
    """Simulates backfill logic without database"""
    
    def __init__(self):
        self.polygon_client = PolygonClient(os.getenv('POLYGON_API_KEY'))
        self.validation_service = ValidationService()
    
    async def simulate_backfill_symbol(self, symbol: str, start: str, end: str):
        """
        Simulate backfill for a single symbol.
        
        Returns: {
            'symbol': str,
            'start_date': str,
            'end_date': str,
            'total_candles': int,
            'validated_candles': int,
            'validation_rate': float,
            'avg_quality_score': float,
            'candles_with_gaps': int,
            'candles_with_volume_anomaly': int
        }
        """
        # Fetch data
        candles = await self.polygon_client.fetch_daily_range(symbol, start, end)
        
        if not candles:
            return {
                'symbol': symbol,
                'start_date': start,
                'end_date': end,
                'total_candles': 0,
                'error': 'No data returned from Polygon'
            }
        
        # Calculate median volume
        median_vol = self.validation_service.calculate_median_volume(candles)
        
        # Validate each candle
        results = {
            'symbol': symbol,
            'start_date': start,
            'end_date': end,
            'total_candles': len(candles),
            'validated_candles': 0,
            'candles_with_gaps': 0,
            'candles_with_volume_anomaly': 0,
            'quality_scores': [],
            'candles': []
        }
        
        prev_close = None
        
        for candle in candles:
            quality, meta = self.validation_service.validate_candle(
                symbol,
                candle,
                prev_close=prev_close,
                median_volume=median_vol if median_vol > 0 else None
            )
            
            # Track results
            results['quality_scores'].append(quality)
            
            if meta['validated']:
                results['validated_candles'] += 1
            
            if meta['gap_detected']:
                results['candles_with_gaps'] += 1
            
            if meta['volume_anomaly']:
                results['candles_with_volume_anomaly'] += 1
            
            # Store enriched candle
            results['candles'].append({
                'time': candle.get('t'),
                'close': candle.get('c'),
                'volume': candle.get('v'),
                'quality_score': quality,
                'validated': meta['validated'],
                'gap_detected': meta['gap_detected'],
                'volume_anomaly': meta['volume_anomaly']
            })
            
            prev_close = candle.get('c')
        
        # Calculate metrics
        results['validation_rate'] = (
            results['validated_candles'] / results['total_candles'] * 100
            if results['total_candles'] > 0 else 0
        )
        results['avg_quality_score'] = (
            sum(results['quality_scores']) / len(results['quality_scores'])
            if results['quality_scores'] else 0
        )
        
        return results


@pytest.fixture
def backfill_sim():
    return MockBackfillSimulator()


@pytest.mark.integration
class TestBackfillSimulation:
    """Test backfill pipeline with real Polygon data"""
    
    @pytest.mark.asyncio
    async def test_single_symbol_backfill(self, backfill_sim):
        """Test backfill for a single symbol"""
        result = await backfill_sim.simulate_backfill_symbol('AAPL', '2024-11-01', '2024-11-07')
        
        assert result['symbol'] == 'AAPL'
        assert result['total_candles'] > 0
        assert result['validated_candles'] > 0
        assert result['validation_rate'] >= 80.0
    
    @pytest.mark.asyncio
    async def test_multi_symbol_backfill(self, backfill_sim):
        """Test backfill for multiple symbols"""
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
        
        results = {}
        for symbol in symbols:
            result = await backfill_sim.simulate_backfill_symbol(symbol, '2024-11-01', '2024-11-07')
            results[symbol] = result
            
            assert result['total_candles'] > 0
            assert result['validation_rate'] >= 80.0
        
        # Print summary
        print("\nBackfill Summary:")
        print(f"{'Symbol':<10} {'Candles':<10} {'Validated':<12} {'Valid %':<10} {'Gaps':<8} {'Vol Anom':<10}")
        print("-" * 70)
        
        for symbol, result in results.items():
            print(
                f"{symbol:<10} {result['total_candles']:<10} "
                f"{result['validated_candles']:<12} "
                f"{result['validation_rate']:<9.1f}% "
                f"{result['candles_with_gaps']:<8} "
                f"{result['candles_with_volume_anomaly']:<10}"
            )
    
    @pytest.mark.asyncio
    async def test_backfill_data_structure(self, backfill_sim):
        """Verify backfill produces correct data structure"""
        result = await backfill_sim.simulate_backfill_symbol('MSFT', '2024-11-05', '2024-11-05')
        
        assert 'symbol' in result
        assert 'total_candles' in result
        assert 'validated_candles' in result
        assert 'validation_rate' in result
        assert 'avg_quality_score' in result
        assert 'candles' in result
        
        assert len(result['candles']) == result['total_candles']
        
        # Check each candle has required fields
        for candle in result['candles']:
            assert 'time' in candle
            assert 'close' in candle
            assert 'volume' in candle
            assert 'quality_score' in candle
            assert 'validated' in candle
            assert 'gap_detected' in candle
            assert 'volume_anomaly' in candle
    
    @pytest.mark.asyncio
    async def test_backfill_ready_for_database(self, backfill_sim):
        """Verify backfill output is ready to insert into database"""
        result = await backfill_sim.simulate_backfill_symbol('AAPL', '2024-11-01', '2024-11-07')
        
        # Verify we have data to insert
        assert result['total_candles'] > 0
        assert len(result['candles']) == result['total_candles']
        
        # Verify quality metrics are acceptable
        assert result['validation_rate'] >= 80.0
        assert result['avg_quality_score'] >= 0.80
        
        # Simulate what database insert would receive
        insert_payload = {
            'symbol': result['symbol'],
            'candles': result['candles'],
            'stats': {
                'total': result['total_candles'],
                'validated': result['validated_candles'],
                'validation_rate': result['validation_rate'],
                'avg_quality': result['avg_quality_score']
            }
        }
        
        print(f"\nDatabase Insert Ready:")
        print(f"  Symbol: {insert_payload['symbol']}")
        print(f"  Candles to insert: {insert_payload['stats']['total']}")
        print(f"  Validation rate: {insert_payload['stats']['validation_rate']:.1f}%")
        print(f"  Average quality: {insert_payload['stats']['avg_quality']:.3f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
