#!/usr/bin/env python3
"""
Repair Unvalidated Data Script

Identifies all records where validated=FALSE, re-validates them against quality thresholds,
and updates the database with actual validation metadata.

Flow:
1. Load all unvalidated records grouped by symbol/timeframe
2. For each symbol/timeframe, load full historical context
3. Re-validate each candle with previous-close gap detection and volume anomaly detection
4. Batch update database with quality scores and validation flags
5. Report completeness and quality distribution

Usage:
    python repair_unvalidated_data.py              # All unvalidated records
    python repair_unvalidated_data.py --limit 1000 # First 1000 unvalidated records
    python repair_unvalidated_data.py --symbols AAPL,BTC  # Specific symbols only
    python repair_unvalidated_data.py --timeframes 1d,1h  # Specific timeframes only
    python repair_unvalidated_data.py --dry-run    # Preview changes without updating DB
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from decimal import Decimal
import sys
import argparse
from pathlib import Path
import json

from dotenv import load_dotenv
import asyncpg

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.validation_service import ValidationService
from src.clients.multi_source_client import MultiSourceClient
from src.config import config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class UnvalidatedDataRepairer:
    """
    Repairs unvalidated market data by re-running through validation pipeline.
    """

    def __init__(
        self,
        database_url: str,
        polygon_api_key: str = None,
        dry_run: bool = False,
        batch_size: int = 100,
        quality_threshold: float = 0.85
    ):
        """
        Initialize repairer.

        Args:
            database_url: PostgreSQL connection string
            polygon_api_key: Polygon.io API key for fallback (optional)
            dry_run: If True, don't update database
            batch_size: Records to process at once
            quality_threshold: Minimum quality score to mark as validated
        """
        self.database_url = database_url
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.quality_threshold = quality_threshold
        self.validation_service = ValidationService()
        
        # Initialize multi-source client for fallback comparison
        # NOTE: Disabled to improve speed (API timeouts causing delays)
        self.data_client = None

        # Stats
        self.stats = {
            "total_unvalidated": 0,
            "records_processed": 0,
            "records_validated": 0,
            "records_rejected": 0,
            "quality_scores": [],
            "symbols_processed": set(),
            "timeframes_processed": set(),
            "errors": [],
            "start_time": datetime.utcnow(),
            "end_time": None
        }

    async def connect(self):
        """Create database connection pool."""
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=5,
            max_size=10,
            command_timeout=60
        )
        logger.info("Connected to database")

    async def disconnect(self):
        """Close database connections."""
        if self.pool:
            await self.pool.close()
            logger.info("Disconnected from database")

    async def get_unvalidated_records(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch unvalidated records from database.

        Args:
            symbols: Filter to specific symbols
            timeframes: Filter to specific timeframes
            limit: Maximum records to fetch

        Returns:
            List of unvalidated records
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT 
                    id, symbol, timeframe, time, 
                    open, high, low, close, volume,
                    quality_score, validation_notes
                FROM market_data
                WHERE validated = FALSE
            """

            params = []

            if symbols:
                placeholders = ",".join([f"${i+1}" for i in range(len(symbols))])
                query += f" AND symbol IN ({placeholders})"
                params.extend(symbols)

            if timeframes:
                tf_placeholders = ",".join([f"${len(params)+i+1}" for i in range(len(timeframes))])
                query += f" AND timeframe IN ({tf_placeholders})"
                params.extend(timeframes)

            query += " ORDER BY symbol, timeframe, time ASC"

            if limit:
                query += f" LIMIT {limit}"

            records = await conn.fetch(query, *params)
            self.stats["total_unvalidated"] = len(records)
            logger.info(f"Loaded {len(records)} unvalidated records")

            return records

    async def validate_and_repair(
        self,
        records: List[Dict],
        batch_size: int = 100
    ) -> Dict:
        """
        Validate records and update database, with optional fallback comparison.

        Args:
            records: List of unvalidated records
            batch_size: How many to process before batch updating DB

        Returns:
            Stats dictionary
        """
        if not records:
            logger.warning("No unvalidated records to process")
            return self.stats

        logger.info(f"Starting validation of {len(records)} records")

        updates = []  # Batch of updates
        current_symbol = None
        current_timeframe = None
        symbol_candles = {}  # Cache of candles per symbol/timeframe

        # Pre-load all unique symbol/timeframe contexts (parallel)
        unique_keys = set((r["symbol"], r["timeframe"]) for r in records)
        for symbol, timeframe in unique_keys:
            key = f"{symbol}_{timeframe}"
            symbol_candles[key] = await self._load_symbol_candles(symbol, timeframe)

        for i, record in enumerate(records):
            symbol = record["symbol"]
            timeframe = record["timeframe"]
            key = f"{symbol}_{timeframe}"

            # Get previous close for gap detection (cached in symbol_candles)
            prev_close = self._get_prev_close_from_cache(symbol_candles[key], record["time"])

            # Calculate median volume for anomaly detection
            candles_for_symbol = symbol_candles[key]
            median_volume = self.validation_service.calculate_median_volume(candles_for_symbol)

            # Validate this candle
            candle_dict = {
                "t": int(record["time"].timestamp() * 1000),  # Convert to milliseconds
                "o": float(record["open"]),
                "h": float(record["high"]),
                "l": float(record["low"]),
                "c": float(record["close"]),
                "v": int(record["volume"])
            }

            quality_score, metadata = self.validation_service.validate_candle(
                symbol=symbol,
                candle=candle_dict,
                prev_close=prev_close,
                median_volume=median_volume if median_volume > 0 else None
            )

            # If quality is poor and fallback client available, try alternate source
            source = None
            if quality_score < 0.85 and self.data_client:
                try:
                    record_date = record["time"].strftime('%Y-%m-%d')
                    alt_candles, alt_source = await self.data_client.fetch_range(
                        symbol=symbol,
                        timeframe=timeframe,
                        start=record_date,
                        end=record_date,
                        validate=True
                    )
                    
                    if alt_candles:
                        alt_quality = self.validation_service.validate_candle(
                            symbol=symbol,
                            candle=alt_candles[0],
                            prev_close=prev_close,
                            median_volume=median_volume if median_volume > 0 else None
                        )[0]
                        
                        if alt_quality > quality_score:
                            logger.info(f"Using {alt_source} data for {symbol}: {alt_quality:.2f} > {quality_score:.2f}")
                            quality_score = alt_quality
                            source = alt_source
                            # Update metadata with alt source info
                            metadata["validation_notes"] += f" [alt:{alt_source}]"
                except Exception as e:
                    logger.debug(f"Fallback fetch failed for {symbol}/{record_date}: {e}")

            # Prepare update
            updates.append({
                "id": record["id"],
                "quality_score": quality_score,
                "validated": metadata["validated"],
                "validation_notes": metadata["validation_notes"],
                "gap_detected": metadata["gap_detected"],
                "volume_anomaly": metadata["volume_anomaly"],
                "source": source
            })

            # Track stats
            self.stats["records_processed"] += 1
            self.stats["quality_scores"].append(quality_score)
            if metadata["validated"]:
                self.stats["records_validated"] += 1
            else:
                self.stats["records_rejected"] += 1

            self.stats["symbols_processed"].add(symbol)
            self.stats["timeframes_processed"].add(timeframe)

            # Batch update
            if len(updates) >= batch_size or i == len(records) - 1:
                if not self.dry_run:
                    await self._batch_update(updates)
                    logger.info(f"Updated {len(updates)} records ({self.stats['records_processed']}/{len(records)})")
                else:
                    logger.info(f"[DRY RUN] Would update {len(updates)} records ({self.stats['records_processed']}/{len(records)})")

                updates = []

            # Progress
            if (self.stats["records_processed"] % 500) == 0:
                logger.info(f"Progress: {self.stats['records_processed']}/{len(records)} records processed")

        self.stats["end_time"] = datetime.utcnow()
        return self.stats

    async def _load_symbol_candles(self, symbol: str, timeframe: str) -> List[Dict]:
        """Load all candles for a symbol/timeframe for context."""
        async with self.pool.acquire() as conn:
            query = """
                SELECT 
                    time, open, high, low, close, volume
                FROM market_data
                WHERE symbol = $1 AND timeframe = $2
                ORDER BY time ASC
            """
            rows = await conn.fetch(query, symbol, timeframe)

            return [
                {
                    "t": int(row["time"].timestamp() * 1000),
                    "o": float(row["open"]),
                    "h": float(row["high"]),
                    "l": float(row["low"]),
                    "c": float(row["close"]),
                    "v": int(row["volume"])
                }
                for row in rows
            ]

    def _get_prev_close_from_cache(self, candles: List[Dict], current_time) -> Optional[float]:
        """Get previous candle's close price from cached candles (no DB call)."""
        current_ts = int(current_time.timestamp() * 1000)
        for i in range(len(candles) - 1, -1, -1):
            if candles[i]["t"] < current_ts:
                return candles[i]["c"]
        return None

    async def _batch_update(self, updates: List[Dict]) -> None:
        """Batch update records in database (parallel)."""
        if not updates:
            return

        query = """
            UPDATE market_data
            SET 
                quality_score = $2,
                validated = $3,
                validation_notes = $4,
                gap_detected = $5,
                volume_anomaly = $6,
                source = COALESCE($7, source),
                fetched_at = NOW()
            WHERE id = $1
        """

        async def update_record(update):
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        query,
                        update["id"],
                        update["quality_score"],
                        update["validated"],
                        update["validation_notes"],
                        update["gap_detected"],
                        update["volume_anomaly"],
                        update.get("source")
                    )
            except Exception as e:
                logger.error(f"Failed to update record {update['id']}: {e}")
                self.stats["errors"].append(f"Update failed for id {update['id']}: {str(e)}")

        # Run all updates in parallel (up to 10 concurrent)
        tasks = [update_record(u) for u in updates]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def generate_report(self) -> Dict:
        """Generate summary report."""
        if self.stats["quality_scores"]:
            quality_scores = self.stats["quality_scores"]
            avg_score = sum(quality_scores) / len(quality_scores)
            min_score = min(quality_scores)
            max_score = max(quality_scores)
        else:
            avg_score = min_score = max_score = 0.0

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "dry_run": self.dry_run,
            "duration_seconds": (self.stats["end_time"] - self.stats["start_time"]).total_seconds(),
            "total_unvalidated_found": self.stats["total_unvalidated"],
            "records_processed": self.stats["records_processed"],
            "records_validated": self.stats["records_validated"],
            "records_rejected": self.stats["records_rejected"],
            "validation_rate": (
                self.stats["records_validated"] / self.stats["records_processed"] * 100
                if self.stats["records_processed"] > 0
                else 0.0
            ),
            "quality_score_stats": {
                "average": round(avg_score, 2),
                "min": round(min_score, 2),
                "max": round(max_score, 2)
            },
            "symbols_processed": sorted(list(self.stats["symbols_processed"])),
            "timeframes_processed": sorted(list(self.stats["timeframes_processed"])),
            "error_count": len(self.stats["errors"]),
            "errors": self.stats["errors"][:10]  # First 10 errors
        }

        return report

    async def run(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        limit: Optional[int] = None
    ) -> Dict:
        """
        Run repair process.

        Args:
            symbols: Filter to specific symbols
            timeframes: Filter to specific timeframes
            limit: Maximum records to process

        Returns:
            Report dictionary
        """
        try:
            await self.connect()

            # Load unvalidated records
            records = await self.get_unvalidated_records(
                symbols=symbols,
                timeframes=timeframes,
                limit=limit
            )

            if not records:
                logger.warning("No unvalidated records found")
                return await self.generate_report()

            # Validate and repair
            await self.validate_and_repair(records, batch_size=self.batch_size)

            # Generate report
            report = await self.generate_report()

            return report

        except Exception as e:
            logger.error(f"Error in repair process: {e}", exc_info=True)
            self.stats["errors"].append(f"Fatal error: {str(e)}")
            return await self.generate_report()

        finally:
            await self.disconnect()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Repair unvalidated market data by re-running validation"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbols (e.g., AAPL,BTC,SPY)"
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        default=None,
        help="Comma-separated timeframes (e.g., 1d,1h,5m)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum records to process"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without updating database"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Records to process before batch updating DB"
    )
    parser.add_argument(
        "--quality-threshold",
        type=float,
        default=0.85,
        help="Quality score threshold for validation"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output report to JSON file"
    )

    args = parser.parse_args()

    # Parse symbols and timeframes
    symbols = args.symbols.split(",") if args.symbols else None
    timeframes = args.timeframes.split(",") if args.timeframes else None

    # Create repairer
    repairer = UnvalidatedDataRepairer(
        database_url=config.database_url,
        polygon_api_key=config.polygon_api_key,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        quality_threshold=args.quality_threshold
    )

    # Run repair
    logger.info(f"Starting repair process (dry_run={args.dry_run})")
    report = await repairer.run(
        symbols=symbols,
        timeframes=timeframes,
        limit=args.limit
    )

    # Output report
    print("\n" + "=" * 70)
    print("REPAIR REPORT")
    print("=" * 70)
    print(f"Timestamp: {report['timestamp']}")
    print(f"Dry Run: {report['dry_run']}")
    print(f"Duration: {report['duration_seconds']:.2f}s")
    print()
    print(f"Total Unvalidated Found: {report['total_unvalidated_found']}")
    print(f"Records Processed: {report['records_processed']}")
    print(f"Records Validated: {report['records_validated']}")
    print(f"Records Rejected: {report['records_rejected']}")
    print(f"Validation Rate: {report['validation_rate']:.1f}%")
    print()
    print("Quality Score Stats:")
    print(f"  Average: {report['quality_score_stats']['average']}")
    print(f"  Min: {report['quality_score_stats']['min']}")
    print(f"  Max: {report['quality_score_stats']['max']}")
    print()
    print(f"Symbols Processed: {', '.join(report['symbols_processed']) or 'None'}")
    print(f"Timeframes Processed: {', '.join(report['timeframes_processed']) or 'None'}")
    print(f"Errors: {report['error_count']}")
    if report['errors']:
        print("Error Details:")
        for error in report['errors']:
            print(f"  - {error}")
    print("=" * 70)

    # Save report if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Report saved to {args.output}")

    return 0 if report['error_count'] == 0 else 1


if __name__ == "__main__":
    load_dotenv()
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
