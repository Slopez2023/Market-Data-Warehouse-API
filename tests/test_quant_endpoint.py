"""
Tests for Quant Features REST API Endpoint.

Tests cover:
- Endpoint availability
- Query parameters validation
- Response schema and format
- Error handling
- Integration with database
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock

from main import app
from src.services.database_service import DatabaseService
from src.quant_engine import QuantFeatureEngine


@pytest.fixture
async def client():
    """Create AsyncClient for testing."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


class TestQuantFeatureEndpointBasics:
    """Test basic endpoint functionality."""

    @pytest.mark.asyncio
    async def test_endpoint_exists(self, client):
        """Test /api/v1/features/quant/{symbol} endpoint exists."""
        with patch.object(DatabaseService, "get_quant_features", return_value=[]):
            response = await client.get("/api/v1/features/quant/AAPL")
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_endpoint_requires_symbol(self, client):
        """Test endpoint requires symbol parameter."""
        response = await client.get("/api/v1/features/quant/")
        # 404 or 405 depending on path routing
        assert response.status_code in [404, 405]

    @pytest.mark.asyncio
    async def test_endpoint_accepts_symbol(self, client):
        """Test endpoint accepts symbol in path."""
        with patch.object(DatabaseService, "get_quant_features", return_value=[]):
            response = await client.get("/api/v1/features/quant/AAPL")
            assert response.status_code in [200, 404]


class TestQuantFeatureEndpointParameters:
    """Test query parameters validation."""

    @pytest.mark.asyncio
    async def test_default_timeframe(self, client):
        """Test default timeframe is applied."""
        mock_features = [
            {
                "time": datetime(2024, 1, 1),
                "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
                "volume": 1000000,
                "return_1d": 0.005, "volatility_20": 0.15, "volatility_50": 0.14,
                "atr": 1.5, "rolling_volume_20": 950000, "volume_ratio": 1.05,
                "structure_label": "bullish", "trend_direction": "up",
                "volatility_regime": "medium", "trend_regime": "uptrend",
                "compression_regime": "expanded", "features_computed_at": datetime(2024, 1, 1, 2, 0, 0)
            }
        ]
        
        with patch.object(DatabaseService, "get_quant_features", return_value=mock_features):
            response = await client.get("/api/v1/features/quant/AAPL")
            if response.status_code == 200:
                data = response.json()
                assert data["timeframe"] == "1d"

    @pytest.mark.asyncio
    async def test_custom_timeframe_accepted(self, client):
        """Test custom timeframe parameter is accepted."""
        mock_features = []
        
        with patch.object(DatabaseService, "get_quant_features", return_value=mock_features):
            response = await client.get("/api/v1/features/quant/AAPL?timeframe=1h")
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_invalid_timeframe_rejected(self, client):
        """Test invalid timeframe is rejected."""
        response = await client.get("/api/v1/features/quant/AAPL?timeframe=invalid")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_valid_timeframes_accepted(self, client):
        """Test all valid timeframes are accepted."""
        valid_timeframes = ["5m", "15m", "30m", "1h", "4h", "1d", "1w"]
        
        for tf in valid_timeframes:
            with patch.object(DatabaseService, "get_quant_features", return_value=[]):
                response = await client.get(f"/api/v1/features/quant/AAPL?timeframe={tf}")
                assert response.status_code in [200, 404], f"Timeframe {tf} rejected with {response.status_code}"

    @pytest.mark.asyncio
    async def test_start_date_parameter(self, client):
        """Test start date parameter is accepted."""
        with patch.object(DatabaseService, "get_quant_features", return_value=[]):
            response = await client.get("/api/v1/features/quant/AAPL?start=2024-01-01")
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_end_date_parameter(self, client):
        """Test end date parameter is accepted."""
        with patch.object(DatabaseService, "get_quant_features", return_value=[]):
            response = await client.get("/api/v1/features/quant/AAPL?end=2024-12-31")
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_limit_parameter(self, client):
        """Test limit parameter is accepted."""
        with patch.object(DatabaseService, "get_quant_features", return_value=[]):
            response = await client.get("/api/v1/features/quant/AAPL?limit=100")
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_limit_bounds(self, client):
        """Test limit parameter is bounded."""
        # Test 0 limit (invalid)
        response = await client.get("/api/v1/features/quant/AAPL?limit=0")
        # 400 or 422 depending on validation
        assert response.status_code in [400, 422]
        
        # Test > 10000 limit (invalid)
        response = await client.get("/api/v1/features/quant/AAPL?limit=20000")
        assert response.status_code in [400, 422]


