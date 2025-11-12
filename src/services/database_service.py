"""Database service for market data operations"""

import logging
from typing import List, Optional, Dict
from datetime import datetime
import time
from sqlalchemy import create_engine, text, bindparam
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# Simple cache for metrics (5-minute TTL)
_metrics_cache = {"data": None, "timestamp": 0}
_CACHE_TTL = 300  # seconds


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
            poolclass=QueuePool,
            pool_size=10,  # Number of connections to keep in pool
            max_overflow=20,  # Additional connections if pool exhausted
            pool_recycle=3600,  # Recycle connections every hour (prevents stale connections)
            pool_pre_ping=True,  # Test connections before using them
            echo=False
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
    
    def insert_ohlcv_batch(
        self,
        symbol: str,
        candles: List[Dict],
        metadata: List[Dict],
        timeframe: str = '1d'
    ) -> int:
        """
        Insert batch of OHLCV candles with validation metadata.
        
        Args:
            symbol: Stock ticker
            candles: List of {time, o, h, l, c, v}
            metadata: List of {quality_score, validated, validation_notes, gap_detected, volume_anomaly}
            timeframe: Candle timeframe (default: '1d')
        
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
                    'fetched_at': datetime.utcnow(),
                    'timeframe': timeframe
                })
            
            # Execute batch insert
            # Using ON CONFLICT DO UPDATE to handle duplicates (upsert)
            insert_stmt = text("""
                INSERT INTO market_data 
                (time, symbol, open, high, low, close, volume, validated, quality_score, 
                 validation_notes, gap_detected, volume_anomaly, source, fetched_at, timeframe)
                VALUES 
                (:time, :symbol, :open, :high, :low, :close, :volume, :validated, 
                 :quality_score, :validation_notes, :gap_detected, :volume_anomaly, 
                 :source, :fetched_at, :timeframe)
                ON CONFLICT (symbol, time, timeframe) DO UPDATE SET
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
        timeframe: str = '1d',
        validated_only: bool = True,
        min_quality: float = 0.85
    ) -> List[Dict]:
        """
        Fetch historical OHLCV data for a symbol.
        
        Args:
            symbol: Stock ticker
            start: Start date YYYY-MM-DD
            end: End date YYYY-MM-DD
            timeframe: Candle timeframe (default: '1d')
            validated_only: Only return validated candles
            min_quality: Minimum quality score (0.0-1.0)
        
        Returns:
            List of {time, symbol, open, high, low, close, volume, quality_score, ...}
        """
        session = self.SessionLocal()
        
        try:
            # Build WHERE clause conditions
            conditions = [
                "symbol = %s",
                "timeframe = %s",
                "time >= %s::timestamp",
                "time < %s::timestamp + INTERVAL '1 day'"
            ]
            
            query_params = [symbol, timeframe, start, end]
            
            if validated_only:
                conditions.append("validated = TRUE")
            
            if min_quality > 0:
                conditions.append(f"quality_score >= {min_quality}")
            
            where_clause = " AND ".join(conditions)
            
            sql = f"""
                SELECT 
                    time, symbol, timeframe, open, high, low, close, volume,
                    source, validated, quality_score, validation_notes,
                    gap_detected, volume_anomaly, fetched_at
                FROM market_data
                WHERE {where_clause}
                ORDER BY time ASC
            """
            
            # Use raw SQL execute with psycopg2 style parameters
            conn = session.connection().connection
            cursor = conn.cursor()
            cursor.execute(sql, query_params)
            rows = cursor.fetchall()
            cursor.close()
            
            # Convert to list of dicts
            data = []
            for row in rows:
                data.append({
                    'time': row[0].isoformat() if row[0] else None,
                    'symbol': row[1],
                    'timeframe': row[2],
                    'open': float(row[3]),
                    'high': float(row[4]),
                    'low': float(row[5]),
                    'close': float(row[6]),
                    'volume': row[7],
                    'source': row[8],
                    'validated': row[9],
                    'quality_score': float(row[10]),
                    'validation_notes': row[11],
                    'gap_detected': row[12],
                    'volume_anomaly': row[13],
                    'fetched_at': row[14].isoformat() if row[14] else None
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
    
    def get_symbol_stats(self, symbol: str) -> Dict:
        """
        Get detailed statistics for a specific symbol.
        
        Args:
            symbol: Stock ticker
        
        Returns:
            Dict with record_count, date_range, validation_rate, gaps_detected
        """
        session = self.SessionLocal()
        
        try:
            stats_query = text("""
                SELECT 
                    COUNT(*) as record_count,
                    MIN(time) as start_date,
                    MAX(time) as end_date,
                    COUNT(*) FILTER (WHERE validated = TRUE) as validated_count,
                    COUNT(*) FILTER (WHERE gap_detected = TRUE) as gaps_count
                FROM market_data
                WHERE symbol = :symbol
            """)
            
            result = session.execute(stats_query, {"symbol": symbol}).first()
            
            if result:
                record_count, start_date, end_date, validated_count, gaps_count = result
                validation_rate = (validated_count / record_count) if record_count > 0 else 0
                
                return {
                    "record_count": record_count or 0,
                    "date_range": {
                        "start": start_date.isoformat() if start_date else None,
                        "end": end_date.isoformat() if end_date else None
                    },
                    "validation_rate": round(validation_rate, 2),
                    "gaps_detected": gaps_count or 0
                }
            else:
                return {
                    "record_count": 0,
                    "date_range": {"start": None, "end": None},
                    "validation_rate": 0,
                    "gaps_detected": 0
                }
        
        except Exception as e:
            logger.error(f"Error getting stats for {symbol}: {e}")
            return {}
        
        finally:
            session.close()
    
    def get_status_metrics(self) -> Dict:
        """Get overall system metrics for status endpoint (cached, 5-min TTL)"""
        global _metrics_cache
        
        # Check cache
        current_time = time.time()
        if (_metrics_cache["data"] is not None and 
            current_time - _metrics_cache["timestamp"] < _CACHE_TTL):
            logger.debug("Returning cached metrics")
            return _metrics_cache["data"]
        
        session = self.SessionLocal()
        
        try:
            # Single optimized query for all metrics
            metrics_query = text("""
                SELECT 
                    COUNT(DISTINCT symbol) as symbols,
                    MAX(time) as latest_time,
                    COUNT(*) as total_records,
                    COUNT(*) FILTER (WHERE validated = TRUE) as validated_records,
                    COUNT(*) FILTER (WHERE gap_detected = TRUE) as gap_records
                FROM market_data
            """)
            result = session.execute(metrics_query).first()
            
            if result:
                symbol_count, latest_date, total_count, valid_count, gap_count = result
                validation_rate = (valid_count / total_count * 100) if total_count > 0 else 0
            else:
                symbol_count, latest_date, total_count, valid_count, gap_count = 0, None, 0, 0, 0
                validation_rate = 0
            
            metrics_data = {
                "symbols_available": symbol_count or 0,
                "latest_data": latest_date.isoformat() if latest_date else None,
                "total_records": total_count or 0,
                "validated_records": valid_count or 0,
                "validation_rate_pct": round(validation_rate, 2),
                "records_with_gaps_flagged": gap_count or 0
            }
            
            # Update cache
            _metrics_cache["data"] = metrics_data
            _metrics_cache["timestamp"] = current_time
            
            return metrics_data
        
        except Exception as e:
            logger.error(f"Error getting status metrics: {e}")
            return {}
        
        finally:
            session.close()
    
    def get_all_symbols_detailed(self) -> List[Dict]:
        """
        Get detailed statistics for all symbols in the database.
        
        Returns:
            List of dicts with: symbol, records, validation_rate, latest_data, data_age_hours, timeframes
        """
        session = self.SessionLocal()
        
        try:
            # Query for per-symbol statistics from market_data
            symbols_query = text("""
                SELECT 
                    m.symbol,
                    COUNT(*) as records,
                    COUNT(*) FILTER (WHERE m.validated = TRUE)::float / COUNT(*) * 100 as validation_rate,
                    MAX(m.time) as latest_data,
                    EXTRACT(EPOCH FROM (NOW() - MAX(m.time))) / 3600 as data_age_hours,
                    COALESCE(ts.timeframes, ARRAY[]::text[]) as timeframes
                FROM market_data m
                LEFT JOIN tracked_symbols ts ON m.symbol = ts.symbol
                GROUP BY m.symbol, ts.timeframes
                ORDER BY m.symbol ASC
            """)
            
            results = session.execute(symbols_query).fetchall()
            
            symbols_data = []
            for row in results:
                symbol, records, validation_rate, latest_data, data_age_hours, timeframes = row
                symbols_data.append({
                    "symbol": symbol,
                    "records": int(records) if records else 0,
                    "validation_rate": float(validation_rate) if validation_rate else 0.0,
                    "latest_data": latest_data.isoformat() if latest_data else None,
                    "data_age_hours": float(data_age_hours) if data_age_hours else 0.0,
                    "timeframes": list(timeframes) if timeframes else []
                })
            
            logger.info(f"Retrieved detailed stats for {len(symbols_data)} symbols")
            return symbols_data
        
        except Exception as e:
            logger.error(f"Error getting detailed symbol stats: {e}")
            return []
        
        finally:
            session.close()
