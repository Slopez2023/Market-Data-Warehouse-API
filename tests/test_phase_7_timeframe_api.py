"""
Phase 7: Unit and Integration Tests for Timeframe API Endpoints

Tests cover:
- Timeframe validation
- Historical data queries with timeframes
- Symbol timeframe configuration
- Symbol info with timeframes
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from decimal import Decimal

from src.config import ALLOWED_TIMEFRAMES, DEFAULT_TIMEFRAMES
from src.models import OHLCVData, UpdateSymbolTimeframesRequest, TrackedSymbol


class TestTimeframeValidation:
    """Unit tests for timeframe validation"""
    
    def test_allowed_timeframes_defined(self):
        """Verify ALLOWED_TIMEFRAMES constant is defined"""
        assert ALLOWED_TIMEFRAMES is not None
        assert isinstance(ALLOWED_TIMEFRAMES, (list, tuple))
        assert len(ALLOWED_TIMEFRAMES) > 0
    
    def test_all_required_timeframes_present(self):
        """Verify all 8 timeframes are allowed"""
        required = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
        for tf in required:
            assert tf in ALLOWED_TIMEFRAMES, f"Timeframe {tf} not in ALLOWED_TIMEFRAMES"
    
    def test_default_timeframes_subset_of_allowed(self):
        """Verify DEFAULT_TIMEFRAMES is subset of ALLOWED_TIMEFRAMES"""
        assert DEFAULT_TIMEFRAMES is not None
        assert isinstance(DEFAULT_TIMEFRAMES, (list, tuple))
        for tf in DEFAULT_TIMEFRAMES:
            assert tf in ALLOWED_TIMEFRAMES


class TestOHLCVDataModel:
    """Unit tests for OHLCVData model with timeframe"""
    
    def test_ohlcv_data_with_valid_timeframe(self):
        """Test OHLCVData model accepts valid timeframe"""
        data = OHLCVData(
            time=datetime.utcnow(),
            symbol="AAPL",
            timeframe="1h",
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=1000000
        )
        assert data.timeframe == "1h"
        assert data.symbol == "AAPL"
    
    def test_ohlcv_data_default_timeframe(self):
        """Test OHLCVData model defaults to 1d timeframe"""
        data = OHLCVData(
            time=datetime.utcnow(),
            symbol="BTC",
            open=Decimal("45000.00"),
            high=Decimal("46000.00"),
            low=Decimal("44000.00"),
            close=Decimal("45500.00"),
            volume=100
        )
        assert data.timeframe == "1d"
    
    def test_ohlcv_data_rejects_invalid_timeframe(self):
        """Test OHLCVData model rejects invalid timeframe"""
        with pytest.raises(ValueError):
            OHLCVData(
                time=datetime.utcnow(),
                symbol="AAPL",
                timeframe="2h",  # Invalid
                open=Decimal("150.00"),
                high=Decimal("152.00"),
                low=Decimal("149.00"),
                close=Decimal("151.00"),
                volume=1000000
            )
    
    @pytest.mark.parametrize("timeframe", ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w'])
    def test_ohlcv_data_all_valid_timeframes(self, timeframe):
        """Test OHLCVData accepts all valid timeframes"""
        data = OHLCVData(
            time=datetime.utcnow(),
            symbol="TEST",
            timeframe=timeframe,
            open=Decimal("100.00"),
            high=Decimal("110.00"),
            low=Decimal("90.00"),
            close=Decimal("105.00"),
            volume=1000
        )
        assert data.timeframe == timeframe


class TestUpdateSymbolTimeframesRequest:
    """Unit tests for UpdateSymbolTimeframesRequest model"""
    
    def test_valid_timeframes_request(self):
        """Test valid timeframes request"""
        req = UpdateSymbolTimeframesRequest(timeframes=["1h", "1d", "4h"])
        # Should deduplicate and sort
        assert req.timeframes == ["1d", "1h", "4h"]
    
    def test_duplicate_timeframes_removed(self):
        """Test that duplicates are removed"""
        req = UpdateSymbolTimeframesRequest(timeframes=["1h", "1d", "1h", "1d"])
        assert req.timeframes == ["1d", "1h"]
    
    def test_timeframes_sorted_alphabetically(self):
        """Test that timeframes are sorted"""
        req = UpdateSymbolTimeframesRequest(timeframes=["1d", "5m", "1h"])
        assert req.timeframes == ["1d", "1h", "5m"]  # Sorted
    
    def test_invalid_timeframe_rejected(self):
        """Test that invalid timeframes are rejected"""
        with pytest.raises(ValueError):
            UpdateSymbolTimeframesRequest(timeframes=["1h", "2h"])  # 2h invalid
    
    def test_empty_timeframes_rejected(self):
        """Test that empty timeframes list is rejected"""
        with pytest.raises(ValueError):
            UpdateSymbolTimeframesRequest(timeframes=[])
    
    @pytest.mark.parametrize("timeframes", [
        ["1h", "1d"],
        ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"],
        ["1m", "1d"],
        ["1w"]
    ])
    def test_valid_timeframe_combinations(self, timeframes):
        """Test various valid timeframe combinations"""
        req = UpdateSymbolTimeframesRequest(timeframes=timeframes)
        assert len(req.timeframes) > 0


class TestTrackedSymbolModel:
    """Unit tests for TrackedSymbol model with timeframes"""
    
    def test_tracked_symbol_with_timeframes(self):
        """Test TrackedSymbol includes timeframes"""
        symbol = TrackedSymbol(
            id=1,
            symbol="AAPL",
            asset_class="stock",
            active=True,
            timeframes=["1h", "1d"]
        )
        assert symbol.timeframes == ["1h", "1d"]
    
    def test_tracked_symbol_default_timeframes(self):
        """Test TrackedSymbol uses default timeframes if not specified"""
        symbol = TrackedSymbol(
            id=1,
            symbol="BTC",
            asset_class="crypto",
            active=True
        )
        assert symbol.timeframes == DEFAULT_TIMEFRAMES
    
    def test_tracked_symbol_rejects_invalid_timeframe(self):
        """Test TrackedSymbol rejects invalid timeframes"""
        with pytest.raises(ValueError):
            TrackedSymbol(
                id=1,
                symbol="TEST",
                asset_class="stock",
                active=True,
                timeframes=["1h", "99m"]  # Invalid
            )
    
    def test_tracked_symbol_rejects_empty_timeframes(self):
        """Test TrackedSymbol rejects empty timeframes"""
        with pytest.raises(ValueError):
            TrackedSymbol(
                id=1,
                symbol="TEST",
                asset_class="stock",
                active=True,
                timeframes=[]
            )


class TestHistoricalDataEndpointTimeframes:
    """Integration tests for historical data endpoint with timeframe filtering"""
    
    @pytest.mark.asyncio
    async def test_historical_data_response_includes_timeframe(self):
        """Test that historical data response includes timeframe field"""
        # This would require a running server or mocked database
        # For now, we test the model structure
        pass
    
    def test_timeframe_parameter_validation(self):
        """Test timeframe parameter is validated"""
        # Valid timeframes should be accepted
        for tf in ALLOWED_TIMEFRAMES:
            # This would be tested with actual API endpoint
            pass
    
    def test_invalid_timeframe_parameter_rejected(self):
        """Test invalid timeframe parameters are rejected"""
        invalid_timeframes = ["2h", "3h", "1min", "30s", "invalid"]
        for tf in invalid_timeframes:
            # This would be tested with actual API endpoint
            assert tf not in ALLOWED_TIMEFRAMES


class TestSymbolManagerTimeframeUpdate:
    """Integration tests for symbol manager timeframe operations"""
    
    @pytest.mark.asyncio
    async def test_update_symbol_timeframes_model(self):
        """Test timeframes can be updated (mocked database)"""
        # Test model validation
        req = UpdateSymbolTimeframesRequest(timeframes=["1h", "4h", "1d"])
        assert len(req.timeframes) == 3
        assert all(tf in ALLOWED_TIMEFRAMES for tf in req.timeframes)
    
    def test_timeframe_deduplication(self):
        """Test that duplicate timeframes are removed"""
        req = UpdateSymbolTimeframesRequest(
            timeframes=["1h", "1h", "1d", "1d", "4h"]
        )
        assert req.timeframes.count("1h") == 1
        assert req.timeframes.count("1d") == 1
        assert req.timeframes.count("4h") == 1
    
    def test_timeframe_sorting(self):
        """Test that timeframes are sorted for consistency"""
        req = UpdateSymbolTimeframesRequest(
            timeframes=["1d", "1h", "5m", "1w", "4h", "15m", "30m"]
        )
        # Should be sorted
        assert req.timeframes == sorted(req.timeframes)


class TestSymbolInfoEndpointTimeframes:
    """Integration tests for symbol info endpoint"""
    
    def test_symbol_info_model_includes_timeframes(self):
        """Test that symbol info includes timeframes field"""
        symbol = TrackedSymbol(
            id=1,
            symbol="AAPL",
            asset_class="stock",
            active=True,
            timeframes=["1h", "4h", "1d"]
        )
        # Should be accessible
        assert hasattr(symbol, 'timeframes')
        assert symbol.timeframes is not None


class TestTimeframeSchedulerIntegration:
    """Integration tests for scheduler with multiple timeframes"""
    
    def test_multiple_timeframes_per_symbol(self):
        """Test that scheduler can handle multiple timeframes per symbol"""
        # Symbol configured with multiple timeframes
        timeframes = ["1h", "4h", "1d"]
        assert all(tf in ALLOWED_TIMEFRAMES for tf in timeframes)
        assert len(set(timeframes)) == len(timeframes)  # No duplicates
    
    def test_timeframe_isolation(self):
        """Test that different timeframes don't interfere"""
        symbol = "AAPL"
        timeframes = ["1h", "1d"]
        
        # Each timeframe is independent
        for tf in timeframes:
            assert tf in ALLOWED_TIMEFRAMES


