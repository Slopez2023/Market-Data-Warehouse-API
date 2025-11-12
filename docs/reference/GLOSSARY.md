# Glossary of Terms

## Market Data Terms

### OHLCV
**Open, High, Low, Close, Volume** - The standard data point for market candles.
- **Open**: Price at start of period
- **High**: Highest price during period
- **Low**: Lowest price during period
- **Close**: Price at end of period
- **Volume**: Total shares/contracts traded

Example: `{"open": 150.25, "high": 151.50, "low": 149.75, "close": 150.80, "volume": 45000000}`

### Timeframe
A time period for candlestick data. This API supports 7 timeframes:
- **5m**: 5-minute candles
- **15m**: 15-minute candles
- **30m**: 30-minute candles
- **1h**: 1-hour candles
- **4h**: 4-hour candles
- **1d**: 1-day candles
- **1w**: 1-week candles

### Ticker / Symbol
A short code representing a security:
- **Stocks**: AAPL (Apple), MSFT (Microsoft), TSLA (Tesla)
- **ETFs**: SPY (S&P 500), QQQ (Nasdaq-100)
- **Crypto**: BTC (Bitcoin), ETH (Ethereum)

### Candle
A single OHLCV data point representing price action over a timeframe. Example for BTC/1h:
```json
{
  "symbol": "BTC",
  "timeframe": "1h",
  "timestamp": "2024-01-15T14:00:00Z",
  "open": 42150.50,
  "high": 42325.00,
  "low": 42100.00,
  "close": 42280.75,
  "volume": 1250
}
```

### Backfill
The process of importing historical market data from Polygon.io into the database. Usually happens automatically on schedule.

### Quality Score
A metric (0.0 to 1.0) indicating data quality. Factors include:
- Missing values
- Outliers
- Validation rule violations
- Consistency with adjacent candles

Example: `"quality_score": 0.95` means high-quality data.

---

## Technical Terms

### API Key
A unique identifier used to authenticate requests to admin endpoints. Format: UUID string (36 characters).

Example: `550e8400-e29b-41d4-a716-446655440000`

### Middleware
Software layer that processes requests/responses before reaching the main application. Used for:
- Authentication (API keys)
- Observability (logging, tracing)
- CORS handling

### Async/Await
Programming pattern for handling asynchronous operations without blocking. Allows concurrent request processing.

### Connection Pool
A cache of database connections ready for use. Improves performance by reusing connections instead of creating new ones each time.

### TTL (Time To Live)
Duration a cached value remains valid. After TTL expires, the cache is invalidated and fresh data is fetched.

Example: `TTL=300` means cache valid for 300 seconds (5 minutes).

### Pagination
Breaking results into smaller pages. Useful for large result sets:
- Offset: Skip first N results
- Limit: Return max N results

Example: `?offset=100&limit=50` returns results 100-150.

---

## Analytics Terms

### Earnings Beat/Miss
Comparison of actual earnings vs. analyst estimates:
- **Beat**: Actual > Estimate (positive)
- **Meet**: Actual = Estimate (neutral)
- **Miss**: Actual < Estimate (negative)

### Earnings Surprise
The percentage difference: `(Actual - Estimate) / Estimate * 100`

Example: If estimated EPS is $1.00 and actual is $1.10:
- Surprise = (1.10 - 1.00) / 1.00 * 100 = 10% beat

### Implied Volatility (IV)
Market's expectation of future price volatility derived from option prices. Range: 0-100+.
- **Low IV**: Market expects low volatility
- **High IV**: Market expects high volatility

### Volatility Regime
Classification of current volatility level:
- **Very Low**: IV in bottom 10%
- **Low**: IV in 10-25%
- **Normal**: IV in 25-75%
- **High**: IV in 75-90%
- **Very High**: IV in top 10%

### Sentiment Score
Numerical representation of text sentiment. Range: -1 to 1.
- **Negative**: < -0.3 (bearish)
- **Neutral**: -0.3 to 0.3
- **Positive**: > 0.3 (bullish)

