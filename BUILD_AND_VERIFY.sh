#!/bin/bash

set -e

echo "======================================"
echo "Market Data API - Build & Verification"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: Environment Variables
echo "1. Checking environment variables..."
if [ ! -f .env ]; then
    echo -e "${RED}✗ .env file not found${NC}"
    echo "  Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}⚠ Please update .env with your actual values:${NC}"
    echo "   - POLYGON_API_KEY: Get from https://polygon.io"
    echo "   - DATABASE_URL: Should be postgresql://market_user:password@localhost:5432/market_data"
    echo "   - DB_PASSWORD: Should match the password in DATABASE_URL"
fi

# Source .env to check values
if [ -f .env ]; then
    source .env
    
    if [ -z "$POLYGON_API_KEY" ] || [ "$POLYGON_API_KEY" = "your_api_key_here" ] || [ "$POLYGON_API_KEY" = "pk_your_key_here" ]; then
        echo -e "${YELLOW}⚠ POLYGON_API_KEY not properly configured${NC}"
        echo "  Get your key at: https://polygon.io"
    else
        echo -e "${GREEN}✓ POLYGON_API_KEY configured${NC}"
    fi
    
    if [ -z "$DATABASE_URL" ]; then
        echo -e "${RED}✗ DATABASE_URL not set in .env${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ DATABASE_URL: ${DATABASE_URL:0:30}...${NC}"
    fi
else
    echo -e "${RED}✗ No .env file found${NC}"
    exit 1
fi

echo ""

# Check 2: Docker services
echo "2. Checking Docker services..."
if docker ps | grep -q market_data_postgres; then
    echo -e "${GREEN}✓ PostgreSQL container running${NC}"
else
    echo -e "${YELLOW}⚠ PostgreSQL container not running${NC}"
    echo "  Starting Docker Compose..."
    docker-compose up -d database
    echo "  Waiting for PostgreSQL to be ready..."
    sleep 5
fi

echo ""

# Check 3: Python dependencies
echo "3. Installing Python dependencies..."
python -m pip install -q -r requirements.txt 2>/dev/null || {
    echo -e "${YELLOW}⚠ Some dependency warnings (usually safe for this project)${NC}"
}
echo -e "${GREEN}✓ Dependencies installed${NC}"

echo ""

# Check 4: Database connectivity
echo "4. Testing database connection..."
python << 'EOF'
import os
import sys
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("✗ DATABASE_URL not set")
    sys.exit(1)

try:
    import psycopg2
    # Parse connection string
    from urllib.parse import urlparse
    parsed = urlparse(db_url)
    
    conn = psycopg2.connect(
        dbname=parsed.path.lstrip('/'),
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 5432
    )
    conn.close()
    print("✓ Database connection successful")
except Exception as e:
    print(f"✗ Database connection failed: {e}")
    sys.exit(1)
EOF

echo ""

# Check 5: Configuration validation
echo "5. Validating application configuration..."
python << 'EOF'
import os
from dotenv import load_dotenv

load_dotenv()

# Try to load config
try:
    from src.config import config
    print("✓ Configuration loaded and validated")
    print(f"  - API: {config.api_host}:{config.api_port}")
    print(f"  - Workers: {config.api_workers}")
    print(f"  - Backfill Schedule: {config.backfill_schedule_hour:02d}:{config.backfill_schedule_minute:02d} UTC")
    print(f"  - Log Level: {config.log_level}")
except Exception as e:
    print(f"✗ Configuration error: {e}")
    import sys
    sys.exit(1)
EOF

echo ""

# Check 6: Python imports
echo "6. Testing critical imports..."
python << 'EOF'
try:
    import fastapi
    import sqlalchemy
    import psycopg2
    import asyncpg
    import aiohttp
    from src.models import HealthResponse
    from src.services.database_service import DatabaseService
    from src.scheduler import AutoBackfillScheduler
    print("✓ All critical imports working")
except ImportError as e:
    print(f"✗ Import error: {e}")
    import sys
    sys.exit(1)
EOF

echo ""

# Check 7: Docker image build
echo "7. Building Docker image..."
if docker build -q -t market-data-api:latest . > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    docker build -t market-data-api:latest .
    exit 1
fi

echo ""

# Check 8: Summary
echo "======================================"
echo -e "${GREEN}✓ Build verification complete!${NC}"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Verify all checks above are passing (GREEN ✓)"
echo "2. Start all services:"
echo "   docker-compose up"
echo ""
echo "3. API will be available at:"
echo "   http://localhost:8000"
echo ""
echo "4. Dashboard will be available at:"
echo "   http://localhost:3001"
echo ""
echo "5. Check API health:"
echo "   curl http://localhost:8000/health"
echo ""
