# Implementation Plan: Advanced Trading Data

Comprehensive plan to add Dividends, Stock Splits, News/Sentiment, Earnings, and IV data to the Market Data API for all supported assets.

---

## Executive Summary

**Goal**: Enhance backtesting accuracy and ML pattern detection by integrating 4 critical data types.

**Timeline**: 4-6 weeks (phased)
**Effort**: ~120-150 developer hours
**Priority**: Phase 1 (Dividends/Splits) → Phase 2 (News/Sentiment) → Phase 3 (Earnings/IV)

| Data Type | Priority | Effort | Impact | Timeline |
|-----------|----------|--------|--------|----------|
| Dividends | Critical | 20h | High | Week 1-2 |
| Stock Splits | Critical | 15h | High | Week 1-2 |
| News/Sentiment | High | 40h | Very High | Week 3-4 |
| Earnings | High | 25h | Very High | Week 4-5 |
| IV (Options) | Medium | 30h | Medium | Week 5-6 |

---

## Phase 1: Dividends & Stock Splits (Weeks 1-2)

### 1.1 Architecture

```
Polygon API
    ↓
backfill_dividends.py (new script)
backfill_splits.py (new script)
    ↓
ValidationService.validate_dividend()
ValidationService.validate_split()
    ↓
Database (dividends table, splits table)
    ↓
API Endpoint: /api/v1/ohlcv/{symbol}/adjusted
    (applies dividend/split adjustments on the fly)
```

### 1.2 Database Schema

```sql
-- Table: dividends
CREATE TABLE dividends (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    ex_date DATE NOT NULL,
    record_date DATE,
    pay_date DATE,
    dividend_amount DECIMAL(12, 4) NOT NULL,
    dividend_type VARCHAR(50), -- 'regular', 'special', 'cash', etc.
    adjusted BOOLEAN DEFAULT FALSE,
    currency VARCHAR(3) DEFAULT 'USD',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, ex_date),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX idx_dividends_symbol ON dividends(symbol);
CREATE INDEX idx_dividends_ex_date ON dividends(ex_date);

-- Table: stock_splits
CREATE TABLE stock_splits (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    execution_date DATE NOT NULL,
    split_from INT NOT NULL, -- numerator
    split_to INT NOT NULL,   -- denominator
    split_ratio DECIMAL(10, 4) NOT NULL, -- split_to / split_from
    adjusted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, execution_date),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX idx_splits_symbol ON stock_splits(symbol);
CREATE INDEX idx_splits_execution_date ON stock_splits(execution_date);

-- Table: ohlcv_adjusted (view or materialized)
-- Stores adjusted prices (dividend & split adjusted)
CREATE TABLE ohlcv_adjusted (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open_adj DECIMAL(12, 4),
    high_adj DECIMAL(12, 4),
    low_adj DECIMAL(12, 4),
    close_adj DECIMAL(12, 4),
    volume_adj BIGINT,
    adjustment_factor DECIMAL(12, 8), -- cumulative multiplier
    adjustment_note TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, timestamp, timeframe),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX idx_ohlcv_adj_symbol_time ON ohlcv_adjusted(symbol, timestamp);
```

### 1.3 Backfill Scripts

#### Script 1: `scripts/backfill_dividends.py`

