"""
Options IV Service - Handles options chain data and implied volatility metrics
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import asyncpg
import math

logger = logging.getLogger(__name__)


class OptionsIVService:
    """Service for managing options IV data and volatility regime"""

    def __init__(self, db):
        self.db = db

    async def insert_options_chain_batch(
        self, options_list: List[Dict]
    ) -> Tuple[int, int]:
        """
        Insert or update options chain data.

        Args:
            options_list: List of option records with fields:
                - symbol, timestamp, quote_date, expiration_date
                - strike_price, option_type ('call' or 'put')
                - implied_volatility, delta, gamma, vega, theta, rho
                - bid_price, ask_price, volume, open_interest

        Returns:
            (inserted_count, updated_count)
        """
        inserted = 0
        updated = 0

        for option in options_list:
            try:
                symbol = option.get("symbol")
                timestamp = option.get("timestamp")
                expiration_date = option.get("expiration_date")
                strike = option.get("strike_price")
                option_type = option.get("option_type")

                if not all([symbol, timestamp, expiration_date, strike, option_type]):
                    logger.warning(f"Missing required option fields: {option}")
                    continue

                # Calculate DTE (Days to Expiration)
                quote_date = option.get("quote_date")
                if quote_date:
                    if isinstance(quote_date, str):
                        quote_dt = datetime.fromisoformat(quote_date)
                    else:
                        quote_dt = quote_date

                    if isinstance(expiration_date, str):
                        exp_dt = datetime.fromisoformat(expiration_date)
                    else:
                        exp_dt = expiration_date

                    dte = (exp_dt - quote_dt).days
                else:
                    dte = None

                # Calculate intrinsic and time value
                current_price = option.get("current_price")
                last_price = option.get("last_price", 0)
                intrinsic_value = None
                time_value = None

                if current_price and last_price:
                    if option_type.lower() == "call":
                        intrinsic_value = max(
                            0, current_price - strike
                        )
                    else:  # put
                        intrinsic_value = max(
                            0, strike - current_price
                        )
                    time_value = max(0, last_price - intrinsic_value)

                # Calculate probability ITM (simplified)
                iv = option.get("implied_volatility")
                probability_itm = None
                if iv and current_price:
                    # Simplified calculation
                    if option_type.lower() == "call":
                        moneyness = math.log(strike / current_price) if current_price > 0 else 0
                    else:
                        moneyness = math.log(current_price / strike) if strike > 0 else 0

                    from scipy.stats import norm
                    try:
                        probability_itm = (
                            norm.cdf(moneyness / (iv * math.sqrt(dte / 365)))
                            * 100
                            if dte else None
                        )
                    except:
                        probability_itm = None

                query = """
                INSERT INTO options_iv (
                    symbol, timestamp, quote_date, expiration_date, dte,
                    strike_price, option_type,
                    implied_volatility, iv_rank, iv_percentile,
                    delta, gamma, vega, theta, rho,
                    bid_price, ask_price, last_price, bid_size, ask_size,
                    volume, open_interest, intrinsic_value, time_value,
                    probability_itm
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                    $21, $22, $23, $24, $25
                )
                ON CONFLICT (symbol, timestamp, option_type, strike_price, expiration_date)
                DO UPDATE SET
                    bid_price = EXCLUDED.bid_price,
                    ask_price = EXCLUDED.ask_price,
                    last_price = EXCLUDED.last_price,
                    volume = EXCLUDED.volume,
                    open_interest = EXCLUDED.open_interest,
                    implied_volatility = EXCLUDED.implied_volatility
                """

                params = (
                    symbol,
                    timestamp,
                    option.get("quote_date"),
                    expiration_date,
                    dte,
                    strike,
                    option_type.lower(),
                    iv,
                    option.get("iv_rank"),
                    option.get("iv_percentile"),
                    option.get("delta"),
                    option.get("gamma"),
                    option.get("vega"),
                    option.get("theta"),
                    option.get("rho"),
                    option.get("bid_price"),
                    option.get("ask_price"),
                    last_price,
                    option.get("bid_size"),
                    option.get("ask_size"),
                    option.get("volume"),
                    option.get("open_interest"),
                    intrinsic_value,
                    time_value,
                    probability_itm,
                )

                await self.db.execute(query, *params)
                inserted += 1

            except Exception as e:
                logger.error(f"Error inserting options data for {symbol}: {e}")

        return inserted, 0

    async def insert_chain_snapshot(
        self, snapshot: Dict
    ) -> bool:
        """
        Insert snapshot of entire options chain for a symbol at a timestamp.

        Args:
            snapshot: Dict with symbol, timestamp, quote_date, and aggregated metrics

        Returns:
            True if successful
        """
        query = """
        INSERT INTO options_chain_snapshot (
            symbol, timestamp, quote_date,
            atm_iv_call, atm_iv_put, atm_iv_avg, iv_skew,
            total_call_volume, total_put_volume, total_open_interest,
            call_oi, put_oi, put_call_ratio,
            iv_volatility, term_structure_slope, vix_equivalent
        )
        VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16
        )
        ON CONFLICT (symbol, timestamp)
        DO UPDATE SET
            atm_iv_call = EXCLUDED.atm_iv_call,
            atm_iv_put = EXCLUDED.atm_iv_put,
            total_call_volume = EXCLUDED.total_call_volume,
            total_put_volume = EXCLUDED.total_put_volume
        """

        try:
            await self.db.execute(
                query,
                snapshot.get("symbol"),
                snapshot.get("timestamp"),
                snapshot.get("quote_date"),
                snapshot.get("atm_iv_call"),
                snapshot.get("atm_iv_put"),
                snapshot.get("atm_iv_avg"),
                snapshot.get("iv_skew"),
                snapshot.get("total_call_volume"),
                snapshot.get("total_put_volume"),
                snapshot.get("total_open_interest"),
                snapshot.get("call_oi"),
                snapshot.get("put_oi"),
                snapshot.get("put_call_ratio"),
                snapshot.get("iv_volatility"),
                snapshot.get("term_structure_slope"),
                snapshot.get("vix_equivalent"),
            )
            return True
        except Exception as e:
            logger.error(f"Error inserting chain snapshot: {e}")
            return False

    async def get_chain_for_symbol(
        self,
        symbol: str,
        expiration_date: str,
        timestamp: Optional[int] = None,
    ) -> List[Dict]:
        """
        Get options chain for a symbol and expiration.

        Args:
            symbol: Stock ticker
            expiration_date: Target expiration (YYYY-MM-DD)
            timestamp: Specific timestamp (optional, uses latest if not provided)

        Returns:
            List of option records
        """
        if timestamp:
            query = """
            SELECT 
                symbol, timestamp, strike_price, option_type,
                implied_volatility, delta, gamma, vega, theta, rho,
                bid_price, ask_price, last_price,
                volume, open_interest, dte
            FROM options_iv
            WHERE symbol = $1 AND expiration_date = $2 AND timestamp = $3
            ORDER BY strike_price ASC
            """
            params = [symbol, expiration_date, timestamp]
        else:
            query = """
            SELECT 
                symbol, timestamp, strike_price, option_type,
                implied_volatility, delta, gamma, vega, theta, rho,
                bid_price, ask_price, last_price,
                volume, open_interest, dte
            FROM options_iv
            WHERE symbol = $1 AND expiration_date = $2
            AND timestamp = (SELECT MAX(timestamp) FROM options_iv 
                            WHERE symbol = $1 AND expiration_date = $2)
            ORDER BY strike_price ASC
            """
            params = [symbol, expiration_date]

        try:
            records = await self.db.fetch(query, *params)
            return [dict(r) for r in records]
        except Exception as e:
            logger.error(f"Error fetching chain for {symbol}: {e}")
            return []

    async def get_iv_summary(
        self, symbol: str, quote_date: str
    ) -> Optional[Dict]:
        """Get daily IV summary for a symbol."""
        query = """
        SELECT 
            symbol, quote_date,
            atm_iv_call, atm_iv_put, atm_iv_avg,
            avg_iv, max_iv, min_iv, iv_std,
            total_volume, total_oi, call_oi, put_oi,
            num_expirations, min_dte, max_dte
        FROM mv_options_iv_summary
        WHERE symbol = $1 AND quote_date = $2
        """

        try:
            result = await self.db.fetchrow(query, symbol, quote_date)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error fetching IV summary: {e}")
            return None

    async def classify_volatility_regime(
        self, symbol: str, iv_level: float, quote_date: str
    ) -> str:
        """
        Classify volatility regime based on 52-week percentile.

        Returns: 'very_low', 'low', 'normal', 'high', 'very_high'
        """
        # Get 52-week IV history
        query = """
        SELECT 
            PERCENTILE_CONT(0.2) WITHIN GROUP (ORDER BY atm_iv_avg) as p20,
            PERCENTILE_CONT(0.4) WITHIN GROUP (ORDER BY atm_iv_avg) as p40,
            PERCENTILE_CONT(0.6) WITHIN GROUP (ORDER BY atm_iv_avg) as p60,
            PERCENTILE_CONT(0.8) WITHIN GROUP (ORDER BY atm_iv_avg) as p80
        FROM mv_options_iv_summary
        WHERE symbol = $1
        AND quote_date >= NOW()::date - INTERVAL '365 days'
        """

        try:
            result = await self.db.fetchrow(query, symbol)
            if result:
                p20 = result["p20"]
                p40 = result["p40"]
                p60 = result["p60"]
                p80 = result["p80"]

                if iv_level <= p20:
                    return "very_low"
                elif iv_level <= p40:
                    return "low"
                elif iv_level <= p60:
                    return "normal"
                elif iv_level <= p80:
                    return "high"
                else:
                    return "very_high"
        except Exception as e:
            logger.error(f"Error classifying volatility regime: {e}")

        return "normal"

    async def record_volatility_regime(
        self,
        symbol: str,
        quote_date: str,
        timestamp: int,
        iv_level: float,
        iv_percentile: float,
        hv_30d: float,
        hv_252d: float,
    ) -> bool:
        """Record daily volatility regime classification."""
        regime = await self.classify_volatility_regime(
            symbol, iv_level, quote_date
        )

        iv_hv_ratio = iv_level / hv_252d if hv_252d > 0 else 0
        iv_zscore = (
            (iv_level - hv_252d) / hv_252d
            if hv_252d > 0
            else 0
        )

        query = """
        INSERT INTO volatility_regime (
            symbol, quote_date, timestamp,
            iv_level, iv_percentile_52w, regime,
            iv_zscore, hv_30d, hv_252d, iv_hv_ratio
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (symbol, quote_date)
        DO UPDATE SET
            iv_level = EXCLUDED.iv_level,
            regime = EXCLUDED.regime,
            updated_at = NOW()
        """

        try:
            await self.db.execute(
                query,
                symbol,
                quote_date,
                timestamp,
                iv_level,
                iv_percentile,
                regime,
                iv_zscore,
                hv_30d,
                hv_252d,
                iv_hv_ratio,
            )
            return True
        except Exception as e:
            logger.error(f"Error recording volatility regime: {e}")
            return False

    async def get_volatility_regime(
        self, symbol: str, quote_date: Optional[str] = None
    ) -> Optional[Dict]:
        """Get volatility regime for a symbol."""
        if quote_date:
            query = """
            SELECT *
            FROM volatility_regime
            WHERE symbol = $1 AND quote_date = $2
            """
            params = [symbol, quote_date]
        else:
            query = """
            SELECT *
            FROM volatility_regime
            WHERE symbol = $1
            ORDER BY quote_date DESC
            LIMIT 1
            """
            params = [symbol]

        try:
            result = await self.db.fetchrow(query, *params)
            return dict(result) if result else None
        except Exception as e:
            logger.error(f"Error fetching volatility regime: {e}")
            return None

    async def get_iv_percentile_52w(
        self, symbol: str, iv_level: float
    ) -> float:
        """Calculate IV percentile rank over 52 weeks."""
        query = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN atm_iv_avg <= $2 THEN 1 ELSE 0 END) as below_count
        FROM mv_options_iv_summary
        WHERE symbol = $1
        AND quote_date >= NOW()::date - INTERVAL '365 days'
        """

        try:
            result = await self.db.fetchrow(query, symbol, iv_level)
            if result and result["total"] > 0:
                return (result["below_count"] / result["total"]) * 100
        except Exception as e:
            logger.error(f"Error calculating IV percentile: {e}")

        return 50.0

    async def get_iv_term_structure(
        self, symbol: str, timestamp: int
    ) -> Optional[Dict]:
        """Get IV term structure (near-term vs far-term comparison)."""
        query = """
        SELECT 
            CASE 
                WHEN dte <= 30 THEN 'near_term'
                WHEN dte <= 90 THEN 'mid_term'
                ELSE 'far_term'
            END as term,
            AVG(implied_volatility) as avg_iv,
            COUNT(*) as num_contracts
        FROM options_iv
        WHERE symbol = $1 AND timestamp = $2
        GROUP BY term
        ORDER BY term
        """

        try:
            records = await self.db.fetch(query, symbol, timestamp)
            if records:
                return {r["term"]: {"avg_iv": r["avg_iv"]} for r in records}
        except Exception as e:
            logger.error(f"Error fetching IV term structure: {e}")

        return None
