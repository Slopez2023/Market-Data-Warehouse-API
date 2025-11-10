"""Global pytest configuration and fixtures"""

import os
import pytest
import asyncio
import asyncpg
from unittest.mock import patch
from pathlib import Path

# Set test environment variables BEFORE importing any code that depends on config
# Use the TimescaleDB container running on port 5433 for tests
TEST_ENV_VARS = {
    "DATABASE_URL": "postgresql://postgres:postgres@localhost:5433/market_data",
    "POLYGON_API_KEY": "pk_test_abcd1234efgh5678ijkl9012mnop3456",
    "LOG_LEVEL": "DEBUG",
    "API_HOST": "127.0.0.1",
    "API_PORT": "8000",
    "API_WORKERS": "1",
    "BACKFILL_SCHEDULE_HOUR": "2",
    "BACKFILL_SCHEDULE_MINUTE": "0",
}

# Apply environment variables immediately
os.environ.update(TEST_ENV_VARS)


def pytest_configure(config):
    """Run migrations before pytest starts"""
    database_url = os.getenv("DATABASE_URL")
    migrations_dir = Path(__file__).parent / "database" / "migrations"
    
    # Run migrations synchronously
    async def run_migrations():
        try:
            conn = await asyncpg.connect(database_url)
            
            # Run all migration files
            migration_files = sorted([
                f for f in migrations_dir.glob("*.sql")
                if f.is_file()
            ])
            
            for migration_file in migration_files:
                sql_content = migration_file.read_text()
                try:
                    await conn.execute(sql_content)
                except Exception as e:
                    print(f"Warning: Migration {migration_file.name} failed: {e}")
            
            await conn.close()
        except Exception as e:
            print(f"Warning: Could not run migrations: {e}")
    
    # Use asyncio.run() for Python 3.7+
    try:
        asyncio.run(run_migrations())
    except Exception as e:
        print(f"Warning: Could not execute migrations: {e}")


@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Cleanup test data after each test"""
    yield
    
    database_url = os.getenv("DATABASE_URL")
    try:
        conn = await asyncpg.connect(database_url)
        # Clean up tables created during tests (optional)
        await conn.close()
    except Exception:
        pass


@pytest.fixture
def api_key():
    """Polygon API key for testing"""
    return "pk_test_abcd1234efgh5678ijkl9012mnop3456"


@pytest.fixture
def sample_candle():
    """Sample valid OHLCV candle for testing"""
    return {
        'o': 150.0,
        'h': 152.0,
        'l': 149.0,
        'c': 151.0,
        'v': 1000000,
        't': 1699507200000,
        'T': 'AAPL',
        'n': 10000
    }


@pytest.fixture
def sample_candle_batch():
    """Sample batch of OHLCV candles"""
    return [
        {
            'o': 150.0, 'h': 152.0, 'l': 149.0, 'c': 151.0,
            'v': 1000000, 't': 1699500000000, 'T': 'AAPL'
        },
        {
            'o': 151.0, 'h': 153.0, 'l': 150.0, 'c': 152.0,
            'v': 1100000, 't': 1699586400000, 'T': 'AAPL'
        },
        {
            'o': 152.0, 'h': 154.0, 'l': 151.0, 'c': 153.0,
            'v': 1200000, 't': 1699672800000, 'T': 'AAPL'
        }
    ]