```python
#!/usr/bin/env python3
"""
Backfill historical dividends for all symbols.
Source: Polygon.io reference API
"""

import asyncio
import logging
import os
import asyncpg
from datetime import datetime, timedelta
from dotenv import load_dotenv

from src.clients.polygon_client import PolygonClient
from src.services.database_service import DatabaseService
from src.services.validation_service import ValidationService

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# Dividend backfill settings
START_DATE = (datetime.utcnow() - timedelta(days=365*10)).date()  # 10 years
END_DATE = datetime.utcnow().date()

async def fetch_dividends_for_symbol(
    symbol: str,
    polygon_client: PolygonClient,
    start_date: datetime.date,
    end_date: datetime.date
) -> list[dict]:
    """
    Fetch dividends from Polygon API for a symbol.
    
    Returns:
        List of dividend records from API
    """
    try:
        logger.info(f"Fetching dividends for {symbol} ({start_date} to {end_date})")
        
        # Polygon endpoint: GET /v2/reference/dividends?ticker={ticker}&from={from}&to={to}
        url = f"https://api.polygon.io/v2/reference/dividends"
        params = {
            "ticker": symbol,
            "from": start_date.strftime('%Y-%m-%d'),
            "to": end_date.strftime('%Y-%m-%d'),
            "apiKey": os.getenv("POLYGON_API_KEY"),
            "limit": 1000
        }
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get('results', [])
                    logger.info(f"  Fetched {len(results)} dividends for {symbol}")
                    return results
                else:
                    logger.warning(f"  API error {response.status} for {symbol}")
                    return []
    except Exception as e:
        logger.error(f"  Error fetching dividends for {symbol}: {e}")
        return []

async def insert_dividends(
    symbol: str,
    dividends: list[dict],
    db_service: DatabaseService
) -> tuple[int, int]:
    """
    Validate and insert dividends into database.
    
    Returns:
        (inserted_count, skipped_count)
    """
    inserted = 0
    skipped = 0
    
    for div in dividends:
        try:
            # Validate dividend data
            ex_date = div.get('ex_dividend_date')
            amount = div.get('cash_amount')
            
            if not ex_date or not amount:
                logger.warning(f"  {symbol}: Missing ex_date or amount in record")
                skipped += 1
                continue
            
            # Insert or skip if exists
            result = db_service.db.execute(
                """
                INSERT INTO dividends 
                (symbol, ex_date, record_date, pay_date, dividend_amount, dividend_type, currency)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol, ex_date) DO NOTHING
                """,
                (
                    symbol,
                    ex_date,
                    div.get('record_date'),
                    div.get('pay_date'),
                    float(amount),
                    div.get('dividend_type', 'regular'),
                    div.get('currency', 'USD')
                )
            )
            
            if result == "INSERT 0 1":
                inserted += 1
            else:
                skipped += 1
        
        except Exception as e:
            logger.error(f"  {symbol}: Error inserting dividend: {e}")
            skipped += 1
    
    return inserted, skipped

async def backfill_dividends(symbols: list[str] = None) -> None:
    """Main backfill function"""
    
    database_url = os.getenv("DATABASE_URL") or construct_db_url()
    polygon_api_key = os.getenv("POLYGON_API_KEY")
    
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY not set")
        return
    
    polygon_client = PolygonClient(polygon_api_key)
    db_service = DatabaseService(database_url)
    
    # Get symbols if not provided
    if not symbols:
        conn = await asyncpg.connect(database_url)
        rows = await conn.fetch(
            "SELECT symbol FROM tracked_symbols WHERE active = TRUE AND asset_class = 'stock'"
        )
        symbols = [row['symbol'] for row in rows]
        await conn.close()
    
    logger.info(f"Starting dividend backfill for {len(symbols)} symbols")
    logger.info(f"Date range: {START_DATE} to {END_DATE}")
    logger.info("-" * 60)
    
    total_inserted = 0
    total_skipped = 0
    
    for symbol in symbols:
        dividends = await fetch_dividends_for_symbol(
            symbol,
            polygon_client,
            START_DATE,
            END_DATE
        )
        
        if dividends:
            inserted, skipped = await insert_dividends(symbol, dividends, db_service)
            total_inserted += inserted
            total_skipped += skipped
            logger.info(f"  ✓ {symbol}: Inserted {inserted}, Skipped {skipped}")
        else:
            logger.info(f"  - {symbol}: No dividend data")
    
    logger.info("-" * 60)
    logger.info(f"Dividend backfill complete!")
    logger.info(f"Total inserted: {total_inserted}")
    logger.info(f"Total skipped: {total_skipped}")

if __name__ == "__main__":
    asyncio.run(backfill_dividends())
```

#### Script 2: `scripts/backfill_splits.py`

Similar structure to dividends but targeting stock splits endpoint.

### 1.4 Polygon API Integration

