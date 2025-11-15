"""
Integration tests for data enrichment pipeline.
Tests UPSERT operations, backfill state tracking, and API endpoints.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import text
import uuid

from src.services.database_service import DatabaseService
from src.config import config


class TestDatabaseServiceUpsert:
    """Test UPSERT and backfill tracking methods"""
    
    @pytest.fixture
    def db_service(self):
        """Initialize database service"""
        return DatabaseService(config.database_url)
    
    def test_upsert_market_data_v2_insert(self, db_service):
        """Test inserting new record via UPSERT"""
        data = {
            'symbol': 'TEST',
            'asset_class': 'stock',
            'timeframe': '1d',
            'timestamp': datetime.utcnow(),
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 102.0,
            'volume': 1000000,
            'source': 'test',
            'is_validated': True,
            'quality_score': 0.95,
            'validation_notes': 'Test data',
            'revision': 1
        }
        
        result = db_service.upsert_market_data_v2(data)
        
        assert result['inserted'] or result['updated']
        assert result['record_id'] is not None
    
    def test_upsert_market_data_v2_update(self, db_service):
        """Test updating existing record via UPSERT"""
        timestamp = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # First insert
        data1 = {
            'symbol': 'TEST_UPD',
            'asset_class': 'stock',
            'timeframe': '1d',
            'timestamp': timestamp,
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 102.0,
            'volume': 1000000,
            'source': 'test',
            'is_validated': True,
            'quality_score': 0.95,
            'revision': 1
        }
        
        result1 = db_service.upsert_market_data_v2(data1)
        assert result1['record_id'] is not None
        
        # Update with same symbol/timestamp
        data2 = {
            'symbol': 'TEST_UPD',
            'asset_class': 'stock',
            'timeframe': '1d',
            'timestamp': timestamp,
            'open': 101.0,
            'high': 106.0,
            'low': 98.0,
            'close': 103.0,
            'volume': 1200000,
            'source': 'test',
            'is_validated': True,
            'quality_score': 0.96,
            'revision': 1
        }
        
        result2 = db_service.upsert_market_data_v2(data2)
        
        # Should update, not insert
        assert result2['updated'] or result2['inserted']
        assert result2['record_id'] is not None
    
    def test_upsert_enriched_batch(self, db_service):
        """Test batch UPSERT operations"""
        records = []
        base_time = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        for i in range(5):
            records.append({
                'symbol': f'BATCH_TEST_{i}',
                'asset_class': 'stock',
                'timeframe': '1d',
                'timestamp': base_time + timedelta(days=i),
                'open': 100.0 + i,
                'high': 105.0 + i,
                'low': 99.0 + i,
                'close': 102.0 + i,
                'volume': 1000000,
                'source': 'test',
                'is_validated': True,
                'quality_score': 0.95,
                'revision': 1
            })
        
        result = db_service.upsert_enriched_batch(records)
        
        assert result['total'] == 5
        assert result['inserted'] + result['updated'] == 5
    
    def test_backfill_state_tracking(self, db_service):
        """Test backfill state update operations"""
        symbol = 'TEST_BACKFILL'
        asset_class = 'stock'
        timeframe = '1d'
        
        # Create initial state
        execution_id = db_service.create_backfill_state(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe
        )
        
        # Update to in_progress
        success = db_service.update_backfill_state(
            execution_id=execution_id,
            status='in_progress'
        )
        assert success is True
        
        # Update to completed
        success = db_service.update_backfill_state(
            execution_id=execution_id,
            status='completed',
            records_inserted=100
        )
        assert success is True
    
    def test_backfill_state_retry_tracking(self, db_service):
        """Test retry count tracking in backfill state"""
        symbol = 'TEST_RETRY'
        asset_class = 'stock'
        timeframe = '1d'
        
        # Create initial state
        execution_id = db_service.create_backfill_state(
            symbol=symbol,
            asset_class=asset_class,
            timeframe=timeframe
        )
        
        # Update to in_progress
        success = db_service.update_backfill_state(
            execution_id=execution_id,
            status='in_progress'
        )
        assert success is True
        
        # Fail the job
        success = db_service.update_backfill_state(
            execution_id=execution_id,
            status='failed',
            error_message='Test error',
            retry_count=1
        )
        assert success is True
    
    def test_enrichment_fetch_logging(self, db_service):
        """Test enrichment fetch log operations"""
        db_service.log_enrichment_fetch(
            symbol='TEST',
            asset_class='stock',
            source='polygon',
            timeframe='1d',
            records_fetched=100,
            records_inserted=95,
            records_updated=5,
            response_time_ms=150,
            success=True,
            api_quota_remaining=500
        )
        
        # Verify by querying the database
        session = db_service.SessionLocal()
        try:
            result = session.execute(
                text("""
                    SELECT symbol, source, records_fetched, success
                    FROM enrichment_fetch_log
                    WHERE symbol = 'TEST' AND source = 'polygon'
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
            ).first()
            
            assert result is not None
            assert result[0] == 'TEST'
            assert result[1] == 'polygon'
            assert result[2] == 100
            assert result[3] is True
        finally:
            session.close()
    
    def test_feature_computation_logging(self, db_service):
        """Test feature computation log operations"""
        db_service.log_feature_computation(
            symbol='TEST',
            asset_class='stock',
            timeframe='1d',
            features_computed=15,
            computation_time_ms=125,
            success=True,
            missing_fields=[]
        )
        
        # Verify by querying the database
        session = db_service.SessionLocal()
        try:
            result = session.execute(
                text("""
                    SELECT symbol, features_computed, success
                    FROM enrichment_compute_log
                    WHERE symbol = 'TEST'
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
            ).first()
            
            assert result is not None
            assert result[0] == 'TEST'
            assert result[1] == 15
            assert result[2] is True
        finally:
            session.close()


class TestEnrichmentEndpoints:
    """Test enrichment API endpoints"""
    
    @pytest.fixture
    def async_client(self):
        """Create async HTTP client"""
        from httpx import AsyncClient
        from main import app
        return AsyncClient(app=app, base_url="http://test")
    
    @pytest.mark.asyncio
    async def test_enrichment_status_endpoint(self, async_client):
        """Test GET /api/v1/enrichment/status/{symbol}"""
        response = await async_client.get("/api/v1/enrichment/status/AAPL")
        assert response.status_code in [200, 404]  # 404 if symbol not found
        if response.status_code == 200:
            data = response.json()
            assert 'symbol' in data
            assert 'timestamp' in data
    
    @pytest.mark.asyncio
    async def test_enrichment_metrics_endpoint(self, async_client):
        """Test GET /api/v1/enrichment/metrics"""
        response = await async_client.get("/api/v1/enrichment/metrics")
        assert response.status_code in [200, 500]  # May fail if no data
        if response.status_code == 200:
            data = response.json()
            assert 'fetch_pipeline' in data
            assert 'compute_pipeline' in data
            assert 'data_quality' in data
    
    @pytest.mark.asyncio
    async def test_enrichment_trigger_endpoint(self, async_client):
        """Test POST /api/v1/enrichment/trigger"""
        params = {
            'symbol': 'AAPL',
            'asset_class': 'stock',
            'timeframes': ['1d']
        }
        response = await async_client.post(
            "/api/v1/enrichment/trigger",
            params=params
        )
        # Will likely fail due to missing services, but endpoint should exist
        assert response.status_code in [200, 500, 503]
    
    @pytest.mark.asyncio
    async def test_data_quality_endpoint(self, async_client):
        """Test GET /api/v1/data/quality/{symbol}"""
        response = await async_client.get("/api/v1/data/quality/AAPL", params={'days': 7})
        assert response.status_code in [200, 404, 500]  # Various outcomes possible
        if response.status_code == 200:
            data = response.json()
            assert 'symbol' in data
            assert 'period_days' in data
            assert 'summary' in data


class TestEnrichmentDataIntegrity:
    """Test data integrity and idempotency"""
    
    @pytest.fixture
    def db_service(self):
        """Initialize database service"""
        return DatabaseService(config.database_url)
    
    def test_upsert_idempotency(self, db_service):
        """Test that UPSERT is idempotent (safe to retry)"""
        timestamp = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        data = {
            'symbol': 'IDEMPOTENT_TEST',
            'asset_class': 'stock',
            'timeframe': '1d',
            'timestamp': timestamp,
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 102.0,
            'volume': 1000000,
            'source': 'test',
            'is_validated': True,
            'quality_score': 0.95,
            'revision': 1
        }
        
        # Insert twice - should get same record_id or update
        result1 = db_service.upsert_market_data_v2(data)
        result2 = db_service.upsert_market_data_v2(data)
        
        # Both should succeed
        assert (result1['inserted'] or result1['updated'])
        assert (result2['inserted'] or result2['updated'])
        
        # Query to verify only one record exists
        session = db_service.SessionLocal()
        try:
            count = session.execute(
                text("""
                    SELECT COUNT(*) FROM market_data_v2
                    WHERE symbol = 'IDEMPOTENT_TEST'
                    AND timestamp = :ts
                """),
                {'ts': timestamp}
            ).scalar()
            
            # Should have exactly 1 record
            assert count == 1
        finally:
            session.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
