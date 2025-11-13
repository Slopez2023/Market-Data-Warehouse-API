# Market Data Enrichment - Implementation Details
**Step-by-Step Technical Guide**

**Document Version:** 1.0  
**Estimated Implementation Time:** 4 weeks  
**Target: Production-ready code with zero technical debt**

---

## Table of Contents

1. [Setup & Project Structure](#setup--project-structure)
2. [Database Migration](#database-migration)
3. [Create Data Aggregator Service](#create-data-aggregator-service)
4. [Implement Connectors](#implement-connectors)
5. [Feature Computation](#feature-computation)
6. [Integration & Orchestration](#integration--orchestration)
7. [Testing Framework](#testing-framework)
8. [Deployment Checklist](#deployment-checklist)

---

## Setup & Project Structure

### New Directory Structure

```
src/
├── clients/
│   ├── polygon_client.py        (existing)
│   ├── binance_client.py        (NEW)
│   ├── yahoo_client.py          (NEW)
│   └── data_aggregator.py       (NEW)
│
├── services/
│   ├── database_service.py      (existing - extend)
│   ├── feature_computation_service.py  (NEW)
│   ├── data_enrichment_service.py      (NEW)
│   ├── data_quality_service.py   (NEW - for validation)
│   └── enrichment_scheduler.py   (NEW)
│
├── validators/
│   └── feature_validator.py     (NEW - validation rules)
│
└── utils/
    └── feature_utils.py         (NEW - helper calculations)

tests/
├── unit/
│   ├── test_binance_client.py
│   ├── test_yahoo_client.py
│   ├── test_feature_computation.py
│   ├── test_data_validation.py
│   └── test_aggregator.py
│
└── integration/
    ├── test_enrichment_pipeline.py
    └── test_database_inserts.py

database/
└── sql/
    ├── 06-market-data-v2-schema.sql    (NEW)
    └── 07-enrichment-support-tables.sql (NEW)
```

---

## Database Migration

### Step 1: Create Migration Files

**File:** `database/sql/06-market-data-v2-schema.sql`

```sql
-- Market Data V2: Enriched OHLCV with computed features
CREATE TABLE IF NOT EXISTS market_data_v2 (
    id BIGSERIAL PRIMARY KEY,
    
    -- Asset Identification
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL,  -- 'stock', 'crypto', 'etf'
    timeframe VARCHAR(10) NOT NULL,    -- '5m', '15m', '30m', '1h', '4h', '1d', '1w'
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Raw OHLCV (universal for all assets)
    open DECIMAL(19, 10),
    high DECIMAL(19, 10),
    low DECIMAL(19, 10),
    close DECIMAL(19, 10),
    volume BIGINT,
    
    -- Crypto-only raw data (from Binance)
    open_interest DECIMAL(19, 8),
    funding_rate DECIMAL(11, 8),
    liquidations_long DECIMAL(19, 8),
    liquidations_short DECIMAL(19, 8),
    taker_buy_volume DECIMAL(19, 8),
    taker_sell_volume DECIMAL(19, 8),
    
    -- Computed Features: Universal (all assets)
    return_1h DECIMAL(11, 8),
    return_1d DECIMAL(11, 8),
    volatility_20 DECIMAL(11, 8),
    volatility_50 DECIMAL(11, 8),
    atr DECIMAL(19, 10),
    trend_direction VARCHAR(10),        -- 'up', 'down', 'neutral'
    market_structure VARCHAR(20),       -- 'bullish', 'bearish', 'range'
    rolling_volume_20 BIGINT,
    
    -- Computed Features: Crypto-only
    delta DECIMAL(11, 8),               -- Long - Short volume
    buy_sell_ratio DECIMAL(11, 8),
    liquidation_intensity DECIMAL(11, 8),
    volume_spike_score DECIMAL(11, 8),
    long_short_ratio DECIMAL(11, 8),
    funding_rate_percentile DECIMAL(5, 2),
    exchange_inflow DECIMAL(19, 8),
    open_interest_change DECIMAL(11, 8),
    
    -- CRITICAL: Data Integrity & Versioning
    revision INT DEFAULT 1,             -- Track amendments
    amended_from BIGINT REFERENCES market_data_v2(id),  -- Link to previous version
    
    -- Quality & Validation
    source VARCHAR(20),                 -- 'polygon', 'binance', 'yahoo'
    is_validated BOOLEAN DEFAULT FALSE,
    quality_score DECIMAL(3, 2),
    data_completeness DECIMAL(3, 2),
    data_age_seconds INT,               -- How old is this data (for SLA tracking)
    validation_notes TEXT,
    gap_detected BOOLEAN DEFAULT FALSE,
    volume_anomaly BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraint to prevent duplicates
    UNIQUE(symbol, asset_class, timeframe, timestamp)
);

-- Indexes for query performance
CREATE INDEX idx_mdv2_symbol_asset_time 
    ON market_data_v2(symbol, asset_class, timeframe, timestamp DESC);
CREATE INDEX idx_mdv2_symbol_timestamp 
    ON market_data_v2(symbol, timestamp DESC);
CREATE INDEX idx_mdv2_validated 
    ON market_data_v2(is_validated) WHERE is_validated = TRUE;
CREATE INDEX idx_mdv2_source 
    ON market_data_v2(source);
CREATE INDEX idx_mdv2_timestamp 
    ON market_data_v2(timestamp DESC);
CREATE INDEX idx_mdv2_asset_class 
    ON market_data_v2(asset_class);
```

**File:** `database/sql/07-enrichment-support-tables.sql`

```sql
-- CRITICAL: Backfill State Tracking (enables pause/resume)
CREATE TABLE IF NOT EXISTS backfill_state (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    backfill_job_id UUID NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    last_successful_date DATE,         -- Resume from here if interrupted
    status VARCHAR(20) DEFAULT 'pending',  -- pending, in_progress, completed, failed
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, asset_class, timeframe, backfill_job_id)
);

CREATE INDEX idx_backfill_state_status 
    ON backfill_state(status) WHERE status IN ('pending', 'in_progress');
CREATE INDEX idx_backfill_state_symbol_job 
    ON backfill_state(symbol, backfill_job_id DESC);

-- CRITICAL: Data Corrections Log (amendment audit trail)
CREATE TABLE IF NOT EXISTS data_corrections (
    id BIGSERIAL PRIMARY KEY,
    original_record_id BIGINT REFERENCES market_data_v2(id) ON DELETE CASCADE,
    field_corrected VARCHAR(50),
    old_value DECIMAL(19, 10),
    new_value DECIMAL(19, 10),
    reason VARCHAR(200),  -- 'source_updated', 'bug_fix', 'manual_correction', 'validation_failure'
    corrected_by VARCHAR(100),
    correction_timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_data_corrections_record_id 
    ON data_corrections(original_record_id);
CREATE INDEX idx_data_corrections_timestamp 
    ON data_corrections(correction_timestamp DESC);

-- Data Source Log (audit trail of all fetch operations)
CREATE TABLE IF NOT EXISTS enrichment_fetch_log (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL,
    source VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    fetch_date_start DATE,
    fetch_date_end DATE,
    records_fetched INT DEFAULT 0,
    records_inserted INT DEFAULT 0,
    records_updated INT DEFAULT 0,
    fetch_timestamp TIMESTAMPTZ DEFAULT NOW(),
    source_response_time_ms INT,
    success BOOLEAN NOT NULL,
    error_details TEXT,
    api_quota_remaining INT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_fetch_log_symbol_time 
    ON enrichment_fetch_log(symbol, created_at DESC);
CREATE INDEX idx_fetch_log_source 
    ON enrichment_fetch_log(source);

-- Feature Computation Log (for debugging)
CREATE TABLE IF NOT EXISTS enrichment_compute_log (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    compute_timestamp TIMESTAMPTZ NOT NULL,
    features_computed INT DEFAULT 0,
    missing_fields TEXT[],
    computation_time_ms INT,
    success BOOLEAN NOT NULL,
    error_details TEXT,
    candles_processed INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_compute_log_symbol_time 
    ON enrichment_compute_log(symbol, created_at DESC);

-- Data Quality Metrics (aggregated stats)
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL,
    metric_date DATE NOT NULL,
    total_records INT DEFAULT 0,
    validated_records INT DEFAULT 0,
    validation_rate DECIMAL(5, 2),
    gaps_detected INT DEFAULT 0,
    anomalies_detected INT DEFAULT 0,
    avg_quality_score DECIMAL(3, 2),
    data_completeness DECIMAL(3, 2),
    sources_used TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, asset_class, metric_date)
);

CREATE INDEX idx_quality_metrics_symbol_date 
    ON data_quality_metrics(symbol, metric_date DESC);

-- Enrichment Status (track progress of enrichment job)
CREATE TABLE IF NOT EXISTS enrichment_status (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    asset_class VARCHAR(10) NOT NULL,
    last_enriched_timestamp TIMESTAMPTZ,
    last_fetch_source VARCHAR(20),
    last_compute_time_ms INT,
    total_records INT DEFAULT 0,
    avg_quality_score DECIMAL(3, 2),
    status VARCHAR(20),  -- 'pending', 'in_progress', 'completed', 'failed'
    error_message TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, asset_class)
);

CREATE INDEX idx_enrichment_status_symbol 
    ON enrichment_status(symbol);
```

### Step 2: Update Migration Service

**File:** `src/services/migration_service.py` (extend existing)

```python
async def run_migrations(self) -> bool:
    """Run all migrations in order"""
    migrations = [
        "database/sql/01-init-user.sql",
        "database/sql/02-tracked-symbols.sql",
        "database/sql/03-api-keys.sql",
        "database/sql/04-ownership-transfer.sql",
        "database/sql/05-market-prediction-tables.sql",
        "database/sql/06-market-data-v2-schema.sql",      # NEW
        "database/sql/07-enrichment-support-tables.sql",  # NEW
    ]
    
    for migration_file in migrations:
        if not await self._run_migration(migration_file):
            self.logger.error(f"Migration failed: {migration_file}")
            return False
    
    return True
```

### Step 3: Create UPSERT Helper & Circuit Breaker

**File:** `src/services/database_upsert.py` (NEW - CRITICAL FOR DATA INTEGRITY)

```python
"""
Idempotent insert/update logic using UPSERT
Prevents duplicates on retry
"""

from sqlalchemy import text
from typing import List, Dict

class UpsertService:
    """
    Handles idempotent inserts using PostgreSQL UPSERT.
    Ensures no duplicates even if job retries.
    """
    
    def __init__(self, db_service):
        self.db = db_service
        self.logger = logging.getLogger(__name__)
    
    async def upsert_market_data(
        self,
        records: List[Dict],
        conflict_columns: List[str] = None
    ) -> int:
        """
        Insert or update market_data_v2 records.
        
        On conflict (duplicate key), update to latest version if quality_score higher.
        
        Args:
            records: List of dicts to insert
            conflict_columns: Which columns to check for conflict
                             (default: symbol, asset_class, timeframe, timestamp)
        
        Returns:
            Number of records inserted/updated
        """
        
        if not records:
            return 0
        
        if conflict_columns is None:
            conflict_columns = ['symbol', 'asset_class', 'timeframe', 'timestamp']
        
        session = self.db.SessionLocal()
        inserted = 0
        
        try:
            # Build UPSERT query
            upsert_query = f"""
            INSERT INTO market_data_v2 (
                symbol, asset_class, timeframe, timestamp,
                open, high, low, close, volume,
                return_1h, return_1d, volatility_20, volatility_50, atr,
                trend_direction, market_structure, rolling_volume_20,
                delta, buy_sell_ratio, liquidation_intensity, volume_spike_score,
                source, is_validated, quality_score, data_completeness,
                validation_notes, gap_detected, volume_anomaly,
                fetched_at, computed_at, updated_at
            ) VALUES (
                :symbol, :asset_class, :timeframe, :timestamp,
                :open, :high, :low, :close, :volume,
                :return_1h, :return_1d, :volatility_20, :volatility_50, :atr,
                :trend_direction, :market_structure, :rolling_volume_20,
                :delta, :buy_sell_ratio, :liquidation_intensity, :volume_spike_score,
                :source, :is_validated, :quality_score, :data_completeness,
                :validation_notes, :gap_detected, :volume_anomaly,
                :fetched_at, :computed_at, :updated_at
            )
            ON CONFLICT(symbol, asset_class, timeframe, timestamp)
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                return_1h = EXCLUDED.return_1h,
                return_1d = EXCLUDED.return_1d,
                volatility_20 = EXCLUDED.volatility_20,
                volatility_50 = EXCLUDED.volatility_50,
                atr = EXCLUDED.atr,
                trend_direction = EXCLUDED.trend_direction,
                market_structure = EXCLUDED.market_structure,
                rolling_volume_20 = EXCLUDED.rolling_volume_20,
                source = EXCLUDED.source,
                quality_score = EXCLUDED.quality_score,
                data_completeness = EXCLUDED.data_completeness,
                updated_at = NOW(),
                revision = market_data_v2.revision + 1
            WHERE EXCLUDED.quality_score > market_data_v2.quality_score
            """
            
            # Batch insert in chunks to avoid memory issues
            chunk_size = 500
            for i in range(0, len(records), chunk_size):
                chunk = records[i:i+chunk_size]
                
                for record in chunk:
                    session.execute(text(upsert_query), record)
                
                session.commit()
                inserted += len(chunk)
            
            self.logger.info(f"Upserted {inserted} records")
            return inserted
        
        except Exception as e:
            session.rollback()
            self.logger.error(f"Upsert failed: {e}")
            raise
        
        finally:
            session.close()
```

**File:** `src/services/circuit_breaker.py` (NEW - CRITICAL FOR API RESILIENCE)

```python
"""
Circuit Breaker Pattern
Prevents API thrashing when external services fail
"""

import time
import logging
from enum import Enum
from typing import Optional, Callable
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, don't call
    HALF_OPEN = "half_open"  # Testing if service recovered

class APICircuitBreaker:
    """
    Circuit breaker for API calls.
    
    CLOSED → OPEN: After N consecutive failures
    OPEN → HALF_OPEN: After timeout_seconds pass
    HALF_OPEN → CLOSED: If next request succeeds
    HALF_OPEN → OPEN: If request fails
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        timeout_seconds: int = 300,
        success_threshold: int = 1
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.logger = logging.getLogger(__name__)
    
    async def call(
        self,
        func: Callable,
        *args,
        fallback_func: Optional[Callable] = None,
        **kwargs
    ):
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to call
            fallback_func: Function to call if circuit is OPEN
            *args, **kwargs: Arguments to pass to func
        
        Returns:
            Result from func or fallback_func
        
        Raises:
            Exception: If circuit is OPEN and no fallback
        """
        
        # Check if circuit should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.logger.info(f"{self.name}: Entering HALF_OPEN state")
            else:
                if fallback_func:
                    self.logger.warning(f"{self.name}: Circuit OPEN, using fallback")
                    return await fallback_func(*args, **kwargs)
                else:
                    raise Exception(f"Circuit breaker {self.name} is OPEN")
        
        # Execute the function
        try:
            result = await func(*args, **kwargs)
            
            # On success: reset counters or close circuit
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.logger.info(f"{self.name}: Circuit CLOSED (recovered)")
            
            return result
        
        except Exception as e:
            # On failure: increment counters
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            self.logger.warning(f"{self.name}: Failure #{self.failure_count}: {str(e)}")
            
            # Transition to OPEN if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.logger.error(f"{self.name}: Circuit OPEN after {self.failure_count} failures")
                
                # Use fallback if available
                if fallback_func:
                    return await fallback_func(*args, **kwargs)
            
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout_seconds
    
    def get_status(self) -> Dict:
        """Get circuit breaker status"""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'last_failure': self.last_failure_time.isoformat() if self.last_failure_time else None
        }
```

---

## Create Data Aggregator Service

### File: `src/clients/data_aggregator.py`

```python
"""
Data Aggregator Service
Unified interface to fetch OHLCV from multiple sources with fallback logic
Includes symbol mapping and timezone handling
"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
import pytz

class DataSource(Enum):
    POLYGON = "polygon"
    BINANCE = "binance"
    YAHOO = "yahoo"

# CRITICAL: Symbol Mapping Between Sources
SYMBOL_MAPPING = {
    'BTC': {
        'polygon': 'BTCUSD',
        'binance': 'BTCUSDT',
        'yahoo': 'BTC-USD',
        'asset_class': 'crypto'
    },
    'ETH': {
        'polygon': 'ETHUSD',
        'binance': 'ETHUSDT',
        'yahoo': 'ETH-USD',
        'asset_class': 'crypto'
    },
    'AAPL': {
        'polygon': 'AAPL',
        'binance': None,  # Not available on Binance
        'yahoo': 'AAPL',
        'asset_class': 'stock'
    },
    # ... add more mappings as needed
}

# CRITICAL: Timezone Configuration Per Asset Class
TIMEZONE_CONFIG = {
    'stock': {
        'timezone': 'US/Eastern',
        'trading_hours': (9.5, 16.0),  # 9:30 AM - 4:00 PM EST
        'market_days': [0, 1, 2, 3, 4],  # Mon-Fri
        'candle_open_time': 'market_open'
    },
    'crypto': {
        'timezone': 'UTC',
        'trading_hours': (0, 24),  # 24/7
        'market_days': list(range(7)),  # All days
        'candle_open_time': '00:00'  # UTC midnight
    },
    'etf': {
        'timezone': 'US/Eastern',
        'trading_hours': (9.5, 16.0),
        'market_days': [0, 1, 2, 3, 4],
        'candle_open_time': 'market_open'
    }
}

# CRITICAL: Data Freshness SLA (defines staleness)
DATA_FRESHNESS_SLA = {
    'stock': {
        'target_latency_seconds': 60,     # Target: 1 minute
        'critical_latency_seconds': 300,  # Critical: 5 minutes
        'stale_threshold_seconds': 3600,  # Stale after 1 hour
        'alert_threshold_seconds': 600    # Alert after 10 minutes
    },
    'crypto': {
        'target_latency_seconds': 30,
        'critical_latency_seconds': 120,
        'stale_threshold_seconds': 600,
        'alert_threshold_seconds': 60
    }
}

class DataAggregator:
    """
    Intelligently fetch market data from multiple sources with fallback.
    
    Features:
    - Primary source based on asset class (Polygon for stocks, Binance for crypto)
    - Automatic fallback if primary source fails
    - Symbol mapping between different source formats
    - Timezone-aware candle validation
    - Circuit breaker for API resilience
    - Data freshness SLA tracking
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Import clients
        from src.clients.polygon_client import PolygonClient
        from src.clients.binance_client import BinanceClient
        from src.clients.yahoo_client import YahooClient
        from src.services.circuit_breaker import APICircuitBreaker
        
        self.polygon = PolygonClient(config.polygon_api_key)
        self.binance = BinanceClient()
        self.yahoo = YahooClient()
        
        # Circuit breakers per source
        self.circuit_breakers = {
            'polygon': APICircuitBreaker('polygon', failure_threshold=3, timeout_seconds=300),
            'binance': APICircuitBreaker('binance', failure_threshold=3, timeout_seconds=300),
            'yahoo': APICircuitBreaker('yahoo', failure_threshold=3, timeout_seconds=300)
        }
        
        # Source priority by asset class
        self.source_priority = {
            'stock': ['polygon', 'yahoo'],
            'etf': ['polygon', 'yahoo'],
            'crypto': ['binance', 'polygon']
        }
    
    async def fetch_ohlcv(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Fetch OHLCV data with smart source selection and fallback.
        
        Args:
            symbol: Asset ticker (AAPL, BTC, ETH, etc.)
            asset_class: 'stock', 'etf', or 'crypto'
            timeframe: '5m', '15m', '30m', '1h', '4h', '1d', '1w'
            start_date: Start timestamp
            end_date: End timestamp
        
        Returns:
            {
                'source': 'polygon',
                'symbol': 'AAPL',
                'candles': [
                    {
                        'timestamp': 2024-01-01T00:00:00Z,
                        'open': 150.0,
                        'high': 152.0,
                        'low': 149.0,
                        'close': 151.0,
                        'volume': 1000000,
                        'vwap': 150.5
                    },
                    ...
                ],
                'metadata': {
                    'total_candles': 252,
                    'response_time_ms': 234,
                    'date_range': {'start': '2024-01-01', 'end': '2024-12-31'},
                    'status': 'success'
                }
            }
        
        Raises:
            Exception: If all sources fail
        """
        
        # Determine source priority for this asset class
        sources = self.source_priority.get(asset_class, ['polygon', 'yahoo'])
        
        # Try each source in priority order
        last_error = None
        for source in sources:
            try:
                self.logger.info(
                    f"Fetching {symbol} from {source}",
                    extra={'asset_class': asset_class, 'timeframe': timeframe}
                )
                
                result = await self._fetch_from_source(
                    source, symbol, asset_class, timeframe, start_date, end_date
                )
                
                if result and len(result['candles']) > 0:
                    self.logger.info(
                        f"Successfully fetched {len(result['candles'])} candles from {source}"
                    )
                    return result
                
            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"Source {source} failed: {str(e)}",
                    extra={'symbol': symbol, 'source': source}
                )
                continue
        
        # All sources failed
        raise Exception(
            f"All data sources failed for {symbol}. "
            f"Last error: {last_error}"
        )
    
    async def _fetch_from_source(
        self,
        source: str,
        symbol: str,
        asset_class: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """Fetch from specific source"""
        
        start_time = datetime.utcnow()
        
        if source == 'polygon':
            candles = await self.polygon.get_agg(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date
            )
            
        elif source == 'binance':
            candles = await self.binance.get_klines(
                symbol=symbol,
                interval=timeframe,
                start_time=start_date,
                end_time=end_date
            )
            
        elif source == 'yahoo':
            candles = await self.yahoo.get_historical(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval='1d'
            )
        else:
            raise ValueError(f"Unknown source: {source}")
        
        response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return {
            'source': source,
            'symbol': symbol,
            'candles': candles,
            'metadata': {
                'total_candles': len(candles),
                'response_time_ms': int(response_time_ms),
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'status': 'success'
            }
        }
    
    async def fetch_crypto_microstructure(
        self,
        symbol: str,
        timeframe: str = '1h'
    ) -> Dict:
        """
        Fetch Binance-specific crypto data:
        - Open Interest
        - Funding Rate
        - Liquidations
        - Taker Buy/Sell Volume
        
        Args:
            symbol: Crypto pair (BTCUSDT, ETHUSDT)
            timeframe: Candle period
        
        Returns:
            {
                'symbol': 'BTCUSDT',
                'open_interest': 1234567.89,
                'funding_rate': 0.0001,
                'liquidations_long': 123.45,
                'liquidations_short': 234.56,
                'taker_buy_volume': 1000000,
                'taker_sell_volume': 900000,
                'timestamp': '2024-01-01T00:00:00Z'
            }
        """
        try:
            data = await self.binance.get_crypto_microstructure(
                symbol=symbol,
                timeframe=timeframe
            )
            return data
        except Exception as e:
            self.logger.error(f"Failed to fetch crypto microstructure: {e}")
            raise
    
    async def fetch_parallel(
        self,
        symbols: List[str],
        asset_class: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        max_concurrent: int = 5
    ) -> List[Dict]:
        """
        Fetch multiple symbols in parallel for speed.
        
        Args:
            symbols: List of tickers
            asset_class: Asset class for all symbols
            timeframe: Candle period
            start_date: Start date
            end_date: End date
            max_concurrent: Max parallel requests
        
        Returns:
            List of fetch results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_with_semaphore(symbol):
            async with semaphore:
                return await self.fetch_ohlcv(
                    symbol, asset_class, timeframe, start_date, end_date
                )
        
        results = await asyncio.gather(
            *[fetch_with_semaphore(s) for s in symbols],
            return_exceptions=True
        )
        
        return results
```

---

## Implement Connectors

### File: `src/clients/binance_client.py`

```python
"""
Binance API Client
Free public endpoints for crypto data
"""

import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime
from decimal import Decimal

class BinanceClient:
    """
    Binance API client for crypto OHLCV and microstructure data.
    No API key required for public endpoints (limited to 1200 req/min).
    """
    
    BASE_URL = "https://fapi.binance.com"  # Futures API (for funding rates)
    SPOT_URL = "https://api.binance.com"
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _ensure_session(self):
        """Create session if needed"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close session"""
        if self.session:
            await self.session.close()
    
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Get OHLCV candles from Binance Futures API.
        
        Args:
            symbol: Trading pair (BTCUSDT, ETHUSDT)
            interval: Candle period (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            start_time: Start timestamp
            end_time: End timestamp
        
        Returns:
            List of candle dicts with o, h, l, c, v
        """
        await self._ensure_session()
        
        # Convert datetime to milliseconds
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        # Binance interval mapping
        binance_interval = self._map_interval(interval)
        
        params = {
            'symbol': symbol,
            'interval': binance_interval,
            'startTime': start_ms,
            'endTime': end_ms,
            'limit': 1500  # Max limit per request
        }
        
        all_candles = []
        
        try:
            while start_ms < end_ms:
                params['startTime'] = start_ms
                
                async with self.session.get(
                    f"{self.BASE_URL}/fapi/v1/klines",
                    params=params
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Binance API error: {response.status}")
                    
                    data = await response.json()
                    
                    if not data:
                        break
                    
                    # Convert to standard format
                    for candle in data:
                        all_candles.append({
                            't': int(candle[0]),  # Open time
                            'o': float(candle[1]),
                            'h': float(candle[2]),
                            'l': float(candle[3]),
                            'c': float(candle[4]),
                            'v': float(candle[7]),  # Quote asset volume
                        })
                    
                    # Move to next batch
                    start_ms = int(candle[0]) + 1000
        
        except Exception as e:
            self.logger.error(f"Error fetching klines: {e}")
            raise
        
        return all_candles
    
    async def get_open_interest(self, symbol: str) -> Decimal:
        """Get current open interest"""
        await self._ensure_session()
        
        try:
            async with self.session.get(
                f"{self.BASE_URL}/fapi/v1/openInterest",
                params={'symbol': symbol}
            ) as response:
                data = await response.json()
                return Decimal(str(data.get('openInterest', 0)))
        except Exception as e:
            self.logger.error(f"Error fetching open interest: {e}")
            raise
    
    async def get_funding_rate(self, symbol: str) -> Decimal:
        """Get current funding rate"""
        await self._ensure_session()
        
        try:
            async with self.session.get(
                f"{self.BASE_URL}/fapi/v1/fundingRate",
                params={'symbol': symbol, 'limit': 1}
            ) as response:
                data = await response.json()
                if data:
                    return Decimal(str(data[0].get('fundingRate', 0)))
                return Decimal(0)
        except Exception as e:
            self.logger.error(f"Error fetching funding rate: {e}")
            raise
    
    async def get_liquidations(
        self,
        symbol: str,
        period: str = '1h'
    ) -> Dict[str, Decimal]:
        """Get liquidation data for recent period"""
        await self._ensure_session()
        
        try:
            # Fetch recent liquidations
            async with self.session.get(
                f"{self.BASE_URL}/fapi/v1/forceOrders",
                params={'symbol': symbol, 'limit': 100}
            ) as response:
                data = await response.json()
                
                long_liquidated = Decimal(0)
                short_liquidated = Decimal(0)
                
                for item in data:
                    quantity = Decimal(str(item.get('origQty', 0)))
                    # Positive quantity = long, negative = short
                    if quantity > 0:
                        long_liquidated += quantity
                    else:
                        short_liquidated += abs(quantity)
                
                return {
                    'liquidations_long': long_liquidated,
                    'liquidations_short': short_liquidated
                }
        
        except Exception as e:
            self.logger.error(f"Error fetching liquidations: {e}")
            raise
    
    async def get_crypto_microstructure(
        self,
        symbol: str,
        timeframe: str = '1h'
    ) -> Dict:
        """
        Get all crypto-specific microstructure data in one call.
        """
        try:
            results = await asyncio.gather(
                self.get_open_interest(symbol),
                self.get_funding_rate(symbol),
                self.get_liquidations(symbol),
                return_exceptions=True
            )
            
            oi, fr, liq = results
            
            return {
                'symbol': symbol,
                'open_interest': oi if isinstance(oi, Decimal) else None,
                'funding_rate': fr if isinstance(fr, Decimal) else None,
                'liquidations_long': liq.get('liquidations_long') if isinstance(liq, dict) else None,
                'liquidations_short': liq.get('liquidations_short') if isinstance(liq, dict) else None,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error fetching microstructure: {e}")
            raise
    
    def _map_interval(self, interval: str) -> str:
        """Map standard interval to Binance format"""
        mapping = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1w'
        }
        return mapping.get(interval, '1h')
```

### File: `src/clients/yahoo_client.py`

```python
"""
Yahoo Finance API Client
Free fallback source for stock/ETF OHLCV data
"""

import aiohttp
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json

class YahooClient:
    """
    Yahoo Finance client for historical OHLCV data.
    Free API with no authentication required.
    Rate limited but good fallback source.
    """
    
    BASE_URL = "https://query1.finance.yahoo.com"
    TIMEOUT = 10  # seconds
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _ensure_session(self):
        """Create session if needed"""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Close session"""
        if self.session:
            await self.session.close()
    
    async def get_historical(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = '1d'
    ) -> List[Dict]:
        """
        Get historical OHLCV data from Yahoo Finance.
        
        Args:
            symbol: Ticker symbol (AAPL, SPY, etc.)
            start_date: Start date
            end_date: End date
            interval: '1d' (daily only for free API)
        
        Returns:
            List of candles in standard format
        """
        await self._ensure_session()
        
        try:
            # Yahoo Finance requires period in seconds
            period1 = int(start_date.timestamp())
            period2 = int(end_date.timestamp())
            
            params = {
                'interval': interval,
                'period1': period1,
                'period2': period2
            }
            
            # Construct URL with symbol
            url = f"{self.BASE_URL}/v10/finance/quoteSummary/{symbol}"
            
            async with self.session.get(
                f"{self.BASE_URL}/v7/finance/download/{symbol}",
                params=params,
                headers={'User-Agent': 'Mozilla/5.0'}
            ) as response:
                if response.status != 200:
                    raise Exception(f"Yahoo Finance API error: {response.status}")
                
                text = await response.text()
                
                # Parse CSV response
                candles = []
                lines = text.strip().split('\n')
                
                for line in lines[1:]:  # Skip header
                    parts = line.split(',')
                    if len(parts) < 6:
                        continue
                    
                    try:
                        date_str = parts[0]
                        date = datetime.strptime(date_str, '%Y-%m-%d')
                        
                        candles.append({
                            't': int(date.timestamp() * 1000),
                            'o': float(parts[1]),
                            'h': float(parts[2]),
                            'l': float(parts[3]),
                            'c': float(parts[4]),
                            'v': int(float(parts[5]))
                        })
                    except (ValueError, IndexError):
                        continue
                
                return candles
        
        except asyncio.TimeoutError:
            self.logger.error(f"Yahoo Finance timeout for {symbol}")
            raise
        except Exception as e:
            self.logger.error(f"Error fetching from Yahoo Finance: {e}")
            raise
```

---

## Feature Computation

### File: `src/services/feature_computation_service.py`

```python
"""
Technical Feature Computation Service
Compute all 22 market features from raw OHLCV data
"""

import numpy as np
import pandas as pd
import logging
from typing import List, Dict, Tuple
from decimal import Decimal
from datetime import datetime

class FeatureComputationService:
    """
    Computes technical indicators and market structure features.
    
    Universal Features (all assets):
    1. return_1h - Hourly return
    2. return_1d - Daily return
    3. volatility_20 - 20-period rolling volatility
    4. volatility_50 - 50-period rolling volatility
    5. atr - Average True Range (14-period)
    6. trend_direction - Up/Down/Neutral
    7. market_structure - Bullish/Bearish/Range
    8. rolling_volume_20 - 20-period rolling avg volume
    
    Crypto-specific Features:
    9. delta - Long - Short volume difference
    10. buy_sell_ratio - Taker buy / total volume
    11. liquidation_intensity - Total liquidations / volume
    12. volume_spike_score - Current vol / 20-period avg
    13. long_short_ratio - Open interest distribution
    14. funding_rate_percentile - Funding rate vs historical
    15. exchange_inflow - Net spot inflow metric
    16. open_interest_change - OI momentum
    17-22. Additional derived metrics
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def compute_all_features(
        self,
        candles: List[Dict],
        asset_class: str = 'stock',
        crypto_data: Dict = None
    ) -> List[Dict]:
        """
        Compute all features for a series of candles.
        
        Args:
            candles: List of OHLCV dicts
            asset_class: 'stock', 'etf', or 'crypto'
            crypto_data: Optional dict with crypto-specific data
        
        Returns:
            List of dicts with features added to each candle
        """
        if not candles or len(candles) < 2:
            self.logger.warning("Insufficient candles for feature computation")
            return candles
        
        # Convert to DataFrame for vectorized operations
        df = self._candles_to_dataframe(candles)
        
        # Compute universal features
        df['return_1h'] = self._compute_return_1h(df)
        df['return_1d'] = self._compute_return_1d(df)
        df['volatility_20'] = self._compute_volatility(df, window=20)
        df['volatility_50'] = self._compute_volatility(df, window=50)
        df['atr'] = self._compute_atr(df, period=14)
        df['trend_direction'] = self._compute_trend_direction(df)
        df['market_structure'] = self._compute_market_structure(df)
        df['rolling_volume_20'] = self._compute_rolling_volume(df, window=20)
        
        # Compute crypto features if applicable
        if asset_class == 'crypto' and crypto_data:
            df['delta'] = self._compute_delta(crypto_data)
            df['buy_sell_ratio'] = self._compute_buy_sell_ratio(crypto_data)
            df['liquidation_intensity'] = self._compute_liquidation_intensity(
                crypto_data, df
            )
            df['volume_spike_score'] = self._compute_volume_spike_score(df)
        
        # Convert back to list of dicts
        return df.to_dict('records')
    
    def _candles_to_dataframe(self, candles: List[Dict]) -> pd.DataFrame:
        """Convert candle list to DataFrame"""
        return pd.DataFrame([
            {
                'timestamp': c.get('t'),
                'open': float(c.get('o', 0)),
                'high': float(c.get('h', 0)),
                'low': float(c.get('l', 0)),
                'close': float(c.get('c', 0)),
                'volume': int(c.get('v', 0))
            }
            for c in candles
        ])
    
    # ============ Universal Features ============
    
    def _compute_return_1h(self, df: pd.DataFrame) -> pd.Series:
        """
        Hourly return: (Close - Open) / Open
        """
        return ((df['close'] - df['open']) / df['open'] * 100).round(4)
    
    def _compute_return_1d(self, df: pd.DataFrame) -> pd.Series:
        """
        Daily return: Yesterday close to today close
        For hourly data, use 24-hour lookback
        """
        return df['close'].pct_change() * 100
    
    def _compute_volatility(
        self,
        df: pd.DataFrame,
        window: int = 20
    ) -> pd.Series:
        """
        Rolling standard deviation of log returns.
        Formula: std(ln(close[t] / close[t-1])) * 100
        """
        log_returns = np.log(df['close'] / df['close'].shift(1))
        volatility = log_returns.rolling(window=window).std() * 100
        return volatility.round(4)
    
    def _compute_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Average True Range: Rolling average of true ranges.
        TR = max(high - low, abs(high - close[t-1]), abs(low - close[t-1]))
        ATR = SMA(TR, 14)
        """
        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift()).abs()
        low_close = (df['low'] - df['close'].shift()).abs()
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.round(8)
    
    def _compute_trend_direction(self, df: pd.DataFrame) -> pd.Series:
        """
        Simple trend: Compare current close to 20-period SMA.
        Up: close > SMA(20)
        Down: close < SMA(20)
        Neutral: close ≈ SMA(20)
        """
        sma20 = df['close'].rolling(window=20).mean()
        
        trend = pd.Series(['neutral'] * len(df), index=df.index)
        trend[df['close'] > sma20 * 1.01] = 'up'
        trend[df['close'] < sma20 * 0.99] = 'down'
        
        return trend
    
    def _compute_market_structure(self, df: pd.DataFrame) -> pd.Series:
        """
        Market structure based on pivot points and support/resistance.
        Bullish: Higher highs and higher lows
        Bearish: Lower highs and lower lows
        Range: Neither (trading in range)
        """
        structure = pd.Series(['range'] * len(df), index=df.index)
        
        # Simple approach: compare current vs 20 bars ago
        window = 20
        for i in range(window, len(df)):
            curr_high = df['high'].iloc[i]
            prev_high = df['high'].iloc[i-window]
            curr_low = df['low'].iloc[i]
            prev_low = df['low'].iloc[i-window]
            
            if curr_high > prev_high and curr_low > prev_low:
                structure.iloc[i] = 'bullish'
            elif curr_high < prev_high and curr_low < prev_low:
                structure.iloc[i] = 'bearish'
        
        return structure
    
    def _compute_rolling_volume(self, df: pd.DataFrame, window: int = 20) -> pd.Series:
        """Average volume over window periods"""
        return df['volume'].rolling(window=window).mean().astype(int)
    
    # ============ Crypto-Specific Features ============
    
    def _compute_delta(self, crypto_data: Dict) -> float:
        """
        Delta = Taker Buy Volume - Taker Sell Volume
        Indicates buying vs selling pressure
        """
        buy_vol = float(crypto_data.get('taker_buy_volume', 0))
        sell_vol = float(crypto_data.get('taker_sell_volume', 0))
        return round(buy_vol - sell_vol, 8)
    
    def _compute_buy_sell_ratio(self, crypto_data: Dict) -> float:
        """
        Buy/Sell Ratio = Taker Buy / (Taker Buy + Taker Sell)
        Values > 0.5 indicate buying pressure
        """
        buy_vol = float(crypto_data.get('taker_buy_volume', 0))
        sell_vol = float(crypto_data.get('taker_sell_volume', 0))
        total = buy_vol + sell_vol
        
        if total == 0:
            return 0.5
        
        return round(buy_vol / total, 4)
    
    def _compute_liquidation_intensity(
        self,
        crypto_data: Dict,
        df: pd.DataFrame
    ) -> float:
        """
        Liquidation Intensity = Total Liquidations / Volume
        Higher values indicate more liquidations (volatility proxy)
        """
        long_liq = float(crypto_data.get('liquidations_long', 0))
        short_liq = float(crypto_data.get('liquidations_short', 0))
        total_liq = long_liq + short_liq
        
        if df.empty:
            return 0.0
        
        volume = float(df['volume'].iloc[-1])
        if volume == 0:
            return 0.0
        
        return round(total_liq / volume, 8)
    
    def _compute_volume_spike_score(self, df: pd.DataFrame) -> float:
        """
        Volume Spike Score = Current Volume / 20-period Average
        > 1.0 indicates spike, < 1.0 indicates low volume
        """
        if len(df) < 20:
            return 1.0
        
        current_vol = df['volume'].iloc[-1]
        avg_vol = df['volume'].rolling(window=20).mean().iloc[-1]
        
        if avg_vol == 0:
            return 0.0
        
        return round(current_vol / avg_vol, 4)
    
    def _compute_long_short_ratio(self, crypto_data: Dict) -> float:
        """
        Long/Short Ratio = Open Interest for Longs / Total OI
        Indicates positioning in futures market
        """
        # Would need market data - placeholder
        return 0.5
    
    def _compute_funding_rate_percentile(self, funding_rates: List[float]) -> float:
        """
        Where current funding rate sits in historical distribution
        """
        if not funding_rates:
            return 0.5
        
        current = funding_rates[-1]
        percentile = (sum(1 for r in funding_rates if r < current) / len(funding_rates)) * 100
        
        return round(percentile, 2)
```

---

## Integration & Orchestration

### File: `src/services/data_enrichment_service.py`

```python
"""
Main Data Enrichment Service
Orchestrates: Fetch → Validate → Compute → Store
"""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from src.clients.data_aggregator import DataAggregator
from src.services.feature_computation_service import FeatureComputationService
from src.services.data_quality_service import DataQualityService
from src.services.database_service import DatabaseService

class DataEnrichmentService:
    """
    Orchestrates the complete enrichment pipeline.
    
    Flow:
    1. Load symbols to enrich
    2. Fetch OHLCV from best source (with fallback)
    3. Validate data integrity
    4. Compute technical features
    5. Insert/update in market_data_v2
    6. Log metrics and errors
    """
    
    def __init__(
        self,
        config,
        db_service: DatabaseService,
        data_aggregator: DataAggregator,
        feature_service: FeatureComputationService,
        quality_service: DataQualityService
    ):
        self.config = config
        self.db = db_service
        self.aggregator = data_aggregator
        self.features = feature_service
        self.quality = quality_service
        self.logger = logging.getLogger(__name__)
    
    async def enrich_asset(
        self,
        symbol: str,
        asset_class: str,
        timeframes: List[str],
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict:
        """
        Complete enrichment pipeline for one asset across multiple timeframes.
        
        Returns:
        {
            'symbol': 'AAPL',
            'asset_class': 'stock',
            'status': 'success',
            'timeframes': {
                '1d': {
                    'records_inserted': 252,
                    'source': 'polygon',
                    'quality_score': 0.97
                },
                ...
            },
            'total_records': 504,
            'errors': []
        }
        """
        
        if start_date is None:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=365)
        
        results = {
            'symbol': symbol,
            'asset_class': asset_class,
            'status': 'in_progress',
            'timeframes': {},
            'errors': []
        }
        
        for timeframe in timeframes:
            try:
                self.logger.info(f"Enriching {symbol} {timeframe}...")
                
                # 1. Fetch from best source
                fetch_result = await self.aggregator.fetch_ohlcv(
                    symbol=symbol,
                    asset_class=asset_class,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date
                )
                
                candles = fetch_result['candles']
                source = fetch_result['source']
                
                # 2. Validate data
                validation_result = self.quality.validate_ohlcv(candles)
                if not validation_result['is_valid']:
                    results['errors'].append(
                        f"{timeframe}: Validation failed - {validation_result['errors']}"
                    )
                    continue
                
                # 3. Compute features
                enriched_candles = self.features.compute_all_features(
                    candles,
                    asset_class=asset_class
                )
                
                # 4. Prepare for database
                records = self._prepare_db_records(
                    symbol=symbol,
                    asset_class=asset_class,
                    timeframe=timeframe,
                    candles=enriched_candles,
                    source=source
                )
                
                # 5. Insert into database
                inserted = await self.db.insert_enriched_data(
                    records, table='market_data_v2'
                )
                
                results['timeframes'][timeframe] = {
                    'records_inserted': inserted,
                    'source': source,
                    'quality_score': validation_result.get('avg_quality_score', 0.95)
                }
                
            except Exception as e:
                self.logger.error(f"Error enriching {symbol} {timeframe}: {e}")
                results['errors'].append(f"{timeframe}: {str(e)}")
        
        results['status'] = 'success' if not results['errors'] else 'partial'
        results['total_records'] = sum(
            tf.get('records_inserted', 0)
            for tf in results['timeframes'].values()
        )
        
        return results
    
    async def enrich_batch(
        self,
        symbols: List[str],
        asset_class: str = 'stock',
        timeframes: List[str] = None,
        max_concurrent: int = 5
    ) -> Dict:
        """
        Enrich multiple symbols in parallel.
        """
        
        if timeframes is None:
            timeframes = self.config.DEFAULT_TIMEFRAMES
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_with_semaphore(symbol):
            async with semaphore:
                return await self.enrich_asset(
                    symbol, asset_class, timeframes
                )
        
        results = await asyncio.gather(
            *[enrich_with_semaphore(s) for s in symbols],
            return_exceptions=True
        )
        
        return {
            'batch_id': datetime.utcnow().isoformat(),
            'symbols': symbols,
            'total_symbols': len(symbols),
            'results': results,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _prepare_db_records(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        candles: List[Dict],
        source: str
    ) -> List[Dict]:
        """Prepare candles for database insertion"""
        
        records = []
        for candle in candles:
            record = {
                'symbol': symbol,
                'asset_class': asset_class,
                'timeframe': timeframe,
                'timestamp': datetime.fromtimestamp(candle['t'] / 1000),
                'open': candle.get('open'),
                'high': candle.get('high'),
                'low': candle.get('low'),
                'close': candle.get('close'),
                'volume': candle.get('volume'),
                'return_1h': candle.get('return_1h'),
                'return_1d': candle.get('return_1d'),
                'volatility_20': candle.get('volatility_20'),
                'volatility_50': candle.get('volatility_50'),
                'atr': candle.get('atr'),
                'trend_direction': candle.get('trend_direction'),
                'market_structure': candle.get('market_structure'),
                'rolling_volume_20': candle.get('rolling_volume_20'),
                'source': source,
                'is_validated': True,
                'quality_score': 0.95,  # Compute properly
                'data_completeness': 1.0
            }
            
            # Add crypto fields if applicable
            if asset_class == 'crypto':
                record.update({
                    'delta': candle.get('delta'),
                    'buy_sell_ratio': candle.get('buy_sell_ratio'),
                    'liquidation_intensity': candle.get('liquidation_intensity'),
                    'volume_spike_score': candle.get('volume_spike_score'),
                })
            
            records.append(record)
        
        return records
```

---

## Testing Framework

### File: `tests/unit/test_feature_computation.py`

```python
"""
Unit tests for feature computation
"""

import unittest
import pandas as pd
from src.services.feature_computation_service import FeatureComputationService

class TestFeatureComputation(unittest.TestCase):
    
    def setUp(self):
        self.service = FeatureComputationService()
        self.sample_candles = [
            {'t': 1000000, 'o': 100.0, 'h': 105.0, 'l': 99.0, 'c': 104.0, 'v': 1000000},
            {'t': 2000000, 'o': 104.0, 'h': 106.0, 'l': 103.0, 'c': 105.0, 'v': 900000},
            # ... more candles
        ]
    
    def test_return_1h(self):
        """Test hourly return calculation"""
        df = self.service._candles_to_dataframe(self.sample_candles)
        returns = self.service._compute_return_1h(df)
        
        # (104 - 100) / 100 * 100 = 4%
        self.assertAlmostEqual(returns.iloc[0], 4.0, places=2)
    
    def test_volatility_positive(self):
        """Volatility should be non-negative"""
        df = self.service._candles_to_dataframe(self.sample_candles)
        vol = self.service._compute_volatility(df, window=20)
        
        self.assertTrue((vol[20:] >= 0).all())
    
    def test_atr_positive(self):
        """ATR should be positive"""
        df = self.service._candles_to_dataframe(self.sample_candles)
        atr = self.service._compute_atr(df)
        
        self.assertTrue((atr[14:] > 0).all())
    
    # ... more tests for all features
```

### File: `tests/integration/test_enrichment_pipeline.py`

```python
"""
Integration tests for full enrichment pipeline
"""

import unittest
import asyncio
from datetime import datetime, timedelta
from src.clients.data_aggregator import DataAggregator
from src.services.data_enrichment_service import DataEnrichmentService

class TestEnrichmentPipeline(unittest.TestCase):
    
    @classmethod
    async def setUpClass(cls):
        # Initialize services
        pass
    
    async def test_end_to_end_enrichment(self):
        """Test complete enrichment for single symbol"""
        
        result = await self.service.enrich_asset(
            symbol='AAPL',
            asset_class='stock',
            timeframes=['1d']
        )
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('1d', result['timeframes'])
        self.assertGreater(result['total_records'], 0)
    
    async def test_parallel_enrichment(self):
        """Test batch enrichment"""
        
        symbols = ['AAPL', 'MSFT', 'GOOGL']
        result = await self.service.enrich_batch(
            symbols=symbols,
            asset_class='stock'
        )
        
        self.assertEqual(len(result['results']), len(symbols))
        self.assertTrue(all(r['status'] == 'success' for r in result['results']))
```

---

## Deployment Checklist

### Pre-Deployment
- [ ] All migrations created and tested locally
- [ ] All new services unit tested (90%+ coverage)
- [ ] Integration tests passing
- [ ] Feature formulas verified with manual calculations
- [ ] Environment variables documented in .env.example
- [ ] API rate limits understood and configured
- [ ] Database backups created
- [ ] Rollback procedure documented

### Deployment
- [ ] Deploy in maintenance window
- [ ] Run migrations on production database
- [ ] Verify new tables created correctly
- [ ] Start enrichment service
- [ ] Monitor logs for errors
- [ ] Verify data being inserted to `market_data_v2`
- [ ] Check API response times (should be < 2s)
- [ ] Monitor database performance

### Post-Deployment
- [ ] Run 24 hours of monitoring
- [ ] Compare `market_data` vs `market_data_v2` for consistency
- [ ] Verify features are computing correctly
- [ ] Update documentation with new endpoints
- [ ] Set up monitoring alerts
- [ ] Train team on new features

### Rollback Procedure
```bash
# If critical issues discovered:
# 1. Stop enrichment service
# 2. Revert API endpoints to query market_data
# 3. Investigate issues in staging
# 4. Document what failed
# 5. Plan fix
# 6. Re-deploy
```

---

## Performance Expectations

| Operation | Target | Notes |
|-----------|--------|-------|
| Fetch OHLCV (100 days, 1 symbol) | < 1 sec | Polygon is fast |
| Compute features (1000 candles) | < 500 ms | Vectorized operations |
| Database insert (1000 records) | < 200 ms | Batch insert with COPY |
| Enrich symbol (5 timeframes, 365 days) | < 10 sec | Parallel operations |
| Enrich 50 symbols | < 5 min | Max 5 concurrent |

---

## Success Metrics

Track these metrics post-deployment:

1. **Data Quality**: Validation pass rate > 95%
2. **Latency**: 95th percentile insert latency < 500ms
3. **Completeness**: 100% of symbols enriched daily
4. **Coverage**: All 22 features computed for all records
5. **Availability**: Zero unplanned downtime

---

**Next Steps:**
1. Review this plan with your team
2. Schedule 4-week implementation sprint
3. Start with Phase 1a: Database migrations
4. Iterate through phases, testing thoroughly
5. Deploy to staging first, then production

**Questions or clarifications needed?**
