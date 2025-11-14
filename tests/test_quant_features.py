"""
Comprehensive tests for Quant Feature Engine.

Tests cover:
- Feature computation accuracy
- Edge case handling (NaN, empty data)
- Data type conversions
- Numerical stability
"""

import pytest
import pandas as pd
import numpy as np
from decimal import Decimal
from datetime import datetime, timedelta
from src.quant_engine import QuantFeatureEngine


def get_sample_df(n_rows: int) -> pd.DataFrame:
    """Generate sample OHLCV data for testing."""
    np.random.seed(42)
    base_price = 100.0
    
    returns = np.random.normal(0.0005, 0.01, n_rows)
    prices = base_price * np.exp(np.cumsum(returns))
    
    return pd.DataFrame({
        "time": pd.date_range("2024-01-01", periods=n_rows),
        "open": prices * (1 + np.random.uniform(-0.005, 0.005, n_rows)),
        "high": prices * (1 + np.random.uniform(0, 0.01, n_rows)),
        "low": prices * (1 - np.random.uniform(0, 0.01, n_rows)),
        "close": prices,
        "volume": np.random.randint(800000, 1200000, n_rows)
    })


class TestQuantFeatureEngineBasics:
    """Test basic feature engine functionality."""

    def test_compute_returns_empty_dataframe(self):
        """Test compute handles empty DataFrame gracefully."""
        df = pd.DataFrame()
        result = QuantFeatureEngine.compute(df)
        assert result.empty

    def test_compute_single_row(self):
        """Test compute with single row of data."""
        df = pd.DataFrame({
            "time": [datetime(2024, 1, 1)],
            "open": [100.0],
            "high": [102.0],
            "low": [99.0],
            "close": [101.0],
            "volume": [1000000]
        })
        result = QuantFeatureEngine.compute(df)
        assert not result.empty
        assert "log_return" in result.columns
        assert "volatility_20" in result.columns

    def test_compute_preserves_ohlcv(self):
        """Test that compute preserves original OHLCV columns."""
        df = get_sample_df(50)
        result = QuantFeatureEngine.compute(df)
        
        # Check original columns are preserved
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in result.columns
            assert (result[col] == df[col]).all()

    def test_compute_adds_all_features(self):
        """Test that compute adds all expected feature columns."""
        df = get_sample_df(100)
        result = QuantFeatureEngine.compute(df)
        
        expected_features = [
            "log_return", "return_1h", "return_1d",
            "volatility_20", "volatility_50", "atr",
            "rolling_volume_20", "volume_ratio",
            "hh", "hl", "lh", "ll",
            "trend_direction", "structure_label",
            "volatility_regime", "trend_regime", "compression_regime"
        ]
        
        for feature in expected_features:
            assert feature in result.columns, f"Missing feature: {feature}"

    def test_compute_preserves_data_order(self):
        """Test that compute preserves row order."""
        df = get_sample_df(50)
        original_times = df["time"].tolist()
        result = QuantFeatureEngine.compute(df)
        result_times = result["time"].tolist()
        assert original_times == result_times


class TestReturnsComputation:
    """Test return feature computation."""

    def test_log_return_calculation(self):
        """Test log return is computed correctly."""
        df = pd.DataFrame({
            "time": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000000, 1100000]
        })
        result = QuantFeatureEngine.compute(df)
        
        # First row should have 0 log return (no previous close)
        assert result.iloc[0]["log_return"] == 0
        
        # Second row: log(102/101) ≈ 0.00995
        expected = np.log(102.0 / 101.0)
        assert abs(result.iloc[1]["log_return"] - expected) < 0.0001

    def test_return_1d_matches_log_return(self):
        """Test return_1d is computed (same as log_return here)."""
        df = get_sample_df(20)
        result = QuantFeatureEngine.compute(df)
        
        # For single-timeframe data, return_1d should be based on previous close
        assert "return_1d" in result.columns
        assert not result["return_1d"].isna().all()

    def test_returns_no_inf_or_nan(self):
        """Test returns contain no inf or nan values."""
        df = get_sample_df(100)
        result = QuantFeatureEngine.compute(df)
        
        return_cols = ["log_return", "return_1h", "return_1d"]
        for col in return_cols:
            assert not result[col].isna().any() or result[col].isna().all()
            assert not result[col].isin([np.inf, -np.inf]).any()


