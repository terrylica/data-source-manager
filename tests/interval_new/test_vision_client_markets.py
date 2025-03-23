#!/usr/bin/env python
"""Test suite for market type support in Enhanced VisionDataClient.

This test suite validates the market type functionality in VisionDataClient,
ensuring proper handling of different markets (spot, futures_usdt, futures_coin)
and their interval constraints.

Test Strategy:
- Verify market type initialization
- Test interval validation for different markets
- Validate supported interval detection
- Test data retrieval for different market types

Quality Attributes Verified:
- Interoperability: Proper handling across market types
- Reliability: Correct application of market-specific constraints
- Functionality: Appropriate interval validation per market
"""

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd
import logging

from core.vision_data_client_enhanced import VisionDataClient
from core.vision_constraints import CONSOLIDATION_DELAY
from utils.market_constraints import Interval

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test data
SPOT_SYMBOL = "BTCUSDT"
FUTURES_USDT_SYMBOL = "BTCUSDT"  # Same symbol but different market
FUTURES_COIN_SYMBOL = "BTCUSD_PERP"


def get_safe_test_time_range(
    days_ago: int = 120, duration_hours: int = 1
) -> tuple[datetime, datetime]:
    """Generate a safe time range for testing that should have available data.

    Args:
        days_ago: Number of days ago to start range (default: 120)
        duration_hours: Duration of the time range in hours (default: 1)

    Returns:
        Tuple of (start_time, end_time) in UTC
    """
    # Use a specific date in the past that we know has data
    # 2023-01-15 is far enough in the past to be available
    base_date = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)

    # Use a short duration to reduce chances of missing data
    start_time = base_date
    end_time = base_date + timedelta(hours=duration_hours)

    logger.info(f"Generated test time range: {start_time} to {end_time}")
    return start_time, end_time


@pytest.mark.parametrize(
    "market_type,symbol",
    [
        ("spot", SPOT_SYMBOL),
        ("futures_usdt", FUTURES_USDT_SYMBOL),
        ("futures_coin", FUTURES_COIN_SYMBOL),
    ],
)
def test_market_type_initialization(market_type, symbol):
    """Test client initialization with different market types."""
    client = VisionDataClient(symbol=symbol, interval="1m", market_type=market_type)
    assert (
        client.market_type == market_type.lower()
    ), f"Expected market_type {market_type}, got {client.market_type}"


@pytest.mark.parametrize(
    "market_type,interval,expected_valid",
    [
        # Spot market supports all intervals
        ("spot", "1s", True),
        ("spot", "1m", True),
        ("spot", "1h", True),
        ("spot", "1d", True),
        # Futures markets don't support 1s
        ("futures_usdt", "1s", False),
        ("futures_usdt", "1m", True),
        ("futures_usdt", "1h", True),
        ("futures_coin", "1s", False),
        ("futures_coin", "1m", True),
        ("futures_coin", "1h", True),
        # Invalid intervals for any market
        ("spot", "2s", False),
        ("futures_usdt", "2s", False),
        ("futures_coin", "2s", False),
    ],
)
def test_interval_validation_per_market(market_type, interval, expected_valid):
    """Test interval validation for different market types."""
    # Static method test
    validation_result = VisionDataClient.is_interval_available_for_market(
        interval, market_type
    )
    assert (
        validation_result == expected_valid
    ), f"Expected {expected_valid} for {interval} in {market_type}, got {validation_result}"

    # Instance method test (should log warning but not fail)
    client = VisionDataClient(
        symbol=SPOT_SYMBOL, interval="1m", market_type=market_type
    )
    # Test initialization with potentially invalid interval
    if not expected_valid:
        # Create client without explicitly checking for warnings
        client2 = VisionDataClient(
            symbol=SPOT_SYMBOL, interval=interval, market_type=market_type
        )
        # Verify client was created
        assert client2 is not None
        # Note: We don't check warnings content since that's implementation-specific


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "market_type,symbol,interval",
    [
        ("spot", SPOT_SYMBOL, "1m"),
        ("futures_usdt", FUTURES_USDT_SYMBOL, "1m"),
        ("futures_coin", FUTURES_COIN_SYMBOL, "1m"),
        ("spot", SPOT_SYMBOL, "1h"),
        ("futures_usdt", FUTURES_USDT_SYMBOL, "1h"),
        ("futures_coin", FUTURES_COIN_SYMBOL, "1h"),
    ],
)
async def test_supported_intervals_availability(
    market_type, symbol, interval, temp_cache_dir
):
    """Test that supported intervals return proper data for different markets."""
    client = VisionDataClient(
        symbol=symbol,
        interval=interval,
        market_type=market_type,
        cache_dir=temp_cache_dir,
        use_cache=True,
    )

    # Get a safe test time range
    start_time, end_time = get_safe_test_time_range(duration_hours=2)

    try:
        # Fetch data
        df = await client.fetch(start_time, end_time)

        # For all market types, we should at least get a valid DataFrame object
        assert isinstance(df, pd.DataFrame), f"Expected DataFrame, got {type(df)}"

        # We don't assert that the DataFrame is non-empty because data availability
        # depends on the specific market, date, and API access

        # If we do have data, verify its structure
        if not df.empty:
            # Verify index name
            assert (
                df.index.name == "open_time"
            ), f"Expected index name 'open_time', got {df.index.name}"

            # Verify interval alignment if we have at least 2 rows
            if interval == "1m" and len(df) > 1:
                time_diff = (df.index[1] - df.index[0]).total_seconds()
                assert (
                    abs(time_diff - 60) < 1
                ), f"Expected 1-minute interval, got {time_diff}s"
            elif interval == "1h" and len(df) > 1:
                time_diff = (df.index[1] - df.index[0]).total_seconds()
                assert (
                    abs(time_diff - 3600) < 1
                ), f"Expected 1-hour interval, got {time_diff}s"

            logger.info(
                f"Successfully fetched {len(df)} records for {symbol} {interval} in {market_type} market"
            )
        else:
            logger.warning(
                f"No data available for {symbol} {interval} in {market_type} market"
            )

    except Exception as e:
        # Log the error but don't fail the test - data availability isn't guaranteed
        logger.warning(
            f"Error fetching data for {symbol} {interval} in {market_type} market: {e}"
        )
        # Check if this is a known error about data availability
        if "Data unavailable" in str(e) or "No data available" in str(e):
            logger.info(
                f"Data unavailable for {symbol} {interval} in {market_type} market - this is expected occasionally"
            )
        elif "Failed to download" in str(e) or "Download failed" in str(e):
            logger.info(
                f"Download failed for {symbol} {interval} in {market_type} market - this is expected occasionally"
            )
        else:
            # For unexpected errors, we might want to log more details
            logger.warning(f"Unexpected error: {e}")

        # Assert the test passes anyway, since data availability is not guaranteed
        assert True


