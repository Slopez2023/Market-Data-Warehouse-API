# Market Data Service - Complete Implementation Plan

## Executive Summary

Separate microservice responsible for collecting, validating, and persisting market data. Feeds shared PostgreSQL database that the API reads from. Decouples data collection from API serving concerns.

---

## 1. Architecture Overview

### System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    MARKET DATA SERVICE                       │
│  (Runs independently, scales independently)                  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Scheduler   │  │  Collectors  │  │  Validators  │       │
│  │  (APScheduler)  │  (yfinance,  │  │  (quality    │       │
│  │              │  │   Finnhub,   │  │   checks)    │       │
│  │  - Daily     │  │   FRED)      │  │              │       │
│  │  - Recurring │  │              │  │  - Gap detect│       │
│  │  - Backfill  │  │              │  │  - Outliers  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                       │                                       │
│                   (write)                                     │
│                       │                                       │
└───────────────────────┼───────────────────────────────────────┘
                        │
                PostgreSQL Database
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
    market_data    dividends       earnings
    fundamentals   technical_indicators
    news           options_iv
        │               │               │
        │ (reads)       │ (reads)       │ (reads)
        │               │               │
        └───────────────┼───────────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
   ┌────────────────────┐      ┌──────────────────┐
   │   API SERVICE      │      │  ML/Analytics    │
   │  (Fast endpoints)  │      │  (Feature eng.)  │
   │  - /quotes         │      │  - /predict      │
   │  - /fundamentals   │      │  - /backtest     │
   │  - /history        │      │  - /features     │
   └────────────────────┘      └──────────────────┘
```

### Service Responsibilities

**Market Data Service owns:**
- Collection scheduling (when to fetch)
- API integration (which sources)
- Data validation (quality checks)
- Error handling & retries
- Database writes
- Monitoring collection health

**API Service owns:**
- Read endpoints
- Caching
- Authentication
- Rate limiting
- Response formatting

**Shared responsibility:**
- PostgreSQL database schema
- Data modeling

---

## 2. Technology Stack

### Core
- **Language:** Python 3.9+
- **Framework:** FastAPI (for health checks, admin endpoints)
- **Scheduling:** APScheduler
- **Database:** psycopg2-binary (PostgreSQL adapter)
- **Async:** asyncio, aiohttp

### Dependencies
```
fastapi==0.104.1
uvicorn==0.24.0
apscheduler==3.10.4
psycopg2-binary==2.9.9
asyncpg==0.29.0
yfinance==0.2.32
pandas==2.1.3
aiohttp==3.9.1
tenacity==8.2.3
python-dotenv==1.0.0
pydantic==2.5.0
```

### Infrastructure
- **Container:** Docker
- **Orchestration:** docker-compose (dev), Kubernetes (prod)
- **Logging:** Python logging → stdout (containerized)
- **Monitoring:** Prometheus metrics

---

## 3. Service Structure

### Directory Layout
```
market-data-service/
├── main.py                          # Entry point
├── config.py                        # Configuration
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── src/
│   ├── __init__.py
│   ├── scheduler.py                 # APScheduler setup
│   ├── health.py                    # Health check endpoint
│   │
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py                  # Base collector class
│   │   ├── yfinance_collector.py    # Stock data
│   │   ├── finnhub_collector.py     # Analyst ratings
│   │   ├── fred_collector.py        # Economic data
│   │   └── coingecko_collector.py   # Crypto (future)
│   │
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── base.py                  # Base validator
│   │   ├── ohlcv_validator.py       # Price data checks
│   │   └── fundamental_validator.py
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py              # DB connection pool
│   │   └── repositories/
│   │       ├── market_data_repo.py
│   │       ├── dividend_repo.py
│   │       ├── earnings_repo.py
│   │       └── ...
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ohlcv.py                 # Data models
│   │   ├── fundamental.py
│   │   └── validation.py
│   │
│   └── jobs/
│       ├── __init__.py
│       ├── daily_jobs.py            # Daily collection
│       ├── weekly_jobs.py           # Weekly aggregation
│       ├── backfill_jobs.py         # Historical data
│       └── maintenance_jobs.py      # Cleanup, optimization
│
├── tests/
│   ├── test_collectors.py
│   ├── test_validators.py
│   └── test_storage.py
│
└── logs/
    └── (generated at runtime)
