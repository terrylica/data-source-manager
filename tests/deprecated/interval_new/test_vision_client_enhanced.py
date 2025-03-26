#!/usr/bin/env python
"""Test suite for enhanced interval support in VisionDataClient.

This test suite validates the enhanced interval support in the upgraded VisionDataClient,
ensuring proper handling of all Binance Vision API intervals.

Test Strategy:
- Verify initialization with different intervals
- Test expected record calculation for different intervals
- Validate interval-specific time alignment
- Test interval validation functionality

Quality Attributes Verified:
- Reliability: Consistent handling across all intervals
- Interoperability: Proper interval conversion and validation
- Functionality: Correct record calculation for all intervals
"""

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd
import logging
from pathlib import Path
import tempfile

from core.vision_data_client_enhanced import VisionDataClient
from core.vision_constraints import CONSOLIDATION_DELAY
from utils.market_constraints import Interval
from utils.time_alignment import TimeRangeManager, get_interval_floor

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def get_test_time_range(
    days_ago: int = None, duration: timedelta = timedelta(hours=1)
) -> tuple[datetime, datetime]:
    """Generate a time range for testing.

    Args:
        days_ago: Number of days ago to start range (if None, uses CONSOLIDATION_DELAY + 1 day for safety)
        duration: Duration of the time range (default: 1 hour)

    Returns:
        Tuple of (start_time, end_time) in UTC, rounded to nearest second
    """
    now = datetime.now(timezone.utc)

    # If days_ago not specified, use CONSOLIDATION_DELAY + 1 day for safety
    if days_ago is None:
        days_ago = (CONSOLIDATION_DELAY + timedelta(days=1)).days

    # Round to nearest second to avoid sub-second precision issues
    start_time = (now - timedelta(days=days_ago)).replace(microsecond=0)
    end_time = (start_time + duration).replace(microsecond=0)
    logger.info(f"Generated test time range: {start_time} to {end_time}")
    return start_time, end_time


@pytest.mark.parametrize(
    "interval_str,interval_enum",
    [
        ("1s", Interval.SECOND_1),
        ("1m", Interval.MINUTE_1),
        ("3m", Interval.MINUTE_3),
        ("5m", Interval.MINUTE_5),
        ("15m", Interval.MINUTE_15),
        ("30m", Interval.MINUTE_30),
        ("1h", Interval.HOUR_1),
        ("2h", Interval.HOUR_2),
        ("4h", Interval.HOUR_4),
        ("6h", Interval.HOUR_6),
        ("8h", Interval.HOUR_8),
        ("12h", Interval.HOUR_12),
        ("1d", Interval.DAY_1),
        ("3d", Interval.DAY_3),
        ("1w", Interval.WEEK_1),
        ("1M", Interval.MONTH_1),
    ],
)
def test_client_initialization(interval_str, interval_enum):
    """Test client initialization with different intervals.

    This test verifies that the client can be initialized with all supported intervals
    and correctly maps string interval representations to Interval enum values.
    """
    client = VisionDataClient("BTCUSDT", interval=interval_str)
    assert (
        client.interval == interval_str
    ), f"Expected interval {interval_str}, got {client.interval}"
    assert (
        client.interval_obj == interval_enum
    ), f"Expected interval enum {interval_enum}, got {client.interval_obj}"


def test_get_supported_intervals():
    """Test the get_supported_intervals method.

    This test verifies that the client correctly returns all supported intervals.
    """
    client = VisionDataClient("BTCUSDT")
    supported_intervals = client.get_supported_intervals()

    # Verify all expected intervals are in the list
    expected_intervals = [
        "1s",
        "1m",
        "3m",
        "5m",
        "15m",
        "30m",
        "1h",
        "2h",
        "4h",
        "6h",
        "8h",
        "12h",
        "1d",
        "3d",
        "1w",
        "1M",
    ]

    for interval in expected_intervals:
        assert (
            interval in supported_intervals
        ), f"Expected interval {interval} not found in supported intervals"

    # Verify the count matches
    assert len(supported_intervals) == len(
        expected_intervals
    ), "Unexpected number of supported intervals"


@pytest.mark.parametrize(
    "interval_str,valid",
    [
        ("1s", True),
        ("1m", True),
        ("3m", True),
        ("5m", True),
        ("15m", True),
        ("30m", True),
        ("1h", True),
        ("2h", True),
        ("4h", True),
        ("6h", True),
        ("8h", True),
        ("12h", True),
        ("1d", True),
        ("3d", True),
        ("1w", True),
        ("1M", True),
        ("2s", False),  # Invalid interval
        ("2m", False),  # Invalid interval
        ("7h", False),  # Invalid interval
        ("2d", False),  # Invalid interval
        ("2w", False),  # Invalid interval
        ("2M", False),  # Invalid interval
    ],
)
def test_validate_interval(interval_str, valid):
    """Test the validate_interval method.

    This test verifies that the client correctly validates intervals.
    """
    client = VisionDataClient("BTCUSDT")
    assert (
        client.validate_interval(interval_str) == valid
    ), f"Expected validate_interval({interval_str}) to return {valid}"


