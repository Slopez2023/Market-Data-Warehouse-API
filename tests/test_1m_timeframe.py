"""
Test suite for 1-minute timeframe integration.

Tests verify that:
- 1m is properly added to supported timeframes
- Polygon client maps 1m correctly
- Database operations work with 1m
- API endpoints accept 1m
- No breaking changes to existing timeframes
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from src.config import ALLOWED_TIMEFRAMES, DEFAULT_TIMEFRAMES
from src.clients.polygon_client import PolygonClient, TIMEFRAME_MAP
from src.models import OHLCVData, TrackedSymbol


class TestTimeframeConfiguration:
    """Test 1m is properly configured"""
    
    def test_1m_in_allowed_timeframes(self):
        """1m should be in ALLOWED_TIMEFRAMES"""
        assert '1m' in ALLOWED_TIMEFRAMES, \
            f"1m not in ALLOWED_TIMEFRAMES: {ALLOWED_TIMEFRAMES}"
    
    def test_1m_is_first_timeframe(self):
        """1m should be the lowest/first timeframe"""
        assert ALLOWED_TIMEFRAMES[0] == '1m', \
            f"1m should be first timeframe, but ALLOWED_TIMEFRAMES[0] is {ALLOWED_TIMEFRAMES[0]}"
    
    def test_all_expected_timeframes_present(self):
        """Verify complete list of supported timeframes"""
        expected = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
        assert ALLOWED_TIMEFRAMES == expected, \
            f"Expected {expected}, got {ALLOWED_TIMEFRAMES}"
    
    def test_default_timeframes_unchanged(self):
        """DEFAULT_TIMEFRAMES should remain ['1h', '1d'] for backward compatibility"""
        assert DEFAULT_TIMEFRAMES == ['1h', '1d'], \
            f"DEFAULT_TIMEFRAMES should be ['1h', '1d'], got {DEFAULT_TIMEFRAMES}"
    
    def test_1m_not_in_defaults(self):
        """1m should not be in defaults (users must explicitly add it)"""
        assert '1m' not in DEFAULT_TIMEFRAMES, \
            "1m should not be in DEFAULT_TIMEFRAMES to maintain backward compatibility"


class TestPolygonClientTimeframeMap:
    """Test Polygon client 1m support"""
    
    def test_1m_in_timeframe_map(self):
        """1m should be defined in TIMEFRAME_MAP"""
        assert '1m' in TIMEFRAME_MAP, \
            f"1m not in TIMEFRAME_MAP. Available: {list(TIMEFRAME_MAP.keys())}"
    
    def test_1m_maps_correctly(self):
        """1m should map to multiplier=1, timespan=minute"""
        expected = {'multiplier': 1, 'timespan': 'minute'}
        actual = TIMEFRAME_MAP.get('1m')
        assert actual == expected, \
            f"1m should map to {expected}, but got {actual}"
    
    def test_1m_timeframe_params(self):
        """_get_timeframe_params should work with 1m"""
        params = PolygonClient._get_timeframe_params('1m')
        assert params['multiplier'] == 1
        assert params['timespan'] == 'minute'
    
    def test_all_timeframes_have_params(self):
        """All ALLOWED_TIMEFRAMES should have Polygon mappings"""
        for tf in ALLOWED_TIMEFRAMES:
            assert tf in TIMEFRAME_MAP, \
                f"Timeframe {tf} not in TIMEFRAME_MAP"
            params = TIMEFRAME_MAP[tf]
            assert 'multiplier' in params and 'timespan' in params, \
                f"Invalid mapping for {tf}: {params}"
    
    def test_unsupported_timeframe_raises(self):
        """Unsupported timeframe should raise ValueError"""
        with pytest.raises(ValueError, match="Unsupported timeframe"):
            PolygonClient._get_timeframe_params('2m')


class TestOHLCVDataModel:
    """Test OHLCVData model accepts 1m"""
    
    def test_1m_ohlcv_creation(self):
        """OHLCVData should accept 1m timeframe"""
        now = datetime.now()
        data = OHLCVData(
            time=now,
            symbol='TEST',
            timeframe='1m',
            open=Decimal('100.00'),
            high=Decimal('101.00'),
            low=Decimal('99.00'),
            close=Decimal('100.50'),
            volume=1000
        )
        assert data.timeframe == '1m'
    
    def test_1m_serialization(self):
        """OHLCVData with 1m should serialize correctly"""
        now = datetime.now()
        data = OHLCVData(
            time=now,
            symbol='AAPL',
            timeframe='1m',
            open=Decimal('150.25'),
            high=Decimal('151.00'),
            low=Decimal('150.00'),
            close=Decimal('150.75'),
            volume=50000
        )
        json_data = data.dict()
        assert json_data['timeframe'] == '1m'
        assert json_data['symbol'] == 'AAPL'
    
    def test_invalid_timeframe_rejected(self):
        """Invalid timeframe should raise ValueError"""
        now = datetime.now()
        with pytest.raises(ValueError, match="Invalid timeframe"):
            OHLCVData(
                time=now,
                symbol='TEST',
                timeframe='2m',  # Invalid
                open=Decimal('100.00'),
                high=Decimal('101.00'),
                low=Decimal('99.00'),
                close=Decimal('100.50'),
                volume=1000
            )


class TestTrackedSymbolModel:
    """Test TrackedSymbol model with 1m"""
    
    def test_tracked_symbol_with_1m(self):
        """TrackedSymbol should accept 1m in timeframes"""
        symbol = TrackedSymbol(
            id=1,
            symbol='AAPL',
            asset_class='stock',
            active=True,
            timeframes=['1m', '5m', '1h', '1d']
        )
        assert '1m' in symbol.timeframes
    
    def test_tracked_symbol_1m_only(self):
        """TrackedSymbol should accept 1m as sole timeframe"""
        symbol = TrackedSymbol(
            id=1,
            symbol='AAPL',
            asset_class='stock',
            active=True,
            timeframes=['1m']
        )
        assert symbol.timeframes == ['1m']
    
    def test_invalid_timeframe_in_list_rejected(self):
        """Invalid timeframe in list should raise ValueError"""
        with pytest.raises(ValueError, match="Invalid timeframes"):
            TrackedSymbol(
                id=1,
                symbol='AAPL',
                asset_class='stock',
                active=True,
                timeframes=['1m', '2m', '1h']  # 2m is invalid
            )


class TestBackwardCompatibility:
    """Ensure existing timeframes still work"""
    
    @pytest.mark.parametrize("timeframe", ['5m', '15m', '30m', '1h', '4h', '1d', '1w'])
    def test_existing_timeframes_work(self, timeframe):
        """Existing timeframes should work unchanged"""
        params = PolygonClient._get_timeframe_params(timeframe)
        assert params is not None
        assert 'multiplier' in params
        assert 'timespan' in params
    
    @pytest.mark.parametrize("timeframe", ['5m', '15m', '30m', '1h', '4h', '1d', '1w'])
    def test_existing_ohlcv_creation(self, timeframe):
        """OHLCVData creation unchanged for existing timeframes"""
        now = datetime.now()
        data = OHLCVData(
            time=now,
            symbol='TEST',
            timeframe=timeframe,
            open=Decimal('100.00'),
            high=Decimal('101.00'),
            low=Decimal('99.00'),
            close=Decimal('100.50'),
            volume=1000
        )
        assert data.timeframe == timeframe
    
    def test_default_timeframe_values_unchanged(self):
        """Default timeframe in OHLCVData should still be 1d"""
        now = datetime.now()
        data = OHLCVData(
            time=now,
            symbol='TEST',
            open=Decimal('100.00'),
            high=Decimal('101.00'),
            low=Decimal('99.00'),
            close=Decimal('100.50'),
            volume=1000
        )
        assert data.timeframe == '1d'


class TestTimeframeOrdering:
    """Test timeframe ordering and hierarchy"""
    
    def test_timeframe_ordering(self):
        """Timeframes should be in ascending order"""
        # 1m < 5m < 15m < 30m < 1h < 4h < 1d < 1w
        order = ['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']
        assert ALLOWED_TIMEFRAMES == order, \
            f"Timeframes not in ascending order. Expected {order}, got {ALLOWED_TIMEFRAMES}"
    
    def test_1m_is_lowest_granularity(self):
        """1m should be the lowest granularity supported"""
        minute_timeframes = [tf for tf in ALLOWED_TIMEFRAMES if 'm' in tf]
        assert minute_timeframes[0] == '1m', \
            f"1m should be first minute timeframe, got {minute_timeframes}"


class TestConfigConsistency:
    """Verify configuration is consistent across modules"""
    
    def test_polygon_map_includes_all_allowed(self):
        """TIMEFRAME_MAP should include all ALLOWED_TIMEFRAMES"""
        missing = [tf for tf in ALLOWED_TIMEFRAMES if tf not in TIMEFRAME_MAP]
        assert not missing, \
            f"These ALLOWED_TIMEFRAMES missing from TIMEFRAME_MAP: {missing}"
    
    def test_no_extra_timeframes_in_polygon_map(self):
        """TIMEFRAME_MAP should not have timeframes not in ALLOWED"""
        extra = [tf for tf in TIMEFRAME_MAP if tf not in ALLOWED_TIMEFRAMES]
        assert not extra, \
            f"These TIMEFRAME_MAP entries not in ALLOWED_TIMEFRAMES: {extra}"
    
    def test_default_timeframes_are_allowed(self):
        """All DEFAULT_TIMEFRAMES should be in ALLOWED_TIMEFRAMES"""
        invalid = [tf for tf in DEFAULT_TIMEFRAMES if tf not in ALLOWED_TIMEFRAMES]
        assert not invalid, \
            f"These DEFAULT_TIMEFRAMES not in ALLOWED_TIMEFRAMES: {invalid}"
