# Reference & Tools

Quick reference materials and tools for the Market Data API.

---

## 📚 Reference Guides

### [Quick Reference](QUICK_REFERENCE.md)
Command and code cheat sheets:
- Common curl commands
- Python client examples
- Configuration templates
- Database queries
- Docker commands

**Use this for**: Quick lookups, copy-paste commands

### [FAQ](FAQ.md)
Frequently asked questions:
- Common questions
- Quick answers
- Troubleshooting tips
- Best practices

**Use this for**: Common questions, quick answers

### [Glossary](GLOSSARY.md)
Terms and definitions:
- Technical terms
- API concepts
- Component names
- Abbreviations

**Use this for**: Understanding terminology, definitions

---

## 🎯 Quick Lookups

### I want to...

- **Find a command** → [Quick Reference](QUICK_REFERENCE.md)
- **Answer a quick question** → [FAQ](FAQ.md)
- **Understand a term** → [Glossary](GLOSSARY.md)
- **Get code examples** → [Quick Reference](QUICK_REFERENCE.md)
- **See common errors** → [FAQ](FAQ.md)

---

## 🔍 Glossary Quick Links

### Common Terms

| Term | Definition |
|------|-----------|
| **API Key** | Unique token for authenticating API requests |
| **OHLCV** | Open, High, Low, Close, Volume (candlestick data) |
| **Symbol** | Market identifier (e.g., AAPL, BTC-USD) |
| **Asset Class** | Category of asset (stock, crypto, etc.) |
| **Backfill** | Historical data collection process |

See [Glossary](GLOSSARY.md) for complete list.

---

## ⚡ Quick Commands

### API Requests
```bash
# Health check
curl http://localhost:8000/api/v1/status

# List symbols
curl http://localhost:8000/api/v1/symbols

# Get stock data
curl "http://localhost:8000/api/v1/bars?symbol=AAPL&limit=10"
```

See [Quick Reference](QUICK_REFERENCE.md) for more commands.

### Database
```bash
# Connect to database
psql $DATABASE_URL

# List tables
\dt

# Check migrations
SELECT * FROM schema_migrations;
```

### Docker
```bash
# Build image
docker build -t marketdata-api .

# Run container
docker run -p 8000:8000 marketdata-api

# View logs
docker logs -f marketdata-api
```

See [Quick Reference](QUICK_REFERENCE.md) for more.

---

## ❓ FAQ Quick Access

### Top Questions

1. **How do I get an API key?**
   → See [FAQ](FAQ.md) → "Authentication"

2. **What are the rate limits?**
   → See [FAQ](FAQ.md) → "Rate Limiting"

3. **How do I add a new symbol?**
   → See [FAQ](FAQ.md) → "Symbols"

4. **Can I use cryptocurrencies?**
   → See [FAQ](FAQ.md) → "Cryptocurrency"

5. **How do I deploy to production?**
   → See [Deployment Guide](/docs/operations/DEPLOYMENT.md)

See [FAQ](FAQ.md) for complete list.

---

## 🔗 Cross-References

### By Use Case

| Use Case | Resources |
|----------|-----------|
| **Getting Started** | [Installation](/docs/getting-started/INSTALLATION.md) \| [Quick Start](/docs/getting-started/QUICKSTART.md) |
| **Using the API** | [Endpoints](/docs/api/ENDPOINTS.md) \| [Authentication](/docs/api/AUTHENTICATION.md) |
| **Deployment** | [Deployment Guide](/docs/operations/DEPLOYMENT.md) \| [Troubleshooting](/docs/operations/TROUBLESHOOTING.md) |
| **Development** | [Architecture](/docs/development/ARCHITECTURE.md) \| [Contributing](/docs/development/CONTRIBUTING.md) |
| **Quick Lookup** | [Quick Reference](QUICK_REFERENCE.md) \| [FAQ](FAQ.md) \| [Glossary](GLOSSARY.md) |

---

## 📊 Development Status

For detailed project status:
- See [Development Status](/DEVELOPMENT_STATUS.md)
- See [Phase Overview](../.phases/)

---

## 🆘 Finding Help

1. **Quick answer**: Check [FAQ](FAQ.md)
2. **Error message**: See [Troubleshooting](/docs/operations/TROUBLESHOOTING.md)
3. **API question**: See [Endpoints](/docs/api/ENDPOINTS.md)
4. **Setup issue**: See [Installation](/docs/getting-started/INSTALLATION.md)
5. **Command reference**: See [Quick Reference](QUICK_REFERENCE.md)
6. **Definition**: See [Glossary](GLOSSARY.md)

---

## 📚 Complete Documentation Index

| Section | Purpose |
|---------|---------|
| [Getting Started](/docs/getting-started/) | Installation and setup |
| [API Reference](/docs/api/) | Endpoints and integration |
| [Operations](/docs/operations/) | Deployment and monitoring |
| [Development](/docs/development/) | Architecture and contributing |
| [Reference](/docs/reference/) | Quick lookups and tools |

---

**Status**: Complete ✅  
**Last Updated**: November 10, 2025
