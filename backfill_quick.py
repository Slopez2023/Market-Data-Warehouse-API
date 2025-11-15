#!/usr/bin/env python3
"""Quick backfill with just 5 symbols x 2 timeframes"""

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from scripts.phase_2_backfill_baseline import BackfillBaselineRunner
from src.config import config

async def main():
    runner = BackfillBaselineRunner(config.database_url, config.polygon_api_key)
    
    results = await runner.run_baseline(
        symbols=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
        timeframes=["1d", "1h"],
        days_back=30
    )
    
    runner.print_report()
    runner.save_report()

if __name__ == "__main__":
    asyncio.run(main())
