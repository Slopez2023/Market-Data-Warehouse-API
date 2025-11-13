#!/usr/bin/env python3
"""Load 5 years of historical test data for 5 assets into the database"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.database_service import DatabaseService
from src.services.structured_logging import StructuredLogger
import asyncpg

logger = StructuredLogger(__name__)

# 5 assets to load
ASSETS_TO_LOAD = [
    ("AAPL", "stock"),
    ("MSFT", "stock"),
    ("GOOGL", "stock"),
    ("BTC", "crypto"),
    ("ETH", "crypto"),
]

# 5 years of data
YEARS = 5
START_DATE = datetime.now() - timedelta(days=365 * YEARS)
END_DATE = datetime.now()


def generate_ohlcv_data(symbol: str, date: datetime, base_price: float) -> dict:
    """Generate realistic OHLCV candle data"""
    # Random walk for prices
    daily_return = random.gauss(0.0005, 0.02)
    price = base_price * (1 + daily_return)
    
    # Open, high, low, close with realistic volatility
    open_price = price * (1 + random.gauss(0, 0.005))
    high_price = price * (1 + abs(random.gauss(0.01, 0.015)))
    low_price = price * (1 - abs(random.gauss(0.01, 0.015)))
    close_price = price
    
    # Ensure OHLC constraints
    high_price = max(open_price, high_price, close_price)
    low_price = min(open_price, low_price, close_price)
    
    # Volume based on volatility
    base_volume = 1_000_000 if "stock" in symbol else 100_000
    volume = int(base_volume * (1 + abs(random.gauss(0, 0.5))))
    
    return {
        "symbol": symbol,
        "date": date.date(),
        "open": round(open_price, 2),
        "high": round(high_price, 2),
        "low": round(low_price, 2),
        "close": round(close_price, 2),
        "volume": volume,
        "vwap": round((open_price + high_price + low_price + close_price) / 4, 2),
        "quality_score": random.uniform(0.85, 1.0),
        "is_validated": True,
        "has_gaps": False,
    }


async def load_test_data():
    """Load test data into database"""
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        sys.exit(1)
    
    print("\n" + "="*70)
    print("Loading Test Data - 5 Assets × 5 Years")
    print("="*70)
    
    # Connect to database
    try:
        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)
    
    total_records = 0
    
    # Load data for each asset
    for symbol, asset_class in ASSETS_TO_LOAD:
        print(f"\n📊 Loading {symbol} ({asset_class})...")
        
        # Ensure symbol exists
        try:
            await conn.execute(
                """
                INSERT INTO symbols (symbol, asset_class, active)
                VALUES ($1, $2, $3)
                ON CONFLICT (symbol) DO UPDATE SET active = TRUE
                """,
                symbol, asset_class, True
            )
        except Exception as e:
            print(f"   ⚠️  Could not insert symbol: {e}")
        
        # Generate and load 5 years of data
        current_date = START_DATE
        base_price = 100.0
        candle_count = 0
        
        candles = []
        
        while current_date <= END_DATE:
            # Skip weekends for stocks
            if asset_class == "stock" and current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                continue
            
            # Generate candle
            candle = generate_ohlcv_data(symbol, current_date, base_price)
            base_price = candle["close"]  # Use close as base for next day
            candles.append(candle)
            candle_count += 1
            
            current_date += timedelta(days=1)
        
        # Batch insert candles
        try:
            await conn.executemany(
                """
                INSERT INTO market_data 
                (symbol, date, open, high, low, close, volume, vwap, quality_score, is_validated, has_gaps)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (symbol, date) DO NOTHING
                """,
                [(
                    c["symbol"], c["date"], c["open"], c["high"], c["low"], c["close"],
                    c["volume"], c["vwap"], c["quality_score"], c["is_validated"], c["has_gaps"]
                ) for c in candles]
            )
            print(f"   ✅ Loaded {candle_count} candles")
            total_records += candle_count
        
        except Exception as e:
            print(f"   ❌ Failed to load candles: {e}")
    
    await conn.close()
    
    # Verify data
    print(f"\n📈 Verifying loaded data...")
    db = DatabaseService(database_url)
    
    metrics = db.get_status_metrics()
    
    print("\n" + "="*70)
    print("Load Complete!")
    print("="*70)
    print(f"\n📊 Database Summary:")
    print(f"   Total Records: {metrics.get('total_records', 0):,}")
    print(f"   Validated Records: {metrics.get('validated_records', 0):,}")
    print(f"   Symbols Available: {metrics.get('symbols_available', 0)}")
    print(f"   Latest Data: {metrics.get('latest_data')}")
    print(f"   Validation Rate: {metrics.get('validation_rate_pct', 0):.1f}%")
    
    print(f"\n✅ Loaded {total_records:,} candles across {len(ASSETS_TO_LOAD)} assets")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(load_test_data())
    except KeyboardInterrupt:
        print("\n❌ Data load interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Data load failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
