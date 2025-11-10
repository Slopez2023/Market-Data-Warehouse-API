"""Load testing suite for Market Data API"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Dict
import pytest
from concurrent.futures import ThreadPoolExecutor

from src.services.structured_logging import StructuredLogger
from src.services.caching import init_query_cache, get_query_cache
from src.services.performance_monitor import init_performance_monitor, get_performance_monitor

logger = StructuredLogger(__name__)


class LoadTestResults:
    """Store and analyze load test results"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.results: List[Dict] = []
        self.start_time = None
        self.end_time = None
    
    def add_result(self, duration_ms: float, success: bool, error: str = None):
        """Add a test result"""
        self.results.append({
            "duration_ms": duration_ms,
            "success": success,
            "error": error,
            "timestamp": datetime.utcnow()
        })
    
    def start(self):
        """Mark test start"""
        self.start_time = time.time()
    
    def stop(self):
        """Mark test end"""
        self.end_time = time.time()
    
    @property
    def duration_seconds(self) -> float:
        """Total test duration"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0
    
    @property
    def successful_count(self) -> int:
        """Count of successful requests"""
        return sum(1 for r in self.results if r["success"])
    
    @property
    def failed_count(self) -> int:
        """Count of failed requests"""
        return sum(1 for r in self.results if not r["success"])
    
    @property
    def success_rate(self) -> float:
        """Success rate percentage"""
        if not self.results:
            return 0
        return (self.successful_count / len(self.results)) * 100
    
    @property
    def avg_response_time_ms(self) -> float:
        """Average response time"""
        if not self.results:
            return 0
        return sum(r["duration_ms"] for r in self.results) / len(self.results)
    
    @property
    def min_response_time_ms(self) -> float:
        """Minimum response time"""
        if not self.results:
            return 0
        return min(r["duration_ms"] for r in self.results)
    
    @property
    def max_response_time_ms(self) -> float:
        """Maximum response time"""
        if not self.results:
            return 0
        return max(r["duration_ms"] for r in self.results)
    
    @property
    def throughput_rps(self) -> float:
        """Requests per second"""
        if self.duration_seconds == 0:
            return 0
        return len(self.results) / self.duration_seconds
    
    def summary(self) -> Dict:
        """Get summary of test results"""
        return {
            "test_name": self.test_name,
            "total_requests": len(self.results),
            "successful": self.successful_count,
            "failed": self.failed_count,
            "success_rate_pct": round(self.success_rate, 2),
            "avg_response_ms": round(self.avg_response_time_ms, 2),
            "min_response_ms": round(self.min_response_time_ms, 2),
            "max_response_ms": round(self.max_response_time_ms, 2),
            "duration_seconds": round(self.duration_seconds, 2),
            "throughput_rps": round(self.throughput_rps, 2),
        }
    
    def print_summary(self):
        """Print formatted summary"""
        summary = self.summary()
        print(f"\n{'='*60}")
        print(f"Load Test: {summary['test_name']}")
        print(f"{'='*60}")
        print(f"Total Requests: {summary['total_requests']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"Success Rate: {summary['success_rate_pct']}%")
        print(f"Avg Response Time: {summary['avg_response_ms']}ms")
        print(f"Min Response Time: {summary['min_response_ms']}ms")
        print(f"Max Response Time: {summary['max_response_ms']}ms")
        print(f"Total Duration: {summary['duration_seconds']}s")
        print(f"Throughput: {summary['throughput_rps']} req/s")
        print(f"{'='*60}\n")


# Fixtures

@pytest.fixture
def cache():
    """Initialize query cache for tests"""
    return init_query_cache(max_size=1000)


@pytest.fixture
def monitor():
    """Initialize performance monitor for tests"""
    return init_performance_monitor(window_hours=24)


# Cache Performance Tests

class TestCachePerformance:
    """Test caching effectiveness"""
    
    async def test_cache_hit_rate(self, cache):
        """Test that cache improves hit rate"""
        # Set some values
        for i in range(100):
            await cache.set("test", f"value_{i}", ttl=60, id=i)
        
        # Access same values multiple times
        hits_before = cache.hits
        for i in range(100):
            await cache.get("test", id=i)
        
        hits_after = cache.hits
        assert hits_after > hits_before
        assert cache.hit_rate > 0
    
    async def test_cache_ttl_expiration(self, cache):
        """Test that cache respects TTL"""
        import time
        
        await cache.set("short", "value", ttl=1, key="test")
        
        # Immediate access should hit
        val1 = await cache.get("short", key="test")
        assert val1 == "value"
        
        # After expiration should miss
        time.sleep(1.1)
        val2 = await cache.get("short", key="test")
        assert val2 is None
    
    async def test_cache_eviction(self, cache):
        """Test that cache evicts when full"""
        small_cache = init_query_cache(max_size=10)
        
        # Fill cache beyond capacity
        for i in range(20):
            await small_cache.set("test", f"value_{i}", ttl=3600, id=i)
        
        # Should not exceed max size
        assert len(small_cache.cache) <= 10
    
    async def test_cache_stats(self, cache):
        """Test cache statistics"""
        stats_before = cache.stats()
        assert stats_before["size"] == 0
        
        # Add entries
        for i in range(10):
            await cache.set("test", f"value_{i}", ttl=60, id=i)
        
        stats_after = cache.stats()
        assert stats_after["size"] == 10


# Performance Monitoring Tests

class TestPerformanceMonitoring:
    """Test performance monitoring"""
    
    async def test_query_recording(self, monitor):
        """Test recording query execution"""
        await monitor.record_query("fetch", 100.5, success=True, symbol="AAPL")
        
        summary = await monitor.get_summary()
        assert summary["total_queries"] == 1
        assert summary["successful"] == 1
    
    async def test_failure_tracking(self, monitor):
        """Test tracking of failed queries"""
        await monitor.record_query("fetch", 50, success=True)
        await monitor.record_query("fetch", 75, success=False, error="timeout")
        
        summary = await monitor.get_summary()
        assert summary["failed"] == 1
        assert summary["error_rate_pct"] == 50.0
    
    async def test_bottleneck_detection(self, monitor):
        """Test detection of slow queries"""
        # Record some normal queries
        for i in range(10):
            await monitor.record_query("fetch", 50 + i*2, success=True)
        
        # Record slow queries
        for i in range(5):
            await monitor.record_query("fetch", 200 + i*10, success=True)
        
        bottlenecks = await monitor.get_bottlenecks(threshold_ms=150)
        assert len(bottlenecks) > 0
        assert bottlenecks[0]["slow_count"] >= 5
    
    async def test_percentile_stats(self, monitor):
        """Test percentile calculations"""
        # Record queries with known distribution
        for i in range(100):
            await monitor.record_query("fetch", i * 10 + 1, success=True)  # +1 to ensure max > p99
        
        stats = await monitor.get_stats()
        assert stats["p95_ms"] >= stats["median_ms"]
        assert stats["p99_ms"] >= stats["p95_ms"]
        assert stats["max_ms"] >= stats["p99_ms"]


# Load Test Scenarios

class TestLoadScenarios:
    """Simulate realistic load scenarios"""
    
    async def test_concurrent_cache_access(self, cache):
        """Test cache with concurrent access"""
        results = LoadTestResults("concurrent_cache_access")
        results.start()
        
        async def access_cache(cache_id: int):
            for i in range(50):
                await cache.set(f"test_{cache_id}", f"value_{i}", ttl=60, key=i)
                val = await cache.get(f"test_{cache_id}", key=i)
                results.add_result(0, val is not None)
        
        # Run concurrent tasks
        await asyncio.gather(*[access_cache(i) for i in range(10)])
        results.stop()
        
        assert results.successful_count > 0
        assert results.success_rate >= 90
    
    async def test_monitoring_under_load(self, monitor):
        """Test monitoring with high query volume"""
        results = LoadTestResults("monitoring_under_load")
        results.start()
        
        async def record_queries(batch_id: int):
            for i in range(100):
                duration = 10 + (i % 50)
                await monitor.record_query(
                    f"query_type_{batch_id % 5}",
                    duration,
                    success=i % 20 != 0,  # 95% success rate
                    symbol="AAPL"
                )
                results.add_result(duration, True)
        
        # Simulate 10 concurrent workers
        await asyncio.gather(*[record_queries(i) for i in range(10)])
        results.stop()
        
        # Verify monitoring handled load
        summary = await monitor.get_summary()
        assert summary["total_queries"] == 1000
        assert summary["error_rate_pct"] < 10


# Baseline Performance Tests

class TestBaselinePerformance:
    """Establish baseline performance metrics"""
    
    async def test_cache_baseline(self, cache):
        """Establish cache performance baseline"""
        results = LoadTestResults("cache_baseline")
        results.start()
        
        # Warm up cache
        for i in range(100):
            await cache.set("baseline", f"value_{i}", ttl=3600, id=i)
        
        # Measure cache hits
        for _ in range(1000):
            for i in range(100):
                start = time.time()
                val = await cache.get("baseline", id=i)
                duration = (time.time() - start) * 1000
                results.add_result(duration, val is not None)
        
        results.stop()
        
        # Cache hits should be fast (<1ms typically)
        assert results.avg_response_time_ms < 5
        assert results.success_rate == 100
        
        results.print_summary()
    
    async def test_monitoring_baseline(self, monitor):
        """Establish monitoring performance baseline"""
        results = LoadTestResults("monitoring_baseline")
        results.start()
        
        # Record 10k queries
        for i in range(10000):
            start = time.time()
            await monitor.record_query(
                f"type_{i % 10}",
                i % 100 + 10,
                success=i % 50 != 0,
                symbol="TEST"
            )
            duration = (time.time() - start) * 1000
            results.add_result(duration, True)
        
        results.stop()
        
        # Recording should be fast
        assert results.avg_response_time_ms < 10
        assert results.throughput_rps > 1000
        
        results.print_summary()


# Stress Tests

class TestStressScenarios:
    """Test system under stress"""
    
    async def test_cache_memory_stress(self):
        """Test cache memory usage under stress"""
        cache = init_query_cache(max_size=10000)
        
        # Fill cache with large values
        for i in range(10000):
            large_value = "x" * 1000  # 1KB per entry
            await cache.set("stress", large_value, ttl=3600, id=i)
        
        # Verify cache enforces size limit
        assert len(cache.cache) == 10000
        
        stats = cache.stats()
        assert stats["size"] == 10000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
