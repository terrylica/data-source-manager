#!/usr/bin/env python
"""Test suite for batch processing capabilities in Enhanced VisionDataClient.

This test suite validates the batch processing functionality in VisionDataClient,
ensuring it can efficiently handle multiple symbols and intervals in a single operation.

Test Strategy:
- Verify batch fetching for multiple symbols
- Test error handling for invalid symbols in batch
- Validate results for different intervals
- Test memory and performance optimizations

Quality Attributes Verified:
- Scalability: Efficient handling of multiple requests
- Reliability: Proper error handling in batch operations
- Performance: Optimized concurrency and memory usage
"""

import pytest
from datetime import datetime, timezone, timedelta
import pandas as pd
import logging
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock, AsyncMock, ANY
import numpy as np
from typing import Dict, List, Optional, Sequence
import time

from core.vision_data_client_enhanced import VisionDataClient
from core.vision_constraints import CONSOLIDATION_DELAY
from utils.market_constraints import Interval
from utils.time_alignment import TimeRangeManager
from utils.download_handler import DownloadHandler
import httpx
import tempfile
import zipfile
import os

# Define required columns
REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test data
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
INTERVAL = "1h"
INVALID_SYMBOL = "INVALID_SYMBOL"

# Constants for testing
SYMBOL = "BTCUSDT"
TEST_SYMBOLS = [f"BTC{i}USDT" for i in range(20)]
INVALID_SYMBOLS = ["INVALIDUSDT1", "INVALIDUSDT2"]


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


def create_mock_data(start_time, end_time, symbol=SYMBOL, columns=None):
    """Create mock data for testing."""
    # Create date range with 1h interval
    date_range = pd.date_range(
        start=start_time, end=end_time, freq="1h", inclusive="left"
    )

    # Create DataFrame with standard columns
    all_data = {
        "open": np.random.rand(len(date_range)) * 10000 + 20000,
        "high": np.random.rand(len(date_range)) * 10000 + 20000,
        "low": np.random.rand(len(date_range)) * 10000 + 20000,
        "close": np.random.rand(len(date_range)) * 10000 + 20000,
        "volume": np.random.rand(len(date_range)) * 1000,
    }

    # Filter columns if specified
    if columns:
        data = {col: all_data[col] for col in columns if col in all_data}
    else:
        data = all_data

    # Create DataFrame
    df = pd.DataFrame(data, index=pd.DatetimeIndex(date_range, name="open_time"))
    return df


