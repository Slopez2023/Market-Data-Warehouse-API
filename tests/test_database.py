"""Unit tests for database_service.py with mocked database"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
from decimal import Decimal

from src.services.database_service import DatabaseService


@pytest.fixture
def mock_engine():
    """Mock SQLAlchemy engine"""
    return MagicMock()


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session"""
    return MagicMock()


@pytest.fixture
def db_service(mock_engine, mock_session):
    """Create DatabaseService with mocked engine"""
    with patch('src.services.database_service.create_engine', return_value=mock_engine):
        with patch('src.services.database_service.sessionmaker') as mock_sessionmaker:
            mock_sessionmaker.return_value = MagicMock(return_value=mock_session)
            service = DatabaseService('postgresql://test:test@localhost/test')
            service.SessionLocal = MagicMock(return_value=mock_session)
            return service


class TestInsertOHLCVBatch:
    """Test batch insert operations"""
    
    def test_insert_valid_batch(self, db_service, mock_session):
        """Test inserting valid OHLCV batch"""
        mock_session.commit = MagicMock()
        mock_session.rollback = MagicMock()
        
        candles = [
            {
                't': 1700000000000,
                'o': 150.0,
                'h': 152.0,
                'l': 149.0,
                'c': 151.0,
                'v': 1000000
            }
        ]
        
        metadata = [
            {
                'validated': True,
                'quality_score': 0.95,
                'validation_notes': None,
                'gap_detected': False,
                'volume_anomaly': False
            }
        ]
        
        result = db_service.insert_ohlcv_batch('AAPL', candles, metadata)
        
        assert result == 1
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
    
    def test_insert_empty_batch(self, db_service, mock_session):
        """Test inserting empty batch returns 0"""
        result = db_service.insert_ohlcv_batch('AAPL', [], [])
        assert result == 0
        mock_session.execute.assert_not_called()
    
    def test_insert_metadata_mismatch(self, db_service, mock_session):
        """Test mismatched candle/metadata counts"""
        candles = [{'t': 1700000000000, 'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0, 'v': 1000000}]
        metadata = [
            {'validated': True, 'quality_score': 0.95, 'validation_notes': None, 'gap_detected': False, 'volume_anomaly': False},
            {'validated': False, 'quality_score': 0.5, 'validation_notes': 'test', 'gap_detected': True, 'volume_anomaly': False}
        ]
        
        result = db_service.insert_ohlcv_batch('AAPL', candles, metadata)
        
        assert result == 0
        mock_session.execute.assert_not_called()
    
    def test_insert_rollback_on_error(self, db_service, mock_session):
        """Test rollback occurs on database error"""
        mock_session.execute.side_effect = Exception("DB Error")
        mock_session.rollback = MagicMock()
        
        candles = [
            {
                't': 1700000000000,
                'o': 150.0,
                'h': 152.0,
                'l': 149.0,
                'c': 151.0,
                'v': 1000000
            }
        ]
        
        metadata = [
            {
                'validated': True,
                'quality_score': 0.95,
                'validation_notes': None,
                'gap_detected': False,
                'volume_anomaly': False
            }
        ]
        
        result = db_service.insert_ohlcv_batch('AAPL', candles, metadata)
        
        assert result == 0
        mock_session.rollback.assert_called_once()
    
    def test_insert_multiple_candles(self, db_service, mock_session):
        """Test inserting multiple candles in batch"""
        mock_session.commit = MagicMock()
        
        candles = [
            {'t': 1700000000000, 'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0, 'v': 1000000},
            {'t': 1700086400000, 'o': 151.0, 'h': 153.0, 'l': 150.0, 'c': 152.0, 'v': 1100000},
            {'t': 1700172800000, 'o': 152.0, 'h': 154.0, 'l': 151.0, 'c': 153.0, 'v': 1200000}
        ]
        
        metadata = [
            {'validated': True, 'quality_score': 0.95, 'validation_notes': None, 'gap_detected': False, 'volume_anomaly': False},
            {'validated': True, 'quality_score': 0.92, 'validation_notes': None, 'gap_detected': False, 'volume_anomaly': False},
            {'validated': True, 'quality_score': 0.88, 'validation_notes': 'high_volume', 'gap_detected': False, 'volume_anomaly': True}
        ]
        
        result = db_service.insert_ohlcv_batch('AAPL', candles, metadata)
        
        assert result == 3
        assert mock_session.execute.call_count == 3
        mock_session.commit.assert_called_once()


class TestGetHistoricalData:
    """Test historical data retrieval"""
    
    def test_query_valid_date_range(self, db_service, mock_session):
        """Test querying data for valid date range"""
        # Mock query result - includes timeframe in correct position
        mock_row = (
            datetime(2024, 11, 7),
            'AAPL',
            '1d',  # timeframe
            150.0, 152.0, 149.0, 151.0, 1000000,
            'polygon',
            True,
            0.95,
            None,
            False, False,
            datetime(2024, 11, 7, 10, 0)
        )
        
        # Mock the raw connection/cursor path
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [mock_row]
        
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        
        mock_db_connection = MagicMock()
        mock_db_connection.connection = mock_connection
        
        mock_session.connection.return_value = mock_db_connection
        
        data = db_service.get_historical_data('AAPL', '2024-11-07', '2024-11-07')
        
        assert len(data) == 1
        assert data[0]['symbol'] == 'AAPL'
        assert data[0]['timeframe'] == '1d'
        assert data[0]['close'] == 151.0
        assert data[0]['validated'] is True
        assert data[0]['quality_score'] == 0.95
    
    def test_query_empty_result(self, db_service, mock_session):
        """Test query with no results"""
        # Mock the raw connection/cursor path
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        
        mock_db_connection = MagicMock()
        mock_db_connection.connection = mock_connection
        
        mock_session.connection.return_value = mock_db_connection
        
        data = db_service.get_historical_data('NONEXISTENT', '2024-11-07', '2024-11-07')
        
        assert len(data) == 0
    
    def test_query_with_validation_filter(self, db_service, mock_session):
        """Test query with validated_only filter"""
        # Mock the raw connection/cursor path
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        
        mock_db_connection = MagicMock()
        mock_db_connection.connection = mock_connection
        
        mock_session.connection.return_value = mock_db_connection
        
        data = db_service.get_historical_data(
            'AAPL', 
            '2024-11-07', 
            '2024-11-07',
            validated_only=True
        )
        
        # Verify query was executed with correct parameters
        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        # Query string should contain validated = TRUE
        assert 'validated = TRUE' in call_args[0][0]
    
    def test_query_with_quality_threshold(self, db_service, mock_session):
        """Test query with minimum quality filter"""
        # Mock the raw connection/cursor path
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        
        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        
        mock_db_connection = MagicMock()
        mock_db_connection.connection = mock_connection
        
        mock_session.connection.return_value = mock_db_connection
        
        data = db_service.get_historical_data(
            'AAPL',
            '2024-11-07',
            '2024-11-07',
            min_quality=0.85
        )
        
        # Verify quality filter in query
        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        assert 'quality_score >= 0.85' in call_args[0][0]
    
    def test_query_error_handling(self, db_service, mock_session):
        """Test error handling in data retrieval"""
        mock_session.execute.side_effect = Exception("Query Error")
        
        data = db_service.get_historical_data('AAPL', '2024-11-07', '2024-11-07')
        
        assert data == []
        mock_session.close.assert_called_once()


class TestLogValidation:
    """Test validation logging"""
    
    def test_log_passed_validation(self, db_service, mock_session):
        """Test logging a passed validation check"""
        mock_session.commit = MagicMock()
        
        db_service.log_validation(
            'AAPL',
            'ohlcv_constraints',
            passed=True,
            quality_score=0.95
        )
        
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
    
    def test_log_failed_validation(self, db_service, mock_session):
        """Test logging a failed validation check"""
        mock_session.commit = MagicMock()
        
        db_service.log_validation(
            'AAPL',
            'price_move',
            passed=False,
            error_message='Extreme price move detected',
            quality_score=0.65
        )
        
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        assert 'validation_log' in call_args[0][0].text
    
    def test_log_validation_error_handling(self, db_service, mock_session):
        """Test error handling when logging validation"""
        mock_session.execute.side_effect = Exception("DB Error")
        mock_session.rollback = MagicMock()
        
        # Should not raise exception
        db_service.log_validation('AAPL', 'test', True)
        
        mock_session.rollback.assert_called_once()


class TestLogBackfill:
    """Test backfill job logging"""
    
    def test_log_successful_backfill(self, db_service, mock_session):
        """Test logging successful backfill job"""
        mock_session.commit = MagicMock()
        
        db_service.log_backfill(
            'AAPL',
            '2024-01-01',
            '2024-01-31',
            records_imported=20,
            success=True
        )
        
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        assert 'backfill_history' in call_args[0][0].text
    
    def test_log_failed_backfill(self, db_service, mock_session):
        """Test logging failed backfill job"""
        mock_session.commit = MagicMock()
        
        db_service.log_backfill(
            'AAPL',
            '2024-01-01',
            '2024-01-31',
            records_imported=0,
            success=False,
            error_details='API rate limit exceeded'
        )
        
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
    
    def test_log_backfill_error_handling(self, db_service, mock_session):
        """Test error handling when logging backfill"""
        mock_session.execute.side_effect = Exception("DB Error")
        mock_session.rollback = MagicMock()
        
        # Should not raise exception
        db_service.log_backfill('AAPL', '2024-01-01', '2024-01-31', 0, False)
        
        mock_session.rollback.assert_called_once()


class TestStatusMetrics:
    """Test metrics calculation and caching"""
    
    def test_get_status_metrics_fresh(self, db_service, mock_session):
        """Test retrieving fresh metrics"""
        mock_row = (5, datetime(2024, 11, 7), 1000, 950, 10)
        mock_result = MagicMock()
        mock_result.first.return_value = mock_row
        mock_session.execute.return_value = mock_result
        
        # Reset cache
        import src.services.database_service as db_module
        db_module._metrics_cache = {"data": None, "timestamp": 0}
        
        metrics = db_service.get_status_metrics()
        
        assert metrics['symbols_available'] == 5
        assert metrics['total_records'] == 1000
        assert metrics['validated_records'] == 950
        assert metrics['validation_rate_pct'] == 95.0
    
    def test_get_status_metrics_cached(self, db_service, mock_session):
        """Test metrics caching (should not query if cache valid)"""
        import src.services.database_service as db_module
        import time
        
        # Set cache with recent timestamp
        current_time = time.time()
        db_module._metrics_cache = {
            "data": {"test": "cached"},
            "timestamp": current_time
        }
        
        metrics = db_service.get_status_metrics()
        
        assert metrics == {"test": "cached"}
        # Should not have queried since cache is fresh
        mock_session.execute.assert_not_called()
    
    def test_get_status_metrics_empty_db(self, db_service, mock_session):
        """Test metrics when database is empty"""
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Reset cache
        import src.services.database_service as db_module
        db_module._metrics_cache = {"data": None, "timestamp": 0}
        
        metrics = db_service.get_status_metrics()
        
        assert metrics['symbols_available'] == 0
        assert metrics['total_records'] == 0
        assert metrics['validation_rate_pct'] == 0
    
    def test_get_status_metrics_error_handling(self, db_service, mock_session):
        """Test error handling in metrics retrieval"""
        mock_session.execute.side_effect = Exception("Query Error")
        
        # Reset cache
        import src.services.database_service as db_module
        db_module._metrics_cache = {"data": None, "timestamp": 0}
        
        metrics = db_service.get_status_metrics()
        
        assert metrics == {}
        mock_session.close.assert_called_once()


class TestSessionManagement:
    """Test database session lifecycle"""
    
    def test_session_closed_on_success(self, db_service, mock_session):
        """Test session is closed after successful operation"""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result
        
        db_service.get_historical_data('AAPL', '2024-11-07', '2024-11-07')
        
        mock_session.close.assert_called_once()
    
    def test_session_closed_on_error(self, db_service, mock_session):
        """Test session is closed even on error"""
        mock_session.execute.side_effect = Exception("Error")
        
        db_service.get_historical_data('AAPL', '2024-11-07', '2024-11-07')
        
        mock_session.close.assert_called_once()


# Run with: pytest tests/test_database.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
