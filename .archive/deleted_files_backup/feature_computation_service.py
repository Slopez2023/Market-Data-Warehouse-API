"""
Technical Feature Computation Service
Computes 22 universal and crypto-specific features from OHLCV data
Optimized with NumPy/Pandas vectorized operations
"""

import numpy as np
import pandas as pd
from decimal import Decimal
from typing import Dict, Optional, Tuple
import logging

from src.services.structured_logging import StructuredLogger


class FeatureComputationService:
    """Compute technical indicators and features"""
    
    def __init__(self):
        self.logger = StructuredLogger(__name__)
    
    @staticmethod
    def compute_return_1h(close_price: float, prev_close: float) -> Optional[float]:
        """
        Compute 1-hour return
        Formula: (Close - PrevClose) / PrevClose
        
        Args:
            close_price: Current close price
            prev_close: Previous close price
            
        Returns:
            Return as decimal (e.g., 0.025 for 2.5%)
        """
        if prev_close <= 0 or pd.isna(prev_close) or pd.isna(close_price):
            return None
        
        return (close_price - prev_close) / prev_close
    
    @staticmethod
    def compute_return_1d(
        candles: pd.DataFrame,
        window: int = 1
    ) -> Optional[float]:
        """
        Compute 1-day return from multiple candles
        
        Args:
            candles: DataFrame with 'open', 'close' columns
            window: Number of candles for 1-day calculation
            
        Returns:
            Daily return or None if insufficient data
        """
        if len(candles) < window + 1:
            return None
        
        open_price = candles.iloc[-window]['open']
        close_price = candles.iloc[-1]['close']
        
        if open_price <= 0 or pd.isna(open_price) or pd.isna(close_price):
            return None
        
        return (close_price - open_price) / open_price
    
    @staticmethod
    def compute_volatility(
        candles: pd.DataFrame,
        window: int
    ) -> Optional[float]:
        """
        Compute rolling volatility (standard deviation of log returns)
        
        Args:
            candles: DataFrame with 'close' column
            window: Period for rolling calculation
            
        Returns:
            Volatility as annualized percentage or None
        """
        if len(candles) < window + 1:
            return None
        
        closes = candles['close'].astype(float)
        
        if closes.isna().any():
            closes = closes.fillna(method='ffill')
        
        # Calculate log returns
        log_returns = np.log(closes / closes.shift(1))
        
        # Calculate rolling std dev
        volatility = log_returns.rolling(window=window).std().iloc[-1]
        
        if pd.isna(volatility) or volatility <= 0:
            return None
        
        # Annualize for daily data (assuming 252 trading days)
        return float(volatility * np.sqrt(252))
    
    @staticmethod
    def compute_atr(
        candles: pd.DataFrame,
        period: int = 14
    ) -> Optional[float]:
        """
        Compute Average True Range
        
        Args:
            candles: DataFrame with 'high', 'low', 'close' columns
            period: ATR period (default: 14)
            
        Returns:
            ATR value or None
        """
        if len(candles) < period + 1:
            return None
        
        high = candles['high'].astype(float)
        low = candles['low'].astype(float)
        close = candles['close'].astype(float)
        
        # Calculate true range
        tr1 = high - low
        tr2 = np.abs(high - close.shift(1))
        tr3 = np.abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR as simple moving average
        atr = tr.rolling(window=period).mean().iloc[-1]
        
        return float(atr) if not pd.isna(atr) else None
    
    @staticmethod
    def compute_trend_direction(
        candles: pd.DataFrame,
        window: int = 5
    ) -> Optional[str]:
        """
        Determine trend direction based on moving average
        
        Args:
            candles: DataFrame with 'close' column
            window: Period for moving average
            
        Returns:
            'up', 'down', or 'neutral'
        """
        if len(candles) < window + 1:
            return None
        
        closes = candles['close'].astype(float)
        sma = closes.rolling(window=window).mean().iloc[-1]
        current_close = closes.iloc[-1]
        
        if pd.isna(sma) or pd.isna(current_close):
            return None
        
        threshold = 0.001  # 0.1% threshold to avoid false signals
        
        if current_close > sma * (1 + threshold):
            return 'up'
        elif current_close < sma * (1 - threshold):
            return 'down'
        else:
            return 'neutral'
    
    @staticmethod
    def compute_market_structure(
        candles: pd.DataFrame,
        window: int = 20
    ) -> Optional[str]:
        """
        Determine market structure (bullish, bearish, range)
        Based on HLC3 pivot point analysis
        
        Args:
            candles: DataFrame with 'high', 'low', 'close' columns
            window: Period for moving average
            
        Returns:
            'bullish', 'bearish', or 'range'
        """
        if len(candles) < window + 1:
            return None
        
        high = candles['high'].astype(float)
        low = candles['low'].astype(float)
        close = candles['close'].astype(float)
        
        # Calculate pivot point
        hlc3 = (high + low + close) / 3
        sma = hlc3.rolling(window=window).mean()
        
        if len(sma) < 2:
            return None
        
        current = sma.iloc[-1]
        prev = sma.iloc[-2]
        
        if pd.isna(current) or pd.isna(prev):
            return None
        
        # Compare current to previous for trend
        # Also check against recent extremes
        recent_high = high.iloc[-window:].max()
        recent_low = low.iloc[-window:].min()
        
        if current > prev and close.iloc[-1] > recent_high * 0.95:
            return 'bullish'
        elif current < prev and close.iloc[-1] < recent_low * 1.05:
            return 'bearish'
        else:
            return 'range'
    
    @staticmethod
    def compute_rolling_volume(
        candles: pd.DataFrame,
        window: int = 20
    ) -> Optional[float]:
        """
        Compute rolling average volume
        
        Args:
            candles: DataFrame with 'volume' column
            window: Period for rolling average
            
        Returns:
            Rolling volume as integer or None
        """
        if len(candles) < window:
            return None
        
        volumes = candles['volume'].astype(float)
        rolling_vol = volumes.rolling(window=window).mean().iloc[-1]
        
        return int(rolling_vol) if not pd.isna(rolling_vol) else None
    
    # Crypto-specific features
    
    @staticmethod
    def compute_delta(
        taker_buy_volume: float,
        taker_sell_volume: float
    ) -> Optional[float]:
        """
        Compute delta (buy volume - sell volume)
        Indicates buying/selling pressure
        
        Args:
            taker_buy_volume: Volume of buy market orders
            taker_sell_volume: Volume of sell market orders
            
        Returns:
            Delta value or None
        """
        if pd.isna(taker_buy_volume) or pd.isna(taker_sell_volume):
            return None
        
        delta = taker_buy_volume - taker_sell_volume
        total = taker_buy_volume + taker_sell_volume
        
        if total == 0:
            return 0.0
        
        # Normalize to -1 to 1
        return delta / total
    
    @staticmethod
    def compute_buy_sell_ratio(
        taker_buy_volume: float,
        taker_sell_volume: float
    ) -> Optional[float]:
        """
        Compute buy/sell volume ratio
        
        Args:
            taker_buy_volume: Volume of buy market orders
            taker_sell_volume: Volume of sell market orders
            
        Returns:
            Ratio (buy/sell) or None
        """
        if pd.isna(taker_sell_volume) or taker_sell_volume <= 0:
            return None
        
        if pd.isna(taker_buy_volume):
            return 0.0
        
        return taker_buy_volume / taker_sell_volume
    
    @staticmethod
    def compute_liquidation_intensity(
        liquidations_long: float,
        liquidations_short: float,
        volume: float
    ) -> Optional[float]:
        """
        Compute liquidation intensity (as % of volume)
        
        Args:
            liquidations_long: Long position liquidation volume
            liquidations_short: Short position liquidation volume
            volume: Total volume
            
        Returns:
            Liquidation intensity or None
        """
        if pd.isna(volume) or volume <= 0:
            return 0.0
        
        total_liquidations = 0
        if not pd.isna(liquidations_long):
            total_liquidations += liquidations_long
        if not pd.isna(liquidations_short):
            total_liquidations += liquidations_short
        
        return total_liquidations / volume
    
    @staticmethod
    def compute_volume_spike_score(
        current_volume: float,
        avg_volume: float
    ) -> Optional[float]:
        """
        Compute volume spike score
        Ratio of current to average volume
        
        Args:
            current_volume: Current candle volume
            avg_volume: Average volume (e.g., 20-period SMA)
            
        Returns:
            Spike score or None
        """
        if pd.isna(avg_volume) or avg_volume <= 0:
            return 0.0
        
        if pd.isna(current_volume):
            return 0.0
        
        return current_volume / avg_volume
    
    @staticmethod
    def compute_long_short_ratio(
        taker_buy_volume: float,
        taker_sell_volume: float
    ) -> Optional[float]:
        """
        Compute long/short open interest ratio
        
        Args:
            taker_buy_volume: Open long positions (approximated by buy volume)
            taker_sell_volume: Open short positions (approximated by sell volume)
            
        Returns:
            Ratio or None
        """
        if pd.isna(taker_sell_volume) or taker_sell_volume <= 0:
            return None
        
        if pd.isna(taker_buy_volume):
            return 0.0
        
        return taker_buy_volume / taker_sell_volume
    
    @staticmethod
    def compute_funding_rate_percentile(
        current_funding_rate: float,
        historical_rates: list
    ) -> Optional[float]:
        """
        Compute funding rate percentile
        Where the current rate sits relative to historical distribution
        
        Args:
            current_funding_rate: Current funding rate
            historical_rates: List of historical funding rates
            
        Returns:
            Percentile (0-100) or None
        """
        if not historical_rates or pd.isna(current_funding_rate):
            return None
        
        rates_array = np.array([r for r in historical_rates if not pd.isna(r)])
        
        if len(rates_array) == 0:
            return None
        
        percentile = (rates_array < current_funding_rate).sum() / len(rates_array) * 100
        return float(percentile)
    
    @staticmethod
    def compute_open_interest_change(
        current_oi: float,
        prev_oi: float
    ) -> Optional[float]:
        """
        Compute change in open interest
        
        Args:
            current_oi: Current open interest
            prev_oi: Previous open interest
            
        Returns:
            Percentage change or None
        """
        if pd.isna(prev_oi) or prev_oi <= 0 or pd.isna(current_oi):
            return None
        
        return (current_oi - prev_oi) / prev_oi
    
    def compute_all(
        self,
        candles: pd.DataFrame,
        asset_class: str = 'stock',
        crypto_data: Optional[Dict] = None
    ) -> pd.DataFrame:
        """
        Compute all features for a candle set
        
        Args:
            candles: DataFrame with OHLCV columns
            asset_class: 'stock', 'crypto', or 'etf'
            crypto_data: Optional dict with crypto-specific fields
            
        Returns:
            Original DataFrame with feature columns added
        """
        try:
            # Make a copy to avoid modifying original
            df = candles.copy()
            
            # Universal features
            df['return_1h'] = df.apply(
                lambda row: self.compute_return_1h(
                    row['close'],
                    df.shift(1).iloc[df.index.get_loc(row.name)]['close'] if df.index.get_loc(row.name) > 0 else row['open']
                ) if pd.notna(row['close']) else None,
                axis=1
            )
            
            # For 1h return, use vectorized approach
            df['return_1h'] = (df['close'] / df['close'].shift(1) - 1).replace([np.inf, -np.inf], None)
            
            # 1-day return (using open of current day to close)
            df['return_1d'] = (df['close'] / df['open'] - 1).replace([np.inf, -np.inf], None)
            
            # Volatility
            df['volatility_20'] = df.apply(
                lambda row: self.compute_volatility(
                    candles.iloc[max(0, df.index.get_loc(row.name) - 19):df.index.get_loc(row.name) + 1],
                    20
                ) if df.index.get_loc(row.name) >= 19 else None,
                axis=1
            )
            
            df['volatility_50'] = df.apply(
                lambda row: self.compute_volatility(
                    candles.iloc[max(0, df.index.get_loc(row.name) - 49):df.index.get_loc(row.name) + 1],
                    50
                ) if df.index.get_loc(row.name) >= 49 else None,
                axis=1
            )
            
            # ATR
            df['atr'] = df.apply(
                lambda row: self.compute_atr(
                    candles.iloc[max(0, df.index.get_loc(row.name) - 13):df.index.get_loc(row.name) + 1]
                ) if df.index.get_loc(row.name) >= 13 else None,
                axis=1
            )
            
            # Trend direction
            df['trend_direction'] = df.apply(
                lambda row: self.compute_trend_direction(
                    candles.iloc[max(0, df.index.get_loc(row.name) - 4):df.index.get_loc(row.name) + 1]
                ) if df.index.get_loc(row.name) >= 4 else None,
                axis=1
            )
            
            # Market structure
            df['market_structure'] = df.apply(
                lambda row: self.compute_market_structure(
                    candles.iloc[max(0, df.index.get_loc(row.name) - 19):df.index.get_loc(row.name) + 1]
                ) if df.index.get_loc(row.name) >= 19 else None,
                axis=1
            )
            
            # Rolling volume
            df['rolling_volume_20'] = df['volume'].rolling(window=20).mean()
            
            # Crypto-specific features
            if asset_class == 'crypto' and crypto_data:
                df['delta'] = df.apply(
                    lambda row: self.compute_delta(
                        crypto_data.get('taker_buy_volume'),
                        crypto_data.get('taker_sell_volume')
                    ),
                    axis=1
                )
                
                df['buy_sell_ratio'] = df.apply(
                    lambda row: self.compute_buy_sell_ratio(
                        crypto_data.get('taker_buy_volume'),
                        crypto_data.get('taker_sell_volume')
                    ),
                    axis=1
                )
                
                df['liquidation_intensity'] = df.apply(
                    lambda row: self.compute_liquidation_intensity(
                        crypto_data.get('liquidations_long'),
                        crypto_data.get('liquidations_short'),
                        row['volume']
                    ),
                    axis=1
                )
                
                df['volume_spike_score'] = self.compute_volume_spike_score(
                    df['volume'].iloc[-1],
                    df['volume'].rolling(window=20).mean().iloc[-1]
                )
                
                df['long_short_ratio'] = df.apply(
                    lambda row: self.compute_long_short_ratio(
                        crypto_data.get('taker_buy_volume'),
                        crypto_data.get('taker_sell_volume')
                    ),
                    axis=1
                )
                
                df['funding_rate_percentile'] = None  # Requires historical data
                df['exchange_inflow'] = None  # Requires external data
                df['open_interest_change'] = None  # Requires previous OI
            
            return df
        
        except Exception as e:
            self.logger.error(
                "feature_computation_error",
                asset_class=asset_class,
                error=str(e)
            )
            return candles
