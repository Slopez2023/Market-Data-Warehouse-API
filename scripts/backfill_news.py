#!/usr/bin/env python3
"""
Backfill historical news and sentiment for all symbols.

Usage:
    python scripts/backfill_news.py [--symbol AAPL] [--resume] [--days 365]

Features:
    - Fetches news from Polygon API
    - Analyzes sentiment using DistilBERT (or TextBlob fallback)
    - Extracts keywords from article text
    - Tracks backfill progress for resumability
    - Respects API rate limits
"""

import asyncio
import logging
import argparse
from datetime import datetime, timedelta
from typing import List, Dict

from src.clients.polygon_client import PolygonClient
from src.services.database_service import DatabaseService
from src.services.sentiment_service import SentimentService
from src.services.news_service import NewsService
from src.config import get_db_url, get_polygon_api_key

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Backfill settings
RATE_LIMIT_DELAY = 1.2  # seconds between requests (50 req/min)


async def fetch_news_for_symbol(
    symbol: str,
    polygon_client: PolygonClient,
    start_date: datetime.date,
    end_date: datetime.date,
    sentiment_service: SentimentService,
    limit_per_symbol: int = 1000
) -> tuple[List[Dict], int]:
    """
    Fetch news and analyze sentiment for a symbol.
    
    Returns:
        (articles_with_sentiment, skipped_count)
    """
    try:
        logger.info(f"Fetching news for {symbol} ({start_date} to {end_date})")
        
        # Fetch news from Polygon
        url = "https://api.polygon.io/v2/reference/news"
        params = {
            "ticker": symbol,
            "from": start_date.strftime('%Y-%m-%d'),
            "to": end_date.strftime('%Y-%m-%d'),
            "limit": limit_per_symbol,
            "apiKey": polygon_client.api_key
        }
        
        # Use aiohttp session for async request
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=30) as response:
                if response.status != 200:
                    logger.error(f"API error {response.status} fetching news for {symbol}")
                    return [], 0
                
                data = await response.json()
                
                if data.get("status") == "ERROR":
                    logger.warning(f"Polygon API error for {symbol}: {data.get('message')}")
                    return [], 0
                
                articles = data.get("results", [])
                logger.info(f"  Fetched {len(articles)} articles for {symbol}")
        
        # Analyze sentiment for each article
        processed = []
        skipped = 0
        
        for article in articles:
            try:
                # Combine title and description for sentiment analysis
                text = f"{article.get('title', '')} {article.get('description', '')}"
                
                # Skip if no meaningful text
                if len(text.strip()) < 20:
                    skipped += 1
                    continue
                
                # Analyze sentiment
                sentiment = sentiment_service.analyze_text(text)
                keywords = sentiment_service.extract_keywords(text)
                
                # Enrich article with sentiment
                processed.append({
                    'title': article.get('title'),
                    'description': article.get('description'),
                    'url': article.get('url'),
                    'image_url': article.get('image_url'),
                    'author': article.get('author'),
                    'source': article.get('source'),
                    'published_at': article.get('published_utc'),
                    'sentiment_score': sentiment['sentiment_score'],
                    'sentiment_label': sentiment['sentiment_label'],
                    'sentiment_confidence': sentiment['confidence'],
                    'keywords': keywords
                })
            
            except Exception as e:
                logger.error(f"Error processing article for {symbol}: {e}")
                skipped += 1
        
        logger.info(f"  Analyzed {len(processed)} articles for {symbol}")
        return processed, skipped
    
    except Exception as e:
        logger.error(f"  Error fetching news for {symbol}: {e}")
        return [], 0


