# Market Data Warehouse & API

**Author:** Stephen Lopez  
**Status:** Ready to Build  
**Version:** v3.0 (Final - Polygon Only)  
**Infrastructure:** OptiPlex 3060 (16GB RAM, 1TB SSD, i3 8th gen) + Proxmox Debian 12

---

## 📌 Project Overview

A **single-source, production-grade OHLCV warehouse** for US stocks. Built for reliability, not complexity.

**Core Promise:** Validated historical data via Polygon.io. Daily auto-backfill. Fast queries for research and analysis. Foundation for future multi-asset expansion.

**Architecture:**
```
Polygon.io (US stocks only)
    ↓
[Async Fetcher + Validator]
    ↓
TimescaleDB (hypertable)
    ↓
FastAPI REST API
    ↓
Research notebooks, custom strategies, future projects
```

**Scope:** 
- US stocks only ($30/mo Polygon starter tier)
- Historical daily OHLCV via auto-backfill (runs nightly)
- Quality validation + gap detection
- Spot-checked against Yahoo Finance
- Backups + monitoring from Day 1

---

## 🎯 System Goals

- **Single authoritative source** for US stock OHLCV data
- **Strict validation** with gap detection (stock splits, dividends, halts)
- **Historical depth:** 5+ years, full retention forever
- **Daily auto-backfill** (no manual intervention)
- **Sub-100ms queries** for any symbol/date range
- **Automated backups** (weekly to external storage)
- **Data quality monitoring** (validation rate, staleness, gaps)
- **Low cost** ($30/mo + your hardware)
- **Extensible foundation** (add crypto/FX/indicators later without refactor)

---

## 🏗️ Technology Stack

### Framework: FastAPI
- Async I/O, auto-docs, Pydantic validation
- 5-10x faster than Flask
- Perfect for time-series queries

### Database: TimescaleDB (PostgreSQL)
- 3.5x faster writes than InfluxDB
- Hypertable auto-chunks by time
- Continuous aggregates: 1d→1w pre-computed (979x faster)
- Compression: 60%+ savings after 7 days
- Full SQL for complex queries

### Data Source: Polygon.io
- **Why single source for MVP:** 
  - Eliminates conflict resolution complexity
  - Clean, reliable data (used by professionals)
  - No need to average/weight multiple sources
  - Simpler validation logic
  - Lower rate limit concerns (150 req/min is plenty for daily backfill)
- **Upgrade path:** Once this works perfectly, add Binance/OANDA as Phase 2 without refactoring

### Utilities
- **Alembic:** Database schema versioning (migrations)
- **tenacity:** Exponential backoff retry logic
- **aiohttp:** Async HTTP client
- **pydantic:** Request/response validation
- **APScheduler:** Daily scheduler for auto-backfill

### Deployment
- **Docker Compose:** Local + Proxmox orchestration
- **Systemd:** Auto-start on reboot
- **Weekly pg_dump:** Automated backups to external storage

---

## 💾 Infrastructure & Backups

**Hardware:** OptiPlex 3060
- **CPU:** i3 8th gen (4 cores → 4 FastAPI workers)
- **RAM:** 16GB (8GB for OS/services, 8GB for TimescaleDB)
- **Storage:** 1TB SSD
  - 5 years × 500 stocks = ~20GB compressed (conservative)
  - Comfortable headroom

**Backup Strategy (Critical):**
```bash
# Weekly automated backup to external USB drive
# Cron job: every Sunday 3 AM

#!/bin/bash
BACKUP_DIR=/mnt/external-backup
DB_NAME=market_data
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Compressed dump (takes ~5 min, ~100MB file)
pg_dump -h localhost -U postgres $DB_NAME | \
  gzip > $BACKUP_DIR/market_data_$TIMESTAMP.sql.gz

# Keep last 12 backups, delete older
cd $BACKUP_DIR && \
  ls -t market_data_*.sql.gz | tail -n +13 | xargs rm -f

# Test restore monthly
pg_restore -d market_data_test -h localhost -U postgres $BACKUP_DIR/latest_backup.sql.gz
```

**Why this matters:**
- Database corruption = restore from last Sunday (max 7 days lost)
- Schema mistake = easy rollback
- Disaster recovery = documented, tested

---

## 📊 Data Quality Strategy

### Validation Rules (Every Candle)
```python
# Strict OHLCV constraints
assert high >= max(open, close), "High must bracket prices"
assert low <= min(open, close), "Low must bracket prices"
assert open > 0 and close > 0, "No zero/negative prices"
assert volume >= 0, "Volume non-negative"
assert price_change < 500%, "Reasonable intraday move (<500%)"
```

### Gap Detection (Identifies Issues)
```python
# Detects:
# - Weekend gaps (normal, expected)
# - Market halts (flag for review)
# - Stock splits (3-for-1 = 66% overnight gap)
# - Delisted symbols (gap never fills)
# - Data corruption (unreasonable gaps)

if gap > 10% and not is_weekend(date):
    log("⚠️ Large gap: possible split/halt")
    validation_notes = "flagged_large_gap"
```

### Volume Anomaly Detection
```python
# Flags:
# - Volume > 10x median = potential corruption
# - Volume < 10% of median = possible delisting warning

if volume > median_volume * 10:
    quality_score -= 0.2  # Not failed, just lower confidence
```

### Spot-Check Protocol (Before Week 1)
```python
# Pick 5 random dates: 2019, 2020, 2021, 2022, 2023
# For each date, compare Polygon vs Yahoo Finance for 3 symbols (AAPL, MSFT, SPY)

# Expected: Match within 0.2%
# If > 1%: Investigate (data lag, splits not adjusted)
# If > 5%: Don't use this source

# Document: "Polygon matches YF within 0.2% for stocks"
```