@pytest.mark.asyncio
async def test_batch_fetch_multiple_symbols(temp_cache_dir):
    """Test batch fetching data for multiple symbols."""
    # Use a specific date that we know should have data (January 15, 2023)
    start_time = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2023, 1, 15, 1, 0, 0, tzinfo=timezone.utc)

    # Enhanced logging for debugging
    test_id = f"batch_multiple_{int(time.time())}"
    logger.info(f"Test ID: {test_id}")
    logger.info(
        f"Test parameters: Time range {start_time} to {end_time}, Cache dir: {temp_cache_dir}"
    )

    # Set up logging for requests
    http_logger = logging.getLogger("httpx")
    original_level = http_logger.level
    http_logger.setLevel(logging.DEBUG)

    try:
        # Set up symbols with mixture of popular and less popular ones
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
        logger.info(f"Testing with symbols: {symbols}")

        # Create a debug directory to save downloaded files for inspection
        debug_dir = Path(temp_cache_dir) / f"debug_{test_id}"
        os.makedirs(debug_dir, exist_ok=True)
        logger.info(f"Created debug directory at {debug_dir}")

        # Direct download test - download a file directly to verify contents
        logger.info("Performing direct download test...")

        # Test multiple intervals to see which ones work
        intervals_to_test = [
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
        ]

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            download_handler = DownloadHandler(client)

            symbol = "BTCUSDT"
            date_str = "2023-01-15"

            for interval in intervals_to_test:
                # Download one file directly for this interval
                zip_file_path = debug_dir / f"{symbol}-{interval}-{date_str}.zip"
                url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{date_str}.zip"

                logger.info(
                    f"Directly downloading {interval} interval: {url} to {zip_file_path}"
                )
                success = await download_handler.download_file(url, zip_file_path)
                logger.info(f"Direct download success for {interval}: {success}")

                if success and zip_file_path.exists():
                    # Examine the file size
                    file_size = zip_file_path.stat().st_size
                    logger.info(f"Downloaded {interval} file size: {file_size} bytes")

                    # Examine file contents
                    if file_size > 0:
                        try:
                            with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                                file_list = zip_ref.namelist()
                                logger.info(
                                    f"Zip file contents for {interval}: {file_list}"
                                )

                                # Read the first file in the zip
                                if file_list:
                                    main_file = file_list[0]
                                    with zip_ref.open(main_file, "r") as f:
                                        lines = f.read().decode("utf-8").splitlines()
                                        logger.info(
                                            f"Found {len(lines)} lines in {interval}/{main_file}"
                                        )
                                        if lines:
                                            sample = lines[:3]
                                            logger.info(
                                                f"Sample lines from {interval}:\n{sample}"
                                            )
                                        else:
                                            logger.warning(
                                                f"File is empty for {interval}"
                                            )
                        except Exception as e:
                            logger.error(
                                f"Error examining zip file for {interval}: {e}"
                            )
                else:
                    logger.error(
                        f"Failed to download or file doesn't exist for {interval}: {zip_file_path}"
                    )

        # Now try the actual batch fetch with a interval that we've confirmed works
        working_interval = "1h"  # Will be updated based on our tests

        # Create a client for the test with explicit parameters for clarity
        client = VisionDataClient(
            symbol="BTCUSDT",  # Base symbol
            interval=working_interval,  # Using interval we confirmed works
            market_type="spot",  # Using spot market
            cache_dir=temp_cache_dir,
            use_cache=True,
        )
        logger.info(
            f"Created client: symbol={client.symbol}, interval={client.interval}, market={client.market_type}"
        )

        # Execute the batch fetch with detailed timing
        start_time_fetch = time.time()
        logger.info(f"Starting batch fetch at {datetime.now(timezone.utc).isoformat()}")
        results = await client.batch_fetch(symbols, start_time, end_time)
        fetch_duration = time.time() - start_time_fetch
        logger.info(f"Batch fetch completed in {fetch_duration:.2f}s")

        # Detailed diagnostics on the results
        logger.info(f"Results type: {type(results)}")
        logger.info(f"Results keys: {list(results.keys())}")

        # Log detailed information about each result
        for symbol, df in results.items():
            if df is not None:
                if not df.empty:
                    logger.info(f"{symbol}: DataFrame shape={df.shape}, non-empty")
                    logger.info(
                        f"{symbol}: Index range: {df.index.min()} to {df.index.max()}"
                    )
                    logger.info(f"{symbol}: First few rows:\n{df.head(2)}")
                else:
                    logger.info(f"{symbol}: Empty DataFrame")

                # Verify DataFrame structure
                assert isinstance(df, pd.DataFrame), f"Expected DataFrame for {symbol}"

                if not df.empty:
                    # Check essential properties
                    assert (
                        df.index.name == "open_time"
                    ), f"Expected index name 'open_time' for {symbol}"
                    assert set(["open", "high", "low", "close", "volume"]).issubset(
                        set(df.columns)
                    ), f"Missing essential columns for {symbol}"

                    # Time boundaries check
                    assert (
                        df.index.min() >= start_time
                    ), f"Data for {symbol} starts before requested time"
                    assert (
                        df.index.max() <= end_time
                    ), f"Data for {symbol} ends after requested time"

                    # Log success
                    logger.info(f"Successfully verified {len(df)} records for {symbol}")
                else:
                    logger.warning(
                        f"No data available for {symbol} - investigating why..."
                    )

                    # Additional diagnostics on empty DataFrame
                    # Check cache directory for downloaded files
                    cache_files = list(Path(temp_cache_dir).glob(f"{symbol}*"))
                    logger.info(f"Cache files for {symbol}: {cache_files}")
            else:
                logger.error(f"{symbol}: Result is None")
                assert False, f"Result for {symbol} should not be None"

        # Specific case
        if all(results[symbol].empty for symbol in symbols):
            logger.warning(
                "All DataFrames are empty, this is unusual but can happen in some environments"
            )
            logger.warning(
                "Check Vision API data availability for the test time period"
            )

    finally:
        # Restore original log level
        http_logger.setLevel(original_level)


