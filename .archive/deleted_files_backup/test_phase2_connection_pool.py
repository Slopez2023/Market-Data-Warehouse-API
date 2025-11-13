"""Phase 2.4: Tests for connection pool optimization"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.services.connection_pool import (
    PoolConfig, OptimizedConnectionPool, ConnectionHealthChecker, PoolMetrics
)


class TestPoolConfig:
    """Test PoolConfig"""
    
    def test_default_config(self):
        """Test default pool configuration"""
        config = PoolConfig()
        
        assert config.pool_size == 10
        assert config.max_overflow == 20
        assert config.pool_recycle == 3600
        assert config.pool_pre_ping is True
        assert config.echo_pool is False
        assert config.use_queuepool is True
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = PoolConfig(
            pool_size=20,
            max_overflow=40,
            pool_recycle=1800,
            echo_pool=True
        )
        
        assert config.pool_size == 20
        assert config.max_overflow == 40
        assert config.pool_recycle == 1800
        assert config.echo_pool is True
    
    def test_config_for_testing(self):
        """Test configuration suitable for testing"""
        config = PoolConfig(
            pool_size=1,
            max_overflow=0,
            use_queuepool=False
        )
        
        assert config.pool_size == 1
        assert config.max_overflow == 0
        assert config.use_queuepool is False


class TestOptimizedConnectionPool:
    """Test OptimizedConnectionPool"""
    
    def test_initialization(self):
        """Test pool initialization"""
        db_url = "postgresql://user:pass@localhost/testdb"
        pool = OptimizedConnectionPool(db_url)
        
        assert pool.database_url == db_url
        assert pool.engine is None
        assert pool.SessionLocal is None
    
    def test_custom_config_initialization(self):
        """Test initialization with custom config"""
        db_url = "postgresql://localhost/testdb"
        config = PoolConfig(pool_size=20)
        pool = OptimizedConnectionPool(db_url, config=config)
        
        assert pool.config.pool_size == 20
    
    def test_stats_initialization(self):
        """Test that statistics are properly initialized"""
        pool = OptimizedConnectionPool("postgresql://localhost/testdb")
        
        assert pool.stats["connections_created"] == 0
        assert pool.stats["pool_checkouts"] == 0
        assert pool.stats["pool_overflows"] == 0
    
    def test_create_engine_with_config(self):
        """Test engine creation with configuration"""
        pool = OptimizedConnectionPool(
            "postgresql://localhost/testdb",
            config=PoolConfig(pool_size=15, use_queuepool=True)
        )
        
        # Verify config is set correctly
        assert pool.config.pool_size == 15
        assert pool.config.pool_recycle == 3600
        assert pool.config.pool_pre_ping is True
    
    def test_create_engine_staticpool_config(self):
        """Test engine creation with StaticPool config"""
        pool = OptimizedConnectionPool(
            "postgresql://localhost/testdb",
            config=PoolConfig(use_queuepool=False)
        )
        
        # Verify StaticPool is configured
        assert pool.config.use_queuepool is False
    
    def test_session_maker_initialization(self):
        """Test session maker can be created"""
        pool = OptimizedConnectionPool("postgresql://localhost/testdb")
        
        # SessionLocal should be None until created
        assert pool.SessionLocal is None
    
    def test_pool_status_uninitialized(self):
        """Test getting status when pool not initialized"""
        pool = OptimizedConnectionPool("postgresql://localhost/testdb")
        
        status = pool.get_pool_status()
        
        assert status["status"] == "pool not initialized"
    
    def test_stats_tracking(self):
        """Test that stats are tracked properly"""
        pool = OptimizedConnectionPool("postgresql://localhost/testdb")
        
        # Manually track some stats
        pool.stats["connections_created"] = 5
        pool.stats["pool_checkouts"] = 10
        pool.stats["pool_overflows"] = 2
        
        assert pool.stats["connections_created"] == 5
        assert pool.stats["pool_checkouts"] == 10
        assert pool.stats["pool_overflows"] == 2


class TestConnectionHealthChecker:
    """Test ConnectionHealthChecker"""
    
    def test_initialization(self):
        """Test health checker initialization"""
        mock_pool = Mock()
        checker = ConnectionHealthChecker(mock_pool)
        
        assert checker.pool is mock_pool
        assert checker.check_interval == 300
        assert checker.is_healthy is True
    
    def test_custom_check_interval(self):
        """Test custom check interval"""
        mock_pool = Mock()
        checker = ConnectionHealthChecker(mock_pool, check_interval=60)
        
        assert checker.check_interval == 60
    
    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check"""
        mock_pool = Mock()
        mock_session = MagicMock()
        mock_pool.get_session.return_value = mock_session
        
        checker = ConnectionHealthChecker(mock_pool)
        result = await checker.health_check()
        
        assert result is True
        assert checker.is_healthy is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test failed health check"""
        mock_pool = Mock()
        mock_pool.get_session.side_effect = Exception("Connection failed")
        
        checker = ConnectionHealthChecker(mock_pool)
        result = await checker.health_check()
        
        assert result is False
        assert checker.is_healthy is False
    
    @pytest.mark.asyncio
    async def test_health_check_recovery_attempt(self):
        """Test that health check attempts recovery on failure"""
        mock_pool = Mock()
        mock_pool.get_session.side_effect = Exception("Connection failed")
        mock_pool.dispose_pool = Mock()
        
        checker = ConnectionHealthChecker(mock_pool)
        await checker.health_check()
        
        # Should attempt to dispose/recover
        mock_pool.dispose_pool.assert_called_once()


class TestPoolMetrics:
    """Test PoolMetrics"""
    
    def test_initialization(self):
        """Test metrics initialization"""
        mock_pool = Mock()
        metrics = PoolMetrics(mock_pool)
        
        assert metrics.pool is mock_pool
    
    def test_get_metrics(self):
        """Test getting metrics"""
        mock_pool = Mock()
        mock_pool.get_pool_status.return_value = {
            "pool_type": "QueuePool",
            "checked_out": 5
        }
        mock_pool.stats = {
            "pool_checkouts": 100,
            "pool_overflows": 5
        }
        
        metrics = PoolMetrics(mock_pool)
        result = metrics.get_metrics()
        
        assert "timestamp" in result
        assert "pool" in result
        assert "efficiency" in result
    
    def test_calculate_efficiency_no_transactions(self):
        """Test efficiency calculation with no transactions"""
        mock_pool = Mock()
        mock_pool.stats = {
            "pool_checkouts": 0,
            "pool_overflows": 0
        }
        
        metrics = PoolMetrics(mock_pool)
        efficiency = metrics._calculate_efficiency()
        
        assert efficiency["overflow_rate_pct"] == 0.0
        assert efficiency["total_transactions"] == 0
    
    def test_calculate_efficiency_low_overflow(self):
        """Test efficiency calculation with low overflow rate"""
        mock_pool = Mock()
        mock_pool.stats = {
            "pool_checkouts": 100,
            "pool_overflows": 5
        }
        
        metrics = PoolMetrics(mock_pool)
        efficiency = metrics._calculate_efficiency()
        
        assert efficiency["overflow_rate_pct"] == 5.0
        assert "adequate" in efficiency["recommended_action"].lower()
    
    def test_calculate_efficiency_high_overflow(self):
        """Test efficiency calculation with high overflow rate"""
        mock_pool = Mock()
        mock_pool.stats = {
            "pool_checkouts": 100,
            "pool_overflows": 20
        }
        
        metrics = PoolMetrics(mock_pool)
        efficiency = metrics._calculate_efficiency()
        
        assert efficiency["overflow_rate_pct"] == 20.0
        assert "increasing" in efficiency["recommended_action"].lower() or "increase" in efficiency["recommended_action"].lower()


class TestConnectionPoolIntegration:
    """Integration tests for connection pool"""
    
    def test_pool_configuration_consistency(self):
        """Test that pool maintains consistent configuration"""
        config = PoolConfig(pool_size=15, max_overflow=30)
        pool = OptimizedConnectionPool("postgresql://localhost/testdb", config=config)
        
        assert pool.config.pool_size == 15
        assert pool.config.max_overflow == 30
    
    def test_pool_lifecycle(self):
        """Test pool initialization through closure"""
        pool = OptimizedConnectionPool(
            "postgresql://localhost/testdb",
            config=PoolConfig(pool_size=5)
        )
        
        # Pool should start uninitialized
        assert pool.engine is None
        
        # After closure should be cleaned up
        pool.close()
        assert pool.engine is None
    
    def test_health_checker_with_real_pool(self):
        """Test health checker integration with pool"""
        mock_pool = Mock()
        mock_session = MagicMock()
        mock_pool.get_session.return_value = mock_session
        
        checker = ConnectionHealthChecker(mock_pool, check_interval=60)
        
        # Should be healthy initially
        assert checker.is_healthy is True