```

---

## 4. Core Components

### 4.1 Scheduler (APScheduler)

```python
# src/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def init_scheduler(app):
    """Initialize scheduler with all jobs"""
    
    # Daily collection at 4:30pm ET (market close)
    scheduler.add_job(
        daily_market_data_collection,
        'cron',
        hour=16,
        minute=30,
        timezone='US/Eastern',
        id='daily_market_data',
        coalesce=True,
        max_instances=1
    )
    
    # Weekly fundamentals update (Sunday 10pm)
    scheduler.add_job(
        weekly_fundamentals_update,
        'cron',
        day_of_week='sun',
        hour=22,
        id='weekly_fundamentals',
        max_instances=1
    )
    
    # Backfill new symbols (daily, low priority)
    scheduler.add_job(
        backfill_missing_data,
        'cron',
        hour=1,  # 1am ET
        id='backfill_data',
        max_instances=1
    )
    
    # Database maintenance (daily, off-hours)
    scheduler.add_job(
        maintenance_tasks,
        'cron',
        hour=3,
        id='maintenance',
        max_instances=1
    )
    
    scheduler.start()
    return scheduler
```

**Job definitions:**
- **Daily (4:30pm ET):** OHLCV, fundamentals, news, options IV
- **Weekly (Sunday 10pm):** Earnings, analyst ratings
- **Backfill (1am ET):** Historical gaps, new symbols
- **Maintenance (3am ET):** Cleanup, indexes, optimization

### 4.2 Base Collector Pattern

```python
# src/collectors/base.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any

