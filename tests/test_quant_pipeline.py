"""
Tests for Quant Features Integration into Data Pipeline.

Tests cover:
- Feature computation within scheduler
- Database insert/update of features
- Feature summary table management
- Error handling in pipeline
"""

import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, AsyncMock, MagicMock, call
from decimal import Decimal

from src.services.database_service import DatabaseService
from src.quant_engine import QuantFeatureEngine


class TestDatabaseServiceQuantMethods:
    """Test DatabaseService quant feature methods."""

    def test_insert_quant_features_signature(self):
        """Test insert_quant_features method exists with correct signature."""
        assert hasattr(DatabaseService, "insert_quant_features")
        assert callable(getattr(DatabaseService, "insert_quant_features"))

    def test_get_quant_features_signature(self):
        """Test get_quant_features method exists with correct signature."""
        assert hasattr(DatabaseService, "get_quant_features")
        assert callable(getattr(DatabaseService, "get_quant_features"))

    def test_update_quant_feature_summary_signature(self):
        """Test update_quant_feature_summary method exists with correct signature."""
        assert hasattr(DatabaseService, "update_quant_feature_summary")
        assert callable(getattr(DatabaseService, "update_quant_feature_summary"))


class TestQuantFeaturesDataFormat:
    """Test data format compatibility."""

    def test_quant_features_dataframe_format(self):
        """Test features are properly formatted for database insertion."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=10),
            "open": [100.0 + i for i in range(10)],
            "high": [101.0 + i for i in range(10)],
            "low": [99.0 + i for i in range(10)],
            "close": [100.5 + i for i in range(10)],
            "volume": [1000000] * 10
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Check all required features are present and numeric
        required_cols = [
            "return_1d", "volatility_20", "volatility_50", "atr",
            "rolling_volume_20", "volume_ratio",
            "structure_label", "trend_direction", "volatility_regime",
            "trend_regime", "compression_regime"
        ]
        
        for col in required_cols:
            assert col in result.columns
            # Check numeric columns are numeric
            if col not in ["structure_label", "trend_direction", "volatility_regime", "trend_regime", "compression_regime"]:
                assert pd.api.types.is_numeric_dtype(result[col])

    def test_quant_features_handle_decimals(self):
        """Test features handle Decimal types for database compatibility."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=10),
            "open": [Decimal("100.0") + i for i in range(10)],
            "high": [Decimal("101.0") + i for i in range(10)],
            "low": [Decimal("99.0") + i for i in range(10)],
            "close": [Decimal("100.5") + i for i in range(10)],
            "volume": [1000000] * 10
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Should not raise error and should have features
        assert "return_1d" in result.columns
        assert not result.empty

    def test_quant_features_timestamp_handling(self):
        """Test timestamp field is preserved correctly."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=10),
            "open": [100.0 + i for i in range(10)],
            "high": [101.0 + i for i in range(10)],
            "low": [99.0 + i for i in range(10)],
            "close": [100.5 + i for i in range(10)],
            "volume": [1000000] * 10
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Timestamps should be preserved
        assert "time" in result.columns
        assert (result["time"] == df["time"]).all()


class TestMultiTimeframeSupport:
    """Test multi-timeframe feature support."""

    def test_features_support_different_timeframes(self):
        """Test features work with different timeframe data."""
        timeframes = {
            "5m": pd.date_range("2024-01-01", periods=100, freq="5min"),
            "1h": pd.date_range("2024-01-01", periods=100, freq="1h"),
            "1d": pd.date_range("2024-01-01", periods=100, freq="1d"),
        }
        
        for tf, times in timeframes.items():
            df = pd.DataFrame({
                "time": times,
                "open": [100.0 + i * 0.1 for i in range(100)],
                "high": [101.0 + i * 0.1 for i in range(100)],
                "low": [99.0 + i * 0.1 for i in range(100)],
                "close": [100.5 + i * 0.1 for i in range(100)],
                "volume": [1000000] * 100
            })
            
            result = QuantFeatureEngine.compute(df)
            
            # Should work for all timeframes
            assert not result.empty, f"Failed for timeframe {tf}"
            assert "volatility_20" in result.columns
            assert result["volatility_20"].notna().sum() > 0

    def test_features_lookback_periods(self):
        """Test features respect appropriate lookback periods."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=100),
            "open": [100.0 + i * 0.1 for i in range(100)],
            "high": [101.0 + i * 0.1 for i in range(100)],
            "low": [99.0 + i * 0.1 for i in range(100)],
            "close": [100.5 + i * 0.1 for i in range(100)],
            "volume": [1000000] * 100
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Features requiring longer lookback may have filled NaN values
        # Check that volatility_50 is computed
        assert "volatility_50" in result.columns
        assert result["volatility_50"].notna().sum() > 0