Add methods to `src/clients/polygon_client.py`:

```python
async def fetch_dividends(
    self,
    symbol: str,
    start: str,
    end: str
) -> List[Dict]:
    """
    Fetch historical dividends for a symbol.
    
    Args:
        symbol: Stock ticker
        start: Start date YYYY-MM-DD
        end: End date YYYY-MM-DD
    
    Returns:
        List of dividend records
    """
    url = f"{self.base_url}/reference/dividends"
    params = {
        "ticker": symbol,
        "from": start,
        "to": end,
        "apiKey": self.api_key,
        "limit": 1000
    }
    # Implementation...

async def fetch_splits(
    self,
    symbol: str,
    start: str,
    end: str
) -> List[Dict]:
    """
    Fetch historical stock splits for a symbol.
    """
    # Implementation...
```

### 1.5 Validation Service

Add to `src/services/validation_service.py`:

```python
def validate_dividend(self, symbol: str, dividend: dict) -> tuple[bool, dict]:
    """
    Validate dividend record.
    
    Returns:
        (is_valid, metadata)
    """
    metadata = {
        'symbol': symbol,
        'validation_errors': [],
        'warnings': []
    }
    
    # Checks
    if not dividend.get('ex_dividend_date'):
        metadata['validation_errors'].append("Missing ex_dividend_date")
    
    if not dividend.get('cash_amount'):
        metadata['validation_errors'].append("Missing cash_amount")
    
    amount = float(dividend.get('cash_amount', 0))
    if amount < 0:
        metadata['validation_errors'].append("Negative dividend amount")
    
    if amount > 100:  # Sanity check
        metadata['warnings'].append(f"Unusually high dividend: ${amount}")
    
    is_valid = len(metadata['validation_errors']) == 0
    return is_valid, metadata

def validate_split(self, symbol: str, split: dict) -> tuple[bool, dict]:
    """Validate stock split record."""
    # Similar validation logic
```

### 1.6 Database Service Methods

Add to `src/services/database_service.py`:

```python
def insert_dividends_batch(self, dividends: list[dict]) -> int:
    """Insert batch of dividend records. Returns count inserted."""
    # Batch insert logic

def insert_splits_batch(self, splits: list[dict]) -> int:
    """Insert batch of split records. Returns count inserted."""
    # Batch insert logic

def calculate_adjusted_price(
    self,
    symbol: str,
    timestamp: int,
    price: float
) -> tuple[float, float]:
    """
    Calculate dividend and split adjusted price.
    
    Returns:
        (adjusted_price, adjustment_factor)
    """
    # Logic to fetch all dividends/splits up to timestamp
    # and calculate cumulative adjustment
```

### 1.7 API Endpoint for Adjusted Data

Add to `src/main.py`:

```python
@app.get("/api/v1/ohlcv/{symbol}/adjusted")
async def get_adjusted_ohlcv(
    symbol: str,
    timeframe: str = "1d",
    start: str = None,
    end: str = None,
    include_dividends: bool = True,
    include_splits: bool = True
):
    """
    Get OHLCV data with dividend and split adjustments.
    
    Returns:
        OHLCV candles with adjusted prices and adjustment notes
    """
    # Fetch raw OHLCV
    # Fetch dividends and splits
    # Apply adjustments
    # Return adjusted data with metadata
```

### 1.8 Testing

```python
# tests/test_dividends.py
def test_validate_dividend():
    pass

def test_insert_dividends_batch():
    pass

def test_calculate_adjusted_price():
    pass

def test_adjusted_ohlcv_endpoint():
    pass
```

### 1.9 Execution Commands

```bash
# Backfill dividends for all stocks
docker exec market_data_api python scripts/backfill_dividends.py

# Backfill splits for all stocks
docker exec market_data_api python scripts/backfill_splits.py

# Get adjusted OHLCV
curl http://localhost:8000/api/v1/ohlcv/AAPL/adjusted?timeframe=1d&start=2024-01-01
```

---

## Phase 2: News & Sentiment (Weeks 3-4)

### 2.1 Architecture

