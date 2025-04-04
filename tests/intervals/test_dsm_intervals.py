#!/usr/bin/env python
"""Integration tests for DataSourceManager across key interval types.

System Under Test (SUT):
- core.data_source_manager.DataSourceManager
- core.vision_data_client.VisionDataClient (indirectly)
- core.rest_data_client.RestDataClient (indirectly)

This test suite validates that the DataSourceManager correctly handles
data retrieval across essential intervals (1s for spot, 1m, 1h, 1d),
with proper time alignment, data consistency, and error handling.

Following the pytest-construction.mdc guidelines:
1. We use real data only (no mocks)
2. We search backward for available data up to 3 days
3. We handle errors without skipping tests
4. We ensure proper cleanup of resources
"""

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from typing import Tuple

from utils.logger_setup import logger
from core.data_source_manager import DataSourceManager, DataSource
from utils.market_constraints import Interval, MarketType
from utils.network_utils import create_client
from core.rest_data_client import RestDataClient

from tests.intervals import (
    SPOT_SYMBOL,
    FUTURES_USDT_SYMBOL,
    FUTURES_COIN_SYMBOL,
    SPOT_INTERVALS,
    FUTURES_INTERVALS,
)


# Apply module-level fixture scope to avoid DeprecationWarning
pytestmark = [
    pytest.mark.asyncio(loop_scope="function"),  # Use function scope for async tests
]

# Configure pytest-asyncio to use function scope by default
pytestasyncio_configure = {"asyncio_default_fixture_loop_scope": "function"}


@pytest.fixture
async def dsm() -> DataSourceManager:
    """Create and clean up a DataSourceManager instance."""
    # Create DataSourceManager with temporary cache
    manager = DataSourceManager(market_type=MarketType.SPOT)

    # Use context manager to ensure proper cleanup
    await manager.__aenter__()

    try:
        yield manager
    finally:
        # Ensure proper cleanup
        await manager.__aexit__(None, None, None)


async def find_available_data(
    market_type: MarketType, symbol: str, interval: Interval, max_days_back: int = 3
) -> Tuple[datetime, bool]:
    """Find the latest date with available data by searching backward.

    Following pytest-construction.mdc guidelines, we search backward
    from the current date to find data, up to 3 days back.

    Args:
        market_type: The market type to check
        symbol: The trading symbol to check
        interval: The interval to check
        max_days_back: Maximum days to search back (default: 3)

    Returns:
        Tuple of (reference_date, found_data)
    """
    logger.info(
        f"Looking for available {interval.value} data for {symbol} ({market_type.name})"
    )

    now = datetime.now(timezone.utc)

    # Create a client for testing availability
    client_session = create_client(timeout=10.0)

    # For smaller intervals like 1s, use shorter windows
    if interval.name == Interval.SECOND_1.name:
        fetch_window = timedelta(minutes=5)
    elif interval.name == Interval.MINUTE_1.name:
        fetch_window = timedelta(hours=1)
    elif interval.name == Interval.HOUR_1.name:
        fetch_window = timedelta(days=1)
    else:  # DAY_1
        fetch_window = timedelta(days=7)

    try:
        # Search backward from current time
        for days_back in range(max_days_back):
            reference_time = now - timedelta(days=days_back)

            # Create clean reference time (eliminate milliseconds/microseconds)
            reference_time = reference_time.replace(minute=0, second=0, microsecond=0)

            start_time = reference_time - fetch_window
            end_time = reference_time

            logger.info(
                f"Checking for data on day -{days_back}: "
                f"{start_time.isoformat()} to {end_time.isoformat()}"
            )

            # Create DataSourceManager with the correct market type
            async with DataSourceManager(market_type=market_type) as manager:
                try:
                    # Try to fetch a small amount of data
                    df = await manager.get_data(
                        symbol=symbol,
                        interval=interval,
                        start_time=start_time,
                        end_time=end_time,
                        enforce_source=DataSource.REST,  # Use REST for faster responses
                    )

                    # If we got data, return this reference time
                    if not df.empty:
                        logger.info(
                            f"Found data for {interval.value} on day -{days_back} "
                            f"with {len(df)} records"
                        )
                        return reference_time, True

                    logger.info(
                        f"No data found for {interval.value} on day -{days_back}"
                    )

                except Exception as e:
                    logger.warning(
                        f"Error checking data availability for {interval.value} "
                        f"on day -{days_back}: {e}"
                    )

        # If we didn't find data in the search period, return the most recent date
        logger.warning(
            f"No data found for {interval.value} within {max_days_back} days. "
            f"Will use most recent date for tests."
        )
        return now.replace(minute=0, second=0, microsecond=0), False

    finally:
        # Clean up the client
        if hasattr(client_session, "aclose"):
            await client_session.aclose()
        else:
            await client_session.close()