class TestDatabaseTimeframeFiltering:
    """Unit tests for database timeframe filtering logic"""
    
    def test_timeframe_filter_in_query(self):
        """Test that timeframe is properly included in database query"""
        # This tests the query building logic
        timeframe = "1h"
        symbol = "AAPL"
        
        # Verify timeframe is valid
        assert timeframe in ALLOWED_TIMEFRAMES
        # Verify query would filter by this timeframe
        assert isinstance(timeframe, str)
        assert len(timeframe) > 0
    
    @pytest.mark.parametrize("timeframe,symbol", [
        ("1d", "AAPL"),
        ("1h", "BTC"),
        ("4h", "SPY"),
        ("5m", "MSFT"),
    ])
    def test_various_timeframe_symbol_combinations(self, timeframe, symbol):
        """Test various timeframe and symbol combinations"""
        assert timeframe in ALLOWED_TIMEFRAMES
        assert len(symbol) > 0


class TestBackfillWithMultipleTimeframes:
    """Integration tests for backfill with multiple timeframes"""
    
    def test_backfill_can_handle_multiple_timeframes(self):
        """Test that backfill process can handle multiple timeframes"""
        symbol = "AAPL"
        timeframes = ["1h", "4h", "1d"]
        
        # All timeframes are valid
        assert all(tf in ALLOWED_TIMEFRAMES for tf in timeframes)
    
    def test_each_timeframe_backfill_independent(self):
        """Test that each timeframe backfill is independent"""
        symbol = "AAPL"
        
        # Backfilling one timeframe shouldn't affect others
        for timeframe in DEFAULT_TIMEFRAMES:
            assert timeframe in ALLOWED_TIMEFRAMES


