"""
Test script for Market Data Client
Tests all endpoints and error handling
"""

import os
import sys
from market_data_client import (
    MarketDataClient, 
    ValidationError, 
    AuthenticationError,
    APIConnectionError
)

# Set credentials
API_KEY = "mdw_2ed1a9e0944f8c1a17b8d59a49a87e29b3529fbbeadaf6b5d3ec960ca7fba19a"
API_URL = "http://localhost:8000"

def test_client_initialization():
    """Test client initialization"""
    print("\n=== Test: Client Initialization ===")
    try:
        client = MarketDataClient(api_url=API_URL, api_key=API_KEY)
        print("✓ Client initialized successfully")
        print(f"  API URL: {client.api_url}")
        print(f"  Timeframes supported: {sorted(client.ALLOWED_TIMEFRAMES)}")
        return client
    except Exception as e:
        print(f"✗ Failed: {e}")
        return None

def test_health_check(client):
    """Test health check endpoint"""
    print("\n=== Test: Health Check ===")
    try:
        is_healthy = client.health_check()
        print(f"✓ Health check: {'Healthy' if is_healthy else 'Unhealthy'}")
    except Exception as e:
        print(f"✗ Failed: {e}")

def test_get_status(client):
    """Test status endpoint"""
    print("\n=== Test: Get Status ===")
    try:
        status = client.get_status()
        print(f"✓ Status retrieved")
        print(f"  API Version: {status['api_version']}")
        print(f"  Available Symbols: {status['database']['symbols_available']}")
        print(f"  Total Records: {status['database']['total_records']:,}")
        print(f"  Validation Rate: {status['database']['validation_rate_pct']:.1f}%")
        print(f"  Scheduler: {status['data_quality']['scheduler_status']}")
    except Exception as e:
        print(f"✗ Failed: {e}")

def test_get_symbols(client):
    """Test symbols endpoint"""
    print("\n=== Test: Get Symbols ===")
    try:
        symbols = client.get_symbols()
        print(f"✓ Symbols retrieved")
        print(f"  Available: {symbols['symbols_available']}")
        print(f"  Latest Data: {symbols['latest_data']}")
    except Exception as e:
        print(f"✗ Failed: {e}")

def test_get_historical_data(client):
    """Test historical data endpoint"""
    print("\n=== Test: Get Historical Data ===")
    try:
        data = client.get_historical_data(
            symbol="AAPL",
            timeframe="1d",
            start="2024-11-01",
            end="2024-11-15"
        )
        print(f"✓ Historical data retrieved")
        print(f"  Symbol: {data.symbol}")
        print(f"  Timeframe: {data.timeframe}")
        print(f"  Candles: {data.count}")
        print(f"  Date Range: {data.start_date} to {data.end_date}")
        
        if data.candles:
            first = data.candles[0]
            print(f"  First Candle: {first.time} | O:{first.open} H:{first.high} L:{first.low} C:{first.close} V:{first.volume}")
            print(f"  Validated: {first.validated} | Quality: {first.quality_score}")
    except Exception as e:
        print(f"✗ Failed: {e}")

def test_get_quant_features(client):
    """Test quant features endpoint"""
    print("\n=== Test: Get Quant Features ===")
    try:
        features = client.get_quant_features(
            symbol="AAPL",
            timeframe="1d",
            limit=3
        )
        print(f"✓ Quant features retrieved")
        print(f"  Symbol: {features.symbol}")
        print(f"  Timeframe: {features.timeframe}")
        print(f"  Records: {features.records_returned}")
        print(f"  Date Range: {features.date_range}")
        
        if features.parsed_features:
            feat = features.parsed_features[0]
            print(f"  First Feature:")
            print(f"    Time: {feat.time}")
            print(f"    Close: {feat.close}")
            print(f"    Return 1D: {feat.return_1d:.6f}")
            print(f"    Volatility 20: {feat.volatility_20:.4f}")
            print(f"    ATR: {feat.atr:.2f}")
            print(f"    Trend: {feat.trend_direction}")
            print(f"    Structure: {feat.structure_label}")
    except Exception as e:
        print(f"✗ Failed: {e}")