### Greeks
Option pricing sensitivity metrics:
- **Delta**: Change in option price per $1 stock move
- **Gamma**: Change in delta per $1 stock move
- **Theta**: Daily time decay value
- **Vega**: Change per 1% volatility move
- **Rho**: Change per 1% interest rate move

---

## Operational Terms

### Health Check / Liveness Probe
An endpoint that returns the system status. Used by infrastructure to detect failures.

Example: `GET /health` returns `{"status": "healthy"}`

### Metrics
Quantitative measurements of system performance:
- Request count
- Error rate
- Response latency
- Cache hit rate
- Database connection pool usage

### Alert
Notification triggered when a metric exceeds a threshold. Examples:
- High error rate (>5%)
- Slow response time (>1s)
- Database disconnected

### Structured Logging
Machine-readable log format (JSON) containing:
- Timestamp
- Log level
- Message
- Trace ID
- Context fields

Example:
```json
{
  "timestamp": "2024-01-15T14:30:45.123Z",
  "level": "INFO",
  "message": "Query completed",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "duration_ms": 142,
  "cache_hit": true
}
```

### Trace ID
Unique identifier following a request through all system components. Useful for debugging.

### Request Validation
Checks that incoming request data is correct:
- Required fields present
- Data types correct
- Values within allowed ranges

### Rate Limiting
Restricting number of requests from a source. Prevents abuse and ensures fair resource use.

---

## Database Terms

### TimescaleDB
PostgreSQL extension optimized for time-series data. Provides:
- Automatic table partitioning
- Compression
- Specialized indexes
- Performance optimizations

### Schema
Structure defining tables, columns, and relationships. Our main tables:
- `ohlcv`: Market candle data
- `api_keys`: Authentication keys
- `audit_logs`: Operation history
- `backfill_history`: Data import history

### Query
Request for data from the database. Examples:
- `SELECT * FROM ohlcv WHERE symbol = 'AAPL'` (get all AAPL data)
- `SELECT COUNT(*) FROM ohlcv` (count all records)

### Transaction
Group of database operations that succeed or fail together. Ensures data consistency.

### Index
Data structure speeding up queries. Common indexes in this system:
- Symbol + timeframe
- Timestamp
- Quality score

---

## Deployment Terms

### Docker
Tool for containerizing applications. A container is a lightweight, isolated environment with all dependencies included.

### Docker Compose
Tool for defining and running multi-container applications. Our setup:
- API container
- Database container
- Dashboard container

### Environment Variables
Configuration values passed to the application via the environment:
- `POLYGON_API_KEY`: API key for Polygon.io
- `DB_PASSWORD`: Database password
- `LOG_LEVEL`: Logging verbosity

### Volume
Persistent data storage mounted into a container. Used for database files to survive container restart.

### Network
Docker network connecting containers. Allows containers to communicate using service names.

Example: API container reaches database via `postgresql://market_data_db:5432/market_data`

---

## Common Abbreviations

| Abbreviation | Meaning |
|--------------|---------|
| OHLCV | Open, High, Low, Close, Volume |
| IV | Implied Volatility |
| HV | Historical Volatility |
| ML | Machine Learning |
| API | Application Programming Interface |
| HTTP | HyperText Transfer Protocol |
| REST | Representational State Transfer |
| JSON | JavaScript Object Notation |
| UTC | Coordinated Universal Time (Zulu time) |
| TTL | Time To Live |
| CRUD | Create, Read, Update, Delete |
| SQL | Structured Query Language |
| EPS | Earnings Per Share |
| ETF | Exchange Traded Fund |
| BTC | Bitcoin |
| ETH | Ethereum |
| SPY | S&P 500 ETF |
| QQQ | Nasdaq-100 ETF |

---

## See Also

- [API Endpoints Reference](/docs/api/ENDPOINTS.md)
- [Technology Stack](/docs/reference/TECH_STACK.md)
- [Quick Reference](/docs/reference/QUICK_REFERENCE.md)
- [FAQ](/docs/reference/FAQ.md)
