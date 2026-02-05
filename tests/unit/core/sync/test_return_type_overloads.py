#!/usr/bin/env python3
"""Unit tests for return_polars @overload type hints.

Tests validate that the @overload type hints for return_polars parameter
work correctly for type narrowing in static type checkers.

These tests serve as a regression safety net for Phase 3 API enhancements.

Copy from: tests/unit/core/sync/test_data_source_manager.py
Task: #80 - Create test_return_type_overloads.py (8 tests)

ADR: docs/adr/2025-01-30-failover-control-protocol.md
Plan: /Users/terryli/.claude/plans/gleaming-frolicking-engelbart.md
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pandas as pd
import polars as pl
import pytest

from data_source_manager import DataProvider, DataSourceManager, Interval, MarketType
from data_source_manager.utils.config import FeatureFlags


# Skip marker for tests that mock the pandas FCP path
# When USE_POLARS_PIPELINE=True, the code takes a different path using get_cache_lazyframes
# instead of process_cache_step, so these mocks don't apply
skip_if_polars_pipeline = pytest.mark.skipif(
    FeatureFlags().USE_POLARS_PIPELINE,
    reason="Test mocks pandas FCP path; skipped when USE_POLARS_PIPELINE=True",
)


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def sample_ohlcv_df():
    """Create a sample OHLCV DataFrame for testing."""
    base_time = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    timestamps = [base_time + timedelta(hours=i) for i in range(6)]
    return pd.DataFrame(
        {
            "open": [42000.0 + i * 10 for i in range(6)],
            "high": [42100.0 + i * 10 for i in range(6)],
            "low": [41900.0 + i * 10 for i in range(6)],
            "close": [42050.0 + i * 10 for i in range(6)],
            "volume": [1000.0 + i for i in range(6)],
        },
        index=pd.DatetimeIndex(timestamps, name="open_time", tz="UTC"),
    )


@pytest.fixture
def historical_time_range():
    """Historical time range for tests."""
    end = datetime(2024, 1, 15, 5, 0, 0, tzinfo=timezone.utc)
    start = datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    return start, end


# =============================================================================
# Test 1-4: get_data() Return Type Tests
# =============================================================================


@skip_if_polars_pipeline
class TestGetDataReturnTypes:
    """Tests for get_data() return type based on return_polars parameter."""

    @patch("data_source_manager.core.sync.data_source_manager.verify_final_data")
    @patch("data_source_manager.core.sync.data_source_manager.process_rest_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_vision_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_cache_step")
    def test_get_data_returns_pandas_by_default(
        self,
        mock_cache_step,
        mock_vision_step,
        mock_rest_step,
        mock_verify,
        sample_ohlcv_df,
        historical_time_range,
    ):
        """get_data() should return pandas DataFrame by default.

        Default: return_polars=False
        """
        start_time, end_time = historical_time_range
        mock_cache_step.return_value = (sample_ohlcv_df, [])
        mock_verify.return_value = sample_ohlcv_df

        manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.SPOT)

        result = manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
        )

        assert isinstance(result, pd.DataFrame)
        assert not isinstance(result, pl.DataFrame)
        manager.close()

    @patch("data_source_manager.core.sync.data_source_manager.verify_final_data")
    @patch("data_source_manager.core.sync.data_source_manager.process_rest_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_vision_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_cache_step")
    def test_get_data_returns_polars_when_true(
        self,
        mock_cache_step,
        mock_vision_step,
        mock_rest_step,
        mock_verify,
        sample_ohlcv_df,
        historical_time_range,
    ):
        """get_data(return_polars=True) should return Polars DataFrame."""
        start_time, end_time = historical_time_range
        mock_cache_step.return_value = (sample_ohlcv_df, [])
        mock_verify.return_value = sample_ohlcv_df

        manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.SPOT)

        result = manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            return_polars=True,
        )

        assert isinstance(result, pl.DataFrame)
        manager.close()

    @patch("data_source_manager.core.sync.data_source_manager.verify_final_data")
    @patch("data_source_manager.core.sync.data_source_manager.process_rest_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_vision_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_cache_step")
    def test_get_data_explicit_false_returns_pandas(
        self,
        mock_cache_step,
        mock_vision_step,
        mock_rest_step,
        mock_verify,
        sample_ohlcv_df,
        historical_time_range,
    ):
        """get_data(return_polars=False) should return pandas DataFrame.

        Type hint: Literal[False] -> pd.DataFrame
        """
        start_time, end_time = historical_time_range
        mock_cache_step.return_value = (sample_ohlcv_df, [])
        mock_verify.return_value = sample_ohlcv_df

        manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.SPOT)

        result = manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            return_polars=False,
        )

        assert isinstance(result, pd.DataFrame)
        manager.close()

    @patch("data_source_manager.core.sync.data_source_manager.verify_final_data")
    @patch("data_source_manager.core.sync.data_source_manager.process_rest_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_vision_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_cache_step")
    def test_get_data_polars_has_correct_columns(
        self,
        mock_cache_step,
        mock_vision_step,
        mock_rest_step,
        mock_verify,
        sample_ohlcv_df,
        historical_time_range,
    ):
        """Polars return should have same columns as pandas.

        Type hint: Literal[True] -> pl.DataFrame
        """
        start_time, end_time = historical_time_range
        mock_cache_step.return_value = (sample_ohlcv_df, [])
        mock_verify.return_value = sample_ohlcv_df

        manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.SPOT)

        result = manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            return_polars=True,
        )

        # Should have OHLCV columns
        assert "open" in result.columns
        assert "high" in result.columns
        assert "low" in result.columns
        assert "close" in result.columns
        assert "volume" in result.columns
        manager.close()


# =============================================================================
# Test 5-8: Type Narrowing and Runtime Behavior
# =============================================================================


@skip_if_polars_pipeline
class TestTypeNarrowing:
    """Tests for type narrowing in conditionals."""

    @patch("data_source_manager.core.sync.data_source_manager.verify_final_data")
    @patch("data_source_manager.core.sync.data_source_manager.process_rest_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_vision_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_cache_step")
    def test_type_narrowing_in_if_statement(
        self,
        mock_cache_step,
        mock_vision_step,
        mock_rest_step,
        mock_verify,
        sample_ohlcv_df,
        historical_time_range,
    ):
        """Type should be correctly narrowed in if statement.

        Pattern used by consumers to handle both return types.
        """
        start_time, end_time = historical_time_range
        mock_cache_step.return_value = (sample_ohlcv_df, [])
        mock_verify.return_value = sample_ohlcv_df

        manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.SPOT)

        # Test with return_polars=True
        result_polars = manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            return_polars=True,
        )

        if isinstance(result_polars, pl.DataFrame):
            # Type narrowed to pl.DataFrame
            assert result_polars.height > 0
        else:
            pytest.fail("Expected pl.DataFrame when return_polars=True")

        manager.close()

    @patch("data_source_manager.core.sync.data_source_manager.verify_final_data")
    @patch("data_source_manager.core.sync.data_source_manager.process_rest_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_vision_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_cache_step")
    def test_type_narrowing_with_false(
        self,
        mock_cache_step,
        mock_vision_step,
        mock_rest_step,
        mock_verify,
        sample_ohlcv_df,
        historical_time_range,
    ):
        """Type should be correctly narrowed with return_polars=False."""
        start_time, end_time = historical_time_range
        mock_cache_step.return_value = (sample_ohlcv_df, [])
        mock_verify.return_value = sample_ohlcv_df

        manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.SPOT)

        result_pandas = manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            return_polars=False,
        )

        if isinstance(result_pandas, pd.DataFrame):
            # Type narrowed to pd.DataFrame
            assert len(result_pandas) > 0
        else:
            pytest.fail("Expected pd.DataFrame when return_polars=False")

        manager.close()

    @patch("data_source_manager.core.sync.data_source_manager.verify_final_data")
    @patch("data_source_manager.core.sync.data_source_manager.process_rest_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_vision_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_cache_step")
    def test_polars_df_methods_available(
        self,
        mock_cache_step,
        mock_vision_step,
        mock_rest_step,
        mock_verify,
        sample_ohlcv_df,
        historical_time_range,
    ):
        """Polars-specific methods should be available on return.

        Validates that the Polars DataFrame API is accessible.
        """
        start_time, end_time = historical_time_range
        mock_cache_step.return_value = (sample_ohlcv_df, [])
        mock_verify.return_value = sample_ohlcv_df

        manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.SPOT)

        result = manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            return_polars=True,
        )

        # Polars-specific attributes/methods
        assert hasattr(result, "height")  # Polars uses height, not len
        assert hasattr(result, "width")
        assert hasattr(result, "lazy")  # Can convert to LazyFrame
        assert hasattr(result, "to_pandas")  # Can convert back

        manager.close()

    @patch("data_source_manager.core.sync.data_source_manager.verify_final_data")
    @patch("data_source_manager.core.sync.data_source_manager.process_rest_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_vision_step")
    @patch("data_source_manager.core.sync.data_source_manager.process_cache_step")
    def test_pandas_df_methods_available(
        self,
        mock_cache_step,
        mock_vision_step,
        mock_rest_step,
        mock_verify,
        sample_ohlcv_df,
        historical_time_range,
    ):
        """Pandas-specific methods should be available on return.

        Validates that the pandas DataFrame API is accessible.
        """
        start_time, end_time = historical_time_range
        mock_cache_step.return_value = (sample_ohlcv_df, [])
        mock_verify.return_value = sample_ohlcv_df

        manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.SPOT)

        result = manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            return_polars=False,
        )

        # Pandas-specific attributes/methods
        assert hasattr(result, "index")  # Pandas has index
        assert hasattr(result, "iloc")
        assert hasattr(result, "loc")
        assert hasattr(result, "to_numpy")

        manager.close()