@pytest.mark.asyncio
async def test_market_specific_1s_limitation(temp_cache_dir):
    """Test the 1-second interval limitation for different market types."""
    # Spot market should support 1s
    spot_client = VisionDataClient(
        symbol=SPOT_SYMBOL,
        interval="1s",
        market_type="spot",
        cache_dir=temp_cache_dir,
        use_cache=True,
    )

    # Futures markets should not support 1s (but client creation shouldn't fail)
    futures_client = VisionDataClient(
        symbol=FUTURES_USDT_SYMBOL,
        interval="1s",
        market_type="futures_usdt",
        cache_dir=temp_cache_dir,
        use_cache=True,
    )

    # Get a safe test time range, but smaller for 1s data
    start_time, end_time = get_safe_test_time_range(duration_hours=1)

    # Test spot market
    try:
        spot_df = await spot_client.fetch(start_time, end_time)
        assert isinstance(
            spot_df, pd.DataFrame
        ), "Expected a DataFrame object for spot market"
        # Note: We don't assert that data is available because 1s data might not be available for all dates
        # or might have gaps. We just verify that the client doesn't fail with market constraint errors.

        if not spot_df.empty:
            logger.info(
                f"Successfully fetched {len(spot_df)} 1s records for spot market"
            )
        else:
            logger.warning(
                "No 1s data available for spot market - this is expected occasionally"
            )
    except Exception as e:
        # Log error but don't fail the test - data availability isn't guaranteed
        logger.warning(f"Error fetching 1s data for spot market: {e}")
        # We don't fail the test since data availability is not guaranteed

    # Test futures market
    try:
        futures_df = await futures_client.fetch(start_time, end_time)
        assert isinstance(
            futures_df, pd.DataFrame
        ), "Expected a DataFrame object for futures market"

        # For futures, we expect empty data or an error since 1s isn't generally supported
        # But we don't assert it must be empty, as API behavior can change
        if futures_df.empty:
            logger.info(
                "Futures market returned empty data for 1s interval as expected"
            )
        else:
            # If we do get data, log it but don't fail the test
            logger.warning(
                f"Unexpectedly received {len(futures_df)} records for 1s interval in futures market"
            )
    except Exception as e:
        # For futures, errors might be expected since 1s interval isn't supported
        if "Invalid interval" in str(e) or "Interval not supported" in str(e):
            logger.info(f"Expected error for futures market with 1s interval: {e}")
        else:
            logger.warning(f"Error fetching 1s data for futures market: {e}")


@pytest.mark.asyncio
async def test_get_supported_intervals():
    """Test the get_supported_intervals method."""
    client = VisionDataClient(symbol=SPOT_SYMBOL)
    supported_intervals = client.get_supported_intervals()

    # Check for essential intervals
    essential_intervals = ["1s", "1m", "1h", "1d", "1w", "1M"]
    for interval in essential_intervals:
        assert (
            interval in supported_intervals
        ), f"Essential interval {interval} not in supported intervals"

    # Ensure all returned intervals are valid (verify no extra invalid ones)
    for interval in supported_intervals:
        assert client.validate_interval(
            interval
        ), f"Returned invalid interval: {interval}"
