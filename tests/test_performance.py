"""Performance tests - API endpoints, database queries, and concurrent load"""

import pytest
import asyncio
import time
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import statistics
from dotenv import load_dotenv

from src.clients.polygon_client import PolygonClient
from src.services.validation_service import ValidationService

load_dotenv()


@pytest.fixture
def polygon_client(api_key):
    return PolygonClient(api_key)


@pytest.fixture
def validation_service():
    return ValidationService()


@pytest.mark.performance
class TestEndpointPerformance:
    """Test API endpoint response times"""
    
    @pytest.mark.asyncio
    async def test_polygon_fetch_single_symbol_latency(self, polygon_client):
        """Measure latency of fetching single symbol from Polygon API"""
        start = time.time()
        data = await polygon_client.fetch_daily_range('AAPL', '2024-11-05', '2024-11-07')
        elapsed = time.time() - start
        
        assert len(data) > 0
        # Polygon API should respond in <2 seconds
        assert elapsed < 2.0, f"Polygon fetch took {elapsed:.2f}s (target: <2.0s)"
        print(f"\n✓ Single symbol fetch: {elapsed:.3f}s")
    
    @pytest.mark.asyncio
    async def test_polygon_fetch_multiple_calls_throughput(self, polygon_client):
        """Measure throughput of multiple sequential API calls"""
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
        start = time.time()
        
        for symbol in symbols:
            await polygon_client.fetch_daily_range(symbol, '2024-11-05', '2024-11-07')
        
        elapsed = time.time() - start
        avg_time = elapsed / len(symbols)
        
        # Should handle 5 sequential calls in <8 seconds (avg 1.6s per call)
        assert elapsed < 8.0, f"5 sequential calls took {elapsed:.2f}s (target: <8.0s)"
        print(f"\n✓ 5 sequential calls: {elapsed:.2f}s total, {avg_time:.3f}s avg per call")
    
    @pytest.mark.asyncio
    async def test_polygon_fetch_concurrent_requests(self, polygon_client):
        """Measure performance of concurrent API calls"""
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
        start = time.time()
        
        # Create concurrent tasks
        tasks = [
            polygon_client.fetch_daily_range(symbol, '2024-11-05', '2024-11-07')
            for symbol in symbols
        ]
        results = await asyncio.gather(*tasks)
        
        elapsed = time.time() - start
        
        assert all(len(r) > 0 for r in results)
        # Concurrent calls should be significantly faster than sequential
        assert elapsed < 5.0, f"5 concurrent calls took {elapsed:.2f}s (target: <5.0s)"
        print(f"\n✓ 5 concurrent calls: {elapsed:.2f}s (speedup vs sequential)")


@pytest.mark.performance
class TestValidationPerformance:
     """Test validation service performance"""
    
    @pytest.mark.asyncio
    async def test_validation_throughput_single_symbol(self, polygon_client, validation_service):
        """Measure validation throughput for single symbol"""
        # Use recent data (free tier available) instead of 2019 (requires premium)
        candles = await polygon_client.fetch_daily_range('AAPL', '2024-01-01', '2024-11-07')
        
        start = time.time()
        median_vol = validation_service.calculate_median_volume(candles)
        
        for candle in candles:
            validation_service.validate_candle('AAPL', candle, median_volume=median_vol)
        
        elapsed = time.time() - start
        throughput = len(candles) / elapsed if elapsed > 0 else 0
        
        # Should process >1000 candles/second
        assert throughput > 1000, f"Validation throughput: {throughput:.0f} candles/sec (target: >1000)"
        print(f"\n✓ Validation throughput: {throughput:.0f} candles/sec ({len(candles)} candles in {elapsed:.3f}s)")
    
    @pytest.mark.asyncio
    async def test_validation_quality_scoring_latency(self, polygon_client, validation_service):
        """Measure individual candle validation latency"""
        candles = await polygon_client.fetch_daily_range('MSFT', '2024-11-01', '2024-11-30')
        median_vol = validation_service.calculate_median_volume(candles)
        
        # Measure 100 validations
        times = []
        for candle in candles[:100]:
            start = time.time()
            validation_service.validate_candle('MSFT', candle, median_volume=median_vol)
            elapsed = time.time() - start
            times.append(elapsed * 1000)  # Convert to ms
        
        avg_ms = statistics.mean(times)
        max_ms = max(times)
        
        # Individual validations should be <1ms
        assert avg_ms < 1.0, f"Validation avg latency: {avg_ms:.3f}ms (target: <1.0ms)"
        print(f"\n✓ Validation latency - Avg: {avg_ms:.3f}ms, Max: {max_ms:.3f}ms")
    
    @pytest.mark.asyncio
    async def test_median_volume_calculation_latency(self, polygon_client, validation_service):
        """Measure median volume calculation for large dataset"""
        # Test with full year of data
        candles = await polygon_client.fetch_daily_range('GOOGL', '2024-01-01', '2024-11-07')
        
        start = time.time()
        median_vol = validation_service.calculate_median_volume(candles)
        elapsed = time.time() - start
        
        assert median_vol > 0
        # Median calculation should be fast even for large datasets
        assert elapsed < 0.1, f"Median calculation took {elapsed:.3f}s (target: <0.1s)"
        print(f"\n✓ Median volume calculation ({len(candles)} candles): {elapsed*1000:.2f}ms")


