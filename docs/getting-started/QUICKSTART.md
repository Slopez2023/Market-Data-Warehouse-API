# 5-Minute Quick Start

Get the Market Data API running in 5 minutes.

## Prerequisites

- Python 3.8+
- PostgreSQL with TimescaleDB
- Polygon.io API key (free tier available)

## Setup

### 1. Clone & Install (1 min)
```bash
git clone <repo>
cd MarketDataAPI
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment (1 min)
```bash
# Copy template
cp .env.example .env  # if available

# Edit .env with your values
export DATABASE_URL="postgresql://user:pass@localhost:5432/marketdata"
export POLYGON_API_KEY="your_api_key"
```

### 3. Database (1 min)
```bash
# Migrations run automatically on first start, but you can run manually:
python scripts/bootstrap_db.py
```

### 4. Start API (1 min)
```bash
python main.py
```

**API**: http://localhost:8000  
**Dashboard**: http://localhost:3000

### 5. Test It (1 min)
```bash
# Get health status
curl http://localhost:8000/api/v1/status

# Or use Python
python -c "import requests; print(requests.get('http://localhost:8000/api/v1/status').json())"
```

---

## First API Call

### Without Authentication
```bash
curl http://localhost:8000/api/v1/tickers
```

### With Authentication (Admin)
```bash
# From bootstrap output or check database
export API_KEY="mdw_your_key_here"

curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v1/admin/api-keys
```

---

## Next Steps

- **Full Setup**: See [Installation Guide](/docs/getting-started/INSTALLATION.md)
- **API Docs**: See [Endpoints Reference](/docs/api/ENDPOINTS.md)
- **Deployment**: See [Deployment Guide](/docs/operations/DEPLOYMENT.md)
- **Troubleshooting**: See [Common Issues](/docs/operations/TROUBLESHOOTING.md)

---

## Common Commands

```bash
# Run all tests
pytest tests/ -v

# Run specific phase tests
pytest tests/test_phase_6_4.py -v

# Check test coverage
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# View API documentation
# Open http://localhost:8000/docs in browser
```

---

## Support

- Documentation: `/docs/`
- Issues: Check [Troubleshooting](/docs/operations/TROUBLESHOOTING.md)
- FAQ: See [FAQ](/docs/reference/FAQ.md)
