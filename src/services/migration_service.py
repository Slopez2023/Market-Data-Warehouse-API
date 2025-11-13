"""Database migration service for schema initialization and versioning."""

import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from typing import Dict, Optional, List
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)

_migration_service: Optional['MigrationService'] = None


class MigrationService:
    """Manages database schema migrations and version control."""
    
    def __init__(self, database_url: str):
        """Initialize migration service."""
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        # Set MIGRATIONS_DIR to the database directory
        self.MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "database" / "migrations"
        if not self.MIGRATIONS_DIR.exists():
            self.MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    
    async def run_migrations(self) -> bool:
        """
        Run all pending database migrations.
        
        Returns:
            True if all migrations completed successfully, False otherwise
        """
        try:
            session = self.SessionLocal()
            try:
                # Create migration history table if it doesn't exist
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        id SERIAL PRIMARY KEY,
                        version VARCHAR(50) UNIQUE NOT NULL,
                        description TEXT,
                        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Get list of executed migrations
                executed = session.execute(
                    text("SELECT version FROM schema_migrations ORDER BY version")
                ).fetchall()
                executed_versions = {row[0] for row in executed}
                
                # Define all migrations
                migrations = [
                    ("001", "Create tracked_symbols table", self._migration_001),
                    ("002", "Create api_keys and audit tables", self._migration_002),
                    ("003", "Create market_data table", self._migration_003),
                    ("004", "Add timeframes support", self._migration_004),
                    ("005", "Create enrichment tables", self._migration_005),
                    ("006", "Create backfill state table", self._migration_006),
                    ("007", "Create validation tables", self._migration_007),
                ]
                
                # Run pending migrations
                for version, description, migration_func in migrations:
                    if version not in executed_versions:
                        logger.info(f"Running migration {version}: {description}")
                        migration_func(session)
                        session.execute(text(
                            "INSERT INTO schema_migrations (version, description) VALUES (:v, :d)"
                        ), {'v': version, 'd': description})
                
                session.commit()
                logger.info("All migrations completed successfully")
                return True
                
            except Exception as e:
                session.rollback()
                logger.error(f"Migration error: {e}")
                raise
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Failed to run migrations: {e}")
            return False
    
    async def verify_schema(self) -> Dict[str, bool]:
        """
        Verify that all required tables and columns exist.
        
        Returns:
            Dictionary with table names as keys and verification status as values
        """
        try:
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            required_tables = [
                'tracked_symbols',
                'api_keys',
                'api_key_audit',
                'market_data',
                'enrichment_fetch_log',
                'enrichment_compute_log',
                'enrichment_status',
                'data_quality_metrics',
                'backfill_state',
                'validation_log',
            ]
            
            status = {}
            for table in required_tables:
                exists = table in tables
                status[table] = exists
                if not exists:
                    logger.warning(f"Required table missing: {table}")
            
            return status
            
        except Exception as e:
            logger.error(f"Schema verification error: {e}")
            return {}
    
    async def get_migration_status(self) -> Dict:
        """
        Get detailed migration status including schema verification.
        
        Returns:
            Dictionary with migration status information
        """
        try:
            # Get list of migration files
            migration_files = []
            if self.MIGRATIONS_DIR.exists():
                migration_files = [
                    f.name for f in self.MIGRATIONS_DIR.glob("*.sql")
                ]
            
            # Get schema status - only check the 4 core tables
            inspector = inspect(self.engine)
            tables = inspector.get_table_names()
            
            core_tables = [
                'tracked_symbols',
                'api_keys',
                'api_key_audit',
                'market_data'
            ]
            
            schema_status = {table: (table in tables) for table in core_tables}
            
            # Count tables
            valid_tables = sum(1 for v in schema_status.values() if v)
            total_tables = len(schema_status)
            
            return {
                'migration_files': sorted(migration_files),
                'schema_status': schema_status,
                'all_tables_valid': all(schema_status.values()),
                'tables_checked': total_tables,
                'tables_valid': valid_tables
            }
            
        except Exception as e:
            logger.error(f"Error getting migration status: {e}")
            return {}
    
    @staticmethod
    def _migration_001(session):
        """Create tracked_symbols table."""
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS tracked_symbols (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) UNIQUE NOT NULL,
                asset_class VARCHAR(50),
                timeframes TEXT[] DEFAULT ARRAY['1h', '1d'],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
    
    @staticmethod
    def _migration_002(session):
        """Create api_keys and api_key_audit tables."""
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY,
                key_hash VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255),
                active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS api_key_audit (
                id SERIAL PRIMARY KEY,
                api_key_id INTEGER REFERENCES api_keys(id) ON DELETE CASCADE,
                endpoint VARCHAR(255),
                method VARCHAR(10),
                status_code INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
    
    @staticmethod
    def _migration_003(session):
        """Create market_data table."""
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS market_data (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL,
                timeframe VARCHAR(10) DEFAULT '1d',
                time TIMESTAMP NOT NULL,
                open DECIMAL(15,8),
                high DECIMAL(15,8),
                low DECIMAL(15,8),
                close DECIMAL(15,8),
                volume DECIMAL(20,2),
                vwap DECIMAL(15,8),
                quality_score DECIMAL(3,2),
                is_valid BOOLEAN DEFAULT FALSE,
                validation_errors TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timeframe, time)
            )
        """))
        
        # Create indexes
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time 
            ON market_data(symbol, time DESC)
        """))
        
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_market_data_symbol_timeframe 
            ON market_data(symbol, timeframe)
        """))
    
    @staticmethod
    def _migration_004(session):
        """Add timeframes support."""
        # These columns are added in migration_001 and migration_003
        # This is a placeholder for any additional timeframe-related schema changes
        pass
    
    @staticmethod
    def _migration_005(session):
        """Create enrichment tables."""
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS enrichment_fetch_log (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20),
                source VARCHAR(50),
                timeframe VARCHAR(10),
                records_fetched INT,
                records_inserted INT,
                source_response_time_ms INT,
                api_quota_remaining INT,
                success BOOLEAN,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS enrichment_compute_log (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20),
                feature_type VARCHAR(100),
                records_computed INT,
                computation_time_ms INT,
                success BOOLEAN,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS enrichment_status (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) UNIQUE,
                asset_class VARCHAR(50),
                status VARCHAR(50),
                last_enrichment_time TIMESTAMP,
                data_age_seconds INT,
                records_available INT,
                quality_score DECIMAL(3,2),
                validation_rate DECIMAL(5,2),
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
    
    @staticmethod
    def _migration_006(session):
        """Create backfill state table."""
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS backfill_state (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20),
                asset_class VARCHAR(50),
                timeframe VARCHAR(10),
                backfill_job_id UUID,
                start_date DATE,
                last_successful_date DATE,
                status VARCHAR(50),
                error_message TEXT,
                retry_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
    
    @staticmethod
    def _migration_007(session):
        """Create validation tables."""
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS validation_log (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20),
                timeframe VARCHAR(10),
                validation_passed BOOLEAN,
                validation_errors TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS data_quality_metrics (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20),
                metric_date DATE,
                total_records INT,
                validated_records INT,
                validation_rate DECIMAL(5,2),
                gaps_detected INT,
                anomalies_detected INT,
                avg_quality_score DECIMAL(3,2),
                data_completeness DECIMAL(3,2),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))


def init_migration_service(database_url: str) -> MigrationService:
    """Initialize the global migration service."""
    global _migration_service
    _migration_service = MigrationService(database_url)
    return _migration_service


def get_migration_service() -> Optional[MigrationService]:
    """Get the global migration service instance."""
    return _migration_service
