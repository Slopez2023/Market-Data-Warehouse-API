# Contributing Guide

Guidelines for contributing to the Market Data API project.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Code Style](#code-style)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Code Review Process](#code-review-process)

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git
- Basic familiarity with FastAPI

### Fork & Clone

```bash
# 1. Fork the repository on GitHub
# https://github.com/Slopez2023/Market-Data-Warehouse-API

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/Market-Data-Warehouse-API.git
cd MarketDataAPI

# 3. Add upstream remote
git remote add upstream https://github.com/Slopez2023/Market-Data-Warehouse-API.git

# 4. Create feature branch
git checkout -b feature/your-feature-name
```

---

## Development Setup

### Local Environment

```bash
# 1. Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Setup environment
cp .env.example .env
# Edit .env with your values (for local development)

# 4. Start services
docker-compose up -d

# 5. Run database migrations
python -c "
from src.services.migration_service import init_migration_service
import asyncio
migration_service = init_migration_service('postgresql://postgres:password@localhost/market_data')
asyncio.run(migration_service.run_migrations())
"

# 6. Run API (development mode)
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Project Structure Review

```
src/
├── clients/              # External API clients
├── middleware/           # Request/response processing
├── services/             # Business logic
├── models.py             # Pydantic schemas
├── config.py             # Configuration
└── scheduler.py          # Background tasks

tests/
├── test_phase_*.py       # Phase-specific tests
├── conftest.py           # Pytest configuration
└── README.md             # Testing guide
```

---

## Making Changes

### Branch Naming

Use descriptive branch names:

```bash
# Features
git checkout -b feature/add-earnings-endpoint

# Bug fixes
git checkout -b fix/cache-invalidation-issue

# Documentation
git checkout -b docs/update-api-reference

# Refactoring
git checkout -b refactor/simplify-database-layer
```

### Commit Messages

Follow conventional commits:

```bash
# Feature
git commit -m "feat: Add earnings data endpoint"

# Bug fix
git commit -m "fix: Resolve cache key collision"

# Documentation
git commit -m "docs: Update API reference"

# Refactoring
git commit -m "refactor: Simplify query caching logic"

# Tests
git commit -m "test: Add coverage for earnings service"

# Style
git commit -m "style: Format code to PEP 8"

# Performance
git commit -m "perf: Optimize database queries"
```

---

## Testing

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_phase_7_timeframe_api.py -v

# Single test
pytest tests/test_phase_7_timeframe_api.py::test_historical_with_timeframe -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Watch mode (requires pytest-watch)
ptw tests/ -v
```

### Writing Tests

All new features must include tests. Example:

```python
# tests/test_my_feature.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

class TestMyFeature:
    """Test my new feature."""
    
    @pytest.mark.asyncio
    async def test_my_endpoint(self):
        """Test that my endpoint returns correct data."""
        response = client.get("/api/v1/my-endpoint?param=value")
        
        assert response.status_code == 200
        assert "expected_key" in response.json()
    
    @pytest.mark.asyncio
    async def test_my_endpoint_invalid_input(self):
        """Test that my endpoint validates input."""
        response = client.get("/api/v1/my-endpoint?invalid=true")
        
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_my_endpoint_error_handling(self):
        """Test error handling."""
        response = client.get("/api/v1/my-endpoint?error=true")
        
        assert response.status_code == 500
```

### Test Coverage

- **Minimum**: 80% coverage of new code
- **Target**: 90%+ coverage
- **Critical paths**: 100% coverage required

Check coverage:

```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html  # View report
```

---

## Code Style

### PEP 8 Compliance

```bash
# Check style
flake8 src/ --max-line-length=100

# Auto-format code
black src/ --line-length=100

# Type checking
mypy src/
```

### Code Standards

1. **Type Hints**: All functions must have type hints
   ```python
   async def get_data(symbol: str, days: int = 30) -> dict:
       """Get data for symbol."""
       pass
   ```

2. **Docstrings**: All public functions need docstrings
   ```python
   async def get_historical_data(symbol: str, timeframe: str) -> dict:
       """
       Fetch historical OHLCV data.
       
       Args:
           symbol: Ticker symbol (e.g., AAPL)
           timeframe: Candle timeframe (5m, 1h, 1d, etc.)
       
       Returns:
           Dictionary with OHLCV data
       """
       pass
   ```

3. **Comments**: Explain *why*, not *what*
   ```python
   # Good: Explains rationale
   # Use exponential backoff to avoid overwhelming the API
   wait_time = initial_wait * (2 ** attempt)
   
   # Avoid: Explains obvious code
   # Increment counter
   counter += 1
   ```

4. **Variable Names**: Clear, descriptive names
   ```python
   # Good
   historical_data = db.get_ohlcv_data(symbol, start, end)
   quality_threshold = 0.85
   
   # Avoid
   data = db.get_data(s, st, e)
   qt = 0.85
   ```

5. **Function Length**: Keep functions focused
   - Aim for <50 lines per function
   - Single responsibility principle
   - Extract complex logic into separate functions

### Async/Await

All I/O operations must be async:

```python
# Good
async def fetch_data(symbol: str) -> dict:
    data = await db.get_historical_data(symbol)
    return data

# Avoid
def fetch_data(symbol: str) -> dict:
    data = db.get_historical_data(symbol)  # Blocks!
    return data
```

---

## Documentation

### Code Documentation

1. **Module docstring**
   ```python
   """
   Market data validation service.
   
   Provides data quality checks, anomaly detection, 
   and validation scoring for OHLCV candles.
   """
   ```

2. **Function docstring**
   ```python
   async def validate_ohlcv(candle: dict) -> float:
       """
       Validate OHLCV candle and return quality score.
       
       Args:
           candle: OHLCV data point
       
       Returns:
           Quality score (0.0-1.0)
       
       Raises:
           ValueError: If candle is invalid
       """
   ```

### User Documentation

Update docs when changing functionality:

```bash
# Affected documentation files to update:
# - docs/api/ENDPOINTS.md          (if API changes)
# - docs/features/*.md             (if feature changes)
# - docs/operations/*.md           (if deployment/ops changes)
# - README.md                      (if major changes)
# - INDEX.md                       (if significant changes)
```

### Example Documentation Update

```markdown
### New Endpoint: `/api/v1/my-endpoint`

**Description**: Brief description of what it does

**Method**: GET / POST / PUT / DELETE

**Parameters**:
- `symbol` (required): Stock ticker
- `days` (optional): Lookback period (default: 30)

**Response**:
```json
{
  "symbol": "AAPL",
  "data": [...]
}
```

**Example**:
```bash
curl "http://localhost:8000/api/v1/my-endpoint?symbol=AAPL&days=60"
```
```

---

## Submitting Changes

### Before Submitting

```bash
# 1. Update from upstream
git fetch upstream
git rebase upstream/main

# 2. Run all tests
pytest tests/ -v

# 3. Check code style
flake8 src/
black src/ --check

# 4. Check type hints
mypy src/

# 5. Update documentation
# Edit relevant docs/ files

# 6. Commit changes
git add .
git commit -m "feat: Add my feature"

# 7. Push to your fork
git push origin feature/my-feature
```

### Pull Request

1. **Title**: Use conventional commit format
   - `feat: Add earnings endpoint`
   - `fix: Resolve cache invalidation bug`

2. **Description**: Include
   - What changed and why
   - Related issues (if any)
   - Testing done
   - Any breaking changes

3. **Example PR Description**:
   ```markdown
   ## Description
   Adds multi-timeframe support for historical data queries.
   
   ## Changes
   - New `timeframe` query parameter for /api/v1/historical
   - Database schema updates for timeframe storage
   - Per-symbol timeframe configuration
   
   ## Related Issues
   Closes #123
   
   ## Testing
   - Added 50+ tests for timeframe functionality
   - All tests passing (400+/400+)
   - Manual testing with multiple symbols
   
   ## Breaking Changes
   None
   ```

---

## Code Review Process

### What Reviewers Look For

1. **Functionality**: Does it work as intended?
2. **Tests**: Are there comprehensive tests?
3. **Code quality**: PEP 8, type hints, docstrings?
4. **Performance**: Any negative performance impact?
5. **Security**: Any new vulnerabilities?
6. **Documentation**: Is it documented?

### Addressing Feedback

```bash
# 1. Make requested changes
# Edit files

# 2. Commit with clear message
git commit -m "Address review feedback"

# 3. Push again (forces update on PR)
git push origin feature/my-feature

# 4. Leave comment explaining changes
# "Updated per review feedback: ..."
```

### Approval & Merging

- At least one approval required
- All tests must pass
- No unresolved conversations
- Maintainer will merge

---

## Development Tips

### Debugging

```python
# Add breakpoint for debugging
import pdb; pdb.set_trace()

# Or in async code
import asyncio; import pdb; pdb.set_trace()

# Print debugging
import logging
logger = logging.getLogger(__name__)
logger.debug(f"Variable value: {variable}")
```

### Database Access During Development

```bash
# Connect to development database
docker exec -it market_data_db psql -U postgres -d market_data

# Run query
SELECT COUNT(*) FROM ohlcv;
```

### API Testing During Development

```bash
# Interactive API docs
http://localhost:8000/docs

# Or use curl
curl http://localhost:8000/api/v1/symbols

# Or use httpie
http GET http://localhost:8000/api/v1/symbols

# Or use Python client
import httpx
async with httpx.AsyncClient() as client:
    response = await client.get("http://localhost:8000/api/v1/symbols")
    print(response.json())
```

---

## Common Workflows

### Adding a New Endpoint

1. **Define the schema** in `src/models.py`
   ```python
   class MyRequest(BaseModel):
       symbol: str
       days: int = 30
   ```

2. **Implement the handler** in `main.py` or service
   ```python
   @app.get("/api/v1/my-endpoint")
   async def my_endpoint(symbol: str, days: int = 30):
       # Implementation
       return {"result": data}
   ```

3. **Add tests** in `tests/`
   ```python
   def test_my_endpoint():
       response = client.get("/api/v1/my-endpoint?symbol=AAPL")
       assert response.status_code == 200
   ```

4. **Update documentation** in `docs/api/ENDPOINTS.md`

5. **Run full test suite**
   ```bash
   pytest tests/ -v
   ```

### Adding a New Service

1. **Create service file** in `src/services/my_service.py`
2. **Implement class** with async methods
3. **Add initialization** in `main.py`
4. **Add tests** in `tests/test_my_service.py`
5. **Document** in relevant docs files

---

## Questions?

- Check [FAQ](/docs/reference/FAQ.md)
- Review existing code for patterns
- Ask in pull request comments
- Check [Architecture](/docs/development/ARCHITECTURE.md)

---

## Code of Conduct

- Be respectful and inclusive
- Give credit where due
- Help others learn
- Ask questions, don't assume
- Provide constructive feedback

---

## See Also

- [Architecture Overview](/docs/development/ARCHITECTURE.md)
- [Testing Guide](/docs/development/TESTING.md)
- [API Reference](/docs/api/ENDPOINTS.md)
- [Development Status](/docs/development/DEVELOPMENT_STATUS.md)
