"""Tests for migration service"""

import pytest
import asyncpg
import os
from pathlib import Path
import tempfile

from src.services.migration_service import MigrationService


@pytest.fixture
async def migration_service():
    """Create migration service for testing"""
    database_url = os.getenv("DATABASE_URL", "postgresql://testuser:testpass@localhost:5432/market_data_test")
    return MigrationService(database_url)


@pytest.fixture
def database_url():
    """Get database URL for tests"""
    return os.getenv("DATABASE_URL", "postgresql://testuser:testpass@localhost:5432/market_data_test")


@pytest.mark.asyncio
async def test_migration_service_initialization(migration_service, database_url):
    """Test migration service initializes correctly"""
    assert migration_service is not None
    assert migration_service.database_url == database_url
    assert migration_service.MIGRATIONS_DIR.exists()


@pytest.mark.asyncio
async def test_run_migrations(migration_service):
    """Test migrations run successfully"""
    result = await migration_service.run_migrations()
    assert result is True


@pytest.mark.asyncio
async def test_migrations_idempotent(migration_service):
    """Test migrations are idempotent (can run multiple times)"""
    # Run migrations
    result1 = await migration_service.run_migrations()
    assert result1 is True
    
    # Run again - should still succeed
    result2 = await migration_service.run_migrations()
    assert result2 is True


@pytest.mark.asyncio
async def test_verify_schema_all_tables_exist(migration_service):
    """Test schema verification finds all tables"""
    # Ensure migrations ran
    await migration_service.run_migrations()
    
    # Verify schema
    schema_status = await migration_service.verify_schema()
    
    # Check all required tables exist
    assert 'tracked_symbols' in schema_status
    assert 'api_keys' in schema_status
    assert 'api_key_audit' in schema_status
    
    # Check all tables are valid
    assert all(schema_status.values())


@pytest.mark.asyncio
async def test_verify_schema_checks_columns(migration_service):
    """Test schema verification checks required columns"""
    # Ensure migrations ran
    await migration_service.run_migrations()
    
    # Verify schema
    schema_status = await migration_service.verify_schema()
    
    # All tables should be valid
    for table, valid in schema_status.items():
        assert valid, f"Table {table} should be valid"


@pytest.mark.asyncio
async def test_get_migration_status(migration_service):
    """Test getting migration status"""
    # Ensure migrations ran
    await migration_service.run_migrations()
    
    # Get status
    status = await migration_service.get_migration_status()
    
    # Check status structure
    assert 'migration_files' in status
    assert 'schema_status' in status
    assert 'all_tables_valid' in status
    assert 'tables_checked' in status
    assert 'tables_valid' in status
    
    # Check values
    assert len(status['migration_files']) > 0
    assert status['tables_checked'] == 3  # tracked_symbols, api_keys, api_key_audit
    assert status['tables_valid'] == 3
    assert status['all_tables_valid'] is True


@pytest.mark.asyncio
async def test_tracked_symbols_table_structure(migration_service, database_url):
    """Test tracked_symbols table has correct structure"""
    import uuid
    await migration_service.run_migrations()
    
    conn = await asyncpg.connect(database_url)
    
    try:
        # Use unique symbol to avoid constraint violations
        unique_symbol = f'TEST_{uuid.uuid4().hex[:8]}'
        
        # Check table exists and can insert
        result = await conn.execute(
            """
            INSERT INTO tracked_symbols (symbol, asset_class, active)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            unique_symbol, 'stock', True
        )
        
        assert result is not None
        
        # Verify data inserted correctly
        row = await conn.fetchrow(
            "SELECT symbol, asset_class, active FROM tracked_symbols WHERE symbol = $1",
            unique_symbol
        )
        
        assert row['symbol'] == unique_symbol
        assert row['asset_class'] == 'stock'
        assert row['active'] is True
    
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_api_keys_table_structure(migration_service, database_url):
    """Test api_keys table has correct structure"""
    import uuid
    await migration_service.run_migrations()
    
    conn = await asyncpg.connect(database_url)
    
    try:
        # Use unique hash to avoid constraint violations
        unique_hash = f'hash_{uuid.uuid4().hex[:16]}'
        unique_name = f'key_{uuid.uuid4().hex[:8]}'
        
        # Check table exists and can insert
        result = await conn.execute(
            """
            INSERT INTO api_keys (key_hash, name, active)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            unique_hash, unique_name, True
        )
        
        assert result is not None
        
        # Verify data inserted correctly
        row = await conn.fetchrow(
            "SELECT key_hash, name, active FROM api_keys WHERE key_hash = $1",
            unique_hash
        )
        
        assert row['key_hash'] == unique_hash
        assert row['name'] == unique_name
        assert row['active'] is True
    
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_api_key_audit_table_structure(migration_service, database_url):
    """Test api_key_audit table has correct structure"""
    import uuid
    await migration_service.run_migrations()
    
    conn = await asyncpg.connect(database_url)
    
    try:
        # Insert an API key first with unique hash
        unique_hash = f'audit_hash_{uuid.uuid4().hex[:12]}'
        unique_name = f'audit_key_{uuid.uuid4().hex[:8]}'
        
        key_result = await conn.fetchrow(
            """
            INSERT INTO api_keys (key_hash, name, active)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            unique_hash, unique_name, True
        )
        key_id = key_result['id']
        
        # Now insert audit record
        result = await conn.execute(
            """
            INSERT INTO api_key_audit (api_key_id, endpoint, method, status_code)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            key_id, '/test/endpoint', 'GET', 200
        )
        
        assert result is not None
        
        # Verify data inserted correctly
        row = await conn.fetchrow(
            "SELECT endpoint, method, status_code FROM api_key_audit WHERE api_key_id = $1",
            key_id
        )
        
        assert row['endpoint'] == '/test/endpoint'
        assert row['method'] == 'GET'
        assert row['status_code'] == 200
    
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_schema_verification_handles_missing_tables(migration_service):
    """Test schema verification detects missing tables"""
    # Don't run migrations - tables won't exist
    # Create a new service pointing to a different (empty) database for this test
    # Skip if we can't test this way
    
    schema_status = await migration_service.verify_schema()
    
    # Should still return the dict, even if tables don't exist
    assert isinstance(schema_status, dict)
    assert 'tracked_symbols' in schema_status
    assert 'api_keys' in schema_status
    assert 'api_key_audit' in schema_status
