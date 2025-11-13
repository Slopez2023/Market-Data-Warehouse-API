#!/usr/bin/env python3
"""
Phase 1f: Migration Runner
Apply database schema migrations for enrichment tables
"""

import asyncio
import sys
import logging
from pathlib import Path
from typing import List, Tuple
import asyncpg
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Run database migrations"""
    
    def __init__(self, database_url: str, migrations_dir: str = None):
        """
        Initialize migration runner
        
        Args:
            database_url: PostgreSQL connection string
            migrations_dir: Directory containing .sql migration files
        """
        self.database_url = database_url
        self.migrations_dir = Path(migrations_dir) if migrations_dir else Path(__file__).parent.parent / "database" / "migrations"
        self.conn = None
        self.completed_migrations = []
        self.failed_migrations = []
    
    async def connect(self) -> bool:
        """Connect to database"""
        try:
            self.conn = await asyncpg.connect(self.database_url)
            logger.info("Connected to database")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from database"""
        if self.conn:
            await self.conn.close()
            logger.info("Disconnected from database")
    
    def get_migration_files(self) -> List[Path]:
        """Get all migration files sorted by name"""
        if not self.migrations_dir.exists():
            logger.error(f"Migrations directory not found: {self.migrations_dir}")
            return []
        
        migration_files = sorted([
            f for f in self.migrations_dir.glob("*.sql")
            if f.is_file()
        ])
        
        logger.info(f"Found {len(migration_files)} migration files")
        return migration_files
    
    async def run_migration(self, migration_file: Path) -> Tuple[bool, str]:
        """
        Run single migration
        
        Returns:
            Tuple of (success, message)
        """
        try:
            logger.info(f"Running migration: {migration_file.name}")
            
            # Read migration file
            sql_content = migration_file.read_text()
            
            if not sql_content.strip():
                return False, "Migration file is empty"
            
            # Execute migration
            try:
                await self.conn.execute(sql_content)
                logger.info(f"Migration successful: {migration_file.name}")
                return True, "Success"
            
            except asyncpg.DuplicateTableError as e:
                logger.warning(f"Table already exists (skipping): {migration_file.name}")
                return True, "Skipped - table exists"
            
            except asyncpg.DuplicateColumnError as e:
                logger.warning(f"Column already exists (skipping): {migration_file.name}")
                return True, "Skipped - column exists"
            
            except asyncpg.DuplicateIndexError as e:
                logger.warning(f"Index already exists (skipping): {migration_file.name}")
                return True, "Skipped - index exists"
            
            except Exception as e:
                error_str = str(e).lower()
                
                # Check for ownership issues
                if "must be owner of table" in error_str or "permission denied" in error_str:
                    logger.warning(f"Insufficient permissions (skipping): {migration_file.name}")
                    return True, "Skipped - permission issue"
                
                # Other errors are failures
                logger.error(f"Migration failed: {migration_file.name} - {str(e)}")
                return False, str(e)
        
        except Exception as e:
            logger.error(f"Error reading migration file {migration_file.name}: {e}")
            return False, str(e)
    
    async def run_all_migrations(self) -> bool:
        """
        Run all migrations in order
        
        Returns:
            True if all migrations succeeded
        """
        migration_files = self.get_migration_files()
        
        if not migration_files:
            logger.warning("No migration files found")
            return False
        
        logger.info(f"Starting migration run with {len(migration_files)} files")
        
        for migration_file in migration_files:
            success, message = await self.run_migration(migration_file)
            
            if success:
                self.completed_migrations.append((migration_file.name, message))
            else:
                self.failed_migrations.append((migration_file.name, message))
                logger.error(f"Migration failed - stopping: {migration_file.name}")
                return False
        
        return True
    
    async def verify_migrations(self) -> dict:
        """
        Verify that all expected tables exist
        
        Returns:
            Dict with verification results
        """
        expected_tables = {
            'backfill_state': ['id', 'symbol', 'status', 'created_at'],
            'enrichment_fetch_log': ['id', 'symbol', 'source', 'success', 'created_at'],
            'enrichment_compute_log': ['id', 'symbol', 'success', 'created_at'],
            'data_quality_metrics': ['id', 'symbol', 'metric_date', 'validation_rate'],
            'data_corrections': ['id', 'symbol', 'reason', 'created_at'],
            'enrichment_status': ['id', 'symbol', 'status', 'updated_at']
        }
        
        results = {}
        
        for table_name, required_columns in expected_tables.items():
            try:
                # Check if table exists
                table_exists = await self.conn.fetchval(
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
                    results[table_name] = {
                        'exists': False,
                        'columns': [],
                        'missing_columns': required_columns
                    }
                    logger.warning(f"Table missing: {table_name}")
                    continue
                
                # Check columns
                columns = await self.conn.fetch(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public'
                    AND table_name = $1
                    ORDER BY column_name
                    """,
                    table_name
                )
                
                column_names = [col['column_name'] for col in columns]
                missing = [c for c in required_columns if c not in column_names]
                
                results[table_name] = {
                    'exists': True,
                    'columns': column_names,
                    'missing_columns': missing,
                    'column_count': len(column_names),
                    'required_columns_present': len(missing) == 0
                }
                
                if missing:
                    logger.warning(f"Table {table_name} missing columns: {missing}")
                else:
                    logger.info(f"Table verified: {table_name}")
            
            except Exception as e:
                logger.error(f"Error verifying table {table_name}: {e}")
                results[table_name] = {
                    'exists': False,
                    'error': str(e)
                }
        
        return results
    
    def print_summary(self, verification: dict = None):
        """Print migration summary"""
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        
        print(f"\nCompleted Migrations: {len(self.completed_migrations)}")
        for migration, message in self.completed_migrations:
            print(f"  ✓ {migration} - {message}")
        
        if self.failed_migrations:
            print(f"\nFailed Migrations: {len(self.failed_migrations)}")
            for migration, message in self.failed_migrations:
                print(f"  ✗ {migration} - {message}")
        
        if verification:
            print(f"\nTable Verification:")
            all_verified = True
            for table_name, status in verification.items():
                if status.get('exists'):
                    if status.get('required_columns_present'):
                        print(f"  ✓ {table_name} ({status['column_count']} columns)")
                    else:
                        print(f"  ⚠ {table_name} - missing columns: {status['missing_columns']}")
                        all_verified = False
                else:
                    print(f"  ✗ {table_name} - table not found")
                    all_verified = False
            
            if all_verified:
                print("\n✓ All tables verified successfully")
            else:
                print("\n⚠ Some tables failed verification")
        
        print("\n" + "="*60)


async def main():
    """Main entry point"""
    # Get database URL from environment or argument
    import os
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("Error: DATABASE_URL environment variable not set")
        print("Usage: DATABASE_URL=postgresql://... python run_migrations.py")
        sys.exit(1)
    
    # Create runner
    runner = MigrationRunner(database_url)
    
    try:
        # Connect to database
        if not await runner.connect():
            print("Failed to connect to database")
            sys.exit(1)
        
        # Run all migrations
        print("Starting database migrations...")
        success = await runner.run_all_migrations()
        
        if not success:
            print("Migration failed")
            runner.print_summary()
            sys.exit(1)
        
        # Verify migrations
        print("\nVerifying database schema...")
        verification = await runner.verify_migrations()
        
        # Print summary
        runner.print_summary(verification)
        
        # Check if all tables verified
        all_verified = all(
            v.get('exists') and v.get('required_columns_present', False)
            for v in verification.values()
        )
        
        if all_verified:
            print("\n✓ All migrations completed successfully")
            sys.exit(0)
        else:
            print("\n⚠ Migrations completed but some tables failed verification")
            sys.exit(1)
    
    finally:
        await runner.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
