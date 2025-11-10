# API Reference

Complete reference for the Market Data API including all endpoints, authentication, and integration guides.

---

## 📚 Reference Documentation

### [Endpoints](ENDPOINTS.md)
Complete reference for all API endpoints:
- Market data endpoints
- Symbol management
- API key management
- Health and status endpoints
- Response formats and error codes

**Use this for**: Building applications, integration guides, response formats

### [Authentication](AUTHENTICATION.md)
API key management and security:
- Creating API keys
- Using API keys in requests
- Key rotation and revocation
- Audit logging
- Best practices

**Use this for**: Setting up authentication, managing keys, audit trails

### [Symbols](SYMBOLS.md)
Working with market symbols:
- Available symbols
- Adding new symbols
- Symbol filtering and retrieval
- Asset classes
- Statistics and backfill status

**Use this for**: Finding symbols, adding symbols, filtering by type

### [Cryptocurrency](CRYPTO.md)
Cryptocurrency endpoint reference:
- Supported cryptocurrencies
- Bitcoin, Ethereum, and more
- Crypto-specific endpoints
- Data formats
- Trading pairs

**Use this for**: Crypto integration, Bitcoin/Ethereum endpoints, pair support

---

## 🎯 Common Tasks

### I want to...

- **See all endpoints** → [Endpoints](ENDPOINTS.md)
- **Create an API key** → [Authentication](AUTHENTICATION.md)
- **Get stock data** → [Endpoints](ENDPOINTS.md) → "Market Data"
- **Get crypto data** → [Cryptocurrency](CRYPTO.md)
- **Add a new symbol** → [Symbols](SYMBOLS.md)
- **Call an endpoint** → [Endpoints](ENDPOINTS.md)

---

## 🔑 Quick Authentication Example

All protected endpoints require an API key:

```bash
# Get your API key
export API_KEY="mdw_your_key_here"

# Use in request headers
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v1/admin/api-keys
```

See [Authentication Guide](AUTHENTICATION.md) for details.

---

## 📊 Endpoint Categories

| Category | Endpoints | Details |
|----------|-----------|---------|
| **Market Data** | `/tickers`, `/bars`, `/quotes` | Stock and crypto OHLCV data |
| **Symbols** | `/symbols`, `/symbols/{id}` | Symbol management |
| **Authentication** | `/admin/api-keys/*` | API key CRUD |
| **Health** | `/status`, `/health` | System status |
| **Monitoring** | `/observability/*` | Metrics and alerts |

See [Endpoints Reference](ENDPOINTS.md) for complete list.

---

## 🧪 Testing an Endpoint

### Using curl:
```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v1/tickers?asset_class=stock
```

### Using Python:
```python
import requests
headers = {"X-API-Key": "your_api_key"}
response = requests.get(
    "http://localhost:8000/api/v1/tickers",
    headers=headers,
    params={"asset_class": "stock"}
)
print(response.json())
```

### Interactive API Docs:
Open http://localhost:8000/docs in your browser

---

## 📋 Response Format

All endpoints return JSON:

```json
{
  "status": "success",
  "data": { ... },
  "timestamp": "2025-11-10T14:00:00Z"
}
```

Error responses:
```json
{
  "status": "error",
  "error": "Invalid API key",
  "code": "AUTH_001",
  "timestamp": "2025-11-10T14:00:00Z"
}
```

See [Endpoints Reference](ENDPOINTS.md) for response examples.

---

## 🚀 Getting Started

1. **Setup**: See [Installation Guide](/docs/getting-started/INSTALLATION.md)
2. **Authenticate**: See [Authentication Guide](AUTHENTICATION.md)
3. **Choose endpoints**: See [Endpoints Reference](ENDPOINTS.md)
4. **Integrate**: Use code examples from guides

---

## 🆘 Common Issues

### 401 Unauthorized
- Check API key is provided in `X-API-Key` header
- Verify key is not revoked
- See [Authentication Guide](AUTHENTICATION.md)

### 404 Not Found
- Check endpoint path is correct
- Verify symbol exists
- See [Endpoints Reference](ENDPOINTS.md)

### 500 Server Error
- Check server logs
- See [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md)

---

## 📚 Next Steps

- **Integrating?** Start with [Endpoints Reference](ENDPOINTS.md)
- **Managing keys?** Go to [Authentication Guide](AUTHENTICATION.md)
- **Using crypto?** Go to [Cryptocurrency Guide](CRYPTO.md)
- **Deploying?** Go to [Deployment Guide](/docs/operations/DEPLOYMENT.md)

---

**Status**: Production Ready ✅  
**Last Updated**: November 10, 2025
