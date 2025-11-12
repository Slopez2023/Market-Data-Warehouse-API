"""
Feature Service - Generates ML features from trading data
Integrates dividends, earnings, news sentiment, and IV data
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import math

logger = logging.getLogger(__name__)


class FeatureService:
    """Service for calculating ML features across all data types"""

    def __init__(self, db):
        self.db = db

    # ==================== DIVIDEND FEATURES ====================

    async def calculate_dividend_yield(
        self, symbol: str, current_price: float, period_days: int = 365
    ) -> Optional[float]:
        """
        Calculate trailing twelve-month (or custom period) dividend yield.

        Args:
            symbol: Stock ticker
            current_price: Current stock price
            period_days: Period to sum dividends (default 365 = TTM)

        Returns:
            Dividend yield as percentage (e.g., 2.5 for 2.5%)
        """
        if current_price <= 0:
            return None

        query = """
        SELECT SUM(dividend_amount) as total_dividends
        FROM dividends
        WHERE symbol = $1
        AND ex_date >= NOW()::date - INTERVAL '1 day' * $2
        AND dividend_amount > 0
        """

        try:
            result = await self.db.fetchrow(query, symbol, period_days)
            if result and result["total_dividends"]:
                yield_pct = (result["total_dividends"] / current_price) * 100
                return yield_pct
        except Exception as e:
            logger.error(f"Error calculating dividend yield: {e}")

        return None

    async def get_dividend_frequency(
        self, symbol: str, days_back: int = 1095
    ) -> Optional[Dict]:
        """
        Analyze dividend payment frequency and consistency.

        Returns:
            Dict with frequency, consistency score, etc.
        """
        query = """
        SELECT 
            COUNT(*) as num_dividends,
            AVG(dividend_amount) as avg_dividend,
            STDDEV(dividend_amount) as div_stddev,
            MIN(dividend_amount) as min_dividend,
            MAX(dividend_amount) as max_dividend,
            MAX(ex_date) - MIN(ex_date) as days_span
        FROM dividends
        WHERE symbol = $1
        AND ex_date >= NOW()::date - INTERVAL '1 day' * $2
        """

        try:
            result = await self.db.fetchrow(query, symbol, days_back)
            if result:
                data = dict(result)

                # Calculate consistency score (low std relative to mean)
                if data.get("avg_dividend") and data.get("div_stddev"):
                    consistency = 1 - (
                        data["div_stddev"] / data["avg_dividend"]
                    )
                    data["consistency_score"] = max(
                        0, min(1, consistency)
                    )

                return data
        except Exception as e:
            logger.error(f"Error calculating dividend frequency: {e}")

        return None

    # ==================== EARNINGS FEATURES ====================

    async def calculate_earnings_beat_rate(
        self, symbol: str, lookback_quarters: int = 8
    ) -> Optional[Dict]:
        """
        Calculate EPS and revenue beat rate over recent earnings.

        Returns:
            Dict with beat_rate, avg_surprise, etc.
        """
        query = """
        SELECT 
            COUNT(*) as total_earnings,
            SUM(CASE WHEN surprise_eps > 0 THEN 1 ELSE 0 END) as eps_beats,
            SUM(CASE WHEN surprise_revenue > 0 THEN 1 ELSE 0 END) as revenue_beats,
            AVG(surprise_eps_pct) as avg_eps_surprise_pct,
            AVG(surprise_revenue_pct) as avg_revenue_surprise_pct,
            STDDEV(surprise_eps_pct) as eps_surprise_std,
            AVG(ABS(surprise_eps_pct)) as avg_abs_eps_surprise_pct
        FROM earnings
        WHERE symbol = $1
        AND fiscal_year * 4 + fiscal_quarter >= 
            (EXTRACT(YEAR FROM NOW())::INT * 4 + 
             CEIL(EXTRACT(MONTH FROM NOW()) / 3.0)::INT - $2)
        AND surprise_eps IS NOT NULL
        """

        try:
            result = await self.db.fetchrow(query, symbol, lookback_quarters)
            if result:
                data = dict(result)
                total = data.get("total_earnings", 0)

                if total > 0:
                    data["eps_beat_rate"] = (
                        data.get("eps_beats", 0) / total
                    ) * 100
                    data["revenue_beat_rate"] = (
                        data.get("revenue_beats", 0) / total
                    ) * 100

                return data
        except Exception as e:
            logger.error(f"Error calculating beat rate: {e}")

        return None

    async def get_upcoming_earnings_date(
        self, symbol: str
    ) -> Optional[Dict]:
        """Get next scheduled earnings date and estimated time."""
        query = """
        SELECT 
            earnings_date,
            earnings_time,
            estimated_eps,
            estimated_revenue,
            EXTRACT(DAY FROM earnings_date - NOW()::date) as days_until_earnings
        FROM earnings
        WHERE symbol = $1
        AND earnings_date > NOW()::date
        ORDER BY earnings_date ASC
        LIMIT 1
        """

        try:
            result = await self.db.fetchrow(query, symbol)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error fetching upcoming earnings: {e}")
            return None

    async def get_earnings_volatility_pattern(
        self, symbol: str, lookback_days: int = 90
    ) -> Optional[Dict]:
        """
        Analyze price volatility around earnings announcements.

        Returns:
            Dict with avg_1d_move, avg_5d_move, etc.
        """
        query = """
        SELECT 
            AVG(ABS(earnings_volatility_1d)) as avg_1d_move,
            AVG(ABS(earnings_volatility_5d)) as avg_5d_move,
            MAX(ABS(earnings_volatility_1d)) as max_1d_move,
            COUNT(*) as num_events
        FROM (
            SELECT 
                e.symbol,
                e.earnings_date,
                -- Would calculate volatility from market_data around earnings_date
                0 as earnings_volatility_1d,
                0 as earnings_volatility_5d
            FROM earnings e
            WHERE e.symbol = $1
            AND e.earnings_date >= NOW()::date - INTERVAL '1 day' * $2
        ) subq
        """

        try:
            result = await self.db.fetchrow(query, symbol, lookback_days)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting earnings volatility pattern: {e}")
            return None

    # ==================== SENTIMENT FEATURES ====================

    async def get_sentiment_features(
        self, symbol: str, lookback_days: int = 30
    ) -> Optional[Dict]:
        """
        Get news sentiment aggregate features for ML.

        Returns:
            Dict with avg_sentiment, trend, distribution, etc.
        """
        query = """
        SELECT 
            AVG(sentiment_score) as avg_sentiment_score,
            STDDEV(sentiment_score) as sentiment_volatility,
            COUNT(*) as article_count,
            SUM(CASE WHEN sentiment_label = 'bullish' THEN 1 ELSE 0 END) as bullish_count,
            SUM(CASE WHEN sentiment_label = 'neutral' THEN 1 ELSE 0 END) as neutral_count,
            SUM(CASE WHEN sentiment_label = 'bearish' THEN 1 ELSE 0 END) as bearish_count,
            -- Trend detection
            (SELECT AVG(sentiment_score) FROM news n2 
             WHERE n2.symbol = $1 AND n2.published_at >= NOW() - INTERVAL '7 days') as recent_sentiment,
            (SELECT AVG(sentiment_score) FROM news n3 
             WHERE n3.symbol = $1 AND n3.published_at < NOW() - INTERVAL '7 days' 
             AND n3.published_at >= NOW() - INTERVAL '14 days') as prior_sentiment
        FROM news n1
        WHERE n1.symbol = $1
        AND n1.published_at >= NOW() - INTERVAL '1 day' * $2
        """

        try:
            result = await self.db.fetchrow(query, symbol, lookback_days)
            if result:
                data = dict(result)

                # Calculate sentiment trend
                recent = data.get("recent_sentiment")
                prior = data.get("prior_sentiment")
                if recent is not None and prior is not None:
                    if recent > prior + 0.05:
                        data["sentiment_trend"] = "improving"
                    elif recent < prior - 0.05:
                        data["sentiment_trend"] = "declining"
                    else:
                        data["sentiment_trend"] = "stable"

                # Calculate distribution percentages
                total = data.get("article_count", 0)
                if total > 0:
                    data["bullish_pct"] = (
                        data.get("bullish_count", 0) / total
                    ) * 100
                    data["neutral_pct"] = (
                        data.get("neutral_count", 0) / total
                    ) * 100
                    data["bearish_pct"] = (
                        data.get("bearish_count", 0) / total
                    ) * 100

                return data
        except Exception as e:
            logger.error(f"Error getting sentiment features: {e}")

        return None

    # ==================== VOLATILITY FEATURES ====================

    async def get_volatility_regime(
        self, symbol: str, quote_date: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get current volatility regime classification.

        Returns:
            Dict with regime, iv_percentile, iv_hv_ratio, etc.
        """
        query = """
        SELECT 
            regime,
            iv_level,
            iv_percentile_52w,
            iv_zscore,
            hv_30d,
            hv_252d,
            iv_hv_ratio
        FROM volatility_regime
        WHERE symbol = $1
        """

        if quote_date:
            query += " AND quote_date = $2"
            params = [symbol, quote_date]
        else:
            query += " ORDER BY quote_date DESC LIMIT 1"
            params = [symbol]

        try:
            result = await self.db.fetchrow(query, *params)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error getting volatility regime: {e}")

        return None

    async def get_iv_percentile(
        self, symbol: str, lookback_days: int = 252
    ) -> Optional[float]:
        """Get IV percentile rank over lookback period."""
        query = """
        SELECT 
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY iv_level) as median_iv,
            COUNT(*) as data_points
        FROM volatility_regime
        WHERE symbol = $1
        AND quote_date >= NOW()::date - INTERVAL '1 day' * $2
        """

        try:
            result = await self.db.fetchrow(query, symbol, lookback_days)
            if result:
                return dict(result)
        except Exception as e:
            logger.error(f"Error getting IV percentile: {e}")

        return None

    # ==================== COMPOSITE FEATURES ====================

    async def get_composite_features(
        self, symbol: str
    ) -> Optional[Dict]:
        """
        Get all features for a symbol (for ML models).

        This is the primary feature vector for trading ML models.
        """
        try:
            current_price = await self._get_current_price(symbol)

            features = {
                "symbol": symbol,
                "timestamp": datetime.utcnow().isoformat(),
                # Fundamental features
                "dividend_yield": await self.calculate_dividend_yield(
                    symbol, current_price
                )
                if current_price
                else None,
                "dividend_frequency": await self.get_dividend_frequency(symbol),
                # Earnings features
                "earnings_beat_rate": await self.calculate_earnings_beat_rate(
                    symbol
                ),
                "upcoming_earnings": await self.get_upcoming_earnings_date(
                    symbol
                ),
                # Sentiment features
                "sentiment": await self.get_sentiment_features(symbol),
                # Volatility features
                "volatility_regime": await self.get_volatility_regime(
                    symbol
                ),
                "iv_metrics": await self.get_iv_percentile(symbol),
            }

            return features

        except Exception as e:
            logger.error(f"Error getting composite features: {e}")
            return None

    # ==================== HELPER METHODS ====================

    async def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get the most recent close price for a symbol."""
        query = """
        SELECT close
        FROM market_data
        WHERE symbol = $1
        AND timeframe = '1d'
        ORDER BY timestamp DESC
        LIMIT 1
        """

        try:
            result = await self.db.fetchrow(query, symbol)
            return result["close"] if result else None
        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return None

    async def calculate_feature_importance(
        self, symbols: List[str]
    ) -> Dict[str, float]:
        """
        Calculate correlation of each feature with price movements.
        (Would typically use a separate ML pipeline for this)
        """
        # Placeholder for more sophisticated feature importance calculation
        return {
            "dividend_yield": 0.15,
            "earnings_beat_rate": 0.25,
            "sentiment_score": 0.20,
            "volatility_regime": 0.18,
            "iv_percentile": 0.12,
            "upcoming_earnings": 0.10,
        }

    async def get_feature_vector_for_backtest(
        self, symbol: str, timestamp: int
    ) -> Optional[Dict]:
        """
        Get feature vector at a specific point in time (for backtesting).

        Returns:
            Dict suitable for ML model input
        """
        # Would need to implement historical feature retrieval
        # For now, returns current features
        return await self.get_composite_features(symbol)