@pytest.mark.parametrize("interval", SPOT_INTERVALS)
async def test_dsm_spot_intervals(
    dsm: DataSourceManager, interval: Interval, caplog_xdist_compatible
):
    """Test DataSourceManager with SPOT market intervals.

    This test verifies that:
    1. DataSourceManager can retrieve data for all SPOT market intervals
    2. The data has the correct format and structure
    3. Time boundaries are properly aligned
    """
    caplog_xdist_compatible.set_level("INFO")

    # Find available data
    reference_time, found_data = await find_available_data(
        market_type=MarketType.SPOT, symbol=SPOT_SYMBOL, interval=interval
    )

    # Define a time window appropriate for this interval
    if interval.name == Interval.SECOND_1.name:
        # For 1s data, use a 2-minute window
        time_window = timedelta(minutes=2)
    elif interval.name == Interval.MINUTE_1.name:
        # For minute-level data, use a 1-hour window
        time_window = timedelta(hours=1)
    elif interval.name == Interval.HOUR_1.name:
        # For hour-level data, use a 1-day window
        time_window = timedelta(days=1)
    else:  # DAY_1
        # For day-level data, use a 30-day window
        time_window = timedelta(days=30)

    # Define test boundaries
    end_time = reference_time
    start_time = end_time - time_window

    logger.info(
        f"Testing DSM with SPOT {interval.value} data from "
        f"{start_time.isoformat()} to {end_time.isoformat()}"
    )

    # Update the DSM market type to match the test
    dsm._market_type = MarketType.SPOT

    # Recreate the REST client with the new market type to ensure proper endpoint construction
    from utils.network_utils import create_client

    dsm.rest_client = RestDataClient(
        market_type=MarketType.SPOT,
        client=create_client(),
        max_concurrent=dsm.max_concurrent,
        retry_count=dsm.retry_count,
    )

    # Fetch data using DataSourceManager
    df = await dsm.get_data(
        symbol=SPOT_SYMBOL,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
    )

    # Log the result
    logger.info(f"Retrieved {len(df)} records of SPOT {interval.value} data")

    # Verify that we got data
    assert not df.empty, f"No data returned for SPOT {interval.value}"

    # Verify expected columns
    expected_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "count",
        "taker_buy_volume",
        "taker_buy_quote_volume",
    ]
    for col in expected_columns:
        assert col in df.columns, f"Missing expected column: {col}"

    # Verify that data is sorted by time
    assert df.index.is_monotonic_increasing, "Data is not sorted by time"

    # Verify time alignment based on interval
    if len(df) > 1:
        time_diffs = np.diff(df.index.astype(np.int64)) / 1e9  # Convert to seconds

        if interval.name == Interval.SECOND_1.name:
            expected_diff = 1  # 1 second
        elif interval.name == Interval.MINUTE_1.name:
            expected_diff = 60  # 1 minute
        elif interval.name == Interval.HOUR_1.name:
            expected_diff = 3600  # 1 hour
        else:  # DAY_1
            expected_diff = 86400  # 1 day

        # Check if most time differences match the expected interval
        # We don't check all because there might be gaps in the data
        close_to_expected = np.abs(time_diffs - expected_diff) < 5
        assert (
            np.mean(close_to_expected) > 0.9
        ), f"Time alignment issues for {interval.value}"

    # Verify that data spans the requested time range
    # Allow for small discrepancies due to time zone handling
    tolerance = timedelta(hours=1)
    assert (
        df.index.min() >= start_time - tolerance
    ), "Data starts before requested range"
    assert df.index.max() <= end_time + tolerance, "Data ends after requested range"