async def backfill_news(
    symbols: List[str] = None,
    resume: bool = False,
    symbol_override: str = None,
    days_back: int = 730
) -> None:
    """
    Main backfill function.
    
    Args:
        symbols: List of symbols to backfill (if None, fetch from DB)
        resume: If True, skip already completed symbols
        symbol_override: Backfill only this symbol
        days_back: How many days of history to backfill
    """
    db_url = get_db_url()
    api_key = get_polygon_api_key()
    
    if not api_key:
        logger.error("POLYGON_API_KEY not set")
        return
    
    polygon_client = PolygonClient(api_key)
    db_service = DatabaseService(db_url)
    news_service = NewsService(db_service)
    sentiment_service = SentimentService(use_transformers=True)
    
    # Calculate date range
    end_date = datetime.utcnow().date()
    start_date = (datetime.utcnow() - timedelta(days=days_back)).date()
    
    # Get symbols list
    if symbol_override:
        symbols = [symbol_override]
        logger.info(f"Backfilling single symbol: {symbol_override}")
    elif not symbols:
        try:
            all_symbols = db_service.get_active_symbols(asset_class='stock')
            symbols = [s['symbol'] for s in all_symbols]
            logger.info(f"Found {len(symbols)} active stock symbols")
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            return
    
    if not symbols:
        logger.warning("No symbols to backfill")
        return
    
    # Filter out completed if resuming
    if resume:
        completed = [
            s for s in symbols
            if news_service.get_backfill_progress(s) and
            news_service.get_backfill_progress(s)['status'] == 'completed'
        ]
        symbols = [s for s in symbols if s not in completed]
        logger.info(f"Resuming: {len(symbols)} symbols remaining (skipped {len(completed)} completed)")
    
    logger.info("=" * 60)
    logger.info(f"Starting news backfill for {len(symbols)} symbols")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Sentiment model: {sentiment_service.sentiment_pipeline is not None and 'transformers' or 'textblob'}")
    logger.info("=" * 60)
    
    total_inserted = 0
    total_skipped = 0
    total_validation_errors = 0
    
    for idx, symbol in enumerate(symbols, 1):
        # Check if already completed
        progress = news_service.get_backfill_progress(symbol)
        if progress and progress['status'] == 'completed':
            logger.info(f"[{idx}/{len(symbols)}] {symbol}: Already completed, skipping")
            continue
        
        # Mark as in progress
        news_service.update_backfill_progress(symbol, 'in_progress')
        
        try:
            # Fetch and analyze sentiment
            articles, skipped = await fetch_news_for_symbol(
                symbol,
                polygon_client,
                start_date,
                end_date,
                sentiment_service
            )
            
            if not articles:
                news_service.update_backfill_progress(symbol, 'completed')
                logger.info(f"[{idx}/{len(symbols)}] {symbol}: No news data")
                continue
            
            # Insert into database
            inserted, db_skipped = news_service.insert_news_batch(symbol, articles)
            
            total_inserted += inserted
            total_skipped += skipped + db_skipped
            total_validation_errors += skipped
            
            # Mark as completed
            news_service.update_backfill_progress(symbol, 'completed')
            logger.info(
                f"[{idx}/{len(symbols)}] {symbol}: ✓ Inserted {inserted}, "
                f"skipped {db_skipped} (validation errors: {skipped})"
            )
        
        except Exception as e:
            logger.error(f"[{idx}/{len(symbols)}] {symbol}: ✗ Error - {e}")
            news_service.update_backfill_progress(
                symbol,
                'failed',
                error_message=str(e)
            )
            total_skipped += 1
        
        # Respect rate limits
        await asyncio.sleep(RATE_LIMIT_DELAY)
    
    logger.info("=" * 60)
    logger.info("News backfill complete!")
    logger.info(f"Total inserted: {total_inserted}")
    logger.info(f"Total skipped: {total_skipped}")
    logger.info(f"Validation errors: {total_validation_errors}")
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Backfill historical news and sentiment from Polygon API"
    )
    parser.add_argument(
        '--symbol',
        type=str,
        help='Backfill only this symbol (e.g., AAPL)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Resume from last checkpoint (skip completed symbols)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=730,
        help='Days of history to backfill (default: 730 = 2 years)'
    )
    
    args = parser.parse_args()
    
    asyncio.run(backfill_news(
        symbols=None,
        resume=args.resume,
        symbol_override=args.symbol,
        days_back=args.days
    ))


if __name__ == "__main__":
    main()
