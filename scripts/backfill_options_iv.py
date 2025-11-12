#!/usr/bin/env python3
"""
Backfill options IV data for tracked symbols.
Source: Polygon.io options endpoints

Usage:
    python scripts/backfill_options_iv.py                    # Backfill all symbols (last 30 days)
    python scripts/backfill_options_iv.py --symbol AAPL      # Single symbol
    python scripts/backfill_options_iv.py --days 90          # Custom lookback period
    python scripts/backfill_options_iv.py --expiration 2025-01-17  # Specific expiration

Note: Options data is large. Start with recent data (30 days) and expand gradually.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import aiohttp
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clients.polygon_client import PolygonClient
from src.services.options_iv_service import OptionsIVService
from src.database import Database

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class OptionsIVBackfiller:
    def __init__(self, db: Database, polygon_client: PolygonClient):
        self.db = db
        self.polygon_client = polygon_client
        self.options_service = OptionsIVService(db)

    async def fetch_options_contracts(
        self, symbol: str, expiration_date: str
    ) -> List[Dict]:
        """
        Fetch options chain for a symbol and expiration.

        Endpoint: GET /v3/snapshot/options/{optionSymbol}
        """
        url = f"https://api.polygon.io/v3/snapshot/options/chains/{symbol}"
        params = {
            "expiration_date": expiration_date,
            "limit": 1000,
            "order": "asc",
            "apiKey": os.getenv("POLYGON_API_KEY"),
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])
                        logger.debug(
                            f"  Fetched {len(results)} contracts for {symbol} {expiration_date}"
                        )
                        return results
                    elif response.status == 429:
                        logger.warning(f"  Rate limited, waiting 2s...")
                        await asyncio.sleep(2)
                        return await self.fetch_options_contracts(
                            symbol, expiration_date
                        )
                    else:
                        logger.warning(f"  API error {response.status}")
                        return []
        except asyncio.TimeoutError:
            logger.error(f"  Timeout fetching options for {symbol}")
            return []
        except Exception as e:
            logger.error(f"  Error fetching options: {e}")
            return []

    def parse_options_record(
        self,
        symbol: str,
        contract: Dict,
        quote_date: str,
        timestamp: int,
    ) -> Optional[Dict]:
        """
        Parse Polygon options contract into our format.
        """
        try:
            option_symbol = contract.get("option_symbol")
            details = contract.get("details", {})
            last_quote = contract.get("last_quote", {})
            last_trade = contract.get("last_trade", {})

            if not option_symbol:
                return None

            # Parse option symbol: e.g., "AAPL  251219C00150000"
            # Format: ticker + expiration (YYMMDD) + type (C/P) + strike
            expiration_str = option_symbol[6:12]  # YYMMDD
            option_type = option_symbol[12]  # C or P
            strike_str = option_symbol[13:]  # Strike with decimals

            try:
                # Convert YYMMDD to date
                yy = int(expiration_str[0:2])
                mm = int(expiration_str[2:4])
                dd = int(expiration_str[4:6])
                century = 2000 if yy < 50 else 1900
                expiration_date = datetime(century + yy, mm, dd).date()

                # Parse strike (divide by 1000)
                strike = float(strike_str) / 1000
            except:
                logger.warning(f"  Could not parse option symbol: {option_symbol}")
                return None

            # Extract Greeks and IV
            last_quote_copy = dict(last_quote) if isinstance(last_quote, dict) else {}
            last_trade_copy = dict(last_trade) if isinstance(last_trade, dict) else {}

            option_dict = {
                "symbol": symbol,
                "option_symbol": option_symbol,
                "timestamp": timestamp,
                "quote_date": quote_date,
                "expiration_date": expiration_date.isoformat(),
                "strike_price": strike,
                "option_type": "call" if option_type == "C" else "put",
                # IV and Greeks
                "implied_volatility": details.get("contract_details", {}).get("implied_volatility"),
                "delta": last_quote_copy.get("delta"),
                "gamma": last_quote_copy.get("gamma"),
                "vega": last_quote_copy.get("vega"),
                "theta": last_quote_copy.get("theta"),
                "rho": last_quote_copy.get("rho"),
                # Market data
                "bid_price": last_quote_copy.get("bid"),
                "ask_price": last_quote_copy.get("ask"),
                "bid_size": last_quote_copy.get("bid_size"),
                "ask_size": last_quote_copy.get("ask_size"),
                "last_price": last_trade_copy.get("price"),
                "volume": contract.get("day", {}).get("volume"),
                "open_interest": contract.get("open_interest"),
                # IV rankings (would need historical context)
                "iv_rank": None,
                "iv_percentile": None,
            }

            return option_dict

        except Exception as e:
            logger.debug(f"  Error parsing options record: {e}")
            return None

    async def get_expirations_for_symbol(
        self, symbol: str, days_ahead: int = 60
    ) -> List[str]:
        """
        Get list of valid option expirations for a symbol.
        For now, returns common expiration dates (weekly + monthly).
        """
        today = datetime.utcnow().date()
        expirations = []

        # Add fridays for next N weeks
        for i in range(1, days_ahead // 7 + 1):
            # Find next Friday
            date = today + timedelta(days=i)
            while date.weekday() != 4:  # Friday is 4
                date += timedelta(days=1)
            if date not in expirations:
                expirations.append(date.isoformat())

        return expirations

    async def insert_options_chain(
        self, symbol: str, options_list: List[Dict]
    ) -> int:
        """Insert options chain records into database."""
        if not options_list:
            return 0

        filtered_options = [o for o in options_list if o is not None]

        if filtered_options:
            inserted, _ = (
                await self.options_service.insert_options_chain_batch(
                    filtered_options
                )
            )
            return inserted

        return 0

    async def backfill_symbol_recent(
        self, symbol: str, days: int = 30
    ) -> bool:
        """Backfill recent options data for a symbol."""
        try:
            logger.info(f"Backfilling options IV for {symbol} (last {days} days)")

            # Get expirations within lookback period
            expirations = await self.get_expirations_for_symbol(
                symbol, days_ahead=days + 30
            )

            total_inserted = 0
            quote_date = (datetime.utcnow().date()).isoformat()
            timestamp = int(datetime.utcnow().timestamp() * 1000)

            for expiration in expirations:
                # Skip past expirations
                if datetime.fromisoformat(expiration).date() < datetime.utcnow().date():
                    continue

                # Fetch chain
                contracts = await self.fetch_options_contracts(
                    symbol, expiration
                )

                if contracts:
                    # Parse records
                    options_list = [
                        self.parse_options_record(
                            symbol, c, quote_date, timestamp
                        )
                        for c in contracts
                    ]

                    # Insert
                    inserted = await self.insert_options_chain(
                        symbol, options_list
                    )
                    total_inserted += inserted
                    logger.info(
                        f"  Inserted {inserted} contracts for {expiration}"
                    )

                await asyncio.sleep(0.5)  # Rate limiting

            logger.info(
                f"  ✓ {symbol}: Total inserted {total_inserted} contracts"
            )
            return True

        except Exception as e:
            logger.error(f"Error backfilling {symbol}: {e}")
            return False


async def get_active_symbols(db: Database) -> List[str]:
    """Get list of active symbols with options available."""
    query = """
    SELECT DISTINCT symbol 
    FROM tracked_symbols 
    WHERE active = TRUE 
    AND asset_class = 'stock'
    AND symbol IN (
        SELECT DISTINCT symbol FROM market_data 
        WHERE timeframe = '1d'
    )
    ORDER BY symbol
    LIMIT 50  -- Start with top 50 by volume
    """

    try:
        records = await db.fetch(query)
        return [r["symbol"] for r in records]
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
        return []


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill options IV data from Polygon.io"
    )
    parser.add_argument(
        "--symbol", type=str, help="Backfill single symbol (e.g., AAPL)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days to backfill (default: 30). Note: Options data is large!",
    )
    parser.add_argument(
        "--expiration",
        type=str,
        help="Specific expiration date (YYYY-MM-DD)",
    )

    args = parser.parse_args()

    # Setup database
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set in environment")
        return

    db = Database(db_url)
    polygon_client = PolygonClient(os.getenv("POLYGON_API_KEY"))
    backfiller = OptionsIVBackfiller(db, polygon_client)

    logger.info(f"Starting options IV backfill")
    logger.info(f"Lookback period: {args.days} days")
    logger.info("-" * 60)

    # Get symbols
    if args.symbol:
        symbols = [args.symbol]
    else:
        symbols = await get_active_symbols(db)

    if not symbols:
        logger.error("No symbols to backfill")
        return

    logger.info(f"Backfilling {len(symbols)} symbols")

    successful = 0
    failed = 0

    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] Processing {symbol}")

        success = await backfiller.backfill_symbol_recent(
            symbol, days=args.days
        )

        if success:
            successful += 1
        else:
            failed += 1

        # Rate limiting
        await asyncio.sleep(2)

    logger.info("-" * 60)
    logger.info(f"Options IV backfill complete!")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(
        "Note: Options data grows quickly. Consider archiving old data quarterly."
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Backfill interrupted by user")
        sys.exit(0)
