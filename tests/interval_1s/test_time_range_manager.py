#!/usr/bin/env python
"""Tests for the TimeRangeManager class."""

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np

from utils.time_alignment import TimeRangeManager
from utils.market_constraints import Interval


class TestTimeRangeManager:
    """Tests for the TimeRangeManager class."""

    def setup_method(self):
        """Set up test data."""
        # Create a test DataFrame
        dates = [datetime(2023, 1, 1, 0, 0, i, tzinfo=timezone.utc) for i in range(10)]

        self.test_df = pd.DataFrame(
            {
                "open": np.random.rand(10),
                "high": np.random.rand(10),
                "low": np.random.rand(10),
                "close": np.random.rand(10),
                "volume": np.random.rand(10),
            },
            index=pd.DatetimeIndex(dates, name="open_time"),
        )

        # Test times
        self.start_time = datetime(2023, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
        self.end_time = datetime(2023, 1, 1, 0, 0, 8, tzinfo=timezone.utc)

    def test_validate_time_window(self):
        """Test validate_time_window method."""
        # Valid time window
        TimeRangeManager.validate_time_window(self.start_time, self.end_time)

        # Invalid time window - start after end
        with pytest.raises(ValueError):
            TimeRangeManager.validate_time_window(self.end_time, self.start_time)

        # Invalid time window - future date
        future = datetime.now(timezone.utc) + timedelta(days=1)
        with pytest.raises(ValueError):
            TimeRangeManager.validate_time_window(self.start_time, future)

    def test_enforce_utc_timezone(self):
        """Test enforce_utc_timezone method."""
        # Non-timezone-aware datetime
        dt = datetime(2023, 1, 1)
        result = TimeRangeManager.enforce_utc_timezone(dt)
        assert result.tzinfo == timezone.utc

        # Different timezone
        dt = datetime(2023, 1, 1, tzinfo=timezone(timedelta(hours=1)))
        result = TimeRangeManager.enforce_utc_timezone(dt)
        assert result.tzinfo == timezone.utc

    def test_get_adjusted_boundaries(self):
        """Test get_adjusted_boundaries method."""
        # Get adjusted boundaries
        adjusted_start, adjusted_end = TimeRangeManager.get_adjusted_boundaries(
            self.start_time, self.end_time, Interval.SECOND_1
        )

        # Verify adjusted start time is floored
        assert adjusted_start.microsecond == 0

        # Verify adjusted end time is floored
        assert adjusted_end.microsecond == 0

        # Verify expected behavior
        assert adjusted_start <= self.start_time
        assert adjusted_end <= self.end_time

    def test_filter_dataframe(self):
        """Test filter_dataframe method."""
        # Filter DataFrame
        filtered_df = TimeRangeManager.filter_dataframe(
            self.test_df, self.start_time, self.end_time
        )

        # Verify shape
        assert len(filtered_df) == 6  # From 2 to 7 (exclusive end)

        # Verify boundaries
        assert filtered_df.index.min() >= self.start_time
        assert filtered_df.index.max() < self.end_time

    def test_get_time_boundaries(self):
        """Test get_time_boundaries method."""
        # Get time boundaries
        boundaries = TimeRangeManager.get_time_boundaries(
            self.start_time, self.end_time, Interval.SECOND_1
        )

        # Verify all expected fields
        assert "adjusted_start" in boundaries
        assert "adjusted_end" in boundaries
        assert "start_ms" in boundaries
        assert "end_ms" in boundaries
        assert "expected_records" in boundaries
        assert "interval_ms" in boundaries
        assert "interval_micros" in boundaries

        # Verify correct behavior
        assert boundaries["expected_records"] == 6  # From 2 to 7 (exclusive end)

    def test_validate_boundaries(self):
        """Test validate_boundaries method."""
        # Filter DataFrame first
        filtered_df = TimeRangeManager.filter_dataframe(
            self.test_df, self.start_time, self.end_time
        )

        # Valid boundaries
        TimeRangeManager.validate_boundaries(
            filtered_df, self.start_time, self.end_time
        )

        # Invalid boundaries - data doesn't cover requested range
        with pytest.raises(ValueError):
            earlier_start = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
            TimeRangeManager.validate_boundaries(
                filtered_df, earlier_start, self.end_time
            )
