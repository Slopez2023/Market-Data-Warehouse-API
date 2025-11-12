"""
Tests for Phase 5: OHLCV Table & Data Migration

Validates:
1. Existing data backfilled with timeframe='1d'
2. New data includes timeframe
3. No duplicate (symbol, timeframe, time) tuples
4. Data consistency
"""

import pytest
import asyncpg
import os
from datetime import datetime
from typing import Dict

from src.config import ALLOWED_TIMEFRAMES


@pytest.fixture
def database_url():
    """Get database URL for tests"""
    return os.getenv("DATABASE_URL", "postgresql://testuser:testpass@localhost:5432/market_data_test")


@pytest.mark.asyncio
async def test_existing_data_has_timeframe(database_url):
    """Test that existing data has been backfilled with timeframe='1d'"""
    conn = await asyncpg.connect(database_url)
    
    try:
        # Check that no records have NULL timeframe
        null_count = await conn.fetchval(
            "SELECT COUNT(*) FROM market_data WHERE timeframe IS NULL"
        )
        assert null_count == 0, f"Found {null_count} records with NULL timeframe"
        
        # If we have any data, verify at least some has timeframe='1d'
        total_records = await conn.fetchval("SELECT COUNT(*) FROM market_data")
        if total_records > 0:
            one_d_count = await conn.fetchval(
                "SELECT COUNT(*) FROM market_data WHERE timeframe = '1d'"
            )
            assert one_d_count > 0, "No records with timeframe='1d' found"
    
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_timeframe_column_not_empty(database_url):
    """Test that timeframe column has no empty strings"""
    conn = await asyncpg.connect(database_url)
    
    try:
        empty_count = await conn.fetchval(
            "SELECT COUNT(*) FROM market_data WHERE timeframe = ''"
        )
        assert empty_count == 0, f"Found {empty_count} records with empty timeframe"
    
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_all_timeframes_are_valid(database_url):
    """Test that all timeframes in database are valid"""
    conn = await asyncpg.connect(database_url)
    
    try:
        # Get all distinct timeframes
        rows = await conn.fetch(
            "SELECT DISTINCT timeframe FROM market_data ORDER BY timeframe"
        )
        
        timeframes = [row['timeframe'] for row in rows]
        
        # Verify all are in ALLOWED_TIMEFRAMES
        for tf in timeframes:
            assert tf in ALLOWED_TIMEFRAMES, f"Invalid timeframe: {tf}. Allowed: {ALLOWED_TIMEFRAMES}"
    
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_no_duplicate_candles(database_url):
    """Test that there are no duplicate (symbol, timeframe, time) tuples"""
    conn = await asyncpg.connect(database_url)
    
    try:
        # Find any duplicates
        duplicates = await conn.fetch(
            """
            SELECT symbol, timeframe, time, COUNT(*) as count
            FROM market_data
            GROUP BY symbol, timeframe, time
            HAVING COUNT(*) > 1
            """
        )
        
        assert len(duplicates) == 0, (
            f"Found {len(duplicates)} duplicate (symbol, timeframe, time) tuples. "
            f"Examples: {duplicates[:5]}"
        )
    
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_insert_ohlcv_batch_with_timeframe(database_url):
    """Test that new inserts properly store timeframe"""
    import uuid
    from datetime import datetime, timedelta
    from src.services.database_service import DatabaseService
    
    # Create test data
    unique_symbol = f'TEST_PHASE5_{uuid.uuid4().hex[:8]}'
    
    candles = [
        {
            't': int(datetime.utcnow().timestamp() * 1000),
            'o': 100.0,
            'h': 101.0,
            'l': 99.0,
            'c': 100.5,
            'v': 1000000
        }
    ]
    
    metadata = [
        {
            'quality_score': 1.0,
            'validated': True,
            'validation_notes': 'Test',
            'gap_detected': False,
            'volume_anomaly': False,
            'timeframe': '1h'  # Test with 1h timeframe
        }
    ]
    
    db_service = DatabaseService(database_url)
    
    try:
        # Insert with timeframe='1h'
        inserted = db_service.insert_ohlcv_batch(
            unique_symbol,
            candles,
            metadata,
            timeframe='1h'
        )
        
        assert inserted == 1, f"Expected 1 record inserted, got {inserted}"
        
        # Verify the record was inserted with correct timeframe
        conn = await asyncpg.connect(database_url)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM market_data WHERE symbol = $1 AND timeframe = '1h'",
                unique_symbol
            )
            
            assert row is not None, f"Record not found for {unique_symbol} with timeframe='1h'"
            assert row['timeframe'] == '1h', f"Timeframe mismatch: {row['timeframe']}"
            assert row['validated'] is True
        finally:
            await conn.close()
    
    finally:
        # Cleanup
        pass