class BaseCollector(ABC):
    """Abstract base for all data collectors"""
    
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.errors = []
        self.collected = 0
        
    async def collect(self) -> Dict[str, Any]:
        """Main collection orchestration"""
        results = {
            'source': self.source_name,
            'timestamp': datetime.now(),
            'symbols': self.symbols,
            'collected': 0,
            'errors': [],
            'data': []
        }
        
        for symbol in self.symbols:
            try:
                data = await self.fetch_data(symbol)
                
                # Validate before returning
                validated = await self.validate(data)
                if validated['valid']:
                    results['data'].append(validated['data'])
                    results['collected'] += 1
                else:
                    results['errors'].append({
                        'symbol': symbol,
                        'reason': validated['errors']
                    })
                    
            except Exception as e:
                logger.error(f"{self.source_name} {symbol}: {e}")
                results['errors'].append({
                    'symbol': symbol,
                    'reason': str(e)
                })
        
        return results
    
    @abstractmethod
    async def fetch_data(self, symbol: str) -> Any:
        """Fetch raw data from source"""
        pass
    
    @abstractmethod
    async def validate(self, data: Any) -> Dict[str, Any]:
        """Validate fetched data"""
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Source identifier"""
        pass
```

### 4.3 Collector Implementations

```python
# src/collectors/yfinance_collector.py
import yfinance as yf
from .base import BaseCollector

class YFinanceCollector(BaseCollector):
    """Collect stock data, dividends, splits, fundamentals"""
    
    @property
    def source_name(self) -> str:
        return 'yfinance'
    
    async def fetch_data(self, symbol: str):
        """Get OHLCV + fundamentals"""
        ticker = yf.Ticker(symbol)
        
        return {
            'symbol': symbol,
            'ohlcv': ticker.history(period='5d'),
            'fundamentals': ticker.info,
            'dividends': ticker.dividends,
            'splits': ticker.splits,
            'news': ticker.news,
            'options': self._get_options(ticker),
        }
    
    async def validate(self, data):
        """Check data quality"""
        # ... validation logic
        return {'valid': True, 'data': data}
    
    def _get_options(self, ticker):
        """Extract options chain"""
        try:
            expirations = ticker.options[:3]  # Nearest 3
            options = {}
            for exp in expirations:
                options[exp] = ticker.option_chain(exp)
            return options
        except:
            return {}
```

```python
# src/collectors/finnhub_collector.py
import aiohttp
from .base import BaseCollector

class FinnhubCollector(BaseCollector):
    """Analyst ratings, company profile, news"""
    
    def __init__(self, symbols, api_key):
        super().__init__(symbols)
        self.api_key = api_key
    
    @property
    def source_name(self) -> str:
        return 'finnhub'
    
    async def fetch_data(self, symbol: str):
        """Get analyst ratings & company data"""
        async with aiohttp.ClientSession() as session:
            endpoints = {
                'recommendations': f'https://finnhub.io/api/v1/stock/recommendation?symbol={symbol}&token={self.api_key}',
                'profile': f'https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={self.api_key}',
                'news': f'https://finnhub.io/api/v1/company-news?symbol={symbol}&from=2024-01-01&token={self.api_key}',
            }
            
            results = {}
            for name, url in endpoints.items():
                async with session.get(url) as resp:
                    if resp.status == 200:
                        results[name] = await resp.json()
            
            return {'symbol': symbol, **results}
```

### 4.4 Validator Pattern

```python
# src/validators/ohlcv_validator.py
from .base import BaseValidator
from datetime import datetime, timedelta
import pandas as pd

class OHLCVValidator(BaseValidator):
    """Validate OHLCV data quality"""
    
    RULES = {
        'price_positive': lambda h, l, c, o: all(x > 0 for x in [h, l, c, o]),
        'high_low': lambda h, l, c, o: h >= l,
        'volume_positive': lambda v: v >= 0,
        'no_gaps': lambda closes: abs(closes.pct_change().max()) < 0.15,  # 15% max gap
        'recent_data': lambda date: (datetime.now() - date).days < 2,
    }
    
    def validate(self, data):
        """Check all rules"""
        errors = []
        
        # Check each price rule
        for rule_name, rule_fn in self.RULES.items():
            try:
                if not rule_fn(*data):
                    errors.append(f"Rule failed: {rule_name}")
            except Exception as e:
                errors.append(f"Rule error {rule_name}: {e}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'quality_score': 1.0 - (len(errors) / len(self.RULES))
        }
```

### 4.5 Storage Layer

```python
# src/storage/database.py
import psycopg2
from psycopg2.pool import SimpleConnectionPool
import os

class Database:
    """Database connection management"""
    
    def __init__(self):
        self.pool = SimpleConnectionPool(
            minconn=2,
            maxconn=10,
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=int(os.getenv('DB_PORT', 5432))
        )
    
    def get_connection(self):
        return self.pool.getconn()
    
    def return_connection(self, conn):
        return self.pool.putconn(conn)
    
    def close_all(self):
        return self.pool.closeall()
```

```python
# src/storage/repositories/market_data_repo.py
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class MarketDataRepository:
    """CRUD operations for market_data table"""
    
    def __init__(self, db):
        self.db = db
    
    async def insert_batch(self, records: list) -> int:
        """Insert multiple records"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            
            query = """
            INSERT INTO market_data 
            (time, symbol, open, high, low, close, volume, source, fetched_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, time) DO UPDATE SET
                validated = FALSE,
                fetched_at = NOW()
            """
            
            from psycopg2.extras import execute_batch
            execute_batch(cursor, query, records, page_size=1000)
            
            conn.commit()
            inserted = cursor.rowcount
            logger.info(f"Inserted {inserted} market data records")
            return inserted
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Insert failed: {e}")
            raise
        finally:
            self.db.return_connection(conn)
    
    async def get_latest(self, symbol: str, limit: int = 100):
        """Get latest records"""
        conn = self.db.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM market_data WHERE symbol = %s ORDER BY time DESC LIMIT %s",
                (symbol, limit)
            )
            return cursor.fetchall()
        finally:
            self.db.return_connection(conn)
