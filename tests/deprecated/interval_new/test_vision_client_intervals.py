#!/usr/bin/env python
"""Test suite for enhanced interval support in VisionDataClient.

This test suite validates the enhanced interval support in VisionDataClient,
ensuring proper handling of all Binance Vision API intervals.

Test Strategy:
- Verify initialization with different intervals
- Test URL construction for different intervals
- Validate time alignment for different intervals
- Test data retrieval with different intervals

Quality Attributes Verified:
- Reliability: Consistent handling across all intervals
- Interoperability: Proper URL construction for all intervals
- Functionality: Correct data retrieval for all intervals
"""

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd
import logging
from pathlib import Path
import tempfile

from core.vision_data_client_enhanced import VisionDataClient
from core.vision_constraints import CONSOLIDATION_DELAY, get_vision_url, FileType
from utils.market_constraints import Interval

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


@pytest.mark.parametrize(
    "interval_str",
    [
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
    ],
)
def test_vision_url_construction(interval_str):
    """Test Vision API URL construction for different intervals.

    This test verifies that the URL construction logic correctly handles all supported intervals.
    """
    symbol = "BTCUSDT"
    date = datetime(2023, 1, 15, tzinfo=timezone.utc)

    # Test data URL construction
    data_url = get_vision_url(symbol, interval_str, date, FileType.DATA)
    expected_data_url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/{interval_str}/{symbol}-{interval_str}-2023-01-15.zip"
    assert (
        data_url == expected_data_url
    ), f"Expected data URL {expected_data_url}, got {data_url}"

    # Test checksum URL construction
    checksum_url = get_vision_url(symbol, interval_str, date, FileType.CHECKSUM)
    expected_checksum_url = f"{expected_data_url}.CHECKSUM"
    assert (
        checksum_url == expected_checksum_url
    ), f"Expected checksum URL {expected_checksum_url}, got {checksum_url}"


@pytest.mark.asyncio
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
    ],
)
async def test_time_alignment(interval_str, expected_seconds, temp_cache_dir):
    """Test time alignment for different intervals.

    This test verifies that the time alignment logic correctly handles all supported intervals.
    """
    # Create a client with the specified interval
    async with VisionDataClient(
        "BTCUSDT", interval=interval_str, cache_dir=temp_cache_dir, use_cache=False
    ) as client:
        # Create a time range with unaligned boundaries
        now = datetime.now(timezone.utc)
        unaligned_start = now.replace(microsecond=123456)
        unaligned_end = unaligned_start + timedelta(seconds=expected_seconds * 2.5)

        # Get time boundaries using the client's fetch method
        from utils.time_alignment import TimeRangeManager

        # Validate time boundaries
        time_boundaries = TimeRangeManager.get_time_boundaries(
            unaligned_start, unaligned_end, client.interval_obj
        )
        aligned_start = time_boundaries["adjusted_start"]
        aligned_end = time_boundaries["adjusted_end"]

        # Verify that microseconds are removed
        assert (
            aligned_start.microsecond == 0
        ), f"Expected microseconds to be 0, got {aligned_start.microsecond}"
        assert (
            aligned_end.microsecond == 0
        ), f"Expected microseconds to be 0, got {aligned_end.microsecond}"

        # Verify alignment based on interval
        if interval_str in ["1m", "3m", "5m", "15m", "30m"]:
            assert (
                aligned_start.second == 0
            ), f"Expected seconds to be 0 for minute interval, got {aligned_start.second}"
            assert (
                aligned_end.second == 0
            ), f"Expected seconds to be 0 for minute interval, got {aligned_end.second}"

        if interval_str in ["1h", "2h", "4h", "6h", "8h", "12h"]:
            assert (
                aligned_start.second == 0
            ), f"Expected seconds to be 0 for hour interval, got {aligned_start.second}"
            assert (
                aligned_start.minute == 0
            ), f"Expected minutes to be 0 for hour interval, got {aligned_start.minute}"
            assert (
                aligned_end.second == 0
            ), f"Expected seconds to be 0 for hour interval, got {aligned_end.second}"
            assert (
                aligned_end.minute == 0
            ), f"Expected minutes to be 0 for hour interval, got {aligned_end.minute}"

        if interval_str in ["1d", "3d", "1w"]:
            assert (
                aligned_start.second == 0
            ), f"Expected seconds to be 0 for day interval, got {aligned_start.second}"
            assert (
                aligned_start.minute == 0
            ), f"Expected minutes to be 0 for day interval, got {aligned_start.minute}"
            assert (
                aligned_start.hour == 0
            ), f"Expected hours to be 0 for day interval, got {aligned_start.hour}"
            assert (
                aligned_end.second == 0
            ), f"Expected seconds to be 0 for day interval, got {aligned_end.second}"
            assert (
                aligned_end.minute == 0
            ), f"Expected minutes to be 0 for day interval, got {aligned_end.minute}"
            assert (
                aligned_end.hour == 0
            ), f"Expected hours to be 0 for day interval, got {aligned_end.hour}"
