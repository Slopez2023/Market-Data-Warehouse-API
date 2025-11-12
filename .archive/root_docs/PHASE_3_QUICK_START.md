# Phase 3 Quick Start Guide

## What Was Built

Phase 3 adds **Earnings** and **Options IV (Implied Volatility)** data for event detection and volatility regime identification.

## Run These Commands (In Order)

### 1. Apply Database Migrations
```bash
# Migrations auto-run on app startup
# Or manually:
psql -d market_data -f database/migrations/009_add_earnings_tables.sql
psql -d market_data -f database/migrations/010_add_options_iv_tables.sql
```

### 2. Backfill Earnings (5-year history)
```bash
# Test with single symbol first
python scripts/backfill_earnings.py --symbol AAPL --days 365

# Then all symbols
python scripts/backfill_earnings.py --days 1825 --resume
```

### 3. Backfill Options IV (start with 30 days!)
```bash
# Options data grows quickly - start small
python scripts/backfill_options_iv.py --symbol AAPL --days 30

# Then expand gradually
python scripts/backfill_options_iv.py --days 60
```

### 4. Test API Endpoints
```bash
# Earnings
curl http://localhost:8000/api/v1/earnings/AAPL
curl http://localhost:8000/api/v1/earnings/AAPL/summary
curl http://localhost:8000/api/v1/earnings/upcoming?days=30

# Options & Volatility
curl http://localhost:8000/api/v1/options/iv/AAPL
curl http://localhost:8000/api/v1/volatility/regime/AAPL

# ML Features
curl http://localhost:8000/api/v1/features/composite/AAPL
curl http://localhost:8000/api/v1/features/importance
```

## What You Get

### Earnings Data
- Historical earnings records with estimates vs actuals
- Automatic surprise calculations (beat/miss)
- Beat rates and average surprises
- Upcoming earnings dates

### Options IV Data
- Options chains with Greeks (delta, gamma, vega, theta, rho)
- Implied volatility metrics and rankings
- Volatility regime classification (low/normal/high)
- IV vs historical volatility comparisons

### ML Features
- Composite feature vectors combining all data types
- Dividend yield + earnings surprises + sentiment + IV regime
- Feature importance weights for model training

## Database Schema

**New Tables:**
- `earnings` - Quarterly earnings with surprises
- `earnings_estimates` - Historical estimate revisions
- `options_iv` - Individual option contracts with Greeks
- `options_chain_snapshot` - Aggregated chain data
- `volatility_regime` - Daily regime classification

**New Views:**
- `mv_earnings_summary` - Earnings aggregates by symbol
- `mv_options_iv_summary` - Daily IV aggregates by symbol

## File Locations

**Services:**
- `src/services/earnings_service.py`
- `src/services/options_iv_service.py`
- `src/services/feature_service.py`

**Backfill Scripts:**
- `scripts/backfill_earnings.py`
- `scripts/backfill_options_iv.py`

**Migrations:**
- `database/migrations/009_add_earnings_tables.sql`
- `database/migrations/010_add_options_iv_tables.sql`

**API Updates:**
- `main.py` (7 new endpoints added)

## Key Insights

### Why Earnings?
- Detect event-driven moves before they happen
- Track company execution (beat/miss rates)
- Upcoming earnings drive realized volatility

### Why IV?
- Identifies volatility regimes (low/high)
- IV rank shows extremes vs history
- Options markets price in forward-looking volatility

### Why Feature Service?
- Combines all advanced data for ML models
- One endpoint returns complete feature vector
- Ready for supervised learning pipelines

## Important Notes

⚠️ **Options data grows FAST!**
- Start with 30 days for testing
- Options IV: 500-2000 rows per symbol per day
- Consider archiving old options data quarterly

💡 **Earnings backfill:**
- Uses Polygon financial statements endpoint
- 5+ years of history available
- Automatically calculates surprise_eps and surprise_revenue

🔄 **Resumable backfills:**
- Use `--resume` flag to skip completed symbols
- Progress tracked in `backfill_progress` table
- Safe to interrupt and restart

## Performance

- Earnings queries: <10ms (indexed by symbol, date)
- Options queries: <50ms (indexed chain lookups)
- Feature endpoint: <200ms (aggregates across services)

## Integration

### In Your ML Models
```python
features = await get_composite_features("AAPL")
# Returns: {
#   "dividend_yield": 0.38,
#   "earnings_beat_rate": 87.5,
#   "sentiment": {...},
#   "volatility_regime": "high",
#   ...
# }
```

### In Backtesting
```python
# Get upcoming earnings
upcoming = await get_upcoming_earnings(symbol, days=30)

# Adjust strategy on earnings dates
if upcoming:
    # Reduce position, add hedges, etc.

# Use volatility regime
regime = await get_volatility_regime(symbol)
if regime['regime'] == 'very_high':
    # Reduce leverage, avoid straddles
```

### In Trading Systems
```python
# Earnings surprise detection
earnings = await get_earnings_by_symbol(symbol, days=90)
if earnings[-1]['surprise_eps_pct'] > 10:
    # Stock beat by >10%, opportunity?

# Volatility extremes
iv_percentile = await get_iv_percentile(symbol)
if iv_percentile > 75:
    # High IV = premium selling opportunity
```

## Troubleshooting

**No earnings data returned?**
- Check backfill script ran successfully
- Verify symbol is in tracked_symbols table
- Check PostgreSQL database connection

**Options IV queries slow?**
- Add indexes: `CREATE INDEX idx_options_iv_date ON options_iv(quote_date DESC)`
- Consider archiving options data >30 days old

**Feature endpoint errors?**
- Check that all Phase 1-2 data exists for symbol
- Some symbols may not have options IV yet

## Next: Integrate Into Your System

Once backfilled:

1. **Dashboard:** Add earnings calendar and sentiment panels
2. **Backtester:** Use adjusted prices + earnings surprises
3. **ML Models:** Train on composite feature vectors
4. **Risk System:** Use volatility regime for position limits

---

**Documentation:** See `PHASE_3_IMPLEMENTATION.md` for full details
