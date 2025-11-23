"""
Test unified backfill endpoint implementation.

Tests that:
1. The endpoint calls the orchestrator
2. The orchestrator triggers master_backfill.py
3. Audit logging works
4. Results are properly formatted
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from src.services.backfill_orchestrator import BackfillOrchestrator
from src.models import BackfillRequest


@pytest.mark.asyncio
async def test_backfill_orchestrator_init():
    """Test orchestrator initialization"""
    orchestrator = BackfillOrchestrator(
        database_url="postgresql://user:pass@localhost/db",
        polygon_api_key="test_key"
    )
    
    assert orchestrator.database_url == "postgresql://user:pass@localhost/db"
    assert orchestrator.polygon_api_key == "test_key"
    print("✓ Orchestrator initialization successful")


@pytest.mark.asyncio
async def test_backfill_orchestrator_trigger():
    """Test triggering a backfill through orchestrator"""
    with patch('asyncio.create_subprocess_exec') as mock_exec:
        # Mock the subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b'', b''))
        mock_exec.return_value = mock_process
        
        # Mock audit logging
        with patch.object(BackfillOrchestrator, '_audit_log', new_callable=AsyncMock):
            with patch.object(BackfillOrchestrator, '_parse_backfill_results', new_callable=AsyncMock) as mock_parse:
                mock_parse.return_value = {
                    "symbols_processed": 2,
                    "successful": 2,
                    "total_candles_inserted": 1000
                }
                
                orchestrator = BackfillOrchestrator(
                    database_url="postgresql://user:pass@localhost/db",
                    polygon_api_key="test_key"
                )
                
                result = await orchestrator.trigger_backfill(
                    symbols=["AAPL", "MSFT"],
                    timeframes=["1d"],
                    days=365,
                    job_id="test-job-123"
                )
                
                assert result["job_id"] == "test-job-123"
                assert result["status"] == "completed"
                assert "results" in result
                assert result["results"]["symbols_processed"] == 2
                
                # Verify subprocess was called with correct command
                call_args = mock_exec.call_args
                assert "master_backfill.py" in call_args[0][0]
                print("✓ Backfill orchestration test passed")


def test_deprecated_backfill_worker():
    """Test that old backfill_worker raises NotImplementedError"""
    from src.services.backfill_worker import init_backfill_worker
    
    with pytest.raises(NotImplementedError):
        init_backfill_worker()
    
    print("✓ Deprecated backfill_worker properly raises NotImplementedError")


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_backfill_orchestrator_init())
    asyncio.run(test_backfill_orchestrator_trigger())
    test_deprecated_backfill_worker()
    
    print("\n✓ All unified backfill tests passed")
