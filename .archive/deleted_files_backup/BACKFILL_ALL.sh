#!/bin/bash
set -e

echo "=========================================="
echo "FULL MARKET DATA BACKFILL"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Backfill all timeframes for OHLCV
echo -e "${BLUE}[1/5]${NC} Backfilling daily (1d) candles..."
python scripts/backfill_ohlcv.py --timeframe 1d
echo -e "${GREEN}✓ Daily complete${NC}\n"

echo -e "${BLUE}[2/5]${NC} Backfilling 4-hour (4h) candles..."
python scripts/backfill_ohlcv.py --timeframe 4h
echo -e "${GREEN}✓ 4h complete${NC}\n"

echo -e "${BLUE}[3/5]${NC} Backfilling hourly (1h) candles..."
python scripts/backfill_ohlcv.py --timeframe 1h
echo -e "${GREEN}✓ 1h complete${NC}\n"

echo -e "${BLUE}[4/5]${NC} Backfilling 30-minute candles..."
python scripts/backfill_ohlcv.py --timeframe 30m
echo -e "${GREEN}✓ 30m complete${NC}\n"

echo -e "${BLUE}[5/5]${NC} Backfilling enhancements (news, earnings, dividends, options)..."
python scripts/backfill_enhancements.py
echo -e "${GREEN}✓ Enhancements complete${NC}\n"

echo "=========================================="
echo -e "${GREEN}✓ ALL BACKFILLS COMPLETE${NC}"
echo "=========================================="
