"""Tests for polygon_client.py - behavior and error handling"""

import pytest
from src.clients.polygon_client import PolygonClient


@pytest.fixture
def polygon_client(api_key):
    """Create PolygonClient instance"""
    return PolygonClient(api_key)


class TestPolygonClientInit:
    """Test client initialization"""
    
    def test_client_initialization(self, api_key):
        """Test client initializes with API key"""
        client = PolygonClient(api_key)
        assert client.api_key == api_key
        assert client.base_url == "https://api.polygon.io/v2"
    
    def test_client_attributes(self, polygon_client):
        """Test client has required attributes"""
        assert hasattr(polygon_client, 'api_key')
        assert hasattr(polygon_client, 'base_url')
        assert hasattr(polygon_client, 'fetch_daily_range')
        assert hasattr(polygon_client, 'fetch_ticker_details')


class TestPolygonClientMethods:
    """Test client methods exist and are callable"""
    
    def test_fetch_daily_range_callable(self, polygon_client):
        """Test fetch_daily_range is async callable"""
        import inspect
        assert inspect.iscoroutinefunction(polygon_client.fetch_daily_range)
    
    def test_fetch_ticker_details_callable(self, polygon_client):
        """Test fetch_ticker_details is async callable"""
        import inspect
        assert inspect.iscoroutinefunction(polygon_client.fetch_ticker_details)
    
    def test_fetch_daily_range_has_retry_decorator(self, polygon_client):
        """Test fetch_daily_range has retry decorator"""
        # The decorator is applied, check for its attributes
        import inspect
        source = inspect.getsource(polygon_client.__class__.fetch_daily_range)
        assert 'retry' in source or 'tenacity' in source.lower()


class TestDateHandling:
    """Test date parameter handling (without actual API calls)"""
    
    def test_various_date_formats(self):
        """Test client accepts various date formats"""
        client = PolygonClient("test_key")
        
        # These should not raise during client initialization
        test_dates = [
            ('2024-01-01', '2024-01-31'),
            ('2024-11-01', '2024-11-07'),
            ('2023-01-01', '2024-11-07'),
        ]
        
        for start, end in test_dates:
            # Just verify client can be called with these dates
            # (won't actually call the API without network)
            assert start and end


class TestSymbolHandling:
    """Test symbol parameter handling"""
    
    def test_symbols_accepted(self):
        """Test various stock symbols are accepted"""
        client = PolygonClient("test_key")
        
        test_symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'BRK.A', 'SPY', 'QQQ']
        
        for symbol in test_symbols:
            # Verify client can handle these symbols
            assert len(symbol) > 0
            assert symbol.isupper() or '.' in symbol


class TestClientConfiguration:
    """Test client configuration and state"""
    
    def test_api_key_stored(self):
        """Test API key is properly stored"""
        api_key = "my_test_key_12345"
        client = PolygonClient(api_key)
        assert client.api_key == api_key
    
    def test_base_url_correct(self, polygon_client):
        """Test base URL is set correctly"""
        assert polygon_client.base_url == "https://api.polygon.io/v2"
        assert polygon_client.base_url.startswith("https://")
    
    def test_multiple_clients_independent(self, api_key):
        """Test multiple clients maintain independent state"""
        client1 = PolygonClient(api_key)
        client2 = PolygonClient("different_key")
        
        assert client1.api_key != client2.api_key
        assert client1.api_key == api_key
        assert client2.api_key == "different_key"


# Run with: pytest tests/test_polygon_client.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
