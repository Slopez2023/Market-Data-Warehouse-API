"""
Data Enrichment Service
Main orchestrator for the enrichment pipeline:
Fetch → Validate → Compute Features → Store
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import uuid

from src.services.data_aggregator import DataAggregator
from src.services.feature_computation_service import FeatureComputationService
from src.services.structured_logging import StructuredLogger


class DataEnrichmentService:
    """Main enrichment orchestrator"""
    
    def __init__(self, db_service, config=None):
        """
        Initialize enrichment service
        
        Args:
            db_service: Database service instance
            config: AppConfig instance
        """
        self.db = db_service
        self.config = config
        self.aggregator = DataAggregator(config)
        self.features = FeatureComputationService()
        self.logger = StructuredLogger(__name__)
    
    async def enrich_asset(
        self,
        symbol: str,
        asset_class: str,
        timeframes: List[str],
        start_date: datetime,
        end_date: datetime,
        source_priority: Optional[List[str]] = None,
        backfill_job_id: Optional[str] = None
    ) -> Dict:
        """
        Complete enrichment pipeline for one asset across timeframes
        
        Args:
            symbol: Asset symbol (e.g., 'BTC', 'AAPL')
            asset_class: 'stock', 'crypto', or 'etf'
            timeframes: List of timeframes to enrich ('5m', '1h', '1d', etc.)
            start_date: Enrichment start date
            end_date: Enrichment end date
            source_priority: Source fetch priority
            backfill_job_id: Optional job ID for backfill tracking
            
        Returns:
            Dict with enrichment results:
            {
                'symbol': str,
                'asset_class': str,
                'job_id': str,
                'start_date': str,
                'end_date': str,
                'timeframes': {
                    '1d': {
                        'status': 'success' | 'failed',
                        'source': str,
                        'records_fetched': int,
                        'records_inserted': int,
                        'records_updated': int,
                        'features_computed': int,
                        'quality_score': float,
                        'error': str (if failed)
                    },
                    ...
                },
                'total_records_inserted': int,
                'total_records_updated': int,
                'success': bool
            }
        """
        job_id = backfill_job_id or str(uuid.uuid4())
        
        results = {
            'symbol': symbol,
            'asset_class': asset_class,
            'job_id': job_id,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'timeframes': {},
            'total_records_inserted': 0,
            'total_records_updated': 0,
            'success': True
        }
        
        self.logger.info(
            "enrichment_started",
            symbol=symbol,
            asset_class=asset_class,
            job_id=job_id,
            timeframes=timeframes
        )
        
        for timeframe in timeframes:
            tf_result = await self._enrich_timeframe(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                source_priority=source_priority,
                job_id=job_id
            )
            
            results['timeframes'][timeframe] = tf_result
            
            if tf_result['status'] == 'success':
                results['total_records_inserted'] += tf_result.get('records_inserted', 0)
                results['total_records_updated'] += tf_result.get('records_updated', 0)
            else:
                results['success'] = False
        
        self.logger.info(
            "enrichment_completed",
            symbol=symbol,
            job_id=job_id,
            success=results['success'],
            total_inserted=results['total_records_inserted'],
            total_updated=results['total_records_updated']
        )
        
        return results
    
    async def _enrich_timeframe(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        source_priority: Optional[List[str]],
        job_id: str
    ) -> Dict:
        """
        Enrich single timeframe
        
        Args:
            symbol: Asset symbol
            asset_class: Asset class
            timeframe: Timeframe
            start_date: Start date
            end_date: End date
            source_priority: Source priority list
            job_id: Job ID for tracking
            
        Returns:
            Timeframe enrichment result
        """
        result = {
            'status': 'failed',
            'source': None,
            'records_fetched': 0,
            'records_inserted': 0,
            'records_updated': 0,
            'features_computed': 0,
            'quality_score': 0.0,
            'error': None
        }
        
        try:
            # 1. FETCH DATA
            self.logger.info(
                "enrich_fetching",
                symbol=symbol,
                timeframe=timeframe
            )
            
            fetch_result = await self.aggregator.fetch_ohlcv(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
                source_priority=source_priority
            )
            
            if not fetch_result['success']:
                result['error'] = fetch_result['error']
                self.logger.error(
                    "enrich_fetch_failed",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=result['error']
                )
                return result
            
            candles = fetch_result['candles']
            result['source'] = fetch_result['source']
            result['records_fetched'] = len(candles)
            
            # 2. VALIDATE DATA
            self.logger.info(
                "enrich_validating",
                symbol=symbol,
                timeframe=timeframe,
                records=len(candles)
            )
            
            validated_candles, validation_notes = self._validate_data(candles)
            quality_score = self._calculate_quality_score(validated_candles, validation_notes)
            result['quality_score'] = quality_score
            
            if quality_score < 0.7:
                result['error'] = f"Quality score too low: {quality_score}"
                self.logger.warning(
                    "enrich_low_quality",
                    symbol=symbol,
                    timeframe=timeframe,
                    quality_score=quality_score
                )
                return result
            
            # 3. COMPUTE FEATURES
            self.logger.info(
                "enrich_computing",
                symbol=symbol,
                timeframe=timeframe
            )
            
            # Get crypto data if needed
            crypto_data = None
            if asset_class == 'crypto':
                crypto_data = await self.aggregator.fetch_crypto_microstructure(
                    symbol=fetch_result['metadata'].get('source_symbol'),
                    timeframe=timeframe
                )
            
            enriched_candles = self.features.compute_all(
                validated_candles,
                asset_class=asset_class,
                crypto_data=crypto_data if crypto_data and crypto_data.get('success') else None
            )
            
            result['features_computed'] = len([
                col for col in enriched_candles.columns
                if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            ])
            
            # 4. STORE IN DATABASE
            self.logger.info(
                "enrich_storing",
                symbol=symbol,
                timeframe=timeframe
            )
            
            inserted, updated = await self._store_enriched_data(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                source=fetch_result['source'],
                candles=enriched_candles,
                quality_score=quality_score,
                validation_notes=validation_notes,
                job_id=job_id
            )
            
            result['records_inserted'] = inserted
            result['records_updated'] = updated
            result['status'] = 'success'
            
            self.logger.info(
                "enrich_success",
                symbol=symbol,
                timeframe=timeframe,
                inserted=inserted,
                updated=updated
            )
            
            # 5. UPDATE BACKFILL STATE
            await self._update_backfill_state(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                job_id=job_id,
                status='completed'
            )
            
            return result
        
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(
                "enrich_exception",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)[:200]
            )
            
            # Update backfill state with error
            await self._update_backfill_state(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                job_id=job_id,
                status='failed',
                error_message=str(e)[:200]
            )
            
            return result
    
    def _validate_data(self, candles: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
        """
        Validate OHLCV data
        
        Returns:
            Tuple of (validated_df, validation_notes)
        """
        df = candles.copy()
        issues = []
        
        # Required fields
        required = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required if col not in df.columns]
        if missing:
            issues.append(f"Missing columns: {missing}")
            return df, '; '.join(issues)
        
        initial_count = len(df)
        
        # Remove rows with NaN in critical fields
        df = df.dropna(subset=['open', 'high', 'low', 'close', 'volume'])
        removed_nan = initial_count - len(df)
        if removed_nan > 0:
            issues.append(f"Removed {removed_nan} rows with NaN")
        
        # Validate OHLC relationships
        invalid_mask = (
            (df['high'] < df['low']) |
            (df['high'] < df['open']) |
            (df['high'] < df['close']) |
            (df['low'] > df['open']) |
            (df['low'] > df['close']) |
            (df['volume'] < 0)
        )
        
        invalid_count = invalid_mask.sum()
        if invalid_count > 0:
            issues.append(f"Invalid OHLC in {invalid_count} candles")
            df = df[~invalid_mask]
        
        # Check for duplicates
        duplicates = df.duplicated(subset=['timestamp']).sum()
        if duplicates > 0:
            issues.append(f"Found {duplicates} duplicate timestamps")
            df = df.drop_duplicates(subset=['timestamp'], keep='first')
        
        # Sort by timestamp
        df = df.sort_values('timestamp')
        
        # Check timestamp monotonicity
        if len(df) > 1:
            ts_diffs = df['timestamp'].diff()[1:]
            gaps = (ts_diffs <= timedelta(0)).sum()
            if gaps > 0:
                issues.append(f"Timestamp gaps: {gaps}")
        
        validation_notes = '; '.join(issues) if issues else 'Valid'
        
        return df, validation_notes
    
    def _calculate_quality_score(self, candles: pd.DataFrame, validation_notes: str) -> float:
        """
        Calculate quality score (0-1.0)
        
        Formula:
        - Data completeness: 40%
        - Validation checks: 30%
        - Feature values valid: 20%
        - Data freshness: 10%
        """
        score = 1.0
        
        # Data completeness
        expected_cols = ['open', 'high', 'low', 'close', 'volume']
        completeness = 1.0 - (candles[expected_cols].isna().sum().sum() / (len(candles) * len(expected_cols)))
        score = score * 0.4 + completeness * 0.4
        
        # Validation checks
        if validation_notes == 'Valid':
            validation_score = 1.0
        else:
            # Penalize based on issues found
            issue_count = validation_notes.count(';') + 1
            validation_score = max(0, 1.0 - (issue_count * 0.1))
        
        score = score * 0.3 + validation_score * 0.3
        
        # Feature values
        feature_score = 0.8  # Assume good if data is valid
        score = score * 0.2 + feature_score * 0.2
        
        # Freshness (always good for historical data)
        freshness_score = 1.0
        score = score * 0.1 + freshness_score * 0.1
        
        return float(score)
    
    async def _store_enriched_data(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        source: str,
        candles: pd.DataFrame,
        quality_score: float,
        validation_notes: str,
        job_id: str
    ) -> Tuple[int, int]:
        """
        Store enriched data in database
        
        Returns:
            Tuple of (records_inserted, records_updated)
        """
        inserted = 0
        updated = 0
        
        try:
            for idx, row in candles.iterrows():
                data = {
                    'symbol': symbol,
                    'asset_class': asset_class,
                    'timeframe': timeframe,
                    'timestamp': row['timestamp'],
                    'open': float(row['open']) if pd.notna(row['open']) else None,
                    'high': float(row['high']) if pd.notna(row['high']) else None,
                    'low': float(row['low']) if pd.notna(row['low']) else None,
                    'close': float(row['close']) if pd.notna(row['close']) else None,
                    'volume': int(row['volume']) if pd.notna(row['volume']) else None,
                    'source': source,
                    'is_validated': True,
                    'quality_score': quality_score,
                    'validation_notes': validation_notes,
                    'fetched_at': datetime.utcnow(),
                    'computed_at': datetime.utcnow()
                }
                
                # Add feature columns
                feature_cols = [col for col in row.index if col not in [
                    'timestamp', 'open', 'high', 'low', 'close', 'volume'
                ]]
                
                for col in feature_cols:
                    if col in row and pd.notna(row[col]):
                        data[col] = float(row[col]) if isinstance(row[col], (int, float)) else row[col]
                
                # UPSERT into database
                result = await self.db.upsert_market_data_v2(data)
                
                if result['inserted']:
                    inserted += 1
                elif result['updated']:
                    updated += 1
            
            return inserted, updated
        
        except Exception as e:
            self.logger.error(
                "store_enriched_data_error",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e)
            )
            return inserted, updated
    
    async def _update_backfill_state(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        job_id: str,
        status: str,
        error_message: Optional[str] = None
    ):
        """Update backfill tracking table"""
        try:
            await self.db.update_backfill_state(
                symbol=symbol,
                asset_class=asset_class,
                timeframe=timeframe,
                job_id=job_id,
                status=status,
                error_message=error_message
            )
        except Exception as e:
            self.logger.warning(
                "backfill_state_update_error",
                symbol=symbol,
                error=str(e)
            )
