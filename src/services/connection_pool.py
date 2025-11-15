"""Phase 2.4: Connection pool optimization and management"""

import logging
import asyncio
from typing import Optional, Dict
from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool, StaticPool

logger = logging.getLogger(__name__)


class PoolConfig:
    """Configuration for database connection pool"""
    
    def __init__(
        self,
        pool_size: int = 20,
        max_overflow: int = 40,
        pool_recycle: int = 3600,
        pool_pre_ping: bool = True,
        echo_pool: bool = False,
        use_queuepool: bool = True
    ):
        """
        Initialize pool configuration.
        
        Args:
            pool_size: Number of connections to keep in pool (default 20)
            max_overflow: Maximum overflow connections (default 40)
            pool_recycle: Recycle connections after N seconds (default 3600/1hr)
            pool_pre_ping: Test connections before using (default True)
            echo_pool: Log pool checkout/checkin (default False)
            use_queuepool: Use QueuePool vs StaticPool (default True)
        """
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_recycle = pool_recycle
        self.pool_pre_ping = pool_pre_ping
        self.echo_pool = echo_pool
        self.use_queuepool = use_queuepool


class OptimizedConnectionPool:
    """
    Optimized connection pool with monitoring and lifecycle management.
    """
    
    def __init__(self, database_url: str, config: PoolConfig = None):
        """
        Initialize optimized connection pool.
        
        Args:
            database_url: PostgreSQL connection URL
            config: PoolConfig instance (or uses defaults)
        """
        self.database_url = database_url
        self.config = config or PoolConfig()
        self.engine = None
        self.SessionLocal = None
        self.stats: Dict = {
            "connections_created": 0,
            "connections_closed": 0,
            "pool_checkouts": 0,
            "pool_checkins": 0,
            "pool_overflows": 0,
            "pool_invalidations": 0,
        }
    
    def create_engine(self):
        """Create optimized SQLAlchemy engine"""
        # Select pool class
        if self.config.use_queuepool:
            poolclass = QueuePool
            pool_kwargs = {
                "pool_size": self.config.pool_size,
                "max_overflow": self.config.max_overflow,
            }
        else:
            poolclass = StaticPool
            pool_kwargs = {}
        
        # Create engine with optimization
        self.engine = create_engine(
            self.database_url,
            poolclass=poolclass,
            pool_recycle=self.config.pool_recycle,
            pool_pre_ping=self.config.pool_pre_ping,
            echo_pool=self.config.echo_pool,
            **pool_kwargs
        )
        
        # Attach event listeners for monitoring
        self._attach_listeners()
        
        logger.info(f"✓ Connection pool created ({self.config.pool_size} size, {self.config.max_overflow} overflow)")
        
        return self.engine
    
    def create_session_maker(self):
        """Create sessionmaker for ORM operations"""
        if not self.engine:
            self.create_engine()
        
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            autoflush=False
        )
        
        return self.SessionLocal
    
    def get_session(self) -> Session:
        """Get a new database session"""
        if not self.SessionLocal:
            self.create_session_maker()
        
        return self.SessionLocal()
    
    def _attach_listeners(self):
        """Attach SQLAlchemy event listeners for pool monitoring"""
        
        @event.listens_for(self.engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            self.stats["connections_created"] += 1
        
        @event.listens_for(self.engine, "close")
        def receive_close(dbapi_conn, connection_record):
            self.stats["connections_closed"] += 1
        
        @event.listens_for(self.engine.pool, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            self.stats["pool_checkouts"] += 1
        
        @event.listens_for(self.engine.pool, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            self.stats["pool_checkins"] += 1
        
        @event.listens_for(self.engine.pool, "overflow")
        def receive_overflow(dbapi_conn, connection_record):
            self.stats["pool_overflows"] += 1
        
        @event.listens_for(self.engine.pool, "invalidate")
        def receive_invalidate(dbapi_conn, connection_record, exception):
            self.stats["pool_invalidations"] += 1
            if exception:
                logger.warning(f"Connection invalidated due to: {exception}")
    
    def get_pool_status(self) -> Dict:
        """Get current pool status"""
        if not self.engine or not hasattr(self.engine.pool, 'size'):
            return {"status": "pool not initialized"}
        
        pool = self.engine.pool
        
        return {
            "pool_type": pool.__class__.__name__,
            "size": getattr(pool, 'size', 'N/A'),
            "checked_out": getattr(pool, 'checkedout', lambda: 'N/A')(),
            "overflow": getattr(pool, 'overflow', lambda: 'N/A')(),
            "total_connections": self.stats["connections_created"],
            "closed_connections": self.stats["connections_closed"],
            "pool_checkouts": self.stats["pool_checkouts"],
            "pool_checkins": self.stats["pool_checkins"],
            "overflow_events": self.stats["pool_overflows"],
            "invalidated_connections": self.stats["pool_invalidations"],
        }
    
    def dispose_pool(self):
        """Dispose of all connections in pool"""
        if self.engine:
            self.engine.dispose()
            logger.info("✓ Connection pool disposed")
    
    def close(self):
        """Close all connections and cleanup"""
        self.dispose_pool()
        if self.engine:
            self.engine.dispose()
            self.engine = None
            self.SessionLocal = None
            logger.info("✓ Connection pool closed")


class ConnectionHealthChecker:
    """Monitors and maintains connection pool health"""
    
    def __init__(self, pool: OptimizedConnectionPool, check_interval: int = 300):
        """
        Initialize health checker.
        
        Args:
            pool: OptimizedConnectionPool instance
            check_interval: Check interval in seconds (default 300/5min)
        """
        self.pool = pool
        self.check_interval = check_interval
        self.is_healthy = True
        self.last_check_time = None
    
    async def health_check(self) -> bool:
        """
        Check pool health by attempting a connection.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            session = self.pool.get_session()
            session.execute("SELECT 1")
            session.close()
            
            self.is_healthy = True
            logger.debug("✓ Connection pool health check passed")
            return True
        
        except Exception as e:
            self.is_healthy = False
            logger.error(f"✗ Connection pool health check failed: {e}")
            
            # Attempt recovery
            try:
                self.pool.dispose_pool()
                logger.info("Attempting pool recovery by disposing and recreating...")
            except Exception as recovery_error:
                logger.error(f"Pool recovery failed: {recovery_error}")
            
            return False
    
    async def periodic_health_check(self):
        """Periodically check pool health"""
        while True:
            await asyncio.sleep(self.check_interval)
            await self.health_check()


class PoolMetrics:
    """Collects and reports pool metrics"""
    
    def __init__(self, pool: OptimizedConnectionPool):
        self.pool = pool
    
    def get_metrics(self) -> Dict:
        """Get current pool metrics"""
        status = self.pool.get_pool_status()
        
        return {
            "timestamp": str(asyncio.get_event_loop().time()),
            "pool": status,
            "efficiency": self._calculate_efficiency(),
        }
    
    def _calculate_efficiency(self) -> Dict:
        """Calculate pool efficiency metrics"""
        stats = self.pool.stats
        
        total_transactions = stats["pool_checkouts"]
        overflows = stats["pool_overflows"]
        
        if total_transactions == 0:
            overflow_rate = 0.0
        else:
            overflow_rate = (overflows / total_transactions) * 100
        
        return {
            "overflow_rate_pct": round(overflow_rate, 2),
            "total_transactions": total_transactions,
            "overflow_events": overflows,
            "recommended_action": (
                "Consider increasing pool_size" if overflow_rate > 10 else
                "Pool size is adequate"
            )
        }