### Quality Score Calculation
```python
quality_score = 1.0

# Subtract for each issue found:
if not passed_ohlcv_constraints: quality_score -= 0.5
if flagged_large_gap: quality_score -= 0.2
if volume_anomaly: quality_score -= 0.1
if adjusted_for_split_dividend: quality_score -= 0.05

# Final range: 0.0-1.0
# Threshold for "validated": quality_score >= 0.85
```

---

## 🚀 5-Week MVP Implementation Plan

### **WEEK 0: Discovery & Validation (Before Coding)**

**Objective:** Verify data sources work, establish spot-check baseline

#### Day 1: Data Source Testing
```bash
# Test Polygon.io with 3 symbols across different eras

# Setup API
export POLYGON_API_KEY=your_key

# Test 1: AAPL (oldest, most reliable)
curl "https://api.polygon.io/v1/aggs/ticker/AAPL/range/1/day/2019-01-01/2019-12-31?apiKey=$POLYGON_API_KEY" | jq '.results | length'

# Expected: ~252 trading days
# If < 200: Data quality issue, investigate

# Test 2: Recent IPO (e.g., TSLA IPO in 2020)
curl "https://api.polygon.io/v1/aggs/ticker/TSLA/range/1/day/2019-01-01/2019-12-31?apiKey=$POLYGON_API_KEY"

# Expected: 0 results (IPO was June 2020), no error
# If error: API auth issue

# Test 3: Delisted symbol (e.g., GE spun off WAFD in 2020)
curl "https://api.polygon.io/v1/aggs/ticker/GE/range/1/day/2020-01-01/2020-12-31?apiKey=$POLYGON_API_KEY"

# Expected: Data present, no gaps around spin-off date
# If gap: Polygon has known issue, log it
```

#### Day 2: Spot-Check Against Yahoo Finance
```python
# Manual check: Pick 5 dates, compare prices

import yfinance as yf
import requests
import os

POLYGON_KEY = os.getenv('POLYGON_API_KEY')
TEST_DATES = ['2019-03-15', '2020-06-30', '2021-11-12', '2022-05-01', '2023-09-20']
TEST_SYMBOLS = ['AAPL', 'MSFT', 'SPY']

for symbol in TEST_SYMBOLS:
    print(f"\n{symbol}:")
    yf_data = yf.download(symbol, start='2019-01-01', end='2023-12-31', progress=False)
    
    for date in TEST_DATES:
        if date in yf_data.index.strftime('%Y-%m-%d'):
            yf_row = yf_data.loc[date]
            
            # Polygon API call
            poly_response = requests.get(
                f"https://api.polygon.io/v1/aggs/ticker/{symbol}/range/1/day/{date}/{date}",
                params={'apiKey': POLYGON_KEY}
            )
            
            if poly_response.ok:
                poly_candle = poly_response.json()['results'][0]
                
                # Compare
                yf_close = float(yf_row['Close'])
                poly_close = float(poly_candle['c'])
                diff_pct = abs((yf_close - poly_close) / yf_close) * 100
                
                status = "✓" if diff_pct < 0.5 else "⚠️" if diff_pct < 2 else "✗"
                print(f"  {date}: YF={yf_close:.2f}, Polygon={poly_close:.2f}, Diff={diff_pct:.3f}% {status}")

# Document results
# Expected output: All ✓ (within 0.5%)
# Save this as: data_validation_baseline.txt
```

#### Day 3: Check Rate Limits
```bash
# Verify we won't hit Polygon rate limits

# Assumption: 500 stocks, daily backfill
# Each symbol = 1 API call/day
# 500 calls/day = well under 150 req/min limit

# Test: Fetch 10 symbols in rapid succession
for symbol in AAPL MSFT GOOGL AMZN NVDA TSLA META AMD NFLX UBER; do
  curl -s "https://api.polygon.io/v1/aggs/ticker/$symbol/range/1/day/2024-01-01/2024-01-31?apiKey=$POLYGON_API_KEY" | jq '.status'
done

# Expected: All 200 responses within 10 seconds (plenty of headroom)
```

#### Day 4: Setup Backup Infrastructure
```bash
# Prepare external USB drive for backups
# On Proxmox:

# 1. Plug in external USB drive
# 2. Mount it
sudo mount /dev/sdb1 /mnt/external-backup

# 3. Create backup directory
sudo mkdir -p /mnt/external-backup/market-data-backups
sudo chown postgres:postgres /mnt/external-backup/market-data-backups

# 4. Test backup (manual, before cron)
pg_dump -h localhost -U postgres market_data | gzip > /mnt/external-backup/market-data-backups/test_backup.sql.gz

# Verify file size
ls -lh /mnt/external-backup/market-data-backups/

# Expected: ~100-200MB when compressed
```

**Week 0 Outcome:**
- ✓ Polygon data matches Yahoo Finance within 0.5%
- ✓ Rate limits verified (500 symbols = no problem)
- ✓ Backup infrastructure tested
- ✓ Document: "data_validation_baseline.txt" + "backup_test_results.txt"

---

### **WEEK 1: Database + Scheduler + Fetcher**

**Objective:** Get Polygon data flowing into TimescaleDB daily

