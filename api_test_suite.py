#!/usr/bin/env python3
"""Comprehensive API test suite"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple

BASE_URL = "http://localhost:8000"
TIMEOUT = 10

class APITester:
    def __init__(self, base_url=BASE_URL):
        self.base_url = base_url
        self.results = []
        self.errors = []
        self.warnings = []
        
    def test_endpoint(self, method: str, endpoint: str, expected_status: int = 200, 
                     params: Dict = None, headers: Dict = None, data: Dict = None) -> Tuple[bool, str, int]:
        """Test a single endpoint"""
        url = f"{self.base_url}{endpoint}"
        try:
            if method.upper() == "GET":
                resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            elif method.upper() == "POST":
                resp = requests.post(url, json=data, headers=headers, timeout=TIMEOUT)
            elif method.upper() == "PUT":
                resp = requests.put(url, json=data, headers=headers, timeout=TIMEOUT)
            elif method.upper() == "DELETE":
                resp = requests.delete(url, headers=headers, timeout=TIMEOUT)
            else:
                return False, f"Unknown method: {method}", 0
            
            success = resp.status_code == expected_status
            status_code = resp.status_code
            
            # Try to parse JSON
            try:
                resp.json()
                message = f"{method} {endpoint} -> {status_code} (OK)"
            except:
                message = f"{method} {endpoint} -> {status_code} (text response)"
            
            return success, message, status_code
        except Exception as e:
            self.errors.append(f"{method} {endpoint}: {str(e)}")
            return False, f"{method} {endpoint} -> ERROR: {str(e)}", 0
    
    def run_tests(self):
        """Run all test categories"""
        print("\n" + "="*70)
        print("MARKET DATA API - COMPREHENSIVE TEST SUITE")
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        print("="*70 + "\n")
        
        # Test 1: Root & Health Endpoints
        print("1. HEALTH & STATUS ENDPOINTS")
        print("-" * 70)
        self._test_health_endpoints()
        
        # Test 2: Data Retrieval Endpoints
        print("\n2. DATA RETRIEVAL ENDPOINTS")
        print("-" * 70)
        self._test_data_endpoints()
        
        # Test 3: Observability Endpoints
        print("\n3. OBSERVABILITY ENDPOINTS")
        print("-" * 70)
        self._test_observability_endpoints()
        
        # Test 4: Performance Endpoints
        print("\n4. PERFORMANCE ENDPOINTS")
        print("-" * 70)
        self._test_performance_endpoints()
        
        # Test 5: Admin Endpoints (auth required)
        print("\n5. ADMIN ENDPOINTS (AUTH REQUIRED)")
        print("-" * 70)
        self._test_admin_endpoints()
        
        # Summary
        print("\n" + "="*70)
        self._print_summary()
        print("="*70 + "\n")
    
    def _test_health_endpoints(self):
        """Test health check endpoints"""
        tests = [
            ("GET", "/", 200),
            ("GET", "/health", 200),
            ("GET", "/api/v1/status", 200),
        ]
        
        for method, endpoint, expected in tests:
            success, msg, status = self.test_endpoint(method, endpoint, expected)
            self.results.append((success, msg))
            print(f"  ✓ {msg}" if success else f"  ✗ {msg}")
    
    def _test_data_endpoints(self):
        """Test data retrieval endpoints"""
        # Test symbols endpoint
        success, msg, _ = self.test_endpoint("GET", "/api/v1/symbols", 200)
        self.results.append((success, msg))
        print(f"  ✓ {msg}" if success else f"  ✗ {msg}")
        
        # Test historical data for different symbols
        symbols = ["AAPL", "MSFT", "GOOGL", "BTC", "ETH"]
        for symbol in symbols:
            params = {"start": "2024-01-01", "end": "2024-01-31"}
            success, msg, status = self.test_endpoint(
                "GET", f"/api/v1/historical/{symbol}", 
                expected_status=200 if symbol in ["AAPL", "MSFT", "GOOGL"] else 404,
                params=params
            )
            self.results.append((success, msg))
            print(f"  ✓ {msg}" if success else f"  ✗ {msg}")
        
        # Test with validated_only parameter
        params = {"start": "2024-01-01", "end": "2024-01-31", "validated_only": "true"}
        success, msg, _ = self.test_endpoint("GET", "/api/v1/historical/AAPL", 200, params=params)
        self.results.append((success, msg))
        print(f"  ✓ {msg}" if success else f"  ✗ {msg}")
        
        # Test with min_quality parameter
        params = {"start": "2024-01-01", "end": "2024-01-31", "min_quality": "0.9"}
        success, msg, _ = self.test_endpoint("GET", "/api/v1/historical/AAPL", 200, params=params)
        self.results.append((success, msg))
        print(f"  ✓ {msg}" if success else f"  ✗ {msg}")
        
        # Test metrics endpoint
        success, msg, _ = self.test_endpoint("GET", "/api/v1/metrics", 200)
        self.results.append((success, msg))
        print(f"  ✓ {msg}" if success else f"  ✗ {msg}")
    
    def _test_observability_endpoints(self):
        """Test observability endpoints"""
        tests = [
            ("GET", "/api/v1/observability/metrics", 200),
            ("GET", "/api/v1/observability/alerts", 200),
        ]
        
        for method, endpoint, expected in tests:
            success, msg, _ = self.test_endpoint(method, endpoint, expected)
            self.results.append((success, msg))
            print(f"  ✓ {msg}" if success else f"  ✗ {msg}")
        
        # Test alerts with limit parameter
        params = {"limit": "50"}
        success, msg, _ = self.test_endpoint("GET", "/api/v1/observability/alerts", 200, params=params)
        self.results.append((success, msg))
        print(f"  ✓ {msg}" if success else f"  ✗ {msg}")
    
    def _test_performance_endpoints(self):
        """Test performance monitoring endpoints"""
        tests = [
            ("GET", "/api/v1/performance/cache", 200),
            ("GET", "/api/v1/performance/queries", 200),
            ("GET", "/api/v1/performance/summary", 200),
        ]
        
        for method, endpoint, expected in tests:
            success, msg, _ = self.test_endpoint(method, endpoint, expected)
            self.results.append((success, msg))
            print(f"  ✓ {msg}" if success else f"  ✗ {msg}")
    
    def _test_admin_endpoints(self):
        """Test admin endpoints (will fail without API key, which is expected)"""
        # Get a dummy API key for testing
        api_key = "test-key-12345"
        headers = {"X-API-Key": api_key}
        
        # These should fail with 401 (Unauthorized) since we don't have a valid key
        tests = [
            ("GET", "/api/v1/admin/symbols", 401, None, headers),
            ("GET", "/api/v1/admin/api-keys", 401, None, headers),
        ]
        
        for method, endpoint, expected, params, hdrs in tests:
            success, msg, status = self.test_endpoint(method, endpoint, expected, params=params, headers=hdrs)
            if status == 401 or status == 403:
                self.results.append((True, msg))
                print(f"  ✓ {msg} (Auth correctly required)")
            else:
                self.results.append((success, msg))
                print(f"  ✗ {msg}")
    
    def _print_summary(self):
        """Print test summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r[0])
        failed = total - passed
        
        print(f"\nTEST RESULTS:")
        print(f"  Total Tests:  {total}")
        print(f"  Passed:       {passed} ({100*passed//total}%)")
        print(f"  Failed:       {failed}")
        
        if self.errors:
            print(f"\nERROR DETAILS:")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\nWARNINGS:")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        print(f"\nAPI STATUS: {'✓ OPERATIONAL' if failed == 0 else '✗ ISSUES DETECTED'}")

def main():
    """Run all tests"""
    tester = APITester()
    
    # Wait for API to be ready
    print("Waiting for API to be ready...")
    for i in range(30):
        try:
            requests.get(f"{BASE_URL}/health", timeout=2)
            print("API is ready!\n")
            break
        except:
            time.sleep(1)
            if i % 5 == 0:
                print(f"  Attempt {i+1}/30...")
    
    # Run tests
    tester.run_tests()

if __name__ == "__main__":
    main()
