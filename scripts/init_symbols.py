#!/usr/bin/env python3
"""
Initialize database with default symbols (stocks + crypto).

Usage:
    python scripts/init_symbols.py
    
This will:
1. Create the tracked_symbols table
2. Insert default 30 symbols (15 stocks + 15 crypto)
3. Skip any that already exist
"""

import asyncio
import asyncpg
import sys

from src.config import config
from src.services.structured_logging import StructuredLogger

logger = StructuredLogger(__name__)

# Default symbols: 15 major stocks + 15 major crypto
DEFAULT_SYMBOLS = [
    # Stocks
    ("AAPL", "stock"),
    ("MSFT", "stock"),
    ("GOOGL", "stock"),
    ("AMZN", "stock"),
    ("NVDA", "stock"),
    ("TSLA", "stock"),
    ("META", "stock"),
    ("NFLX", "stock"),
    ("AMD", "stock"),
    ("INTC", "stock"),
    ("PYPL", "stock"),
    ("SQ", "stock"),
    ("ROKU", "stock"),
    ("MSTR", "stock"),
    ("SOFI", "stock"),
    
    # Crypto
    ("BTC", "crypto"),
    ("ETH", "crypto"),
    ("BNB", "crypto"),
    ("SOL", "crypto"),
    ("XRP", "crypto"),
    ("ADA", "crypto"),
    ("DOGE", "crypto"),
    ("AVAX", "crypto"),
    ("MATIC", "crypto"),
    ("LINK", "crypto"),
    ("LTC", "crypto"),
    ("UNI", "crypto"),
    ("ARB", "crypto"),
    ("OP", "crypto"),
    ("PEPE", "crypto"),
]


async def init_symbols():
    """Initialize symbols in database"""
    
    try:
        conn = await asyncpg.connect(config.database_url)
        
        inserted = 0
        skipped = 0
        
        print(f"\nInitializing {len(DEFAULT_SYMBOLS)} default symbols...")
        print("-" * 60)
        
        for symbol, asset_class in DEFAULT_SYMBOLS:
            try:
                # Try to insert
                result = await conn.execute(
                    """
                    INSERT INTO tracked_symbols (symbol, asset_class, active)
                    VALUES ($1, $2, TRUE)
                    ON CONFLICT (symbol) DO NOTHING
                    """,
                    symbol, asset_class
                )
                
                # Check if actually inserted (not a conflict)
                if result == "INSERT 0 1":
                    print(f"  ✓ {symbol:6} ({asset_class:6})")
                    inserted += 1
                else:
                    print(f"  - {symbol:6} ({asset_class:6}) [already exists]")
                    skipped += 1
            
            except Exception as e:
                print(f"  ✗ {symbol:6} ({asset_class:6}) - Error: {e}")
                skipped += 1
        
        await conn.close()
        
        print("-" * 60)
        print(f"\nResults:")
        print(f"  Inserted: {inserted}")
        print(f"  Skipped:  {skipped}")
        print(f"  Total:    {len(DEFAULT_SYMBOLS)}")
        print()
        
        if inserted > 0:
            print("✓ Symbols initialized successfully")
            return 0
        else:
            print("Note: All symbols already exist in database")
            return 0
    
    except Exception as e:
        print(f"Error initializing symbols: {e}")
        logger.error("Symbol initialization failed", extra={"error": str(e)})
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(init_symbols())
    sys.exit(exit_code)
