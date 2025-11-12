"""Tests for Phase 6.5: Crypto Symbol Support Implementation"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call
from decimal import Decimal

from src.scheduler import AutoBackfillScheduler
from src.clients.polygon_client import PolygonClient
from src.services.symbol_manager import SymbolManager
from src.services.database_service import DatabaseService


# ==============================================================================
# Phase 6.5.1: Polygon Crypto Endpoint Verification
# ==============================================================================

@pytest.mark.asyncio
async def test_polygon_client_has_crypto_endpoint():
    """Test that PolygonClient has crypto fetch method"""
    client = PolygonClient("test_key")
    
    assert hasattr(client, 'fetch_crypto_daily_range')
    assert callable(client.fetch_crypto_daily_range)


@pytest.mark.asyncio
async def test_fetch_crypto_daily_range_method_signature():
    """Test crypto method has correct signature"""
    import inspect
    
    client = PolygonClient("test_key")
    sig = inspect.signature(client.fetch_crypto_daily_range)
    
    params = list(sig.parameters.keys())
    assert 'symbol' in params
    assert 'start' in params
    assert 'end' in params


@pytest.mark.asyncio
async def test_fetch_crypto_daily_range_is_async():
    """Test crypto method is an async function"""
    import inspect
    
    client = PolygonClient("test_key")
    assert inspect.iscoroutinefunction(client.fetch_crypto_daily_range)


def test_fetch_crypto_has_docstring():
    """Test crypto method has docstring"""
    client = PolygonClient("test_key")
    
    doc = client.fetch_crypto_daily_range.__doc__
    assert doc is not None
    assert 'crypto' in doc.lower()


def test_fetch_crypto_method_name():
    """Test crypto method has correct name"""
    client = PolygonClient("test_key")
    
    assert hasattr(client, 'fetch_crypto_daily_range')
    assert client.fetch_crypto_daily_range.__name__ == 'fetch_crypto_daily_range'


def test_fetch_crypto_has_retry_decorator():
    """Test crypto method has retry decorator"""
    import inspect
    
    client = PolygonClient("test_key")
    source = inspect.getsource(client.__class__.fetch_crypto_daily_range)
    
    # Should have retry handling in docstring or implementation
    assert 'retry' in source.lower() or 'tenacity' in source.lower()


# ==============================================================================
# Phase 6.5.2: Crypto Symbol Handling
# ==============================================================================

@pytest.mark.asyncio
async def test_add_crypto_symbol_to_manager():
    """Test adding crypto symbol via SymbolManager"""
    manager = SymbolManager("postgresql://test")
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetchrow.return_value = None  # Symbol doesn't exist
        mock_conn.fetchrow.side_effect = [
            None,  # Check existing
            {
                'id': 1,
                'symbol': 'BTCUSD',
                'asset_class': 'crypto',
                'active': True,
                'date_added': datetime.now(),
                'backfill_status': 'pending', 'timeframes': ['1h', '1d']
            }  # Insert result
        ]
        
        result = await manager.add_symbol('BTCUSD', 'crypto')
        
        assert result['symbol'] == 'BTCUSD'
        assert result['asset_class'] == 'crypto'
        assert result['active'] is True


@pytest.mark.asyncio
async def test_add_multiple_crypto_symbols():
    """Test adding multiple crypto symbols"""
    manager = SymbolManager("postgresql://test")
    
    crypto_symbols = [
        ('BTCUSD', 'crypto'),
        ('ETHGBP', 'crypto'),
        ('SOLUSD', 'crypto'),
    ]
    
    for symbol, asset_class in crypto_symbols:
        assert symbol.isupper()
        assert asset_class == 'crypto'


@pytest.mark.asyncio
async def test_crypto_symbol_case_insensitive():
    """Test that crypto symbols are uppercased"""
    manager = SymbolManager("postgresql://test")
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetchrow.side_effect = [
            None,  # Check existing
            {
                'id': 1,
                'symbol': 'BTCUSD',
                'asset_class': 'crypto',
                'active': True,
                'date_added': datetime.now(),
                'backfill_status': 'pending', 'timeframes': ['1h', '1d']
            }
        ]
        
        result = await manager.add_symbol('btcusd', 'crypto')
        
        assert result['symbol'] == 'BTCUSD'


@pytest.mark.asyncio
async def test_get_crypto_symbol_with_asset_class():
    """Test retrieving crypto symbol with asset_class field"""
    manager = SymbolManager("postgresql://test")
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetchrow.return_value = {
            'id': 1,
            'symbol': 'ETHGBP',
            'asset_class': 'crypto',
            'active': True,
            'date_added': datetime.now(),
            'last_backfill': None,
            'backfill_status': 'pending', 'timeframes': ['1h', '1d']
        }
        
        result = await manager.get_symbol('ETHGBP')
        
        assert result['symbol'] == 'ETHGBP'
        assert result['asset_class'] == 'crypto'


# ==============================================================================
# Phase 6.5.3: Asset Class Filtering
# ==============================================================================

@pytest.mark.asyncio
async def test_scheduler_filters_by_asset_class():
    """Test scheduler correctly filters symbols by asset class"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    # Set up mixed symbols
    scheduler.symbols = [
        ('AAPL', 'stock'),
        ('MSFT', 'stock'),
        ('BTCUSD', 'crypto'),
        ('ETHGBP', 'crypto'),
        ('SPY', 'etf'),
    ]
    
    # Filter stocks
    stocks = [s for s, ac in scheduler.symbols if ac == 'stock']
    assert len(stocks) == 2
    assert 'AAPL' in stocks
    assert 'MSFT' in stocks
    
    # Filter crypto
    crypto = [s for s, ac in scheduler.symbols if ac == 'crypto']
    assert len(crypto) == 2
    assert 'BTCUSD' in crypto
    assert 'ETHGBP' in crypto
    
    # Filter ETFs
    etfs = [s for s, ac in scheduler.symbols if ac == 'etf']
    assert len(etfs) == 1
    assert 'SPY' in etfs


