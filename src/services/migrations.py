"""Database migration runner."""

import logging
import os
from pathlib import Path
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def run_migrations(database_url: str) -> None:
    """Run all SQL migrations from the database directory."""
    try:
        # Create engine
        engine = create_engine(database_url)
        
        # Get migration directory
        db_dir = Path(__file__).parent.parent.parent / "database"
        
        if not db_dir.exists():
            logger.warning(f"Database migration directory not found: {db_dir}")
            return
        
        # Get all migration files sorted by number
        migration_files = sorted(db_dir.glob("*.sql"))
        
        if not migration_files:
            logger.warning("No migration files found")
            return
        
        logger.info(f"Running {len(migration_files)} migration(s)")
        
        for migration_file in migration_files:
            try:
                logger.info(f"Running migration: {migration_file.name}")
                
                # Read SQL file
                with open(migration_file, 'r') as f:
                    sql_content = f.read()
                
                # Execute migrations
                with engine.connect() as conn:
                    # Split by semicolon and execute each statement
                    statements = [s.strip() for s in sql_content.split(';') if s.strip()]
                    for statement in statements:
                        conn.execute(text(statement))
                    conn.commit()
                
                logger.info(f"✓ Completed: {migration_file.name}")
                
            except Exception as e:
                logger.error(f"✗ Failed migration {migration_file.name}: {e}")
                # Continue with other migrations
        
        logger.info("All migrations completed")
        
    except Exception as e:
        logger.error(f"Migration runner failed: {e}")
        raise