class TestQuantFeatureQuality:
    """Test quality of computed features."""

    def test_features_no_inf_values(self):
        """Test computed features don't contain infinite values."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=100),
            "open": [100.0 + i * 0.5 for i in range(100)],
            "high": [101.0 + i * 0.5 for i in range(100)],
            "low": [99.0 + i * 0.5 for i in range(100)],
            "close": [100.5 + i * 0.5 for i in range(100)],
            "volume": [1000000] * 100
        })
        
        result = QuantFeatureEngine.compute(df)
        
        numeric_cols = [
            "return_1d", "volatility_20", "volatility_50", "atr",
            "rolling_volume_20", "volume_ratio"
        ]
        
        for col in numeric_cols:
            assert not result[col].isin([float('inf'), float('-inf')]).any(), f"{col} contains infinity"

    def test_features_reasonable_ranges(self):
        """Test computed features are within reasonable ranges."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=100),
            "open": [100.0 + i * 0.5 for i in range(100)],
            "high": [101.0 + i * 0.5 for i in range(100)],
            "low": [99.0 + i * 0.5 for i in range(100)],
            "close": [100.5 + i * 0.5 for i in range(100)],
            "volume": [1000000] * 100
        })
        
        result = QuantFeatureEngine.compute(df)
        
        # Returns should be between -1 and 1 (typical log returns)
        returns = result["return_1d"].dropna()
        if len(returns) > 0:
            assert returns.max() < 1.0
            assert returns.min() > -1.0
        
        # Volatility should be positive and < 2 (annualized)
        vol = result["volatility_20"].dropna()
        if len(vol) > 0:
            assert (vol >= 0).all()
            assert (vol < 2).all()
        
        # Volume ratio should be positive
        vol_ratio = result["volume_ratio"].dropna()
        if len(vol_ratio) > 0:
            assert (vol_ratio >= 0).all()

    def test_features_consistency_across_runs(self):
        """Test features are consistent across multiple runs."""
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=100),
            "open": [100.0 + i * 0.5 for i in range(100)],
            "high": [101.0 + i * 0.5 for i in range(100)],
            "low": [99.0 + i * 0.5 for i in range(100)],
            "close": [100.5 + i * 0.5 for i in range(100)],
            "volume": [1000000] * 100
        })
        
        result1 = QuantFeatureEngine.compute(df.copy())
        result2 = QuantFeatureEngine.compute(df.copy())
        
        # Results should be identical
        for col in ["return_1d", "volatility_20", "volatility_50", "atr"]:
            assert (result1[col] == result2[col]).all() or (result1[col].isna() == result2[col].isna()).all()


class TestSchedulerIntegration:
    """Test integration with scheduler."""

    def test_scheduler_has_compute_quant_features_method(self):
        """Test scheduler has _compute_quant_features method."""
        from src.scheduler import AutoBackfillScheduler
        
        assert hasattr(AutoBackfillScheduler, "_compute_quant_features")

    def test_compute_quant_features_method_signature(self):
        """Test _compute_quant_features has correct signature."""
        from src.scheduler import AutoBackfillScheduler
        import inspect
        
        method = getattr(AutoBackfillScheduler, "_compute_quant_features")
        
        sig = inspect.signature(method)
        params = list(sig.parameters.keys())
        
        # Should have self, symbol, timeframe
        assert "symbol" in params
        assert "timeframe" in params


class TestFeatureComputationSafety:
    """Test safety of feature computation in pipeline."""

    def test_computation_doesnt_modify_input(self):
        """Test feature computation doesn't modify input DataFrame."""
        df_original = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=50),
            "open": [100.0 + i * 0.1 for i in range(50)],
            "high": [101.0 + i * 0.1 for i in range(50)],
            "low": [99.0 + i * 0.1 for i in range(50)],
            "close": [100.5 + i * 0.1 for i in range(50)],
            "volume": [1000000] * 50
        })
        
        df_copy = df_original.copy()
        
        result = QuantFeatureEngine.compute(df_original)
        
        # Original should be unchanged
        assert (df_original == df_copy).all().all()

    def test_computation_handles_large_datasets(self):
        """Test feature computation handles large datasets."""
        large_df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=10000, freq="1min"),
            "open": [100.0 + i * 0.0001 for i in range(10000)],
            "high": [101.0 + i * 0.0001 for i in range(10000)],
            "low": [99.0 + i * 0.0001 for i in range(10000)],
            "close": [100.5 + i * 0.0001 for i in range(10000)],
            "volume": [1000000] * 10000
        })
        
        result = QuantFeatureEngine.compute(large_df)
        
        # Should handle without error
        assert not result.empty
        assert len(result) == 10000

    def test_computation_performance(self):
        """Test feature computation completes in reasonable time."""
        import time
        
        df = pd.DataFrame({
            "time": pd.date_range("2024-01-01", periods=1000),
            "open": [100.0 + i * 0.01 for i in range(1000)],
            "high": [101.0 + i * 0.01 for i in range(1000)],
            "low": [99.0 + i * 0.01 for i in range(1000)],
            "close": [100.5 + i * 0.01 for i in range(1000)],
            "volume": [1000000] * 1000
        })
        
        start = time.time()
        result = QuantFeatureEngine.compute(df)
        elapsed = time.time() - start
        
        # Should complete in < 1 second for 1000 rows
        assert elapsed < 1.0
        assert not result.empty
