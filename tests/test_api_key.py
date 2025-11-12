#!/usr/bin/env python3
"""Quick test to verify Polygon API key is valid."""
import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_key():
    api_key = os.getenv('POLYGON_API_KEY')
    
    if not api_key:
        print("❌ POLYGON_API_KEY not found in .env")
        return False
    
    print(f"✓ Found API key: {api_key[:10]}...")
    
    # Test a simple request
    from src.clients.polygon_client import PolygonClient
    client = PolygonClient(api_key)
    
    try:
        result = await client.fetch_daily_range('AAPL', '2025-11-01', '2025-11-10')
        print(f"✓ API key works! Fetched {len(result)} candles for AAPL")
        return True
    except Exception as e:
        print(f"❌ API key test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_key())
    sys.exit(0 if success else 1)
