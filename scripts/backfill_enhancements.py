#!/usr/bin/env python3
"""
Backfill Enhancements - Alternative data and market insights.
Includes data that complements standard OHLCV:
  - News Articles & Sentiment Analysis
  - Adjusted OHLCV prices (split/dividend adjusted)

NOTE: Dividends, Splits, Earnings, and Options require higher Polygon API tier.
      This script runs on Starter plan ($29/mo) - only News and Adjusted OHLCV available.

Prerequisite: Run backfill_ohlcv.py first for standard price/volume data.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
import argparse
from dotenv import load_dotenv
import asyncpg

from src.clients.polygon_client import PolygonClient
from src.services.validation_service import ValidationService
from src.services.database_service import DatabaseService
from src.services.news_service import NewsService
from src.services.sentiment_service import SentimentService
from src.services.dividend_split_service import DividendSplitService
from src.services.feature_service import FeatureService

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default backfill date range (5 years of data)
END_DATE = datetime.utcnow().date()
START_DATE = END_DATE - timedelta(days=365*5)


async def backfill_ohlcv(
    symbol: str,
    polygon_client: PolygonClient,
    validation_service: ValidationService,
    db_service: DatabaseService,
    start_date: datetime.date,
    end_date: datetime.date,
    timeframe: str = '1d'
) -> tuple[int, int]:
    """
    Backfill OHLCV data for a single symbol and timeframe.
    """
    try:
        logger.info(f"[{symbol}] Backfilling OHLCV ({timeframe}): {start_date} to {end_date}")
        
        candles = await polygon_client.fetch_range(
            symbol,
            timeframe,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if not candles:
            logger.warning(f"[{symbol}] No OHLCV data returned")
            return 0, 1
        
        logger.info(f"[{symbol}] Fetched {len(candles)} candles ({timeframe})")
        
        # Calculate median volume for anomaly detection
        median_vol = validation_service.calculate_median_volume(candles)
        
        # Validate each candle
        from decimal import Decimal
        metadata_list = []
        prev_close = None
        
        for candle in candles:
            _, meta = validation_service.validate_candle(
                symbol,
                candle,
                prev_close=Decimal(str(prev_close)) if prev_close is not None else None,
                median_volume=median_vol if median_vol > 0 else None
            )
            metadata_list.append(meta)
            prev_close = candle.get('c')
        
        # Insert into database
        inserted = db_service.insert_ohlcv_batch(symbol, candles, metadata_list, timeframe)
        
        logger.info(f"[{symbol}] ✓ Inserted {inserted} OHLCV records ({timeframe})")
        return inserted, 0
    
    except Exception as e:
        logger.error(f"[{symbol}] ✗ Error backfilling OHLCV: {e}")
        return 0, 1


async def backfill_news_sentiment(
    symbol: str,
    polygon_client: PolygonClient,
    sentiment_service: SentimentService,
    news_service: NewsService,
    start_date: datetime.date,
    end_date: datetime.date
) -> tuple[int, int]:
    """
    Backfill news articles with sentiment analysis.
    """
    try:
        logger.info(f"[{symbol}] Backfilling news/sentiment: {start_date} to {end_date}")
        
        # Fetch news from Polygon
        articles = await polygon_client.fetch_news(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if not articles:
            logger.warning(f"[{symbol}] No news articles found")
            return 0, 0
        
        logger.info(f"[{symbol}] Fetched {len(articles)} news articles")
        
        # Analyze sentiment for each article
        articles_with_sentiment = []
        for article in articles:
            try:
                title = article.get('title', '')
                description = article.get('description', '')
                
                # Combine title and description for sentiment analysis
                text = f"{title} {description}".strip()
                
                if text:
                    sentiment = sentiment_service.analyze_text(text)
                    article['sentiment_score'] = sentiment.get('sentiment_score', 0)
                    article['sentiment_label'] = sentiment.get('sentiment_label', 'NEUTRAL')
                    article['sentiment_confidence'] = sentiment.get('confidence', 0)
                else:
                    article['sentiment_score'] = 0
                    article['sentiment_label'] = 'NEUTRAL'
                    article['sentiment_confidence'] = 0
                
                articles_with_sentiment.append(article)
            except Exception as e:
                logger.warning(f"[{symbol}] Error analyzing sentiment for article: {e}")
                article['sentiment_score'] = 0
                article['sentiment_label'] = 'NEUTRAL'
                article['sentiment_confidence'] = 0
                articles_with_sentiment.append(article)
        
        # Insert into database
        inserted, failed = news_service.insert_news_batch(symbol, articles_with_sentiment)
        logger.info(f"[{symbol}] ✓ Inserted {inserted} news articles with sentiment")
        return inserted, failed
    
    except Exception as e:
        logger.error(f"[{symbol}] ✗ Error backfilling news/sentiment: {e}")
        return 0, 1





async def backfill_adjusted_ohlcv(
    symbol: str,
    polygon_client: PolygonClient,
    dividend_service: DividendSplitService,
    start_date: datetime.date,
    end_date: datetime.date,
    timeframe: str = '1d'
) -> tuple[int, int]:
    """
    Backfill adjusted OHLCV prices (adjusted for splits and dividends).
    """
    try:
        logger.info(f"[{symbol}] Backfilling adjusted OHLCV ({timeframe}): {start_date} to {end_date}")
        
        # Fetch adjusted data from Polygon
        candles = await polygon_client.fetch_range(
            symbol,
            timeframe,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            adjusted=True
        )
        
        if not candles:
            logger.info(f"[{symbol}] No adjusted OHLCV data returned")
            return 0, 0
        
        logger.info(f"[{symbol}] Fetched {len(candles)} adjusted candles ({timeframe})")
        
        # Insert into database
        inserted = dividend_service.insert_adjusted_ohlcv_batch(symbol, candles, timeframe)
        logger.info(f"[{symbol}] ✓ Inserted {inserted} adjusted OHLCV records ({timeframe})")
        return inserted, 0
    
    except Exception as e:
        logger.error(f"[{symbol}] ✗ Error backfilling adjusted OHLCV: {e}")
        return 0, 1


def _parse_args():
    parser = argparse.ArgumentParser(description="Backfill alternative data (Starter plan: News + Adjusted OHLCV only)")
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbols (e.g., AAPL,MSFT). If omitted, backfills all active symbols"
    )
    parser.add_argument(
        "--start",
        type=str,
        default=START_DATE.strftime("%Y-%m-%d"),
        help="Start date (YYYY-MM-DD). Defaults to ~5 years ago"
    )
    parser.add_argument(
        "--end",
        type=str,
        default=END_DATE.strftime("%Y-%m-%d"),
        help="End date (YYYY-MM-DD). Defaults to today (UTC)"
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="1d",
        help="Timeframe: 5m, 15m, 30m, 1h, 4h, 1d (default), 1w"
    )
    parser.add_argument(
        "--only-ohlcv",
        action="store_true",
        help="Only backfill OHLCV data (not recommended, use backfill_ohlcv.py instead)"
    )
    parser.add_argument(
        "--skip-news",
        action="store_true",
        help="Skip news/sentiment backfill (default: enabled)"
    )
    parser.add_argument(
        "--skip-adjusted",
        action="store_true",
        help="Skip adjusted OHLCV backfill"
    )
    return parser.parse_args()


async def fetch_active_symbols(database_url: str) -> list[str]:
    """Fetch all active symbols from tracked_symbols table"""
    try:
        conn = await asyncpg.connect(database_url)
        rows = await conn.fetch(
            "SELECT symbol FROM tracked_symbols WHERE active = TRUE ORDER BY symbol"
        )
        await conn.close()
        return [row['symbol'] for row in rows]
    except Exception as e:
        logger.error(f"Error fetching symbols from database: {e}")
        return []


async def main():
    """Run comprehensive backfill for requested symbols"""
    args = _parse_args()
    
    try:
        start_dt = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(args.end, "%Y-%m-%d").date()
    except ValueError:
        logger.error("Invalid --start or --end date. Use YYYY-MM-DD format.")
        return

    if start_dt > end_dt:
        logger.error("Start date must be <= end date")
        return

    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        db_user = os.getenv("DB_USER", "market_user")
        db_password = os.getenv("DB_PASSWORD", "changeMe123")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/market_data"
    
    # Determine which symbols to backfill
    if args.symbols:
        requested_symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        logger.info("Fetching active symbols from database...")
        requested_symbols = await fetch_active_symbols(database_url)
    
    if not requested_symbols:
        logger.error("No symbols to backfill. Initialize symbols first with: python scripts/init_symbols.py")
        return
    
    # Validate timeframe
    if args.timeframe not in ['5m', '15m', '30m', '1h', '4h', '1d', '1w']:
        logger.error(f"Invalid timeframe: {args.timeframe}")
        return
    
    polygon_api_key = os.getenv("POLYGON_API_KEY")
    if not polygon_api_key:
        logger.error("POLYGON_API_KEY not set in environment")
        return
    
    # Initialize services
    polygon_client = PolygonClient(polygon_api_key)
    validation_service = ValidationService()
    db_service = DatabaseService(database_url)
    news_service = NewsService(db_service)
    sentiment_service = SentimentService()
    dividend_service = DividendSplitService(db_service)
    feature_service = FeatureService(database_url)
    
    logger.info("=" * 80)
    logger.info(f"BACKFILL V2 - Comprehensive Market Data Backfill")
    logger.info("=" * 80)
    logger.info(f"Symbols: {len(requested_symbols)}")
    logger.info(f"Date range: {start_dt} to {end_dt}")
    logger.info(f"Timeframe: {args.timeframe}")
    logger.info("=" * 80)
    
    # Track statistics
    stats = {
        'ohlcv': {'inserted': 0, 'failed': 0},
        'news': {'inserted': 0, 'failed': 0},
        'adjusted': {'inserted': 0, 'failed': 0},
    }
    
    # Backfill each symbol
    for i, symbol in enumerate(requested_symbols, 1):
        logger.info(f"\n[{i}/{len(requested_symbols)}] Processing {symbol}")
        logger.info("-" * 80)
        
        try:
            # OHLCV Data (skip by default in V2, only if --only-ohlcv flag is used)
            if args.only_ohlcv:
                inserted, failed = await backfill_ohlcv(
                    symbol, polygon_client, validation_service, db_service,
                    start_dt, end_dt, args.timeframe
                )
                stats['ohlcv']['inserted'] += inserted
                stats['ohlcv']['failed'] += failed
            
            # News & Sentiment
            if not args.skip_news:
                inserted, failed = await backfill_news_sentiment(
                    symbol, polygon_client, sentiment_service, news_service,
                    start_dt, end_dt
                )
                stats['news']['inserted'] += inserted
                stats['news']['failed'] += failed
            
            # Adjusted OHLCV
            if not args.skip_adjusted:
                inserted, failed = await backfill_adjusted_ohlcv(
                    symbol, polygon_client, dividend_service,
                    start_dt, end_dt, args.timeframe
                )
                stats['adjusted']['inserted'] += inserted
                stats['adjusted']['failed'] += failed
        
        except Exception as e:
            logger.error(f"[{symbol}] Fatal error: {e}")
            continue
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("BACKFILL COMPLETE (Starter Plan - News + Adjusted OHLCV)")
    logger.info("=" * 80)
    logger.info(f"Total symbols processed: {len(requested_symbols)}")
    logger.info("\nData inserted:")
    logger.info(f"  OHLCV: {stats['ohlcv']['inserted']:,} records")
    logger.info(f"  News/Sentiment: {stats['news']['inserted']:,} articles")
    logger.info(f"  Adjusted OHLCV: {stats['adjusted']['inserted']:,} records")
    logger.info("\nData failed:")
    logger.info(f"  OHLCV: {stats['ohlcv']['failed']} symbols")
    logger.info(f"  News/Sentiment: {stats['news']['failed']} symbols")
    logger.info(f"  Adjusted OHLCV: {stats['adjusted']['failed']} symbols")
    logger.info("\nNote: Dividends, Splits, Earnings, Options require higher Polygon API tier")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