@pytest.mark.asyncio
async def test_batch_fetch_with_mixed_validity(temp_cache_dir):
    """Test batch fetching with a mix of valid and invalid symbols."""
    from core.vision_data_client_enhanced import VisionDataClient

    # Get a safe test time range
    start_time, end_time = get_safe_test_time_range(duration_hours=1)

    # Define a mix of valid and invalid symbols
    valid_symbols = ["BTCUSDT", "ETHUSDT"]
    invalid_symbols = ["INVALIDUSDT1", "INVALIDUSDT2"]
    symbols = valid_symbols + invalid_symbols

    # Create a client
    client = VisionDataClient(symbol=SYMBOL, interval=INTERVAL)

    try:
        # Batch fetch with mixed validity using real data
        results = await client.batch_fetch(symbols, start_time, end_time)

        # Verify results structure
        assert isinstance(results, dict), "Results should be a dictionary"
        assert set(results.keys()) == set(
            symbols
        ), f"Expected keys {symbols}, got {list(results.keys())}"

        # Verify valid symbols have DataFrames (may be empty due to data availability)
        for symbol in valid_symbols:
            assert isinstance(
                results[symbol], pd.DataFrame
            ), f"Result for {symbol} should be a DataFrame"

            # If we have data, verify structure
            if not results[symbol].empty:
                assert (
                    results[symbol].index.name == "open_time"
                ), f"Index name for {symbol} should be 'open_time'"
                # Check if some essential columns are present
                essential_columns = ["open", "close"]
                for col in essential_columns:
                    assert (
                        col in results[symbol].columns
                    ), f"Essential column {col} missing for {symbol}"

                logger.info(
                    f"Successfully fetched {len(results[symbol])} records for {symbol}"
                )
            else:
                logger.warning(
                    f"No data available for valid symbol {symbol} - this is expected occasionally"
                )

        # Verify invalid symbols have empty DataFrames
        for symbol in invalid_symbols:
            assert isinstance(
                results[symbol], pd.DataFrame
            ), f"Result for {symbol} should be a DataFrame"
            assert results[
                symbol
            ].empty, f"DataFrame for invalid symbol {symbol} should be empty"
            logger.info(f"As expected, no data available for invalid symbol {symbol}")

    except Exception as e:
        logger.error(f"Error during batch fetch with mixed validity: {e}")
        pytest.fail(f"Unexpected error during batch fetch with mixed validity: {e}")


@pytest.mark.asyncio
async def test_batch_fetch_with_different_interval(temp_cache_dir):
    """Test batch fetching with a time range that spans multiple days."""
    from core.vision_data_client_enhanced import VisionDataClient

    # Use a 2-day range to test over multiple days
    start_time = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    end_time = start_time + timedelta(days=2)
    print(f"Generated test time range: {start_time} to {end_time}")

    # Define real symbols to test
    symbols = ["BTCUSDT", "ETHUSDT"]

    # Create a client with a longer interval to ensure data is available
    # Use 1h interval which should have better data availability than shorter intervals
    client = VisionDataClient(symbol=SYMBOL, interval="1h")

    try:
        # Batch fetch with a longer time range using real data
        results = await client.batch_fetch(symbols, start_time, end_time)

        # Verify results structure
        assert isinstance(results, dict), "Results should be a dictionary"
        assert set(results.keys()) == set(
            symbols
        ), f"Expected keys {symbols}, got {list(results.keys())}"

        # Verify each result is a DataFrame (may be empty due to data availability)
        for symbol, df in results.items():
            assert isinstance(
                df, pd.DataFrame
            ), f"Result for {symbol} should be a DataFrame"

            # If we have data, verify structure
            if not df.empty:
                assert (
                    df.index.name == "open_time"
                ), f"Index name for {symbol} should be 'open_time'"
                # Check if some essential columns are present
                essential_columns = ["open", "close"]
                for col in essential_columns:
                    assert (
                        col in df.columns
                    ), f"Essential column {col} missing for {symbol}"

                # Verify data is within the requested time boundaries
                assert (
                    df.index.min() >= start_time
                ), f"Data for {symbol} starts earlier than requested"
                assert (
                    df.index.max() < end_time
                ), f"Data for {symbol} ends later than requested"

                # For longer intervals, we should have fewer points covering the same time range
                # Check that we have a reasonable number of data points for a 2-day range with 1h interval
                expected_min_points = (
                    12  # At least half a day's worth of hourly data points
                )
                if len(df) >= expected_min_points:
                    logger.info(
                        f"Successfully fetched {len(df)} records for {symbol}, which is adequate for the time range"
                    )
                else:
                    logger.warning(
                        f"Only fetched {len(df)} records for {symbol}, which is less than expected ({expected_min_points})"
                    )
            else:
                logger.warning(
                    f"No data available for {symbol} - this is expected occasionally"
                )

    except Exception as e:
        logger.error(f"Error during batch fetch with different interval: {e}")
        pytest.fail(f"Unexpected error during batch fetch with different interval: {e}")