```

---

## 5. Job Definitions

### 5.1 Daily Collection Job

```python
# src/jobs/daily_jobs.py
import logging
from datetime import datetime
from src.collectors import YFinanceCollector, FinnhubCollector
from src.storage import Database, MarketDataRepository

logger = logging.getLogger(__name__)

async def daily_market_data_collection():
    """
    Run at 4:30pm ET (market close)
    
    Collects:
    - OHLCV (daily)
    - Dividends
    - Stock Splits
    - News
    - Options IV
    - Fundamentals (cached)
    """
    
    logger.info("Starting daily market data collection")
    start_time = datetime.now()
    
    db = Database()
    
    try:
        # Get symbols to collect
        symbols = get_active_symbols(db)
        logger.info(f"Collecting data for {len(symbols)} symbols")
        
        # yfinance collection
        yf_collector = YFinanceCollector(symbols)
        yf_results = await yf_collector.collect()
        
        logger.info(f"yfinance: {yf_results['collected']} symbols, {len(yf_results['errors'])} errors")
        
        # Store results
        repos = {
            'market_data': MarketDataRepository(db),
            'dividends': DividendRepository(db),
            'splits': SplitRepository(db),
            'news': NewsRepository(db),
            'options': OptionsRepository(db),
            'fundamentals': FundamentalRepository(db),
        }
        
        # Process and persist
        stored_count = await persist_collection_results(yf_results, repos)
        logger.info(f"Stored {stored_count} records")
        
        # Send metrics
        duration = (datetime.now() - start_time).total_seconds()
        await send_metrics({
            'job': 'daily_collection',
            'status': 'success',
            'symbols_collected': yf_results['collected'],
            'errors': len(yf_results['errors']),
            'duration_seconds': duration,
        })
        
    except Exception as e:
        logger.error(f"Daily collection failed: {e}", exc_info=True)
        await send_alert(f"Market data collection failed: {e}")
        raise
    
    finally:
        db.close_all()
```

### 5.2 Backfill Job

```python
# src/jobs/backfill_jobs.py
async def backfill_missing_data():
    """
    Fill gaps in historical data
    
    Runs daily at 1am ET (low priority)
    """
    
    logger.info("Starting backfill job")
    db = Database()
    
    try:
        # Find symbols with gaps
        gaps = await find_data_gaps(db)
        
        for symbol, missing_dates in gaps.items():
            logger.info(f"Backfilling {symbol}: {len(missing_dates)} days")
            
            collector = YFinanceCollector([symbol])
            
            # Fetch historical data
            start_date = min(missing_dates)
            end_date = max(missing_dates)
            
            data = await collector.fetch_historical(start_date, end_date)
            await persist_data(data, db)
        
        logger.info("Backfill complete")
        
    finally:
        db.close_all()
```

### 5.3 Maintenance Job

```python
# src/jobs/maintenance_jobs.py
async def maintenance_tasks():
    """
    Database and system maintenance
    
    - Vacuum (reclaim space)
    - Analyze (optimizer stats)
    - Reindex (performance)
    - Cleanup old logs
    """
    
    logger.info("Starting maintenance tasks")
    db = Database()
    conn = db.get_connection()
    
    try:
        cursor = conn.cursor()
        
        # Vacuum
        cursor.execute("VACUUM ANALYZE")
        logger.info("Vacuumed database")
        
        # Reindex
        cursor.execute("REINDEX INDEX idx_symbol_time")
        logger.info("Reindexed")
        
        # Delete old logs (keep 90 days)
        cursor.execute("DELETE FROM validation_log WHERE timestamp < NOW() - INTERVAL '90 days'")
        logger.info(f"Cleaned up logs: {cursor.rowcount} rows deleted")
        
        conn.commit()
        
    finally:
        db.return_connection(conn)
