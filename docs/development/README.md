# Development

Guides for understanding, developing, and contributing to the Market Data API.

---

## 📚 Development Guides

### [Architecture Guide](ARCHITECTURE.md)
System design and architecture:
- Project structure
- Component overview
- Data flow
- Design patterns
- Technology choices

**Use this for**: Understanding how the system works, planning changes

### [Contributing Guide](CONTRIBUTING.md)
Development workflow and guidelines:
- Setup development environment
- Making changes
- Running tests
- Code style guidelines
- Commit messages
- Pull request process

**Use this for**: Contributing code, setting up development

### [Testing Guide](TESTING.md)
Test suite and testing best practices:
- Test organization
- Running tests
- Writing new tests
- Test coverage
- Common testing patterns
- Mock usage

**Use this for**: Writing tests, understanding test structure, debugging tests

---

## 🎯 Common Tasks

### I want to...

- **Understand the codebase** → [Architecture Guide](ARCHITECTURE.md)
- **Make a code change** → [Contributing Guide](CONTRIBUTING.md)
- **Write a test** → [Testing Guide](TESTING.md)
- **See the project structure** → [Architecture Guide](ARCHITECTURE.md) → "Project Structure"
- **Run the test suite** → [Testing Guide](TESTING.md) → "Running Tests"
- **Understand design patterns** → [Architecture Guide](ARCHITECTURE.md) → "Design Patterns"

---

## 🚀 Getting Started with Development

### 1. Setup Development Environment
```bash
# Clone repository
git clone <repo>
cd MarketDataAPI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies (optional)
pip install -r requirements-dev.txt
```

### 2. Understand the Architecture
Read [Architecture Guide](ARCHITECTURE.md) to understand:
- Project structure
- Key components
- Data flow
- Dependencies

### 3. Run the Tests
```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### 4. Make Changes
1. Create a branch: `git checkout -b feature/your-feature`
2. Make code changes
3. Write tests for new functionality
4. Run tests: `pytest tests/`
5. Commit: `git commit -m "description"`

### 5. Review Guidelines
Before submitting changes:
- Read [Contributing Guide](CONTRIBUTING.md)
- Check code style
- Ensure tests pass
- Add test coverage for new code
- Update documentation if needed

---

## 📊 Project Stats

| Metric | Value |
|--------|-------|
| Total Tests | 347 |
| Pass Rate | 100% |
| Test Files | 19 |
| Source Files | 50+ |
| Lines of Code | 7,800+ |
| Phases Complete | 6.5 |

---

## 📁 Project Structure

```
MarketDataAPI/
├── src/                           # Source code
│   ├── services/                  # Business logic
│   ├── models.py                  # Pydantic models
│   ├── middleware.py              # FastAPI middleware
│   └── ...
├── tests/                         # Test suite (347 tests)
├── database/                      # SQL migrations
├── docs/                          # Documentation
├── scripts/                       # Utility scripts
├── config/                        # Configuration
├── infrastructure/                # Docker & deployment
└── main.py                        # FastAPI application
```

See [Architecture Guide](ARCHITECTURE.md) for complete structure.

---

## 🧪 Test Summary

| Component | Tests | Status |
|-----------|-------|--------|
| Validation | 25 | ✅ |
| Database | 22 | ✅ |
| Environment | 16 | ✅ |
| Scheduler | 28 | ✅ |
| Data Quality | 44 | ✅ |
| Connection Pool | 29 | ✅ |
| Observability | 29 | ✅ |
| Load Testing | 13 | ✅ |
| Migrations | 10 | ✅ |
| API Keys | 70 | ✅ |
| Symbols | 19 | ✅ |
| Comprehensive | 124 | ✅ |
| Crypto | 24 | ✅ |
| **Total** | **347** | **✅** |

---

## 🔗 Test Organization

Tests are organized by phase and feature:

```
tests/
├── test_phase_6_4.py              # Comprehensive tests
├── test_phase_6_5.py              # Crypto support
├── test_api_key_*.py              # API key tests
├── test_migration_service.py      # Database tests
├── test_observability.py          # Monitoring tests
├── test_phase2_*.py               # Error handling tests
└── ...
```

---

## 📚 Code Style

- **Language**: Python 3.8+
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **Style**: PEP 8 (use `black` for formatting)
- **Type Hints**: Yes, comprehensive
- **Docstrings**: Yes, all public APIs

See [Contributing Guide](CONTRIBUTING.md) for detailed guidelines.

---

## 🚀 Running Common Tasks

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Phase Tests
```bash
pytest tests/test_phase_6_4.py tests/test_phase_6_5.py -v
```

### Check Test Coverage
```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Start Development Server
```bash
python main.py
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
```

### Format Code
```bash
black src/ tests/
```

### Run Linting
```bash
pylint src/
```

---

## 🆘 Common Development Issues

### Tests Fail to Import
→ See [Testing Guide](TESTING.md) → "Troubleshooting"

### Can't Connect to Database
→ Check DATABASE_URL environment variable
→ See [Architecture Guide](ARCHITECTURE.md) → "Configuration"

### API Not Starting
→ Check logs: `python main.py`
→ See [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md)

### Test Takes Too Long
→ See [Testing Guide](TESTING.md) → "Performance"

---

## 📋 Development Checklist

Before committing code:

- [ ] Code follows style guidelines
- [ ] Tests pass: `pytest tests/`
- [ ] New tests added for new features
- [ ] Docstrings updated
- [ ] README updated if needed
- [ ] No hardcoded values
- [ ] No debug print statements
- [ ] Commit message is descriptive

See [Contributing Guide](CONTRIBUTING.md) for details.

---

## 🤝 Contributing

**Want to contribute?** Great! Follow these steps:

1. Read [Contributing Guide](CONTRIBUTING.md)
2. Set up development environment (above)
3. Make your changes
4. Write tests
5. Run test suite
6. Submit pull request

See [Contributing Guide](CONTRIBUTING.md) for complete process.

---

## 🎓 Learning Path

Recommended reading order:

1. [Architecture Guide](ARCHITECTURE.md) - Understand the system
2. [Contributing Guide](CONTRIBUTING.md) - Learn workflow
3. [Testing Guide](TESTING.md) - Understand testing approach
4. Code examples in tests
5. [Troubleshooting Guide](/docs/operations/TROUBLESHOOTING.md) - Common issues

---

**Status**: Production Ready ✅  
**Last Updated**: November 10, 2025
