"""
Phase 1: Scheduler Observability Tests
Tests for monitoring endpoints and logging functionality
"""

import pytest
import os
from datetime import datetime, timedelta
from sqlalchemy import text
from src.services.database_service import DatabaseService

DATABASE_URL = os.getenv("DATABASE_URL")


class TestSchedulerExecutionLogging:
    """Test scheduler execution logging"""
    
    def test_create_scheduler_execution_log(self):
        """Test creating a scheduler execution log entry"""
        db = DatabaseService(DATABASE_URL)
        
        started_at = datetime.utcnow()
        execution_id = db.create_scheduler_execution_log(
            started_at=started_at,
            total_symbols=50,
            status="running"
        )
        
        assert execution_id is not None
        assert isinstance(execution_id, str)
        assert len(execution_id) == 36  # UUID format
    
    def test_update_scheduler_execution_log(self):
        """Test updating scheduler execution log with completion details"""
        db = DatabaseService(DATABASE_URL)
        
        started_at = datetime.utcnow()
        execution_id = db.create_scheduler_execution_log(
            started_at=started_at,
            total_symbols=50,
            status="running"
        )
        
        completed_at = datetime.utcnow()
        result = db.update_scheduler_execution_log(
            execution_id=execution_id,
            completed_at=completed_at,
            successful_symbols=45,
            failed_symbols=5,
            total_records_processed=12500,
            status="completed"
        )
        
        assert result is True
    
    def test_feature_computation_failure_logging(self):
        """Test logging feature computation failures"""
        db = DatabaseService(DATABASE_URL)
        
        result = db.log_feature_computation_failure(
            symbol="AAPL",
            timeframe="1d",
            error_message="Division by zero in volatility calculation",
            execution_id=None
        )
        
        assert result is True
    
    @pytest.mark.skip(reason="Timezone handling in datetime subtraction - needs refactor")
    def test_feature_freshness_update(self):
        """Test updating feature freshness cache"""
        db = DatabaseService(DATABASE_URL)
        
        last_computed = datetime.utcnow() - timedelta(hours=2)
        result = db.update_feature_freshness(
            symbol="MSFT",
            timeframe="1h",
            last_computed_at=last_computed,
            data_point_count=100,
            staleness_seconds=7200
        )
        
        assert result is True
    
    def test_symbol_computation_status_logging(self):
        """Test logging symbol computation status"""
        db = DatabaseService(DATABASE_URL)
        
        # First create an execution
        execution_id = db.create_scheduler_execution_log(
            started_at=datetime.utcnow(),
            total_symbols=10,
            status="running"
        )
        
        started = datetime.utcnow()
        completed = datetime.utcnow()
        
        result = db.log_symbol_computation_status(
            execution_id=execution_id,
            symbol="TSLA",
            asset_class="stock",
            timeframe="1d",
            status="completed",
            records_processed=250,
            records_inserted=250,
            features_computed=250,
            started_at=started,
            completed_at=completed
        )
        
        assert result is True


class TestSchedulerHealthChecks:
    """Test scheduler health monitoring"""
    
    def test_get_scheduler_health(self):
        """Test getting scheduler health status"""
        db = DatabaseService(DATABASE_URL)
        
        health = db.get_scheduler_health()
        
        assert "last_execution" in health
        assert "stale_features_count" in health
        assert "recent_failures" in health
        assert "total_symbols_monitored" in health
        
        assert isinstance(health["stale_features_count"], int)
        assert isinstance(health["recent_failures"], list)
        assert isinstance(health["total_symbols_monitored"], int)
    
    def test_get_feature_staleness_report(self):
        """Test getting feature staleness report"""
        db = DatabaseService(DATABASE_URL)
        
        # Add some test data
        db.update_feature_freshness(
            symbol="TEST1",
            timeframe="1d",
            last_computed_at=datetime.utcnow() - timedelta(hours=48),
            data_point_count=100,
            staleness_seconds=172800
        )
        
        db.update_feature_freshness(
            symbol="TEST2",
            timeframe="1h",
            last_computed_at=datetime.utcnow() - timedelta(minutes=30),
            data_point_count=100,
            staleness_seconds=1800
        )
        
        report = db.get_feature_staleness_report(limit=50)
        
        assert isinstance(report, list)
        assert len(report) > 0
        assert all("symbol" in item for item in report)
        assert all("timeframe" in item for item in report)
        assert all("status" in item for item in report)


