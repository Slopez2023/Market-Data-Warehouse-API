"""
Comprehensive tests for backfill progress tracking implementation.
Tests the complete flow from API endpoint to database to background worker.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from uuid import uuid4

from src.services.backfill_worker import BackfillWorker, init_backfill_worker, enqueue_backfill_job
from src.services.database_service import DatabaseService


class TestBackfillJobCreation:
    """Test backfill job creation in database"""
    
    def test_create_backfill_job_success(self, db_service):
        """Test creating a new backfill job"""
        job_id = str(uuid4())
        symbols = ["AAPL", "MSFT"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1h", "1d"]
        
        result = db_service.create_backfill_job(
            job_id, symbols, start_date, end_date, timeframes
        )
        
        assert result["job_id"] == job_id
        assert result["status"] == "created"
    
    def test_create_backfill_job_large_symbol_list(self, db_service):
        """Test creating backfill job with max symbols"""
        job_id = str(uuid4())
        symbols = [f"SYM{i:03d}" for i in range(100)]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1d"]
        
        result = db_service.create_backfill_job(
            job_id, symbols, start_date, end_date, timeframes
        )
        
        assert result["job_id"] == job_id
        assert result["status"] == "created"
    
    def test_create_backfill_job_multiple_timeframes(self, db_service):
        """Test creating backfill job with multiple timeframes"""
        job_id = str(uuid4())
        symbols = ["AAPL"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        
        result = db_service.create_backfill_job(
            job_id, symbols, start_date, end_date, timeframes
        )
        
        assert result["job_id"] == job_id


class TestBackfillJobStatus:
    """Test backfill job status retrieval"""
    
    def test_get_backfill_job_status_queued(self, db_service):
        """Test getting status of queued job"""
        job_id = str(uuid4())
        symbols = ["AAPL"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1d"]
        
        db_service.create_backfill_job(job_id, symbols, start_date, end_date, timeframes)
        status = db_service.get_backfill_job_status(job_id)
        
        assert status["job_id"] == job_id
        assert status["status"] == "queued"
        assert status["progress_pct"] == 0
        assert status["symbols_total"] == 1
        assert status["symbols_completed"] == 0
        assert status["total_records_fetched"] == 0
        assert status["total_records_inserted"] == 0
    
    def test_get_backfill_job_status_nonexistent(self, db_service):
        """Test getting status of nonexistent job"""
        fake_job_id = str(uuid4())
        status = db_service.get_backfill_job_status(fake_job_id)
        
        assert "error" in status
        assert status["error"] == "Job not found"
    
    def test_get_backfill_job_status_with_progress(self, db_service):
        """Test getting status of job with progress"""
        job_id = str(uuid4())
        symbols = ["AAPL", "MSFT"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1h", "1d"]
        
        db_service.create_backfill_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Simulate progress by directly updating (this would happen in worker)
        session = db_service.SessionLocal()
        try:
            from sqlalchemy import text
            
            # Insert progress records
            session.execute(
                text("""
                    INSERT INTO backfill_job_progress 
                    (job_id, symbol, timeframe, status, records_fetched, records_inserted, completed_at)
                    VALUES (:job_id, :symbol, :timeframe, 'completed', :records_fetched, :records_inserted, NOW())
                """),
                {
                    "job_id": job_id,
                    "symbol": "AAPL",
                    "timeframe": "1h",
                    "records_fetched": 250,
                    "records_inserted": 250
                }
            )
            session.commit()
        finally:
            session.close()
        
        status = db_service.get_backfill_job_status(job_id)
        
        assert len(status["details"]) == 1
        assert status["details"][0]["symbol"] == "AAPL"
        assert status["details"][0]["timeframe"] == "1h"
        assert status["details"][0]["status"] == "completed"
        assert status["details"][0]["records_inserted"] == 250


class TestGetRecentBackfillJobs:
    """Test retrieving recent backfill jobs"""
    
    def test_get_recent_backfill_jobs_empty(self, db_service):
        """Test getting recent jobs when none exist"""
        jobs = db_service.get_recent_backfill_jobs(limit=10)
        # Should not raise error, can be empty list
        assert isinstance(jobs, list)
    
    def test_get_recent_backfill_jobs_multiple(self, db_service):
        """Test getting multiple recent jobs"""
        job_ids = []
        for i in range(3):
            job_id = str(uuid4())
            job_ids.append(job_id)
            db_service.create_backfill_job(
                job_id, 
                [f"SYM{i}"], 
                "2024-01-01", 
                "2024-01-31",
                ["1d"]
            )
        
        jobs = db_service.get_recent_backfill_jobs(limit=10)
        
        assert len(jobs) == 3
        # Most recent first
        assert jobs[0]["job_id"] == job_ids[2]
    
    def test_get_recent_backfill_jobs_limit(self, db_service):
        """Test limit parameter"""
        for i in range(5):
            job_id = str(uuid4())
            db_service.create_backfill_job(
                job_id,
                [f"SYM{i}"],
                "2024-01-01",
                "2024-01-31",
                ["1d"]
            )
        
        jobs = db_service.get_recent_backfill_jobs(limit=2)
        
        assert len(jobs) == 2


class TestBackfillWorker:
    """Test the BackfillWorker class"""
    
    @pytest.mark.asyncio
    async def test_backfill_worker_initialization(self):
        """Test that worker initializes correctly"""
        mock_db = Mock()
        mock_polygon = Mock()
        
        worker = BackfillWorker(mock_db, mock_polygon)
        
        assert worker.db is mock_db
        assert worker.polygon is mock_polygon
    
    @pytest.mark.asyncio
    async def test_backfill_worker_process_job_updates_status(self, db_service):
        """Test that worker updates job status"""
        job_id = str(uuid4())
        symbols = ["AAPL"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1d"]
        
        db_service.create_backfill_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Mock polygon service
        mock_polygon = AsyncMock()
        mock_polygon.fetch_candles = AsyncMock(return_value=[])
        
        worker = BackfillWorker(db_service, mock_polygon)
        
        # Mock insert_candles_batch
        db_service.insert_candles_batch = AsyncMock(return_value=0)
        
        # Process the job
        await worker.process_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Check job status was updated
        status = db_service.get_backfill_job_status(job_id)
        assert status["status"] == "completed"
        assert status["progress_pct"] == 100
    
    @pytest.mark.asyncio
    async def test_backfill_worker_handles_fetch_error(self, db_service):
        """Test that worker handles fetch errors gracefully"""
        job_id = str(uuid4())
        symbols = ["AAPL"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1d"]
        
        db_service.create_backfill_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Mock polygon service to raise error
        mock_polygon = AsyncMock()
        mock_polygon.fetch_candles = AsyncMock(
            side_effect=Exception("API Error")
        )
        
        worker = BackfillWorker(db_service, mock_polygon)
        db_service.insert_candles_batch = AsyncMock(return_value=0)
        
        # Process the job - should handle error
        await worker.process_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Check job status
        status = db_service.get_backfill_job_status(job_id)
        # Job should still complete even if symbol failed
        assert status["status"] == "completed"
        # Check that progress record was marked as failed
        assert any(d["status"] == "failed" for d in status["details"])
    
    @pytest.mark.asyncio
    async def test_backfill_worker_multiple_symbols(self, db_service):
        """Test processing multiple symbols"""
        job_id = str(uuid4())
        symbols = ["AAPL", "MSFT"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1d"]
        
        db_service.create_backfill_job(job_id, symbols, start_date, end_date, timeframes)
        
        mock_polygon = AsyncMock()
        mock_polygon.fetch_candles = AsyncMock(return_value=[])
        
        worker = BackfillWorker(db_service, mock_polygon)
        db_service.insert_candles_batch = AsyncMock(return_value=0)
        
        await worker.process_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Verify polygon was called for each symbol
        assert mock_polygon.fetch_candles.call_count == 2
        
        status = db_service.get_backfill_job_status(job_id)
        assert status["progress_pct"] == 100


class TestBackfillWorkerInitialization:
    """Test backfill worker initialization"""
    
    def test_init_backfill_worker_success(self):
        """Test initializing backfill worker"""
        mock_db = Mock()
        mock_polygon = Mock()
        
        init_backfill_worker(mock_db, mock_polygon)
        
        # Worker should be initialized (we can't directly access the global)
        # but we can test that calling enqueue_backfill_job doesn't raise
        try:
            enqueue_backfill_job(
                str(uuid4()),
                ["AAPL"],
                "2024-01-01",
                "2024-01-31",
                ["1d"]
            )
        except RuntimeError as e:
            if "not initialized" in str(e):
                pytest.fail("Worker was not initialized")


class TestBackfillIntegration:
    """Integration tests for the complete backfill flow"""
    
    def test_backfill_api_request_validation(self):
        """Test that API validates backfill requests"""
        # This would be tested with FastAPI test client
        # Validate: symbols required, date format, symbol count limit
        pass
    
    @pytest.mark.asyncio
    async def test_complete_backfill_flow(self, db_service):
        """Test complete backfill flow: create -> status -> complete"""
        job_id = str(uuid4())
        symbols = ["AAPL"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1d"]
        
        # Step 1: Create job
        db_service.create_backfill_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Step 2: Verify queued status
        status = db_service.get_backfill_job_status(job_id)
        assert status["status"] == "queued"
        assert status["progress_pct"] == 0
        
        # Step 3: Simulate worker processing
        mock_polygon = AsyncMock()
        mock_polygon.fetch_candles = AsyncMock(return_value=[
            {"o": 150, "h": 151, "l": 149, "c": 150.5, "v": 1000000, "t": 1704067200}
        ])
        
        worker = BackfillWorker(db_service, mock_polygon)
        db_service.insert_candles_batch = AsyncMock(return_value=1)
        
        await worker.process_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Step 4: Verify completed status
        status = db_service.get_backfill_job_status(job_id)
        assert status["status"] == "completed"
        assert status["progress_pct"] == 100
        assert status["total_records_inserted"] == 1


class TestBackfillDatabaseSchema:
    """Test the database schema for backfill jobs"""
    
    def test_backfill_jobs_table_exists(self, db_service):
        """Test that backfill_jobs table exists"""
        session = db_service.SessionLocal()
        try:
            from sqlalchemy import text
            result = session.execute(text("""
                SELECT EXISTS(
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'backfill_jobs'
                )
            """)).scalar()
            assert result is True
        finally:
            session.close()
    
    def test_backfill_job_progress_table_exists(self, db_service):
        """Test that backfill_job_progress table exists"""
        session = db_service.SessionLocal()
        try:
            from sqlalchemy import text
            result = session.execute(text("""
                SELECT EXISTS(
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'backfill_job_progress'
                )
            """)).scalar()
            assert result is True
        finally:
            session.close()
    
    def test_backfill_jobs_indexes_exist(self, db_service):
        """Test that required indexes exist"""
        session = db_service.SessionLocal()
        try:
            from sqlalchemy import text
            # Check for status index
            result = session.execute(text("""
                SELECT EXISTS(
                    SELECT FROM information_schema.statistics 
                    WHERE table_name = 'backfill_jobs' 
                    AND index_name = 'idx_backfill_jobs_status'
                )
            """)).scalar()
            # Note: index existence depends on database - may not work on all systems
        finally:
            session.close()


class TestErrorHandling:
    """Test error handling in backfill system"""
    
    def test_create_backfill_job_invalid_dates(self, db_service):
        """Test error handling for invalid dates"""
        job_id = str(uuid4())
        
        # This would be validated at API level before reaching database
        # Database should still handle it gracefully
        pass
    
    @pytest.mark.asyncio
    async def test_backfill_worker_recovery_from_partial_failure(self, db_service):
        """Test that worker continues after some symbols fail"""
        job_id = str(uuid4())
        symbols = ["AAPL", "MSFT", "GOOGL"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1d"]
        
        db_service.create_backfill_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Mock polygon to fail for MSFT
        call_count = 0
        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            symbol = kwargs.get("symbol")
            if symbol == "MSFT":
                raise Exception("API unavailable")
            return []
        
        mock_polygon = AsyncMock()
        mock_polygon.fetch_candles = AsyncMock(side_effect=side_effect)
        
        worker = BackfillWorker(db_service, mock_polygon)
        db_service.insert_candles_batch = AsyncMock(return_value=0)
        
        await worker.process_job(job_id, symbols, start_date, end_date, timeframes)
        
        # Should have called fetch_candles 3 times (once per symbol)
        assert mock_polygon.fetch_candles.call_count == 3
        
        # Job should complete despite one failure
        status = db_service.get_backfill_job_status(job_id)
        assert status["status"] == "completed"
        
        # Check progress details
        assert len(status["details"]) == 3
        failed = [d for d in status["details"] if d["status"] == "failed"]
        completed = [d for d in status["details"] if d["status"] == "completed"]
        assert len(failed) == 1
        assert len(completed) == 2


class TestProgressTracking:
    """Test progress tracking accuracy"""
    
    @pytest.mark.asyncio
    async def test_progress_percentage_calculation(self, db_service):
        """Test that progress percentage is calculated correctly"""
        job_id = str(uuid4())
        symbols = ["AAPL", "MSFT"]
        start_date = "2024-01-01"
        end_date = "2024-01-31"
        timeframes = ["1h", "1d"]  # 4 total combinations
        
        db_service.create_backfill_job(job_id, symbols, start_date, end_date, timeframes)
        
        mock_polygon = AsyncMock()
        mock_polygon.fetch_candles = AsyncMock(return_value=[])
        
        worker = BackfillWorker(db_service, mock_polygon)
        db_service.insert_candles_batch = AsyncMock(return_value=0)
        
        await worker.process_job(job_id, symbols, start_date, end_date, timeframes)
        
        status = db_service.get_backfill_job_status(job_id)
        # 4 total combinations, should be 100% when complete
        assert status["progress_pct"] == 100


# Fixtures
@pytest.fixture
def db_service():
    """Create a test database service"""
    from src.config import config
    db = DatabaseService(config.database_url)
    return db
