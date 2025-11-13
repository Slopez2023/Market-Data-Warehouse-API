#!/usr/bin/env python3
"""
Historical data backfill script
Pulls 5+ years of OHLCV data for specified symbols
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.clients.polygon_client import PolygonClient
from src.services.database_service import DatabaseService


async def backfill_symbol(
    db: DatabaseService,
    polygon_client: PolygonClient,
    symbol: str,
    years_back: int = 5
):
    """Backfill historical data for a symbol"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365 * years_back)
    
    print(f"\nBackfilling {symbol}: {start_date} to {end_date}")
    
    try:
        candles = await polygon_client.fetch_daily_range(
            symbol=symbol,
            start_date=str(start_date),
            end_date=str(end_date)
        )
        
        if not candles:
            print(f"  ✗ No data returned for {symbol}")
            return 0
        
        print(f"  → Fetched {len(candles)} candles")
        
        # Insert into database
        inserted = db.insert_market_data(symbol, candles)
        print(f"  ✓ Inserted {inserted} records")
        return inserted
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return 0


async def main():
    """Main backfill function"""
    api_key = os.getenv("POLYGON_API_KEY")
    db_url = os.getenv("DATABASE_URL")
    
    if not api_key:
        print("Error: POLYGON_API_KEY not set")
        return 1
    
    if not db_url:
        print("Error: DATABASE_URL not set")
        return 1
    
    # Initialize services
    db = DatabaseService(db_url)
    polygon_client = PolygonClient(api_key)
    
    # Symbols to backfill
    symbols = [
        ("AAPL", "stock"),
        ("MSFT", "stock"),
        ("TSLA", "stock"),
        ("GOOGL", "stock"),
        ("AMZN", "stock"),
    ]
    
    print("=" * 60)
    print("Historical Data Backfill")
    print("=" * 60)
    
    total_records = 0
    for symbol, asset_class in symbols:
        # Add symbol to tracking
        try:
            db.add_tracked_symbol(symbol, asset_class)
            print(f"Added {symbol} to tracking")
        except Exception as e:
            print(f"Symbol {symbol} may already exist: {e}")
        
        # Backfill data
        records = await backfill_symbol(db, polygon_client, symbol, years_back=5)
        total_records += records
    
    print("\n" + "=" * 60)
    print(f"Total records inserted: {total_records}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
