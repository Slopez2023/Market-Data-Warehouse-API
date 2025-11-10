"""Tests for Phase 6.3: Symbol Management Enhancements"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, call

from src.scheduler import AutoBackfillScheduler
from src.services.symbol_manager import SymbolManager
from src.services.database_service import DatabaseService


# ==============================================================================
# Phase 6.3.1: Scheduler Symbol Loading from DB
# ==============================================================================

@pytest.mark.asyncio
async def test_load_symbols_returns_tuples_with_asset_class():
    """Test that symbols loaded from DB include asset_class"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test",
        symbols=[]
    )
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetch.return_value = [
            {'symbol': 'AAPL', 'asset_class': 'stock'},
            {'symbol': 'MSFT', 'asset_class': 'stock'},
            {'symbol': 'BTC', 'asset_class': 'crypto'},
        ]
        
        symbols = await scheduler._load_symbols_from_db()
        
        assert len(symbols) == 3
        assert symbols[0] == ('AAPL', 'stock')
        assert symbols[1] == ('MSFT', 'stock')
        assert symbols[2] == ('BTC', 'crypto')
        
        mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_load_symbols_empty_list():
    """Test loading symbols when table is empty"""
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


@pytest.mark.asyncio
async def test_load_symbols_database_error():
    """Test error handling when database connection fails"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test",
        symbols=[]
    )
    
    with patch('asyncpg.connect', side_effect=Exception("Connection failed")):
        symbols = await scheduler._load_symbols_from_db()
        
        # Should return empty list on error
        assert symbols == []


@pytest.mark.asyncio
async def test_load_symbols_ordered_by_symbol():
    """Test that symbols are returned in alphabetical order"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test",
        symbols=[]
    )
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetch.return_value = [
            {'symbol': 'MSFT', 'asset_class': 'stock'},
            {'symbol': 'AAPL', 'asset_class': 'stock'},
            {'symbol': 'BTC', 'asset_class': 'crypto'},
        ]
        
        symbols = await scheduler._load_symbols_from_db()
        
        # Query should have ORDER BY
        mock_conn.fetch.assert_called_once()
        query_arg = mock_conn.fetch.call_args[0][0]
        assert "ORDER BY symbol ASC" in query_arg


# ==============================================================================
# Phase 6.3.2: Backfill Status Tracking
# ==============================================================================

@pytest.mark.asyncio
async def test_update_backfill_status_completed():
    """Test updating symbol status to completed"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        await scheduler._update_symbol_backfill_status("AAPL", "completed", None)
        
        # Should update with status and clear error
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "backfill_status = $1" in call_args[0][0]
        assert "backfill_error = NULL" in call_args[0][0]
        assert call_args[0][1] == "completed"
        assert call_args[0][2] == "AAPL"


@pytest.mark.asyncio
async def test_update_backfill_status_failed():
    """Test updating symbol status to failed with error message"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        error_msg = "API rate limited"
        await scheduler._update_symbol_backfill_status("AAPL", "failed", error_msg)
        
        # Should update with status and error message
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "backfill_status = $1" in call_args[0][0]
        assert "backfill_error = $2" in call_args[0][0]
        assert call_args[0][1] == "failed"
        assert call_args[0][2] == error_msg
        assert call_args[0][3] == "AAPL"


@pytest.mark.asyncio
async def test_update_backfill_status_in_progress():
    """Test updating symbol status to in_progress"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        await scheduler._update_symbol_backfill_status("BTC", "in_progress", None)
        
        mock_conn.execute.assert_called_once()


@pytest.mark.asyncio
async def test_update_backfill_status_database_error():
    """Test error handling when update fails"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    with patch('asyncpg.connect', side_effect=Exception("DB error")):
        # Should not raise exception
        await scheduler._update_symbol_backfill_status("AAPL", "failed", "Error")


# ==============================================================================
# Phase 6.3.3: Symbol Statistics Endpoint
# ==============================================================================