@pytest.mark.asyncio
async def test_timeframe_distribution(database_url):
    """Test that we can query timeframe distribution"""
    conn = await asyncpg.connect(database_url)
    
    try:
        distribution = await conn.fetch(
            """
            SELECT timeframe, COUNT(*) as count
            FROM market_data
            GROUP BY timeframe
            ORDER BY timeframe
            """
        )
        
        # Should have results if data exists
        if distribution:
            dist_dict = {row['timeframe']: row['count'] for row in distribution}
            
            # All timeframes should be valid
            for tf in dist_dict.keys():
                assert tf in ALLOWED_TIMEFRAMES, f"Invalid timeframe in distribution: {tf}"
            
            # At minimum, if we have data, we should have 1d
            # (from migration backfill)
            if sum(row['count'] for row in distribution) > 0:
                assert '1d' in dist_dict, "No 1d timeframe found in distribution"
    
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_unique_constraint_enforced(database_url):
    """Test that unique constraint on (symbol, timeframe, time) is enforced"""
    import uuid
    from datetime import datetime
    
    unique_symbol = f'TEST_UNIQUE_{uuid.uuid4().hex[:8]}'
    test_time = datetime.utcnow()
    test_timestamp_ms = int(test_time.timestamp() * 1000)
    
    conn = await asyncpg.connect(database_url)
    
    try:
        # Insert first record
        await conn.execute(
            """
            INSERT INTO market_data
            (symbol, timeframe, time, open, high, low, close, volume, 
             validated, quality_score, validation_notes, gap_detected, 
             volume_anomaly, source, fetched_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            """,
            unique_symbol, '1d', test_time, 100.0, 101.0, 99.0, 100.5,
            1000000, True, 1.0, 'test', False, False, 'polygon', datetime.utcnow()
        )
        
        # Try to insert duplicate - should fail or update
        # The database should have ON CONFLICT DO UPDATE, so this should succeed
        # but not create a duplicate
        await conn.execute(
            """
            INSERT INTO market_data
            (symbol, timeframe, time, open, high, low, close, volume, 
             validated, quality_score, validation_notes, gap_detected, 
             volume_anomaly, source, fetched_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT (symbol, timeframe, time) DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                validated = EXCLUDED.validated,
                quality_score = EXCLUDED.quality_score,
                validation_notes = EXCLUDED.validation_notes,
                gap_detected = EXCLUDED.gap_detected,
                volume_anomaly = EXCLUDED.volume_anomaly,
                fetched_at = EXCLUDED.fetched_at
            """,
            unique_symbol, '1d', test_time, 100.5, 101.5, 99.5, 101.0,
            1100000, True, 0.95, 'test updated', False, False, 'polygon', datetime.utcnow()
        )
        
        # Verify only one record exists
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM market_data WHERE symbol = $1 AND timeframe = '1d'",
            unique_symbol
        )
        
        assert count == 1, f"Expected 1 record, found {count}"
        
        # Verify it was updated
        row = await conn.fetchrow(
            "SELECT close, volume FROM market_data WHERE symbol = $1 AND timeframe = '1d'",
            unique_symbol
        )
        
        assert row['close'] == 101.0, "Record was not updated"
        assert row['volume'] == 1100000, "Record was not updated"
    
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_file_exists(database_url):
    """Test that migration file exists"""
    from pathlib import Path
    
    migration_file = Path(__file__).parent.parent / "database" / "migrations" / "006_backfill_existing_data_with_timeframes.sql"
    assert migration_file.exists(), f"Migration file not found: {migration_file}"
    
    # Verify it has content
    content = migration_file.read_text()
    assert 'UPDATE market_data' in content, "Migration file missing UPDATE statement"
    assert "timeframe = '1d'" in content, "Migration file missing timeframe assignment"