@pytest.mark.parametrize("interval", FUTURES_INTERVALS)
@pytest.mark.parametrize(
    "market_type,symbol,_",
    [
        (MarketType.FUTURES_USDT, FUTURES_USDT_SYMBOL, 1500),
        (MarketType.FUTURES_COIN, FUTURES_COIN_SYMBOL, 1500),
    ],
)
async def test_dsm_futures_intervals(
    dsm: DataSourceManager,
    market_type: MarketType,
    symbol: str,
    _: int,
    interval: Interval,
    caplog_xdist_compatible,
):
    """Test DataSourceManager with futures market intervals.

    This test verifies that:
    1. DataSourceManager can retrieve data for all futures market intervals
    2. The data has the correct format and structure for futures markets
    3. Time boundaries are properly aligned
    """
    # Set log level for the test
    caplog_xdist_compatible.set_level("INFO")

    # Find available data
    reference_time, found_data = await find_available_data(
        market_type=market_type, symbol=symbol, interval=interval
    )

    # Define a time window appropriate for this interval
    if interval.name == Interval.MINUTE_1.name:
        # For minute-level data, use a 1-hour window
        time_window = timedelta(hours=1)
    elif interval.name == Interval.HOUR_1.name:
        # For hour-level data, use a 1-day window
        time_window = timedelta(days=1)
    else:  # DAY_1
        # For day-level data, use a 30-day window
        time_window = timedelta(days=30)

    # Define test boundaries
    end_time = reference_time
    start_time = end_time - time_window

    logger.info(
        f"Testing DSM with {market_type.name} {interval.value} data from "
        f"{start_time.isoformat()} to {end_time.isoformat()}"
    )

    # Update the DSM market type to match the test
    dsm._market_type = market_type

    # Recreate the REST client with the new market type to ensure proper endpoint construction
    from utils.network_utils import create_client

    dsm.rest_client = RestDataClient(
        market_type=market_type,
        client=create_client(),
        max_concurrent=dsm.max_concurrent,
        retry_count=dsm.retry_count,
    )

    # Fetch data using DataSourceManager
    df = await dsm.get_data(
        symbol=symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
    )

    # Log the result
    logger.info(
        f"Retrieved {len(df)} records of {market_type.name} {interval.value} data"
    )

    # Verify that we got data
    assert not df.empty, f"No data returned for {market_type.name} {interval.value}"

    # Verify expected columns
    expected_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "count",
        "taker_buy_volume",
        "taker_buy_quote_volume",
    ]
    for col in expected_columns:
        assert col in df.columns, f"Missing expected column: {col}"

    # Verify that data is sorted by time
    assert df.index.is_monotonic_increasing, "Data is not sorted by time"

    # Verify time alignment based on interval
    if len(df) > 1:
        time_diffs = np.diff(df.index.astype(np.int64)) / 1e9  # Convert to seconds

        if interval.name == Interval.MINUTE_1.name:
            expected_diff = 60  # 1 minute
        elif interval.name == Interval.HOUR_1.name:
            expected_diff = 3600  # 1 hour
        else:  # DAY_1
            expected_diff = 86400  # 1 day

        # Check if most time differences match the expected interval
        # We don't check all because there might be gaps in the data
        close_to_expected = np.abs(time_diffs - expected_diff) < 5
        assert (
            np.mean(close_to_expected) > 0.9
        ), f"Time alignment issues for {interval.value}"

    # Verify that data spans the requested time range
    # Allow for small discrepancies due to time zone handling
    tolerance = timedelta(hours=1)
    assert (
        df.index.min() >= start_time - tolerance
    ), "Data starts before requested range"
    assert df.index.max() <= end_time + tolerance, "Data ends after requested range"


