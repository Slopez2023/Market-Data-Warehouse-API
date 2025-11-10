#!/usr/bin/env python3
"""
Load testing runner for Market Data API.
Simulates realistic traffic patterns and generates performance reports.
"""

import asyncio
import time
import json
import sys
from datetime import datetime
from typing import List, Dict
import random

import aiohttp
import asyncio


class LoadTestRunner:
    """Execute load tests against running API"""
    
    def __init__(self, base_url: str = "http://localhost:8000", workers: int = 10):
        self.base_url = base_url
        self.workers = workers
        self.results: List[Dict] = []
        self.symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA"]
        
    async def health_check(self) -> bool:
        """Check if API is responding"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health", timeout=5) as resp:
                    return resp.status == 200
        except Exception as e:
            print(f"Health check failed: {e}")
            return False
    
    async def test_endpoint(
        self,
        endpoint: str,
        method: str = "GET",
        success_status: int = 200
    ) -> Dict:
        """Test a single endpoint"""
        start = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    timeout=10
                ) as resp:
                    await resp.json()
                    duration = (time.time() - start) * 1000
                    return {
                        "success": resp.status == success_status,
                        "status": resp.status,
                        "duration_ms": duration,
                        "endpoint": endpoint
                    }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "status": 0,
                "duration_ms": (time.time() - start) * 1000,
                "error": "timeout",
                "endpoint": endpoint
            }
        except Exception as e:
            return {
                "success": False,
                "status": 0,
                "duration_ms": (time.time() - start) * 1000,
                "error": str(e),
                "endpoint": endpoint
            }
    
    async def test_historical_endpoint(self, symbol: str) -> Dict:
        """Test historical data endpoint"""
        endpoint = f"/api/v1/historical/{symbol}?start=2024-01-01&end=2024-01-31"
        return await self.test_endpoint(endpoint, success_status=200)
    
    async def worker(self, test_func, iterations: int):
        """Worker task executing test function repeatedly"""
        for _ in range(iterations):
            result = await test_func()
            self.results.append(result)
    
    async def run_baseline_test(self):
        """Run baseline performance test"""
        print("\n" + "="*60)
        print("BASELINE PERFORMANCE TEST")
        print("="*60)
        
        if not await self.health_check():
            print("ERROR: API not responding")
            return None
        
        print(f"Testing with {self.workers} concurrent workers...")
        print("Running 100 requests per worker...\n")
        
        # Test various endpoints
        tests = [
            ("Health Check", "/health"),
            ("Status", "/api/v1/status"),
            ("Symbols", "/api/v1/symbols"),
            ("Metrics", "/api/v1/metrics"),
            ("Observability", "/api/v1/observability/metrics"),
        ]
        
        for test_name, endpoint in tests:
            self.results = []
            
            # Create tasks
            tasks = [
                self.worker(
                    lambda e=endpoint: self.test_endpoint(e),
                    iterations=100
                )
                for _ in range(self.workers)
            ]
            
            start = time.time()
            await asyncio.gather(*tasks)
            duration = time.time() - start
            
            # Analyze results
            successful = sum(1 for r in self.results if r["success"])
            failed = len(self.results) - successful
            
            if self.results:
                durations = [r["duration_ms"] for r in self.results]
                avg_duration = sum(durations) / len(durations)
                min_duration = min(durations)
                max_duration = max(durations)
                throughput = len(self.results) / duration
                
                print(f"{test_name}:")
                print(f"  Requests: {len(self.results)} | "
                      f"Success: {successful} | Failed: {failed} | "
                      f"Success Rate: {(successful/len(self.results)*100):.1f}%")
                print(f"  Avg: {avg_duration:.2f}ms | "
                      f"Min: {min_duration:.2f}ms | "
                      f"Max: {max_duration:.2f}ms | "
                      f"Throughput: {throughput:.1f} req/s")
        
        print()
    
    async def run_historical_load_test(self):
        """Test historical data endpoint under load"""
        print("\n" + "="*60)
        print("HISTORICAL DATA ENDPOINT LOAD TEST")
        print("="*60)
        
        if not await self.health_check():
            print("ERROR: API not responding")
            return None
        
        print(f"Testing with {self.workers} concurrent workers...")
        print("Running 50 requests per worker...\n")
        
        self.results = []
        
        # Create tasks
        tasks = [
            self.worker(
                lambda s=random.choice(self.symbols): self.test_historical_endpoint(s),
                iterations=50
            )
            for _ in range(self.workers)
        ]
        
        start = time.time()
        await asyncio.gather(*tasks)
        duration = time.time() - start
        
        # Analyze results
        successful = sum(1 for r in self.results if r["success"])
        failed = len(self.results) - successful
        
        if self.results:
            durations = [r["duration_ms"] for r in self.results]
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            p95_duration = sorted(durations)[int(len(durations) * 0.95)]
            p99_duration = sorted(durations)[int(len(durations) * 0.99)]
            throughput = len(self.results) / duration
            
            print(f"Total Requests: {len(self.results)}")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            print(f"Success Rate: {(successful/len(self.results)*100):.1f}%\n")
            print(f"Response Time Statistics (ms):")
            print(f"  Average:    {avg_duration:.2f}")
            print(f"  Min:        {min_duration:.2f}")
            print(f"  Max:        {max_duration:.2f}")
            print(f"  P95:        {p95_duration:.2f}")
            print(f"  P99:        {p99_duration:.2f}\n")
            print(f"Throughput: {throughput:.1f} req/s")
            print(f"Test Duration: {duration:.2f}s")
        
        print()
    
    async def run_sustained_load_test(self, duration_seconds: int = 60):
        """Run sustained load test for specified duration"""
        print("\n" + "="*60)
        print(f"SUSTAINED LOAD TEST ({duration_seconds}s)")
        print("="*60)
        
        if not await self.health_check():
            print("ERROR: API not responding")
            return None
        
        print(f"Testing with {self.workers} concurrent workers...")
        print(f"Running for {duration_seconds} seconds...\n")
        
        self.results = []
        start_time = time.time()
        
        async def sustained_worker():
            while time.time() - start_time < duration_seconds:
                symbol = random.choice(self.symbols)
                result = await self.test_historical_endpoint(symbol)
                self.results.append(result)
                await asyncio.sleep(0.01)  # Small delay between requests
        
        # Create tasks
        tasks = [sustained_worker() for _ in range(self.workers)]
        
        start = time.time()
        await asyncio.gather(*tasks)
        total_duration = time.time() - start
        
        # Analyze results
        successful = sum(1 for r in self.results if r["success"])
        failed = len(self.results) - successful
        
        if self.results:
            durations = [r["duration_ms"] for r in self.results]
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            throughput = len(self.results) / total_duration
            
            print(f"Total Requests: {len(self.results)}")
            print(f"Successful: {successful}")
            print(f"Failed: {failed}")
            print(f"Success Rate: {(successful/len(self.results)*100):.1f}%\n")
            print(f"Response Time Statistics (ms):")
            print(f"  Average:    {avg_duration:.2f}")
            print(f"  Min:        {min_duration:.2f}")
            print(f"  Max:        {max_duration:.2f}\n")
            print(f"Throughput: {throughput:.1f} req/s")
            print(f"Actual Duration: {total_duration:.2f}s")
        
        print()
    
    async def run_spike_test(self):
        """Test how API handles sudden traffic spike"""
        print("\n" + "="*60)
        print("SPIKE TEST (Sudden Load Increase)")
        print("="*60)
        
        if not await self.health_check():
            print("ERROR: API not responding")
            return None
        
        print("Phase 1: Normal load (10 workers)")
        self.results = []
        tasks = [
            self.worker(
                lambda: self.test_endpoint("/api/v1/status"),
                iterations=50
            )
            for _ in range(10)
        ]
        await asyncio.gather(*tasks)
        normal_results = self.results
        
        print(f"  Requests: {len(normal_results)} | "
              f"Avg Response: {sum(r['duration_ms'] for r in normal_results)/len(normal_results):.2f}ms")
        
        print("Phase 2: Spike (50 workers)")
        self.results = []
        tasks = [
            self.worker(
                lambda: self.test_endpoint("/api/v1/status"),
                iterations=50
            )
            for _ in range(50)
        ]
        await asyncio.gather(*tasks)
        spike_results = self.results
        
        print(f"  Requests: {len(spike_results)} | "
              f"Avg Response: {sum(r['duration_ms'] for r in spike_results)/len(spike_results):.2f}ms")
        
        normal_avg = sum(r["duration_ms"] for r in normal_results) / len(normal_results)
        spike_avg = sum(r["duration_ms"] for r in spike_results) / len(spike_results)
        degradation = ((spike_avg - normal_avg) / normal_avg) * 100
        
        print(f"\nPerformance Degradation: {degradation:.1f}%")
        print()


async def main():
    """Main entry point"""
    print("\n" + "="*60)
    print("MARKET DATA API - LOAD TEST SUITE")
    print(f"Started: {datetime.utcnow().isoformat()}")
    print("="*60)
    
    runner = LoadTestRunner(base_url="http://localhost:8000", workers=10)
    
    # Run all tests
    await runner.run_baseline_test()
    await runner.run_historical_load_test()
    await runner.run_sustained_load_test(duration_seconds=30)
    await runner.run_spike_test()
    
    print("="*60)
    print(f"Completed: {datetime.utcnow().isoformat()}")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