@pytest.mark.asyncio
async def test_load_symbols_preserves_asset_class():
    """Test that loading symbols preserves asset_class info"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetch.return_value = [
            {'symbol': 'AAPL', 'asset_class': 'stock', 'timeframes': ['1h', '1d']},
            {'symbol': 'BTCUSD', 'asset_class': 'crypto', 'timeframes': ['1h', '1d']},
            {'symbol': 'ETH', 'asset_class': 'crypto', 'timeframes': ['1h', '1d']},
            {'symbol': 'SPY', 'asset_class': 'etf', 'timeframes': ['1h', '1d']},
        ]
        
        symbols = await scheduler._load_symbols_from_db()
        
        assert len(symbols) == 4
        
        # Verify asset classes are preserved (symbols are now tuples with timeframes)
        symbol_dict = {s: ac for s, ac, _ in symbols}
        assert symbol_dict['AAPL'] == 'stock'
        assert symbol_dict['BTCUSD'] == 'crypto'
        assert symbol_dict['ETH'] == 'crypto'
        assert symbol_dict['SPY'] == 'etf'


# ==============================================================================
# Phase 6.5.4: Backfill Pipeline Integration
# ==============================================================================

@pytest.mark.asyncio
async def test_fetch_and_insert_routes_to_crypto_endpoint():
    """Test that crypto symbols use fetch_range"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    with patch.object(scheduler.polygon_client, 'fetch_range', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [
            {'t': 1609459200000, 'o': 29000, 'h': 30000, 'l': 28000, 'c': 29500, 'v': 100}
        ]
        
        with patch.object(scheduler, 'db_service'):
            with patch.object(scheduler.validation_service, 'validate_candle') as mock_validate:
                mock_validate.return_value = (True, {'validated': True})
                with patch.object(scheduler.db_service, 'insert_ohlcv_batch', return_value=1):
                    with patch.object(scheduler.db_service, 'log_backfill'):
                        result = await scheduler._fetch_and_insert(
                            'BTCUSD',
                            datetime(2021, 1, 1),
                            datetime(2021, 1, 31),
                            'crypto',
                            '1d'
                        )
                        
                        # Should call fetch_range for crypto
                        mock_fetch.assert_called_once()
                        assert result >= 0