@pytest.mark.performance
class TestConcurrentLoad:
     """Test behavior under concurrent load"""
    
    @pytest.mark.asyncio
    async def test_concurrent_validation_load(self, polygon_client, validation_service):
        """Test validation service under concurrent load"""
        # Fetch data for multiple symbols
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
        tasks = [
            polygon_client.fetch_daily_range(symbol, '2024-11-01', '2024-11-07')
            for symbol in symbols
        ]
        all_candles = await asyncio.gather(*tasks)
        
        start = time.time()
        
        # Validate all candles concurrently
        validation_tasks = []
        for symbol, candles in zip(symbols, all_candles):
            median_vol = validation_service.calculate_median_volume(candles)
            for candle in candles:
                # Create async-friendly validation (wrapped for compatibility)
                validation_tasks.append(
                    self._validate_candle_async(
                        validation_service, symbol, candle, median_vol
                    )
                )
        
        results = await asyncio.gather(*validation_tasks)
        elapsed = time.time() - start
        
        assert len(results) > 0
        total_candles = sum(len(c) for c in all_candles)
        throughput = total_candles / elapsed if elapsed > 0 else 0
        
        print(f"\n✓ Concurrent validation - {total_candles} candles in {elapsed:.2f}s ({throughput:.0f} candles/sec)")
    
    @staticmethod
    async def _validate_candle_async(validation_service, symbol, candle, median_vol):
        """Async wrapper for validation (runs in event loop)"""
        return validation_service.validate_candle(symbol, candle, median_volume=median_vol)
    
    @pytest.mark.asyncio
    async def test_multiple_symbol_concurrent_fetch(self, polygon_client):
        """Test fetching many symbols concurrently"""
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'FB', 'NFLX', 'GOOG', 'ASML']
        
        start = time.time()
        tasks = [
            polygon_client.fetch_daily_range(symbol, '2024-11-01', '2024-11-07')
            for symbol in symbols
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start
        
        # Count successful fetches
        successful = sum(1 for r in results if isinstance(r, list) and len(r) > 0)
        assert successful >= 8, f"Only {successful}/10 symbols fetched successfully"
        
        # Should complete in reasonable time
        assert elapsed < 10.0, f"10 concurrent fetches took {elapsed:.2f}s (target: <10.0s)"
        print(f"\n✓ 10 concurrent symbol fetches: {elapsed:.2f}s, {successful}/10 successful")


@pytest.mark.performance
class TestMemoryEfficiency:
     """Test memory usage and data handling efficiency"""
    
    @pytest.mark.asyncio
    async def test_large_dataset_handling(self, polygon_client, validation_service):
        """Test handling of large dataset (full year)"""
        # Fetch full year of data
        start_time = time.time()
        candles = await polygon_client.fetch_daily_range('SPY', '2024-01-01', '2024-11-07')
        fetch_time = time.time() - start_time
        
        assert len(candles) > 200, f"SPY should have >200 trading days in a year, got {len(candles)}"
        
        # Validate all candles
        start_time = time.time()
        median_vol = validation_service.calculate_median_volume(candles)
        validated_count = 0
        
        for candle in candles:
            quality, meta = validation_service.validate_candle('SPY', candle, median_volume=median_vol)
            if meta['validated']:
                validated_count += 1
        
        validation_time = time.time() - start_time
        
        # Should handle large dataset efficiently
        assert validated_count / len(candles) > 0.9, f"Validation rate too low: {validated_count}/{len(candles)}"
        print(f"\n✓ Large dataset handling:")
        print(f"  - Fetch time: {fetch_time:.2f}s ({len(candles)} candles)")
        print(f"  - Validation time: {validation_time:.2f}s")
        print(f"  - Validation rate: {validated_count/len(candles)*100:.1f}%")
    
    @pytest.mark.asyncio
    async def test_batch_processing_efficiency(self, polygon_client, validation_service):
        """Test efficiency of batch processing multiple symbols"""
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']
        batch_start = time.time()
        
        all_data = []
        for symbol in symbols:
            candles = await polygon_client.fetch_daily_range(symbol, '2024-11-01', '2024-11-07')
            median_vol = validation_service.calculate_median_volume(candles)
            
            for candle in candles:
                quality, meta = validation_service.validate_candle(symbol, candle, median_volume=median_vol)
                all_data.append({
                    'symbol': symbol,
                    'quality': quality,
                    'validated': meta['validated']
                })
        
        batch_time = time.time() - batch_start
        total_records = len(all_data)
        
        print(f"\n✓ Batch processing ({len(symbols)} symbols):")
        print(f"  - Total records: {total_records}")
        print(f"  - Time: {batch_time:.2f}s")
        print(f"  - Throughput: {total_records/batch_time:.0f} records/sec")


@pytest.mark.performance
class TestDataQualityPerformance:
     """Test performance of quality filtering and analytics"""
    
    @pytest.mark.asyncio
    async def test_quality_filtering_performance(self, polygon_client, validation_service):
        """Measure performance of filtering by quality threshold"""
        candles = await polygon_client.fetch_daily_range('AAPL', '2024-01-01', '2024-11-07')
        median_vol = validation_service.calculate_median_volume(candles)
        
        # Calculate quality scores for all candles
        start = time.time()
        quality_scores = []
        for candle in candles:
            quality, _ = validation_service.validate_candle('AAPL', candle, median_volume=median_vol)
            quality_scores.append(quality)
        
        # Filter by quality thresholds
        high_quality = sum(1 for q in quality_scores if q >= 0.95)
        good_quality = sum(1 for q in quality_scores if q >= 0.85)
        
        elapsed = time.time() - start
        
        print(f"\n✓ Quality filtering ({len(candles)} candles in {elapsed:.2f}s):")
        print(f"  - High quality (≥0.95): {high_quality} ({high_quality/len(candles)*100:.1f}%)")
        print(f"  - Good quality (≥0.85): {good_quality} ({good_quality/len(candles)*100:.1f}%)")


@pytest.mark.performance
class TestRegressionPerformance:
     """Regression tests to ensure performance doesn't degrade"""
    
    @pytest.mark.asyncio
    async def test_health_check_response_time(self, polygon_client, validation_service):
        """Baseline test for health check - should be very fast"""
        # Health check equivalent: validate a single candle
        candle = {'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.5, 'v': 1000000, 't': 1000000}
        
        times = []
        for _ in range(100):
            start = time.time()
            validation_service.validate_candle('TEST', candle, median_volume=1000000)
            times.append((time.time() - start) * 1000)  # ms
        
        avg_ms = statistics.mean(times)
        max_ms = max(times)
        
        # Health check should be <5ms on average
        assert avg_ms < 5.0, f"Health check latency: {avg_ms:.2f}ms (target: <5ms)"
        print(f"\n✓ Health check latency: {avg_ms:.2f}ms avg, {max_ms:.2f}ms max")
    
    @pytest.mark.asyncio
    async def test_status_endpoint_complexity(self, polygon_client, validation_service):
        """Baseline test for status endpoint - aggregates many metrics"""
        # Simulate status endpoint: fetch and validate multiple symbols
        symbols = ['AAPL', 'MSFT', 'GOOGL']
        
        start = time.time()
        
        for symbol in symbols:
            candles = await polygon_client.fetch_daily_range(symbol, '2024-11-05', '2024-11-07')
            median_vol = validation_service.calculate_median_volume(candles)
            
            total = len(candles)
            validated = 0
            
            for candle in candles:
                _, meta = validation_service.validate_candle(symbol, candle, median_volume=median_vol)
                if meta['validated']:
                    validated += 1
        
        elapsed = time.time() - start
        
        # Status endpoint aggregation should be reasonable
        assert elapsed < 10.0, f"Status aggregation took {elapsed:.2f}s (target: <10s)"
        print(f"\n✓ Status endpoint aggregation (3 symbols): {elapsed:.2f}s")


# Run with: pytest tests/test_performance.py -v -s
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