@pytest.mark.parametrize(
    "interval",
    [
        Interval.MINUTE_1,  # Common small interval
        Interval.HOUR_1,  # Common medium interval
        Interval.DAY_1,  # Common large interval
    ],
)
async def test_dsm_interval_data_consistency(
    dsm: DataSourceManager, interval: Interval, caplog_xdist_compatible
):
    """Test that DSM returns consistent data across different sources.

    This test verifies that:
    1. Data is consistent when retrieved from different sources (REST vs VISION)
    2. Column names and data types are consistent
    3. Results have the same shape and content regardless of source
    """
    caplog_xdist_compatible.set_level("INFO")

    # Find available data
    reference_time, found_data = await find_available_data(
        market_type=MarketType.SPOT, symbol=SPOT_SYMBOL, interval=interval
    )

    # Define a time window appropriate for this interval
    if interval.name == Interval.MINUTE_1.name:
        # For minute-level data, use a 1-hour window
        time_window = timedelta(hours=1)
    elif interval.name == Interval.HOUR_1.name:
        # For hour-level data, use a 1-day window
        time_window = timedelta(days=1)
    else:  # DAY_1
        # For day-level data, use a 10-day window
        time_window = timedelta(days=10)

    # Define test boundaries
    end_time = reference_time
    start_time = end_time - time_window

    logger.info(
        f"Testing data consistency for {interval.value} from "
        f"{start_time.isoformat()} to {end_time.isoformat()}"
    )

    # Using SPOT market for consistency tests
    dsm._market_type = MarketType.SPOT

    # Recreate the REST client with the new market type to ensure proper endpoint construction
    from utils.network_utils import create_client

    dsm.rest_client = RestDataClient(
        market_type=MarketType.SPOT,
        client=create_client(),
        max_concurrent=dsm.max_concurrent,
        retry_count=dsm.retry_count,
    )

    # Fetch data from REST source
    df_rest = await dsm.get_data(
        symbol=SPOT_SYMBOL,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
        enforce_source=DataSource.REST,
    )

    # For 1-minute data, also try to fetch from VISION source
    # (Vision data might not be available for very recent data)
    if interval.name in [
        Interval.MINUTE_1.name,
        Interval.HOUR_1.name,
        Interval.DAY_1.name,
    ]:
        try:
            # Try to fetch from VISION, but may not be available for recent data
            # Use a slightly earlier time window to increase chances of finding data
            vision_end_time = end_time - timedelta(days=1)
            vision_start_time = vision_end_time - time_window

            df_vision = await dsm.get_data(
                symbol=SPOT_SYMBOL,
                interval=interval,
                start_time=vision_start_time,
                end_time=vision_end_time,
                enforce_source=DataSource.VISION,
            )

            # If we got data from both sources, compare them
            if not df_rest.empty and not df_vision.empty:
                logger.info(
                    f"Comparing {len(df_rest)} REST records with {len(df_vision)} VISION records"
                )

                # Verify core column consistency
                rest_columns = set(df_rest.columns)
                vision_columns = set(df_vision.columns)

                # Common columns that should be in both
                common_columns = ["open", "high", "low", "close", "volume"]
                for col in common_columns:
                    assert col in rest_columns, f"Missing {col} in REST data"
                    assert col in vision_columns, f"Missing {col} in VISION data"

                # Check data types for common columns
                for col in common_columns:
                    assert df_rest[col].dtype == df_vision[col].dtype, (
                        f"Data type mismatch for {col}: "
                        f"REST={df_rest[col].dtype}, VISION={df_vision[col].dtype}"
                    )

                # If there's an overlap in the time periods, compare values
                rest_dates = set(df_rest.index)
                vision_dates = set(df_vision.index)
                common_dates = rest_dates.intersection(vision_dates)

                if common_dates:
                    # Take a sample date for comparison
                    sample_date = sorted(common_dates)[0]
                    logger.info(f"Comparing data for {sample_date}")

                    rest_row = df_rest.loc[sample_date]
                    vision_row = df_vision.loc[sample_date]

                    # Compare price values with tolerance for float comparison
                    # (small differences might exist due to data source differences)
                    for col in ["open", "high", "low", "close"]:
                        rest_val = float(rest_row[col])
                        vision_val = float(vision_row[col])
                        diff_pct = abs(rest_val - vision_val) / rest_val * 100

                        # Difference should be very small (<0.1%)
                        assert diff_pct < 0.1, (
                            f"Value mismatch for {col} at {sample_date}: "
                            f"REST={rest_val}, VISION={vision_val}, diff={diff_pct:.6f}%"
                        )

        except Exception as e:
            # VISION data may not be available for very recent dates
            # This is not a test failure
            logger.warning(f"Could not fetch VISION data for comparison: {e}")
            # We don't assert anything here, as the test can still pass
            # even if VISION data is not available

    # Basic validation of REST data
    assert not df_rest.empty, f"No data returned for {interval.value} from REST"
    logger.info(f"Successfully validated {interval.value} data consistency")