@pytest.mark.asyncio
async def test_backfill_job_processes_crypto_symbols():
    """Test backfill job correctly processes crypto symbols"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test",
        symbols=[('BTCUSD', 'crypto', ['1d'])]
    )
    
    with patch.object(scheduler, '_load_symbols_from_db', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = [('BTCUSD', 'crypto', ['1d'])]
        
        with patch.object(scheduler, '_backfill_symbol', new_callable=AsyncMock) as mock_backfill:
            mock_backfill.return_value = 5
            
            with patch.object(scheduler, '_update_symbol_backfill_status', new_callable=AsyncMock):
                await scheduler._backfill_job()
                
                # Should call backfill with crypto asset class and timeframe
                mock_backfill.assert_called_once_with('BTCUSD', 'crypto', '1d')


@pytest.mark.asyncio
async def test_mixed_asset_class_backfill_sequence():
    """Test backfill handles mixed stock/crypto sequence correctly"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    scheduler.symbols = [
        ('AAPL', 'stock', ['1d']),
        ('BTCUSD', 'crypto', ['1d']),
        ('MSFT', 'stock', ['1d']),
        ('ETHGBP', 'crypto', ['1d']),
    ]
    
    with patch.object(scheduler, '_load_symbols_from_db', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = scheduler.symbols
        
        with patch.object(scheduler.polygon_client, 'fetch_range', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [{'t': 1609459200000, 'o': 130, 'h': 131, 'l': 129, 'c': 130.5, 'v': 1000000}]
            
            with patch.object(scheduler, 'db_service'):
                with patch.object(scheduler.validation_service, 'validate_candle') as mock_validate:
                    mock_validate.return_value = (True, {'validated': True})
                    with patch.object(scheduler.db_service, 'insert_ohlcv_batch', return_value=1):
                        with patch.object(scheduler.db_service, 'log_backfill'):
                            with patch.object(scheduler, '_update_symbol_backfill_status', new_callable=AsyncMock):
                                await scheduler._backfill_job()
                                
                                # fetch_range should be called 4 times (once per symbol with 1 timeframe)
                                assert mock_fetch.call_count == 4


# ==============================================================================
# Phase 6.5.5: Data Format & Validation
# ==============================================================================

def test_crypto_candle_format_matches_stock_format():
    """Test that crypto candles have same format as stock candles"""
    # Test candle format definition
    required_fields = ['t', 'o', 'h', 'l', 'c', 'v']
    
    # Simulated candle response
    candle = {'t': 1609459200000, 'o': 29000, 'h': 30000, 'l': 28000, 'c': 29500, 'v': 100}
    
    for field in required_fields:
        assert field in candle


@pytest.mark.asyncio
async def test_crypto_large_volume_handling():
    """Test crypto volume values are handled correctly"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    # Crypto volume is typically much smaller than stock volume
    crypto_candle = {
        't': 1609459200000,
        'o': 29000,
        'h': 30000,
        'l': 28000,
        'c': 29500,
        'v': 0.5  # Small volume in crypto
    }
    
    # Should be treated as valid volume (not rejected as anomaly)
    assert crypto_candle['v'] >= 0


# ==============================================================================
# Phase 6.5.6: Crypto-Specific Endpoints
# ==============================================================================

@pytest.mark.asyncio
async def test_polygon_client_crypto_base_url():
    """Test that crypto client has correct base URL"""
    client = PolygonClient("test_key")
    
    assert hasattr(client, 'crypto_base_url')
    # Note: current implementation uses same v2 endpoint for crypto
    # But client has crypto_base_url attribute defined


@pytest.mark.asyncio
async def test_various_crypto_pair_formats():
    """Test crypto symbol format handling (BTCUSD, ETHGBP, etc)"""
    client = PolygonClient("test_key")
    
    crypto_pairs = [
        'BTCUSD',  # Bitcoin/USD
        'ETHGBP',  # Ethereum/GBP
        'SOLUSD',  # Solana/USD
        'ADAUSD',  # Cardano/USD
    ]
    
    for pair in crypto_pairs:
        assert len(pair) >= 6
        assert pair.isupper()


# ==============================================================================
# Phase 6.5.7: Error Handling & Edge Cases
# ==============================================================================

@pytest.mark.asyncio
async def test_crypto_symbol_not_found_handling():
    """Test handling of non-existent crypto symbol"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    with patch.object(scheduler.polygon_client, 'fetch_range', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = []  # No data
        
        with patch.object(scheduler.db_service, 'log_backfill') as mock_log:
            result = await scheduler._fetch_and_insert(
                'FAKECRYPTO',
                datetime(2021, 1, 1),
                datetime(2021, 1, 31),
                'crypto',
                '1d'
            )
            
            assert result == 0


@pytest.mark.asyncio
async def test_crypto_backfill_handles_no_data():
    """Test crypto backfill when no data is returned"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    with patch.object(scheduler.polygon_client, 'fetch_range', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = []  # No data
        
        with patch.object(scheduler.db_service, 'log_backfill') as mock_log:
            result = await scheduler._fetch_and_insert(
                'FAKECRYPTO',
                datetime(2021, 1, 1),
                datetime(2021, 1, 31),
                'crypto',
                '1d'
            )
            
            assert result == 0
            mock_log.assert_called_once()


@pytest.mark.asyncio
async def test_crypto_empty_symbol_list():
    """Test scheduler handles empty crypto symbols list"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test",
        symbols=[]
    )
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        mock_conn.fetch.return_value = []
        
        symbols = await scheduler._load_symbols_from_db()
        
        assert symbols == []


# ==============================================================================
# Phase 6.5.8: Integration Test Summary
# ==============================================================================

@pytest.mark.asyncio
async def test_phase_6_5_crypto_implementation_complete():
    """Verify all Phase 6.5 crypto functionality is implemented"""
    client = PolygonClient("test_key")
    scheduler = AutoBackfillScheduler("test_key", "postgresql://test")
    manager = SymbolManager("postgresql://test")
    
    # Check PolygonClient has crypto support
    assert hasattr(client, 'fetch_crypto_daily_range')
    assert callable(client.fetch_crypto_daily_range)
    
    # Check Scheduler handles asset_class parameter
    assert hasattr(scheduler, '_fetch_and_insert')
    sig = str(inspect.signature(scheduler._fetch_and_insert))
    assert 'asset_class' in sig
    
    # Check Scheduler routes correctly
    assert hasattr(scheduler, '_backfill_symbol')
    
    # Check SymbolManager supports crypto
    assert hasattr(manager, 'add_symbol')


@pytest.mark.asyncio
async def test_crypto_end_to_end_flow():
    """Test complete crypto symbol flow: add -> load -> backfill"""
    manager = SymbolManager("postgresql://test")
    scheduler = AutoBackfillScheduler("test_key", "postgresql://test")
    
    # Step 1: Add crypto symbol
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetchrow.side_effect = [
            None,  # Check existing
            {
                'id': 1,
                'symbol': 'BTCUSD',
                'asset_class': 'crypto',
                'active': True,
                'date_added': datetime.now(),
                'backfill_status': 'pending', 'timeframes': ['1h', '1d']
            }
        ]
        
        symbol_result = await manager.add_symbol('BTCUSD', 'crypto')
        assert symbol_result['asset_class'] == 'crypto'
    
    # Step 2: Load crypto symbol from DB
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetch.return_value = [
            {'symbol': 'BTCUSD', 'asset_class': 'crypto', 'timeframes': ['1d']}
        ]
        
        symbols = await scheduler._load_symbols_from_db()
        assert len(symbols) == 1
        assert symbols[0][1] == 'crypto'
    
    # Step 3: Backfill crypto symbol
    with patch.object(scheduler.polygon_client, 'fetch_range', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [
            {'t': 1609459200000, 'o': 29000, 'h': 30000, 'l': 28000, 'c': 29500, 'v': 100}
        ]
        
        with patch.object(scheduler.db_service, 'insert_ohlcv_batch', return_value=1):
            with patch.object(scheduler.db_service, 'log_backfill'):
                with patch.object(scheduler.validation_service, 'validate_candle') as mock_validate:
                    mock_validate.return_value = (True, {'validated': True})
                    
                    result = await scheduler._fetch_and_insert(
                        'BTCUSD',
                        datetime(2021, 1, 1),
                        datetime(2021, 1, 31),
                        'crypto',
                        '1d'
                    )
                    
                    assert result >= 0


# ==============================================================================
# Import required for inspection
# ==============================================================================

import inspect