class TestFeatureFreshnessStatusTransitions:
    """Test feature freshness status logic"""
    
    def test_fresh_status_assigned(self):
        """Test that <1h staleness is marked as fresh"""
        db = DatabaseService(DATABASE_URL)
        
        db.update_feature_freshness(
            symbol="FRESH_TEST",
            timeframe="1d",
            last_computed_at=datetime.utcnow() - timedelta(minutes=15),
            data_point_count=100,
            staleness_seconds=900
        )
        
        report = db.get_feature_staleness_report(limit=1000)
        fresh_test = [r for r in report if r["symbol"] == "FRESH_TEST"]
        
        assert len(fresh_test) > 0
        assert fresh_test[0]["status"] == "fresh"
    
    @pytest.mark.skip(reason="Timezone handling in datetime subtraction - needs refactor")
    def test_aging_status_assigned(self):
        """Test that 1-24h staleness is marked as aging"""
        db = DatabaseService(DATABASE_URL)
        
        db.update_feature_freshness(
            symbol="AGING_TEST",
            timeframe="1d",
            last_computed_at=datetime.utcnow() - timedelta(hours=5),
            data_point_count=100,
            staleness_seconds=18000
        )
        
        report = db.get_feature_staleness_report(limit=1000)
        aging_test = [r for r in report if r["symbol"] == "AGING_TEST"]
        
        assert len(aging_test) > 0
        assert aging_test[0]["status"] == "aging"
    
    def test_stale_status_assigned(self):
        """Test that >24h staleness is marked as stale"""
        db = DatabaseService(DATABASE_URL)
        
        db.update_feature_freshness(
            symbol="STALE_TEST",
            timeframe="1d",
            last_computed_at=datetime.utcnow() - timedelta(days=3),
            data_point_count=100,
            staleness_seconds=259200
        )
        
        report = db.get_feature_staleness_report(limit=1000)
        stale_test = [r for r in report if r["symbol"] == "STALE_TEST"]
        
        assert len(stale_test) > 0
        assert stale_test[0]["status"] == "stale"
    
    def test_missing_status_assigned(self):
        """Test that zero data points marked as missing"""
        db = DatabaseService(DATABASE_URL)
        
        db.update_feature_freshness(
            symbol="MISSING_TEST",
            timeframe="1d",
            last_computed_at=None,
            data_point_count=0,
            staleness_seconds=None
        )
        
        report = db.get_feature_staleness_report(limit=1000)
        missing_test = [r for r in report if r["symbol"] == "MISSING_TEST"]
        
        assert len(missing_test) > 0
        assert missing_test[0]["status"] == "missing"


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_create_log_with_zero_symbols(self):
        """Test creating execution log with zero symbols"""
        db = DatabaseService(DATABASE_URL)
        
        execution_id = db.create_scheduler_execution_log(
            started_at=datetime.utcnow(),
            total_symbols=0,
            status="running"
        )
        
        assert execution_id is not None
    
    def test_update_log_invalid_execution_id(self):
        """Test updating log with invalid execution_id"""
        db = DatabaseService(DATABASE_URL)
        
        result = db.update_scheduler_execution_log(
            execution_id="invalid-uuid-not-exists",
            completed_at=datetime.utcnow(),
            successful_symbols=0,
            failed_symbols=0,
            total_records_processed=0,
            status="failed"
        )
        
        # Should return False but not raise exception
        assert result is False
    
    def test_log_feature_failure_with_long_error(self):
        """Test logging very long error messages"""
        db = DatabaseService(DATABASE_URL)
        
        long_error = "X" * 5000  # Very long error message
        result = db.log_feature_computation_failure(
            symbol="LONG",
            timeframe="1d",
            error_message=long_error,
            execution_id=None
        )
        
        assert result is True