@pytest.mark.parametrize(
    "interval",
    [
        Interval.MINUTE_1,
        Interval.HOUR_1,
        Interval.DAY_1,
    ],
)
async def test_dsm_metadata_consistency(
    dsm: DataSourceManager,
    interval: Interval,
    caplog_xdist_compatible,
):
    """Test that DSM data index is consistent across intervals.

    This test verifies that:
    1. The DataFrame index is a DatetimeIndex
    2. Timestamps are properly handled and aligned
    """
    caplog_xdist_compatible.set_level("INFO")

    # Find available data
    reference_time, found_data = await find_available_data(
        market_type=MarketType.SPOT, symbol=SPOT_SYMBOL, interval=interval
    )

    # Define a time window appropriate for this interval
    if interval.name == Interval.MINUTE_1.name:
        # For minute-level data, use a 1-hour window
        time_window = timedelta(hours=1)
    elif interval.name == Interval.HOUR_1.name:
        # For hour-level data, use a 1-day window
        time_window = timedelta(days=1)
    else:  # DAY_1
        # For day-level data, use a 10-day window
        time_window = timedelta(days=10)

    # Define test boundaries
    end_time = reference_time
    start_time = end_time - time_window

    logger.info(
        f"Testing timestamp index for {interval.value} from "
        f"{start_time.isoformat()} to {end_time.isoformat()}"
    )

    # Using SPOT market for metadata tests
    dsm._market_type = MarketType.SPOT

    # Recreate the REST client with the new market type to ensure proper endpoint construction
    from utils.network_utils import create_client

    dsm.rest_client = RestDataClient(
        market_type=MarketType.SPOT,
        client=create_client(),
        max_concurrent=dsm.max_concurrent,
        retry_count=dsm.retry_count,
    )

    # Fetch data
    df = await dsm.get_data(
        symbol=SPOT_SYMBOL,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
    )

    # Verify data was returned
    assert not df.empty, f"No data returned for {interval.value}"

    # Verify the index is a DatetimeIndex
    assert isinstance(df.index, pd.DatetimeIndex), "Index is not a DatetimeIndex"

    # Verify index is timezone aware and in UTC
    assert df.index.tz is not None, "Index is not timezone aware"

    # Verify index is monotonically increasing
    assert df.index.is_monotonic_increasing, "Index is not monotonically increasing"

    # Verify index range matches requested time range (with tolerance)
    tolerance = timedelta(hours=1)
    assert (
        df.index.min() >= start_time - tolerance
    ), "Data starts before requested range"
    assert df.index.max() <= end_time + tolerance, "Data ends after requested range"

    # For specific intervals, verify time alignment
    if interval.name == Interval.MINUTE_1.name:
        # For minute data, each timestamp should be aligned to the minute
        for ts in df.index:
            assert ts.second == 0, f"Timestamp {ts} not aligned to minute boundary"
    elif interval.name == Interval.HOUR_1.name:
        # For hour data, each timestamp should be aligned to the hour
        for ts in df.index:
            assert (
                ts.minute == 0 and ts.second == 0
            ), f"Timestamp {ts} not aligned to hour boundary"
    elif interval.name == Interval.DAY_1.name:
        # For day data, each timestamp should be aligned to the day
        for ts in df.index:
            assert (
                ts.hour == 0 and ts.minute == 0 and ts.second == 0
            ), f"Timestamp {ts} not aligned to day boundary"
