"""Service for managing dividend and stock split data operations"""

import logging
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DividendSplitService:
    """
    Handles database operations for dividends and stock splits.
    Provides resumable backfill tracking and batch insert operations.
    """
    
    def __init__(self, db_service):
        """
        Initialize with database service reference.
        
        Args:
            db_service: DatabaseService instance
        """
        self.db = db_service
    
    def insert_dividends_batch(self, symbol: str, dividends: List[Dict]) -> tuple[int, int]:
        """
        Insert batch of dividend records.
        
        Args:
            symbol: Stock ticker
            dividends: List of {ex_dividend_date, record_date, pay_date, cash_amount, dividend_type, currency}
        
        Returns:
            (inserted_count, skipped_count)
        """
        if not dividends:
            return 0, 0
        
        session = self.db.SessionLocal()
        inserted = 0
        skipped = 0
        
        try:
            for div in dividends:
                try:
                    # Use raw SQL for upsert (on conflict do nothing)
                    query = text("""
                        INSERT INTO dividends 
                        (symbol, ex_date, record_date, pay_date, dividend_amount, dividend_type, currency)
                        VALUES (:symbol, :ex_date, :record_date, :pay_date, :amount, :div_type, :currency)
                        ON CONFLICT (symbol, ex_date) DO NOTHING
                    """)
                    
                    result = session.execute(
                        query,
                        {
                            'symbol': symbol,
                            'ex_date': div.get('ex_dividend_date'),
                            'record_date': div.get('record_date'),
                            'pay_date': div.get('pay_date'),
                            'amount': float(div.get('cash_amount', 0)),
                            'div_type': div.get('dividend_type', 'regular'),
                            'currency': div.get('currency', 'USD')
                        }
                    )
                    
                    # Check if row was actually inserted
                    if result.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                
                except Exception as e:
                    logger.error(f"Error inserting dividend for {symbol}: {e}")
                    skipped += 1
            
            session.commit()
            logger.info(f"Dividend batch for {symbol}: inserted {inserted}, skipped {skipped}")
        
        except Exception as e:
            logger.error(f"Error in dividend batch insert: {e}")
            session.rollback()
        
        finally:
            session.close()
        
        return inserted, skipped
    
    def insert_splits_batch(self, symbol: str, splits: List[Dict]) -> tuple[int, int]:
        """
        Insert batch of stock split records.
        
        Args:
            symbol: Stock ticker
            splits: List of {execution_date, split_from, split_to}
        
        Returns:
            (inserted_count, skipped_count)
        """
        if not splits:
            return 0, 0
        
        session = self.db.SessionLocal()
        inserted = 0
        skipped = 0
        
        try:
            for split in splits:
                try:
                    # Calculate split ratio if not provided
                    split_from = int(split.get('split_from', 1))
                    split_to = int(split.get('split_to', 1))
                    ratio = split_to / split_from if split_from > 0 else 1.0
                    
                    query = text("""
                        INSERT INTO stock_splits 
                        (symbol, execution_date, split_from, split_to, split_ratio)
                        VALUES (:symbol, :execution_date, :split_from, :split_to, :ratio)
                        ON CONFLICT (symbol, execution_date) DO NOTHING
                    """)
                    
                    result = session.execute(
                        query,
                        {
                            'symbol': symbol,
                            'execution_date': split.get('execution_date'),
                            'split_from': split_from,
                            'split_to': split_to,
                            'ratio': ratio
                        }
                    )
                    
                    if result.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                
                except Exception as e:
                    logger.error(f"Error inserting split for {symbol}: {e}")
                    skipped += 1
            
            session.commit()
            logger.info(f"Split batch for {symbol}: inserted {inserted}, skipped {skipped}")
        
        except Exception as e:
            logger.error(f"Error in split batch insert: {e}")
            session.rollback()
        
        finally:
            session.close()
        
        return inserted, skipped
    
    def update_backfill_progress(
        self,
        backfill_type: str,
        symbol: str,
        status: str,
        last_processed_date: str = None,
        error_message: str = None
    ) -> bool:
        """
        Update or create backfill progress record for resumability.
        
        Args:
            backfill_type: 'dividends' or 'splits'
            symbol: Stock ticker
            status: 'pending', 'in_progress', 'completed', 'failed'
            last_processed_date: Date up to which backfill was processed
            error_message: Error details if status is 'failed'
        
        Returns:
            True if successful
        """
        session = self.db.SessionLocal()
        
        try:
            # Upsert backfill progress
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
                    'backfill_type': backfill_type,
                    'symbol': symbol,
                    'status': status,
                    'last_processed_date': last_processed_date,
                    'error_message': error_message,
                    'now': datetime.utcnow()
                }
            )
            
            session.commit()
            logger.info(f"Updated progress for {backfill_type}/{symbol}: {status}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating backfill progress: {e}")
            session.rollback()
            return False
        
        finally:
            session.close()
    
    def get_backfill_progress(self, backfill_type: str, symbol: str) -> Optional[Dict]:
        """
        Get backfill progress for a symbol.
        
        Returns:
            Progress dict or None if not found
        """
        session = self.db.SessionLocal()
        
        try:
            query = text("""
                SELECT status, last_processed_date, error_message, attempted_at, completed_at
                FROM backfill_progress
                WHERE backfill_type = :backfill_type AND symbol = :symbol
            """)
            
            result = session.execute(
                query,
                {'backfill_type': backfill_type, 'symbol': symbol}
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
            logger.error(f"Error fetching backfill progress: {e}")
            return None
        
        finally:
            session.close()
    
    def get_completed_symbols(self, backfill_type: str) -> List[str]:
        """
        Get all symbols that have been successfully backfilled.
        
        Returns:
            List of symbols with status='completed'
        """
        session = self.db.SessionLocal()
        
        try:
            query = text("""
                SELECT DISTINCT symbol
                FROM backfill_progress
                WHERE backfill_type = :backfill_type AND status = 'completed'
                ORDER BY completed_at DESC
            """)
            
            results = session.execute(
                query,
                {'backfill_type': backfill_type}
            ).fetchall()
            
            return [row[0] for row in results]
        
        except Exception as e:
            logger.error(f"Error fetching completed symbols: {e}")
            return []
        
        finally:
            session.close()
    
    def get_pending_symbols(self, backfill_type: str) -> List[str]:
        """
        Get symbols pending backfill.
        
        Returns:
            List of symbols with status='pending'
        """
        session = self.db.SessionLocal()
        
        try:
            query = text("""
                SELECT DISTINCT symbol
                FROM backfill_progress
                WHERE backfill_type = :backfill_type AND status = 'pending'
                ORDER BY attempted_at ASC
            """)
            
            results = session.execute(
                query,
                {'backfill_type': backfill_type}
            ).fetchall()
            
            return [row[0] for row in results]
        
        except Exception as e:
            logger.error(f"Error fetching pending symbols: {e}")
            return []
        
        finally:
            session.close()
    
    def insert_adjusted_ohlcv_batch(self, symbol: str, candles: List[Dict], timeframe: str = '1d') -> int:
        """
        Insert batch of adjusted OHLCV records.
        
        Args:
            symbol: Stock ticker
            candles: List of {t, o, h, l, c, v} with adjusted prices from Polygon
            timeframe: Candle timeframe (default: '1d')
        
        Returns:
            Number of rows inserted
        """
        if not candles:
            return 0
        
        session = self.db.SessionLocal()
        inserted = 0
        
        try:
            for candle in candles:
                try:
                    # Convert Polygon timestamp (milliseconds) to seconds
                    from datetime import datetime as dt
                    timestamp_ms = candle.get('t', 0)
                    timestamp = dt.utcfromtimestamp(timestamp_ms / 1000)
                    
                    query = text("""
                        INSERT INTO ohlcv_adjusted 
                        (time, symbol, open, high, low, close, volume, timeframe, source, fetched_at)
                        VALUES (:time, :symbol, :open, :high, :low, :close, :volume, :timeframe, :source, :fetched_at)
                        ON CONFLICT (symbol, time, timeframe) DO UPDATE SET
                            open = EXCLUDED.open,
                            high = EXCLUDED.high,
                            low = EXCLUDED.low,
                            close = EXCLUDED.close,
                            volume = EXCLUDED.volume,
                            fetched_at = EXCLUDED.fetched_at
                    """)
                    
                    result = session.execute(
                        query,
                        {
                            'time': timestamp,
                            'symbol': symbol,
                            'open': float(candle.get('o', 0)),
                            'high': float(candle.get('h', 0)),
                            'low': float(candle.get('l', 0)),
                            'close': float(candle.get('c', 0)),
                            'volume': int(candle.get('v', 0)),
                            'timeframe': timeframe,
                            'source': 'polygon',
                            'fetched_at': datetime.utcnow()
                        }
                    )
                    
                    if result.rowcount > 0:
                        inserted += 1
                
                except Exception as e:
                    logger.error(f"Error inserting adjusted OHLCV for {symbol}: {e}")
            
            session.commit()
            logger.info(f"Adjusted OHLCV batch for {symbol}: inserted {inserted}")
        
        except Exception as e:
            logger.error(f"Error in adjusted OHLCV batch insert: {e}")
            session.rollback()
        
        finally:
            session.close()
        
        return inserted
