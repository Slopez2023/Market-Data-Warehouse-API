#!/usr/bin/env python3
"""
Feature Enrichment Backfill

Computes and stores technical features for OHLCV data:
- Returns (1h, 1d)
- Volatility (20-period, 50-period)
- ATR (Average True Range)
- Trend direction
- Market structure
- Rolling volume metrics

Stores computed features in market_data_v2 table.

Usage:
    python backfill_features.py                    # All symbols, all timeframes
    python backfill_features.py --symbols AAPL,BTC # Specific symbols
    python backfill_features.py --timeframes 1h,1d # Specific timeframes
    python backfill_features.py --days 365         # 1 year history (default)
"""

import asyncio
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from decimal import Decimal

import pandas as pd
import asyncpg
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.database_service import DatabaseService
from src.quant_engine.quant_features import QuantFeatureEngine
from src.config import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class FeatureEnricher:
    """
    Enriches OHLCV data with computed technical features.
    """

    def __init__(
        self,
        database_url: str,
        days_history: int = 365,
        max_concurrent: int = 5
    ):
        """
        Initialize enricher.

        Args:
            database_url: PostgreSQL connection string
            days_history: Days of data to enrich
            max_concurrent: Max concurrent symbols
        """
        self.database_url = database_url
        self.db_service = DatabaseService(database_url)
        self.days_history = days_history
        self.max_concurrent = max_concurrent

        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbols_processed": {},
            "summary": {
                "total_symbols": 0,
                "successful": 0,
                "failed": 0,
                "total_records_processed": 0,
                "total_records_inserted": 0,
                "total_records_updated": 0,
                "duration_seconds": 0
            }
        }

    async def run(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None
    ) -> Dict:
        """
        Run feature enrichment pipeline.

        Args:
            symbols: Specific symbols (None = all active)
            timeframes: Specific timeframes (None = all configured)

        Returns:
            Results dictionary
        """
        start_time = datetime.utcnow()
        logger.info("=" * 80)
        logger.info("FEATURE ENRICHMENT PIPELINE STARTED")
        logger.info("=" * 80)

        try:
            # Load symbols and timeframes
            tracked_data = await self._load_tracked_symbols(symbols, timeframes)
            if not tracked_data:
                logger.error("No symbols to enrich")
                return self.results

            self.results["summary"]["total_symbols"] = len(tracked_data)
            logger.info(f"Loaded {len(tracked_data)} symbols")

            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=self.days_history)
            logger.info(f"Date range: {start_date.date()} to {end_date.date()}")

            # Process symbols in parallel groups
            for i in range(0, len(tracked_data), self.max_concurrent):
                group = tracked_data[i : i + self.max_concurrent]
                logger.info(
                    f"\nProcessing group {i // self.max_concurrent + 1} "
                    f"({len(group)} symbols)"
                )

                tasks = []
                for symbol, asset_class, timeframes_list in group:
                    task = self._enrich_symbol(
                        symbol, asset_class, timeframes_list, start_date, end_date
                    )
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for (symbol, _, _), result in zip(group, results):
                    if isinstance(result, Exception):
                        logger.error(f"{symbol}: {result}")
                        self.results["symbols_processed"][symbol] = {
                            "status": "failed",
                            "error": str(result)
                        }
                        self.results["summary"]["failed"] += 1
                    else:
                        self.results["symbols_processed"][symbol] = result
                        if result["status"] == "completed":
                            self.results["summary"]["successful"] += 1
                        else:
                            self.results["summary"]["failed"] += 1

            # Final summary
            duration = (datetime.utcnow() - start_time).total_seconds()
            self.results["summary"]["duration_seconds"] = duration
            self._print_summary(duration)

            return self.results

        except Exception as e:
            logger.error(f"Enrichment pipeline failed: {e}", exc_info=True)
            return self.results

    async def _load_tracked_symbols(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None
    ) -> List[Tuple[str, str, List[str]]]:
        """Load tracked symbols from database"""
        try:
            conn = await asyncpg.connect(self.database_url)
            rows = await conn.fetch(
                "SELECT symbol, asset_class, timeframes FROM tracked_symbols WHERE active = TRUE"
            )
            await conn.close()

            result = []
            for row in rows:
                sym = row['symbol']

                # Filter by requested symbols
                if symbols and sym not in symbols:
                    continue

                # Get timeframes
                symbol_timeframes = list(row['timeframes']) if row['timeframes'] else ['1d']
                if timeframes:
                    symbol_timeframes = [tf for tf in symbol_timeframes if tf in timeframes]

                if symbol_timeframes:
                    result.append((sym, row['asset_class'], symbol_timeframes))

            return sorted(result)

        except Exception as e:
            logger.error(f"Failed to load symbols: {e}")
            return []

    async def _enrich_symbol(
        self,
        symbol: str,
        asset_class: str,
        timeframes: List[str],
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Enrich features for single symbol across all timeframes.
        """
        result = {
            "symbol": symbol,
            "asset_class": asset_class,
            "timeframes": {},
            "status": "completed",
            "total_processed": 0,
            "total_inserted": 0,
            "total_updated": 0,
            "errors": []
        }

        for timeframe in timeframes:
            try:
                logger.info(f"  {symbol}/{timeframe}: computing features...")

                tf_result = await self._compute_and_store_features(
                    symbol, timeframe, start_date, end_date
                )

                result["timeframes"][timeframe] = tf_result
                result["total_processed"] += tf_result.get("processed", 0)
                result["total_inserted"] += tf_result.get("inserted", 0)
                result["total_updated"] += tf_result.get("updated", 0)

                logger.info(
                    f"  {symbol}/{timeframe}: ✓ "
                    f"processed={tf_result.get('processed', 0)}, "
                    f"inserted={tf_result.get('inserted', 0)}, "
                    f"updated={tf_result.get('updated', 0)}"
                )

            except Exception as e:
                logger.error(f"  {symbol}/{timeframe}: {e}")
                result["timeframes"][timeframe] = {
                    "status": "failed",
                    "error": str(e)
                }
                result["errors"].append(timeframe)
                result["status"] = "partial_failure"

        self.results["summary"]["total_records_processed"] += result["total_processed"]
        self.results["summary"]["total_records_inserted"] += result["total_inserted"]
        self.results["summary"]["total_records_updated"] += result["total_updated"]

        return result

    async def _compute_and_store_features(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Compute features for symbol/timeframe and store in database.
        """
        # Fetch OHLCV data from database
        data = self.db_service.get_historical_data(
            symbol=symbol,
            timeframe=timeframe,
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            validated_only=False,
            min_quality=0
        )

        if not data:
            logger.debug(f"No OHLCV data found for {symbol}/{timeframe}")
            return {
                "status": "skipped",
                "processed": 0,
                "inserted": 0,
                "updated": 0
            }

        # Convert to DataFrame
        df = pd.DataFrame([
            {
                'time': pd.to_datetime(d['time']),
                'open': float(d['open']),
                'high': float(d['high']),
                'low': float(d['low']),
                'close': float(d['close']),
                'volume': int(d['volume'])
            }
            for d in data
        ])

        # Compute features
        df_with_features = QuantFeatureEngine.compute(df)

        # Prepare features for insertion
        features_data = []
        for idx, row in df_with_features.iterrows():
            features_data.append({
                'time': row['time'],
                'return_1d': float(row.get('return_1d', 0)),
                'volatility_20': float(row.get('volatility_20', 0)),
                'volatility_50': float(row.get('volatility_50', 0)),
                'atr': float(row.get('atr', 0)),
                'rolling_volume_20': int(row.get('rolling_volume_20', 0)),
                'volume_ratio': float(row.get('volume_ratio', 1)),
                'structure_label': str(row.get('structure_label', 'range')),
                'trend_direction': str(row.get('trend_direction', 'neutral')),
                'volatility_regime': str(row.get('volatility_regime', 'medium')),
                'trend_regime': str(row.get('trend_regime', 'ranging')),
                'compression_regime': str(row.get('compression_regime', 'expanded'))
            })

        # Store in database
        updated = self.db_service.insert_quant_features(
            symbol=symbol,
            timeframe=timeframe,
            features_data=features_data
        )

        return {
            "status": "completed",
            "processed": len(features_data),
            "inserted": 0,  # Both count towards records processed
            "updated": updated
        }

    def _print_summary(self, duration: float) -> None:
        """Print final summary"""
        summary = self.results["summary"]
        logger.info("\n" + "=" * 80)
        logger.info("ENRICHMENT SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration:.1f}s")
        logger.info(f"Symbols Processed: {summary['total_symbols']}")
        logger.info(f"  Successful: {summary['successful']}")
        logger.info(f"  Failed: {summary['failed']}")
        logger.info(f"Total Records Processed: {summary['total_records_processed']:,}")
        logger.info(f"Total Features Computed: {summary['total_records_updated']:,}")
        logger.info("=" * 80)


def _parse_args():
    """Parse command line arguments"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute and store technical features for OHLCV data"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbols (e.g., AAPL,BTC). Default: all active"
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        default=None,
        help="Comma-separated timeframes (e.g., 1m,1h,1d). Default: all configured"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Days of history to enrich (default: 365)"
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Max concurrent symbols (default: 5)"
    )

    return parser.parse_args()


async def main():
    """Main entry point"""
    args = _parse_args()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable required")
        sys.exit(1)

    # Parse symbols and timeframes
    symbols = (
        [s.strip().upper() for s in args.symbols.split(",")]
        if args.symbols
        else None
    )
    timeframes = (
        [t.strip() for t in args.timeframes.split(",")]
        if args.timeframes
        else None
    )

    enricher = FeatureEnricher(
        database_url=database_url,
        days_history=args.days,
        max_concurrent=args.max_concurrent
    )

    await enricher.run(symbols=symbols, timeframes=timeframes)


if __name__ == "__main__":
    asyncio.run(main())
