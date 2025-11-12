# Testing Guide

Comprehensive guide to testing in the Market Data API.

---

## Table of Contents

- [Overview](#overview)
- [Running Tests](#running-tests)
- [Test Structure](#test-structure)
- [Writing Tests](#writing-tests)
- [Mocking & Fixtures](#mocking--fixtures)
- [Coverage](#coverage)
- [Best Practices](#best-practices)

---

## Overview

The test suite consists of **400+ tests** covering:
- API endpoints (integration tests)
- Services (unit tests)
- Data validation
- Error handling
- Performance

**Current Status**: 100% pass rate ✅

---

## Running Tests

### Basic Commands

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_phase_7_timeframe_api.py -v

# Specific test class
pytest tests/test_phase_7_timeframe_api.py::TestTimeframeAPI -v

# Specific test function
pytest tests/test_phase_7_timeframe_api.py::TestTimeframeAPI::test_historical_with_timeframe -v

# Last 5 failed tests
pytest --lf -v

# Tests matching pattern
pytest -k "timeframe" -v

# Stop on first failure
pytest -x tests/

# Show local variables on failure
pytest -l tests/
```

### Advanced Options

```bash
# Parallel execution (requires pytest-xdist)
pytest -n auto tests/

# Only failed tests
pytest --failed-first tests/

# Quiet mode (less output)
pytest -q tests/

# Run with markers
pytest -m "slow" -v         # Only slow tests
pytest -m "not slow" -v     # Everything except slow tests

# Generate HTML report
pytest --html=report.html tests/

# Timeout (requires pytest-timeout)
pytest --timeout=10 tests/
```

### Continuous Testing

```bash
# Watch mode (requires pytest-watch)
ptw tests/ -v

# Rerun on file changes
pytest-watch tests/ --runner "pytest -x"
```

---

## Test Structure

### Directory Layout

```
tests/
├── conftest.py                      # Pytest configuration & fixtures
├── test_phase_1_*.py                # Phase 1 tests
├── test_phase_2_*.py                # Phase 2 tests
├── test_phase_7_*.py                # Phase 7 tests (current)
└── README.md                        # Test documentation
```

### Test File Organization

```python
# tests/test_my_feature.py

import pytest
from fastapi.testclient import TestClient
from main import app

# Setup
client = TestClient(app)

# Fixtures
@pytest.fixture
def sample_symbol():
    """Provide sample symbol for tests."""
    return "AAPL"

# Test class
class TestMyFeature:
    """Test my feature."""
    
    @pytest.mark.asyncio
    async def test_basic_functionality(self, sample_symbol):
        """Test basic functionality."""
        response = client.get(f"/api/v1/symbols/{sample_symbol}")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling."""
        response = client.get("/api/v1/symbols/INVALID")
        assert response.status_code == 404

# Standalone tests
def test_utility_function():
    """Test a utility function."""
    from src.services.my_service import utility_function
    result = utility_function("input")
    assert result == "expected"
```

---

## Writing Tests

### Test Template

```python
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

class TestMyFeature:
    """Test my new feature."""
    
    @pytest.mark.asyncio
    async def test_happy_path(self):
        """Test normal operation."""
        # Arrange
        symbol = "AAPL"
        
        # Act
        response = client.get(f"/api/v1/my-endpoint?symbol={symbol}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == symbol
    
    @pytest.mark.asyncio
    async def test_invalid_input(self):
        """Test validation of invalid input."""
        response = client.get("/api/v1/my-endpoint?symbol=")
        
        # Expect validation error
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_not_found(self):
        """Test handling of missing resource."""
        response = client.get("/api/v1/my-endpoint?symbol=FAKE123")
        
        # Expect not found error
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test handling of server errors."""
        # Mock a failure
        with pytest.raises(Exception):
            # Code that should fail
            pass
```

### Test Naming Convention

```python
# Good naming: test_<feature>_<condition>_<expected_result>

def test_historical_with_valid_symbol_returns_data():
    pass

def test_historical_with_invalid_symbol_returns_404():
    pass

def test_historical_with_future_dates_returns_empty():
    pass

def test_cache_hit_returns_cached_data():
    pass

def test_cache_miss_queries_database():
    pass
```

### Test Categories

#### 1. Happy Path Tests
Test normal operation with valid inputs:

```python
def test_get_historical_data_valid():
    """Test getting data with valid parameters."""
    response = client.get(
        "/api/v1/historical/AAPL"
        "?start=2024-01-01&end=2024-01-31&timeframe=1d"
    )
    assert response.status_code == 200
    assert len(response.json()["data"]) > 0
```

#### 2. Edge Case Tests
Test boundary conditions:

```python
def test_get_historical_data_single_day():
    """Test with start == end date."""
    response = client.get(
        "/api/v1/historical/AAPL"
        "?start=2024-01-01&end=2024-01-01&timeframe=1d"
    )
    assert response.status_code == 200

def test_get_historical_data_empty_range():
    """Test with future date range."""
    response = client.get(
        "/api/v1/historical/AAPL"
        "?start=2099-01-01&end=2099-12-31&timeframe=1d"
    )
    assert response.status_code == 404
```

#### 3. Error Case Tests
Test error handling:

```python
def test_get_historical_invalid_timeframe():
    """Test with invalid timeframe."""
    response = client.get(
        "/api/v1/historical/AAPL"
        "?start=2024-01-01&end=2024-01-31&timeframe=1x"
    )
    assert response.status_code == 400

def test_get_historical_invalid_date_format():
    """Test with invalid date format."""
    response = client.get(
        "/api/v1/historical/AAPL"
        "?start=01-01-2024&end=01-31-2024&timeframe=1d"
    )
    assert response.status_code == 400
```

#### 4. Integration Tests
Test multiple components together:

```python
async def test_symbol_add_and_query():
    """Test adding symbol then querying data."""
    # Add symbol
    add_response = client.post(
        "/api/v1/admin/symbols",
        headers={"X-API-Key": "test-key"},
        json={
            "symbol": "TEST",
            "name": "Test Corp",
            "asset_type": "stock",
            "timeframes": ["1d"]
        }
    )
    assert add_response.status_code == 201
    
    # Query data
    symbol = add_response.json()["symbol"]
    query_response = client.get(f"/api/v1/symbols")
    assert symbol in [s["symbol"] for s in query_response.json()["symbols"]]
```

#### 5. Performance Tests
Test performance characteristics:

```python
import time

def test_historical_response_time():
    """Test that queries respond quickly."""
    start = time.time()
    response = client.get(
        "/api/v1/historical/AAPL"
        "?start=2024-01-01&end=2024-01-31&timeframe=1d"
    )
    elapsed = time.time() - start
    
    # Should respond within 1 second (cached)
    assert elapsed < 1.0
```

---

## Mocking & Fixtures

### Built-in Fixtures

```python
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

@pytest.fixture
def api_key():
    """Provide a test API key."""
    return "test-key-550e8400-e29b-41d4-a716-446655440000"

@pytest.fixture
def sample_data():
    """Provide sample market data."""
    return {
        "symbol": "AAPL",
        "timeframe": "1d",
        "timestamp": "2024-01-15",
        "open": 150.25,
        "high": 151.50,
        "low": 149.75,
        "close": 150.80,
        "volume": 45000000
    }

@pytest.fixture
def admin_headers(api_key):
    """Provide admin authorization headers."""
    return {"X-API-Key": api_key}
```

### Using Fixtures

```python
class TestAdminAPI:
    """Test admin endpoints."""
    
    def test_create_symbol(self, admin_headers, sample_data):
        """Test creating a symbol."""
        response = client.post(
            "/api/v1/admin/symbols",
            headers=admin_headers,
            json=sample_data
        )
        assert response.status_code == 201
```

### Mocking External Calls

```python
from unittest.mock import patch, AsyncMock
import pytest

class TestPolygonIntegration:
    """Test Polygon API integration."""
    
    @pytest.mark.asyncio
    async def test_polygon_api_call(self):
        """Test handling of Polygon API response."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "status": "OK",
            "results": [{"c": 150.25, "h": 151.50, ...}]
        }
        
        with patch("httpx.AsyncClient.get", return_value=mock_response):
            # Call code that uses Polygon API
            response = client.get("/api/v1/historical/AAPL?start=2024-01-01&end=2024-01-31")
            assert response.status_code == 200
```

### Database Mocking

```python
from unittest.mock import patch, AsyncMock
import pytest

class TestDataAccess:
    """Test data access layer."""
    
    @pytest.mark.asyncio
    async def test_get_data_from_cache(self):
        """Test that cache is used when available."""
        mock_data = [{"open": 150.25, "close": 150.80, ...}]
        
        with patch("src.services.caching.get_query_cache") as mock_cache:
            mock_cache.return_value.get.return_value = mock_data
            
            # Call should use cache
            response = client.get("/api/v1/historical/AAPL?start=2024-01-01&end=2024-01-31")
            assert response.status_code == 200
```

---

## Coverage

### Checking Coverage

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=html

# View HTML report
open htmlcov/index.html

# Check coverage for specific file
pytest tests/ --cov=src.services.caching --cov-report=term-missing
```

### Coverage Targets

| Component | Target |
|-----------|--------|
| API endpoints | 95%+ |
| Services | 90%+ |
| Utils | 80%+ |
| Integration | 85%+ |

### Coverage Exclusions

Some code can be excluded from coverage:

```python
# Exclude from coverage
if False:  # pragma: no cover
    # This won't be tested
    pass

# Exclude line
x = complex_calculation()  # pragma: no cover
```

---

## Best Practices

### 1. Isolation

Each test should be independent:

```python
# Good - test is isolated
def test_get_symbols():
    response = client.get("/api/v1/symbols")
    assert response.status_code == 200

# Avoid - test depends on previous test
def test_add_symbol():
    # Assumes get_symbols already ran
    pass
```

### 2. Clarity

Test names and assertions should be clear:

```python
# Good - clear what's being tested
def test_historical_with_invalid_timeframe_returns_400():
    response = client.get(
        "/api/v1/historical/AAPL?timeframe=invalid&start=2024-01-01&end=2024-01-31"
    )
    assert response.status_code == 400, "Should reject invalid timeframe"

# Avoid - unclear
def test_endpoint():
    r = client.get("/api/v1/historical/AAPL")
    assert r.status_code == 200
```

### 3. Arrange-Act-Assert

Structure tests clearly:

```python
def test_calculate_quality_score():
    # Arrange
    candle = {"open": 100, "high": 105, "low": 95, "close": 102}
    
    # Act
    score = validate_ohlcv(candle)
    
    # Assert
    assert score >= 0.8
```

### 4. One Assertion Per Test (Preferred)

```python
# Good - focused test
def test_response_has_symbol():
    response = client.get("/api/v1/symbols")
    assert "AAPL" in [s["symbol"] for s in response.json()["symbols"]]

def test_response_has_count():
    response = client.get("/api/v1/symbols")
    assert response.json()["count"] > 0

# Acceptable - related assertions
def test_response_format():
    response = client.get("/api/v1/symbols")
    data = response.json()
    assert "symbols" in data
    assert "count" in data
    assert len(data["symbols"]) == data["count"]
```

### 5. Descriptive Error Messages

```python
# Good - message explains failure
assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

# Avoid - no context
assert response.status_code == 200
```

### 6. Test Documentation

```python
def test_cache_reduces_database_load():
    """
    Verify that query caching reduces database load.
    
    This test ensures that:
    1. First query hits the database
    2. Subsequent queries within TTL use cache
    3. Cache is invalidated after TTL expires
    """
    # Test implementation
    pass
```

---

## Async Testing

Tests use pytest-asyncio for async support:

```python
import pytest

class TestAsync:
    """Test async code."""
    
    @pytest.mark.asyncio
    async def test_async_function(self):
        """Test async function."""
        from src.services.my_service import get_data
        
        result = await get_data("AAPL")
        assert result is not None
```

---

## Test Markers

Mark tests for selective execution:

```python
import pytest

@pytest.mark.slow
def test_heavy_computation():
    """This test takes a long time."""
    pass

@pytest.mark.integration
def test_full_workflow():
    """Test multiple components together."""
    pass

# Run only integration tests
# pytest -m integration tests/

# Run everything except slow tests
# pytest -m "not slow" tests/
```

---

## Continuous Integration

Tests run automatically on:
- Push to main/develop
- Pull requests
- Scheduled (daily)

See `.github/workflows/` for CI configuration.

---

## Troubleshooting Tests

### Test Fails Locally But Passes in CI

```bash
# Run tests exactly as CI does
pytest tests/ -v --tb=short

# Check environment
echo $POLYGON_API_KEY
echo $DB_HOST
```

### Flaky Tests

Flaky tests pass sometimes, fail others:

```python
# Add retry decorator
import pytest

@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_sometimes_fails():
    """This test might be flaky."""
    pass
```

### Test Hangs

```bash
# Run with timeout
pytest --timeout=30 tests/

# Or kill specific test
pkill -f pytest
```

---

## See Also

- [Contributing Guide](/docs/development/CONTRIBUTING.md)
- [Architecture Overview](/docs/development/ARCHITECTURE.md)
- [Development Status](/docs/development/DEVELOPMENT_STATUS.md)
- [API Reference](/docs/api/ENDPOINTS.md)