```

---

## 6. Configuration

### 6.1 Environment Variables (.env)

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=marketdata
DB_USER=postgres
DB_PASSWORD=your_password

# APIs
FINNHUB_API_KEY=your_key
FRED_API_KEY=your_key
ALPHA_VANTAGE_KEY=demo

# Service
SERVICE_NAME=market-data-service
SERVICE_PORT=8001
LOG_LEVEL=INFO
TIMEZONE=US/Eastern

# Symbols (comma-separated)
TRACKED_SYMBOLS=AAPL,MSFT,GOOGL,AMZN,TSLA

# Features
ENABLE_BACKFILL=true
ENABLE_MAINTENANCE=true
BACKFILL_HISTORY_DAYS=365

# Monitoring
METRICS_ENABLED=true
ALERT_EMAIL=ops@company.com
```

### 6.2 Config Class

```python
# config.py
from pydantic import BaseSettings
import os

class Settings(BaseSettings):
    # Database
    db_host: str = os.getenv('DB_HOST', 'localhost')
    db_port: int = int(os.getenv('DB_PORT', 5432))
    db_name: str = os.getenv('DB_NAME', 'marketdata')
    db_user: str = os.getenv('DB_USER', 'postgres')
    db_password: str = os.getenv('DB_PASSWORD', '')
    
    # APIs
    finnhub_key: str = os.getenv('FINNHUB_API_KEY', '')
    fred_key: str = os.getenv('FRED_API_KEY', '')
    
    # Service
    service_name: str = 'market-data-service'
    service_port: int = 8001
    log_level: str = 'INFO'
    
    # Features
    tracked_symbols: list = os.getenv('TRACKED_SYMBOLS', 'AAPL,MSFT').split(',')
    
    class Config:
        env_file = '.env'

settings = Settings()
```

---

## 7. Entry Point & Health Check

### 7.1 Main Application

```python
# main.py
import logging
from fastapi import FastAPI
from src.scheduler import init_scheduler
from src.health import router as health_router
from config import settings

logging.basicConfig(
    level=settings.log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title='Market Data Service',
    version='1.0.0',
    docs_url='/api/v1/docs'
)

@app.on_event('startup')
async def startup():
    """Initialize scheduler on startup"""
    logger.info("Starting Market Data Service")
    
    scheduler = init_scheduler(app)
    app.scheduler = scheduler
    
    logger.info("Scheduler initialized")
    logger.info(f"Tracking symbols: {settings.tracked_symbols}")

@app.on_event('shutdown')
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("Shutting down Market Data Service")
    if hasattr(app, 'scheduler'):
        app.scheduler.shutdown()

# Health check endpoints
app.include_router(health_router, prefix='/api/v1')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=settings.service_port)
```

### 7.2 Health Check Endpoint

```python
# src/health.py
from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get('/health')
async def health_check(app):
    """Service health status"""
    
    scheduler_running = app.scheduler.running if hasattr(app, 'scheduler') else False
    
    return {
        'status': 'healthy' if scheduler_running else 'unhealthy',
        'service': 'market-data-service',
        'timestamp': datetime.now().isoformat(),
        'scheduler_running': scheduler_running,
        'jobs': get_scheduled_jobs(app)
    }

@router.get('/metrics')
async def metrics(app):
    """Collection metrics"""
    return {
        'last_collection': app.state.get('last_collection_time'),
        'total_records': app.state.get('total_records_inserted', 0),
        'last_errors': app.state.get('last_errors', [])
    }
```

---

## 8. Error Handling & Retry Logic

### 8.1 Retry Decorator