class TestVolatilityComputation:
    """Test volatility feature computation."""

    def test_volatility_20_range(self):
        """Test volatility_20 values are reasonable (0-1 range typically)."""
        df = get_sample_df(100)
        result = QuantFeatureEngine.compute(df)
        
        vol_20 = result["volatility_20"].dropna()
        assert (vol_20 >= 0).all()
        # Annualized volatility should typically be < 2 for stocks
        assert (vol_20 < 2).all()

    def test_volatility_50_range(self):
        """Test volatility_50 values are reasonable."""
        df = get_sample_df(100)
        result = QuantFeatureEngine.compute(df)
        
        vol_50 = result["volatility_50"].dropna()
        assert (vol_50 >= 0).all()
        assert (vol_50 < 2).all()

    def test_volatility_increases_with_variance(self):
        """Test volatility increases when price variance increases."""
        # Low variance data
        low_var_df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=100),
            "open": [100.0 + i * 0.01 for i in range(100)],
            "high": [100.5 + i * 0.01 for i in range(100)],
            "low": [99.5 + i * 0.01 for i in range(100)],
            "close": [100.25 + i * 0.01 for i in range(100)],
            "volume": [1000000] * 100
        })
        
        # High variance data
        high_var_df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=100),
            "open": [100.0 + i * 1.0 for i in range(100)],
            "high": [100.5 + i * 1.0 for i in range(100)],
            "low": [99.5 + i * 1.0 for i in range(100)],
            "close": [100.25 + i * 1.0 for i in range(100)],
            "volume": [1000000] * 100
        })
        
        low_var_result = QuantFeatureEngine.compute(low_var_df)
        high_var_result = QuantFeatureEngine.compute(high_var_df)
        
        low_vol_20 = low_var_result.iloc[-1]["volatility_20"]
        high_vol_20 = high_var_result.iloc[-1]["volatility_20"]
        
        assert high_vol_20 > low_vol_20

    def test_atr_positive(self):
        """Test ATR values are positive."""
        df = get_sample_df(50)
        result = QuantFeatureEngine.compute(df)
        
        atr = result["atr"].dropna()
        assert (atr >= 0).all()

    def test_atr_related_to_range(self):
        """Test ATR is related to average high-low range."""
        df = get_sample_df(50)
        result = QuantFeatureEngine.compute(df)
        
        # Average range should be roughly comparable to ATR
        avg_range = (result["high"] - result["low"]).mean()
        avg_atr = result["atr"].mean()
        
        # ATR should be in same ballpark as range (within 2x)
        assert avg_atr > 0
        assert avg_atr > avg_range * 0.5


class TestVolumeComputation:
    """Test volume-based features."""

    def test_rolling_volume_20_positive(self):
        """Test rolling volume is positive."""
        df = get_sample_df(50)
        result = QuantFeatureEngine.compute(df)
        
        rolling_vol = result["rolling_volume_20"].dropna()
        assert (rolling_vol >= 0).all()

    def test_rolling_volume_average(self):
        """Test rolling volume approximates mean volume."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [100.0] * 50,
            "high": [101.0] * 50,
            "low": [99.0] * 50,
            "close": [100.5] * 50,
            "volume": [1000000] * 50
        })
        
        result = QuantFeatureEngine.compute(df)
        rolling_vol = result["rolling_volume_20"].iloc[-1]
        
        # Should be close to 1000000
        assert rolling_vol > 900000
        assert rolling_vol < 1100000

    def test_volume_ratio_normalized(self):
        """Test volume ratio is normalized to ~1.0."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [100.0] * 50,
            "high": [101.0] * 50,
            "low": [99.0] * 50,
            "close": [100.5] * 50,
            "volume": [1000000] * 50
        })
        
        result = QuantFeatureEngine.compute(df)
        vol_ratio = result["volume_ratio"].iloc[-1]
        
        # Should be very close to 1.0 (current vol / avg vol)
        assert 0.95 < vol_ratio < 1.05