```
Polygon API (News endpoint)
    ↓
NLP/Sentiment Service (TextBlob or Transformers)
    ↓
backfill_news.py (new script)
    ↓
ValidationService.validate_news()
    ↓
Database (news table)
    ↓
API Endpoint: /api/v1/news/{symbol}
API Endpoint: /api/v1/sentiment/{symbol}
```

### 2.2 Database Schema

```sql
CREATE TABLE news (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    url VARCHAR(500) NOT NULL,
    image_url VARCHAR(500),
    author VARCHAR(255),
    source VARCHAR(100),
    published_at TIMESTAMP NOT NULL,
    
    -- Sentiment fields
    sentiment_score DECIMAL(4, 3), -- -1.0 to 1.0
    sentiment_label VARCHAR(20), -- 'bearish', 'neutral', 'bullish'
    sentiment_confidence DECIMAL(4, 3), -- 0.0 to 1.0
    
    -- Keywords/topics
    keywords TEXT[], -- array of extracted keywords
    topics VARCHAR(100)[], -- extracted topics
    
    -- Metadata
    is_premium BOOLEAN DEFAULT FALSE,
    word_count INT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, url),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX idx_news_symbol ON news(symbol);
CREATE INDEX idx_news_published_at ON news(published_at);
CREATE INDEX idx_news_sentiment ON news(sentiment_label);

-- Materialized view for daily sentiment aggregates
CREATE MATERIALIZED VIEW daily_sentiment_aggregate AS
SELECT
    symbol,
    DATE(published_at) as sentiment_date,
    AVG(sentiment_score) as avg_sentiment,
    COUNT(*) as article_count,
    ARRAY_AGG(DISTINCT sentiment_label) as sentiment_distribution
FROM news
GROUP BY symbol, DATE(published_at);
```

### 2.3 Sentiment Analysis Service

Create `src/services/sentiment_service.py`:

```python
"""
Sentiment analysis for news articles.
Uses transformer models (DistilBERT) or TextBlob fallback.
"""

from transformers import pipeline
from textblob import TextBlob
import logging

logger = logging.getLogger(__name__)

class SentimentService:
    def __init__(self, use_transformers: bool = True):
        self.use_transformers = use_transformers
        
        if use_transformers:
            # DistilBERT financial sentiment model
            try:
                self.sentiment_pipeline = pipeline(
                    "sentiment-analysis",
                    model="distilbert-base-uncased-finetuned-sst-2-english"
                )
            except Exception as e:
                logger.warning(f"Failed to load transformers model: {e}. Falling back to TextBlob.")
                self.use_transformers = False
    
    def analyze_text(self, text: str) -> dict:
        """
        Analyze sentiment of text.
        
        Returns:
            {
                'sentiment_score': float (-1.0 to 1.0),
                'sentiment_label': str ('bearish', 'neutral', 'bullish'),
                'confidence': float (0.0 to 1.0)
            }
        """
        if not text:
            return {'sentiment_score': 0.0, 'sentiment_label': 'neutral', 'confidence': 0.0}
        
        # Clean text
        text = text.strip()[:512]  # Limit to 512 chars for performance
        
        if self.use_transformers:
            result = self.sentiment_pipeline(text)[0]
            label = result['label']  # 'POSITIVE' or 'NEGATIVE'
            score = result['score']  # 0.0 to 1.0
            
            # Convert to -1 to 1 scale
            if label == 'POSITIVE':
                sentiment_score = score
                sentiment_label = 'bullish' if score > 0.7 else 'neutral'
            else:
                sentiment_score = -score
                sentiment_label = 'bearish' if score > 0.7 else 'neutral'
        else:
            # Fallback to TextBlob
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity  # -1 to 1
            sentiment_score = polarity
            
            if polarity > 0.1:
                sentiment_label = 'bullish' if polarity > 0.5 else 'neutral'
            elif polarity < -0.1:
                sentiment_label = 'bearish' if polarity < -0.5 else 'neutral'
            else:
                sentiment_label = 'neutral'
            
            score = abs(polarity)
        
        return {
            'sentiment_score': sentiment_score,
            'sentiment_label': sentiment_label,
            'confidence': score
        }
    
    def extract_keywords(self, text: str, max_keywords: int = 5) -> list[str]:
        """Extract keywords from text."""
        # Simple implementation using TextBlob
        blob = TextBlob(text)
        words = [word for word in blob.words.lower() if len(word) > 4]
        # Remove stopwords, return top N
        return words[:max_keywords]
```

