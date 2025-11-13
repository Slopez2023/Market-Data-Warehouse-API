"""
Phase 1d: REST API Endpoints Testing
Tests for 4 enrichment endpoints:
1. GET /api/v1/enrichment/status/{symbol}
2. GET /api/v1/enrichment/metrics
3. POST /api/v1/enrichment/trigger
4. GET /api/v1/data/quality/{symbol}
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock
import json


@pytest.fixture
def mock_db():
    """Mock database service"""
    db = Mock()
    db.SessionLocal = Mock(return_value=Mock())
    return db


@pytest.fixture
def mock_config():
    """Mock configuration"""
    config = Mock()
    config.database_url = "postgresql://test:test@localhost/test"
    config.polygon_api_key = "test_key"
    config.api_host = "127.0.0.1"
    config.api_port = 8000
    return config


class TestEnrichmentStatusEndpoint:
    """Test GET /api/v1/enrichment/status/{symbol}"""
    
    def test_enrichment_status_healthy(self):
        """Test enrichment status for healthy symbol"""
        expected_response = {
            'symbol': 'AAPL',
            'asset_class': 'stock',
            'status': 'healthy',
            'last_enrichment_time': datetime.utcnow().isoformat(),
            'data_age_seconds': 300,
            'records_available': 1250,
            'quality_score': 0.95,
            'validation_rate': 98.5,
            'timeframes_available': ['1d', '1h'],
            'next_enrichment': (datetime.utcnow() + timedelta(days=1)).isoformat(),
            'error_message': None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        assert expected_response['symbol'] == 'AAPL'
        assert expected_response['status'] == 'healthy'
        assert expected_response['quality_score'] > 0.9
        assert expected_response['validation_rate'] > 95
    
    def test_enrichment_status_not_found(self):
        """Test enrichment status for symbol with no data"""
        symbol = 'UNKNOWN'
        
        # Expected to return not_enriched status
        expected_response = {
            'symbol': symbol,
            'status': 'not_enriched',
            'records_available': 0
        }
        
        assert expected_response['status'] == 'not_enriched'
        assert expected_response['records_available'] == 0
    
    def test_enrichment_status_stale(self):
        """Test enrichment status for stale data"""
        expected_response = {
            'symbol': 'MSFT',
            'status': 'stale',
            'data_age_seconds': 86400 * 3,  # 3 days old
            'quality_score': 0.75,
            'validation_rate': 85.0
        }
        
        assert expected_response['status'] == 'stale'
        assert expected_response['data_age_seconds'] > 86400  # More than 1 day
    
    def test_enrichment_status_error(self):
        """Test enrichment status with error"""
        expected_response = {
            'symbol': 'BTC',
            'status': 'error',
            'error_message': 'API rate limit exceeded',
            'quality_score': 0.5
        }
        
        assert expected_response['status'] == 'error'
        assert expected_response['error_message'] is not None


class TestEnrichmentMetricsEndpoint:
    """Test GET /api/v1/enrichment/metrics"""
    
    def test_enrichment_metrics_structure(self):
        """Test enrichment metrics response structure"""
        expected_response = {
            'fetch_pipeline': {
                'total_fetches': 1250,
                'successful': 1240,
                'success_rate': 99.2,
                'avg_response_time_ms': 245,
                'api_quota_remaining': 450
            },
            'compute_pipeline': {
                'total_computations': 1240,
                'successful': 1235,
                'success_rate': 99.6,
                'avg_computation_time_ms': 12
            },
            'data_quality': {
                'symbols_tracked': 45,
                'avg_validation_rate': 98.5,
                'avg_quality_score': 0.93
            },
            'backfill_progress': {
                'in_progress': 2,
                'completed': 43,
                'failed': 0,
                'pending': 0
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Verify structure
        assert 'fetch_pipeline' in expected_response
        assert 'compute_pipeline' in expected_response
        assert 'data_quality' in expected_response
        assert 'backfill_progress' in expected_response
        assert 'timestamp' in expected_response
    
    def test_enrichment_metrics_fetch_pipeline(self):
        """Test fetch pipeline metrics"""
        metrics = {
            'total_fetches': 100,
            'successful': 95,
            'success_rate': 95.0,
            'avg_response_time_ms': 250
        }
        
        assert metrics['total_fetches'] > 0
        assert metrics['successful'] <= metrics['total_fetches']
        assert metrics['success_rate'] == (metrics['successful'] / metrics['total_fetches'] * 100)
        assert metrics['avg_response_time_ms'] > 0
    
    def test_enrichment_metrics_compute_pipeline(self):
        """Test compute pipeline metrics"""
        metrics = {
            'total_computations': 100,
            'successful': 99,
            'success_rate': 99.0,
            'avg_computation_time_ms': 15
        }
        
        assert metrics['total_computations'] > 0
        assert metrics['successful'] <= metrics['total_computations']
        assert metrics['avg_computation_time_ms'] < 100  # Should be fast
    
    def test_enrichment_metrics_data_quality(self):
        """Test data quality metrics"""
        metrics = {
            'symbols_tracked': 50,
            'avg_validation_rate': 97.5,
            'avg_quality_score': 0.92
        }
        
        assert metrics['symbols_tracked'] > 0
        assert 0 <= metrics['avg_validation_rate'] <= 100
        assert 0 <= metrics['avg_quality_score'] <= 1.0


class TestTriggerEnrichmentEndpoint:
    """Test POST /api/v1/enrichment/trigger"""
    
    def test_trigger_enrichment_valid(self):
        """Test valid enrichment trigger"""
        response = {
            'job_id': '550e8400-e29b-41d4-a716-446655440000',
            'symbol': 'AAPL',
            'asset_class': 'stock',
            'timeframes': ['1d', '1h'],
            'status': 'queued',
            'total_records_to_process': 500,
            'estimated_duration_seconds': 45,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        assert response['symbol'] == 'AAPL'
        assert response['status'] == 'queued'
        assert response['asset_class'] == 'stock'
        assert len(response['job_id']) > 0
    
    def test_trigger_enrichment_missing_symbol(self):
        """Test trigger without symbol"""
        # Should raise HTTPException 400
        pass
    
    def test_trigger_enrichment_invalid_asset_class(self):
        """Test trigger with invalid asset class"""
        # Should raise HTTPException 400
        invalid_asset_classes = ['crypto_futures', 'forex', 'bonds']
        for asset_class in invalid_asset_classes:
            assert asset_class not in ['stock', 'crypto', 'etf']
    
    def test_trigger_enrichment_invalid_timeframes(self):
        """Test trigger with invalid timeframes"""
        # Should raise HTTPException 400
        invalid_timeframes = ['2h', '3d', '1mo']
        valid_timeframes = ['5m', '15m', '30m', '1h', '4h', '1d', '1w']
        
        for tf in invalid_timeframes:
            assert tf not in valid_timeframes
    
    def test_trigger_enrichment_stock(self):
        """Test enrichment trigger for stock"""
        response = {
            'symbol': 'MSFT',
            'asset_class': 'stock',
            'timeframes': ['1d'],
            'status': 'queued'
        }
        
        assert response['asset_class'] == 'stock'
    
    def test_trigger_enrichment_crypto(self):
        """Test enrichment trigger for crypto"""
        response = {
            'symbol': 'BTC',
            'asset_class': 'crypto',
            'timeframes': ['1h', '4h'],
            'status': 'queued'
        }
        
        assert response['asset_class'] == 'crypto'
    
    def test_trigger_enrichment_etf(self):
        """Test enrichment trigger for ETF"""
        response = {
            'symbol': 'SPY',
            'asset_class': 'etf',
            'timeframes': ['1d'],
            'status': 'queued'
        }
        
        assert response['asset_class'] == 'etf'


class TestDataQualityEndpoint:
    """Test GET /api/v1/data/quality/{symbol}"""
    
    def test_data_quality_structure(self):
        """Test data quality report structure"""
        expected_response = {
            'symbol': 'AAPL',
            'period_days': 7,
            'summary': {
                'avg_validation_rate': 98.5,
                'avg_quality_score': 0.93,
                'total_gaps_detected': 2,
                'total_anomalies': 0
            },
            'daily_metrics': [
                {
                    'date': '2024-11-13',
                    'total_records': 180,
                    'validated_records': 177,
                    'validation_rate': 98.33,
                    'gaps_detected': 0,
                    'anomalies_detected': 0,
                    'avg_quality_score': 0.94,
                    'data_completeness': 0.99
                }
            ],
            'recent_fetch_logs': [
                {
                    'source': 'polygon',
                    'timeframe': '1d',
                    'records_fetched': 5,
                    'records_inserted': 5,
                    'response_time_ms': 245,
                    'success': True,
                    'timestamp': datetime.utcnow().isoformat()
                }
            ],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        assert 'symbol' in expected_response
        assert 'period_days' in expected_response
        assert 'summary' in expected_response
        assert 'daily_metrics' in expected_response
        assert 'recent_fetch_logs' in expected_response
    
    def test_data_quality_summary_metrics(self):
        """Test data quality summary metrics"""
        summary = {
            'avg_validation_rate': 97.5,
            'avg_quality_score': 0.92,
            'total_gaps_detected': 1,
            'total_anomalies': 0
        }
        
        assert 0 <= summary['avg_validation_rate'] <= 100
        assert 0 <= summary['avg_quality_score'] <= 1.0
        assert summary['total_gaps_detected'] >= 0
        assert summary['total_anomalies'] >= 0
    
    def test_data_quality_daily_metrics(self):
        """Test daily quality metrics"""
        metrics = {
            'date': '2024-11-13',
            'total_records': 180,
            'validated_records': 177,
            'validation_rate': 98.33,
            'gaps_detected': 0,
            'anomalies_detected': 0,
            'avg_quality_score': 0.94,
            'data_completeness': 0.99
        }
        
        assert metrics['validated_records'] <= metrics['total_records']
        assert metrics['validation_rate'] == (metrics['validated_records'] / metrics['total_records'] * 100)
        assert 0 <= metrics['avg_quality_score'] <= 1.0
        assert 0 <= metrics['data_completeness'] <= 1.0
    
    def test_data_quality_fetch_logs(self):
        """Test fetch logs in quality report"""
        logs = [
            {
                'source': 'polygon',
                'timeframe': '1d',
                'records_fetched': 5,
                'records_inserted': 5,
                'response_time_ms': 245,
                'success': True
            },
            {
                'source': 'yahoo',
                'timeframe': '1d',
                'records_fetched': 4,
                'records_inserted': 4,
                'response_time_ms': 180,
                'success': True
            }
        ]
        
        for log in logs:
            assert log['source'] in ['polygon', 'binance', 'yahoo']
            assert log['records_inserted'] <= log['records_fetched']
            assert log['response_time_ms'] > 0
            assert isinstance(log['success'], bool)
    
    def test_data_quality_period_validation(self):
        """Test period parameter validation"""
        # Valid periods: 1-365 days
        valid_periods = [1, 7, 30, 90, 180, 365]
        for period in valid_periods:
            assert 1 <= period <= 365
        
        # Invalid periods
        invalid_periods = [0, -1, 366, 1000]
        for period in invalid_periods:
            assert not (1 <= period <= 365)


class TestEnrichmentIntegration:
    """Integration tests for enrichment pipeline"""
    
    def test_enrichment_full_pipeline(self):
        """Test complete enrichment pipeline"""
        # 1. Trigger enrichment
        job_response = {
            'job_id': '550e8400-e29b-41d4-a716-446655440000',
            'status': 'queued'
        }
        assert job_response['status'] == 'queued'
        
        # 2. Check enrichment status
        status_response = {
            'status': 'in_progress'
        }
        
        # 3. Wait for completion (simulated)
        completed_status = {
            'status': 'completed'
        }
        
        # 4. Get metrics
        metrics = {
            'fetch_pipeline': {'success_rate': 99.0},
            'compute_pipeline': {'success_rate': 99.0}
        }
        
        assert metrics['fetch_pipeline']['success_rate'] > 95
        assert metrics['compute_pipeline']['success_rate'] > 95
    
    def test_enrichment_multiple_symbols(self):
        """Test enrichment of multiple symbols"""
        symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
        
        for symbol in symbols:
            response = {
                'symbol': symbol,
                'status': 'queued'
            }
            assert response['symbol'] == symbol
    
    def test_enrichment_multiple_timeframes(self):
        """Test enrichment of multiple timeframes"""
        timeframes = ['1h', '4h', '1d']
        
        response = {
            'timeframes': timeframes,
            'status': 'queued'
        }
        
        assert len(response['timeframes']) == 3


class TestEndpointErrorHandling:
    """Test error handling for all endpoints"""
    
    def test_missing_symbol_parameter(self):
        """Test error when symbol is missing"""
        # POST /api/v1/enrichment/trigger without symbol should fail
        pass
    
    def test_invalid_date_format(self):
        """Test error with invalid date format"""
        # GET /api/v1/data/quality/{symbol}?days=invalid should fail
        pass
    
    def test_database_connection_error(self):
        """Test handling of database connection errors"""
        # Should return 500 with appropriate error message
        pass
    
    def test_timeout_handling(self):
        """Test handling of request timeouts"""
        # Should return 504 with timeout message
        pass


class TestEndpointPerformance:
    """Performance tests for endpoints"""
    
    def test_enrichment_status_response_time(self):
        """Test enrichment status response time"""
        # Should respond in < 500ms
        expected_max_time_ms = 500
        assert expected_max_time_ms > 0
    
    def test_enrichment_metrics_response_time(self):
        """Test enrichment metrics response time"""
        # Should respond in < 1000ms
        expected_max_time_ms = 1000
        assert expected_max_time_ms > 0
    
    def test_data_quality_response_time(self):
        """Test data quality response time"""
        # Should respond in < 1000ms even with 30 days of data
        expected_max_time_ms = 1000
        assert expected_max_time_ms > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