#### Day 1-2: Project Setup + Alembic
```bash
mkdir market-data-api
cd market-data-api

python -m venv venv
source venv/bin/activate

pip install \
  fastapi uvicorn \
  sqlalchemy psycopg2-binary alembic \
  pydantic aiohttp tenacity \
  pandas apscheduler python-dotenv \
  pytest pytest-asyncio

# Initialize Alembic (schema versioning)
alembic init migrations

cat > .env << EOF
POLYGON_API_KEY=your_key
DATABASE_URL=postgresql://postgres:password@localhost:5432/market_data
DB_PASSWORD=password
LOG_LEVEL=INFO
EOF

# Start TimescaleDB
docker run -d \
  --name timescaledb \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  -v timescale_data:/var/lib/postgresql/data \
  timescale/timescaledb:latest-pg15

# Wait for it to be ready
sleep 5

# Create database
PGPASSWORD=password psql -h localhost -U postgres -c "CREATE DATABASE market_data;"
```

#### Day 2-3: Database Schema
```sql
-- sql/schema.sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE market_data (
    id BIGSERIAL,
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open DECIMAL(19,8) NOT NULL,
    high DECIMAL(19,8) NOT NULL,
    low DECIMAL(19,8) NOT NULL,
    close DECIMAL(19,8) NOT NULL,
    volume BIGINT NOT NULL,
    
    -- Source tracking
    source VARCHAR(20) DEFAULT 'polygon',
    
    -- Validation metadata
    validated BOOLEAN DEFAULT FALSE,
    quality_score NUMERIC(3,2) DEFAULT 0.00,
    validation_notes TEXT,
    gap_detected BOOLEAN DEFAULT FALSE,
    volume_anomaly BOOLEAN DEFAULT FALSE,
    
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (symbol, time)
);

-- Convert to hypertable (auto-partition by time)
SELECT create_hypertable(
    'market_data',
    'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

-- Indexes
CREATE INDEX idx_symbol_time ON market_data (symbol, time DESC);
CREATE INDEX idx_validated ON market_data (validated) WHERE validated = TRUE;
CREATE INDEX idx_gap_detected ON market_data (gap_detected) WHERE gap_detected = TRUE;

-- Validation audit log
CREATE TABLE validation_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    symbol VARCHAR(20),
    check_name VARCHAR(100),
    passed BOOLEAN,
    error_message TEXT,
    quality_score NUMERIC(3,2)
);

-- Import tracking (when backfill ran)
CREATE TABLE backfill_history (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20),
    start_date DATE,
    end_date DATE,
    records_imported INT,
    backfill_timestamp TIMESTAMPTZ DEFAULT NOW(),
    success BOOLEAN,
    error_details TEXT
);

-- Monitoring: last successful backfill per symbol
CREATE TABLE symbol_status (
    symbol VARCHAR(20) PRIMARY KEY,
    last_backfill_date DATE,
    last_backfill_success BOOLEAN,
    last_validation_score NUMERIC(3,2),
    data_freshness_days INT,
    latest_date_in_db DATE
);
```

