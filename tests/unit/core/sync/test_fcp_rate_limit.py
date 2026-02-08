"""Tests for FCP rate limit handling (Phase 1 fixes).

Validates that rate-limited REST requests preserve partial data from cache+vision
instead of destroying it with a RuntimeError.

Related: GitHub Issue #18 (Rate Limit Handling Overhaul)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pandas as pd

from ckvd.utils.for_core.ckvd_fcp_utils import process_rest_step
from ckvd.utils.for_core.rest_exceptions import RateLimitError


def _make_ohlcv_df(start: datetime, count: int, freq_minutes: int = 60) -> pd.DataFrame:
    """Create a sample OHLCV DataFrame for testing."""
    rows = []
    for i in range(count):
        ts = start + timedelta(minutes=freq_minutes * i)
        rows.append(
            {
                "open_time": ts,
                "open": 42000.0 + i,
                "high": 42100.0 + i,
                "low": 41900.0 + i,
                "close": 42050.0 + i,
                "volume": 1000.0 + i,
            }
        )
    return pd.DataFrame(rows).set_index("open_time")


class TestProcessRestStepRateLimit:
    """Tests for process_rest_step() rate limit handling."""

    def test_preserves_existing_data_on_rate_limit(self):
        """When REST is rate-limited, cache+vision data in result_df is preserved."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # Simulate cache+vision data already in result_df (5 days)
        existing_df = _make_ohlcv_df(start, count=120, freq_minutes=60)
        existing_df["_data_source"] = "VISION"

        # REST fetch raises RateLimitError
        mock_fetch_rest = MagicMock(side_effect=RateLimitError(retry_after=60))

        # One missing range that REST would fill
        missing_ranges = [
            (start + timedelta(days=5), start + timedelta(days=7)),
        ]

        from ckvd.utils.market_constraints import Interval

        result = process_rest_step(
            fetch_from_rest_func=mock_fetch_rest,
            symbol="BTCUSDT",
            missing_ranges=missing_ranges,
            interval=Interval.HOUR_1,
            include_source_info=True,
            result_df=existing_df,
        )

        # Existing data preserved
        assert len(result) == 120
        assert result.attrs.get("_rate_limited") is True
        assert result.attrs.get("_fcp_partial") is True

    def test_rate_limit_with_empty_result_returns_empty(self):
        """When REST is rate-limited and result_df is empty, return empty (no flags)."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)

        mock_fetch_rest = MagicMock(side_effect=RateLimitError(retry_after=60))
        missing_ranges = [
            (start, start + timedelta(days=7)),
        ]

        from ckvd.utils.market_constraints import Interval

        result = process_rest_step(
            fetch_from_rest_func=mock_fetch_rest,
            symbol="BTCUSDT",
            missing_ranges=missing_ranges,
            interval=Interval.HOUR_1,
            include_source_info=True,
            result_df=pd.DataFrame(),
        )

        assert result.empty
        assert "_rate_limited" not in result.attrs

    def test_partial_rest_data_merged_before_rate_limit(self):
        """REST ranges fetched before rate limit are merged into result."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)

        existing_df = _make_ohlcv_df(start, count=24, freq_minutes=60)
        existing_df["_data_source"] = "CACHE"

        # First range succeeds, second raises RateLimitError
        rest_range1_df = _make_ohlcv_df(start + timedelta(days=1), count=24, freq_minutes=60)
        call_count = 0

        def _mock_fetch(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rest_range1_df
            raise RateLimitError(retry_after=60)

        mock_fetch_rest = MagicMock(side_effect=_mock_fetch)

        # Use non-adjacent ranges so merge_adjacent_ranges doesn't collapse them
        missing_ranges = [
            (start + timedelta(days=1), start + timedelta(days=2)),
            (start + timedelta(days=5), start + timedelta(days=6)),
        ]

        from ckvd.utils.market_constraints import Interval

        result = process_rest_step(
            fetch_from_rest_func=mock_fetch_rest,
            symbol="BTCUSDT",
            missing_ranges=missing_ranges,
            interval=Interval.HOUR_1,
            include_source_info=True,
            result_df=existing_df,
        )

        # Should have cache (24) + first REST range (24) = 48
        assert len(result) == 48
        assert result.attrs.get("_rate_limited") is True
        assert result.attrs.get("_fcp_partial") is True

    def test_no_rate_limit_returns_normal_data(self):
        """Normal fetch without rate limit has no partial flags."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)

        rest_df = _make_ohlcv_df(start, count=24, freq_minutes=60)
        mock_fetch_rest = MagicMock(return_value=rest_df)

        missing_ranges = [
            (start, start + timedelta(days=1)),
        ]

        from ckvd.utils.market_constraints import Interval

        result = process_rest_step(
            fetch_from_rest_func=mock_fetch_rest,
            symbol="BTCUSDT",
            missing_ranges=missing_ranges,
            interval=Interval.HOUR_1,
            include_source_info=True,
            result_df=pd.DataFrame(),
        )

        assert len(result) == 24
        assert "_rate_limited" not in result.attrs
        assert "_fcp_partial" not in result.attrs
