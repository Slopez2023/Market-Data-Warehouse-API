"""Database service for market data operations"""

import logging
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Handles all database operations:
    - Insert OHLCV data
    - Query historical data
    - Update validation metadata
    - Track backfill history
    - Monitor symbol status
    """
    
    def __init__(self, database_url: str):
        """
        Initialize database connection.
        
        Args:
            database_url: PostgreSQL connection string
                         (e.g., postgresql://user:pass@localhost:5432/market_data)
        """
        self.engine = create_engine(
            database_url,
            poolclass=NullPool,  # Disable connection pooling for better compatibility
            echo=False
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
    
    def insert_ohlcv_batch(
        self,
        symbol: str,
        candles: List[Dict],
        metadata: List[Dict]
    ) -> int:
        """
        Insert batch of OHLCV candles with validation metadata.
        
        Args:
            symbol: Stock ticker
            candles: List of {time, o, h, l, c, v}
            metadata: List of {quality_score, validated, validation_notes, gap_detected, volume_anomaly}
        
        Returns:
            Number of rows inserted
        """
        if not candles or not metadata:
            return 0
        
        if len(candles) != len(metadata):
            logger.error(f"Mismatch: {len(candles)} candles but {len(metadata)} metadata")
            return 0
        
        session = self.SessionLocal()
        inserted = 0
        
        try:
            # Prepare insert values
            values = []
            for candle, meta in zip(candles, metadata):
                # Convert Polygon timestamp (milliseconds) to seconds
                timestamp_ms = candle.get('t', 0)
                timestamp = datetime.utcfromtimestamp(timestamp_ms / 1000)
                
                values.append({
                    'time': timestamp,
                    'symbol': symbol,
                    'open': candle.get('o', 0),
                    'high': candle.get('h', 0),
                    'low': candle.get('l', 0),
                    'close': candle.get('c', 0),
                    'volume': int(candle.get('v', 0)),
                    'validated': meta['validated'],
                    'quality_score': meta['quality_score'],
                    'validation_notes': meta['validation_notes'],
                    'gap_detected': meta['gap_detected'],
                    'volume_anomaly': meta['volume_anomaly'],
                    'source': 'polygon',
                    'fetched_at': datetime.utcnow()
                })
            
            # Execute batch insert
            # Using ON CONFLICT DO UPDATE to handle duplicates (upsert)
            insert_stmt = text("""
                INSERT INTO market_data 
                (time, symbol, open, high, low, close, volume, validated, quality_score, 
                 validation_notes, gap_detected, volume_anomaly, source, fetched_at)
                VALUES 
                (:time, :symbol, :open, :high, :low, :close, :volume, :validated, 
                 :quality_score, :validation_notes, :gap_detected, :volume_anomaly, 
                 :source, :fetched_at)
                ON CONFLICT (symbol, time) DO UPDATE SET
                    validated = EXCLUDED.validated,
                    quality_score = EXCLUDED.quality_score,
                    validation_notes = EXCLUDED.validation_notes,
                    gap_detected = EXCLUDED.gap_detected,
                    volume_anomaly = EXCLUDED.volume_anomaly,
                    fetched_at = EXCLUDED.fetched_at
            """)
            
            for value in values:
                session.execute(insert_stmt, value)
            
            session.commit()
            inserted = len(values)
            logger.info(f"Inserted {inserted} records for {symbol}")
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error inserting OHLCV batch for {symbol}: {e}")
        
        finally:
            session.close()
        
        return inserted
    
    def get_historical_data(
        self,
        symbol: str,
        start: str,
        end: str,
        validated_only: bool = True,
        min_quality: float = 0.85
    ) -> List[Dict]:
        """
        Fetch historical OHLCV data for a symbol.
        
        Args:
            symbol: Stock ticker
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
            validated_only: Only return validated candles
            min_quality: Minimum quality score (0.0-1.0)
        
        Returns:
            List of {time, symbol, open, high, low, close, volume, quality_score, ...}
        """
        session = self.SessionLocal()
        
        try:
            query = text("""
                SELECT 
                    time, symbol, open, high, low, close, volume,
                    source, validated, quality_score, validation_notes,
                    gap_detected, volume_anomaly, fetched_at
                FROM market_data
                WHERE symbol = :symbol
                  AND time >= :start_date::timestamp
                  AND time <= :end_date::timestamp
            """)
            
            params = {
                'symbol': symbol,
                'start_date': start,
                'end_date': end
            }
            
            # Add optional filters
            if validated_only:
                query = text(query.text + " AND validated = TRUE")
            
            if min_quality > 0:
                query = text(query.text + f" AND quality_score >= {min_quality}")
            
            query = text(query.text + " ORDER BY time ASC")
            
            result = session.execute(query, params)
            rows = result.fetchall()
            
            # Convert to list of dicts
            data = []
            for row in rows:
                data.append({
                    'time': row[0].isoformat() if row[0] else None,
                    'symbol': row[1],
                    'open': float(row[2]),
                    'high': float(row[3]),
                    'low': float(row[4]),
                    'close': float(row[5]),
                    'volume': row[6],
                    'source': row[7],
                    'validated': row[8],
                    'quality_score': float(row[9]),
                    'validation_notes': row[10],
                    'gap_detected': row[11],
                    'volume_anomaly': row[12],
                    'fetched_at': row[13].isoformat() if row[13] else None
                })
            
            logger.info(f"Retrieved {len(data)} records for {symbol} ({start} to {end})")
            return data
        
        except Exception as e:
            logger.error(f"Error querying historical data for {symbol}: {e}")
            return []
        
        finally:
            session.close()
    
    def log_validation(
        self,
        symbol: str,
        check_name: str,
        passed: bool,
        error_message: str = None,
        quality_score: float = None
    ) -> None:
        """Log validation check results to audit table"""
        session = self.SessionLocal()
        
        try:
            insert_stmt = text("""
                INSERT INTO validation_log 
                (symbol, check_name, passed, error_message, quality_score)
                VALUES (:symbol, :check_name, :passed, :error_message, :quality_score)
            """)
            
            session.execute(insert_stmt, {
                'symbol': symbol,
                'check_name': check_name,
                'passed': passed,
                'error_message': error_message,
                'quality_score': quality_score
            })
            
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error logging validation: {e}")
        finally:
            session.close()
    
    def log_backfill(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        records_imported: int,
        success: bool,
        error_details: str = None
    ) -> None:
        """Log backfill job results"""
        session = self.SessionLocal()
        
        try:
            insert_stmt = text("""
                INSERT INTO backfill_history
                (symbol, start_date, end_date, records_imported, success, error_details)
                VALUES (:symbol, :start_date, :end_date, :records_imported, :success, :error_details)
            """)
            
            session.execute(insert_stmt, {
                'symbol': symbol,
                'start_date': start_date,
                'end_date': end_date,
                'records_imported': records_imported,
                'success': success,
                'error_details': error_details
            })
            
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error logging backfill: {e}")
        finally:
            session.close()
    
    def get_status_metrics(self) -> Dict:
        """Get overall system metrics for status endpoint"""
        session = self.SessionLocal()
        
        try:
            # Count symbols
            symbols_query = text("SELECT COUNT(DISTINCT symbol) FROM market_data")
            symbol_count = session.execute(symbols_query).scalar() or 0
            
            # Latest date in DB
            latest_query = text("SELECT MAX(time) FROM market_data")
            latest_date = session.execute(latest_query).scalar()
            
            # Validation metrics
            validation_query = text("""
                SELECT 
                    COUNT(*) FILTER (WHERE validated = TRUE) as valid_count,
                    COUNT(*) as total_count
                FROM market_data
            """)
            result = session.execute(validation_query).first()
            valid_count, total_count = result if result else (0, 0)
            validation_rate = (valid_count / total_count * 100) if total_count > 0 else 0
            
            # Gap detection
            gap_query = text("SELECT COUNT(*) FROM market_data WHERE gap_detected = TRUE")
            gap_count = session.execute(gap_query).scalar() or 0
            
            return {
                "symbols_available": symbol_count,
                "latest_data": latest_date.isoformat() if latest_date else None,
                "total_records": total_count,
                "validated_records": valid_count,
                "validation_rate_pct": round(validation_rate, 2),
                "records_with_gaps_flagged": gap_count
            }
        
        except Exception as e:
            logger.error(f"Error getting status metrics: {e}")
            return {}
        
        finally:
            session.close()
