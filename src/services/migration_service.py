"""Database migration service"""

import os
from pathlib import Path
from typing import Dict, List
import asyncpg

from src.services.structured_logging import StructuredLogger

logger = StructuredLogger(__name__)


class MigrationService:
    """Manages database migrations and schema verification"""
    
    MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "database" / "migrations"
    
    def __init__(self, database_url: str):
        """
        Initialize migration service.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
    
    async def run_migrations(self) -> bool:
        """
        Execute all SQL migration files in order.
        
        Returns:
            True if all migrations executed successfully
        """
        try:
            conn = await asyncpg.connect(self.database_url)
            
            # Get all .sql files in migrations directory, sorted
            migration_files = sorted([
                f for f in self.MIGRATIONS_DIR.glob("*.sql")
                if f.is_file()
            ])
            
            if not migration_files:
                logger.warning("No migration files found", extra={
                    "migrations_dir": str(self.MIGRATIONS_DIR)
                })
                await conn.close()
                return False
            
            # Execute each migration
            for migration_file in migration_files:
                logger.info("Running migration", extra={
                    "file": migration_file.name
                })
                
                try:
                    sql_content = migration_file.read_text()
                    
                    # Execute the SQL
                    await conn.execute(sql_content)
                    
                    logger.info("Migration completed", extra={
                        "file": migration_file.name
                    })
                
                except Exception as e:
                    logger.error("Migration failed", extra={
                        "file": migration_file.name,
                        "error": str(e)
                    })
                    await conn.close()
                    return False
            
            await conn.close()
            logger.info("All migrations completed successfully")
            return True
        
        except Exception as e:
            logger.error("Migration execution error", extra={
                "error": str(e)
            })
            return False
    
    async def verify_schema(self) -> Dict[str, bool]:
        """
        Verify that all required tables exist and have correct structure.
        
        Returns:
            Dictionary mapping table name to existence boolean
        """
        required_tables = {
            'tracked_symbols': ['id', 'symbol', 'asset_class', 'active', 'timeframes'],
            'api_keys': ['id', 'key_hash', 'name', 'active'],
            'api_key_audit': ['id', 'api_key_id', 'endpoint', 'method'],
            'market_data': ['id', 'symbol', 'time', 'open', 'high', 'low', 'close', 'volume', 'timeframe']
        }
        
        results = {}
        
        try:
            conn = await asyncpg.connect(self.database_url)
            
            for table_name, required_columns in required_tables.items():
                try:
                    # Check if table exists
                    table_exists = await conn.fetchval(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables
                            WHERE table_schema = 'public'
                            AND table_name = $1
                        )
                        """,
                        table_name
                    )
                    
                    if not table_exists:
                        logger.warning("Table missing", extra={
                            "table": table_name
                        })
                        results[table_name] = False
                        continue
                    
                    # Check if all required columns exist
                    columns = await conn.fetch(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = $1
                        """,
                        table_name
                    )
                    
                    column_names = [col['column_name'] for col in columns]
                    missing_columns = [c for c in required_columns if c not in column_names]
                    
                    if missing_columns:
                        logger.warning("Columns missing", extra={
                            "table": table_name,
                            "missing": missing_columns
                        })
                        results[table_name] = False
                    else:
                        logger.info("Table verified", extra={
                            "table": table_name
                        })
                        results[table_name] = True
                
                except Exception as e:
                    logger.error("Table verification error", extra={
                        "table": table_name,
                        "error": str(e)
                    })
                    results[table_name] = False
            
            await conn.close()
            
            # Return True only if all tables are valid
            all_valid = all(results.values())
            if all_valid:
                logger.info("Schema verification passed", extra={
                    "tables_checked": len(results)
                })
            else:
                logger.warning("Schema verification failed", extra={
                    "tables_checked": len(results),
                    "valid_tables": sum(results.values())
                })
            
            return results
        
        except Exception as e:
            logger.error("Schema verification error", extra={
                "error": str(e)
            })
            return {table: False for table in required_tables.keys()}
    
    async def get_migration_status(self) -> Dict[str, any]:
        """
        Get current migration and schema status.
        
        Returns:
            Dictionary with migration information
        """
        # Get migration files
        migration_files = sorted([
            f for f in self.MIGRATIONS_DIR.glob("*.sql")
            if f.is_file()
        ])
        
        # Verify schema
        schema_status = await self.verify_schema()
        all_tables_valid = all(schema_status.values())
        
        return {
            'migration_files': [f.name for f in migration_files],
            'schema_status': schema_status,
            'all_tables_valid': all_tables_valid,
            'tables_checked': len(schema_status),
            'tables_valid': sum(schema_status.values())
        }


# Global instance holder
_migration_service = None


def init_migration_service(database_url: str) -> MigrationService:
    """Initialize global migration service"""
    global _migration_service
    _migration_service = MigrationService(database_url)
    return _migration_service


def get_migration_service() -> MigrationService:
    """Get global migration service instance"""
    if _migration_service is None:
        raise RuntimeError("Migration service not initialized. Call init_migration_service() first.")
    return _migration_service
