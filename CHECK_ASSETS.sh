#!/bin/bash

echo "=================================="
echo "ASSET VERIFICATION COMMANDS"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}1. Check Database Tables${NC}"
echo "   docker exec market_data_postgres psql -U market_user -d market_data -c \"\\dt\""
docker exec market_data_postgres psql -U market_user -d market_data -c "\dt"
echo ""

echo -e "${BLUE}2. Check Row Counts in Each Table${NC}"
echo "   docker exec market_data_postgres psql -U market_user -d market_data -c \"SELECT tablename, schemaname FROM pg_tables WHERE schemaname='public';\""
docker exec market_data_postgres psql -U market_user -d market_data -c "
  SELECT 
    'market_data' as table_name, 
    COUNT(*) as row_count 
  FROM market_data
  UNION ALL
  SELECT 'tracked_symbols', COUNT(*) FROM tracked_symbols
  UNION ALL
  SELECT 'api_keys', COUNT(*) FROM api_keys
  UNION ALL
  SELECT 'api_key_audit', COUNT(*) FROM api_key_audit
  UNION ALL
  SELECT 'backfill_history', COUNT(*) FROM backfill_history
  UNION ALL
  SELECT 'validation_log', COUNT(*) FROM validation_log
  UNION ALL
  SELECT 'symbol_status', COUNT(*) FROM symbol_status
  ORDER BY table_name;
"
echo ""

echo -e "${BLUE}3. Check Tracked Symbols${NC}"
echo "   docker exec market_data_postgres psql -U market_user -d market_data -c \"SELECT * FROM tracked_symbols;\""
docker exec market_data_postgres psql -U market_user -d market_data -c "
  SELECT 
    symbol, 
    asset_class, 
    active, 
    last_backfill, 
    backfill_status 
  FROM tracked_symbols 
  ORDER BY symbol;
"
echo ""

echo -e "${BLUE}4. Check API Keys${NC}"
echo "   docker exec market_data_postgres psql -U market_user -d market_data -c \"SELECT id, name, active, created_at FROM api_keys;\""
docker exec market_data_postgres psql -U market_user -d market_data -c "
  SELECT 
    id, 
    name, 
    active, 
    created_at,
    request_count
  FROM api_keys 
  ORDER BY id;
"
echo ""

echo -e "${BLUE}5. Check Market Data Records (Latest 5 per symbol)${NC}"
echo "   docker exec market_data_postgres psql -U market_user -d market_data -c \"SELECT symbol, time, close, volume, validated FROM market_data ORDER BY time DESC LIMIT 20;\""
docker exec market_data_postgres psql -U market_user -d market_data -c "
  SELECT 
    symbol,
    time,
    open,
    high,
    low,
    close,
    volume,
    validated,
    quality_score
  FROM market_data 
  ORDER BY time DESC 
  LIMIT 10;
"
echo ""

echo -e "${BLUE}6. Check Backfill History${NC}"
echo "   docker exec market_data_postgres psql -U market_user -d market_data -c \"SELECT * FROM backfill_history ORDER BY backfill_timestamp DESC LIMIT 10;\""
docker exec market_data_postgres psql -U market_user -d market_data -c "
  SELECT 
    symbol,
    backfill_timestamp,
    records_imported,
    success,
    error_details
  FROM backfill_history 
  ORDER BY backfill_timestamp DESC 
  LIMIT 10;
"
echo ""

echo -e "${BLUE}7. Check API Status${NC}"
curl -s http://localhost:8000/api/v1/status | python -m json.tool 2>/dev/null || echo "API not responding"
echo ""

echo -e "${BLUE}8. Check Configuration${NC}"
python << 'EOF' 2>/dev/null
from dotenv import load_dotenv
import os
load_dotenv()

print("Environment Variables:")
print(f"  API_HOST: {os.getenv('API_HOST', 'not set')}")
print(f"  API_PORT: {os.getenv('API_PORT', 'not set')}")
print(f"  API_WORKERS: {os.getenv('API_WORKERS', 'not set')}")
print(f"  LOG_LEVEL: {os.getenv('LOG_LEVEL', 'not set')}")
print(f"  BACKFILL_SCHEDULE_HOUR: {os.getenv('BACKFILL_SCHEDULE_HOUR', 'not set')}")
print(f"  BACKFILL_SCHEDULE_MINUTE: {os.getenv('BACKFILL_SCHEDULE_MINUTE', 'not set')}")
print(f"  POLYGON_API_KEY: {os.getenv('POLYGON_API_KEY')[:4]}...{os.getenv('POLYGON_API_KEY')[-4:] if os.getenv('POLYGON_API_KEY') else 'not set'}")
print(f"  DATABASE_URL: postgresql://market_user:***@{os.getenv('DATABASE_URL', 'not set').split('@')[1] if '@' in os.getenv('DATABASE_URL', '') else 'not set'}")
EOF
echo ""

echo -e "${BLUE}9. Docker Services Status${NC}"
docker-compose ps
echo ""

echo -e "${BLUE}10. API Endpoints Test${NC}"
echo "  Health: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/health)"
echo "  Status: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/status)"
echo "  Symbols: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/symbols)"
echo "  Metrics: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/api/v1/metrics)"
echo "  Docs: $(curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/docs)"
echo ""

echo "=================================="
echo "ASSET CHECK COMPLETE"
echo "=================================="
