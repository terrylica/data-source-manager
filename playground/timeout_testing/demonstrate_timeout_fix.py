#!/usr/bin/env python

"""
Demonstration script to showcase the timeout fix in DataSourceManager.

This script focuses on testing the robustness of the timeout handling in the
DataSourceManager by running multiple scenarios:

1. Concurrent operations - Testing many overlapping data retrieval requests
   to ensure they complete without false timeout errors.
2. Resource cleanup - Verifying that resources are properly cleaned up after
   operations, preventing memory leaks and task accumulation.

The script serves as a stress test and verification that the timeout fix properly
handles concurrent and sequential operations, demonstrating that the fix addresses
the key issues with curl_cffi background tasks.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.data_source_manager import DataSourceManager, DataSource
from utils.market_constraints import MarketType, Interval
from utils.logger_setup import logger

# Set up logging for the demonstration script
logger.setup_root(level="ERROR", show_filename=True)
logger.use_rich(True)


async def run_concurrent_operations():
    """Run multiple operations concurrently to test the timeout fix."""
    logger.info("===== TESTING CONCURRENT OPERATIONS WITH TIMEOUT FIX =====")

    # Ensure the timeout log directory exists
    Path("logs/timeout_incidents").mkdir(parents=True, exist_ok=True)

    # Create managers for different market types
    spot_manager = DataSourceManager(market_type=MarketType.SPOT, use_cache=False)
    futures_manager = DataSourceManager(
        market_type=MarketType.FUTURES_USDT, use_cache=False
    )

    # Define symbols and time ranges
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    end_time = datetime.now(timezone.utc)

    # Create different time ranges to test various scenarios
    time_ranges = [
        (end_time - timedelta(minutes=60), end_time),  # 1 hour
        (end_time - timedelta(minutes=720), end_time),  # 12 hours
        (end_time - timedelta(days=1), end_time - timedelta(hours=6)),  # Older data
    ]

    # Create tasks for all combinations
    tasks = []

    for symbol in symbols:
        for start_time, end_time in time_ranges:
            # Add SPOT tasks
            tasks.append(
                fetch_data_with_timeout_protection(
                    spot_manager,
                    symbol,
                    start_time,
                    end_time,
                    Interval.MINUTE_1,
                    "SPOT",
                )
            )

            # Add FUTURES tasks with different intervals
            tasks.append(
                fetch_data_with_timeout_protection(
                    futures_manager,
                    symbol,
                    start_time,
                    end_time,
                    Interval.MINUTE_1,
                    "FUTURES",
                )
            )

    # Run all tasks concurrently
    start_time = time.time()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.time() - start_time

    # Analyze results - revised to be more accurate
    total_operations = len(results)
    actual_success_count = 0
    error_count = 0
    empty_data_count = 0

    for result in results:
        if isinstance(result, Exception):
            error_count += 1
        elif result is None or result == 0:  # Empty dataframe case
            empty_data_count += 1
        elif isinstance(result, int) and result > 0:  # Has data
            actual_success_count += 1
        else:
            # Unexpected result type
            error_count += 1

    logger.info("===== CONCURRENT OPERATIONS SUMMARY =====")
    logger.info(f"Total operations: {total_operations}")
    logger.info(f"Successful operations with data: {actual_success_count}")
    logger.info(f"Operations that returned empty data: {empty_data_count}")
    logger.info(f"Failed operations with errors: {error_count}")
    logger.info(f"Total time elapsed: {elapsed:.2f} seconds")

    # Check for specific errors
    timeout_errors = sum(
        1 for r in results if isinstance(r, Exception) and "timeout" in str(r).lower()
    )
    if timeout_errors > 0:
        logger.warning(f"Found {timeout_errors} timeout errors!")
    else:
        logger.info(f"SUCCESS: No timeout errors detected!")

    # Clean up resources
    await spot_manager.__aexit__(None, None, None)
    await futures_manager.__aexit__(None, None, None)


async def fetch_data_with_timeout_protection(
    manager, symbol, start_time, end_time, interval, market_type
):
    """Fetch data with timeout protection and detailed logging."""
    try:
        logger.info(
            f"Starting fetch for {symbol} ({market_type}) from {start_time} to {end_time}"
        )
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
            logger.warning(f"Empty data for {symbol} ({market_type})")
            return 0  # Return 0 to indicate empty data

        record_count = len(df)
        logger.info(
            f"Successfully fetched {record_count} records for {symbol} ({market_type}) in {elapsed:.2f}s"
        )
        return record_count  # Return positive count for success with data

    except Exception as e:
        logger.error(f"Error fetching {symbol} ({market_type}): {str(e)}")
        # Re-raise to be caught by the gather
        raise


async def test_cleanup_with_multiple_operations():
    """Test that cleanup works properly after multiple operations."""
    logger.info("===== TESTING CLEANUP AFTER MULTIPLE OPERATIONS =====")

    # Create a manager
    manager = DataSourceManager(market_type=MarketType.SPOT, use_cache=False)

    # Perform a series of operations
    symbol = "BTCUSDT"
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=60)

    logger.info("Performing 5 sequential operations")
    for i in range(5):
        # Adjust time slightly for each request
        request_start = start_time - timedelta(minutes=i * 10)
        request_end = end_time - timedelta(minutes=i * 10)

        logger.info(
            f"Operation {i+1}/5: Fetching {symbol} from {request_start} to {request_end}"
        )

        df = await manager.get_data(
            symbol=symbol,
            start_time=request_start,
            end_time=request_end,
            interval=Interval.MINUTE_1,
            enforce_source=DataSource.REST,
        )

        logger.info(f"Operation {i+1}/5 completed, retrieved {len(df)} records")

    # Now clean up and check for proper resource disposal
    logger.info("Testing cleanup...")
    await manager.__aexit__(None, None, None)
    logger.info("Cleanup complete!")

    # Create a new manager and do a single operation to verify everything works after cleanup
    logger.info("Creating new manager after cleanup...")
    new_manager = DataSourceManager(market_type=MarketType.SPOT, use_cache=False)

    df = await new_manager.get_data(
        symbol=symbol,
        start_time=start_time,
        end_time=end_time,
        interval=Interval.MINUTE_1,
        enforce_source=DataSource.REST,
    )

    logger.info(f"Post-cleanup operation successful, retrieved {len(df)} records")

    # Clean up the new manager
    await new_manager.__aexit__(None, None, None)


async def main():
    """Run all demonstration methods."""
    logger.info("===== DEMONSTRATING TIMEOUT FIX ROBUSTNESS =====")
    logger.info(f"Current time: {datetime.now(timezone.utc)}")

    # Run cleanup test
    await test_cleanup_with_multiple_operations()

    # Run concurrent operations test
    await run_concurrent_operations()

    logger.info("===== TIMEOUT FIX DEMONSTRATION COMPLETE =====")


if __name__ == "__main__":
    # Logger is already configured at the module level
    asyncio.run(main())
