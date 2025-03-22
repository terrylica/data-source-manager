#!/usr/bin/env python
"""Test suite for time alignment utilities.

This test suite verifies the behavior of time alignment utilities
to ensure consistent handling of time boundaries across the codebase.
"""

import logging
import unittest
from datetime import datetime, timedelta, timezone
import pandas as pd

from utils.market_constraints import Interval
from utils.time_alignment import (
    adjust_time_window,
    get_time_boundaries,
    filter_time_range,
)


class TestTimeAlignmentUtils(unittest.TestCase):
    """Test suite for time alignment utilities."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = logging.getLogger(__name__)

        # Create common test times
        self.exact_time = datetime(2025, 3, 18, 5, 1, 16, 0, tzinfo=timezone.utc)
        self.mid_time = datetime(2025, 3, 18, 5, 1, 16, 500000, tzinfo=timezone.utc)
        self.end_time = datetime(2025, 3, 18, 5, 1, 16, 999999, tzinfo=timezone.utc)

        # Time window cases
        self.test_windows = [
            {
                "name": "exact-exact",
                "start": datetime(2025, 3, 18, 5, 1, 16, 0, tzinfo=timezone.utc),
                "end": datetime(2025, 3, 18, 5, 1, 21, 0, tzinfo=timezone.utc),
                "expected_records": 5,
            },
            {
                "name": "mid-mid",
                "start": datetime(2025, 3, 18, 5, 1, 16, 500000, tzinfo=timezone.utc),
                "end": datetime(2025, 3, 18, 5, 1, 21, 500000, tzinfo=timezone.utc),
                "expected_records": 5,
            },
            {
                "name": "end-mid",
                "start": datetime(2025, 3, 18, 5, 1, 16, 999999, tzinfo=timezone.utc),
                "end": datetime(2025, 3, 18, 5, 1, 21, 500000, tzinfo=timezone.utc),
                "expected_records": 5,
            },
        ]

        # Create a test DataFrame with 10 seconds of data
        base_time = datetime(2025, 3, 18, 5, 1, 10, 0, tzinfo=timezone.utc)
        test_data = []

        for i in range(20):
            ts = base_time + timedelta(seconds=i)
            test_data.append(
                {
                    "open_time": ts,
                    "open": 100 + i,
                    "high": 101 + i,
                    "low": 99 + i,
                    "close": 100.5 + i,
                    "volume": 1000 + i * 10,
                }
            )

        self.test_df = pd.DataFrame(test_data)
        self.test_df.set_index("open_time", inplace=True)

    def test_adjust_time_window(self):
        """Test adjust_time_window function."""
        for window in self.test_windows:
            start_time = window["start"]
            end_time = window["end"]

            # Call adjust_time_window
            adjusted_start, adjusted_end = adjust_time_window(
                start_time, end_time, Interval.SECOND_1
            )

            # Verify adjusted start time is floor of original
            expected_start = datetime(
                start_time.year,
                start_time.month,
                start_time.day,
                start_time.hour,
                start_time.minute,
                start_time.second,
                0,
                tzinfo=timezone.utc,
            )
            self.assertEqual(
                adjusted_start,
                expected_start,
                f"Start time not properly floored for case {window['name']}",
            )

            # Verify adjusted end time is floor of original
            expected_end = datetime(
                end_time.year,
                end_time.month,
                end_time.day,
                end_time.hour,
                end_time.minute,
                end_time.second,
                0,
                tzinfo=timezone.utc,
            )
            self.assertEqual(
                adjusted_end,
                expected_end,
                f"End time not properly floored for case {window['name']}",
            )

            # Verify time span
            time_span = int((adjusted_end - adjusted_start).total_seconds())
            self.assertEqual(
                time_span,
                window["expected_records"],
                f"Time span incorrect for case {window['name']}",
            )

    def test_get_time_boundaries(self):
        """Test get_time_boundaries function."""
        for window in self.test_windows:
            start_time = window["start"]
            end_time = window["end"]

            # Call get_time_boundaries
            boundaries = get_time_boundaries(start_time, end_time, Interval.SECOND_1)

            # Verify the returned dictionary contains all expected keys
            expected_keys = [
                "adjusted_start",
                "adjusted_end",
                "start_ms",
                "end_ms",
                "expected_records",
                "interval_ms",
                "interval_micros",
                "boundary_type",
            ]
            for key in expected_keys:
                self.assertIn(
                    key,
                    boundaries,
                    f"Key '{key}' missing from boundaries dict for case {window['name']}",
                )

            # Verify adjusted timestamps
            expected_start = datetime(
                start_time.year,
                start_time.month,
                start_time.day,
                start_time.hour,
                start_time.minute,
                start_time.second,
                0,
                tzinfo=timezone.utc,
            )
            self.assertEqual(
                boundaries["adjusted_start"],
                expected_start,
                f"Adjusted start time incorrect for case {window['name']}",
            )

            expected_end = datetime(
                end_time.year,
                end_time.month,
                end_time.day,
                end_time.hour,
                end_time.minute,
                end_time.second,
                0,
                tzinfo=timezone.utc,
            )
            self.assertEqual(
                boundaries["adjusted_end"],
                expected_end,
                f"Adjusted end time incorrect for case {window['name']}",
            )

            # Verify expected records
            self.assertEqual(
                boundaries["expected_records"],
                window["expected_records"],
                f"Expected records incorrect for case {window['name']}",
            )

            # Verify millisecond timestamps
            self.assertEqual(
                boundaries["start_ms"],
                int(expected_start.timestamp() * 1000),
                f"Start milliseconds incorrect for case {window['name']}",
            )
            self.assertEqual(
                boundaries["end_ms"],
                int(expected_end.timestamp() * 1000),
                f"End milliseconds incorrect for case {window['name']}",
            )

            # Verify interval conversions
            self.assertEqual(boundaries["interval_ms"], 1000)
            self.assertEqual(boundaries["interval_micros"], 1_000_000)

            # Verify boundary type
            self.assertEqual(
                boundaries["boundary_type"],
                "inclusive_start_exclusive_end",
                f"Boundary type incorrect for case {window['name']}",
            )

    def test_filter_time_range(self):
        """Test filter_time_range function."""
        # Test case 1: Filter exact window
        start_time = datetime(2025, 3, 18, 5, 1, 15, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 3, 18, 5, 1, 18, 0, tzinfo=timezone.utc)

        filtered_df = filter_time_range(self.test_df, start_time, end_time)

        # Should include 15, 16, 17 but not 18 (exclusive end)
        self.assertEqual(len(filtered_df), 3)
        self.assertEqual(
            filtered_df.index[0],
            datetime(2025, 3, 18, 5, 1, 15, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            filtered_df.index[2],
            datetime(2025, 3, 18, 5, 1, 17, 0, tzinfo=timezone.utc),
        )

        # Test case 2: Filter with microseconds
        start_time = datetime(2025, 3, 18, 5, 1, 15, 500000, tzinfo=timezone.utc)
        end_time = datetime(2025, 3, 18, 5, 1, 18, 500000, tzinfo=timezone.utc)

        filtered_df = filter_time_range(self.test_df, start_time, end_time)

        # Should include 16, 17, 18 but not 15 or 19
        self.assertEqual(len(filtered_df), 3)
        self.assertEqual(
            filtered_df.index[0],
            datetime(2025, 3, 18, 5, 1, 16, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            filtered_df.index[2],
            datetime(2025, 3, 18, 5, 1, 18, 0, tzinfo=timezone.utc),
        )

        # Test case 3: Empty result
        start_time = datetime(2025, 3, 18, 5, 2, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 3, 18, 5, 2, 10, 0, tzinfo=timezone.utc)

        filtered_df = filter_time_range(self.test_df, start_time, end_time)
        self.assertTrue(filtered_df.empty)

        # Test case 4: Empty input
        empty_df = pd.DataFrame()
        filtered_df = filter_time_range(empty_df, start_time, end_time)
        self.assertTrue(filtered_df.empty)
