# Getting Started

Complete guides to install, configure, and run the Market Data API.

---

## 📚 Guides in This Section

### [Installation](INSTALLATION.md)
Complete installation instructions including:
- System requirements
- Python virtual environment setup
- Dependency installation
- Database setup
- Configuration

**Time**: 15 minutes

### [Setup Guide](SETUP_GUIDE.md)
Step-by-step configuration including:
- Environment variables
- Database connection
- API key setup
- Bootstrap process
- Initial data seeding

**Time**: 10 minutes

### [5-Minute Quickstart](QUICKSTART.md)
Fastest path to running the API including:
- Prerequisites
- Quick installation
- Configuration
- First API call
- Next steps

**Time**: 5 minutes

---

## 🚀 Quick Start Path

**New users**: Follow this order:

1. [5-Minute Quickstart](QUICKSTART.md) - Get it running immediately
2. [Installation](INSTALLATION.md) - Detailed setup instructions
3. [Setup Guide](SETUP_GUIDE.md) - Configuration details

---

## ✅ Verification

After setup, verify everything works:

```bash
# Check API is running
curl http://localhost:8000/api/v1/status

# Check database
curl http://localhost:8000/api/v1/tickers

# Check dashboard
open http://localhost:3000
```

---

## 🆘 Troubleshooting

If you run into issues:

1. Check the [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md)
2. Review [FAQ](/docs/reference/FAQ.md)
3. Check API logs for errors

---

## 📋 Next Steps

After getting started:

- **Using the API**: Go to [API Reference](/docs/api/)
- **Production deployment**: Go to [Deployment Guide](/docs/operations/DEPLOYMENT.md)
- **Development**: Go to [Contributing Guide](/docs/development/CONTRIBUTING.md)

---

**Ready?** Start with [5-Minute Quickstart](QUICKSTART.md) →
