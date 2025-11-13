#!/usr/bin/env python3
"""
Feature Engineering for Market Prediction Models

Combines OHLCV + fundamentals + news + indicators into ML features
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class FeatureEngineering:
    """Build ML features from raw market data"""
    
    @staticmethod
    def price_features(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """Price-based features from OHLCV"""
        df = ohlcv_df.copy()
        
        # Returns
        df['return_1d'] = df['close'].pct_change(1)
        df['return_5d'] = df['close'].pct_change(5)
        df['return_20d'] = df['close'].pct_change(20)
        
        # Price ranges
        df['high_low_ratio'] = (df['high'] - df['low']) / df['close']
        df['close_open_ratio'] = (df['close'] - df['open']) / df['open']
        
        # Volatility
        df['volatility_20'] = df['return_1d'].rolling(20).std()
        df['volatility_60'] = df['return_1d'].rolling(60).std()
        
        # Gap detection
        df['gap'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1)
        
        return df
    
    @staticmethod
    def volume_features(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """Volume-based features"""
        df = ohlcv_df.copy()
        
        # Volume changes
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        df['volume_trend'] = df['volume'].rolling(20).mean() / df['volume'].rolling(60).mean()
        
        # On-Balance Volume (OBV)
        df['obv'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        
        # Volume Price Trend
        df['vpt'] = (df['volume'] * df['close'].pct_change()).fillna(0).cumsum()
        
        return df
    
    @staticmethod
    def momentum_features(ohlcv_df: pd.DataFrame) -> pd.DataFrame:
        """Momentum and technical indicators"""
        df = ohlcv_df.copy()
        
        # Rate of Change
        df['roc_5'] = ((df['close'] - df['close'].shift(5)) / df['close'].shift(5)) * 100
        df['roc_10'] = ((df['close'] - df['close'].shift(10)) / df['close'].shift(10)) * 100
        
        # Momentum
        df['momentum_10'] = df['close'] - df['close'].shift(10)
        df['momentum_20'] = df['close'] - df['close'].shift(20)
        
        return df
    
    @staticmethod
    def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add pre-computed technical indicators"""
        # Assumes columns: rsi_14, macd, sma_20, sma_50, etc.
        
        if 'rsi_14' in df.columns:
            df['rsi_overbought'] = (df['rsi_14'] > 70).astype(int)
            df['rsi_oversold'] = (df['rsi_14'] < 30).astype(int)
        
        if 'macd' in df.columns:
            df['macd_signal_cross'] = (
                (df['macd'] > df['macd_signal']) & 
                (df['macd'].shift(1) <= df['macd_signal'].shift(1))
            ).astype(int)
        
        if 'sma_20' in df.columns and 'sma_50' in df.columns:
            df['sma_20_above_50'] = (df['sma_20'] > df['sma_50']).astype(int)
            df['sma_cross'] = (
                (df['sma_20'] > df['sma_50']) & 
                (df['sma_20'].shift(1) <= df['sma_50'].shift(1))
            ).astype(int)
        
        if 'bb_upper' in df.columns:
            df['bb_band_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
            df['bb_above_upper'] = (df['close'] > df['bb_upper']).astype(int)
            df['bb_below_lower'] = (df['close'] < df['bb_lower']).astype(int)
        
        return df
    
    @staticmethod
    def fundamental_features(df: pd.DataFrame, fundamentals: dict) -> pd.DataFrame:
        """Add fundamental data features"""
        # fundamentals: {symbol: {pe_ratio, pb_ratio, div_yield, market_cap, ...}}
        
        if not fundamentals:
            return df
        
        symbol = df.get('symbol', 'UNKNOWN')
        if symbol not in fundamentals:
            return df
        
        fund = fundamentals[symbol]
        
        df['pe_ratio'] = fund.get('pe_ratio')
        df['pb_ratio'] = fund.get('pb_ratio')
        df['dividend_yield'] = fund.get('dividend_yield')
        df['roe'] = fund.get('roe')
        df['roa'] = fund.get('roa')
        df['debt_to_equity'] = fund.get('debt_to_equity')
        
        return df
    
    @staticmethod
    def dividend_event_features(df: pd.DataFrame, dividends_df: pd.DataFrame) -> pd.DataFrame:
        """Add dividend event features"""
        
        if dividends_df.empty:
            df['days_to_dividend'] = np.nan
            df['dividend_upcoming'] = 0
            return df
        
        # Merge with date
        df['date'] = pd.to_datetime(df.index)
        dividends_df['ex_date'] = pd.to_datetime(dividends_df['ex_date'])
        
        def days_to_next_dividend(row_date):
            upcoming = dividends_df[dividends_df['ex_date'] > row_date]
            if upcoming.empty:
                return np.nan
            return (upcoming.iloc[0]['ex_date'] - row_date).days
        
        df['days_to_dividend'] = df['date'].apply(days_to_next_dividend)
        df['dividend_upcoming'] = (df['days_to_dividend'] <= 30).astype(int)
        
        return df.drop('date', axis=1)
    
    @staticmethod
    def earnings_event_features(df: pd.DataFrame, earnings_df: pd.DataFrame) -> pd.DataFrame:
        """Add earnings event features"""
        
        if earnings_df.empty:
            df['days_to_earnings'] = np.nan
            df['earnings_upcoming'] = 0
            df['recent_surprise'] = np.nan
            return df
        
        df['date'] = pd.to_datetime(df.index)
        earnings_df['earnings_date'] = pd.to_datetime(earnings_df['earnings_date'])
        
        def days_to_next_earnings(row_date):
            upcoming = earnings_df[earnings_df['earnings_date'] > row_date]
            if upcoming.empty:
                return np.nan
            return (upcoming.iloc[0]['earnings_date'] - row_date).days
        
        def recent_surprise(row_date):
            recent = earnings_df[earnings_df['earnings_date'] <= row_date].tail(1)
            if recent.empty:
                return np.nan
            return recent.iloc[0].get('surprise_percent')
        
        df['days_to_earnings'] = df['date'].apply(days_to_next_earnings)
        df['earnings_upcoming'] = (df['days_to_earnings'] <= 30).astype(int)
        df['recent_surprise'] = df['date'].apply(recent_surprise)
        
        return df.drop('date', axis=1)
    
    @staticmethod
    def news_sentiment_features(df: pd.DataFrame, news_df: pd.DataFrame, window_days: int = 5) -> pd.DataFrame:
        """Add news sentiment features"""
        
        if news_df.empty:
            df['recent_positive_news'] = 0
            df['recent_negative_news'] = 0
            df['news_count'] = 0
            return df
        
        df['date'] = pd.to_datetime(df.index)
        news_df['news_date'] = pd.to_datetime(news_df['news_date'])
        
        def count_sentiment(row_date, sentiment_type):
            recent_news = news_df[
                (news_df['news_date'] >= row_date - timedelta(days=window_days)) &
                (news_df['news_date'] <= row_date)
            ]
            if sentiment_type == 'positive':
                return len(recent_news[recent_news['sentiment'] == 'positive'])
            elif sentiment_type == 'negative':
                return len(recent_news[recent_news['sentiment'] == 'negative'])
            else:
                return len(recent_news)
        
        df['recent_positive_news'] = df['date'].apply(lambda x: count_sentiment(x, 'positive'))
        df['recent_negative_news'] = df['date'].apply(lambda x: count_sentiment(x, 'negative'))
        df['news_count'] = df['date'].apply(lambda x: count_sentiment(x, 'all'))
        
        return df.drop('date', axis=1)
    
    @staticmethod
    def options_iv_features(df: pd.DataFrame, iv_df: pd.DataFrame) -> pd.DataFrame:
        """Add options IV features"""
        
        if iv_df.empty:
            df['atm_call_iv'] = np.nan
            df['atm_put_iv'] = np.nan
            df['iv_skew'] = np.nan
            return df
        
        df['date'] = pd.to_datetime(df.index)
        iv_df['updated_at'] = pd.to_datetime(iv_df['updated_at'])
        
        # Get ATM IV
        def get_atm_iv(row_date, option_type):
            day_iv = iv_df[
                (iv_df['updated_at'].dt.date == row_date.date()) &
                (iv_df['option_type'] == option_type)
            ]
            
            if day_iv.empty:
                return np.nan
            
            close_price = row_date.get('close', 0)
            
            # Get closest to ATM
            day_iv['strike_diff'] = abs(day_iv['strike_price'] - close_price)
            atm = day_iv.nsmallest(1, 'strike_diff')
            
            return atm.iloc[0]['implied_volatility'] if not atm.empty else np.nan
        
        df['atm_call_iv'] = df.apply(lambda row: get_atm_iv(row, 'call'), axis=1)
        df['atm_put_iv'] = df.apply(lambda row: get_atm_iv(row, 'put'), axis=1)
        df['iv_skew'] = df['atm_put_iv'] - df['atm_call_iv']
        
        return df.drop('date', axis=1)
    
    @staticmethod
    def create_target(df: pd.DataFrame, horizon_days: int = 5) -> pd.Series:
        """Create target variable: will price go up in next N days?"""
        
        future_close = df['close'].shift(-horizon_days)
        target = (future_close > df['close']).astype(int)
        
        return target
    
    @staticmethod
    def create_regression_target(df: pd.DataFrame, horizon_days: int = 5) -> pd.Series:
        """Create regression target: what will be the return in N days?"""
        
        future_close = df['close'].shift(-horizon_days)
        target = (future_close - df['close']) / df['close']
        
        return target


def build_ml_dataset(
    ohlcv_df: pd.DataFrame,
    technical_df: pd.DataFrame = None,
    fundamentals: dict = None,
    dividends_df: pd.DataFrame = None,
    earnings_df: pd.DataFrame = None,
    news_df: pd.DataFrame = None,
    iv_df: pd.DataFrame = None,
    target_horizon: int = 5,
    regression: bool = False
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Build complete ML dataset with all features
    
    Returns:
        (features_df, target_series)
    """
    
    fe = FeatureEngineering()
    df = ohlcv_df.copy()
    
    # Price & volume features
    df = fe.price_features(df)
    df = fe.volume_features(df)
    df = fe.momentum_features(df)
    
    # Technical indicators
    if technical_df is not None:
        df = df.merge(technical_df, left_index=True, right_index=True, how='left')
    
    df = fe.add_technical_indicators(df)
    
    # Fundamental features
    if fundamentals:
        df = fe.fundamental_features(df, fundamentals)
    
    # Event features
    if dividends_df is not None:
        df = fe.dividend_event_features(df, dividends_df)
    
    if earnings_df is not None:
        df = fe.earnings_event_features(df, earnings_df)
    
    # Sentiment
    if news_df is not None:
        df = fe.news_sentiment_features(df, news_df)
    
    # Options
    if iv_df is not None:
        df = fe.options_iv_features(df, iv_df)
    
    # Create target
    if regression:
        target = fe.create_regression_target(df, target_horizon)
    else:
        target = fe.create_target(df, target_horizon)
    
    # Remove rows with NaN targets
    valid_idx = ~target.isna()
    df = df[valid_idx]
    target = target[valid_idx]
    
    # Fill NaN features with median
    df = df.fillna(df.median())
    
    return df, target
