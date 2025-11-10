"""Pytest configuration and shared fixtures"""

import os
import sys
import pytest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


@pytest.fixture(scope="session")
def api_key():
    """Get Polygon API key from environment"""
    key = os.getenv("POLYGON_API_KEY")
    if not key:
        pytest.skip("POLYGON_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def database_url():
    """Get database URL from environment"""
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line("markers", "asyncio: async test")
    config.addinivalue_line("markers", "integration: integration test")
    config.addinivalue_line("markers", "performance: performance test")
