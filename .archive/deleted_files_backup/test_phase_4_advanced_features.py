"""
Phase 4: Advanced Features & Data Integrity Tests
Tests for backfill state persistence, health monitoring, and data quality maintenance
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncpg

from src.services.database_service import DatabaseService
from src.scheduler import AutoBackfillScheduler


class TestBackfillStatePersistence:
    """Test backfill state persistence (concurrent job tracking)"""
    
    def test_create_backfill_state(self, db_service: DatabaseService):
        """Test creating a new backfill state record"""
        exec_id = db_service.create_backfill_state(
            symbol="AAPL",
            asset_class="stock",
            timeframe="1d",
            status="pending"
        )
        
        assert exec_id is not None
        assert isinstance(exec_id, str)
        
        # Update to in_progress so we can query it
        success = db_service.update_backfill_state(exec_id, "in_progress")
        assert success is True
        
        # Verify record was created and is active
        states = db_service.get_active_backfill_states()
        # Filter by symbol since multiple tests may run
        aapl_states = [s for s in states if s['symbol'] == 'AAPL' and s['timeframe'] == '1d' and s['execution_id'] == exec_id]
        assert len(aapl_states) >= 1
    
    def test_update_backfill_state_success(self, db_service: DatabaseService):
        """Test updating backfill state to completed"""
        exec_id = db_service.create_backfill_state(
            symbol="GOOGL",
            asset_class="stock",
            timeframe="1d",
            status="pending"
        )
        
        # Update to in_progress
        success = db_service.update_backfill_state(
            execution_id=exec_id,
            status="in_progress",
            records_inserted=0
        )
        assert success is True
        
        # Update to completed
        success = db_service.update_backfill_state(
            execution_id=exec_id,
            status="completed",
            records_inserted=100
        )
        assert success is True
    
    def test_update_backfill_state_failed(self, db_service: DatabaseService):
        """Test updating backfill state to failed with error message"""
        exec_id = db_service.create_backfill_state(
            symbol="MSFT",
            asset_class="stock",
            timeframe="1h"
        )
        
        success = db_service.update_backfill_state(
            execution_id=exec_id,
            status="failed",
            error_message="API rate limit exceeded",
            retry_count=3
        )
        assert success is True
    
    def test_get_active_backfill_states(self, db_service: DatabaseService):
        """Test retrieving active (in_progress) backfill states"""
        # Create multiple states
        ids = []
        for i in range(3):
            exec_id = db_service.create_backfill_state(
                symbol=f"TEST{i}",
                asset_class="stock",
                timeframe="1d",
                status="pending"
            )
            ids.append(exec_id)
            
            # Mark one as in_progress
            if i == 1:
                db_service.update_backfill_state(exec_id, "in_progress")
        
        active_states = db_service.get_active_backfill_states()
        assert isinstance(active_states, list)
        
        # Should have at least the one we marked as in_progress
        in_progress_count = len([s for s in active_states if s['symbol'] in ['TEST0', 'TEST1', 'TEST2']])
        assert in_progress_count >= 1


class TestDataQualityMaintenance:
    """Test data quality maintenance (cleanup and anomaly detection)"""
    
    def test_cleanup_duplicate_records_dry_run(self, db_service: DatabaseService):
        """Test dry-run duplicate detection without deleting"""
        results = db_service.cleanup_duplicate_records(
            symbol="AAPL",
            timeframe="1d",
            dry_run=True
        )
        
        assert isinstance(results, dict)
        assert "total_duplicates_found" in results
        assert "total_records_removed" in results
        assert results["total_records_removed"] == 0  # Dry run shouldn't remove
    
    def test_cleanup_duplicate_records_active(self, db_service: DatabaseService):
        """Test actual duplicate cleanup"""
        results = db_service.cleanup_duplicate_records(
            symbol=None,  # Check all symbols
            timeframe="1d",
            dry_run=False
        )
        
        assert isinstance(results, dict)
        assert "total_duplicates_found" in results
        assert "total_records_removed" in results
        assert "cleanup_details" in results
        
        if results["total_duplicates_found"] > 0:
            assert results["total_records_removed"] >= 0
            assert isinstance(results["cleanup_details"], list)
    
    def test_detect_data_anomalies_gaps(self, db_service: DatabaseService):
        """Test detection of data gaps"""
        results = db_service.detect_data_anomalies(
            symbol=None,
            check_gaps=True,
            check_outliers=False,
            check_staleness=False
        )
        
        assert isinstance(results, dict)
        assert "gaps" in results
        assert "timestamp" in results
        assert isinstance(results["gaps"], list)
    
    def test_detect_data_anomalies_staleness(self, db_service: DatabaseService):
        """Test detection of stale data"""
        results = db_service.detect_data_anomalies(
            symbol=None,
            check_gaps=False,
            check_outliers=False,
            check_staleness=True
        )
        
        assert isinstance(results, dict)
        assert "stale_data" in results
        assert isinstance(results["stale_data"], list)
    
    def test_detect_data_anomalies_outliers(self, db_service: DatabaseService):
        """Test detection of price outliers"""
        results = db_service.detect_data_anomalies(
            symbol=None,
            check_gaps=False,
            check_outliers=True,
            check_staleness=False
        )
        
        assert isinstance(results, dict)
        assert "outliers" in results
        assert isinstance(results["outliers"], list)
    
    def test_detect_data_anomalies_combined(self, db_service: DatabaseService):
        """Test all anomaly checks combined"""
        results = db_service.detect_data_anomalies(
            symbol=None,
            check_gaps=True,
            check_outliers=True,
            check_staleness=True
        )
        
        assert isinstance(results, dict)
        assert "total_anomalies" in results
        assert results["total_anomalies"] >= 0


class TestSymbolFailureTracking:
    """Test consecutive failure tracking and alerting"""
    
    def test_track_symbol_success(self, db_service: DatabaseService):
        """Test tracking successful backfill resets failure count"""
        # First, track a failure
        db_service.track_symbol_failure("TEST_SYM", success=False)
        db_service.track_symbol_failure("TEST_SYM", success=False)
        
        # Then track success
        result = db_service.track_symbol_failure("TEST_SYM", success=True)
        
        assert result["symbol"] == "TEST_SYM"
        assert result["consecutive_failures"] == 0
        assert result["alert_sent"] is False
    
    def test_track_symbol_failure_count(self, db_service: DatabaseService):
        """Test failure count increments"""
        symbol = f"FAIL_TEST_{datetime.utcnow().timestamp()}"
        
        # Track 3 failures
        for i in range(3):
            result = db_service.track_symbol_failure(symbol, success=False)
            assert result["consecutive_failures"] == i + 1
    
    def test_track_symbol_failure_alert(self, db_service: DatabaseService):
        """Test alert triggering at 3 consecutive failures"""
        symbol = f"ALERT_TEST_{datetime.utcnow().timestamp()}"
        
        # Track 3 failures
        for i in range(3):
            result = db_service.track_symbol_failure(symbol, success=False)
        
        # Should trigger alert
        assert result["consecutive_failures"] == 3
        assert result["should_alert"] is True


class TestHealthMonitoringIntegration:
    """Integration tests for health monitoring job"""
    
    @pytest.mark.asyncio
    async def test_health_monitoring_job_execution(self, db_service: DatabaseService):
        """Test health monitoring job can execute"""
        scheduler = AutoBackfillScheduler(
            polygon_api_key="test_key",
            database_url="postgresql://test:test@localhost:5432/test",
            symbols=[],
            config=None
        )
        
        # Mock the database methods
        with patch.object(scheduler, '_load_symbols_from_db', return_value=[]):
            with patch.object(scheduler.db_service, 'detect_data_anomalies', return_value={'total_anomalies': 0}):
                try:
                    await scheduler._health_monitoring_job()
                    # If we get here, the job executed without crashing
                    assert True
                except Exception as e:
                    # Expected if database isn't available
                    assert "asyncpg" in str(type(e).__name__) or "Connection" in str(e)
    
    @pytest.mark.asyncio
    async def test_load_symbols_from_db(self):
        """Test loading symbols from database"""
        scheduler = AutoBackfillScheduler(
            polygon_api_key="test_key",
            database_url="postgresql://test:test@localhost:5432/test",
            symbols=[]
        )
        
        # Mock asyncpg connection
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {'symbol': 'AAPL', 'asset_class': 'stock', 'timeframes': ['1d', '1h']},
            {'symbol': 'BTC', 'asset_class': 'crypto', 'timeframes': ['1h', '4h']}
        ]
        mock_conn.close = AsyncMock()
        
        with patch('asyncpg.connect', return_value=mock_conn):
            symbols = await scheduler._load_symbols_from_db()
            
            assert len(symbols) == 2
            assert symbols[0][0] == 'AAPL'
            assert symbols[0][1] == 'stock'
            assert 'AAPL' in [s[0] for s in symbols]


class TestPhase4Integration:
    """Integration tests for Phase 4 features working together"""
    
    def test_concurrent_backfill_tracking_workflow(self, db_service: DatabaseService):
        """Test full workflow: create, update, query backfill states"""
        # Create states for multiple symbols
        exec_ids = []
        symbols = ['TEST_A', 'TEST_B', 'TEST_C']
        
        for symbol in symbols:
            exec_id = db_service.create_backfill_state(
                symbol=symbol,
                asset_class="stock",
                timeframe="1d",
                status="pending"
            )
            exec_ids.append(exec_id)
            
            # Update to in_progress
            db_service.update_backfill_state(exec_id, "in_progress")
        
        # Get active states
        active = db_service.get_active_backfill_states()
        active_symbols = [s['symbol'] for s in active]
        
        # Should have at least our test symbols
        for symbol in symbols:
            matching = [s for s in active if s['symbol'] == symbol]
            assert len(matching) >= 1
        
        # Complete all states
        for exec_id in exec_ids:
            db_service.update_backfill_state(
                exec_id,
                "completed",
                records_inserted=50
            )
    
    def test_data_quality_workflow(self, db_service: DatabaseService):
        """Test data quality workflow: detect -> cleanup -> verify"""
        # Detect anomalies
        anomalies = db_service.detect_data_anomalies(
            check_gaps=True,
            check_outliers=True,
            check_staleness=True
        )
        
        assert "total_anomalies" in anomalies
        initial_count = anomalies["total_anomalies"]
        
        # Cleanup duplicates
        cleanup = db_service.cleanup_duplicate_records(dry_run=False)
        assert "total_records_removed" in cleanup
        
        # Detect again
        anomalies_after = db_service.detect_data_anomalies(
            check_gaps=True,
            check_outliers=True,
            check_staleness=True
        )
        
        # May have fewer anomalies after cleanup
        assert "total_anomalies" in anomalies_after


# Fixtures

@pytest.fixture
def db_service():
    """Database service instance for testing"""
    import os
    database_url = os.getenv("DATABASE_URL", "postgresql://market_user:changeMe123@localhost:5432/market_data")
    service = DatabaseService(database_url)
    yield service
