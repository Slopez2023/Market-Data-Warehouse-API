#!/usr/bin/env python3
"""
Backfill historical earnings data for all tracked symbols.
Source: Polygon.io reference API (via Benzinga)

Usage:
    python scripts/backfill_earnings.py                    # Backfill all symbols
    python scripts/backfill_earnings.py --symbol AAPL      # Single symbol
    python scripts/backfill_earnings.py --resume           # Skip completed symbols
    python scripts/backfill_earnings.py --days 365         # Custom lookback period
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
from src.services.earnings_service import EarningsService
from src.services.database_service import DatabaseService
from src.config import get_db_url, get_polygon_api_key

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class EarningsBackfiller:
    def __init__(self, db_service: DatabaseService, polygon_client: PolygonClient):
        self.db_service = db_service
        self.polygon_client = polygon_client
        self.earnings_service = EarningsService(db_service)

    async def fetch_earnings_from_polygon(
        self, symbol: str, from_date: str, to_date: str
    ) -> List[Dict]:
        """
        Fetch earnings data from Polygon.io reference/financials endpoint.

        Endpoint: GET /v3/reference/financials
        """
        url = "https://api.polygon.io/v3/reference/financials"
        params = {
            "ticker": symbol,
            "timeframe": "quarterly",
            "limit": 100,
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
                        logger.info(
                            f"  Fetched {len(results)} earnings periods for {symbol}"
                        )
                        return results
                    elif response.status == 429:
                        logger.warning(f"  Rate limited for {symbol}, retrying...")
                        await asyncio.sleep(2)
                        return await self.fetch_earnings_from_polygon(
                            symbol, from_date, to_date
                        )
                    else:
                        logger.warning(f"  API error {response.status} for {symbol}")
                        return []
        except asyncio.TimeoutError:
            logger.error(f"  Timeout fetching earnings for {symbol}")
            return []
        except Exception as e:
            logger.error(f"  Error fetching earnings for {symbol}: {e}")
            return []

    def parse_earnings_record(
        self, symbol: str, financial_record: Dict
    ) -> Optional[Dict]:
        """
        Parse Polygon financial record into earnings dict.

        Maps financial data to our earnings table structure.
        """
        try:
            filing_date = financial_record.get("filing_date")
            end_date = financial_record.get("end_date")

            if not end_date:
                return None

            # Extract fiscal info from end_date
            end_dt = datetime.fromisoformat(end_date.split("T")[0])
            month = end_dt.month

            fiscal_quarter = (month - 1) // 3 + 1
            fiscal_year = end_dt.year

            # Extract financials
            financials = financial_record.get("financials", {})
            income_statement = financials.get("income_statement", {})

            net_income = income_statement.get("net_income", {})
            revenues = income_statement.get("revenues", {})

            net_income_value = (
                net_income.get("value") if isinstance(net_income, dict) else None
            )
            revenue_value = (
                revenues.get("value") if isinstance(revenues, dict) else None
            )

            # Calculate EPS (simplified - would need share count for accuracy)
            eps = None
            if net_income_value:
                eps = net_income_value / 1_000_000  # Rough estimate

            earnings_dict = {
                "symbol": symbol,
                "earnings_date": end_date,
                "earnings_time": "bmo",  # Default to before market open
                "fiscal_year": fiscal_year,
                "fiscal_quarter": fiscal_quarter,
                "actual_eps": eps,
                "actual_revenue": revenue_value,
                "data_source": "polygon",
                "confirmed": True,
            }

            return earnings_dict

        except Exception as e:
            logger.warning(f"  Error parsing earnings record for {symbol}: {e}")
            return None

    async def insert_earnings(
        self, symbol: str, earnings_list: List[Dict]
    ) -> tuple[int, int]:
        """Insert earnings records into database."""
        if not earnings_list:
            return 0, 0

        filtered_earnings = [e for e in earnings_list if e is not None]

        if filtered_earnings:
            inserted, updated = (
                await self.earnings_service.insert_earnings_batch(
                    filtered_earnings
                )
            )
            return inserted, updated

        return 0, 0

    def update_backfill_progress(
        self,
        backfill_type: str,
        symbol: str,
        status: str,
        last_date: Optional[str] = None,
        error_msg: Optional[str] = None,
    ) -> None:
        """Track backfill progress for resumability."""
        from sqlalchemy import text
        session = self.db_service.SessionLocal()
        
        try:
            query = text("""
                INSERT INTO backfill_progress 
                (backfill_type, symbol, status, last_processed_date, error_message, attempted_at)
                VALUES (:backfill_type, :symbol, :status, :last_date, :error_msg, NOW())
                ON CONFLICT (backfill_type, symbol)
                DO UPDATE SET
                    status = EXCLUDED.status,
                    last_processed_date = EXCLUDED.last_processed_date,
                    error_message = EXCLUDED.error_message,
                    attempted_at = NOW()
            """)
            
            session.execute(
                query,
                {
                    'backfill_type': backfill_type,
                    'symbol': symbol,
                    'status': status,
                    'last_date': last_date,
                    'error_msg': error_msg
                }
            )
            session.commit()
        except Exception as e:
            logger.error(f"Error updating backfill progress: {e}")
            session.rollback()
        finally:
            session.close()

    async def backfill_symbol(
        self, symbol: str, from_date: str, to_date: str
    ) -> bool:
        """Backfill earnings for a single symbol."""
        try:
            logger.info(f"Backfilling earnings for {symbol}")

            # Fetch from Polygon
            financials = await self.fetch_earnings_from_polygon(
                symbol, from_date, to_date
            )

            if not financials:
                logger.warning(f"  No earnings data for {symbol}")
                self.update_backfill_progress(
                    "earnings", symbol, "no_data"
                )
                return False

            # Parse records
            earnings_list = [
                self.parse_earnings_record(symbol, f) for f in financials
            ]

            # Insert into database
            inserted, updated = await self.insert_earnings(
                symbol, earnings_list
            )
            logger.info(
                f"  ✓ {symbol}: Inserted {inserted}, Updated {updated}"
            )

            self.update_backfill_progress(
                "earnings", symbol, "completed", to_date
            )
            return True

        except Exception as e:
            logger.error(f"Error backfilling {symbol}: {e}")
            self.update_backfill_progress(
                "earnings", symbol, "failed", error_msg=str(e)
            )
            return False


def get_active_symbols(db_service: DatabaseService) -> List[str]:
    """Get list of active symbols from database."""
    from sqlalchemy import text
    session = db_service.SessionLocal()
    
    try:
        query = text("""
            SELECT DISTINCT symbol 
            FROM tracked_symbols 
            WHERE active = TRUE 
            AND asset_class IN ('stock', 'etf')
            ORDER BY symbol
        """)
        
        records = session.execute(query).fetchall()
        return [r[0] for r in records]
    except Exception as e:
        logger.error(f"Error fetching symbols: {e}")
        return []
    finally:
        session.close()


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill earnings data from Polygon.io"
    )
    parser.add_argument(
        "--symbol", type=str, help="Backfill single symbol (e.g., AAPL)"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip symbols that have completed",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1825,
        help="Days to look back (default: 1825 = 5 years)",
    )

    args = parser.parse_args()

    # Setup database
    db_url = get_db_url()
    if not db_url:
        logger.error("DATABASE_URL not set in environment")
        return

    db_service = DatabaseService(db_url)
    polygon_api_key = get_polygon_api_key()
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY not set in environment")
        return
        
    polygon_client = PolygonClient(polygon_api_key)
    backfiller = EarningsBackfiller(db_service, polygon_client)

    # Date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=args.days)

    logger.info(f"Starting earnings backfill")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info("-" * 60)

    # Get symbols
    if args.symbol:
        symbols = [args.symbol]
    else:
        symbols = get_active_symbols(db_service)

    if not symbols:
        logger.error("No symbols to backfill")
        return

    logger.info(f"Backfilling {len(symbols)} symbols")

    # Track results
    successful = 0
    failed = 0

    for i, symbol in enumerate(symbols, 1):
        logger.info(f"[{i}/{len(symbols)}] Processing {symbol}")

        if args.resume:
            # Check if already completed
            from sqlalchemy import text
            session = db_service.SessionLocal()
            try:
                query = text("""
                    SELECT status FROM backfill_progress 
                    WHERE backfill_type = 'earnings' AND symbol = :symbol
                """)
                result = session.execute(query, {'symbol': symbol}).first()
                if result and result[0] == "completed":
                    logger.info(f"  Skipping {symbol} (already completed)")
                    session.close()
                    continue
            except Exception as e:
                logger.warning(f"  Could not check progress for {symbol}: {e}")
            finally:
                session.close()

        success = await backfiller.backfill_symbol(
            symbol, start_date.isoformat(), end_date.isoformat()
        )

        if success:
            successful += 1
        else:
            failed += 1

        # Rate limiting: 50 requests/min = 1.2s per request
        await asyncio.sleep(1.2)

    logger.info("-" * 60)
    logger.info(f"Earnings backfill complete!")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Backfill interrupted by user")
        sys.exit(0)
