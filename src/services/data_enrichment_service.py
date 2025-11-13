"""Data enrichment service for fetching and processing market data enrichments."""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio
from sqlalchemy import text

logger = logging.getLogger(__name__)


class DataEnrichmentService:
    """Service for enriching market data with external sources and computed features."""
    
    def __init__(self, db_service, config):
        """
        Initialize enrichment service.
        
        Args:
            db_service: Database service instance
            config: Configuration object
        """
        self.db = db_service
        self.config = config
    
    async def enrich_symbol(
        self,
        symbol: str,
        asset_class: str = 'stock',
        timeframes: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict:
        """
        Enrich data for a symbol across specified timeframes.
        
        Args:
            symbol: Asset symbol
            asset_class: Asset class (stock, crypto, etf)
            timeframes: List of timeframes to enrich
            start_date: Start date for enrichment
            end_date: End date for enrichment
            
        Returns:
            Dictionary with enrichment results
        """
        try:
            if not timeframes:
                timeframes = ['1d']
            
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=365)
            
            if not end_date:
                end_date = datetime.utcnow()
            
            results = {
                'symbol': symbol,
                'asset_class': asset_class,
                'timeframes': timeframes,
                'enrichments': [],
                'errors': []
            }
            
            # Fetch enrichments for each timeframe
            for timeframe in timeframes:
                try:
                    enrichment_data = await self._fetch_enrichments(
                        symbol, asset_class, timeframe, start_date, end_date
                    )
                    
                    # Store enrichment data
                    await self._store_enrichment_data(
                        symbol, timeframe, enrichment_data
                    )
                    
                    results['enrichments'].append({
                        'timeframe': timeframe,
                        'records_processed': len(enrichment_data),
                        'status': 'success'
                    })
                    
                except Exception as e:
                    logger.error(f"Error enriching {symbol} {timeframe}: {e}")
                    results['errors'].append({
                        'timeframe': timeframe,
                        'error': str(e)
                    })
            
            # Update enrichment status
            await self._update_enrichment_status(symbol, asset_class, results)
            
            return results
            
        except Exception as e:
            logger.error(f"Error enriching {symbol}: {e}")
            raise
    
    async def _fetch_enrichments(
        self,
        symbol: str,
        asset_class: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Fetch enrichment data from external sources."""
        enrichments = []
        
        try:
            # Fetch dividend data for stocks
            if asset_class == 'stock':
                dividends = await self._fetch_dividends(symbol, start_date, end_date)
                enrichments.extend(dividends)
            
            # Fetch earnings data for stocks
            if asset_class == 'stock':
                earnings = await self._fetch_earnings(symbol)
                enrichments.extend(earnings)
            
            # Fetch news
            news = await self._fetch_news(symbol, timeframe, start_date, end_date)
            enrichments.extend(news)
            
            # Compute technical features
            features = await self._compute_features(symbol, timeframe, start_date, end_date)
            enrichments.extend(features)
            
        except Exception as e:
            logger.error(f"Error fetching enrichments for {symbol}: {e}")
        
        return enrichments
    
    async def _fetch_dividends(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Fetch dividend data for a stock."""
        try:
            # This would normally call Polygon API or other dividend data source
            logger.debug(f"Fetching dividends for {symbol}")
            return []
        except Exception as e:
            logger.error(f"Error fetching dividends for {symbol}: {e}")
            return []
    
    async def _fetch_earnings(self, symbol: str) -> List[Dict]:
        """Fetch earnings data for a stock."""
        try:
            # This would normally call Polygon API or other earnings data source
            logger.debug(f"Fetching earnings for {symbol}")
            return []
        except Exception as e:
            logger.error(f"Error fetching earnings for {symbol}: {e}")
            return []
    
    async def _fetch_news(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Fetch news articles for a symbol."""
        try:
            # This would normally call news API
            logger.debug(f"Fetching news for {symbol}")
            return []
        except Exception as e:
            logger.error(f"Error fetching news for {symbol}: {e}")
            return []
    
    async def _compute_features(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """Compute technical features from OHLCV data."""
        try:
            session = self.db.SessionLocal()
            
            try:
                # Fetch OHLCV data
                data = session.execute(text("""
                    SELECT time, open, high, low, close, volume
                    FROM market_data
                    WHERE symbol = :symbol AND timeframe = :timeframe
                    AND time BETWEEN :start AND :end
                    ORDER BY time
                """), {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'start': start_date,
                    'end': end_date
                }).fetchall()
                
                features = []
                
                if len(data) > 0:
                    closes = [row[4] for row in data]
                    
                    # Compute moving averages
                    ma_20 = sum(closes[-20:]) / len(closes[-20:]) if len(closes) >= 20 else None
                    ma_50 = sum(closes[-50:]) / len(closes[-50:]) if len(closes) >= 50 else None
                    
                    # Compute volatility
                    if len(closes) > 1:
                        returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
                        volatility = (sum(r**2 for r in returns) / len(returns)) ** 0.5
                    else:
                        volatility = None
                    
                    features.append({
                        'type': 'technical_indicators',
                        'ma_20': ma_20,
                        'ma_50': ma_50,
                        'volatility': volatility
                    })
                
                return features
                
            finally:
                session.close()
        
        except Exception as e:
            logger.error(f"Error computing features for {symbol}: {e}")
            return []
    
    async def _store_enrichment_data(
        self,
        symbol: str,
        timeframe: str,
        enrichment_data: List[Dict]
    ) -> None:
        """Store enrichment data in database."""
        try:
            session = self.db.SessionLocal()
            
            try:
                for enrichment in enrichment_data:
                    # Store fetch log
                    session.execute(text("""
                        INSERT INTO enrichment_fetch_log
                        (symbol, source, timeframe, records_fetched, success, created_at)
                        VALUES (:symbol, :source, :timeframe, :records, :success, NOW())
                    """), {
                        'symbol': symbol,
                        'source': enrichment.get('source', 'internal'),
                        'timeframe': timeframe,
                        'records': len(enrichment_data),
                        'success': True
                    })
                
                session.commit()
            
            except Exception as e:
                session.rollback()
                logger.error(f"Error storing enrichment data: {e}")
            
            finally:
                session.close()
        
        except Exception as e:
            logger.error(f"Error storing enrichment data: {e}")
    
    async def _update_enrichment_status(
        self,
        symbol: str,
        asset_class: str,
        results: Dict
    ) -> None:
        """Update enrichment status for a symbol."""
        try:
            session = self.db.SessionLocal()
            
            try:
                # Check if status exists
                existing = session.execute(text("""
                    SELECT id FROM enrichment_status WHERE symbol = :symbol
                """), {'symbol': symbol}).first()
                
                if existing:
                    # Update existing status
                    session.execute(text("""
                        UPDATE enrichment_status
                        SET status = :status,
                            last_enrichment_time = NOW(),
                            updated_at = NOW()
                        WHERE symbol = :symbol
                    """), {
                        'symbol': symbol,
                        'status': 'completed' if not results['errors'] else 'warning'
                    })
                else:
                    # Insert new status
                    session.execute(text("""
                        INSERT INTO enrichment_status
                        (symbol, asset_class, status, last_enrichment_time, created_at, updated_at)
                        VALUES (:symbol, :asset_class, :status, NOW(), NOW(), NOW())
                    """), {
                        'symbol': symbol,
                        'asset_class': asset_class,
                        'status': 'completed' if not results['errors'] else 'warning'
                    })
                
                session.commit()
            
            except Exception as e:
                session.rollback()
                logger.error(f"Error updating enrichment status: {e}")
            
            finally:
                session.close()
        
        except Exception as e:
            logger.error(f"Error updating enrichment status: {e}")
    
    async def get_enrichment_status(self, symbol: str) -> Optional[Dict]:
        """Get current enrichment status for a symbol."""
        try:
            session = self.db.SessionLocal()
            
            try:
                status = session.execute(text("""
                    SELECT symbol, asset_class, status, last_enrichment_time,
                           records_available, quality_score
                    FROM enrichment_status
                    WHERE symbol = :symbol
                """), {'symbol': symbol}).first()
                
                if status:
                    return {
                        'symbol': status[0],
                        'asset_class': status[1],
                        'status': status[2],
                        'last_enrichment_time': status[3],
                        'records_available': status[4],
                        'quality_score': status[5]
                    }
                
                return None
            
            finally:
                session.close()
        
        except Exception as e:
            logger.error(f"Error getting enrichment status: {e}")
            return None