### 2.4 Backfill Script

Create `scripts/backfill_news.py`:

```python
#!/usr/bin/env python3
"""
Backfill historical news and sentiment for all symbols.
Source: Polygon.io News API
"""

import asyncio
from datetime import datetime, timedelta
import logging

from src.clients.polygon_client import PolygonClient
from src.services.sentiment_service import SentimentService
from src.services.database_service import DatabaseService

logger = logging.getLogger(__name__)

# Backfill 2 years of historical news
START_DATE = (datetime.utcnow() - timedelta(days=365*2)).date()
END_DATE = datetime.utcnow().date()

async def backfill_news(symbols: list[str] = None, limit_per_symbol: int = 1000):
    """
    Backfill news for all symbols.
    
    Args:
        symbols: List of symbols (if None, fetch all active)
        limit_per_symbol: Max articles per symbol
    """
    db_service = DatabaseService(get_db_url())
    polygon_client = PolygonClient(get_api_key())
    sentiment_service = SentimentService(use_transformers=True)
    
    if not symbols:
        symbols = db_service.get_active_symbols()
    
    logger.info(f"Backfilling news for {len(symbols)} symbols")
    
    total_inserted = 0
    
    for symbol in symbols:
        try:
            # Fetch news from Polygon
            url = f"https://api.polygon.io/v2/reference/news"
            params = {
                "ticker": symbol,
                "from": START_DATE.strftime('%Y-%m-%d'),
                "to": END_DATE.strftime('%Y-%m-%d'),
                "limit": limit_per_symbol,
                "apiKey": get_api_key()
            }
            
            # GET request and parse results...
            articles = []  # fetch_news(url, params)
            
            for article in articles:
                try:
                    # Analyze sentiment
                    text = f"{article['title']} {article.get('description', '')}"
                    sentiment = sentiment_service.analyze_text(text)
                    keywords = sentiment_service.extract_keywords(text)
                    
                    # Insert into database
                    db_service.db.execute(
                        """
                        INSERT INTO news 
                        (symbol, title, description, url, image_url, author, source, published_at,
                         sentiment_score, sentiment_label, sentiment_confidence, keywords)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, url) DO NOTHING
                        """,
                        (
                            symbol,
                            article['title'],
                            article.get('description'),
                            article['url'],
                            article.get('image_url'),
                            article.get('author'),
                            article.get('source'),
                            article['published_at'],
                            sentiment['sentiment_score'],
                            sentiment['sentiment_label'],
                            sentiment['confidence'],
                            keywords
                        )
                    )
                    total_inserted += 1
                
                except Exception as e:
                    logger.error(f"Error processing article for {symbol}: {e}")
        
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
    
    logger.info(f"News backfill complete. Inserted: {total_inserted}")

if __name__ == "__main__":
    asyncio.run(backfill_news())
```

### 2.5 API Endpoints

```python
@app.get("/api/v1/news/{symbol}")
async def get_news(
    symbol: str,
    days: int = 30,
    limit: int = 50,
    sentiment_filter: str = None  # 'bullish', 'bearish', 'neutral'
):
    """Get recent news for symbol with sentiment."""
    # Fetch from news table filtered by date/sentiment

@app.get("/api/v1/sentiment/{symbol}")
async def get_sentiment_aggregate(
    symbol: str,
    days: int = 30
):
    """Get aggregated sentiment metrics."""
    # Query daily_sentiment_aggregate view
    # Return: avg_sentiment, article_count, distribution
```

---

## Phase 3: Earnings & IV (Weeks 4-6)

### 3.1 Earnings Data

