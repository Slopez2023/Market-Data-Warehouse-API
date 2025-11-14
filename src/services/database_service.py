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
    
    def upsert_market_data_v2(self, data: Dict) -> Dict:
        """
        Insert or update enriched market data in market_data_v2 table.
        Idempotent operation - safe to retry without creating duplicates.
        
        Args:
            data: Dictionary with enriched data including:
                - symbol, asset_class, timeframe, timestamp (required)
                - open, high, low, close, volume
                - computed features (optional)
                - quality_score, is_validated, validation_notes, etc.
        
        Returns:
            Dict with {'inserted': bool, 'updated': bool, 'record_id': int}
        """
        session = self.SessionLocal()
        
        try:
            # Build INSERT ON CONFLICT DO UPDATE statement dynamically
            # Get all columns from data dict
            columns = sorted([k for k in data.keys() if data[k] is not None])
            placeholders = [f":{col}" for col in columns]
            
            # Build update clause for existing records
            update_clause = ", ".join([
                f"{col} = EXCLUDED.{col}" 
                for col in columns 
                if col not in ['symbol', 'asset_class', 'timeframe', 'timestamp', 'revision']
            ])
            
            upsert_stmt = text(f"""
                INSERT INTO market_data_v2 ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                ON CONFLICT (symbol, asset_class, timeframe, timestamp, revision) 
                DO UPDATE SET
                    {update_clause},
                    updated_at = NOW()
                RETURNING id, (xmax::text::int = 0) as inserted
            """)
            
            result = session.execute(upsert_stmt, data).first()
            session.commit()
            
            if result:
                record_id, inserted = result
                return {
                    'inserted': inserted,
                    'updated': not inserted,
                    'record_id': record_id
                }
            
            return {'inserted': False, 'updated': False, 'record_id': None}
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error upserting market_data_v2: {e}")
            return {'inserted': False, 'updated': False, 'record_id': None}
        
        finally:
            session.close()
    
    def upsert_enriched_batch(self, records: List[Dict]) -> Dict:
        """
        Batch UPSERT multiple enriched records.
        Uses COPY for high-performance bulk operations.
        
        Args:
            records: List of enriched data dictionaries
        
        Returns:
            Dict with {'inserted': int, 'updated': int, 'total': int}
        """
        if not records:
            return {'inserted': 0, 'updated': 0, 'total': 0}
        
        session = self.SessionLocal()
        inserted = 0
        updated = 0
        
        try:
            for record in records:
                result = self.upsert_market_data_v2(record)
                if result['inserted']:
                    inserted += 1
                elif result['updated']:
                    updated += 1
            
            logger.info(f"Batch upsert: {inserted} inserted, {updated} updated out of {len(records)}")
            return {'inserted': inserted, 'updated': updated, 'total': len(records)}
        
        except Exception as e:
            logger.error(f"Error in batch upsert: {e}")
            return {'inserted': inserted, 'updated': updated, 'total': len(records)}
        
        finally:
            session.close()
    
    def update_backfill_state(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        job_id: str,
        status: str,
        last_successful_date: str = None,
        error_message: str = None
    ) -> None:
        """
        Update backfill state tracking.
        
        Args:
            symbol: Asset symbol
            asset_class: Asset class
            timeframe: Timeframe
            job_id: Backfill job ID
            status: Status (pending, in_progress, completed, failed)
            last_successful_date: Last successfully enriched date
            error_message: Error details if failed
        """
        session = self.SessionLocal()
        
        try:
            # Check if record exists
            existing = session.execute(
                text("""
                    SELECT id FROM backfill_state 
                    WHERE symbol = :symbol 
                    AND asset_class = :asset_class 
                    AND timeframe = :timeframe 
                    AND backfill_job_id = :job_id
                """),
                {
                    'symbol': symbol,
                    'asset_class': asset_class,
                    'timeframe': timeframe,
                    'job_id': job_id
                }
            ).first()
            
            if existing:
                # Update existing record
                update_stmt = text("""
                    UPDATE backfill_state 
                    SET status = :status,
                        last_successful_date = COALESCE(:last_date, last_successful_date),
                        error_message = :error,
                        retry_count = CASE WHEN :status = 'failed' THEN retry_count + 1 ELSE retry_count END,
                        updated_at = NOW()
                    WHERE id = :id
                """)
                
                session.execute(update_stmt, {
                    'status': status,
                    'last_date': last_successful_date,
                    'error': error_message,
                    'id': existing[0]
                })
            else:
                # Insert new record
                insert_stmt = text("""
                    INSERT INTO backfill_state 
                    (symbol, asset_class, timeframe, backfill_job_id, status, 
                     start_date, end_date, last_successful_date, error_message, created_at, updated_at)
                    VALUES (:symbol, :asset_class, :timeframe, :job_id, :status, 
                            CURRENT_DATE, CURRENT_DATE, :last_date, :error, NOW(), NOW())
                """)
                
                session.execute(insert_stmt, {
                    'symbol': symbol,
                    'asset_class': asset_class,
                    'timeframe': timeframe,
                    'job_id': job_id,
                    'status': status,
                    'last_date': last_successful_date,
                    'error': error_message
                })
            
            session.commit()
            logger.info(f"Updated backfill state: {symbol} {timeframe} -> {status}")
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating backfill state: {e}")
        
        finally:
            session.close()
    
    def log_enrichment_fetch(
        self,
        symbol: str,
        asset_class: str,
        source: str,
        timeframe: str,
        records_fetched: int,
        records_inserted: int,
        records_updated: int,
        response_time_ms: int,
        success: bool,
        error_details: str = None,
        api_quota_remaining: int = None
    ) -> None:
        """
        Log data fetch operation from external API.
        
        Args:
            symbol: Asset symbol
            asset_class: Asset class
            source: Data source (polygon, binance, yahoo)
            timeframe: Timeframe
            records_fetched: Number of records fetched
            records_inserted: Number inserted
            records_updated: Number updated
            response_time_ms: API response time
            success: Whether fetch succeeded
            error_details: Error message if failed
            api_quota_remaining: Remaining API quota
        """
        session = self.SessionLocal()
        
        try:
            insert_stmt = text("""
                INSERT INTO enrichment_fetch_log 
                (symbol, asset_class, source, timeframe, records_fetched, records_inserted, 
                 records_updated, fetch_timestamp, source_response_time_ms, success, 
                 error_details, api_quota_remaining, created_at)
                VALUES (:symbol, :asset_class, :source, :timeframe, :records_fetched, 
                        :records_inserted, :records_updated, NOW(), :response_time_ms, 
                        :success, :error_details, :api_quota_remaining, NOW())
            """)
            
            session.execute(insert_stmt, {
                'symbol': symbol,
                'asset_class': asset_class,
                'source': source,
                'timeframe': timeframe,
                'records_fetched': records_fetched,
                'records_inserted': records_inserted,
                'records_updated': records_updated,
                'response_time_ms': response_time_ms,
                'success': success,
                'error_details': error_details,
                'api_quota_remaining': api_quota_remaining
            })
            
            session.commit()
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error logging enrichment fetch: {e}")
        
        finally:
            session.close()
    
    def log_feature_computation(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        features_computed: int,
        computation_time_ms: int,
        success: bool,
        missing_fields: List[str] = None,
        error_details: str = None
    ) -> None:
        """
        Log feature computation operation.
        
        Args:
            symbol: Asset symbol
            asset_class: Asset class
            timeframe: Timeframe
            features_computed: Number of features computed
            computation_time_ms: Computation time
            success: Whether computation succeeded
            missing_fields: List of missing field names
            error_details: Error message if failed
        """
        session = self.SessionLocal()
        
        try:
            insert_stmt = text("""
                INSERT INTO enrichment_compute_log 
                (symbol, asset_class, timeframe, computation_timestamp, features_computed, 
                 computation_time_ms, success, missing_fields, error_details, created_at)
                VALUES (:symbol, :asset_class, :timeframe, NOW(), :features_computed, 
                        :computation_time_ms, :success, :missing_fields, :error_details, NOW())
            """)
            
            session.execute(insert_stmt, {
                'symbol': symbol,
                'asset_class': asset_class,
                'timeframe': timeframe,
                'features_computed': features_computed,
                'computation_time_ms': computation_time_ms,
                'success': success,
                'missing_fields': missing_fields,
                'error_details': error_details
            })
            
            session.commit()
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error logging feature computation: {e}")
        
        finally:
            session.close()
    
    def get_backfill_status(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """
        Get current backfill status for symbol/timeframe.
        
        Args:
            symbol: Asset symbol
            timeframe: Timeframe
        
        Returns:
            Dict with backfill state or None if not found
        """
        session = self.SessionLocal()
        
        try:
            query = text("""
                SELECT id, backfill_job_id, status, last_successful_date, 
                       retry_count, error_message, created_at, updated_at
                FROM backfill_state
                WHERE symbol = :symbol AND timeframe = :timeframe
                ORDER BY updated_at DESC
                LIMIT 1
            """)
            
            result = session.execute(query, {'symbol': symbol, 'timeframe': timeframe}).first()
            
            if result:
                return {
                    'id': result[0],
                    'job_id': str(result[1]),
                    'status': result[2],
                    'last_successful_date': result[3].isoformat() if result[3] else None,
                    'retry_count': result[4],
                    'error_message': result[5],
                    'created_at': result[6].isoformat() if result[6] else None,
                    'updated_at': result[7].isoformat() if result[7] else None
                }
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting backfill status: {e}")
            return None
        
        finally:
            session.close()
    
    def insert_quant_features(
        self,
        symbol: str,
        timeframe: str,
        features_data: List[Dict]
    ) -> int:
        """
        Insert computed quant features for OHLCV data.
        
        Args:
            symbol: Stock ticker
            timeframe: Candle timeframe
            features_data: List of dicts with keys:
                - time: timestamp
                - return_1d: float
                - volatility_20: float
                - volatility_50: float
                - atr: float
                - rolling_volume_20: int
                - volume_ratio: float
                - structure_label: str
                - trend_direction: str
                - volatility_regime: str
                - trend_regime: str
                - compression_regime: str
        
        Returns:
            Number of rows updated with features
        """
        if not features_data:
            return 0
        
        session = self.SessionLocal()
        updated = 0
        
        try:
            for feature in features_data:
                # Update market_data with computed features
                update_stmt = text("""
                    UPDATE market_data
                    SET 
                        return_1d = :return_1d,
                        volatility_20 = :volatility_20,
                        volatility_50 = :volatility_50,
                        atr = :atr,
                        rolling_volume_20 = :rolling_volume_20,
                        volume_ratio = :volume_ratio,
                        structure_label = :structure_label,
                        trend_direction = :trend_direction,
                        volatility_regime = :volatility_regime,
                        trend_regime = :trend_regime,
                        compression_regime = :compression_regime,
                        features_computed_at = :computed_at
                    WHERE symbol = :symbol 
                        AND timeframe = :timeframe 
                        AND time = :time
                """)
                
                result = session.execute(update_stmt, {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'time': feature['time'],
                    'return_1d': feature.get('return_1d'),
                    'volatility_20': feature.get('volatility_20'),
                    'volatility_50': feature.get('volatility_50'),
                    'atr': feature.get('atr'),
                    'rolling_volume_20': feature.get('rolling_volume_20'),
                    'volume_ratio': feature.get('volume_ratio'),
                    'structure_label': feature.get('structure_label'),
                    'trend_direction': feature.get('trend_direction'),
                    'volatility_regime': feature.get('volatility_regime'),
                    'trend_regime': feature.get('trend_regime'),
                    'compression_regime': feature.get('compression_regime'),
                    'computed_at': datetime.utcnow()
                })
                
                updated += result.rowcount
            
            session.commit()
            logger.info(f"Updated {updated} records with quant features for {symbol}/{timeframe}")
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error inserting quant features for {symbol}/{timeframe}: {e}")
        
        finally:
            session.close()
        
        return updated
    
    def get_quant_features(
        self,
        symbol: str,
        timeframe: str = '1d',
        start: str = None,
        end: str = None,
        limit: int = 500
    ) -> List[Dict]:
        """
        Fetch computed quant features for a symbol.
        
        Args:
            symbol: Stock ticker
            timeframe: Candle timeframe (default: '1d')
            start: Start date YYYY-MM-DD (optional)
            end: End date YYYY-MM-DD (optional)
            limit: Max records to return (default: 500)
        
        Returns:
            List of dicts with OHLCV + all quant features
        """
        session = self.SessionLocal()
        
        try:
            conditions = [
                "symbol = :symbol",
                "timeframe = :timeframe",
                "features_computed_at IS NOT NULL"
            ]
            
            params = {'symbol': symbol, 'timeframe': timeframe, 'limit': limit}
            
            if start:
                conditions.append("time >= :start::timestamp")
                params['start'] = start
            
            if end:
                conditions.append("time < :end::timestamp + INTERVAL '1 day'")
                params['end'] = end
            
            where_clause = " AND ".join(conditions)
            
            sql = f"""
                SELECT 
                    time, symbol, timeframe, open, high, low, close, volume,
                    return_1d, volatility_20, volatility_50, atr, rolling_volume_20,
                    volume_ratio, structure_label, trend_direction, volatility_regime,
                    trend_regime, compression_regime, quality_score, validated,
                    features_computed_at
                FROM market_data
                WHERE {where_clause}
                ORDER BY time ASC
                LIMIT :limit
            """
            
            result = session.execute(text(sql), params)
            rows = result.fetchall()
            
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
                    'return_1d': float(row[8]) if row[8] is not None else None,
                    'volatility_20': float(row[9]) if row[9] is not None else None,
                    'volatility_50': float(row[10]) if row[10] is not None else None,
                    'atr': float(row[11]) if row[11] is not None else None,
                    'rolling_volume_20': row[12],
                    'volume_ratio': float(row[13]) if row[13] is not None else None,
                    'structure_label': row[14],
                    'trend_direction': row[15],
                    'volatility_regime': row[16],
                    'trend_regime': row[17],
                    'compression_regime': row[18],
                    'quality_score': float(row[19]) if row[19] is not None else None,
                    'validated': row[20],
                    'features_computed_at': row[21].isoformat() if row[21] else None
                })
            
            logger.info(f"Retrieved {len(data)} quant feature records for {symbol}/{timeframe}")
            return data
        
        except Exception as e:
            logger.error(f"Error fetching quant features for {symbol}/{timeframe}: {e}")
            return []
        
        finally:
            session.close()
    
    def update_quant_feature_summary(
        self,
        symbol: str,
        timeframe: str,
        latest_record: Dict
    ) -> bool:
        """
        Update the quant feature summary table with latest features.
        
        Args:
            symbol: Stock ticker
            timeframe: Candle timeframe
            latest_record: Dict with latest feature values
        
        Returns:
            True if successful
        """
        session = self.SessionLocal()
        
        try:
            upsert_stmt = text("""
                INSERT INTO quant_feature_summary 
                (symbol, timeframe, latest_timestamp, return_1d, volatility_20, 
                 volatility_50, atr, rolling_volume_20, volume_ratio,
                 structure_label, trend_direction, volatility_regime, 
                 trend_regime, compression_regime, computed_at, updated_at)
                VALUES 
                (:symbol, :timeframe, :time, :return_1d, :volatility_20,
                 :volatility_50, :atr, :rolling_volume_20, :volume_ratio,
                 :structure_label, :trend_direction, :volatility_regime,
                 :trend_regime, :compression_regime, :now, :now)
                ON CONFLICT (symbol, timeframe) DO UPDATE SET
                    latest_timestamp = EXCLUDED.latest_timestamp,
                    return_1d = EXCLUDED.return_1d,
                    volatility_20 = EXCLUDED.volatility_20,
                    volatility_50 = EXCLUDED.volatility_50,
                    atr = EXCLUDED.atr,
                    rolling_volume_20 = EXCLUDED.rolling_volume_20,
                    volume_ratio = EXCLUDED.volume_ratio,
                    structure_label = EXCLUDED.structure_label,
                    trend_direction = EXCLUDED.trend_direction,
                    volatility_regime = EXCLUDED.volatility_regime,
                    trend_regime = EXCLUDED.trend_regime,
                    compression_regime = EXCLUDED.compression_regime,
                    updated_at = EXCLUDED.updated_at
            """)
            
            session.execute(upsert_stmt, {
                'symbol': symbol,
                'timeframe': timeframe,
                'time': latest_record.get('time'),
                'return_1d': latest_record.get('return_1d'),
                'volatility_20': latest_record.get('volatility_20'),
                'volatility_50': latest_record.get('volatility_50'),
                'atr': latest_record.get('atr'),
                'rolling_volume_20': latest_record.get('rolling_volume_20'),
                'volume_ratio': latest_record.get('volume_ratio'),
                'structure_label': latest_record.get('structure_label'),
                'trend_direction': latest_record.get('trend_direction'),
                'volatility_regime': latest_record.get('volatility_regime'),
                'trend_regime': latest_record.get('trend_regime'),
                'compression_regime': latest_record.get('compression_regime'),
                'now': datetime.utcnow()
            })
            
            session.commit()
            logger.info(f"Updated quant feature summary for {symbol}/{timeframe}")
            return True
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating quant feature summary: {e}")
            return False
        
        finally:
            session.close()
    
    # ============== PHASE 1: SCHEDULER MONITORING ==============
    
    def create_scheduler_execution_log(
        self,
        started_at: datetime,
        total_symbols: int,
        status: str = "running"
    ) -> str:
        """
        Create a new scheduler execution log entry.
        
        Args:
            started_at: When the execution started
            total_symbols: Total symbols being processed
            status: Current status (running, completed, failed)
        
        Returns:
            execution_id UUID string
        """
        session = self.SessionLocal()
        
        try:
            # Raw SQL to insert and return execution_id
            result = session.execute(text("""
                INSERT INTO scheduler_execution_log 
                (started_at, total_symbols, status)
                VALUES (:started_at, :total_symbols, :status)
                RETURNING execution_id::text
            """), {
                "started_at": started_at,
                "total_symbols": total_symbols,
                "status": status
            })
            
            execution_id = result.scalar()
            session.commit()
            logger.debug(f"Created scheduler execution log: {execution_id}")
            return execution_id
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating scheduler execution log: {e}")
            raise
        
        finally:
            session.close()
    
    def update_scheduler_execution_log(
        self,
        execution_id: str,
        completed_at: datetime,
        successful_symbols: int,
        failed_symbols: int,
        total_records_processed: int,
        status: str = "completed",
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update scheduler execution log with completion details.
        
        Args:
            execution_id: UUID of the execution
            completed_at: When execution completed
            successful_symbols: Count of successful symbols
            failed_symbols: Count of failed symbols
            total_records_processed: Total records processed
            status: Final status
            error_message: Any error message if failed
        
        Returns:
            Success boolean
        """
        session = self.SessionLocal()
        
        try:
            # Calculate duration
            duration_seconds = None
            started_at_result = session.execute(
                text("SELECT started_at FROM scheduler_execution_log WHERE execution_id = :id"),
                {"id": execution_id}
            ).scalar()
            
            if started_at_result:
                # Ensure both datetimes are timezone-aware for subtraction
                from dateutil import parser
                if isinstance(started_at_result, str):
                    started_at_result = parser.isoparse(started_at_result)
                
                # Make completed_at timezone-aware if it isn't
                if completed_at.tzinfo is None:
                    from pytz import UTC
                    completed_at = completed_at.replace(tzinfo=UTC)
                
                duration = completed_at - started_at_result
                duration_seconds = int(duration.total_seconds())
            
            session.execute(text("""
                UPDATE scheduler_execution_log
                SET completed_at = :completed_at,
                    successful_symbols = :successful_symbols,
                    failed_symbols = :failed_symbols,
                    total_records_processed = :total_records_processed,
                    status = :status,
                    error_message = :error_message,
                    duration_seconds = :duration_seconds
                WHERE execution_id = :execution_id
            """), {
                "completed_at": completed_at,
                "successful_symbols": successful_symbols,
                "failed_symbols": failed_symbols,
                "total_records_processed": total_records_processed,
                "status": status,
                "error_message": error_message,
                "duration_seconds": duration_seconds,
                "execution_id": execution_id
            })
            
            session.commit()
            logger.debug(f"Updated scheduler execution log: {execution_id}")
            return True
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating scheduler execution log: {e}")
            return False
        
        finally:
            session.close()
    
    def log_feature_computation_failure(
        self,
        symbol: str,
        timeframe: str,
        error_message: str,
        execution_id: Optional[str] = None
    ) -> bool:
        """
        Log a feature computation failure for a symbol/timeframe.
        
        Args:
            symbol: Stock ticker
            timeframe: Candle timeframe
            error_message: Error description
            execution_id: Link to scheduler execution if available
        
        Returns:
            Success boolean
        """
        session = self.SessionLocal()
        
        try:
            session.execute(text("""
                INSERT INTO feature_computation_failures 
                (symbol, timeframe, error_message, execution_id)
                VALUES (:symbol, :timeframe, :error_message, :execution_id)
            """), {
                "symbol": symbol,
                "timeframe": timeframe,
                "error_message": error_message,
                "execution_id": execution_id
            })
            
            session.commit()
            logger.debug(f"Logged feature computation failure: {symbol}/{timeframe}")
            return True
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error logging feature computation failure: {e}")
            return False
        
        finally:
            session.close()
    
    def update_feature_freshness(
        self,
        symbol: str,
        timeframe: str,
        last_computed_at: datetime,
        data_point_count: int,
        staleness_seconds: int
    ) -> bool:
        """
        Update feature freshness cache for a symbol/timeframe.
        
        Args:
            symbol: Stock ticker
            timeframe: Candle timeframe
            last_computed_at: When features were last computed
            data_point_count: Number of computed features
            staleness_seconds: Seconds since computation
        
        Returns:
            Success boolean
        """
        session = self.SessionLocal()
        
        try:
            # Determine status based on staleness
            if staleness_seconds is None or staleness_seconds > 86400:  # >24h
                status = "stale"
            elif staleness_seconds > 3600:  # >1h
                status = "aging"
            else:
                status = "fresh"
            
            if data_point_count == 0:
                status = "missing"
            
            session.execute(text("""
                INSERT INTO feature_freshness 
                (symbol, timeframe, last_computed_at, data_point_count, status, staleness_seconds)
                VALUES (:symbol, :timeframe, :last_computed_at, :data_point_count, :status, :staleness_seconds)
                ON CONFLICT (symbol, timeframe) DO UPDATE SET
                    last_computed_at = :last_computed_at,
                    data_point_count = :data_point_count,
                    status = :status,
                    staleness_seconds = :staleness_seconds,
                    updated_at = NOW()
            """), {
                "symbol": symbol,
                "timeframe": timeframe,
                "last_computed_at": last_computed_at,
                "data_point_count": data_point_count,
                "status": status,
                "staleness_seconds": staleness_seconds
            })
            
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating feature freshness: {e}")
            return False
        
        finally:
            session.close()
    
    def log_symbol_computation_status(
        self,
        execution_id: str,
        symbol: str,
        asset_class: str,
        timeframe: str,
        status: str,
        records_processed: int = 0,
        records_inserted: int = 0,
        features_computed: int = 0,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ) -> bool:
        """
        Log status of a symbol computation within an execution.
        
        Args:
            execution_id: UUID of the parent scheduler execution
            symbol: Stock ticker
            asset_class: Type (stock, crypto, etf)
            timeframe: Candle timeframe
            status: Status (pending, in_progress, completed, failed)
            records_processed: Records processed
            records_inserted: Records inserted
            features_computed: Features computed
            error_message: Error if failed
            started_at: When computation started
            completed_at: When computation completed
        
        Returns:
            Success boolean
        """
        session = self.SessionLocal()
        
        try:
            duration_seconds = None
            if started_at and completed_at:
                duration_seconds = int((completed_at - started_at).total_seconds())
            
            session.execute(text("""
                INSERT INTO symbol_computation_status
                (execution_id, symbol, asset_class, timeframe, status, 
                 records_processed, records_inserted, features_computed, 
                 error_message, started_at, completed_at, duration_seconds)
                VALUES (:execution_id, :symbol, :asset_class, :timeframe, :status,
                        :records_processed, :records_inserted, :features_computed,
                        :error_message, :started_at, :completed_at, :duration_seconds)
            """), {
                "execution_id": execution_id,
                "symbol": symbol,
                "asset_class": asset_class,
                "timeframe": timeframe,
                "status": status,
                "records_processed": records_processed,
                "records_inserted": records_inserted,
                "features_computed": features_computed,
                "error_message": error_message,
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_seconds": duration_seconds
            })
            
            session.commit()
            return True
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error logging symbol computation status: {e}")
            return False
        
        finally:
            session.close()
    
    def get_scheduler_health(self) -> Dict:
        """
        Get health status of scheduler and features.
        
        Returns:
            Dict with:
            - last_execution: Last successful execution
            - stale_features: Count of stale features
            - recent_failures: Recent computation failures
            - symbols_monitored: Total symbols in feature_freshness
        """
        session = self.SessionLocal()
        
        try:
            # Last execution
            last_exec = session.execute(text("""
                SELECT execution_id, started_at, completed_at, status, 
                       successful_symbols, failed_symbols
                FROM scheduler_execution_log
                ORDER BY started_at DESC
                LIMIT 1
            """)).first()
            
            # Stale features (>24h)
            stale_count = session.execute(text("""
                SELECT COUNT(*) as count
                FROM feature_freshness
                WHERE status = 'stale'
            """)).scalar()
            
            # Recent failures (last 24h)
            recent_failures = session.execute(text("""
                SELECT symbol, timeframe, error_message, failed_at
                FROM feature_computation_failures
                WHERE failed_at > NOW() - INTERVAL '24 hours'
                  AND resolved = FALSE
                ORDER BY failed_at DESC
                LIMIT 10
            """)).fetchall()
            
            # Total symbols monitored
            total_symbols = session.execute(text("""
                SELECT COUNT(DISTINCT symbol) as count
                FROM feature_freshness
            """)).scalar()
            
            return {
                "last_execution": {
                    "execution_id": str(last_exec[0]) if last_exec else None,
                    "started_at": last_exec[1].isoformat() if last_exec else None,
                    "completed_at": last_exec[2].isoformat() if last_exec else None,
                    "status": last_exec[3] if last_exec else None,
                    "successful_symbols": last_exec[4] if last_exec else 0,
                    "failed_symbols": last_exec[5] if last_exec else 0
                },
                "stale_features_count": stale_count or 0,
                "recent_failures": [
                    {
                        "symbol": f[0],
                        "timeframe": f[1],
                        "error": f[2],
                        "failed_at": f[3].isoformat()
                    }
                    for f in recent_failures
                ] if recent_failures else [],
                "total_symbols_monitored": total_symbols or 0
            }
        
        except Exception as e:
            logger.error(f"Error getting scheduler health: {e}")
            return {
                "error": str(e),
                "last_execution": None,
                "stale_features_count": 0,
                "recent_failures": [],
                "total_symbols_monitored": 0
            }
        
        finally:
            session.close()
    
    def get_feature_staleness_report(self, limit: int = 50) -> List[Dict]:
        """
        Get features sorted by staleness for monitoring dashboard.
        
        Args:
            limit: Max results to return
        
        Returns:
            List of dicts with symbol, timeframe, staleness, status
        """
        session = self.SessionLocal()
        
        try:
            results = session.execute(text("""
                SELECT symbol, timeframe, last_computed_at, staleness_seconds, status, data_point_count
                FROM feature_freshness
                ORDER BY staleness_seconds DESC NULLS LAST
                LIMIT :limit
            """), {"limit": limit}).fetchall()
            
            return [
                {
                    "symbol": r[0],
                    "timeframe": r[1],
                    "last_computed_at": r[2].isoformat() if r[2] else None,
                    "staleness_seconds": r[3],
                    "status": r[4],
                    "data_point_count": r[5]
                }
                for r in results
            ]
        
        except Exception as e:
            logger.error(f"Error getting feature staleness report: {e}")
            return []
        
        finally:
            session.close()
    
    # ===== Phase 4: Backfill State Persistence =====
    
    def create_backfill_state(
        self,
        symbol: str,
        asset_class: str = 'stock',
        timeframe: str = '1d',
        status: str = 'pending'
    ) -> str:
        """
        Create a new backfill state record for concurrent backfill tracking.
        
        Args:
            symbol: Stock ticker
            asset_class: Type of asset (stock, crypto, etf)
            timeframe: Candle timeframe
            status: Initial status (pending, in_progress, completed, failed)
        
        Returns:
            execution_id (UUID) for tracking
        """
        session = self.SessionLocal()
        try:
            result = session.execute(
                text("""
                    INSERT INTO backfill_state_persistent
                    (symbol, asset_class, timeframe, status, created_at)
                    VALUES (:symbol, :asset_class, :timeframe, :status, NOW())
                    RETURNING execution_id::text
                """),
                {
                    "symbol": symbol,
                    "asset_class": asset_class,
                    "timeframe": timeframe,
                    "status": status
                }
            )
            session.commit()
            execution_id = result.scalar()
            logger.debug(f"Created backfill state for {symbol}/{timeframe}: {execution_id}")
            return execution_id
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create backfill state: {e}")
            raise
        finally:
            session.close()
    
    def update_backfill_state(
        self,
        execution_id: str,
        status: str,
        records_inserted: int = 0,
        error_message: str = None,
        retry_count: int = 0
    ) -> bool:
        """
        Update backfill state record with completion details.
        
        Args:
            execution_id: UUID from create_backfill_state
            status: Updated status
            records_inserted: Number of records inserted
            error_message: Error details if failed
            retry_count: Current retry count
        
        Returns:
            True if successful, False otherwise
        """
        session = self.SessionLocal()
        try:
            completed_at = None if status == 'in_progress' else "NOW()"
            
            session.execute(
                text("""
                    UPDATE backfill_state_persistent
                    SET status = :status,
                        records_inserted = :records_inserted,
                        error_message = :error_message,
                        retry_count = :retry_count,
                        completed_at = CASE WHEN :status != 'in_progress' THEN NOW() ELSE NULL END,
                        updated_at = NOW()
                    WHERE execution_id = :execution_id
                """),
                {
                    "execution_id": execution_id,
                    "status": status,
                    "records_inserted": records_inserted,
                    "error_message": error_message,
                    "retry_count": retry_count
                }
            )
            session.commit()
            logger.debug(f"Updated backfill state {execution_id} to {status}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update backfill state {execution_id}: {e}")
            return False
        finally:
            session.close()
    
    def get_active_backfill_states(self) -> List[Dict]:
        """
        Get all active (in_progress) backfill states.
        
        Returns:
            List of backfill state records
        """
        session = self.SessionLocal()
        try:
            results = session.execute(
                text("""
                    SELECT execution_id::text, symbol, timeframe, started_at,
                           retry_count, max_retries
                    FROM backfill_state_persistent
                    WHERE status = 'in_progress'
                    ORDER BY started_at ASC
                """)
            ).fetchall()
            
            return [
                {
                    "execution_id": r[0],
                    "symbol": r[1],
                    "timeframe": r[2],
                    "started_at": r[3],
                    "retry_count": r[4],
                    "max_retries": r[5]
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Error getting active backfill states: {e}")
            return []
        finally:
            session.close()
    
    # ===== Phase 4: Data Quality Maintenance =====
    
    def cleanup_duplicate_records(
        self,
        symbol: str = None,
        timeframe: str = None,
        dry_run: bool = False
    ) -> Dict:
        """
        Detect and remove duplicate records for a symbol/timeframe.
        
        Args:
            symbol: Optional symbol filter
            timeframe: Optional timeframe filter
            dry_run: If True, only report duplicates without deleting
        
        Returns:
            Dictionary with cleanup results
        """
        session = self.SessionLocal()
        try:
            # Find duplicate records (same symbol, timeframe, time)
            where_clause = ""
            params = {}
            
            if symbol:
                where_clause += " AND symbol = :symbol"
                params["symbol"] = symbol
            if timeframe:
                where_clause += " AND timeframe = :timeframe"
                params["timeframe"] = timeframe
            
            # Find records with duplicates
            duplicate_query = f"""
                SELECT symbol, timeframe, time, COUNT(*) as cnt
                FROM market_data
                WHERE time IS NOT NULL {where_clause}
                GROUP BY symbol, timeframe, time
                HAVING COUNT(*) > 1
            """
            
            duplicates = session.execute(text(duplicate_query), params).fetchall()
            
            total_removed = 0
            results = {
                "total_duplicates_found": len(duplicates),
                "total_records_removed": 0,
                "cleanup_details": []
            }
            
            if not dry_run and duplicates:
                # For each duplicate, keep the newest and remove others
                for dup in duplicates:
                    sym, tf, candle_time, count = dup
                    
                    # Find IDs to remove (keep the one with highest id = newest)
                    id_query = """
                        SELECT id
                        FROM market_data
                        WHERE symbol = :symbol AND timeframe = :timeframe AND time = :time
                        ORDER BY id DESC
                        OFFSET 1
                    """
                    
                    ids_to_remove = session.execute(
                        text(id_query),
                        {"symbol": sym, "timeframe": tf, "time": candle_time}
                    ).fetchall()
                    
                    if ids_to_remove:
                        id_list = [r[0] for r in ids_to_remove]
                        
                        # Delete duplicates
                        delete_query = """
                            DELETE FROM market_data
                            WHERE id = ANY(:ids)
                        """
                        session.execute(text(delete_query), {"ids": id_list})
                        
                        # Log cleanup
                        session.execute(
                            text("""
                                INSERT INTO duplicate_records_log
                                (symbol, timeframe, candle_time, duplicate_count, duplicate_ids)
                                VALUES (:symbol, :timeframe, :candle_time, :count, :ids)
                            """),
                            {
                                "symbol": sym,
                                "timeframe": tf,
                                "candle_time": candle_time,
                                "count": count - 1,
                                "ids": id_list
                            }
                        )
                        
                        removed = len(id_list)
                        total_removed += removed
                        results["cleanup_details"].append({
                            "symbol": sym,
                            "timeframe": tf,
                            "candle_time": candle_time.isoformat(),
                            "duplicates_removed": removed
                        })
                
                session.commit()
            
            results["total_records_removed"] = total_removed
            logger.info(f"Data cleanup: {total_removed} duplicate records removed (dry_run={dry_run})")
            
            return results
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error cleaning up duplicate records: {e}")
            return {"error": str(e), "total_records_removed": 0}
        finally:
            session.close()
    
    def detect_data_anomalies(
        self,
        symbol: str = None,
        check_gaps: bool = True,
        check_outliers: bool = True,
        check_staleness: bool = True
    ) -> Dict:
        """
        Detect data anomalies: gaps, duplicates, outliers, stale data.
        
        Args:
            symbol: Optional symbol filter
            check_gaps: Check for data gaps/breaks
            check_outliers: Check for price/volume outliers
            check_staleness: Check for stale data
        
        Returns:
            Dictionary with anomaly details
        """
        session = self.SessionLocal()
        try:
            results = {
                "timestamp": datetime.utcnow().isoformat(),
                "gaps": [],
                "outliers": [],
                "stale_data": [],
                "total_anomalies": 0
            }
            
            where_clause = ""
            params = {}
            
            if symbol:
                where_clause = " WHERE symbol = :symbol"
                params["symbol"] = symbol
            
            # Check for gaps (missing candles)
            if check_gaps:
                gap_query = f"""
                    WITH gap_analysis AS (
                        SELECT
                            symbol,
                            timeframe,
                            time,
                            LAG(time) OVER (
                                PARTITION BY symbol, timeframe
                                ORDER BY time
                            ) as prev_time,
                            EXTRACT(EPOCH FROM time - LAG(time) OVER (
                                PARTITION BY symbol, timeframe
                                ORDER BY time
                            )) as time_gap_seconds
                        FROM market_data
                        {where_clause}
                    )
                    SELECT symbol, timeframe, time, prev_time, time_gap_seconds
                    FROM gap_analysis
                    WHERE time_gap_seconds > 86400
                    LIMIT 100
                """
                
                gaps = session.execute(text(gap_query)).fetchall()
                for gap in gaps:
                    results["gaps"].append({
                        "symbol": gap[0],
                        "timeframe": gap[1],
                        "gap_time": gap[2].isoformat() if gap[2] else None,
                        "gap_seconds": int(gap[4]) if gap[4] else 0
                    })
                
                # Log anomalies
                for gap in gaps:
                    session.execute(
                        text("""
                            INSERT INTO data_anomalies
                            (symbol, timeframe, anomaly_type, severity, data_point_time, description)
                            VALUES (:symbol, :timeframe, 'gap', 'medium', :time, :desc)
                        """),
                        {
                            "symbol": gap[0],
                            "timeframe": gap[1],
                            "time": gap[2],
                            "desc": f"Gap of {int(gap[4]) // 3600} hours detected"
                        }
                    )
            
            # Check for stale data (last update > 24 hours)
            if check_staleness:
                stale_query = f"""
                    SELECT symbol, timeframe, MAX(time) as last_time,
                           EXTRACT(EPOCH FROM NOW() - MAX(time)) as staleness_seconds
                    FROM market_data
                    {where_clause}
                    GROUP BY symbol, timeframe
                    HAVING EXTRACT(EPOCH FROM NOW() - MAX(time)) > 86400
                    ORDER BY staleness_seconds DESC
                    LIMIT 100
                """
                
                stale = session.execute(text(stale_query)).fetchall()
                for record in stale:
                    hours_stale = int(record[3] / 3600)
                    results["stale_data"].append({
                        "symbol": record[0],
                        "timeframe": record[1],
                        "last_update": record[2].isoformat() if record[2] else None,
                        "hours_stale": hours_stale
                    })
                    
                    # Log anomaly
                    session.execute(
                        text("""
                            INSERT INTO data_anomalies
                            (symbol, timeframe, anomaly_type, severity, data_point_time, description)
                            VALUES (:symbol, :timeframe, 'stale', 'high', NOW(), :desc)
                        """),
                        {
                            "symbol": record[0],
                            "timeframe": record[1],
                            "desc": f"Data stale for {hours_stale} hours"
                        }
                    )
            
            # Check for outliers (price movements > 20% in one candle)
            if check_outliers:
                outlier_query = f"""
                    WITH price_changes AS (
                        SELECT
                            symbol,
                            timeframe,
                            time,
                            close,
                            LAG(close) OVER (
                                PARTITION BY symbol, timeframe
                                ORDER BY time
                            ) as prev_close,
                            ABS((close - LAG(close) OVER (
                                PARTITION BY symbol, timeframe
                                ORDER BY time
                            )) / LAG(close) OVER (
                                PARTITION BY symbol, timeframe
                                ORDER BY time
                            )) as pct_change
                        FROM market_data
                        {where_clause}
                    )
                    SELECT symbol, timeframe, time, close, prev_close, pct_change
                    FROM price_changes
                    WHERE pct_change > 0.20
                    ORDER BY pct_change DESC
                    LIMIT 100
                """
                
                outliers = session.execute(text(outlier_query)).fetchall()
                for outlier in outliers:
                    results["outliers"].append({
                        "symbol": outlier[0],
                        "timeframe": outlier[1],
                        "time": outlier[2].isoformat() if outlier[2] else None,
                        "close": float(outlier[3]),
                        "prev_close": float(outlier[4]) if outlier[4] else None,
                        "pct_change": float(outlier[5]) * 100 if outlier[5] else 0
                    })
                    
                    # Log anomaly with severity based on magnitude
                    severity = "critical" if (outlier[5] or 0) > 0.50 else "high"
                    session.execute(
                        text("""
                            INSERT INTO data_anomalies
                            (symbol, timeframe, anomaly_type, severity, data_point_time, description)
                            VALUES (:symbol, :timeframe, 'outlier', :severity, :time, :desc)
                        """),
                        {
                            "symbol": outlier[0],
                            "timeframe": outlier[1],
                            "severity": severity,
                            "time": outlier[2],
                            "desc": f"Price outlier: {(outlier[5] or 0) * 100:.2f}% change"
                        }
                    )
            
            results["total_anomalies"] = (
                len(results["gaps"]) + 
                len(results["outliers"]) + 
                len(results["stale_data"])
            )
            
            session.commit()
            logger.info(f"Data anomaly detection: {results['total_anomalies']} anomalies found")
            
            return results
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error detecting data anomalies: {e}")
            return {"error": str(e), "total_anomalies": 0}
        finally:
            session.close()
    
    def track_symbol_failure(
        self,
        symbol: str,
        success: bool = False
    ) -> Dict:
        """
        Track consecutive failures for a symbol and trigger alerts.
        
        Args:
            symbol: Stock ticker
            success: Whether the operation was successful
        
        Returns:
            Updated failure tracking record
        """
        session = self.SessionLocal()
        try:
            # Get or create tracking record
            result = session.execute(
                text("""
                    INSERT INTO symbol_failure_tracking (symbol)
                    VALUES (:symbol)
                    ON CONFLICT (symbol) DO NOTHING
                    RETURNING consecutive_failures
                """),
                {"symbol": symbol}
            )
            session.flush()
            
            if success:
                # Reset on success
                session.execute(
                    text("""
                        UPDATE symbol_failure_tracking
                        SET consecutive_failures = 0,
                            last_success_at = NOW(),
                            alert_sent = FALSE,
                            updated_at = NOW()
                        WHERE symbol = :symbol
                    """),
                    {"symbol": symbol}
                )
            else:
                # Increment on failure
                session.execute(
                    text("""
                        UPDATE symbol_failure_tracking
                        SET consecutive_failures = consecutive_failures + 1,
                            last_failure_at = NOW(),
                            updated_at = NOW()
                        WHERE symbol = :symbol
                    """),
                    {"symbol": symbol}
                )
            
            session.commit()
            
            # Fetch updated record
            record = session.execute(
                text("""
                    SELECT consecutive_failures, last_failure_at, alert_sent
                    FROM symbol_failure_tracking
                    WHERE symbol = :symbol
                """),
                {"symbol": symbol}
            ).fetchone()
            
            if record:
                return {
                    "symbol": symbol,
                    "consecutive_failures": record[0],
                    "last_failure_at": record[1],
                    "alert_sent": record[2],
                    "should_alert": record[0] >= 3 and not record[2]
                }
            
            return {"symbol": symbol, "error": "Failed to track"}
        
        except Exception as e:
            session.rollback()
            logger.error(f"Error tracking symbol failure for {symbol}: {e}")
            return {"symbol": symbol, "error": str(e)}
        finally:
            session.close()
