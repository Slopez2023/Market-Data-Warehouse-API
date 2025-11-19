"""
Test the 4 new monitoring dashboard endpoints
"""
import pytest
import asyncio
from httpx import AsyncClient
from main import app
import json


@pytest.mark.asyncio
async def test_enrichment_dashboard_overview():
    """Test GET /api/v1/enrichment/dashboard/overview"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/enrichment/dashboard/overview")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "scheduler_status" in data
        assert "last_run" in data
        assert "next_run" in data
        assert "success_rate" in data
        assert "symbols_enriched" in data
        assert "total_symbols" in data
        assert "avg_enrichment_time_seconds" in data
        assert "recent_errors" in data
        assert "timestamp" in data
        
        # Verify value types
        assert isinstance(data["scheduler_status"], str)
        assert data["scheduler_status"] in ["running", "stopped"]
        assert isinstance(data["success_rate"], (int, float))
        assert isinstance(data["symbols_enriched"], int)


@pytest.mark.asyncio
async def test_enrichment_dashboard_metrics():
    """Test GET /api/v1/enrichment/dashboard/metrics"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/enrichment/dashboard/metrics")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "fetch_pipeline" in data
        assert "compute_pipeline" in data
        assert "data_quality" in data
        assert "symbol_health" in data
        assert "last_24h" in data
        assert "timestamp" in data
        
        # Verify fetch pipeline
        fetch = data["fetch_pipeline"]
        assert "total_jobs" in fetch
        assert "success_rate" in fetch
        assert "avg_job_duration_seconds" in fetch
        assert "total_records_fetched" in fetch
        
        # Verify compute pipeline
        compute = data["compute_pipeline"]
        assert "total_computations" in compute
        assert "success_rate" in compute
        assert "avg_computation_time_ms" in compute
        assert "total_features_computed" in compute
        
        # Verify symbol health
        health = data["symbol_health"]
        assert "healthy" in health
        assert "warning" in health
        assert "stale" in health
        assert "error" in health
        assert "total" in health


@pytest.mark.asyncio
async def test_enrichment_history():
    """Test GET /api/v1/enrichment/history"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test default limit
        response = await client.get("/api/v1/enrichment/history")
        assert response.status_code == 200
        data = response.json()
        
        assert "jobs" in data
        assert "count" in data
        assert "timestamp" in data
        assert isinstance(data["jobs"], list)
        
        # Test with custom limit
        response = await client.get("/api/v1/enrichment/history?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) <= 5
        
        # Verify job structure (if jobs exist)
        if data["jobs"]:
            job = data["jobs"][0]
            assert "symbol" in job
            assert "status" in job
            assert "records_fetched" in job
            assert "records_inserted" in job
            assert "response_time_ms" in job
            assert "created_at" in job
            assert job["status"] in ["success", "failed"]


@pytest.mark.asyncio
async def test_enrichment_dashboard_health():
    """Test GET /api/v1/enrichment/dashboard/health"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/enrichment/dashboard/health")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "scheduler" in data
        assert "database" in data
        assert "api_connectivity" in data
        assert "recent_failures_24h" in data
        assert "failure_rate_percent" in data
        assert "last_health_check" in data
        
        # Verify health values
        for health_key in ["scheduler", "database", "api_connectivity"]:
            assert data[health_key] in ["healthy", "degraded", "critical", "unknown"]
        
        assert isinstance(data["recent_failures_24h"], int)
        assert isinstance(data["failure_rate_percent"], (int, float))


@pytest.mark.asyncio
async def test_enrichment_history_validation():
    """Test enrichment history parameter validation"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test max limit
        response = await client.get("/api/v1/enrichment/history?limit=100")
        assert response.status_code == 200
        
        # Test over limit (should be capped at 100)
        response = await client.get("/api/v1/enrichment/history?limit=200")
        # This should either return 200 (with limit capped) or 422 (validation error)
        # depending on FastAPI validation config
        assert response.status_code in [200, 422]
        
        # Test min limit
        response = await client.get("/api/v1/enrichment/history?limit=1")
        assert response.status_code == 200


if __name__ == "__main__":
    # Run tests with: pytest test_monitoring_endpoints.py -v
    pytest.main([__file__, "-v"])