```python
# src/utils/retry.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import logging

logger = logging.getLogger(__name__)

def retry_with_backoff(max_attempts=3):
    """Retry with exponential backoff"""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying {retry_state.fn_name}, attempt {retry_state.attempt_number}"
        )
    )

# Usage
@retry_with_backoff(max_attempts=3)
async def fetch_with_retry(symbol):
    return await yfinance_collector.fetch_data(symbol)
```

### 8.2 Error Tracking

```python
# src/utils/error_handler.py
class CollectionError:
    """Track collection errors for monitoring"""
    
    def __init__(self):
        self.errors = {
            'symbol': [],
            'source': [],
            'timestamp': [],
            'reason': []
        }
    
    def add(self, symbol, source, reason):
        self.errors['symbol'].append(symbol)
        self.errors['source'].append(source)
        self.errors['timestamp'].append(datetime.now())
        self.errors['reason'].append(reason)
    
    def get_recent(self, hours=24):
        """Get errors from last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [
            {
                'symbol': s,
                'source': src,
                'reason': r,
                'time': t
            }
            for s, src, r, t in zip(
                self.errors['symbol'],
                self.errors['source'],
                self.errors['reason'],
                self.errors['timestamp']
            )
            if t > cutoff
        ]
        return recent
```

---

## 9. Monitoring & Logging

### 9.1 Structured Logging

```python
# src/utils/logger.py
import json
import logging
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """Output logs as JSON for easy parsing"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

# Setup
logger = logging.getLogger()
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
```

### 9.2 Prometheus Metrics

```python
# src/utils/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

# Counters
collection_total = Counter(
    'market_data_collection_total',
    'Total collection attempts',
    ['source', 'status']
)

records_inserted = Counter(
    'market_data_inserted_total',
    'Total records inserted',
    ['table']
)

# Gauges
collection_duration = Histogram(
    'market_data_collection_seconds',
    'Collection duration in seconds',
    ['source']
)

last_collection = Gauge(
    'market_data_last_collection_timestamp',
    'Last successful collection timestamp'
)

# Usage
@collection_duration.labels(source='yfinance').time()
async def collect_data():
    # ... collection code
    collection_total.labels(source='yfinance', status='success').inc()
    records_inserted.labels(table='market_data').inc(count)
```

---

## 10. Docker Deployment

### 10.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/api/v1/health || exit 1

# Run service
CMD ["python", "main.py"]
```

### 10.2 docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: marketdata
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/sql:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  market-data-service:
    build: .
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: marketdata
      DB_USER: postgres
      DB_PASSWORD: password
      FINNHUB_API_KEY: ${FINNHUB_API_KEY}
      FRED_API_KEY: ${FRED_API_KEY}
      LOG_LEVEL: INFO
    ports:
      - "8001:8001"
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

volumes:
  postgres_data:
```

---

## 11. API Service Integration

### 11.1 API Reads from Shared DB

```python
# api/endpoints.py (in separate API service)
from fastapi import APIRouter
from src.storage import Database, MarketDataRepository

router = APIRouter(prefix="/api/v1", tags=["market_data"])

@router.get("/quotes/{symbol}")
async def get_quotes(symbol: str, days: int = 30):
    """Get latest OHLCV data (read from DB populated by Market Data Service)"""
    
    db = Database()
    repo = MarketDataRepository(db)
    
    data = await repo.get_latest(symbol, limit=days)
    
    return {
        'symbol': symbol,
        'quotes': data,
        'source': 'market-data-service'
    }

@router.get("/fundamentals/{symbol}")
async def get_fundamentals(symbol: str):
    """Get company fundamentals"""
    
    db = Database()
    repo = FundamentalRepository(db)
    
    data = await repo.get_by_symbol(symbol)
    
    return data
```

---

## 12. Deployment Strategies

### 12.1 Development (Local)

```bash
# Start both services
docker-compose up

# Market Data Service: http://localhost:8001/api/v1/health
# PostgreSQL: localhost:5432

# View logs
docker-compose logs -f market-data-service
```

### 12.2 Production (Kubernetes)

