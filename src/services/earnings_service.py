"""
Earnings Service - Handles earnings data operations and analysis
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import asyncpg

logger = logging.getLogger(__name__)


class EarningsService:
    """Service for managing earnings data and metrics"""

    def __init__(self, db):
        self.db = db

    async def insert_earnings_batch(
        self, earnings_list: List[Dict]
    ) -> Tuple[int, int]:
        """
        Insert or update earnings records.

        Args:
            earnings_list: List of earnings dicts with required fields:
                - symbol, earnings_date, earnings_time
                - estimated_eps, actual_eps (optional)
                - estimated_revenue, actual_revenue (optional)

        Returns:
            (inserted_count, updated_count)
        """
        inserted = 0
        updated = 0

        for earnings in earnings_list:
            try:
                symbol = earnings.get("symbol")
                earnings_date = earnings.get("earnings_date")

                if not symbol or not earnings_date:
                    logger.warning(f"Missing symbol or earnings_date: {earnings}")
                    continue

                # Calculate surprises if both estimate and actual exist
                surprise_eps = None
                surprise_eps_pct = None
                if (
                    earnings.get("estimated_eps")
                    and earnings.get("actual_eps") is not None
                ):
                    surprise_eps = (
                        earnings.get("actual_eps")
                        - earnings.get("estimated_eps")
                    )
                    if earnings.get("estimated_eps") != 0:
                        surprise_eps_pct = (
                            surprise_eps / earnings.get("estimated_eps")
                        ) * 100

                surprise_revenue = None
                surprise_revenue_pct = None
                if (
                    earnings.get("estimated_revenue")
                    and earnings.get("actual_revenue") is not None
                ):
                    surprise_revenue = (
                        earnings.get("actual_revenue")
                        - earnings.get("estimated_revenue")
                    )
                    if earnings.get("estimated_revenue") != 0:
                        surprise_revenue_pct = (
                            surprise_revenue
                            / earnings.get("estimated_revenue")
                        ) * 100

                query = """
                INSERT INTO earnings (
                    symbol, earnings_date, earnings_time,
                    fiscal_year, fiscal_quarter,
                    estimated_eps, estimated_revenue,
                    actual_eps, actual_revenue,
                    surprise_eps, surprise_eps_pct,
                    surprise_revenue, surprise_revenue_pct,
                    prior_eps, prior_revenue,
                    conference_call_url, data_source, confirmed
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9,
                    $10, $11, $12, $13, $14, $15, $16, $17, $18
                )
                ON CONFLICT (symbol, earnings_date)
                DO UPDATE SET
                    earnings_time = COALESCE(EXCLUDED.earnings_time, earnings.earnings_time),
                    actual_eps = COALESCE(EXCLUDED.actual_eps, earnings.actual_eps),
                    actual_revenue = COALESCE(EXCLUDED.actual_revenue, earnings.actual_revenue),
                    surprise_eps = COALESCE(EXCLUDED.surprise_eps, earnings.surprise_eps),
                    surprise_eps_pct = COALESCE(EXCLUDED.surprise_eps_pct, earnings.surprise_eps_pct),
                    surprise_revenue = COALESCE(EXCLUDED.surprise_revenue, earnings.surprise_revenue),
                    surprise_revenue_pct = COALESCE(EXCLUDED.surprise_revenue_pct, earnings.surprise_revenue_pct),
                    confirmed = COALESCE(EXCLUDED.confirmed, earnings.confirmed),
                    updated_at = NOW()
                RETURNING 1
                """

                params = (
                    symbol,
                    earnings_date,
                    earnings.get("earnings_time"),
                    earnings.get("fiscal_year"),
                    earnings.get("fiscal_quarter"),
                    earnings.get("estimated_eps"),
                    earnings.get("estimated_revenue"),
                    earnings.get("actual_eps"),
                    earnings.get("actual_revenue"),
                    surprise_eps,
                    surprise_eps_pct,
                    surprise_revenue,
                    surprise_revenue_pct,
                    earnings.get("prior_eps"),
                    earnings.get("prior_revenue"),
                    earnings.get("conference_call_url"),
                    earnings.get("data_source", "polygon"),
                    earnings.get("confirmed", False),
                )

                result = await self.db.fetch(query, *params)
                if result:
                    if "EXCLUDED" in query:
                        updated += 1
                    else:
                        inserted += 1

            except Exception as e:
                logger.error(f"Error inserting earnings for {symbol}: {e}")

        return inserted, updated

    async def get_earnings_by_symbol(
        self,
        symbol: str,
        days_back: int = 365,
        include_estimates: bool = False,
    ) -> List[Dict]:
        """
        Get earnings history for a symbol.

        Args:
            symbol: Stock ticker
            days_back: Look back period in days
            include_estimates: Include estimate history

        Returns:
            List of earnings records with surprises
        """
        query = """
        SELECT 
            id, symbol, earnings_date, earnings_time,
            fiscal_year, fiscal_quarter,
            estimated_eps, actual_eps, surprise_eps, surprise_eps_pct,
            estimated_revenue, actual_revenue, surprise_revenue, surprise_revenue_pct,
            prior_eps, prior_revenue,
            conference_call_url, confirmed, created_at
        FROM earnings
        WHERE symbol = $1
        AND earnings_date >= NOW() - INTERVAL '1 day' * $2
        ORDER BY earnings_date DESC
        """

        try:
            records = await self.db.fetch(query, symbol, days_back)
            return [dict(r) for r in records]
        except Exception as e:
            logger.error(f"Error fetching earnings for {symbol}: {e}")
            return []

    async def get_upcoming_earnings(
        self, days_ahead: int = 30, symbols: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Get upcoming earnings announcements.

        Args:
            days_ahead: Days in advance to look
            symbols: Filter by symbols (optional)

        Returns:
            List of upcoming earnings
        """
        where_clause = (
            "AND symbol = ANY($2)" if symbols else "AND 1=1"
        )
        params = [days_ahead] + ([symbols] if symbols else [])

        query = f"""
        SELECT 
            symbol, earnings_date, earnings_time,
            fiscal_year, fiscal_quarter,
            estimated_eps, estimated_revenue,
            conference_call_url
        FROM earnings
        WHERE earnings_date > NOW()
        AND earnings_date <= NOW() + INTERVAL '1 day' * $1
        {where_clause}
        ORDER BY earnings_date ASC
        """

        try:
            records = await self.db.fetch(query, *params)
            return [dict(r) for r in records]
        except Exception as e:
            logger.error(f"Error fetching upcoming earnings: {e}")
            return []

    async def get_earnings_summary(self, symbol: str) -> Optional[Dict]:
        """
        Get aggregated earnings statistics for a symbol.

        Returns:
            Dict with avg_eps_surprise, positive_surprises, etc.
        """
        query = """
        SELECT 
            total_earnings,
            avg_eps_surprise_pct,
            avg_revenue_surprise_pct,
            positive_eps_surprises,
            positive_revenue_surprises,
            latest_earnings,
            recent_earnings_count
        FROM mv_earnings_summary
        WHERE symbol = $1
        """

        try:
            result = await self.db.fetchrow(query, symbol)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error fetching earnings summary for {symbol}: {e}")
            return None

    async def get_earnings_surprises(
        self, symbol: str, days_back: int = 252
    ) -> Dict:
        """
        Calculate earnings surprise metrics (hit rate, avg surprise, etc.).

        Args:
            symbol: Stock ticker
            days_back: Historical period to analyze

        Returns:
            Dict with surprise metrics
        """
        query = """
        SELECT 
            COUNT(*) as total_beats,
            SUM(CASE WHEN surprise_eps > 0 THEN 1 ELSE 0 END) as eps_beats,
            SUM(CASE WHEN surprise_revenue > 0 THEN 1 ELSE 0 END) as revenue_beats,
            AVG(ABS(surprise_eps_pct)) as avg_abs_eps_surprise_pct,
            AVG(ABS(surprise_revenue_pct)) as avg_abs_revenue_surprise_pct,
            AVG(surprise_eps_pct) as avg_eps_surprise_pct,
            AVG(surprise_revenue_pct) as avg_revenue_surprise_pct,
            STDDEV(surprise_eps_pct) as eps_surprise_volatility,
            STDDEV(surprise_revenue_pct) as revenue_surprise_volatility
        FROM earnings
        WHERE symbol = $1
        AND earnings_date >= NOW() - INTERVAL '1 day' * $2
        AND surprise_eps_pct IS NOT NULL
        """

        try:
            result = await self.db.fetchrow(query, symbol, days_back)
            if result:
                data = dict(result)
                # Calculate hit rates
                total = data.get("total_beats", 0)
                if total > 0:
                    data["eps_beat_rate"] = (
                        (data.get("eps_beats", 0) / total) * 100
                    )
                    data["revenue_beat_rate"] = (
                        (data.get("revenue_beats", 0) / total) * 100
                    )
                return data
        except Exception as e:
            logger.error(f"Error calculating earnings surprises: {e}")

        return {}

    async def record_earnings_estimate_revision(
        self,
        earnings_id: int,
        estimate_date: str,
        estimated_eps: float,
        estimated_revenue: float,
        num_analysts: int = None,
    ) -> bool:
        """
        Record estimate revision for tracking consensus changes.

        Returns:
            True if successful
        """
        query = """
        INSERT INTO earnings_estimates (
            earnings_id, estimate_date, estimated_eps,
            estimated_revenue, num_analysts
        )
        VALUES ($1, $2, $3, $4, $5)
        """

        try:
            await self.db.execute(
                query,
                earnings_id,
                estimate_date,
                estimated_eps,
                estimated_revenue,
                num_analysts,
            )
            return True
        except Exception as e:
            logger.error(f"Error recording estimate revision: {e}")
            return False

    async def get_estimate_revisions(
        self, earnings_id: int
    ) -> List[Dict]:
        """Get historical estimate revisions for an earnings event."""
        query = """
        SELECT 
            estimate_date, estimated_eps, estimated_revenue,
            num_analysts, revision_direction, created_at
        FROM earnings_estimates
        WHERE earnings_id = $1
        ORDER BY estimate_date ASC
        """

        try:
            records = await self.db.fetch(query, earnings_id)
            return [dict(r) for r in records]
        except Exception as e:
            logger.error(f"Error fetching estimate revisions: {e}")
            return []
