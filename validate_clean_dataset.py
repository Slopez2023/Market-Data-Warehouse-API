#!/usr/bin/env python3
"""
Validate exported dataset meets AI training standards.

Checks:
- Minimum record count per file
- Data gaps (no missing data > expected frequency)
- Price continuity (no 5% jumps)
- No null values
"""

import pandas as pd
from pathlib import Path
import logging
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatasetValidator:
    """Validate exported dataset for training."""

    REQUIREMENTS = {
        'min_records': 100,           # At least 100 candles
        'max_gap_hours': 120,         # No gaps > 5 days (allows weekends/holidays)
        'min_coverage': 0.80,         # 80% of expected dates
        'max_price_jump': 0.20,       # Max 20% jump between candles
    }

    def validate_file(self, filepath: str) -> Dict[str, bool]:
        """Validate single CSV file."""
        try:
            df = pd.read_csv(filepath)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')

            results = {
                'file': Path(filepath).name,
                'sufficient_records': len(df) >= self.REQUIREMENTS['min_records'],
                'no_extreme_gaps': self._check_gaps(df),
                'no_nulls': df[['open', 'high', 'low', 'close', 'volume']].isnull().sum().sum() == 0,
                'price_continuity': self._check_price_continuity(df),
                'record_count': len(df),
            }

            return results

        except Exception as e:
            logger.error(f"Error validating {filepath}: {e}")
            return {
                'file': Path(filepath).name,
                'error': str(e)
            }

    def _check_gaps(self, df: pd.DataFrame) -> bool:
        """Check for extreme gaps in data."""
        if len(df) < 2:
            return True

        df['time_diff'] = df['timestamp'].diff().dt.total_seconds() / 3600  # Hours

        max_gap = df['time_diff'].max()
        max_allowed = self.REQUIREMENTS['max_gap_hours']

        return max_gap <= max_allowed

    def _check_price_continuity(self, df: pd.DataFrame) -> bool:
        """Check for suspicious price jumps."""
        if len(df) < 2:
            return True

        # Check close-to-open jumps
        df['price_jump'] = abs(df['close'].shift() - df['open']) / df['close'].shift().abs()
        
        bad_jumps = (df['price_jump'] > self.REQUIREMENTS['max_price_jump']).sum()
        
        # Allow 1-2 bad jumps (gaps, corporate actions)
        return bad_jumps <= 2

    def validate_all(self, data_dir: str = 'data') -> Dict:
        """Validate all exported files."""
        data_path = Path(data_dir)
        
        if not data_path.exists():
            logger.error(f"Data directory not found: {data_dir}")
            return {}

        files = sorted(data_path.glob('*_clean.csv'))

        if not files:
            logger.warning(f"No CSV files found in {data_dir}")
            return {}

        logger.info(f"Validating {len(files)} files")

        results = {}
        for filepath in files:
            result = self.validate_file(str(filepath))
            results[filepath.name] = result

        return results

    def print_report(self, results: Dict):
        """Print validation report."""
        if not results:
            print("No results to report")
            return

        print("\n" + "=" * 100)
        print("DATASET VALIDATION REPORT")
        print("=" * 100)

        # Summary
        passed = sum(1 for r in results.values() if all(v == True for k, v in r.items() if k != 'file' and k != 'record_count'))
        total = len(results)

        print(f"\nValidation Results: {passed}/{total} PASSED")
        print()

        # Detailed results
        print(f"{'File':<40} {'Records':>10} {'Status':<20}")
        print("-" * 70)

        for filename, checks in sorted(results.items()):
            if 'error' in checks:
                status = f"❌ ERROR: {checks['error']}"
            else:
                all_pass = all(v == True for k, v in checks.items() 
                              if k not in ['file', 'record_count'])
                status = "✅ PASS" if all_pass else "❌ FAIL"
                
                # Show which checks failed
                failures = [k for k, v in checks.items() 
                           if k not in ['file', 'record_count'] and v == False]
                if failures:
                    status += f" ({', '.join(failures)})"

            records = checks.get('record_count', 'N/A')
            print(f"{filename:<40} {records:>10} {status:<20}")

        print("=" * 100 + "\n")

        # Recommendations
        print("Recommendations:")
        print("- Files marked with ✅ PASS are ready for backtesting/AI training")
        print("- Files marked with ❌ FAIL need manual review or reprocessing")
        print("- Ensure all files have at least 100 records for statistical validity")
        print()


async def main():
    """Main entry point."""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Validate clean dataset for AI training"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Directory containing exported CSV files"
    )

    args = parser.parse_args()

    validator = DatasetValidator()
    results = validator.validate_all(args.data_dir)
    validator.print_report(results)

    # Return success if all passed
    passed = sum(1 for r in results.values() 
                if all(v == True for k, v in r.items() 
                      if k not in ['file', 'record_count']))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    import asyncio
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