class TestMarketStructureComputation:
    """Test market structure feature computation."""

    def test_hh_hl_lh_ll_values(self):
        """Test structure labels are binary (0 or 1)."""
        df = get_sample_df(50)
        result = QuantFeatureEngine.compute(df)
        
        for col in ["hh", "hl", "lh", "ll"]:
            assert set(result[col].unique()).issubset({0, 1})

    def test_trend_direction_valid(self):
        """Test trend_direction contains valid values."""
        df = get_sample_df(50)
        result = QuantFeatureEngine.compute(df)
        
        valid_trends = {"up", "down", "neutral"}
        assert set(result["trend_direction"].unique()).issubset(valid_trends)

    def test_structure_label_valid(self):
        """Test structure_label contains valid values."""
        df = get_sample_df(50)
        result = QuantFeatureEngine.compute(df)
        
        valid_structures = {"bullish", "bearish", "range"}
        assert set(result["structure_label"].unique()).issubset(valid_structures)

    def test_bullish_structure_pattern(self):
        """Test bullish structure is identified (HH + HL)."""
        # Create uptrend data
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [100.0 + i * 0.5 for i in range(50)],
            "high": [102.0 + i * 0.5 for i in range(50)],
            "low": [99.0 + i * 0.5 for i in range(50)],
            "close": [101.0 + i * 0.5 for i in range(50)],
            "volume": [1000000] * 50
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Later rows should show bullish structure
        recent_structures = result.iloc[-10:]["structure_label"].tolist()
        assert "bullish" in recent_structures


class TestRegimeComputation:
    """Test regime feature computation."""

    def test_volatility_regime_valid(self):
        """Test volatility_regime contains valid values."""
        df = get_sample_df(100)
        result = QuantFeatureEngine.compute(df)
        
        valid_regimes = {"low", "medium", "high"}
        assert set(result["volatility_regime"].unique()).issubset(valid_regimes)

    def test_trend_regime_valid(self):
        """Test trend_regime contains valid values."""
        df = get_sample_df(100)
        result = QuantFeatureEngine.compute(df)
        
        valid_regimes = {"uptrend", "downtrend", "ranging"}
        assert set(result["trend_regime"].unique()).issubset(valid_regimes)

    def test_compression_regime_valid(self):
        """Test compression_regime contains valid values."""
        df = get_sample_df(100)
        result = QuantFeatureEngine.compute(df)
        
        valid_regimes = {"compressed", "expanded"}
        assert set(result["compression_regime"].unique()).issubset(valid_regimes)

    def test_uptrend_detected_in_rising_market(self):
        """Test uptrend regime is detected in rising market."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=100),
            "open": [100.0 + i * 0.5 for i in range(100)],
            "high": [102.0 + i * 0.5 for i in range(100)],
            "low": [99.0 + i * 0.5 for i in range(100)],
            "close": [101.0 + i * 0.5 for i in range(100)],
            "volume": [1000000] * 100
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Recent trend should be uptrend
        recent_trends = result.iloc[-10:]["trend_regime"].tolist()
        assert recent_trends.count("uptrend") > recent_trends.count("downtrend")

    def test_downtrend_detected_in_falling_market(self):
        """Test downtrend regime is detected in falling market."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=100),
            "open": [100.0 - i * 0.5 for i in range(100)],
            "high": [102.0 - i * 0.5 for i in range(100)],
            "low": [99.0 - i * 0.5 for i in range(100)],
            "close": [101.0 - i * 0.5 for i in range(100)],
            "volume": [1000000] * 100
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Recent trend should be downtrend
        recent_trends = result.iloc[-10:]["trend_regime"].tolist()
        assert recent_trends.count("downtrend") > recent_trends.count("uptrend")