```sql
CREATE TABLE earnings (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    earnings_date DATE NOT NULL,
    earnings_time VARCHAR(20), -- 'bmo', 'amc', 'after_hours'
    
    -- Estimates
    estimated_eps DECIMAL(12, 4),
    estimated_revenue DECIMAL(18, 2),
    
    -- Actuals
    actual_eps DECIMAL(12, 4),
    actual_revenue DECIMAL(18, 2),
    
    -- Metrics
    surprise_eps DECIMAL(12, 4),
    surprise_eps_pct DECIMAL(8, 4),
    surprise_revenue DECIMAL(18, 2),
    surprise_revenue_pct DECIMAL(8, 4),
    
    -- Context
    prior_eps DECIMAL(12, 4),
    fy_guidance VARCHAR(255),
    conference_call_url VARCHAR(500),
    
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, earnings_date),
    FOREIGN KEY (symbol) REFERENCES tracked_symbols(symbol)
);

CREATE INDEX idx_earnings_symbol ON earnings(symbol);
CREATE INDEX idx_earnings_date ON earnings(earnings_date);
```

Script: `scripts/backfill_earnings.py` (Benzinga API via Polygon)

### 3.2 Options IV Data

```sql
CREATE TABLE options_iv (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    timestamp BIGINT NOT NULL, -- Unix ms
    expiration_date DATE NOT NULL,
    strike_price DECIMAL(12, 4) NOT NULL,
    
    -- IV metrics
    implied_volatility DECIMAL(8, 6),
    iv_rank DECIMAL(5, 2), -- 0-100
    iv_percentile DECIMAL(5, 2), -- 0-100
    
    -- Greeks (optional)
    delta DECIMAL(5, 4),
    gamma DECIMAL(8, 6),
    vega DECIMAL(8, 6),
    theta DECIMAL(8, 6),
    
    -- Market data
    bid_price DECIMAL(12, 4),
    ask_price DECIMAL(12, 4),
    last_price DECIMAL(12, 4),
    volume INT,
    open_interest INT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(symbol, timestamp, expiration_date, strike_price)
);

CREATE INDEX idx_options_iv_symbol ON options_iv(symbol);
CREATE INDEX idx_options_iv_timestamp ON options_iv(timestamp);
```

---

## Integration Points

### 3.3 ML Feature Engineering

Create `src/services/feature_service.py`:

```python
class FeatureService:
    def calculate_dividend_yield(self, symbol: str, current_price: float) -> float:
        """Calculate TTM dividend yield."""
        
    def calculate_earnings_surprise_score(self, symbol: str, days_back: int = 180) -> float:
        """Calculate average earnings surprise (normalized)."""
        
    def get_sentiment_features(self, symbol: str, lookback_days: int = 30) -> dict:
        """Return sentiment aggregates for ML models."""
        # avg_sentiment, volatility_of_sentiment, acceleration
        
    def get_volatility_regime(self, symbol: str, timeframe: str = '1d') -> str:
        """Determine IV regime: 'high', 'medium', 'low'."""
```

### 3.4 Backtest Integration

Modify backtesting engine to use adjusted prices:

```python
# In backtesting system
def get_price_for_backtest(symbol: str, timestamp: int, use_adjusted: bool = True) -> float:
    if use_adjusted:
        return db.get_adjusted_close(symbol, timestamp)
    else:
        return db.get_raw_close(symbol, timestamp)
```

---

## Implementation Checklist

### Phase 1: Dividends & Splits
- [ ] Create database tables
- [ ] Add Polygon API client methods
- [ ] Write validation logic
- [ ] Create backfill scripts (dividends & splits)
- [ ] Add database service methods
- [ ] Create `/adjusted` API endpoint
- [ ] Write tests
- [ ] Execute backfill
- [ ] Verify data quality

### Phase 2: News & Sentiment
- [ ] Create news table
- [ ] Implement sentiment analysis service
- [ ] Create news backfill script
- [ ] Add API endpoints (/news, /sentiment)
- [ ] Create materialized views for aggregates
- [ ] Write tests
- [ ] Execute backfill (2-year window)
- [ ] Monitor sentiment model performance

