"""Service for managing news data and sentiment operations"""

import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from sqlalchemy import text

logger = logging.getLogger(__name__)


class NewsService:
    """
    Handles database operations for news articles and sentiment data.
    """
    
    def __init__(self, db_service):
        """
        Initialize with database service reference.
        
        Args:
            db_service: DatabaseService instance
        """
        self.db = db_service
    
    def insert_news_batch(self, symbol: str, articles: List[Dict]) -> tuple[int, int]:
        """
        Insert batch of news articles with sentiment.
        
        Args:
            symbol: Stock ticker
            articles: List of {title, description, url, image_url, author, source, published_at,
                              sentiment_score, sentiment_label, sentiment_confidence, keywords}
        
        Returns:
            (inserted_count, skipped_count)
        """
        if not articles:
            return 0, 0
        
        session = self.db.SessionLocal()
        inserted = 0
        skipped = 0
        
        try:
            for article in articles:
                try:
                    # Convert keywords list to PostgreSQL array format
                    keywords = article.get('keywords', [])
                    if keywords:
                        keywords_str = '{' + ','.join([f'"{k}"' for k in keywords]) + '}'
                    else:
                        keywords_str = None
                    
                    query = text("""
                        INSERT INTO news 
                        (symbol, title, description, url, image_url, author, source, published_at,
                         sentiment_score, sentiment_label, sentiment_confidence, keywords)
                        VALUES (:symbol, :title, :description, :url, :image_url, :author, :source, 
                                :published_at, :sentiment_score, :sentiment_label, :sentiment_confidence, 
                                :keywords)
                        ON CONFLICT (symbol, url) DO NOTHING
                    """)
                    
                    result = session.execute(
                        query,
                        {
                            'symbol': symbol,
                            'title': article.get('title'),
                            'description': article.get('description'),
                            'url': article.get('url'),
                            'image_url': article.get('image_url'),
                            'author': article.get('author'),
                            'source': article.get('source'),
                            'published_at': article.get('published_at'),
                            'sentiment_score': float(article.get('sentiment_score', 0)),
                            'sentiment_label': article.get('sentiment_label'),
                            'sentiment_confidence': float(article.get('sentiment_confidence', 0)),
                            'keywords': keywords_str
                        }
                    )
                    
                    if result.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                
                except Exception as e:
                    logger.error(f"Error inserting article for {symbol}: {e}")
                    skipped += 1
            
            session.commit()
            logger.info(f"News batch for {symbol}: inserted {inserted}, skipped {skipped}")
        
        except Exception as e:
            logger.error(f"Error in news batch insert: {e}")
            session.rollback()
        
        finally:
            session.close()
        
        return inserted, skipped
    
    def get_news_by_symbol(
        self,
        symbol: str,
        days: int = 30,
        limit: int = 50,
        sentiment_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Get recent news for a symbol, optionally filtered by sentiment.
        
        Args:
            symbol: Stock ticker
            days: Look back this many days
            limit: Maximum articles to return
            sentiment_filter: 'bullish', 'bearish', 'neutral' or None (all)
        
        Returns:
            List of news dicts
        """
        session = self.db.SessionLocal()
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Build query
            where_clause = "WHERE symbol = :symbol AND published_at >= :cutoff_date"
            if sentiment_filter:
                where_clause += " AND sentiment_label = :sentiment_label"
            
            query = text(f"""
                SELECT id, title, description, url, image_url, author, source, published_at,
                       sentiment_score, sentiment_label, sentiment_confidence, keywords
                FROM news
                {where_clause}
                ORDER BY published_at DESC
                LIMIT :limit
            """)
            
            params = {
                'symbol': symbol,
                'cutoff_date': cutoff_date,
                'limit': limit
            }
            if sentiment_filter:
                params['sentiment_label'] = sentiment_filter
            
            results = session.execute(query, params).fetchall()
            
            articles = []
            for row in results:
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'description': row[2],
                    'url': row[3],
                    'image_url': row[4],
                    'author': row[5],
                    'source': row[6],
                    'published_at': row[7].isoformat() if row[7] else None,
                    'sentiment_score': float(row[8]) if row[8] else None,
                    'sentiment_label': row[9],
                    'sentiment_confidence': float(row[10]) if row[10] else None,
                    'keywords': row[11] if row[11] else []
                })
            
            return articles
        
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []
        
        finally:
            session.close()
    
    def get_sentiment_aggregate(
        self,
        symbol: str,
        days: int = 30
    ) -> Dict:
        """
        Get aggregated sentiment metrics for a symbol.
        
        Args:
            symbol: Stock ticker
            days: Lookback period
        
        Returns:
            {
                'symbol': str,
                'avg_sentiment_score': float,
                'bullish_count': int,
                'neutral_count': int,
                'bearish_count': int,
                'total_articles': int,
                'sentiment_trend': str ('improving' | 'stable' | 'declining')
            }
        """
        session = self.db.SessionLocal()
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            query = text("""
                SELECT 
                    AVG(sentiment_score) as avg_sentiment,
                    COUNT(CASE WHEN sentiment_label = 'bullish' THEN 1 END) as bullish_count,
                    COUNT(CASE WHEN sentiment_label = 'neutral' THEN 1 END) as neutral_count,
                    COUNT(CASE WHEN sentiment_label = 'bearish' THEN 1 END) as bearish_count,
                    COUNT(*) as total_count
                FROM news
                WHERE symbol = :symbol AND published_at >= :cutoff_date
            """)
            
            result = session.execute(
                query,
                {'symbol': symbol, 'cutoff_date': cutoff_date}
            ).first()
            
            if not result or result[4] == 0:  # No articles
                return {
                    'symbol': symbol,
                    'avg_sentiment_score': 0.0,
                    'bullish_count': 0,
                    'neutral_count': 0,
                    'bearish_count': 0,
                    'total_articles': 0,
                    'sentiment_trend': 'neutral'
                }
            
            avg_sentiment = float(result[0]) if result[0] else 0.0
            bullish = int(result[1]) if result[1] else 0
            neutral = int(result[2]) if result[2] else 0
            bearish = int(result[3]) if result[3] else 0
            total = int(result[4]) if result[4] else 0
            
            # Determine trend (compare first half vs second half of period)
            mid_date = datetime.utcnow() - timedelta(days=days//2)
            
            query_first = text("""
                SELECT AVG(sentiment_score)
                FROM news
                WHERE symbol = :symbol 
                  AND published_at >= :cutoff_date 
                  AND published_at < :mid_date
            """)
            
            query_second = text("""
                SELECT AVG(sentiment_score)
                FROM news
                WHERE symbol = :symbol 
                  AND published_at >= :mid_date 
                  AND published_at <= :now
            """)
            
            first_half = session.execute(
                query_first,
                {'symbol': symbol, 'cutoff_date': cutoff_date, 'mid_date': mid_date}
            ).first()
            
            second_half = session.execute(
                query_second,
                {'symbol': symbol, 'mid_date': mid_date, 'now': datetime.utcnow()}
            ).first()
            
            sentiment_trend = 'stable'
            if first_half[0] and second_half[0]:
                diff = float(second_half[0]) - float(first_half[0])
                if diff > 0.1:
                    sentiment_trend = 'improving'
                elif diff < -0.1:
                    sentiment_trend = 'declining'
            
            return {
                'symbol': symbol,
                'avg_sentiment_score': round(avg_sentiment, 3),
                'bullish_count': bullish,
                'neutral_count': neutral,
                'bearish_count': bearish,
                'total_articles': total,
                'sentiment_trend': sentiment_trend
            }
        
        except Exception as e:
            logger.error(f"Error fetching sentiment aggregate: {e}")
            return {
                'symbol': symbol,
                'avg_sentiment_score': 0.0,
                'bullish_count': 0,
                'neutral_count': 0,
                'bearish_count': 0,
                'total_articles': 0,
                'sentiment_trend': 'neutral'
            }
        
        finally:
            session.close()
    
    def update_backfill_progress(
        self,
        symbol: str,
        status: str,
        last_processed_date: str = None,
        error_message: str = None
    ) -> bool:
        """
        Update news backfill progress.
        
        Args:
            symbol: Stock ticker
            status: 'pending', 'in_progress', 'completed', 'failed'
            last_processed_date: Date up to which backfill was processed
            error_message: Error details if status is 'failed'
        
        Returns:
            True if successful
        """
        session = self.db.SessionLocal()
        
        try:
            query = text("""
                INSERT INTO backfill_progress 
                (backfill_type, symbol, status, last_processed_date, error_message, attempted_at)
                VALUES (:backfill_type, :symbol, :status, :last_processed_date, :error_message, :now)
                ON CONFLICT (backfill_type, symbol) DO UPDATE SET
                    status = :status,
                    last_processed_date = COALESCE(:last_processed_date, last_processed_date),
                    error_message = :error_message,
                    attempted_at = :now,
                    completed_at = CASE WHEN :status = 'completed' THEN :now ELSE completed_at END
            """)
            
            session.execute(
                query,
                {
                    'backfill_type': 'news',
                    'symbol': symbol,
                    'status': status,
                    'last_processed_date': last_processed_date,
                    'error_message': error_message,
                    'now': datetime.utcnow()
                }
            )
            
            session.commit()
            return True
        
        except Exception as e:
            logger.error(f"Error updating news backfill progress: {e}")
            session.rollback()
            return False
        
        finally:
            session.close()
    
    def get_backfill_progress(self, symbol: str) -> Optional[Dict]:
        """Get news backfill progress for a symbol."""
        session = self.db.SessionLocal()
        
        try:
            query = text("""
                SELECT status, last_processed_date, error_message, attempted_at, completed_at
                FROM backfill_progress
                WHERE backfill_type = 'news' AND symbol = :symbol
            """)
            
            result = session.execute(
                query,
                {'symbol': symbol}
            ).first()
            
            if result:
                return {
                    'status': result[0],
                    'last_processed_date': result[1],
                    'error_message': result[2],
                    'attempted_at': result[3],
                    'completed_at': result[4]
                }
            
            return None
        
        except Exception as e:
            logger.error(f"Error fetching news backfill progress: {e}")
            return None
        
        finally:
            session.close()