def test_get_symbol_stats_with_data():
    """Test getting statistics for a symbol with data"""
    db = DatabaseService("postgresql://test")
    
    # Mock the database query
    with patch.object(db, 'SessionLocal') as mock_session:
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        
        # Mock the result
        mock_result = MagicMock()
        mock_result.first.return_value = (
            100,  # record_count
            datetime(2023, 1, 1),  # start_date
            datetime(2023, 12, 31),  # end_date
            95,  # validated_count
            2  # gaps_count
        )
        
        mock_session_instance.execute.return_value = mock_result
        
        stats = db.get_symbol_stats("AAPL")
        
        assert stats["record_count"] == 100
        assert stats["date_range"]["start"] == "2023-01-01T00:00:00"
        assert stats["date_range"]["end"] == "2023-12-31T00:00:00"
        assert stats["validation_rate"] == 0.95
        assert stats["gaps_detected"] == 2


def test_get_symbol_stats_no_data():
    """Test getting statistics for symbol with no data"""
    db = DatabaseService("postgresql://test")
    
    with patch.object(db, 'SessionLocal') as mock_session:
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        
        # Mock empty result
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session_instance.execute.return_value = mock_result
        
        stats = db.get_symbol_stats("NEWCOIN")
        
        assert stats["record_count"] == 0
        assert stats["date_range"]["start"] is None
        assert stats["date_range"]["end"] is None
        assert stats["validation_rate"] == 0
        assert stats["gaps_detected"] == 0


def test_get_symbol_stats_all_validated():
    """Test statistics when all records are validated"""
    db = DatabaseService("postgresql://test")
    
    with patch.object(db, 'SessionLocal') as mock_session:
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        
        mock_result = MagicMock()
        mock_result.first.return_value = (
            50,  # record_count
            datetime(2023, 1, 1),  # start_date
            datetime(2023, 2, 17),  # end_date
            50,  # all validated
            0  # no gaps
        )
        
        mock_session_instance.execute.return_value = mock_result
        
        stats = db.get_symbol_stats("BTC")
        
        assert stats["validation_rate"] == 1.0
        assert stats["gaps_detected"] == 0


def test_get_symbol_stats_low_validation():
    """Test statistics with low validation rate"""
    db = DatabaseService("postgresql://test")
    
    with patch.object(db, 'SessionLocal') as mock_session:
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        
        mock_result = MagicMock()
        mock_result.first.return_value = (
            100,  # record_count
            datetime(2023, 1, 1),
            datetime(2023, 12, 31),
            30,  # only 30% validated
            15  # many gaps
        )
        
        mock_session_instance.execute.return_value = mock_result
        
        stats = db.get_symbol_stats("BADDATA")
        
        assert stats["validation_rate"] == 0.3
        assert stats["gaps_detected"] == 15


# ==============================================================================
# Phase 6.3.4: Crypto Support
# ==============================================================================

@pytest.mark.asyncio
async def test_backfill_handles_stock_asset_class():
    """Test backfill processes stocks correctly"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    with patch.object(scheduler.polygon_client, 'fetch_daily_range', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [
            {'t': 1609459200000, 'o': 130.0, 'h': 131.0, 'l': 129.0, 'c': 130.5, 'v': 1000000}
        ]
        
        with patch.object(scheduler, 'db_service'):
            with patch.object(scheduler, '_update_symbol_backfill_status', new_callable=AsyncMock):
                records = await scheduler._backfill_symbol("AAPL", "stock")
                
                # Should call fetch_daily_range for stocks
                mock_fetch.assert_called_once()


@pytest.mark.asyncio
async def test_backfill_handles_crypto_asset_class():
    """Test backfill processes crypto correctly"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    with patch.object(scheduler.polygon_client, 'fetch_crypto_daily_range', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [
            {'t': 1609459200000, 'o': 29000.0, 'h': 30000.0, 'l': 28000.0, 'c': 29500.0, 'v': 100}
        ]
        
        with patch.object(scheduler, 'db_service'):
            with patch.object(scheduler, '_update_symbol_backfill_status', new_callable=AsyncMock):
                records = await scheduler._backfill_symbol("BTCUSD", "crypto")
                
                # Should call fetch_crypto_daily_range for crypto
                mock_fetch.assert_called_once()