def test_get_data_quality(client):
    """Test data quality endpoint"""
    print("\n=== Test: Get Data Quality ===")
    try:
        quality = client.get_data_quality(symbol="AAPL", days=7)
        print(f"✓ Data quality report retrieved")
        print(f"  Symbol: {quality['symbol']}")
        print(f"  Period: {quality['period_days']} days")
        print(f"  Summary:")
        print(f"    Avg Validation Rate: {quality['summary']['avg_validation_rate']:.1f}%")
        print(f"    Avg Quality Score: {quality['summary']['avg_quality_score']:.2f}")
        print(f"    Gaps Detected: {quality['summary']['total_gaps_detected']}")
    except Exception as e:
        print(f"✗ Failed: {e}")

def test_validation_errors(client):
    """Test parameter validation"""
    print("\n=== Test: Validation Errors ===")
    
    # Invalid timeframe
    try:
        client.get_historical_data("AAPL", timeframe="invalid", start="2024-01-01", end="2024-12-31")
        print("✗ Should have raised ValidationError for invalid timeframe")
    except ValidationError as e:
        print(f"✓ Caught invalid timeframe: {e}")
    
    # Invalid date format
    try:
        client.get_historical_data("AAPL", timeframe="1d", start="01-01-2024", end="2024-12-31")
        print("✗ Should have raised ValidationError for invalid date")
    except ValidationError as e:
        print(f"✓ Caught invalid date: {e}")
    
    # Missing dates
    try:
        client.get_historical_data("AAPL", timeframe="1d")
        print("✗ Should have raised ValidationError for missing dates")
    except ValidationError as e:
        print(f"✓ Caught missing dates: {e}")
    
    # Invalid quality score
    try:
        client.get_historical_data("AAPL", timeframe="1d", start="2024-01-01", end="2024-12-31", min_quality=1.5)
        print("✗ Should have raised ValidationError for invalid quality")
    except ValidationError as e:
        print(f"✓ Caught invalid quality: {e}")
    
    # Invalid limit
    try:
        client.get_quant_features("AAPL", limit=50000)
        print("✗ Should have raised ValidationError for invalid limit")
    except ValidationError as e:
        print(f"✓ Caught invalid limit: {e}")

def test_context_manager(client):
    """Test context manager usage"""
    print("\n=== Test: Context Manager ===")
    try:
        with MarketDataClient(api_url=API_URL, api_key=API_KEY) as ctx_client:
            status = ctx_client.get_status()
            print(f"✓ Context manager works")
            print(f"  Symbols: {status['database']['symbols_available']}")
        print("✓ Context manager closed successfully")
    except Exception as e:
        print(f"✗ Failed: {e}")

def test_invalid_auth():
    """Test invalid authentication"""
    print("\n=== Test: Invalid Authentication ===")
    try:
        bad_client = MarketDataClient(api_url=API_URL, api_key="mdw_invalid_key_12345")
        bad_client.get_status()
        print("✗ Should have raised AuthenticationError")
    except AuthenticationError as e:
        print(f"✓ Caught auth error: {e}")
    except Exception as e:
        print(f"✓ Caught error: {type(e).__name__}: {e}")

def run_all_tests():
    """Run all tests"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║     Market Data Client - Comprehensive Test Suite          ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    # Initialize client
    client = test_client_initialization()
    if not client:
        print("\n✗ Cannot continue without client")
        return
    
    # Run tests
    test_health_check(client)
    test_get_status(client)
    test_get_symbols(client)
    test_get_historical_data(client)
    test_get_quant_features(client)
    test_get_data_quality(client)
    test_validation_errors(client)
    test_context_manager(client)
    test_invalid_auth()
    
    # Cleanup
    client.close()
    
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║                   Tests Complete                           ║")
    print("╚════════════════════════════════════════════════════════════╝\n")

if __name__ == "__main__":
    run_all_tests()
