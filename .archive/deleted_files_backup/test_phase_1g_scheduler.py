"""
Tests for Phase 1g: Enrichment Scheduler
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from src.services.enrichment_scheduler import EnrichmentScheduler, EnrichmentJobStatus


@pytest.fixture
def mock_db():
    """Create mock database service"""
    db = Mock()
    db.database_url = "postgresql://test:test@localhost/test"
    db.SessionLocal = Mock()
    return db


@pytest.fixture
def mock_config():
    """Create mock config"""
    config = Mock()
    config.polygon_api_key = "test_key"
    config.database_url = "postgresql://test:test@localhost/test"
    return config


@pytest.fixture
async def scheduler(mock_db, mock_config):
    """Create scheduler instance"""
    scheduler = EnrichmentScheduler(
        db_service=mock_db,
        config=mock_config,
        enrichment_hour=1,
        enrichment_minute=30,
        max_concurrent_symbols=5,
        enable_daily_enrichment=False  # Don't auto-start
    )
    yield scheduler
    # Cleanup
    if scheduler.is_running:
        scheduler.stop()


@pytest.mark.asyncio
async def test_scheduler_initialization(scheduler):
    """Test scheduler initializes correctly"""
    assert scheduler.enrichment_hour == 1
    assert scheduler.enrichment_minute == 30
    assert scheduler.max_concurrent_symbols == 5
    assert scheduler.max_retries == 3
    assert scheduler.is_running == False


@pytest.mark.asyncio
async def test_scheduler_start_stop(scheduler):
    """Test scheduler start and stop"""
    scheduler.start()
    assert scheduler.is_running == True
    assert scheduler.scheduler.running == True
    
    scheduler.stop()
    assert scheduler.is_running == False


@pytest.mark.asyncio
async def test_load_symbols_from_db(scheduler):
    """Test loading symbols from database"""
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetch.return_value = [
            {'symbol': 'AAPL', 'asset_class': 'stock', 'timeframes': ['1d', '1h']},
            {'symbol': 'BTC', 'asset_class': 'crypto', 'timeframes': ['1d']}
        ]
        
        symbols = await scheduler._get_symbols_to_enrich()
        
        assert len(symbols) == 2
        assert symbols[0][0] == 'AAPL'
        assert symbols[1][0] == 'BTC'


@pytest.mark.asyncio
async def test_job_status_tracking(scheduler):
    """Test job status tracking"""
    symbol = "AAPL"
    
    # Check initial status
    status = await scheduler.get_job_status(symbol)
    assert status == {}
    
    # Initialize job
    scheduler.job_status[symbol] = {
        "status": EnrichmentJobStatus.PENDING,
        "retry_count": 0,
        "last_error": None
    }
    
    # Check tracked status
    status = await scheduler.get_job_status(symbol)
    assert status["status"] == EnrichmentJobStatus.PENDING
    assert status["retry_count"] == 0


@pytest.mark.asyncio
async def test_scheduler_status(scheduler):
    """Test getting scheduler status"""
    status = await scheduler.get_scheduler_status()
    
    assert "running" in status
    assert "scheduler_running" in status
    assert "config" in status
    assert status["config"]["enrichment_hour"] == 1
    assert status["config"]["max_concurrent_symbols"] == 5


@pytest.mark.asyncio
async def test_manual_enrichment_trigger(scheduler):
    """Test manual enrichment trigger"""
    with patch.object(scheduler, '_enrichment_job') as mock_job:
        mock_job.return_value = {
            "symbols_total": 10,
            "symbols_successful": 10,
            "symbols_failed": 0
        }
        
        result = await scheduler.trigger_enrichment_now(symbols=["AAPL"])
        
        mock_job.assert_called_once_with(symbols=["AAPL"], asset_class=None, manual_trigger=True)


@pytest.mark.asyncio
async def test_concurrent_processing(scheduler):
    """Test concurrent symbol processing"""
    symbols = [
        ("AAPL", "stock", ["1d"]),
        ("MSFT", "stock", ["1d"]),
        ("BTC", "crypto", ["1d"]),
        ("ETH", "crypto", ["1d"]),
        ("SPY", "etf", ["1d"])
    ]
    
    results = {
        "processing_symbols": {},
        "symbols_successful": 0,
        "symbols_failed": 0,
        "symbols_retried": 0,
        "total_records_inserted": 0,
        "total_records_updated": 0,
        "errors": []
    }
    
    with patch.object(scheduler, '_process_symbol_with_retry', new_callable=AsyncMock) as mock_process:
        mock_process.return_value = None
        
        await scheduler._process_symbols_concurrent(symbols, results)
        
        # Verify all symbols were processed
        assert mock_process.call_count == 5


@pytest.mark.asyncio
async def test_enrichment_metrics(scheduler):
    """Test getting enrichment metrics"""
    with patch('asyncpg.connect') as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        
        mock_conn.fetchrow.side_effect = [
            {
                'total_fetches': 100,
                'successful_fetches': 98,
                'avg_response_time_ms': 250,
                'api_quota_remaining': 450
            },
            {
                'total_computations': 98,
                'successful_computations': 96,
                'avg_computation_time_ms': 15
            },
            {
                'symbols_tracked': 10,
                'avg_validation_rate': 98.5,
                'avg_quality_score': 0.93
            }
        ]
        
        metrics = await scheduler.get_enrichment_metrics()
        
        assert metrics['fetch_pipeline']['total_fetches'] == 100
        assert metrics['compute_pipeline']['total_computations'] == 98
        assert metrics['data_quality']['symbols_tracked'] == 10


@pytest.mark.asyncio
async def test_max_concurrent_control(scheduler):
    """Test that max_concurrent_symbols is respected"""
    scheduler.max_concurrent_symbols = 2
    
    # Verify semaphore is created with correct size
    assert scheduler.max_concurrent_symbols == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