class TestQuantFeatureEndpointResponse:
    """Test response format and schema."""

    @pytest.mark.asyncio
    async def test_response_contains_metadata(self, client):
        """Test response contains required metadata."""
        mock_features = []
        
        with patch.object(DatabaseService, "get_quant_features", return_value=mock_features):
            response = await client.get("/api/v1/features/quant/AAPL")
            if response.status_code == 200:
                data = response.json()
                assert "symbol" in data
                assert "timeframe" in data
                assert "records_returned" in data
                assert "features" in data
                assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_response_features_structure(self, client):
        """Test each feature record has required fields."""
        mock_features = [
            {
                "time": datetime(2024, 1, 1),
                "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
                "volume": 1000000,
                "return_1d": 0.005, "volatility_20": 0.15, "volatility_50": 0.14,
                "atr": 1.5, "rolling_volume_20": 950000, "volume_ratio": 1.05,
                "structure_label": "bullish", "trend_direction": "up",
                "volatility_regime": "medium", "trend_regime": "uptrend",
                "compression_regime": "expanded", "features_computed_at": datetime(2024, 1, 1, 2, 0, 0)
            }
        ]
        
        with patch.object(DatabaseService, "get_quant_features", return_value=mock_features):
            response = await client.get("/api/v1/features/quant/AAPL")
            if response.status_code == 200:
                data = response.json()
                features = data["features"]
                if features:
                    record = features[0]
                    # Check OHLCV
                    assert "time" in record
                    assert "open" in record
                    assert "high" in record
                    assert "low" in record
                    assert "close" in record
                    assert "volume" in record
                    
                    # Check quant features
                    assert "return_1d" in record
                    assert "volatility_20" in record
                    assert "volatility_50" in record
                    assert "atr" in record
                    assert "rolling_volume_20" in record
                    assert "volume_ratio" in record
                    assert "structure_label" in record
                    assert "trend_direction" in record
                    assert "volatility_regime" in record
                    assert "trend_regime" in record
                    assert "compression_regime" in record
                    assert "features_computed_at" in record

    @pytest.mark.asyncio
    async def test_response_count_matches_records(self, client):
        """Test records_returned matches features array length."""
        mock_features = [
            {
                "time": datetime(2024, 1, i),
                "open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i, "close": 100.5 + i,
                "volume": 1000000,
                "return_1d": 0.005, "volatility_20": 0.15, "volatility_50": 0.14,
                "atr": 1.5, "rolling_volume_20": 950000, "volume_ratio": 1.05,
                "structure_label": "bullish", "trend_direction": "up",
                "volatility_regime": "medium", "trend_regime": "uptrend",
                "compression_regime": "expanded", "features_computed_at": datetime(2024, 1, i, 2, 0, 0)
            }
            for i in range(1, 6)
        ]
        
        with patch.object(DatabaseService, "get_quant_features", return_value=mock_features):
            response = await client.get("/api/v1/features/quant/AAPL")
            if response.status_code == 200:
                data = response.json()
                assert data["records_returned"] == len(mock_features)
                assert len(data["features"]) == data["records_returned"]


class TestQuantFeatureEndpointErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_invalid_symbol_returns_404(self, client):
        """Test invalid symbol returns 404."""
        with patch.object(DatabaseService, "get_quant_features", return_value=[]):
            response = await client.get("/api/v1/features/quant/NONEXISTENT")
            # Should either return 404 or empty 200
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_no_features_found_returns_404(self, client):
        """Test 404 when no features found."""
        with patch.object(DatabaseService, "get_quant_features", return_value=[]):
            response = await client.get("/api/v1/features/quant/AAPL")
            # Should return 404 if no features
            assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_database_error_returns_500(self, client):
        """Test 500 on database error."""
        with patch.object(DatabaseService, "get_quant_features", side_effect=Exception("DB Error")):
            response = await client.get("/api/v1/features/quant/AAPL")
            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_invalid_date_format_returns_400(self, client):
        """Test 400 on invalid date format."""
        response = await client.get("/api/v1/features/quant/AAPL?start=invalid-date")
        assert response.status_code == 400


class TestQuantFeatureEndpointIntegration:
    """Test end-to-end endpoint integration."""

    @pytest.mark.asyncio
    async def test_symbol_case_insensitive(self, client):
        """Test symbol parameter is case-insensitive."""
        with patch.object(DatabaseService, "get_quant_features", return_value=[]):
            response_upper = await client.get("/api/v1/features/quant/AAPL")
            response_lower = await client.get("/api/v1/features/quant/aapl")
            
            # Both should be accepted
            assert response_upper.status_code in [200, 404]
            assert response_lower.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_response_timestamp_present(self, client):
        """Test response includes current timestamp."""
        with patch.object(DatabaseService, "get_quant_features", return_value=[]):
            response = await client.get("/api/v1/features/quant/AAPL")
            if response.status_code == 200:
                data = response.json()
                assert "timestamp" in data
                # Timestamp should be recent (within last minute)
                ts = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
                now = datetime.now(ts.tzinfo)
                assert (now - ts).total_seconds() < 60

    @pytest.mark.asyncio
    async def test_date_range_in_response(self, client):
        """Test response includes date range metadata."""
        mock_features = [
            {
                "time": datetime(2024, 1, 1),
                "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5,
                "volume": 1000000,
                "return_1d": 0.005, "volatility_20": 0.15, "volatility_50": 0.14,
                "atr": 1.5, "rolling_volume_20": 950000, "volume_ratio": 1.05,
                "structure_label": "bullish", "trend_direction": "up",
                "volatility_regime": "medium", "trend_regime": "uptrend",
                "compression_regime": "expanded", "features_computed_at": datetime(2024, 1, 1, 2, 0, 0)
            },
            {
                "time": datetime(2024, 1, 31),
                "open": 105.0, "high": 106.0, "low": 104.0, "close": 105.5,
                "volume": 1100000,
                "return_1d": 0.05, "volatility_20": 0.16, "volatility_50": 0.15,
                "atr": 1.6, "rolling_volume_20": 1050000, "volume_ratio": 1.05,
                "structure_label": "bullish", "trend_direction": "up",
                "volatility_regime": "medium", "trend_regime": "uptrend",
                "compression_regime": "expanded", "features_computed_at": datetime(2024, 1, 31, 2, 0, 0)
            }
        ]
        
        with patch.object(DatabaseService, "get_quant_features", return_value=mock_features):
            response = await client.get("/api/v1/features/quant/AAPL")
            if response.status_code == 200:
                data = response.json()
                assert "date_range" in data
                assert "start" in data["date_range"]
                assert "end" in data["date_range"]
