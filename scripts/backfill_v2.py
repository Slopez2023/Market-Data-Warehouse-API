#!/usr/bin/env python3
"""
Backfill v2 - Comprehensive backfill for all available data
Extends backfill.py to include:
  - News & Sentiment
  - Options IV & Chain Data
  - Earnings & Estimates
  - Dividends & Stock Splits
  - Adjusted OHLCV prices
  - Volatility Regime classification
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
from src.services.options_iv_service import OptionsIVService
from src.services.earnings_service import EarningsService
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
                    sentiment = sentiment_service.analyze_sentiment(text)
                    article['sentiment_score'] = sentiment.get('score', 0)
                    article['sentiment_label'] = sentiment.get('label', 'NEUTRAL')
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


async def backfill_dividends(
    symbol: str,
    polygon_client: PolygonClient,
    dividend_service: DividendSplitService,
    start_date: datetime.date,
    end_date: datetime.date
) -> tuple[int, int]:
    """
    Backfill dividend records.
    """
    try:
        logger.info(f"[{symbol}] Backfilling dividends: {start_date} to {end_date}")
        
        # Fetch dividends from Polygon
        dividends = await polygon_client.fetch_dividends(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if not dividends:
            logger.info(f"[{symbol}] No dividends found")
            return 0, 0
        
        logger.info(f"[{symbol}] Fetched {len(dividends)} dividend records")
        
        # Insert into database
        inserted, failed = dividend_service.insert_dividends_batch(symbol, dividends)
        logger.info(f"[{symbol}] ✓ Inserted {inserted} dividend records")
        return inserted, failed
    
    except Exception as e:
        logger.error(f"[{symbol}] ✗ Error backfilling dividends: {e}")
        return 0, 1


async def backfill_stock_splits(
    symbol: str,
    polygon_client: PolygonClient,
    dividend_service: DividendSplitService,
    start_date: datetime.date,
    end_date: datetime.date
) -> tuple[int, int]:
    """
    Backfill stock split records.
    """
    try:
        logger.info(f"[{symbol}] Backfilling stock splits: {start_date} to {end_date}")
        
        # Fetch splits from Polygon
        splits = await polygon_client.fetch_splits(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if not splits:
            logger.info(f"[{symbol}] No stock splits found")
            return 0, 0
        
        logger.info(f"[{symbol}] Fetched {len(splits)} split records")
        
        # Insert into database
        inserted, failed = dividend_service.insert_splits_batch(symbol, splits)
        logger.info(f"[{symbol}] ✓ Inserted {inserted} stock split records")
        return inserted, failed
    
    except Exception as e:
        logger.error(f"[{symbol}] ✗ Error backfilling stock splits: {e}")
        return 0, 1


async def backfill_earnings(
    symbol: str,
    polygon_client: PolygonClient,
    earnings_service: EarningsService,
    start_date: datetime.date,
    end_date: datetime.date
) -> tuple[int, int]:
    """
    Backfill earnings announcements and historical data.
    """
    try:
        logger.info(f"[{symbol}] Backfilling earnings: {start_date} to {end_date}")
        
        # Fetch earnings from Polygon
        earnings = await polygon_client.fetch_earnings(
            symbol,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        if not earnings:
            logger.info(f"[{symbol}] No earnings found")
            return 0, 0
        
        logger.info(f"[{symbol}] Fetched {len(earnings)} earnings records")
        
        # Insert into database
        inserted, updated = await earnings_service.insert_earnings_batch(earnings)
        logger.info(f"[{symbol}] ✓ Inserted {inserted} earnings records (updated: {updated})")
        return inserted, 0
    
    except Exception as e:
        logger.error(f"[{symbol}] ✗ Error backfilling earnings: {e}")
        return 0, 1


async def backfill_options_iv(
    symbol: str,
    polygon_client: PolygonClient,
    options_service: OptionsIVService,
    end_date: datetime.date
) -> tuple[int, int]:
    """
    Backfill options chain and IV data (current snapshot only, Polygon doesn't provide historical options chains).
    """
    try:
        logger.info(f"[{symbol}] Fetching options IV snapshot: {end_date}")
        
        # Fetch options chain from Polygon
        options_data = await polygon_client.fetch_options_chain(symbol, end_date)
        
        if not options_data:
            logger.info(f"[{symbol}] No options data found")
            return 0, 0
        
        logger.info(f"[{symbol}] Fetched options chain snapshot")
        
        # Insert into database
        inserted = options_service.insert_options_iv_batch(
            symbol,
            options_data.get('options', []),
            options_data.get('current_price'),
            end_date
        )
        logger.info(f"[{symbol}] ✓ Inserted {inserted} options IV records")
        return inserted, 0
    
    except Exception as e:
        logger.error(f"[{symbol}] ✗ Error backfilling options IV: {e}")
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
    parser = argparse.ArgumentParser(description="Comprehensive backfill for all market data")
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
        "--skip-ohlcv",
        action="store_true",
        help="Skip OHLCV backfill"
    )
    parser.add_argument(
        "--skip-news",
        action="store_true",
        help="Skip news/sentiment backfill"
    )
    parser.add_argument(
        "--skip-dividends",
        action="store_true",
        help="Skip dividend backfill"
    )
    parser.add_argument(
        "--skip-splits",
        action="store_true",
        help="Skip stock split backfill"
    )
    parser.add_argument(
        "--skip-earnings",
        action="store_true",
        help="Skip earnings backfill"
    )
    parser.add_argument(
        "--skip-options",
        action="store_true",
        help="Skip options IV backfill"
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
    news_service = NewsService(database_url)
    sentiment_service = SentimentService()
    options_service = OptionsIVService(database_url)
    earnings_service = EarningsService(database_url)
    dividend_service = DividendSplitService(database_url)
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
        'dividends': {'inserted': 0, 'failed': 0},
        'splits': {'inserted': 0, 'failed': 0},
        'earnings': {'inserted': 0, 'failed': 0},
        'options': {'inserted': 0, 'failed': 0},
        'adjusted': {'inserted': 0, 'failed': 0},
    }
    
    # Backfill each symbol
    for i, symbol in enumerate(requested_symbols, 1):
        logger.info(f"\n[{i}/{len(requested_symbols)}] Processing {symbol}")
        logger.info("-" * 80)
        
        try:
            # OHLCV Data
            if not args.skip_ohlcv:
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
            
            # Dividends
            if not args.skip_dividends:
                inserted, failed = await backfill_dividends(
                    symbol, polygon_client, dividend_service,
                    start_dt, end_dt
                )
                stats['dividends']['inserted'] += inserted
                stats['dividends']['failed'] += failed
            
            # Stock Splits
            if not args.skip_splits:
                inserted, failed = await backfill_stock_splits(
                    symbol, polygon_client, dividend_service,
                    start_dt, end_dt
                )
                stats['splits']['inserted'] += inserted
                stats['splits']['failed'] += failed
            
            # Earnings
            if not args.skip_earnings:
                inserted, failed = await backfill_earnings(
                    symbol, polygon_client, earnings_service,
                    start_dt, end_dt
                )
                stats['earnings']['inserted'] += inserted
                stats['earnings']['failed'] += failed
            
            # Options IV
            if not args.skip_options:
                inserted, failed = await backfill_options_iv(
                    symbol, polygon_client, options_service,
                    end_dt
                )
                stats['options']['inserted'] += inserted
                stats['options']['failed'] += failed
            
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
    logger.info("BACKFILL V2 COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total symbols processed: {len(requested_symbols)}")
    logger.info("\nData inserted:")
    logger.info(f"  OHLCV: {stats['ohlcv']['inserted']:,} records")
    logger.info(f"  News/Sentiment: {stats['news']['inserted']:,} articles")
    logger.info(f"  Dividends: {stats['dividends']['inserted']:,} records")
    logger.info(f"  Stock Splits: {stats['splits']['inserted']:,} records")
    logger.info(f"  Earnings: {stats['earnings']['inserted']:,} records")
    logger.info(f"  Options IV: {stats['options']['inserted']:,} records")
    logger.info(f"  Adjusted OHLCV: {stats['adjusted']['inserted']:,} records")
    logger.info("\nData failed:")
    logger.info(f"  OHLCV: {stats['ohlcv']['failed']} symbols")
    logger.info(f"  News/Sentiment: {stats['news']['failed']} symbols")
    logger.info(f"  Dividends: {stats['dividends']['failed']} symbols")
    logger.info(f"  Stock Splits: {stats['splits']['failed']} symbols")
    logger.info(f"  Earnings: {stats['earnings']['failed']} symbols")
    logger.info(f"  Options IV: {stats['options']['failed']} symbols")
    logger.info(f"  Adjusted OHLCV: {stats['adjusted']['failed']} symbols")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
