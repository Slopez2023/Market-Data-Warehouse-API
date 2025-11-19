#!/usr/bin/env python3
"""
Export production-ready dataset for backtesting/AI training.

Filters:
- Only validated records (quality_score >= 0.80)
- Exports as CSV with metadata
- Detects data gaps
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
import asyncpg
import json
import sys

from dotenv import load_dotenv
from src.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CleanDataExporter:
    """Export clean dataset for AI training."""

    def __init__(self, database_url: str, output_dir: str = "data"):
        self.database_url = database_url
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.pool = None
        self.export_log = []

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

    async def get_available_symbols_timeframes(self) -> List[tuple]:
        """Get all unique symbol/timeframe combinations."""
        async with self.pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT DISTINCT symbol, timeframe
                FROM market_data
                WHERE validated = TRUE
                ORDER BY symbol, timeframe
            """)
            return [(r['symbol'], r['timeframe']) for r in records]

    async def export_symbol(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Export single symbol/timeframe to CSV."""
        try:
            async with self.pool.acquire() as conn:
                records = await conn.fetch("""
                    SELECT 
                        time, open, high, low, close, volume,
                        quality_score, source
                    FROM market_data
                    WHERE 
                        symbol = $1 
                        AND timeframe = $2
                        AND validated = true
                        AND quality_score >= 0.80
                    ORDER BY time ASC
                """, symbol, timeframe)

            if not records:
                logger.warning(f"No valid records for {symbol}/{timeframe}")
                return None

            # Convert to DataFrame
            data = []
            for r in records:
                data.append({
                    'timestamp': r['time'].isoformat(),
                    'open': float(r['open']),
                    'high': float(r['high']),
                    'low': float(r['low']),
                    'close': float(r['close']),
                    'volume': int(r['volume']),
                    'quality_score': float(r['quality_score']),
                    'source': r['source'] or 'polygon'
                })

            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')

            # Detect gaps
            gaps = self._detect_gaps(df)

            # Export to CSV
            filename = self.output_dir / f"{symbol}_{timeframe}_clean.csv"
            df.to_csv(filename, index=False)
            
            logger.info(f"Exported {len(df)} records to {filename}")

            result = {
                'symbol': symbol,
                'timeframe': timeframe,
                'records': len(df),
                'start_date': df['timestamp'].min().isoformat(),
                'end_date': df['timestamp'].max().isoformat(),
                'avg_quality_score': float(df['quality_score'].mean()),
                'gaps': gaps,
                'file': str(filename)
            }

            return result

        except Exception as e:
            logger.error(f"Failed to export {symbol}/{timeframe}: {e}")
            return None

    def _detect_gaps(self, df: pd.DataFrame) -> List[Dict]:
        """Find data gaps in dataset."""
        gaps = []
        if len(df) < 2:
            return gaps

        df_sorted = df.sort_values('timestamp')
        df_sorted['time_diff'] = df_sorted['timestamp'].diff()

        # Calculate expected frequency
        if len(df_sorted) > 10:
            typical_diff = df_sorted['time_diff'].median()
            threshold = typical_diff * 1.5
        else:
            return gaps

        gap_rows = df_sorted[df_sorted['time_diff'] > threshold]
        for idx, row in gap_rows.iterrows():
            gaps.append({
                'after_date': row['timestamp'].isoformat(),
                'gap_duration': str(row['time_diff'])
            })

        return gaps

    async def run(self, symbols: Optional[List[str]] = None, timeframes: Optional[List[str]] = None):
        """Run export process."""
        try:
            await self.connect()

            # Get available combinations
            available = await self.get_available_symbols_timeframes()
            
            if symbols:
                available = [(s, t) for s, t in available if s in symbols]
            if timeframes:
                available = [(s, t) for s, t in available if t in timeframes]

            if not available:
                logger.warning("No data matching filters")
                return

            logger.info(f"Exporting {len(available)} symbol/timeframe combinations")

            for symbol, timeframe in available:
                result = await self.export_symbol(symbol, timeframe)
                if result:
                    self.export_log.append(result)

            self._generate_summary()
            self._save_export_metadata()

        except Exception as e:
            logger.error(f"Error in export process: {e}", exc_info=True)

        finally:
            await self.disconnect()

    def _generate_summary(self):
        """Print export summary."""
        if not self.export_log:
            print("\nNo data exported")
            return

        total_records = sum(e['records'] for e in self.export_log)
        avg_quality = sum(e['avg_quality_score'] for e in self.export_log) / len(self.export_log)
        total_gaps = sum(len(e['gaps']) for e in self.export_log)

        print("\n" + "=" * 80)
        print("CLEAN DATA EXPORT SUMMARY")
        print("=" * 80)
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        print(f"Output Directory: {self.output_dir}")
        print()
        print(f"Total Records Exported: {total_records:,}")
        print(f"Symbols: {len(set(e['symbol'] for e in self.export_log))}")
        print(f"Timeframes: {len(set(e['timeframe'] for e in self.export_log))}")
        print(f"Average Quality Score: {avg_quality:.2f}")
        print(f"Total Data Gaps Detected: {total_gaps}")
        print()
        print("Files Created:")
        for export in sorted(self.export_log, key=lambda x: (x['symbol'], x['timeframe'])):
            gap_info = f" ({len(export['gaps'])} gaps)" if export['gaps'] else ""
            print(f"  - {export['symbol']:12} {export['timeframe']:6} {export['records']:8,} records{gap_info}")
        print("=" * 80 + "\n")

    def _save_export_metadata(self):
        """Save export metadata to JSON."""
        metadata = {
            'timestamp': datetime.utcnow().isoformat(),
            'output_directory': str(self.output_dir),
            'total_exports': len(self.export_log),
            'total_records': sum(e['records'] for e in self.export_log),
            'exports': self.export_log
        }

        metadata_file = self.output_dir / "EXPORT_METADATA.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Metadata saved to {metadata_file}")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Export clean market data for backtesting/AI training"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbols (e.g., AAPL,BTC-USD)"
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        default=None,
        help="Comma-separated timeframes (e.g., 1d,1h)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data",
        help="Output directory for CSV files"
    )

    args = parser.parse_args()

    symbols = args.symbols.split(",") if args.symbols else None
    timeframes = args.timeframes.split(",") if args.timeframes else None

    exporter = CleanDataExporter(
        database_url=config.database_url,
        output_dir=args.output
    )

    logger.info("Starting clean data export")
    await exporter.run(symbols=symbols, timeframes=timeframes)

    return 0


if __name__ == "__main__":
    load_dotenv()
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
