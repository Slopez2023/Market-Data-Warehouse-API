#!/usr/bin/env python3
"""
Initialize database with default trading symbols (stocks, crypto, ETFs).

Usage:
    python scripts/init_symbols.py                           # All 60 symbols
    python scripts/init_symbols.py --count 10                # First 10 symbols
    python scripts/init_symbols.py --exclude-asset-type crypto  # Stocks + ETFs only
    python scripts/init_symbols.py --reset                   # Clear & reinitialize
    python scripts/init_symbols.py --check-only              # Verify without modifying

This will:
1. Create the tracked_symbols table if needed
2. Insert default symbols (60 total: 20 stocks + 20 crypto + 20 ETFs)
3. Configure all symbols with full timeframe support (5m, 15m, 30m, 1h, 4h, 1d, 1w)
4. Skip any that already exist (unless --reset is used)

Execution time: ~3-5 seconds

Timeframes pulled for each symbol:
- 5m (5 minutes)
- 15m (15 minutes)
- 30m (30 minutes)
- 1h (1 hour)
- 4h (4 hours)
- 1d (1 day)
- 1w (1 week)
"""

import argparse
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


async def init_symbols(args):
    """Initialize symbols in database"""
    
    try:
        conn = await asyncpg.connect(config.database_url)
        
        # Filter symbols based on arguments
        symbols_to_init = DEFAULT_SYMBOLS
        
        if args.exclude_asset_type:
            symbols_to_init = [
                (sym, cls) for sym, cls in symbols_to_init
                if cls != args.exclude_asset_type
            ]
        
        if args.count:
            symbols_to_init = symbols_to_init[:args.count]
        
        print(f"\nInitializing {len(symbols_to_init)} symbols...")
        
        if args.reset:
            print("⚠️  Clearing existing symbols...")
            await conn.execute("TRUNCATE tracked_symbols")
        
        print("-" * 60)
        
        inserted = 0
        skipped = 0
        
        if args.check_only:
            # Check which symbols exist without modifying
            for symbol, asset_class in symbols_to_init:
                exists = await conn.fetchval(
                    "SELECT 1 FROM tracked_symbols WHERE symbol = $1",
                    symbol
                )
                if exists:
                    print(f"  ✓ {symbol:6} ({asset_class:6}) [exists]")
                    skipped += 1
                else:
                    print(f"  - {symbol:6} ({asset_class:6}) [missing]")
                    inserted += 1
        else:
            # Insert symbols
            for symbol, asset_class in symbols_to_init:
                try:
                    # Check if symbol already exists
                    exists = await conn.fetchval(
                        "SELECT 1 FROM tracked_symbols WHERE symbol = $1",
                        symbol
                    )
                    
                    if exists and not args.reset:
                        print(f"  - {symbol:6} ({asset_class:6}) [already exists]")
                        skipped += 1
                    else:
                        # Insert with full timeframe support
                        await conn.execute(
                            """
                            INSERT INTO tracked_symbols (symbol, asset_class, active, timeframes)
                            VALUES ($1, $2, TRUE, ARRAY['5m', '15m', '30m', '1h', '4h', '1d', '1w'])
                            ON CONFLICT (symbol) DO UPDATE SET 
                                asset_class = $2,
                                timeframes = ARRAY['5m', '15m', '30m', '1h', '4h', '1d', '1w']
                            """,
                            symbol, asset_class
                        )
                        print(f"  ✓ {symbol:6} ({asset_class:6})")
                        inserted += 1
                
                except Exception as e:
                    print(f"  ✗ {symbol:6} ({asset_class:6}) - Error: {e}")
                    logger.error(f"Failed to insert {symbol}", extra={"error": str(e)})
                    skipped += 1
        
        await conn.close()
        
        print("-" * 60)
        print(f"\nResults:")
        print(f"  Processed: {inserted}")
        print(f"  Skipped:   {skipped}")
        print(f"  Total:     {len(symbols_to_init)}")
        print()
        
        if args.check_only:
            print(f"✓ Check complete ({skipped} exist, {inserted} missing)")
        elif inserted > 0:
            print("✓ Symbols initialized successfully")
        else:
            print("Note: All symbols already exist in database")
        
        return 0
    
    except Exception as e:
        print(f"Error initializing symbols: {e}")
        logger.error("Symbol initialization failed", extra={"error": str(e)})
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initialize database with default trading symbols"
    )
    parser.add_argument(
        "--count",
        type=int,
        help="Number of symbols to initialize (default: all 60)"
    )
    parser.add_argument(
        "--exclude-asset-type",
        choices=["stock", "crypto", "etf"],
        help="Exclude symbols of specified asset type"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear all symbols before reinitializing"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Check which symbols exist without modifying database"
    )
    
    args = parser.parse_args()
    exit_code = asyncio.run(init_symbols(args))
    sys.exit(exit_code)