@pytest.mark.parametrize(
    "interval_str,expected_seconds",
    [
        ("1s", 1),
        ("1m", 60),
        ("3m", 180),
        ("5m", 300),
        ("15m", 900),
        ("30m", 1800),
        ("1h", 3600),
        ("2h", 7200),
        ("4h", 14400),
        ("6h", 21600),
        ("8h", 28800),
        ("12h", 43200),
        ("1d", 86400),
        ("3d", 259200),
        ("1w", 604800),
    ],
)
def test_get_interval_seconds(interval_str, expected_seconds):
    """Test the get_interval_seconds method.

    This test verifies that the client correctly calculates the number of seconds in each interval.
    """
    client = VisionDataClient("BTCUSDT", interval=interval_str)
    assert (
        client.get_interval_seconds() == expected_seconds
    ), f"Expected {expected_seconds} seconds for {interval_str}, got {client.get_interval_seconds()}"


@pytest.mark.parametrize(
    "interval_str,duration_hours,expected_records",
    [
        ("1s", 1, 3600),  # 1 hour = 3600 seconds
        ("1m", 1, 60),  # 1 hour = 60 minutes
        ("5m", 1, 12),  # 1 hour = 12 5-minute intervals
        ("15m", 1, 4),  # 1 hour = 4 15-minute intervals
        ("30m", 1, 2),  # 1 hour = 2 30-minute intervals
        ("1h", 1, 1),  # 1 hour = 1 1-hour interval
        ("1h", 2, 2),  # 2 hours = 2 1-hour intervals
        ("4h", 4, 1),  # 4 hours = 1 4-hour interval
        ("1d", 24, 1),  # 24 hours = 1 day
    ],
)
def test_get_expected_records_for_timerange(
    interval_str, duration_hours, expected_records
):
    """Test the get_expected_records_for_timerange method.

    This test verifies that the client correctly calculates the expected number of records
    for a given time range based on the interval.
    """
    client = VisionDataClient("BTCUSDT", interval=interval_str)

    # Create a time range
    start_time = datetime(2023, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=duration_hours)

    # Calculate expected records
    records = client.get_expected_records_for_timerange(start_time, end_time)

    assert (
        records == expected_records
    ), f"Expected {expected_records} records for {interval_str} over {duration_hours} hours, got {records}"


@pytest.mark.parametrize(
    "interval_str,unaligned_time,expected_aligned",
    [
        # 1-second interval - should floor to the second
        (
            "1s",
            datetime(2023, 1, 1, 12, 34, 56, 789000, tzinfo=timezone.utc),
            datetime(2023, 1, 1, 12, 34, 56, 0, tzinfo=timezone.utc),
        ),
        # 1-minute interval - should floor to the minute
        (
            "1m",
            datetime(2023, 1, 1, 12, 34, 56, 789000, tzinfo=timezone.utc),
            datetime(2023, 1, 1, 12, 34, 0, 0, tzinfo=timezone.utc),
        ),
        # 5-minute interval - should floor to the nearest 5-minute boundary
        (
            "5m",
            datetime(2023, 1, 1, 12, 37, 56, 789000, tzinfo=timezone.utc),
            datetime(2023, 1, 1, 12, 35, 0, 0, tzinfo=timezone.utc),
        ),
        # 1-hour interval - should floor to the hour
        (
            "1h",
            datetime(2023, 1, 1, 12, 34, 56, 789000, tzinfo=timezone.utc),
            datetime(2023, 1, 1, 12, 0, 0, 0, tzinfo=timezone.utc),
        ),
        # 1-day interval - should floor to the day
        (
            "1d",
            datetime(2023, 1, 1, 12, 34, 56, 789000, tzinfo=timezone.utc),
            datetime(2023, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc),
        ),
    ],
)
def test_time_alignment_with_intervals(interval_str, unaligned_time, expected_aligned):
    """Test time alignment with different intervals.

    This test verifies that the time alignment logic correctly handles all supported intervals.
    """
    # Get the interval enum
    client = VisionDataClient("BTCUSDT", interval=interval_str)
    interval_obj = client.interval_obj

    # Use the get_interval_floor function to align the time
    aligned_time = get_interval_floor(unaligned_time, interval_obj)

    assert (
        aligned_time == expected_aligned
    ), f"Expected {expected_aligned} for {interval_str}, got {aligned_time}"


@pytest.mark.parametrize(
    "interval_str,start_offset,end_offset,expected_boundaries",
    [
        # 1-second interval with unaligned boundaries
        ("1s", {"microsecond": 123456}, {"microsecond": 789012}, {"microsecond": 0}),
        # 1-minute interval with unaligned boundaries
        (
            "1m",
            {"second": 30, "microsecond": 123456},
            {"second": 45, "microsecond": 789012},
            {"second": 0, "microsecond": 0},
        ),
        # 1-hour interval with unaligned boundaries
        (
            "1h",
            {"minute": 30, "second": 30, "microsecond": 123456},
            {"minute": 45, "second": 45, "microsecond": 789012},
            {"minute": 0, "second": 0, "microsecond": 0},
        ),
        # 1-day interval with unaligned boundaries
        (
            "1d",
            {"hour": 12, "minute": 30, "second": 30, "microsecond": 123456},
            {"hour": 18, "minute": 45, "second": 45, "microsecond": 789012},
            {"hour": 0, "minute": 0, "second": 0, "microsecond": 0},
        ),
    ],
)
def test_time_boundaries_with_intervals(
    interval_str, start_offset, end_offset, expected_boundaries
):
    """Test time boundary calculations with different intervals.

    This test verifies that the time boundary calculations correctly handle all supported intervals.
    """
    # Create a client with the specified interval
    client = VisionDataClient("BTCUSDT", interval=interval_str)

    # Create base times
    base_time = datetime(2023, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc)

    # Apply offsets to create unaligned times
    start_time = base_time.replace(**start_offset)
    end_time = (base_time + timedelta(hours=2)).replace(**end_offset)

    # Get time boundaries using TimeR