### Phase 3: Earnings & IV
- [ ] Create earnings table
- [ ] Create options_iv table
- [ ] Write backfill scripts
- [ ] Add API endpoints
- [ ] Integrate into feature engineering
- [ ] Write tests
- [ ] Execute backfills

### Phase 4: Integration
- [ ] Create FeatureService for ML
- [ ] Integrate into backtesting engine
- [ ] Add data validation pipeline
- [ ] Create monitoring dashboards
- [ ] Documentation

---

## Data Quality Assurance

### Validation Rules

1. **Dividends**
   - ex_date ≥ record_date ≥ pay_date
   - dividend_amount > 0
   - No duplicate ex_dates per symbol

2. **Splits**
   - split_from > 0 and split_to > 0
   - No more than 1 split per week (anomaly detection)

3. **News**
   - Title length: 10-200 chars
   - Sentiment score: -1.0 to 1.0
   - Published date ≤ current date

4. **Earnings**
   - EPS and revenue > 0
   - surprise_pct = (actual - estimate) / estimate
   - No future earnings_dates

### Monitoring

```python
# Create monitoring queries
SELECT 
    COUNT(*) as dividend_count,
    COUNT(DISTINCT symbol) as symbols_with_dividends,
    MAX(ex_date) as latest_dividend
FROM dividends;

SELECT 
    COUNT(*) as news_count,
    COUNT(DISTINCT symbol) as symbols_with_news,
    AVG(sentiment_score) as avg_market_sentiment
FROM news
WHERE published_at > NOW() - INTERVAL '7 days';
```

---

## API Rate Limiting Strategy

| Endpoint | Requests/min | Batch Strategy |
|----------|--------------|-----------------|
| /dividends | 50 | 100 symbols/request |
| /splits | 50 | 100 symbols/request |
| /news | 50 | 5 symbols/request |
| /earnings | 30 | 50 symbols/request |

Use queue system in backfill scripts to respect rate limits.

---

## Success Metrics

After Phase 1-3 completion, measure:

1. **Data Coverage**
   - % of symbols with dividend history
   - % of symbols with news coverage
   - % of symbols with earnings data

2. **Backtesting Accuracy**
   - Adjust previous backtests with dividend adjustments
   - Verify no false price movements

3. **ML Model Improvement**
   - Sentiment model accuracy (classify news correctly)
   - Feature correlation with price movements
   - Model accuracy improvement vs. OHLCV-only baseline

4. **API Performance**
   - Endpoint latency for adjusted prices
   - News retrieval speed

---

## Timeline Summary

```
Week 1-2: Dividends & Splits
  - Day 1-2: Schema, client methods
  - Day 3-4: Backfill scripts, validation
  - Day 5: Testing, execution
  - Day 6-10: Data verification, fixes

Week 3-4: News & Sentiment
  - Day 1: Sentiment service, NLP setup
  - Day 2-3: Backfill script, API endpoints
  - Day 4: Testing, 2-year backfill
  - Day 5-10: Model validation, tuning

Week 5-6: Earnings & IV
  - Day 1: Schema, backfill scripts
  - Day 2-3: API integration, testing
  - Day 4-10: Backfill, validation

Week 7: Integration & Polish
  - Feature engineering layer
  - Backtesting integration
  - Documentation
  - Monitoring setup
```

---

## Dependencies to Add

```
# requirements.txt additions
transformers==4.35.0  # For sentiment analysis
torch==2.0.0  # For transformers
textblob==0.17.1  # Fallback sentiment
aiohttp==3.9.0  # Already have
asyncpg==0.29.0  # Already have
```

---

## Post-Implementation

### Documentation
- [ ] Update API docs with new endpoints
- [ ] Create feature engineering guide
- [ ] Write backtest integration tutorial

### Monitoring
- [ ] Set up data freshness alerts
- [ ] Track sentiment model accuracy
- [ ] Monitor API rate limits

### Future Enhancements
- Real-time news streaming via WebSocket
- Custom sentiment model fine-tuning
- Options flow analysis
- Insider transaction tracking
