# Backfill Guide

Two-step backfill process for market data.

## Step 1: Backfill OHLCV (Price/Volume Data)

Fetches standard candlestick data (Open, High, Low, Close, Volume).

```bash
# Backfill all active symbols with daily data
python scripts/backfill_ohlcv.py

# Backfill specific symbols with hourly data
python scripts/backfill_ohlcv.py --symbols AAPL,MSFT --timeframe 1h

# Custom date range
python scripts/backfill_ohlcv.py --start 2023-01-01 --end 2024-01-01 --timeframe 1d
```

**Options:**
- `--symbols` - Comma-separated list (AAPL,MSFT,GOOGL). If omitted, uses all active symbols
- `--timeframe` - 5m, 15m, 30m, 1h, 4h, 1d (default), 1w
- `--start` - Start date (YYYY-MM-DD)
- `--end` - End date (YYYY-MM-DD)

## Step 2: Backfill Enhancements (Additional Data)

Fetches news, earnings, dividends, options, and adjusted prices.

```bash
# Backfill all enhancement data
python scripts/backfill_enhancements.py

# Backfill specific symbols
python scripts/backfill_enhancements.py --symbols AAPL,MSFT

# Skip specific data types
python scripts/backfill_enhancements.py --skip-news --skip-options
```

**Options:**
- `--symbols` - Comma-separated list
- `--start` - Start date (YYYY-MM-DD)
- `--end` - End date (YYYY-MM-DD)
- `--skip-news` - Skip news/sentiment
- `--skip-dividends` - Skip dividends
- `--skip-splits` - Skip stock splits
- `--skip-earnings` - Skip earnings
- `--skip-options` - Skip options IV
- `--skip-adjusted` - Skip adjusted prices

## Typical Workflow

```bash
# 1. Full backfill (OHLCV + enhancements)
python scripts/backfill_ohlcv.py --symbols AAPL,MSFT
python scripts/backfill_enhancements.py --symbols AAPL,MSFT

# 2. Multiple timeframes
python scripts/backfill_ohlcv.py --timeframe 1d
python scripts/backfill_ohlcv.py --timeframe 1h
python scripts/backfill_enhancements.py
```

## Notes

- Always run `backfill_ohlcv.py` before `backfill_enhancements.py`
- Each script is idempotent (safe to re-run)
- Progress logged to console and API logs