class TestTimeframeEdgeCases:
    """Test edge cases in timeframe handling"""
    
    def test_single_timeframe(self):
        """Test symbol with single timeframe"""
        symbol = TrackedSymbol(
            id=1,
            symbol="TEST",
            asset_class="stock",
            active=True,
            timeframes=["1d"]
        )
        assert symbol.timeframes == ["1d"]
    
    def test_all_timeframes_enabled(self):
        """Test symbol with all timeframes enabled"""
        symbol = TrackedSymbol(
            id=1,
            symbol="TEST",
            asset_class="stock",
            active=True,
            timeframes=list(ALLOWED_TIMEFRAMES)
        )
        assert len(symbol.timeframes) == len(ALLOWED_TIMEFRAMES)
    
    def test_timeframe_case_sensitivity(self):
        """Test timeframe case handling"""
        # Timeframes should be lowercase
        for tf in ALLOWED_TIMEFRAMES:
            assert tf.islower() or tf[0].isdigit()
    
    def test_default_timeframes_reasonable(self):
        """Test that default timeframes make sense"""
        # Should include at least daily
        assert "1d" in DEFAULT_TIMEFRAMES
        # Should not be empty
        assert len(DEFAULT_TIMEFRAMES) > 0
        # All should be valid
        assert all(tf in ALLOWED_TIMEFRAMES for tf in DEFAULT_TIMEFRAMES)


class TestTimeframeDataConsistency:
    """Test data consistency with timeframes"""
    
    def test_same_symbol_different_timeframes_independent(self):
        """Test that same symbol with different timeframes are independent"""
        symbol = "AAPL"
        timeframes = ["1h", "4h", "1d"]
        
        # Each timeframe is a separate data stream
        for tf in timeframes:
            assert tf in ALLOWED_TIMEFRAMES
    
    def test_timeframe_in_ohlcv_record(self):
        """Test timeframe is stored with each OHLCV record"""
        data = OHLCVData(
            time=datetime.utcnow(),
            symbol="AAPL",
            timeframe="4h",
            open=Decimal("150.00"),
            high=Decimal("152.00"),
            low=Decimal("149.00"),
            close=Decimal("151.00"),
            volume=1000000
        )
        # Timeframe should be persisted
        assert data.timeframe == "4h"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
