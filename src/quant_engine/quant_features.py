"""
Quant Feature Engine: AI-ready price-based feature generation.

Generates financial features from OHLCV data:
- Returns: 1h, 4h, 1d, log returns
- Volatility: 20-period, 50-period, ATR
- Volume: rolling 20-period, volume ratio
- Market Structure: HH, HL, LH, LL, trend direction
- Regimes: volatility, trend, compression

All computations use pandas for efficiency and numerical stability.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)


class QuantFeatureEngine:
    """
    Generates AI-ready quant features from OHLCV data.
    
    Features are computed incrementally and efficiently.
    Handles NaN values gracefully with forward fill.
    """

    # Constants for lookback periods
    VOLATILITY_PERIODS = [20, 50]
    VOLUME_PERIODS = [20]
    ATR_PERIOD = 14

    @staticmethod
    def compute(df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute all quant features from OHLCV DataFrame.

        Args:
            df: DataFrame with columns [time, open, high, low, close, volume]
                Must be sorted by time (ascending)

        Returns:
            DataFrame with original OHLCV + computed features
        """
        if df.empty:
            return df

        # Ensure sorted by time
        df = df.sort_values("time").reset_index(drop=True)

        # Ensure numeric columns
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
        df["high"] = pd.to_numeric(df["high"], errors="coerce")
        df["low"] = pd.to_numeric(df["low"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")

        # Compute returns
        df = compute_returns(df)

        # Compute volatility
        df = compute_volatility(df)

        # Compute ATR
        df = compute_atr(df)

        # Compute volume features
        df = compute_volume_features(df)

        # Compute market structure
        df = compute_market_structure(df)

        # Compute regimes
        df = compute_regimes(df)

        return df


def compute_returns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute return features.

    Returns:
    - return_1h: 1-hour log return (if data supports it)
    - return_1d: Daily log return (previous close)
    - log_return: Intrabar log return (open to close)
    """
    # Simple log return (close to previous close)
    df["log_return"] = np.log(df["close"] / df["close"].shift(1))

    # 1-hour return (for intraday data, shift by ~60 bars at 1-min intervals)
    # For now, use 1-bar return as proxy for 1h
    df["return_1h"] = df["log_return"].copy()

    # 1-day return (previous close to current close)
    # Compute based on business days or calendar days
    df["return_1d"] = np.log(df["close"] / df["close"].shift(1))

    # Forward fill NaN values from beginning of series
    df["log_return"] = df["log_return"].fillna(0)
    df["return_1h"] = df["return_1h"].fillna(0)
    df["return_1d"] = df["return_1d"].fillna(0)

    return df


def compute_volatility(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute volatility features using rolling standard deviation.

    Returns:
    - volatility_20: 20-period rolling volatility (annualized)
    - volatility_50: 50-period rolling volatility (annualized)
    """
    # Use log returns for volatility calculation
    returns = np.log(df["close"] / df["close"].shift(1))

    # 20-period volatility
    volatility_20 = returns.rolling(window=20).std()
    # Annualize (assuming 252 trading days per year)
    df["volatility_20"] = volatility_20 * np.sqrt(252)

    # 50-period volatility
    volatility_50 = returns.rolling(window=50).std()
    df["volatility_50"] = volatility_50 * np.sqrt(252)

    # Forward fill NaN
    df["volatility_20"] = df["volatility_20"].bfill().fillna(0)
    df["volatility_50"] = df["volatility_50"].bfill().fillna(0)

    return df


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Compute Average True Range (ATR).

    ATR = EMA of True Range (14-period default)
    Used for volatility and position sizing.
    """
    # True Range = max(high - low, |high - prev_close|, |low - prev_close|)
    prev_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Compute EMA of TR
    atr = tr.ewm(span=period, adjust=False).mean()
    df["atr"] = atr

    # Forward fill NaN
    df["atr"] = df["atr"].bfill().fillna(0)

    return df


def compute_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute volume-based features.

    Returns:
    - rolling_volume_20: 20-period average volume
    - volume_ratio: Current volume / 20-period average
    """
    # 20-period rolling average volume
    rolling_vol_20 = df["volume"].rolling(window=20).mean()
    df["rolling_volume_20"] = rolling_vol_20.bfill().fillna(
        df["volume"].mean()
    )

    # Volume ratio (current / rolling average)
    df["volume_ratio"] = (
        df["volume"] / (df["rolling_volume_20"] + 1)
    )  # +1 to avoid division by zero

    return df


def compute_market_structure(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute market structure features (Higher High/Low, Lower High/Low).

    Returns:
    - hh: Higher High (1 if high > prev 5 highs, 0 else)
    - hl: Higher Low (1 if low > prev 5 lows, 0 else)
    - lh: Lower High (1 if high < prev 5 highs, 0 else)
    - ll: Lower Low (1 if low < prev 5 lows, 0 else)
    - trend_direction: 'up', 'down', or 'neutral'
    - structure_label: Market structure ('bullish', 'bearish', 'range')
    """
    # Look back 5 periods for comparison
    lookback = 5

    # Higher High / Lower High
    prev_highs = df["high"].shift(1)
    for i in range(2, lookback + 1):
        prev_highs = pd.concat(
            [prev_highs, df["high"].shift(i)], axis=1
        ).max(axis=1)

    df["hh"] = (df["high"] > prev_highs).astype(int)  # Higher High
    df["lh"] = (df["high"] < prev_highs).astype(int)  # Lower High

    # Higher Low / Lower Low
    prev_lows = df["low"].shift(1)
    for i in range(2, lookback + 1):
        prev_lows = pd.concat(
            [prev_lows, df["low"].shift(i)], axis=1
        ).min(axis=1)

    df["hl"] = (df["low"] > prev_lows).astype(int)  # Higher Low
    df["ll"] = (df["low"] < prev_lows).astype(int)  # Lower Low

    # Trend direction: based on recent close direction
    df["trend_direction"] = "neutral"
    recent_return = df["close"].pct_change(5)  # 5-bar return
    df.loc[recent_return > 0.01, "trend_direction"] = "up"
    df.loc[recent_return < -0.01, "trend_direction"] = "down"

    # Market structure label
    df["structure_label"] = "range"
    # Bullish: HH and HL pattern
    df.loc[(df["hh"] == 1) & (df["hl"] == 1), "structure_label"] = "bullish"
    # Bearish: LH and LL pattern
    df.loc[(df["lh"] == 1) & (df["ll"] == 1), "structure_label"] = "bearish"

    return df


def compute_regimes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute market regime features.

    Returns:
    - volatility_regime: 'low', 'medium', 'high' based on volatility percentile
    - trend_regime: 'uptrend', 'downtrend', 'ranging' based on EMA
    - compression_regime: 'compressed', 'expanded' based on Bollinger Bands
    """
    # Volatility regime (based on 50-period volatility percentile)
    vol_50_pctl = df["volatility_50"].rolling(window=50).quantile(0.5)
    df["volatility_regime"] = "medium"
    df.loc[df["volatility_50"] < vol_50_pctl * 0.7, "volatility_regime"] = "low"
    df.loc[df["volatility_50"] > vol_50_pctl * 1.3, "volatility_regime"] = "high"

    # Trend regime (EMA-based)
    ema_20 = df["close"].ewm(span=20, adjust=False).mean()
    ema_50 = df["close"].ewm(span=50, adjust=False).mean()
    df["trend_regime"] = "ranging"
    df.loc[ema_20 > ema_50, "trend_regime"] = "uptrend"
    df.loc[ema_20 < ema_50, "trend_regime"] = "downtrend"

    # Compression regime (Bollinger Bands width)
    sma_20 = df["close"].rolling(window=20).mean()
    std_20 = df["close"].rolling(window=20).std()
    bb_width = (std_20 * 2) / sma_20  # Width as % of price
    bb_width_pctl = bb_width.rolling(window=50).quantile(0.5)
    df["compression_regime"] = "expanded"
    df.loc[bb_width < bb_width_pctl * 0.7, "compression_regime"] = "compressed"

    # Forward fill NaN
    df["volatility_regime"] = df["volatility_regime"].fillna("medium")
    df["trend_regime"] = df["trend_regime"].fillna("ranging")
    df["compression_regime"] = df["compression_regime"].fillna("expanded")

    return df


def extract_numeric_features(df: pd.DataFrame) -> Dict[str, float]:
    """
    Extract latest numeric feature values from DataFrame.

    Converts Decimal and other types to float for JSON serialization.
    """
    if df.empty:
        return {}

    latest = df.iloc[-1]
    features = {
        "return_1h": float(latest.get("return_1h", 0)) if pd.notna(latest.get("return_1h")) else 0,
        "return_1d": float(latest.get("return_1d", 0)) if pd.notna(latest.get("return_1d")) else 0,
        "volatility_20": float(latest.get("volatility_20", 0)) if pd.notna(latest.get("volatility_20")) else 0,
        "volatility_50": float(latest.get("volatility_50", 0)) if pd.notna(latest.get("volatility_50")) else 0,
        "atr": float(latest.get("atr", 0)) if pd.notna(latest.get("atr")) else 0,
        "rolling_volume_20": int(latest.get("rolling_volume_20", 0)) if pd.notna(latest.get("rolling_volume_20")) else 0,
        "volume_ratio": float(latest.get("volume_ratio", 1)) if pd.notna(latest.get("volume_ratio")) else 1,
    }
    return features


def extract_categorical_features(df: pd.DataFrame) -> Dict[str, str]:
    """
    Extract latest categorical feature values from DataFrame.
    """
    if df.empty:
        return {}

    latest = df.iloc[-1]
    features = {
        "trend_direction": str(latest.get("trend_direction", "neutral")),
        "structure_label": str(latest.get("structure_label", "range")),
        "volatility_regime": str(latest.get("volatility_regime", "medium")),
        "trend_regime": str(latest.get("trend_regime", "ranging")),
        "compression_regime": str(latest.get("compression_regime", "expanded")),
    }
    return features