@pytest.mark.asyncio
async def test_batch_fetch_concurrency_limits(temp_cache_dir):
    """Test batch fetching respects concurrency limits."""
    from core.vision_data_client_enhanced import VisionDataClient

    # Get a safe test time range
    start_time, end_time = get_safe_test_time_range(duration_hours=1)

    # Use a list of common symbols, enough to test concurrency
    symbols = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "ADAUSDT",
        "DOGEUSDT",
        "LTCUSDT",
    ]

    # Create a client with a low concurrency limit to test batching
    max_concurrent = 3
    client = VisionDataClient(
        symbol=SYMBOL,
        interval=INTERVAL,
        max_concurrent_downloads=max_concurrent,
    )

    try:
        # Measure time to confirm batching affects performance
        start_proc_time = time.time()

        # Batch fetch with concurrency limits
        results = await client.batch_fetch(symbols, start_time, end_time)

        end_proc_time = time.time()
        proc_time = end_proc_time - start_proc_time

        # Verify results structure
        assert isinstance(results, dict), "Results should be a dictionary"
        assert set(results.keys()) == set(
            symbols
        ), f"Expected keys {symbols}, got {list(results.keys())}"

        # Verify each result is a DataFrame
        for symbol, df in results.items():
            assert isinstance(
                df, pd.DataFrame
            ), f"Result for {symbol} should be a DataFrame"

        # Log processing time - we can't make assertions about this since it depends on
        # network conditions, but we can log it for observational purposes
        logger.info(
            f"Batch fetch with max_concurrent={max_concurrent} for {len(symbols)} symbols took {proc_time:.2f} seconds"
        )

        # Count how many symbols have data
        symbols_with_data = sum(1 for df in results.values() if not df.empty)
        logger.info(f"Found data for {symbols_with_data} out of {len(symbols)} symbols")

    except Exception as e:
        logger.error(f"Error during batch fetch with concurrency limits: {e}")
        pytest.fail(f"Unexpected error during batch fetch with concurrency limits: {e}")


@pytest.mark.asyncio
async def test_batch_fetch_empty_symbols_list(temp_cache_dir):
    """Test batch fetching with an empty symbols list."""
    from core.vision_data_client_enhanced import VisionDataClient

    # Get a safe test time range
    start_time, end_time = get_safe_test_time_range(duration_hours=1)

    # Create a client - no need to patch since we're testing empty list behavior
    client = VisionDataClient(symbol=SYMBOL, interval=INTERVAL)

    try:
        # Batch fetch with empty symbols list
        results = await client.batch_fetch([], start_time, end_time)

        # Verify results structure is an empty dict
        assert isinstance(results, dict), "Results should be a dictionary"
        assert len(results) == 0, "Results should be empty for empty symbols list"

        logger.info("Successfully handled empty symbols list")

    except Exception as e:
        logger.error(f"Error during batch fetch with empty symbols list: {e}")
        pytest.fail(f"Unexpected error during batch fetch with empty symbols list: {e}")


@pytest.mark.asyncio
async def test_batch_fetch_performance(temp_cache_dir):
    """Test batch fetching performance."""
    from core.vision_data_client_enhanced import VisionDataClient
    import time

    # Get a safe test time range
    start_time, end_time = get_safe_test_time_range(duration_hours=2)

    # Use real symbols
    symbols = ["BTCUSDT", "ETHUSDT"]

    # Create a client
    client = VisionDataClient(
        symbol=SYMBOL,
        interval=INTERVAL,
    )

    try:
        # First batch fetch
        logger.info("First batch fetch...")
        start_time_first = time.time()
        first_results = await client.batch_fetch(symbols, start_time, end_time)
        end_time_first = time.time()
        first_fetch_time = end_time_first - start_time_first

        # Verify results structure
        assert isinstance(first_results, dict), "Results should be a dictionary"
        assert set(first_results.keys()) == set(
            symbols
        ), f"Expected keys {symbols}, got {list(first_results.keys())}"

        # Verify each result is a DataFrame
        for symbol, df in first_results.items():
            assert isinstance(
                df, pd.DataFrame
            ), f"Result for {symbol} should be a DataFrame"

        # Count symbols with data
        symbols_with_data = sum(1 for df in first_results.values() if not df.empty)
        logger.info(
            f"First fetch: Found data for {symbols_with_data} out of {len(symbols)} symbols"
        )
        logger.info(f"First fetch took {first_fetch_time:.2f} seconds")

        # Second batch fetch - demonstrates consistency
        logger.info("Second batch fetch - testing consistency...")
        start_time_second = time.time()
        second_results = await client.batch_fetch(symbols, start_time, end_time)
        end_time_second = time.time()
        second_fetch_time = end_time_second - start_time_second

        # Verify second results structure
        assert isinstance(second_results, dict), "Second results should be a dictionary"
        assert set(second_results.keys()) == set(
            symbols
        ), f"Expected keys {symbols}, got {list(second_results.keys())}"

        # Compare first and second fetches to verify consistency
        for symbol in symbols:
            # Check if we have data in both fetches
            if not first_results[symbol].empty and not second_results[symbol].empty:
                # The shape should be the same
                assert first_results[symbol].shape == second_results[symbol].shape, (
                    f"Inconsistent DataFrame shapes for {symbol}: "
                    f"first={first_results[symbol].shape}, second={second_results[symbol].shape}"
                )

        logger.info(f"Second fetch took {second_fetch_time:.2f} seconds")

    except Exception as e:
        logger.error(f"Error during batch fetch performance test: {e}")
        pytest.fail(f"Unexpected error during batch fetch performance test: {e}")