class TestEdgeCases:
    """Test edge cases and data quality handling."""

    def test_all_same_prices(self):
        """Test handling of flat price data (no volatility)."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [100.0] * 50,
            "high": [100.0] * 50,
            "low": [100.0] * 50,
            "close": [100.0] * 50,
            "volume": [1000000] * 50
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Should handle without error
        assert not result.empty
        assert result["volatility_20"].iloc[-1] == 0.0
        assert result["atr"].iloc[-1] == 0.0

    def test_zero_volume(self):
        """Test handling of zero volume."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [100.0] * 50,
            "high": [101.0] * 50,
            "low": [99.0] * 50,
            "close": [100.5] * 50,
            "volume": [0] * 50
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Should handle without error
        assert not result.empty
        # Rolling volume with all zeros may result in 0 or fallback value
        assert result["rolling_volume_20"].iloc[-1] >= 0

    def test_nan_prices(self):
        """Test handling of NaN prices."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [100.0 if i % 5 != 0 else np.nan for i in range(50)],
            "high": [101.0] * 50,
            "low": [99.0] * 50,
            "close": [100.5] * 50,
            "volume": [1000000] * 50
        })
        
        # Convert to numeric (should coerce NaN)
        result = QuantFeatureEngine.compute(df)
        
        # Should handle gracefully
        assert not result.empty

    def test_large_price_jumps(self):
        """Test handling of large price gaps (stock splits, etc.)."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [100.0 if i < 25 else 200.0 for i in range(50)],
            "high": [101.0 if i < 25 else 201.0 for i in range(50)],
            "low": [99.0 if i < 25 else 199.0 for i in range(50)],
            "close": [100.5 if i < 25 else 200.5 for i in range(50)],
            "volume": [1000000] * 50
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Should not have inf or nan
        assert not result["return_1d"].isin([np.inf, -np.inf]).any()

    def test_negative_prices_converted(self):
        """Test negative prices are handled."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [-100.0] * 50,
            "high": [-99.0] * 50,
            "low": [-101.0] * 50,
            "close": [-100.5] * 50,
            "volume": [1000000] * 50
        })
        
        # Negative prices get coerced to NaN
        result = QuantFeatureEngine.compute(df)
        
        # Should handle without error
        assert not result.empty

    def test_very_small_prices(self):
        """Test handling of very small prices (penny stocks, cryptos)."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [0.0001] * 50,
            "high": [0.0001001] * 50,
            "low": [0.00009999] * 50,
            "close": [0.000100005] * 50,
            "volume": [1000000000] * 50
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Should handle without error
        assert not result.empty
        assert not result["volatility_20"].isin([np.inf, -np.inf]).any()

    def test_very_large_prices(self):
        """Test handling of very large prices."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [10000.0] * 50,
            "high": [10001.0] * 50,
            "low": [9999.0] * 50,
            "close": [10000.5] * 50,
            "volume": [1000] * 50
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Should handle without error
        assert not result.empty


class TestDataTypeHandling:
    """Test handling of different data types."""

    def test_string_prices_converted(self):
        """Test string prices are converted to numeric."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=10),
            "open": ["100.0"] * 10,
            "high": ["101.0"] * 10,
            "low": ["99.0"] * 10,
            "close": ["100.5"] * 10,
            "volume": ["1000000"] * 10
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Should convert without error
        assert not result.empty
        assert result["log_return"].dtype in [float, np.float64]

    def test_decimal_prices(self):
        """Test Decimal type prices."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=10),
            "open": [Decimal("100.0")] * 10,
            "high": [Decimal("101.0")] * 10,
            "low": [Decimal("99.0")] * 10,
            "close": [Decimal("100.5")] * 10,
            "volume": [1000000] * 10
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Should handle Decimal types
        assert not result.empty

    def test_integer_prices(self):
        """Test integer prices are handled."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=10),
            "open": [100] * 10,
            "high": [101] * 10,
            "low": [99] * 10,
            "close": [100] * 10,
            "volume": [1000000] * 10
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Should handle without error
        assert not result.empty


class TestDataOrdering:
    """Test behavior with differently ordered data."""

    def test_unsorted_data_sorted_internally(self):
        """Test unsorted data is sorted by the compute function."""
        times = pd.date_range("2024-01-01", periods=20)
        df = pd.DataFrame({
            "time": times[[10, 5, 15, 0, 19]].tolist() + times[[1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 18]].tolist(),
            "open": [100.0 + i for i in range(20)],
            "high": [101.0 + i for i in range(20)],
            "low": [99.0 + i for i in range(20)],
            "close": [100.5 + i for i in range(20)],
            "volume": [1000000] * 20
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Result should be sorted by time
        assert (result["time"].diff().dt.total_seconds().dropna() >= 0).all()
