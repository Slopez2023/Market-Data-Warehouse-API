#!/bin/bash

# Backfill all active stocks with all supported timeframes
# Usage: ./BACKFILL_ALL_TIMEFRAMES.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}Market Data API - Full Backfill (All Timeframes)${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠ .env file not found. Using default environment variables.${NC}"
    echo "  Make sure DATABASE_URL and POLYGON_API_KEY are set."
else
    echo -e "${GREEN}✓ .env file found${NC}"
fi

echo ""

# Define all supported timeframes
TIMEFRAMES=("5m" "15m" "30m" "1h" "4h" "1d" "1w")

# Date range (5 years of data)
END_DATE=$(date -u +%Y-%m-%d)
START_DATE=$(date -u -d "5 years ago" +%Y-%m-%d 2>/dev/null || date -u -v-5y +%Y-%m-%d)

echo -e "${YELLOW}Backfill Configuration:${NC}"
echo "  Date Range: $START_DATE to $END_DATE"
echo "  Timeframes: ${TIMEFRAMES[*]}"
echo ""

# Counter
total_iterations=0
completed=0

for timeframe in "${TIMEFRAMES[@]}"; do
    ((total_iterations++))
done

echo -e "${BLUE}Starting backfill for all timeframes...${NC}"
echo ""

# Backfill each timeframe sequentially
for timeframe in "${TIMEFRAMES[@]}"; do
    ((completed++))
    echo -e "${YELLOW}[${completed}/${total_iterations}] Backfilling all symbols with timeframe: ${GREEN}${timeframe}${NC}"
    echo "-----------------------------------------------------"
    
    python scripts/backfill.py \
        --start "$START_DATE" \
        --end "$END_DATE" \
        --timeframe "$timeframe"
    
    echo ""
done

echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✓ Backfill complete for all timeframes!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

echo -e "${YELLOW}Summary:${NC}"
echo "  All active symbols backfilled with:"
for tf in "${TIMEFRAMES[@]}"; do
    echo "    ✓ $tf"
done
echo ""

echo -e "${YELLOW}Data Summary:${NC}"
python << 'PYSCRIPT'
import os
from dotenv import load_dotenv
from src.services.database_service import DatabaseService

load_dotenv()
database_url = os.getenv('DATABASE_URL')
if database_url:
    try:
        db = DatabaseService(database_url)
        metrics = db.get_status_metrics()
        print(f"  Symbols Available: {metrics.get('symbols_available', 0)}")
        print(f"  Total Records: {metrics.get('total_records', 0):,}")
        print(f"  Validated Records: {metrics.get('validated_records', 0):,}")
        print(f"  Validation Rate: {metrics.get('validation_rate_pct', 0):.1f}%")
        print(f"  Latest Data: {metrics.get('latest_data')}")
    except Exception as e:
        print(f"  Error connecting to database: {e}")
else:
    print("  DATABASE_URL not set")
PYSCRIPT

echo ""
echo -e "${GREEN}Backfill ready for analysis and trading strategies!${NC}"
