#!/usr/bin/env python3
"""
Initialize database with default trading symbols (stocks, crypto, ETFs).

Usage:
    python scripts/init_symbols.py
    
This will:
1. Create the tracked_symbols table
2. Insert default 60 symbols (20 stocks + 20 crypto + 20 ETFs)
3. Skip any that already exist

Execution time: ~3-5 seconds
"""

import asyncio
import asyncpg
import sys

from src.config import config
from src.services.structured_logging import StructuredLogger

logger = StructuredLogger(__name__)

# Default symbols: Stocks, Crypto, ETFs (all supported by Polygon.io)
DEFAULT_SYMBOLS = [
    # US Stocks (20)
    ("AAPL", "stock"),        # Apple
    ("MSFT", "stock"),        # Microsoft
    ("GOOGL", "stock"),       # Alphabet
    ("AMZN", "stock"),        # Amazon
    ("META", "stock"),        # Meta Platforms
    ("NVDA", "stock"),        # NVIDIA
    ("TSLA", "stock"),        # Tesla
    ("AMD", "stock"),         # Advanced Micro Devices
    ("NFLX", "stock"),        # Netflix
    ("BRK.B", "stock"),       # Berkshire Hathaway
    ("JPM", "stock"),         # JPMorgan Chase
    ("V", "stock"),           # Visa
    ("XOM", "stock"),         # ExxonMobil
    ("PG", "stock"),          # Procter & Gamble
    ("KO", "stock"),          # Coca-Cola
    ("PEP", "stock"),         # PepsiCo
    ("COST", "stock"),        # Costco
    ("INTC", "stock"),        # Intel
    ("BA", "stock"),          # Boeing
    ("DIS", "stock"),         # Disney
    
    # Crypto (20)
    ("BTC-USD", "crypto"),    # Bitcoin
    ("ETH-USD", "crypto"),    # Ethereum
    ("BNB-USD", "crypto"),    # Binance Coin
    ("SOL-USD", "crypto"),    # Solana
    ("XRP-USD", "crypto"),    # Ripple
    ("ADA-USD", "crypto"),    # Cardano
    ("AVAX-USD", "crypto"),   # Avalanche
    ("DOT-USD", "crypto"),    # Polkadot
    ("MATIC-USD", "crypto"),  # Polygon
    ("ATOM-USD", "crypto"),   # Cosmos
    ("DOGE-USD", "crypto"),   # Dogecoin
    ("SHIB-USD", "crypto"),   # Shiba Inu
    ("LINK-USD", "crypto"),   # Chainlink
    ("AAVE-USD", "crypto"),   # Aave
    ("UNI-USD", "crypto"),    # Uniswap
    ("OP-USD", "crypto"),     # Optimism
    ("ARB-USD", "crypto"),    # Arbitrum
    ("INJ-USD", "crypto"),    # Injective
    ("LTC-USD", "crypto"),    # Litecoin
    ("NEAR-USD", "crypto"),   # NEAR Protocol
    
    # ETFs (20)
    ("SPY", "etf"),           # S&P 500 ETF
    ("QQQ", "etf"),           # Nasdaq 100 ETF
    ("DIA", "etf"),           # Dow Jones ETF
    ("IWM", "etf"),           # Russell 2000 ETF
    ("VIX", "etf"),           # Volatility Index
    ("TLT", "etf"),           # 20+ Year Treasury ETF
    ("XLK", "etf"),           # Tech Sector ETF
    ("XLF", "etf"),           # Financial Sector ETF
    ("EEM", "etf"),           # Emerging Markets ETF
    ("ARKK", "etf"),          # Innovation ETF
    ("GLD", "etf"),           # Gold ETF
    ("SLV", "etf"),           # Silver ETF
    ("XLE", "etf"),           # Energy Sector ETF
    ("XLV", "etf"),           # Healthcare Sector ETF
    ("XLI", "etf"),           # Industrials Sector ETF
    ("XLP", "etf"),           # Consumer Staples ETF
    ("XLY", "etf"),           # Consumer Discretionary ETF
    ("XLRE", "etf"),          # Real Estate ETF
    ("XLU", "etf"),           # Utilities Sector ETF
    ("SCHB", "etf"),          # Broad Market ETF
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