```yaml
# k8s/market-data-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: market-data-service
spec:
  replicas: 1  # Single instance (scheduler not distributed)
  selector:
    matchLabels:
      app: market-data-service
  template:
    metadata:
      labels:
        app: market-data-service
    spec:
      containers:
      - name: market-data-service
        image: your-registry/market-data-service:latest
        env:
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: market-data-config
              key: db_host
        - name: FINNHUB_API_KEY
          valueFrom:
            secretKeyRef:
              name: market-data-secrets
              key: finnhub_key
        ports:
        - containerPort: 8001
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8001
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 5
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
```

---

## 13. Implementation Timeline

### Phase 1: Foundation (Week 1-2)
- [ ] Setup project structure
- [ ] Implement base collector & validator
- [ ] Create database repositories
- [ ] Setup logging & monitoring

### Phase 2: Core Collectors (Week 2-3)
- [ ] yfinance collector (OHLCV, fundamentals, dividends)
- [ ] News & options collectors
- [ ] Daily job implementation
- [ ] Error handling & retries

### Phase 3: Integration (Week 3-4)
- [ ] Finnhub collector (analyst ratings)
- [ ] FRED collector (economic data)
- [ ] Backfill job
- [ ] Maintenance job

### Phase 4: Production Ready (Week 4-5)
- [ ] Docker setup
- [ ] Health checks & metrics
- [ ] Monitoring & alerting
- [ ] Documentation
- [ ] Load testing

### Phase 5: Migration (Week 5-6)
- [ ] Deploy separately from API
- [ ] Run in parallel with existing system
- [ ] Cutover & validation
- [ ] Monitoring & rollback plan

---

## 14. Success Criteria

### Operational
- ✅ 99.9% uptime (only scheduled downtime)
- ✅ Daily jobs complete in < 30 minutes
- ✅ Zero data loss (ACID compliance)
- ✅ < 5% collection error rate per symbol

### Data Quality
- ✅ All symbols updated daily
- ✅ OHLCV data validated
- ✅ No duplicate records
- ✅ Gap detection working

### Monitoring
- ✅ Health check endpoint responding
- ✅ Prometheus metrics exposed
- ✅ Logs structured & searchable
- ✅ Alerts firing for failures

---

## 15. Appendix: Quick Commands

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (dev mode)
python -m uvicorn main:app --reload --port 8001

# Run tests
pytest tests/

# Docker build
docker build -t market-data-service:latest .

# Docker run
docker run -p 8001:8001 \
  -e DB_HOST=localhost \
  -e FINNHUB_API_KEY=your_key \
  market-data-service:latest
```

### Monitoring
```bash
# Check service health
curl http://localhost:8001/api/v1/health

# View metrics
curl http://localhost:8001/metrics

# View logs (docker)
docker logs -f market-data-service

# Database queries
psql -h localhost -U postgres -d marketdata
> SELECT COUNT(*) FROM market_data;
> SELECT * FROM market_data WHERE symbol='AAPL' ORDER BY time DESC LIMIT 10;
```

### Troubleshooting
```bash
# Check if scheduler is running
curl http://localhost:8001/api/v1/health | jq .scheduler_running

# View recent errors
curl http://localhost:8001/api/v1/errors

# Manual collection trigger (development only)
curl -X POST http://localhost:8001/api/v1/admin/trigger-collection

# Database connection test
psql -h DB_HOST -U DB_USER -d DB_NAME -c "SELECT 1"
```

---

## Summary

This Market Data Service:
1. **Runs independently** - separate from API
2. **Collects continuously** - APScheduler handles timing
3. **Validates data** - quality checks prevent bad data
4. **Stores reliably** - ACID PostgreSQL guarantees
5. **Monitors itself** - health checks + metrics
6. **Scales operationally** - easy to deploy/restart
7. **Feeds the API** - shared database design

Start with **Phase 1-2**, get it working locally, then migrate to separate service when ready for production.