@pytest.mark.asyncio
async def test_backfill_job_processes_mixed_assets():
    """Test backfill job handles mixed stock and crypto symbols"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    # Set up mixed symbols
    scheduler.symbols = [
        ("AAPL", "stock"),
        ("MSFT", "stock"),
        ("BTCUSD", "crypto"),
        ("SPY", "etf")
    ]
    
    with patch.object(scheduler, '_load_symbols_from_db', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = scheduler.symbols
        
        with patch.object(scheduler, '_backfill_symbol', new_callable=AsyncMock) as mock_backfill:
            mock_backfill.return_value = 5
            
            with patch.object(scheduler, '_update_symbol_backfill_status', new_callable=AsyncMock):
                await scheduler._backfill_job()
                
                # Should process all symbols
                assert mock_backfill.call_count == 4
                
                # Check calls include asset class
                calls = mock_backfill.call_args_list
                assert calls[0][0] == ("AAPL", "stock")
                assert calls[1][0] == ("MSFT", "stock")
                assert calls[2][0] == ("BTCUSD", "crypto")
                assert calls[3][0] == ("SPY", "etf")


# ==============================================================================
# Phase 6.3.5: Full Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_backfill_job_updates_status_progression():
    """Test that backfill job properly tracks status transitions"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test",
        symbols=[("AAPL", "stock")]  # Provide symbols in constructor
    )
    
    with patch.object(scheduler, '_load_symbols_from_db', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = [("AAPL", "stock")]
        
        with patch.object(scheduler, '_backfill_symbol', new_callable=AsyncMock) as mock_backfill:
            mock_backfill.return_value = 10
            
            with patch.object(scheduler, '_update_symbol_backfill_status', new_callable=AsyncMock) as mock_status:
                await scheduler._backfill_job()
                
                # Should have 2 calls: in_progress, then completed
                assert mock_status.call_count >= 2
                
                # First call should be in_progress
                first_call = mock_status.call_args_list[0]
                assert first_call[0][1] == "in_progress"
                
                # Last call should be completed
                last_call = mock_status.call_args_list[-1]
                assert last_call[0][1] == "completed"


@pytest.mark.asyncio
async def test_backfill_job_error_updates_failed_status():
    """Test that failed backfill updates status to failed"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test",
        symbols=[("BADTICKER", "stock")]
    )
    
    with patch.object(scheduler, '_load_symbols_from_db', new_callable=AsyncMock) as mock_load:
        mock_load.return_value = [("BADTICKER", "stock")]
        
        with patch.object(scheduler, '_backfill_symbol', side_effect=Exception("API error")):
            with patch.object(scheduler, '_update_symbol_backfill_status', new_callable=AsyncMock) as mock_status:
                await scheduler._backfill_job()
                
                # Should have called status with failed
                failed_calls = [
                    call_item for call_item in mock_status.call_args_list
                    if call_item[0][1] == "failed"
                ]
                assert len(failed_calls) > 0


@pytest.mark.asyncio
async def test_symbol_manager_get_all_symbols_with_asset_class():
    """Test that symbol manager returns asset_class field"""
    manager = SymbolManager("postgresql://test")
    
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetch.return_value = [
            {
                'id': 1,
                'symbol': 'AAPL',
                'asset_class': 'stock',
                'active': True,
                'date_added': datetime(2023, 1, 1),
                'last_backfill': datetime(2023, 12, 31),
                'backfill_status': 'completed'
            }
        ]
        
        symbols = await manager.get_all_symbols(active_only=True)
        
        assert len(symbols) == 1
        assert symbols[0]['asset_class'] == 'stock'


# ==============================================================================
# Summary Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_phase_6_3_summary():
    """Test that Phase 6.3 functionality is complete"""
    scheduler = AutoBackfillScheduler(
        polygon_api_key="test_key",
        database_url="postgresql://test"
    )
    
    # Check methods exist
    assert hasattr(scheduler, '_load_symbols_from_db')
    assert hasattr(scheduler, '_update_symbol_backfill_status')
    assert hasattr(scheduler, '_backfill_symbol')
    assert callable(scheduler._load_symbols_from_db)
    assert callable(scheduler._update_symbol_backfill_status)
    
    # Check polygon client has crypto support
    assert hasattr(scheduler.polygon_client, 'fetch_crypto_daily_range')
    assert callable(scheduler.polygon_client.fetch_crypto_daily_range)
    
    # Check database service has stats method
    db = DatabaseService("postgresql://test")
    assert hasattr(db, 'get_symbol_stats')
    assert callable(db.get_symbol_stats)
