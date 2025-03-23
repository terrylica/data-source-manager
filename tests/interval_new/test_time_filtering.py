#!/usr/bin/env python
"""Test the time filtering implementation."""

import pytest
import pandas as pd
import time
import asyncio
import logging
import os
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.vision_data_client_enhanced import VisionDataClient
from utils.time_alignment import TimeRangeManager, filter_time_range
from utils.download_handler import VisionDownloadManager, DownloadHandler
from utils.market_constraints import MarketType, Interval

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Fixture for a temporary cache directory
@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache."""
    import tempfile

    temp_dir = tempfile.mkdtemp()
    yield temp_dir

    # Clean up
    try:
        import shutil

        shutil.rmtree(temp_dir)
    except Exception as e:
        logger.error(f"Error cleaning up temp directory: {e}")


@pytest.mark.asyncio
async def test_direct_filtering(temp_cache_dir):
    """Test filtering directly with known data."""
    # Create a date range that we know works from our previous test
    start_date = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2023, 1, 15, 1, 0, 0, tzinfo=timezone.utc)

    logger.info(f"Start date: {start_date.isoformat()}, timezone: {start_date.tzinfo}")
    logger.info(f"End date: {end_date.isoformat()}, timezone: {end_date.tzinfo}")

    # Create a debug directory
    debug_dir = Path(temp_cache_dir) / f"debug_filter_{int(time.time())}"
    os.makedirs(debug_dir, exist_ok=True)
    logger.info(f"Created debug directory at {debug_dir}")

    # Directly download the 1h file for BTCUSDT for 2023-01-15
    symbol = "BTCUSDT"
    date_str = "2023-01-15"
    interval = "1h"

    # Download the file using httpx
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            download_handler = DownloadHandler(client)

            # Download one file directly
            zip_file_path = debug_dir / f"{symbol}-{interval}-{date_str}.zip"
            url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{date_str}.zip"

            logger.info(f"Directly downloading {url} to {zip_file_path}")
            success = await download_handler.download_file(url, zip_file_path)
            logger.info(f"Direct download success: {success}")

            if success and zip_file_path.exists():
                # Read the data directly ourselves
                import zipfile

                with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                    file_list = zip_ref.namelist()
                    logger.info(f"Zip file contents: {file_list}")

                    if file_list:
                        main_file = file_list[0]
                        csv_file_path = debug_dir / main_file

                        # Extract the file
                        zip_ref.extract(main_file, debug_dir)

                        # Read the CSV directly
                        df = pd.read_csv(
                            csv_file_path,
                            names=[
                                "open_time",
                                "open",
                                "high",
                                "low",
                                "close",
                                "volume",
                                "close_time",
                                "quote_volume",
                                "trades",
                                "taker_buy_volume",
                                "taker_buy_quote_volume",
                                "ignored",
                            ],
                        )

                        # Log the raw timestamps
                        logger.info(f"Raw open_time values (first 3 rows):")
                        for i in range(min(3, len(df))):
                            logger.info(f"Row {i}: {df['open_time'].iloc[i]}")

                        # Convert timestamps to datetime
                        from core.vision_constraints import detect_timestamp_unit

                        sample_ts = df["open_time"].iloc[0]
                        ts_unit = detect_timestamp_unit(sample_ts)
                        logger.info(
                            f"Detected timestamp unit: {ts_unit} for sample value: {sample_ts}"
                        )

                        # Convert timestamps with proper timezone
                        df["open_time"] = pd.to_datetime(
                            df["open_time"], unit=ts_unit
                        ).dt.tz_localize("UTC")
                        logger.info(
                            f"Converted open_time, first value: {df['open_time'].iloc[0]}"
                        )
                        logger.info(
                            f"Timezone of converted timestamps: {df['open_time'].dt.tz}"
                        )

                        # Set index and analyze data
                        df.set_index("open_time", inplace=True)

                        # Print index range and data shape
                        logger.info(
                            f"Original data range: {df.index.min()} to {df.index.max()}"
                        )
                        logger.info(f"Original data shape: {df.shape}")
                        logger.info(f"Original data index timezone: {df.index.tz}")

                        # Test filtering
                        filtered_df = filter_time_range(df, start_date, end_date)

                        # Analyze filtered data
                        if filtered_df.empty:
                            logger.warning(f"Filtered data is empty!")
                            logger.warning(
                                f"Filter parameters: {start_date} to {end_date}"
                            )

                            # Test direct comparison for debugging
                            logger.info(
                                f"Start date: {start_date}, index min: {df.index.min()}"
                            )
                            logger.info(
                                f"Start date <= index min: {start_date <= df.index.min()}"
                            )
                            logger.info(
                                f"End date: {end_date}, index max: {df.index.max()}"
                            )
                            logger.info(
                                f"End date > index min: {end_date > df.index.min()}"
                            )

                            # Check timezone issues
                            logger.info(f"Start date timezone: {start_date.tzinfo}")
                            logger.info(f"Index timezone: {df.index.tz}")

                            # Try a more permissive filter
                            one_day_before = start_date - timedelta(days=1)
                            one_day_after = end_date + timedelta(days=1)
                            broad_filtered_df = filter_time_range(
                                df, one_day_before, one_day_after
                            )
                            logger.info(
                                f"Broader filter range: {one_day_before} to {one_day_after}"
                            )
                            logger.info(
                                f"Broader filtered data is empty: {broad_filtered_df.empty}"
                            )
                            if not broad_filtered_df.empty:
                                logger.info(
                                    f"Broader filter shape: {broad_filtered_df.shape}"
                                )
                                logger.info(
                                    f"Broader filter range: {broad_filtered_df.index.min()} to {broad_filtered_df.index.max()}"
                                )
                        else:
                            logger.info(
                                f"Filtered data range: {filtered_df.index.min()} to {filtered_df.index.max()}"
                            )
                            logger.info(f"Filtered data shape: {filtered_df.shape}")

                        # Try the TimeRangeManager approach used by the client
                        manager_filtered_df = TimeRangeManager.filter_dataframe(
                            df, start_date, end_date
                        )
                        logger.info(
                            f"Manager filtered data is empty: {manager_filtered_df.empty}"
                        )
                        if not manager_filtered_df.empty:
                            logger.info(
                                f"Manager filtered shape: {manager_filtered_df.shape}"
                            )
                            logger.info(
                                f"Manager filtered range: {manager_filtered_df.index.min()} to {manager_filtered_df.index.max()}"
                            )

                        # Look at client internal filtering code directly
                        # Create a client
                        client = VisionDataClient(
                            symbol=symbol,
                            interval=interval,
                            market_type="spot",
                            cache_dir=temp_cache_dir,
                            use_cache=False,
                        )

                        # Test the client's download_and_cache method
                        result = await client._download_and_cache(start_date, end_date)
                        logger.info(f"Client result is empty: {result.empty}")
                        if not result.empty:
                            logger.info(f"Client result shape: {result.shape}")
                            logger.info(
                                f"Client result range: {result.index.min()} to {result.index.max()}"
                            )
                        else:
                            logger.warning(
                                "Client result is empty - something is wrong with filtering!"
                            )
    except Exception as e:
        logger.error(f"Error in direct filtering test: {str(e)}")


@pytest.mark.asyncio
async def test_1h_time_boundary_issue():
    """Test specific issues with 1h data and time boundaries."""
    # Create dates for the test - 1 hour range on January 15, 2023
    start_date = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2023, 1, 15, 1, 0, 0, tzinfo=timezone.utc)

    # Create test data to simulate the 1h data
    # From our manual test, we know the original data looks like:
    # '1673740800000,20952.76000000,21001.84000000,20623.21000000,20767.05000000,14735.14851000,1673744399999,306555040.00370580,385102,7087.26178000,147452754.40220560,0'
    # Which is:
    # - open_time: 1673740800000 (2023-01-15 00:00:00 UTC)
    # - close_time: 1673744399999 (2023-01-15 00:59:59.999 UTC)

    # Create a DataFrame with 24 hours of 1h data for January 15, 2023
    data = []
    for hour in range(24):
        open_time = datetime(2023, 1, 15, hour, 0, 0, tzinfo=timezone.utc)
        open_ts = int(open_time.timestamp() * 1000)  # Convert to milliseconds
        close_time = open_time + timedelta(hours=1) - timedelta(milliseconds=1)
        close_ts = int(close_time.timestamp() * 1000)  # Convert to milliseconds

        # Create a row with all the required columns
        row = [
            open_ts,  # open_time
            20000.0 + hour,  # open
            21000.0 + hour,  # high
            19000.0 + hour,  # low
            20500.0 + hour,  # close
            1000.0 + hour,  # volume
            close_ts,  # close_time
            20000000.0 + hour,  # quote_volume
            1000 + hour,  # trades
            500.0 + hour,  # taker_buy_volume
            10000000.0 + hour,  # taker_buy_quote_volume
            0,  # ignored
        ]
        data.append(row)

    # Create DataFrame
    df = pd.DataFrame(
        data,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "taker_buy_volume",
            "taker_buy_quote_volume",
            "ignored",
        ],
    )

    # Convert timestamps with proper timezone
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms").dt.tz_localize("UTC")
    df.set_index("open_time", inplace=True)

    # Check the data
    logger.info(f"Test data range: {df.index.min()} to {df.index.max()}")
    logger.info(f"Test data shape: {df.shape}")
    logger.info(f"Test data timezone: {df.index.tz}")

    # Test filtering with our time range
    filtered_df = filter_time_range(df, start_date, end_date)

    # Analyze results
    logger.info(f"Filtered data is empty: {filtered_df.empty}")
    if not filtered_df.empty:
        logger.info(f"Filtered data shape: {filtered_df.shape}")
        logger.info(
            f"Filtered data range: {filtered_df.index.min()} to {filtered_df.index.max()}"
        )
    else:
        logger.warning("Filtered data is empty - investigating why")
        # Test specific comparisons
        first_index = df.index[0]
        logger.info(
            f"First index: {first_index} >= start date {start_date}: {first_index >= start_date}"
        )
        logger.info(
            f"First index: {first_index} < end date {end_date}: {first_index < end_date}"
        )

        # Test with exact timestamps from data
        exact_start = df.index[0]
        exact_end = df.index[1]  # Second hour
        exact_filtered = filter_time_range(df, exact_start, exact_end)
        logger.info(f"Exact filtered is empty: {exact_filtered.empty}")
        if not exact_filtered.empty:
            logger.info(f"Exact filtered shape: {exact_filtered.shape}")

    # Test with boundary edge cases
    logger.info("\nTesting boundary edge cases:")
    # What if we go to 1:00:00 exactly?
    inclusive_end = datetime(2023, 1, 15, 1, 0, 0, tzinfo=timezone.utc)
    inclusive_filtered = df[(df.index >= start_date) & (df.index <= inclusive_end)]
    logger.info(f"Inclusive end (<=1:00) filter shape: {inclusive_filtered.shape}")

    # What if we reduce end by 1 microsecond?
    almost_end = datetime(2023, 1, 15, 1, 0, 0, tzinfo=timezone.utc) - timedelta(
        microseconds=1
    )
    almost_filtered = df[(df.index >= start_date) & (df.index <= almost_end)]
    logger.info(f"Almost end (<=0:59:59.999999) filter shape: {almost_filtered.shape}")

    # Use the actual TimeRangeManager implementation
    manager_filtered = TimeRangeManager.filter_dataframe(df, start_date, end_date)
    logger.info(f"TimeRangeManager filter shape: {manager_filtered.shape}")

    # Call the low-level filter function directly
    direct_filtered = filter_time_range(df, start_date, end_date)
    logger.info(f"Direct filter_time_range shape: {direct_filtered.shape}")


@pytest.mark.asyncio
async def test_vision_manager_download():
    """Test the VisionDownloadManager directly."""
    # Set up parameters
    test_date = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    symbol = "BTCUSDT"
    interval = "1h"
    market_type = "spot"

    logger.info(f"Testing VisionDownloadManager with date: {test_date.isoformat()}")

    # Create a client and download manager
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        download_manager = VisionDownloadManager(
            client=client,
            symbol=symbol,
            interval=interval,
            market_type=market_type,
        )

        # Download data for the test date
        logger.info(f"Downloading data for date: {test_date.strftime('%Y-%m-%d')}")
        df = await download_manager.download_date(test_date)

        if df is None:
            logger.error("Download failed - returned None")
        elif df.empty:
            logger.warning("Downloaded DataFrame is empty")
        else:
            # Analyze the data
            logger.info(f"Downloaded data shape: {df.shape}")
            logger.info(f"Downloaded data range: {df.index.min()} to {df.index.max()}")
            logger.info(f"Downloaded data timezone: {df.index.tz}")
            logger.info(f"First few rows:\n{df.head(2)}")

            # Test filtering the data
            start_time = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
            end_time = datetime(2023, 1, 15, 1, 0, 0, tzinfo=timezone.utc)

            # Filter with TimeRangeManager
            filtered_df = TimeRangeManager.filter_dataframe(df, start_time, end_time)
            logger.info(f"Filtered data shape: {filtered_df.shape}")
            if not filtered_df.empty:
                logger.info(
                    f"Filtered data range: {filtered_df.index.min()} to {filtered_df.index.max()}"
                )
            else:
                logger.warning("Filtered data is empty!")


@pytest.mark.asyncio
async def test_vision_client_direct(temp_cache_dir):
    """Test the VisionDataClient directly with the problematic time range."""
    # Set up parameters
    start_time = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2023, 1, 15, 1, 0, 0, tzinfo=timezone.utc)

    logger.info(
        f"Testing VisionDataClient with time range: {start_time.isoformat()} to {end_time.isoformat()}"
    )

    # Create the client
    client = VisionDataClient(
        symbol="BTCUSDT",
        interval="1h",
        market_type="spot",
        cache_dir=temp_cache_dir,
        use_cache=True,
    )

    # Test the download_and_cache method directly
    logger.info("Calling _download_and_cache method directly...")
    result = await client._download_and_cache(start_time, end_time)

    logger.info(f"Result is empty: {result.empty}")
    if not result.empty:
        logger.info(f"Result shape: {result.shape}")
        logger.info(f"Result range: {result.index.min()} to {result.index.max()}")
    else:
        logger.warning("Result is empty - investigating why...")

    # Test the fetch method
    logger.info("\nCalling fetch method...")
    fetch_result = await client.fetch(start_time, end_time)

    logger.info(f"Fetch result is empty: {fetch_result.empty}")
    if not fetch_result.empty:
        logger.info(f"Fetch result shape: {fetch_result.shape}")
        logger.info(
            f"Fetch result range: {fetch_result.index.min()} to {fetch_result.index.max()}"
        )
    else:
        logger.warning(
            "Fetch result is empty - something is wrong with the fetch pipeline!"
        )

    # Add more detailed logging around the filtering part
    logger.info("\nDiagnosing the issue - download date directly...")

    # Get the direct date dataframe
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http_client:
        download_manager = VisionDownloadManager(
            client=http_client,
            symbol="BTCUSDT",
            interval="1h",
            market_type="spot",
        )
        df = await download_manager.download_date(
            start_time.replace(hour=0, minute=0, second=0, microsecond=0)
        )

        if df is not None:
            logger.info(f"Downloaded day data shape: {df.shape}")

            # Get current dates list from _download_and_cache method implementation
            current_date = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
            dates = []
            while current_date < end_time:
                dates.append(current_date)
                current_date += timedelta(days=1)

            logger.info(
                f"Dates list that would be used: {[d.strftime('%Y-%m-%d') for d in dates]}"
            )

            # The key step - apply the time filtering to the dataframe
            filtered_df = TimeRangeManager.filter_dataframe(df, start_time, end_time)

            logger.info(
                f"DIRECT FILTERING RESULT - filtered_df shape: {filtered_df.shape}"
            )
            if not filtered_df.empty:
                logger.info(
                    f"DIRECT FILTERING - data range: {filtered_df.index.min()} to {filtered_df.index.max()}"
                )
            else:
                logger.error("DIRECT FILTERING - filtered data is empty!")

                # Check raw indexes
                logger.info(f"Raw df index values: {df.index.tolist()}")

                # Check indices timezone matching
                logger.info(
                    f"df.index.tz: {df.index.tz}, start_time.tzinfo: {start_time.tzinfo}"
                )

                # Check direct comparison of timestamp values
                first_idx = df.index[0]
                logger.info(
                    f"First index: {first_idx}, first_idx >= start_time: {first_idx >= start_time}"
                )
                logger.info(
                    f"First index: {first_idx}, first_idx < end_time: {first_idx < end_time}"
                )

                # Check types
                logger.info(
                    f"Types - df.index[0]: {type(df.index[0])}, start_time: {type(start_time)}"
                )

                # Try manual filtering on the raw df
                manual_filtered = df[(df.index >= start_time) & (df.index < end_time)]
                logger.info(f"Manual filtering result shape: {manual_filtered.shape}")
        else:
            logger.error("Could not download data for direct testing")


@pytest.mark.asyncio
async def test_vision_client_with_validation_disabled(temp_cache_dir):
    """Test the VisionDataClient with validation disabled."""
    # Set up parameters
    start_time = datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2023, 1, 15, 1, 0, 0, tzinfo=timezone.utc)

    logger.info(
        f"Testing VisionDataClient with validation disabled: {start_time.isoformat()} to {end_time.isoformat()}"
    )

    # Create the client
    client = VisionDataClient(
        symbol="BTCUSDT",
        interval="1h",
        market_type="spot",
        cache_dir=temp_cache_dir,
        use_cache=True,
    )

    # Override the fetch method to disable validation
    original_fetch = client.fetch

    async def fetch_without_validation(start_time, end_time, columns=None):
        """Modified fetch method without boundary validation."""
        # Validate and normalize time range using centralized utility
        TimeRangeManager.validate_time_window(start_time, end_time)

        # Get time boundaries using the centralized manager
        time_boundaries = TimeRangeManager.get_time_boundaries(
            start_time, end_time, client.interval_obj
        )
        start_time = time_boundaries["adjusted_start"]
        end_time = time_boundaries["adjusted_end"]

        logger.info(
            f"Fetching WITHOUT VALIDATION {client.symbol} {client.interval} data: "
            f"{start_time.isoformat()} -> {end_time.isoformat()} (exclusive end)"
        )

        # Direct fetch without validation
        try:
            df = await client._download_and_cache(start_time, end_time, columns=columns)
            if not df.empty:
                # Skip validation
                logger.info(f"Successfully fetched {len(df)} records")
                return df

            logger.warning(f"No data available for {start_time} to {end_time}")
            return client._create_empty_dataframe()
        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")
            return client._create_empty_dataframe()

    # Replace the fetch method
    client.fetch = fetch_without_validation

    # Try fetching with disabled validation
    logger.info("Calling modified fetch method without validation...")
    fetch_result = await client.fetch(start_time, end_time)

    logger.info(f"Modified fetch result is empty: {fetch_result.empty}")
    if not fetch_result.empty:
        logger.info(f"Modified fetch result shape: {fetch_result.shape}")
        logger.info(
            f"Modified fetch result range: {fetch_result.index.min()} to {fetch_result.index.max()}"
        )
    else:
        logger.warning("Modified fetch result is empty - there might be other issues!")

    # Restore the original fetch method
    client.fetch = original_fetch


if __name__ == "__main__":
    import httpx

    asyncio.run(test_direct_filtering(temp_cache_dir()))
    asyncio.run(test_1h_time_boundary_issue())
    asyncio.run(test_vision_manager_download())
