#!/usr/bin/env python

import asyncio
import time
import inspect
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys

from core.data_source_manager import DataSourceManager, DataSource
from utils.market_constraints import MarketType, Interval
from utils.logger_setup import logger
from utils.async_cleanup import cleanup_all_force_timeout_tasks


async def debug_tasks():
    """Print details about all running asyncio tasks."""
    print("\n--- Current asyncio tasks ---")
    for i, task in enumerate(asyncio.all_tasks()):
        print(f"Task {i+1}: {task}")
        if "_force_timeout" in str(task):
            print(f"  [FORCE TIMEOUT TASK DETECTED] {task}")
            # Print task stack
            if not task.done():
                task_stack = task.get_stack()
                print("  Task stack:")
                for frame in task_stack:
                    frame_info = inspect.getframeinfo(frame)
                    print(
                        f"    File {frame_info.filename}, line {frame_info.lineno}, in {frame_info.function}"
                    )
    print("---------------------------\n")


async def debug_cleanup_mechanism():
    """Test if the cleanup mechanism is working correctly."""
    print("\nTesting cleanup mechanism...")

    # Create the DataSourceManager
    manager = DataSourceManager(market_type=MarketType.SPOT)

    # Check tasks before any operations
    print("Tasks before any operations:")
    await debug_tasks()

    # Make a small data request to initialize clients
    print("Making a small data request...")
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=5)

    df = await manager.get_data(
        "BTCUSDT",
        start_time,
        end_time,
        interval=Interval.MINUTE_1,
        enforce_source=DataSource.REST,
        use_cache=False,
    )

    print(f"Retrieved {len(df)} records")

    # Check tasks after the request
    print("Tasks after request:")
    await debug_tasks()

    # Explicitly trigger cleanup
    print("Explicitly triggering cleanup...")
    await manager._cleanup_force_timeout_tasks()

    # Check tasks after explicit cleanup
    print("Tasks after explicit cleanup:")
    await debug_tasks()

    # Now try to clean up with the utility function
    print("Using utility function for force timeout cleanup...")
    await cleanup_all_force_timeout_tasks()

    # Check tasks after utility cleanup
    print("Tasks after utility cleanup:")
    await debug_tasks()

    # Finally clean up the manager
    print("Cleaning up the manager...")
    await manager.__aexit__(None, None, None)

    # Check tasks after manager cleanup
    print("Tasks after manager cleanup:")
    await debug_tasks()

    print("Cleanup mechanism test complete.\n")


async def debug_timeout_occurrence():
    """Test when exactly the timeout occurs in the data retrieval process."""
    print("\nDebugging timeout occurrence...")

    # Create the DataSourceManager with debug
    manager = DataSourceManager(market_type=MarketType.SPOT)

    # Set up a time range that should trigger a timeout
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=6)  # 6 hours data with 1s interval

    print(f"Fetching data for BTCUSDT from {start_time} to {end_time}...")

    # Instrument the _fetch_from_source method to see timing
    original_fetch = manager._fetch_from_source

    async def instrumented_fetch(*args, **kwargs):
        print(f"_fetch_from_source called at {time.time()}")
        start = time.time()
        try:
            result = await original_fetch(*args, **kwargs)
            print(f"_fetch_from_source completed in {time.time() - start:.2f}s")
            return result
        except Exception as e:
            print(f"_fetch_from_source failed after {time.time() - start:.2f}s: {e}")
            raise

    # Replace the method temporarily
    manager._fetch_from_source = instrumented_fetch

    # Time the get_data method
    start = time.time()
    try:
        print("Starting get_data call...")
        df = await manager.get_data(
            "BTCUSDT",
            start_time,
            end_time,
            interval=Interval.SECOND_1,
            enforce_source=DataSource.REST,
            use_cache=False,
        )

        elapsed = time.time() - start
        print(f"get_data completed in {elapsed:.2f}s, returned {len(df)} records")

        if df.empty:
            print("RESULT: Empty DataFrame (likely timeout)")
        else:
            print("RESULT: Data retrieved successfully (no timeout)")
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        print(f"EXPLICIT TIMEOUT: get_data timed out after {elapsed:.2f}s")
    except Exception as e:
        elapsed = time.time() - start
        print(
            f"ERROR: get_data failed after {elapsed:.2f}s with {type(e).__name__}: {e}"
        )

    # Check tasks after the operation
    await debug_tasks()

    # Clean up
    manager._fetch_from_source = original_fetch
    await manager.__aexit__(None, None, None)

    print("Timeout occurrence debug complete.\n")


async def debug_separate_operations():
    """Test each operation separately to find where the timeout might be occurring."""
    print("\nDebugging separate operations...")

    # Create the DataSourceManager
    manager = DataSourceManager(market_type=MarketType.SPOT)

    # 1. Test client initialization
    print("1. Testing client initialization...")
    start = time.time()
    try:
        await manager._ensure_rest_client("BTCUSDT", Interval.SECOND_1)
        print(f"REST client initialized in {time.time() - start:.2f}s")
    except Exception as e:
        print(
            f"REST client initialization failed after {time.time() - start:.2f}s: {e}"
        )

    # Check tasks
    await debug_tasks()

    # 2. Test a small data fetch
    print("2. Testing a small data fetch (last 5 minutes)...")
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=5)

    start = time.time()
    try:
        df = await manager.get_data(
            "BTCUSDT",
            start_time,
            end_time,
            interval=Interval.MINUTE_1,
            enforce_source=DataSource.REST,
            use_cache=False,
        )
        print(
            f"Small fetch completed in {time.time() - start:.2f}s, returned {len(df)} records"
        )
    except Exception as e:
        print(f"Small fetch failed after {time.time() - start:.2f}s: {e}")

    # Check tasks
    await debug_tasks()

    # 3. Test cleanup methods
    print("3. Testing cleanup methods...")
    start = time.time()
    try:
        await manager._cleanup_force_timeout_tasks()
        print(f"Force timeout cleanup completed in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"Force timeout cleanup failed after {time.time() - start:.2f}s: {e}")

    # Check tasks
    await debug_tasks()

    # 4. Test full cleanup
    print("4. Testing full cleanup with __aexit__...")
    start = time.time()
    try:
        await manager.__aexit__(None, None, None)
        print(f"Full cleanup completed in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"Full cleanup failed after {time.time() - start:.2f}s: {e}")

    # Check tasks
    await debug_tasks()

    print("Separate operations debug complete.\n")


async def main():
    """Run all debug operations."""
    # Create logs directory if needed
    Path("logs/timeout_incidents").mkdir(parents=True, exist_ok=True)

    print("=== DEBUGGING TIMEOUT ISSUES ===")
    print(f"Current time: {datetime.now(timezone.utc)}")
    print(f"Python version: {sys.version}")

    # Run the debug operations
    await debug_cleanup_mechanism()
    await debug_timeout_occurrence()
    await debug_separate_operations()

    # Final check for lingering tasks
    print("\nFinal task check:")
    await debug_tasks()

    print("=== DEBUG COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