```bash
# Create schema
PGPASSWORD=password psql -h localhost -U postgres -d market_data -f sql/schema.sql

# Initialize Alembic
# This creates migrations/ directory for future schema changes
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

#### Day 3-4: Polygon Client (Single Source)
```python
# src/clients/polygon_client.py
import aiohttp
import logging
from typing import List, Dict
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class PolygonClient:
    """
    Polygon.io API client for US stocks
    Rate limit: 150 requests/minute (we use <10 for daily backfill)
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.polygon.io/v1"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def fetch_daily_range(
        self,
        symbol: str,
        start: str,
        end: str
    ) -> List[Dict]:
        """
        Fetch daily OHLCV from Polygon.
        
        Returns: [{'t': timestamp_ms, 'o': open, 'h': high, 'l': low, 'c': close, 'v': volume}]
        
        Args:
            symbol: Stock ticker (e.g., 'AAPL')
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
        
        Raises:
            ValueError: If API error or rate limit
        """
        url = f"{self.base_url}/aggs/ticker/{symbol}/range/1/day/{start}/{end}"
        
        params = {
            "apiKey": self.api_key,
            "sort": "asc",
            "limit": 50000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=30) as response:
                    
                    if response.status == 429:
                        raise ValueError("Rate limited (429) - too many requests")
                    
                    response.raise_for_status()
                    data = await response.json()
                    
                    if 'results' in data and data['results']:
                        logger.info(f"✓ Polygon: {len(data['results'])} candles for {symbol}")
                        return data['results']
                    
                    logger.warning(f"⚠️ No results for {symbol} ({start} to {end})")
                    return []
        
        except Exception as e:
            logger.error(f"✗ Polygon fetch error for {symbol}: {e}")
            raise
```

#### Day 4: Pydantic Models
```python
# src/models.py
from pydantic import BaseModel, validator
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

class OHLCVData(BaseModel):
    time: datetime
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    validated: bool = False
    quality_score: Decimal = Decimal('0.00')
    validation_notes: Optional[str] = None
    gap_detected: bool = False
    volume_anomaly: bool = False
    
    @validator('volume')
    def volume_must_be_non_negative(cls, v):
        if v < 0:
            raise ValueError("Volume cannot be negative")
        return v
    
    class Config:
        json_encoders = {Decimal: lambda v: float(v)}

class HistoricalDataResponse(BaseModel):
    symbol: str
    count: int
    start_date: datetime
    end_date: datetime
    data: List[dict]
    validation_rate: float  # Percentage validated
```

---

### **WEEK 2: Validation + Smart Backfill Scheduler**

**Objective:** Validate data, detect gaps, auto-backfill nightly

#### Day 5-6: Validation Service
```python
# src/services/validation_service.py
from decimal import Decimal
from typing import Tuple, List, Dict
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ValidationService:
    """Validate OHLCV candles with gap + anomaly detection"""
    
    def __init__(self):
        self.median_volumes = {}  # Track per symbol for anomaly detection
    
    def validate_ohlcv(self, data: dict) -> Tuple[bool, Decimal, List[str], bool, bool]:
        """
        Validate single OHLCV candle.
        
        Returns:
            (passed: bool, quality_score: Decimal, errors: List[str], gap_flagged: bool, volume_anomaly: bool)
        """
        errors = []
        checks_passed = 0
        total_checks = 6
        gap_flagged = False
        volume_anomaly = False
        
        try:
            o = Decimal(str(data['open']))
            h = Decimal(str(data['high']))
            l = Decimal(str(data['low']))
            c = Decimal(str(data['close']))
            v = Decimal(str(data['volume']))
        except (ValueError, TypeError, KeyError) as e:
            return False, Decimal('0.00'), [f"Invalid types: {e}"], False, False
        
        # Check 1: High >= Low
        if h >= l:
            checks_passed += 1
        else:
            errors.append(f"High ({h}) < Low ({l})")
        
        # Check 2: High >= max(O, C)
        max_oc = max(o, c)
        if h >= max_oc:
            checks_passed += 1
        else:
            errors.append(f"High ({h}) < max(O,C) ({max_oc})")
        
        # Check 3: Low <= min(O, C)
        min_oc = min(o, c)
        if l <= min_oc:
            checks_passed += 1
        else:
            errors.append(f"Low ({l}) > min(O,C) ({min_oc})")
        
        # Check 4: All prices > 0
        if all(p > 0 for p in [o, h, l, c]):
            checks_passed += 1
        else:
            errors.append("Prices must be > 0")
        
        # Check 5: Volume >= 0
        if v >= 0:
            checks_passed += 1
        else:
            errors.append(f"Volume negative: {v}")
        
        # Check 6: Price move < 500%
        if o > 0:
            pct = abs((c - o) / o) * 100
            if pct <= Decimal('500'):
                checks_passed += 1
            else:
                errors.append(f"Extreme move: {pct:.1f}%")
        
        passed = len(errors) == 0
        quality_score = Decimal(checks_passed) / Decimal(total_checks)
        
        return passed, quality_score, errors, gap_flagged, volume_anomaly
    
    def detect_gap(
        self,
        current_date: datetime,
        previous_date: datetime,
        current_open: Decimal,
        previous_close: Decimal
    ) -> Tuple[bool, str]:
        """
        Detect gaps and classify them.
        
        Returns: (is_significant_gap, reason)
        """
        days_diff = (current_date.date() - previous_date.date()).days
        
        # Calculate gap percentage
        if previous_close > 0:
            gap_pct = abs((current_open - previous_close) / previous_close) * 100
        else:
            gap_pct = 0
        
        # Classify gap
        
        # Normal: Weekend gap (Fri→Mon, 2-3 days, any pct is normal)
        is_weekend = previous_date.weekday() == 4 and current_date.weekday() == 0
        if is_weekend:
            return False, f"Weekend gap: {days_diff} days, {gap_pct:.2f}%"
        
        # Normal: Holiday (3+ days, gaps happen)
        if days_diff >= 3:
            return False, f"Holiday gap: {days_diff} days, {gap_pct:.2f}%"
        
        # Normal: Consecutive days, small gap (<2%)
        if gap_pct < 2:
            return False, None
        
        # Significant: 2-5% gap (market volatility, dividend, minor event)
        if gap_pct < 5:
            return True, f"Moderate gap: {gap_pct:.2f}% (possible dividend/corporate event)"
        
        # Large: >5% gap (stock split, major event, or corruption)
        if gap_pct < 10:
            return True, f"Large gap: {gap_pct:.2f}% (possible 2-for-1 split or major event)"
        
        # Extreme: >10% gap (data corruption or major distress)
        return True, f"Extreme gap: {gap_pct:.2f}% (possible data corruption, needs review)"
    
    def detect_volume_anomaly(
        self,
        symbol: str,
        volume: Decimal,
        median_volume: Decimal
    ) -> Tuple[bool, str]:
        """
        Detect volume anomalies (spikes, droughts).
        
        Returns: (is_anomaly, reason)
        """
        if median_volume == 0:
            return False, None
        
        volume_ratio = float(volume) / float(median_volume)
        
        # Normal: within 0.5x to 10x median
        if 0.5 <= volume_ratio <= 10:
            return False, None
        
        # Anomaly: <50% of median (delisting warning, low liquidity)
        if volume_ratio < 0.5:
            return True, f"Low volume: {volume_ratio:.1f}x median (possible delisting warning)"
        
        # Anomaly: >10x median (corruption or major event)
        if volume_ratio > 10:
            return True, f"High volume: {volume_ratio:.1f}x median (possible data spike or manipulation)"
        
        return False, None
```

#### Day 6-7: Database Service + Gap Detection
```python
# src/services/database_service.py
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from typing import List, Dict, Optional
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self, database_url: str):
        self.engine = create_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=20
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def bulk_insert_ohlcv(self, records: List[Dict]) -> int:
        """Insert validated OHLCV records"""
        session = self.SessionLocal()
        inserted = 0
        
        for record in records:
            try:
                query = text("""
                    INSERT INTO market_data (
                        time, symbol, open, high, low, close, volume,
                        validated, quality_score, validation_notes,
                        gap_detected, volume_anomaly
                    ) VALUES (
                        :time, :symbol, :open, :high, :low, :close, :volume,
                        :validated, :quality_score, :validation_notes,
                        :gap_detected, :volume_anomaly
                    )
                    ON CONFLICT (symbol, time)
                    DO UPDATE SET
                        quality_score = EXCLUDED.quality_score,
                        validated = EXCLUDED.validated,
                        gap_detected = EXCLUDED.gap_detected,
                        volume_anomaly = EXCLUDED.volume_anomaly
                """)
                
                session.execute(query, record)
                inserted += 1
            
            except Exception as e:
                logger.warning(f"Skip record: {e}")
                session.rollback()
        
        session.commit()
        session.close()
        
        logger.info(f"✓ Inserted {inserted}/{len(records)} records")
        return inserted
    
    def get_import_gaps(
        self,
        symbol: str,
        start: str,
        end: str
    ) -> List[str]:
        """Find missing trading dates in database"""
        session = self.SessionLocal()
        
        try:
            result = session.execute(text("""
                SELECT DISTINCT date_trunc('day', time)::date
                FROM market_data
                WHERE symbol = :symbol
                  AND time >= :start
                  AND time <= :end
                ORDER BY 1
            """), {"symbol": symbol, "start": start, "end": end})
            
            imported_dates = set(row[0] for row in result)
            all_dates = pd.date_range(start, end, freq='B')  # 'B' = business days only
            
            gaps = [
                d.strftime('%Y-%m-%d')
                for d in all_dates
                if d.date() not in imported_dates
            ]
            
            if gaps:
                logger.info(f"⚠️ {symbol}: {len(gaps)} missing trading dates")
            
            return gaps
        finally:
            session.close()
    
    def get_historical_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        validated_only: bool = True,
        min_quality: float = 0.85
    ) -> List[Dict]:
        """Query historical data"""
        session = self.SessionLocal()
        
        try:
            sql = """
                SELECT time, symbol, open, high, low, close, volume,
                       quality_score, validated, gap_detected, volume_anomaly
                FROM market_data
                WHERE symbol = :symbol
                  AND time >= :start_date
                  AND time <= :end_date
            """
            
            params = {
                "symbol": symbol,
                "start_date": f"{start_date}T00:00:00Z",
                "end_date": f"{end_date}T23:59:59Z"
            }
            
            if validated_only:
                sql += " AND validated = true AND quality_score >= :min_quality"
                params["min_quality"] = min_quality
            
            sql += " ORDER BY time ASC"
            
            result = session.execute(text(sql), params)
            rows = result.fetchall()
            
            logger.info(f"✓ Retrieved {len(rows)} candles for {symbol}")
            
            return [
                {
                    "timestamp": str(row[0]),
                    "symbol": row[1],
                    "open": float(row[2]),
                    "high": float(row[3]),
                    "low": float(row[4]),
                    "close": float(row[5]),
                    "volume": int(row[6]),
                    "quality_score": float(row[7]),
                    "validated": row[8],
                    "gap_detected": row[9],
                    "volume_anomaly": row[10]
                }
                for row in rows
            ]
        
        except Exception as e:
            logger.error(f"Query error: {e}")
            return []
        finally:
            session.close()
    
    def update_symbol_status(self, symbol: str, latest_date: str, quality_score: float):
        """Update monitoring table"""
        session = self.SessionLocal()
        
        try:
            query = text("""
                INSERT INTO symbol_status (symbol, last_backfill_date, last_backfill_success, last_validation_score, latest_date_in_db)
                VALUES (:symbol, NOW()::date, true, :quality_score, :latest_date::date)
                ON CONFLICT (symbol)
                DO UPDATE SET
                    last_backfill_date = NOW()::date,
                    last_backfill_success = true,
                    last_validation_score = :quality_score,
                    latest_date_in_db = :latest_date::date
            """)
            
            session.execute(query, {"symbol": symbol, "quality_score": quality_score, "latest_date": latest_date})
            session.commit()
        finally:
            session.close()
```

#### Day 7-9: Scheduler + Auto-Backfill
```python
# src/scheduler.py
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from src.clients.polygon_client import PolygonClient
from src.services.validation_service import ValidationService
from src.services.database_service import DatabaseService
import logging
import os
import json

logger = logging.getLogger(__name__)

class AutoBackfillScheduler:
    """
    Daily automatic backfill at 2 AM.
    
    Logic:
    1. For each symbol in tracking list
    2. Find missing dates (gaps)
    3. Fetch from Polygon
    4. Validate + detect gaps/anomalies
    5. Store in DB
    6. Update symbol_status
    """
    
    def __init__(self, polygon_key: str, db_url: str):
        self.client = PolygonClient(polygon_key)
        self.db = DatabaseService(db_url)
        self.validator = ValidationService()
        
        self.scheduler = BackgroundScheduler()
        
        # Register job: every day at 2 AM
        self.scheduler.add_job(
            self._backfill_job,
            CronTrigger(hour=2, minute=0),
            id='daily_backfill',
            name='Daily Polygon.io backfill',
            misfire_grace_time=600
        )
    
    def start(self):
        """Start scheduler (call on app startup)"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✓ Auto-backfill scheduler started (runs daily at 2 AM)")
    
    async def _backfill_job(self):
        """Job function: backfill each symbol"""
        logger.info("📊 Daily backfill starting...")
        
        symbols = self._get_symbols_to_backfill()
        
        for symbol in symbols:
            try:
                await self._backfill_symbol(symbol)
            except Exception as e:
                logger.error(f"✗ Backfill failed for {symbol}: {e}")
                self.db.update_symbol_status(symbol, None, 0.0)  # Mark as failed
    
    async def _backfill_symbol(self, symbol: str):
        """Backfill single symbol"""
        
        # Look back 5 years for backfill
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365*5)
        
        logger.info(f"Backfilling {symbol}...")
        
        # Find gaps
        gaps = self.db.get_import_gaps(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if not gaps:
            logger.info(f"✓ {symbol} already complete")
            return
        
        logger.info(f"  {len(gaps)} missing dates, batching...")
        
        # Process in 365-day chunks (yearly)
        for i in range(0, len(gaps), 365):
            batch = gaps[i:i+365]
            batch_start = batch[0]
            batch_end = batch[-1]
            
            try:
                # Fetch from Polygon
                logger.info(f"  Fetching {symbol} ({batch_start} to {batch_end})...")
                candles = await self.client.fetch_daily_range(symbol, batch_start, batch_end)
                
                if not candles:
                    logger.warning(f"  No data for {symbol}")
                    continue
                
                # Validate + enrich
                validated_records = []
                previous_candle = None
                volumes = [float(c['v']) for c in candles]
                median_volume = sorted(volumes)[len(volumes)//2] if volumes else 0
                
                quality_scores = []
                
                for candle in candles:
                    passed, quality_score, errors, _, _ = self.validator.validate_ohlcv(candle)
                    
                    # Gap detection
                    gap_detected = False
                    gap_reason = None
                    if previous_candle:
                        gap_detected, gap_reason = self.validator.detect_gap(
                            datetime.fromtimestamp(candle['t'] / 1000),
                            datetime.fromtimestamp(previous_candle['t'] / 1000),
                            candle['o'],
                            previous_candle['c']
                        )
                    
                    # Volume anomaly
                    vol_anomaly, vol_reason = self.validator.detect_volume_anomaly(
                        symbol,
                        candle['v'],
                        median_volume
                    )
                    
                    notes = []
                    if errors:
                        notes.extend(errors)
                    if gap_reason:
                        notes.append(gap_reason)
                    if vol_reason:
                        notes.append(vol_reason)
                    
                    record = {
                        'time': datetime.fromtimestamp(candle['t'] / 1000),
                        'symbol': symbol,
                        'open': candle['o'],
                        'high': candle['h'],
                        'low': candle['l'],
                        'close': candle['c'],
                        'volume': candle['v'],
                        'validated': passed,
                        'quality_score': float(quality_score),
                        'validation_notes': '; '.join(notes) if notes else None,
                        'gap_detected': gap_detected,
                        'volume_anomaly': vol_anomaly
                    }
                    
                    validated_records.append(record)
                    previous_candle = candle
                    quality_scores.append(float(quality_score))
                
                # Bulk insert
                inserted = self.db.bulk_insert_ohlcv(validated_records)
                avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
                
                # Update status
                latest_date = max([c['t'] for c in candles])
                latest_datetime = datetime.fromtimestamp(latest_date / 1000)
                self.db.update_symbol_status(symbol, latest_datetime.strftime('%Y-%m-%d'), avg_quality)
                
                logger.info(f"  ✓ {symbol}: {inserted} records, quality={avg_quality:.2f}")
            
            except Exception as e:
                logger.error(f"  ✗ Batch failed for {symbol} ({batch_start}): {e}")
    
    def _get_symbols_to_backfill(self) -> List[str]:
        """Get list of symbols to backfill"""
        # Hardcoded for MVP; later read from config file
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX', 'AMD', 'CRM',
            'SPY', 'QQQ', 'IWM', 'EEM', 'VTI',
        ]
```

#### Day 9-10: Testing
```python
# tests/test_validation.py
import pytest
from src.services.validation_service import ValidationService
from decimal import Decimal

class TestValidation:
    
    def test_valid_ohlcv(self):
        service = ValidationService()
        data = {'open': 100, 'high': 105, 'low': 95, 'close': 102, 'volume': 1000}
        passed, score, errors, gap, vol_anom = service.validate_ohlcv(data)
        
        assert passed is True
        assert score == Decimal('1.0')
        assert errors == []
    
    def test_gap_weekend(self):
        service = ValidationService()
        from datetime import datetime
        
        fri = datetime(2024, 1, 12)  # Friday
        mon = datetime(2024, 1, 15)  # Monday
        
        is_sig, reason = service.detect_gap(mon, fri, Decimal('100'), Decimal('100'))
        assert is_sig is False  # Weekend gap is normal
    
    def test_gap_large(self):
        service = ValidationService()
        from datetime import datetime
        
        day1 = datetime(2024, 1, 12)  # Friday
        day2 = datetime(2024, 1, 15)  # Monday
        
        # 20% gap (possible split)
        is_sig, reason = service.detect_gap(day2, day1, Decimal('80'), Decimal('100'))
        assert is_sig is True
        assert 'gap' in reason.lower()
```

---

### **WEEK 3: FastAPI + REST Endpoints**

**Objective:** Build queryable API with monitoring

#### Day 10-11: FastAPI Application
```python
# main.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
from src.services.database_service import DatabaseService
from src.scheduler import AutoBackfillScheduler
from contextlib import asynccontextmanager
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Initialize services
db = DatabaseService(os.getenv('DATABASE_URL'))
scheduler = AutoBackfillScheduler(os.getenv('POLYGON_API_KEY'), os.getenv('DATABASE_URL'))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    scheduler.start()
    logger.info("✓ App startup complete")
    yield
    # Shutdown
    if scheduler.scheduler.running:
        scheduler.scheduler.shutdown()
    logger.info("✓ App shutdown")

app = FastAPI(
    title="Market Data API",
    description="Validated US stock OHLCV warehouse",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health():
    """System health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "scheduler_running": scheduler.scheduler.running
    }

@app.get("/api/v1/status")
async def get_status():
    """System monitoring endpoint"""
    # Query database for stats
    session = db.SessionLocal()
    
    try:
        # Count symbols
        symbols_result = session.execute(text("""
            SELECT COUNT(DISTINCT symbol) FROM market_data
        """))
        symbol_count = symbols_result.scalar() or 0
        
        # Latest date in DB
        latest_result = session.execute(text("""
            SELECT MAX(time) FROM market_data
        """))
        latest_date = latest_result.scalar()
        
        # Validation rate
        validation_result = session.execute(text("""
            SELECT COUNT(*) FILTER (WHERE validated = TRUE) as valid_count,
                   COUNT(*) as total_count
            FROM market_data
        """))
        valid_count, total_count = validation_result.first()
        validation_rate = (valid_count / total_count * 100) if total_count > 0 else 0
        
        # Gap-flagged records
        gap_result = session.execute(text("""
            SELECT COUNT(*) FROM market_data WHERE gap_detected = TRUE
        """))
        gap_count = gap_result.scalar() or 0
        
        return {
            "api_version": "1.0.0",
            "status": "healthy",
            "database": {
                "symbols_available": symbol_count,
                "latest_data": latest_date.isoformat() if latest_date else None,
                "total_records": total_count,
                "validation_rate_pct": round(validation_rate, 2)
            },
            "data_quality": {
                "records_with_gaps_flagged": gap_count,
                "scheduler_status": "running" if scheduler.scheduler.running else "stopped",
                "last_backfill": "check symbol_status table"
            }
        }
    
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return {"status": "error", "detail": str(e)}
    finally:
        session.close()

@app.get("/api/v1/historical/{symbol}")
async def get_historical_data(
    symbol: str,
    start: str = Query(..., description="Start date YYYY-MM-DD"),
    end: str = Query(..., description="End date YYYY-MM-DD"),
    validated_only: bool = Query(True, description="Filter to validated candles"),
    min_quality: float = Query(0.85, ge=0, le=1, description="Minimum quality score")
):
    """
    Fetch historical OHLCV data.
    
    Example: GET /api/v1/historical/AAPL?start=2022-01-01&end=2023-12-31
    """
    try:
        data = db.get_historical_data(symbol, start, end, validated_only, min_quality)
        
        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {symbol} ({start} to {end})"
            )
        
        return {
            "symbol": symbol,
            "start_date": start,
            "end_date": end,
            "count": len(data),
            "data": data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=4)
```

#### Day 11-12: Unit Tests
```python
# tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_status_endpoint():
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert "database" in data
    assert "data_quality" in data

def test_historical_missing_params():
    response = client.get("/api/v1/historical/AAPL")
    assert response.status_code == 422  # Validation error

def test_historical_invalid_symbol():
    response = client.get(
        "/api/v1/historical/ZZZZZ",
        params={"start": "2022-01-01", "end": "2023-12-31"}
    )
    assert response.status_code == 404
```

#### Day 12-13: Documentation
- Auto-generated OpenAPI at `/docs`
- README with examples
- Deployment guide

---

### **WEEK 4: Docker Deployment + Backup Setup**

**Objective:** Production deployment on Proxmox

#### Day 14-15: Docker Setup
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: market_data
    ports:
      - "5432:5432"
    volumes:
      - db_data:/var/lib/postgresql/data
      - ./sql/schema.sql:/docker-entrypoint-initdb.d/schema.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  api:
    build: .
    depends_on:
      timescaledb:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://postgres:${DB_PASSWORD}@timescaledb:5432/market_data
      POLYGON_API_KEY: ${POLYGON_API_KEY}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    ports:
      - "8000:8000"
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

volumes:
  db_data:
```

#### Day 15-16: Deploy to Proxmox
```bash
# On Proxmox VM
sudo apt update && sudo apt install -y docker.io docker-compose git

git clone <your-repo>
cd market-data-api

# Setup external backup drive
sudo mkdir -p /mnt/external-backup
# Plug in USB drive and mount it

cp .env.example .env
# Edit .env with your keys

docker-compose up -d

# Verify
docker-compose logs -f api
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/status
```

#### Day 16-17: Systemd Service + Backup Cron
```ini
# /etc/systemd/system/market-data-api.service
[Unit]
Description=Market Data API with TimescaleDB
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=/opt/market-data-api
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
RemainAfterExit=yes
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo cp /etc/systemd/system/market-data-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable market-data-api
sudo systemctl start market-data-api
sudo systemctl status market-data-api
```

```bash
# /opt/market-data-api/backup.sh (automated weekly backup)
#!/bin/bash

set -e

BACKUP_DIR="/mnt/external-backup/market-data-backups"
DB_NAME="market_data"
DB_HOST="localhost"
DB_USER="postgres"
DB_PASSWORD=${DB_PASSWORD}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

echo "[$(date)] Starting backup..."

# Compressed dump
PGPASSWORD=$DB_PASSWORD pg_dump -h $DB_HOST -U $DB_USER $DB_NAME | \
  gzip > $BACKUP_DIR/market_data_$TIMESTAMP.sql.gz

FILE_SIZE=$(du -h $BACKUP_DIR/market_data_$TIMESTAMP.sql.gz | cut -f1)
echo "[$(date)] Backup complete: $FILE_SIZE"

# Keep last 12 backups
cd $BACKUP_DIR
ls -t market_data_*.sql.gz | tail -n +13 | xargs -r rm -f

echo "[$(date)] Backup job finished"
```

```bash
# Cron: Sunday 3 AM
(crontab -l 2>/dev/null; echo "0 3 * * 0 /opt/market-data-api/backup.sh") | crontab -
```

#### Day 17-18: First Backfill + Validation
```bash
# Manual backfill to test everything
docker-compose exec api python -c "
from src.scheduler import AutoBackfillScheduler
import asyncio
import os

scheduler = AutoBackfillScheduler(
    os.getenv('POLYGON_API_KEY'),
    os.getenv('DATABASE_URL')
)

# Run backfill manually
asyncio.run(scheduler._backfill_job())
"

# Check status
curl http://localhost:8000/api/v1/status

# Spot-check a symbol
curl "http://localhost:8000/api/v1/historical/AAPL?start=2023-01-01&end=2023-12-31" | jq '.data | .[0:3]'

# Verify backup works
/opt/market-data-api/backup.sh

# Test restore (monthly)
pg_restore -d market_data_test -h localhost -U postgres /mnt/external-backup/market-data-backups/latest.sql.gz
```

---

## 📋 Project Structure

```
market-data-api/
├── main.py                         # FastAPI entry point
├── requirements.txt                # Dependencies
├── Dockerfile                      # Container image
├── docker-compose.yml              # Orchestration
├── .env.example                    # Template
├── backup.sh                       # Weekly backup script
├── .gitignore
├── README.md
├── sql/
│   └── schema.sql                  # Database schema
├── src/
│   ├── __init__.py
│   ├── clients/
│   │   ├── __init__.py
│   │   └── polygon_client.py       # Polygon.io client
│   ├── services/
│   │   ├── __init__.py
│   │   ├── validation_service.py   # OHLCV + gap detection
│   │   └── database_service.py     # Database operations
│   ├── models.py                   # Pydantic schemas
│   └── scheduler.py                # Daily auto-backfill
├── migrations/
│   └── versions/                   # Alembic schema versions
├── tests/
│   ├── __init__.py
│   ├── test_validation.py
│   ├── test_api.py
│   └── test_database.py
└── logs/                           # Docker-mounted log directory
```

---

## 🚀 Implementation Checklist

### **Week 0: Discovery (Before Coding)**
- [ ] Test Polygon.io with AAPL (5 years)
- [ ] Spot-check against Yahoo Finance (5 dates × 3 symbols)
- [ ] Verify rate limits (10 requests/sec = OK)
- [ ] Setup external backup USB drive
- [ ] Document results in data_validation_baseline.txt

### **Week 1: Foundation**
- [ ] Clone/scaffold project
- [ ] Setup Docker + TimescaleDB
- [ ] Create schema with Alembic
- [ ] Implement Polygon client
- [ ] Test client with 1 symbol

### **Week 2: Validation + Scheduler**
- [ ] Implement validation service (OHLCV + gaps + volume)
- [ ] Implement database service
- [ ] Implement APScheduler (daily 2 AM)
- [ ] Backfill test with 5 symbols
- [ ] Verify gap detection working
- [ ] Verify quality scores calculated

### **Week 3: API**
- [ ] Build FastAPI app
- [ ] Implement /health, /status, /historical endpoints
- [ ] Write unit tests
- [ ] Test endpoint manually (curl)
- [ ] Verify OpenAPI docs at /docs

### **Week 4: Production**
- [ ] Build Docker images
- [ ] Docker Compose locally (full test)
- [ ] Deploy to Proxmox VM
- [ ] Setup systemd service (auto-start)
- [ ] Setup backup cron job
- [ ] Full backfill production database
- [ ] Test backup + restore
- [ ] Monitor first week of auto-backfills

---

## ⚠️ Security Notes

```python
"""
SECURITY WARNINGS:
- API has ZERO authentication
- Do NOT expose to internet
- Only use on trusted LAN (Proxmox internal)
- Future: Add API key auth + rate limiting
"""
```

---

## 📊 Success Criteria (End of Week 4)

✅ Backfill 5+ years for 15+ US stocks  
✅ >95% validation success rate  
✅ Gap detection working (flags splits, anomalies)  
✅ Query <100ms for any symbol/date  
✅ Auto-backfill runs daily at 2 AM  
✅ Weekly backups working + tested restore  
✅ Status endpoint shows all metrics  
✅ OpenAPI docs complete  
✅ Systemd service auto-starts on reboot  
✅ Data spot-checked against Yahoo Finance (matches within 0.5%)  

**Result:** Production-ready US stock data warehouse. Single source of truth. Ready for research, analysis, and future strategy integration.

---

## 💰 Real Cost Breakdown

| Item | Cost | Notes |
|---|---|---|
| Polygon.io Starter | $29.99/mo | 150 req/min, sufficient for daily backfill |
| Proxmox + OptiPlex | $0 | You own it |
| TimescaleDB | $0 | Open source |
| FastAPI | $0 | Open source |
| Docker | $0 | Open source |
| **Total** | **~$30/mo** | Stays this way with 500 symbols |

*If you later need Polygon Pro ($199/mo) for minute-level data or 1000+ symbols, that's future planning, not MVP.*

---

## 🔮 Future Expansion (No Refactoring Needed)

**Phase 2: Multi-Timeframe Aggregates (Week 5-6)**
- Continuous aggregates: 1d→5d→1w (979x faster queries)
- Derive minute/5m/hourly from daily (for future)

**Phase 3: Crypto + FX (Week 7-8)**
- Add Binance API client (like Polygon but for crypto)
- Add OANDA API client (for FX)
- Multi-source conflict resolution (from early notes)

**Phase 4: Indicators + ML (Week 9+)**
- Pre-compute RSI, MACD, Bollinger Bands
- Store in separate table
- API endpoints for indicator queries
- Foundation for price prediction models

**All of this is possible without touching current schema or API.**

---

## 🎯 Next Steps

1. **Create GitHub repo** with this structure
2. **Start Week 0:** Test Polygon data
3. **Gather API keys:** Polygon signup ($29.99)
4. **Setup OptiPlex:** Mount backup drive, prepare Proxmox
5. **Week 1 Day 1:** Clone project, start building

**This is buildable, testable, and shippable in 4-5 weeks.**

You have no unknowns. Execute.
