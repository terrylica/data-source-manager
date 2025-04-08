#!/usr/bin/env python
"""
Comprehensive verification script for timeout handling in the DataSourceManager.

This script verifies that data retrieval works properly with the timeout fixes
implemented in the DataSourceManager by testing multiple scenarios:

1. Sequential data retrieval - Fetches data for multiple symbols one after another
2. Concurrent data retrieval - Runs multiple data fetches simultaneously
3. Extended historical data - Tests retrieving larger historical datasets
4. Recent hourly data - Tests retrieving recent data that may not be fully consolidated
5. Recent minute data - Tests retrieving very recent minute data
6. Partial data retrieval - Tests data spanning from available past data to recent data

The script captures warnings, analyzes data completeness, and verifies no timeout errors
occur when using the fixed DataSourceManager implementation.

This file consolidates the key testing functionality from several previous test scripts
into a single comprehensive verification suite.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.data_source_manager import DataSourceManager, DataSource
from utils.market_constraints import MarketType, Interval
from utils.logger_setup import logger

# Set up logging for the verification script
logger.setup_root(level="ERROR", show_filename=True)
logger.info("Logger configured for data retrieval verification")


async def verify_sequential_data_retrieval():
    """Verify sequential data retrieval for multiple symbols."""
    logger.info("===== VERIFYING SEQUENTIAL DATA RETRIEVAL =====")

    # Create manager
    manager = DataSourceManager(market_type=MarketType.SPOT, use_cache=False)

    # Define symbols and time range
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=5)

    logger.info(f"Time range for verification: {start_time} to {end_time}")

    # Fetch data for each symbol sequentially
    for symbol in symbols:
        try:
            start_op = time.time()

            logger.info(f"Retrieving data for {symbol}...")
            df = await manager.get_data(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                interval=Interval.MINUTE_1,
                enforce_source=DataSource.REST,
            )

            elapsed = time.time() - start_op

            if df.empty:
                logger.warning(f"No data retrieved for {symbol}")
                continue

            logger.info(
                f"Successfully retrieved {len(df)} records for {symbol} in {elapsed:.2f}s"
            )

            # Log a sample of the data
            if not df.empty:
                logger.info(f"{symbol} data sample: {df.iloc[0:2].to_dict('records')}")

        except Exception as e:
            logger.error(f"Error retrieving data for {symbol}: {str(e)}")

    # Clean up resources
    await manager.__aexit__(None, None, None)


async def verify_concurrent_data_retrieval():
    """Verify concurrent data retrieval for multiple symbols."""
    logger.info("===== VERIFYING CONCURRENT DATA RETRIEVAL =====")

    # Create manager
    manager = DataSourceManager(market_type=MarketType.SPOT, use_cache=False)

    # Define symbols and time range
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)

    logger.info(f"Time range for verification: {start_time} to {end_time}")

    # Create tasks for concurrent data retrieval
    tasks = []

    # Add multiple tasks for each symbol to increase concurrency
    for symbol in symbols:
        # Create two tasks for each symbol
        for _ in range(2):
            tasks.append(
                asyncio.create_task(
                    fetch_data_for_verification(
                        manager, symbol, start_time, end_time, Interval.MINUTE_1
                    )
                )
            )

    # Run tasks concurrently
    start_op = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start_op

    # Analyze results
    total_operations = len(results)
    success_count = sum(1 for r in results if isinstance(r, tuple) and r[0] > 0)
    empty_count = sum(1 for r in results if isinstance(r, tuple) and r[0] == 0)
    error_count = sum(1 for r in results if isinstance(r, Exception))

    logger.info(f"Concurrent operations completed in {elapsed:.2f}s")
    logger.info(f"Total operations: {total_operations}")
    logger.info(f"Successful operations: {success_count}")
    logger.info(f"Empty results: {empty_count}")
    logger.info(f"Error count: {error_count}")

    # Check for timeout errors
    timeout_errors = sum(
        1 for r in results if isinstance(r, Exception) and "timeout" in str(r).lower()
    )
    if timeout_errors > 0:
        logger.warning(f"Found {timeout_errors} timeout errors")
    else:
        logger.info("No timeout errors detected")

    # Clean up resources
    await manager.__aexit__(None, None, None)


async def verify_extended_historical_data():
    """Verify retrieval of extended historical data."""
    logger.info("===== VERIFYING EXTENDED HISTORICAL DATA RETRIEVAL =====")

    # Create manager
    manager = DataSourceManager(market_type=MarketType.SPOT, use_cache=False)

    # Define historical time range (3 days ago to now)
    end_time = datetime.now(timezone.utc)  # Use current time to test warnings
    start_time = end_time - timedelta(days=3)

    logger.info(f"Historical time range: {start_time} to {end_time}")

    try:
        start_op = time.time()

        # Retrieve extended historical data
        df = await manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            enforce_source=DataSource.REST,
        )

        elapsed = time.time() - start_op

        if df.empty:
            logger.warning("No historical data retrieved")
        else:
            logger.info(
                f"Successfully retrieved {len(df)} historical records in {elapsed:.2f}s"
            )

            # Log time range of data
            if not df.empty:
                first_time = df.index.min()
                last_time = df.index.max()
                logger.info(f"Data spans from {first_time} to {last_time}")

                # Log a sample of the data
                logger.info(
                    f"Historical data sample: {df.iloc[0:2].to_dict('records')}"
                )

    except Exception as e:
        logger.error(f"Error retrieving historical data: {str(e)}")

    # Clean up resources
    await manager.__aexit__(None, None, None)


async def verify_very_recent_hourly_data():
    """Verify retrieval of very recent hourly data that may not be fully consolidated."""
    logger.info("===== VERIFYING VERY RECENT HOURLY DATA RETRIEVAL =====")

    # Create manager
    manager = DataSourceManager(market_type=MarketType.SPOT, use_cache=False)

    # Define time range - use current time to ensure we hit consolidation warnings
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(
        hours=24
    )  # Use last 24 hours to ensure some data is returned

    logger.info(f"Recent hourly time range: {start_time} to {end_time}")

    try:
        start_op = time.time()

        # Set up storage for capturing warnings
        warnings_detected = []

        # Create a context manager to temporarily capture warnings
        original_warning_fn = logger.warning

        def capture_warning(*args, **kwargs):
            message = args[0] if args else kwargs.get("msg", "")
            if isinstance(message, str) and "may not be fully consolidated" in message:
                warnings_detected.append(message)
            # Call the original warning function to maintain logging
            return original_warning_fn(*args, **kwargs)

        # Replace the warning function temporarily
        logger.warning = capture_warning

        # Retrieve hourly data
        df = await manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            enforce_source=DataSource.REST,
        )

        # Restore original warning function
        logger.warning = original_warning_fn

        elapsed = time.time() - start_op

        logger.info(f"Recent hourly data retrieval completed in {elapsed:.2f}s")
        logger.info(f"Retrieved {len(df)} hourly records")

        if len(df) > 0:
            # Check data coverage
            data_start = df.index.min()
            data_end = df.index.max()
            logger.info(f"Data spans from {data_start} to {data_end}")

            # Calculate expected records
            total_hours = (end_time - start_time).total_seconds() / 3600
            logger.info(
                f"Expected ~{int(total_hours)} hourly records, got {len(df)} ({len(df)/total_hours*100:.1f}% complete)"
            )

        # Log any warnings that were captured
        if warnings_detected:
            logger.info(
                f"Detected {len(warnings_detected)} data consolidation warnings during hourly retrieval"
            )
            for warning in warnings_detected[:2]:  # Show first few warnings
                logger.info(f"Sample warning: {warning}")

    except Exception as e:
        logger.error(f"Error retrieving recent hourly data: {str(e)}")

    # Clean up resources
    await manager.__aexit__(None, None, None)


async def verify_very_recent_minute_data():
    """Verify retrieval of very recent minute data that may not be fully consolidated."""
    logger.info("===== VERIFYING VERY RECENT MINUTE DATA RETRIEVAL =====")

    # Create manager
    manager = DataSourceManager(market_type=MarketType.SPOT, use_cache=False)

    # Define time range - use current time to ensure we hit consolidation warnings
    current_time = datetime.now(timezone.utc)
    # Use a time that's exactly 10 seconds in the past
    end_time = current_time - timedelta(seconds=10)
    start_time = end_time - timedelta(minutes=10)  # 10 minutes before that

    logger.info(f"Current time: {current_time.isoformat()}")
    logger.info(f"Recent minute time range: {start_time} to {end_time}")
    logger.info(
        f"End time is {(current_time - end_time).total_seconds():.1f} seconds in the past"
    )

    try:
        start_op = time.time()

        # Set up storage for capturing warnings
        warnings_detected = []

        # Create a context manager to temporarily capture warnings
        original_warning_fn = logger.warning

        def capture_warning(*args, **kwargs):
            message = args[0] if args else kwargs.get("msg", "")
            if isinstance(message, str) and "may not be fully consolidated" in message:
                warnings_detected.append(message)
            # Call the original warning function to maintain logging
            return original_warning_fn(*args, **kwargs)

        # Replace the warning function temporarily
        logger.warning = capture_warning

        # Retrieve minute data
        df = await manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.MINUTE_1,
            enforce_source=DataSource.REST,
        )

        # Restore original warning function
        logger.warning = original_warning_fn

        elapsed = time.time() - start_op

        logger.info(f"Recent minute data retrieval completed in {elapsed:.2f}s")
        logger.info(f"Retrieved {len(df)} minute records")

        if len(df) > 0:
            # Check data coverage
            data_start = df.index.min()
            data_end = df.index.max()
            logger.info(f"Data spans from {data_start} to {data_end}")

            # Calculate expected records
            total_minutes = (end_time - start_time).total_seconds() / 60
            logger.info(
                f"Expected ~{int(total_minutes)} minute records, got {len(df)} ({len(df)/total_minutes*100:.1f}% complete)"
            )
        else:
            logger.warning("No minute data retrieved at all")

        # Log any warnings that were captured
        if warnings_detected:
            logger.info(
                f"Detected {len(warnings_detected)} data consolidation warnings during minute retrieval"
            )
            for warning in warnings_detected[:2]:  # Show first few warnings
                logger.info(f"Sample warning: {warning}")

    except Exception as e:
        logger.error(f"Error retrieving recent minute data: {str(e)}")

    # Clean up resources
    await manager.__aexit__(None, None, None)


async def fetch_data_for_verification(manager, symbol, start_time, end_time, interval):
    """Fetch data for verification and return success indicator."""
    try:
        logger.info(f"Starting concurrent fetch for {symbol}")

        start_op = time.time()
        df = await manager.get_data(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            interval=interval,
            enforce_source=DataSource.REST,
        )
        elapsed = time.time() - start_op

        if df.empty:
            logger.debug(f"No data retrieved for {symbol} in concurrent operation")
            return (0, symbol)

        logger.info(
            f"Successfully retrieved {len(df)} records for {symbol} in {elapsed:.2f}s"
        )
        return (len(df), symbol)

    except Exception as e:
        logger.error(f"Error in concurrent fetch for {symbol}: {str(e)}")
        raise


async def verify_partial_minute_data():
    """Verify retrieval of data that spans from available past data to potentially unavailable recent data."""
    logger.info("===== VERIFYING PARTIAL DATA RETRIEVAL (PAST TO RECENT) =====")

    # Create manager
    manager = DataSourceManager(market_type=MarketType.SPOT, use_cache=False)

    # Define time range that spans from certainly available data to potentially unavailable recent data
    current_time = datetime.now(timezone.utc)

    # Start time is 60 minutes ago (should be fully available)
    start_time = current_time - timedelta(minutes=60)
    # End time is current time (some very recent data may not be consolidated)
    end_time = current_time

    logger.info(f"Current time: {current_time.isoformat()}")
    logger.info(f"Partial data time range: {start_time} to {end_time}")
    logger.info(
        f"This range intentionally spans from available past data (60 min ago) "
        f"to very recent data that may not be fully consolidated yet"
    )

    try:
        start_op = time.time()

        # Set up storage for capturing warnings
        warnings_detected = []

        # Create a context manager to temporarily capture warnings
        original_warning_fn = logger.warning

        def capture_warning(*args, **kwargs):
            message = args[0] if args else kwargs.get("msg", "")
            if isinstance(message, str) and (
                "may not be fully consolidated" in message or "Retrieved" in message
            ):
                warnings_detected.append(message)
            # Call the original warning function to maintain logging
            return original_warning_fn(*args, **kwargs)

        # Replace the warning function temporarily
        logger.warning = capture_warning

        # First case: Get data for the full range
        df = await manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.MINUTE_1,
            enforce_source=DataSource.REST,
        )

        # Restore original warning function
        logger.warning = original_warning_fn

        elapsed = time.time() - start_op

        logger.info(f"Partial data retrieval completed in {elapsed:.2f}s")
        logger.info(f"Retrieved {len(df)} records")

        if len(df) > 0:
            # Check data coverage
            data_start = df.index.min()
            data_end = df.index.max()
            logger.info(f"Data spans from {data_start} to {data_end}")

            # Calculate expected records
            total_minutes = (end_time - start_time).total_seconds() / 60
            actual_expected = (
                int(total_minutes) + 1
            )  # Add one for partial current minute

            # Calculate completion percentage
            completion_pct = (
                (len(df) / actual_expected) * 100 if actual_expected > 0 else 0
            )

            logger.info(
                f"Expected ~{actual_expected} minute records (up to current time), got {len(df)} ({completion_pct:.1f}% complete)"
            )

            missing_records = actual_expected - len(df)
            logger.info(
                f"Missing {missing_records} records (likely the most recent ones)"
            )

            # Show the most recent records to see where data cuts off
            if len(df) >= 2:
                logger.info(f"Last 2 records: {df.iloc[-2:].to_dict('records')}")

            # Second case: Demonstrate artificial partial retrieval by limiting data to first 45 records
            logger.info("\n=== DEMONSTRATING PARTIAL RETRIEVAL WITH SUBSET OF DATA ===")
            if len(df) > 45:
                partial_df = df.iloc[:45]
                logger.info(
                    f"Created artificial partial dataset with {len(partial_df)}/{len(df)} records ({len(partial_df)/len(df)*100:.1f}%)"
                )
                logger.info(
                    f"Partial data spans from {partial_df.index.min()} to {partial_df.index.max()}"
                )
                logger.info(
                    f"Missing {len(df) - len(partial_df)} records from the end of the dataset"
                )

                # Show a sample of where the data cuts off
                if len(partial_df) >= 2:
                    logger.info(
                        f"Last 2 records of partial dataset: {partial_df.iloc[-2:].to_dict('records')}"
                    )

                # Calculate completeness metrics
                partial_completion_pct = (
                    (len(partial_df) / actual_expected) * 100
                    if actual_expected > 0
                    else 0
                )
                logger.info(
                    f"Partial dataset has {len(partial_df)}/{actual_expected} expected records ({partial_completion_pct:.1f}% complete)"
                )

        else:
            logger.warning("No data retrieved at all")

        # Log any warnings that were captured
        if warnings_detected:
            logger.info(f"Detected {len(warnings_detected)} data availability warnings")
            for warning in warnings_detected[:3]:  # Show first few warnings
                logger.info(f"Sample warning: {warning}")

    except Exception as e:
        logger.error(f"Error retrieving partial data: {str(e)}")

    # Clean up resources
    await manager.__aexit__(None, None, None)


async def main():
    """Run all verification tests."""
    logger.info("===== STARTING DATA RETRIEVAL VERIFICATION =====")
    logger.info(f"Current time: {datetime.now(timezone.utc)}")

    # Ensure logs directory exists
    Path("logs/timeout_incidents").mkdir(parents=True, exist_ok=True)

    # Run verification tests
    await verify_sequential_data_retrieval()
    await verify_concurrent_data_retrieval()
    await verify_extended_historical_data()
    await verify_very_recent_hourly_data()
    await verify_very_recent_minute_data()
    await verify_partial_minute_data()

    logger.info("===== DATA RETRIEVAL VERIFICATION COMPLETE =====")


if __name__ == "__main__":
    # Run the verification
    asyncio.run(main())
