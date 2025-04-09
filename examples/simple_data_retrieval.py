#!/usr/bin/env python
"""
Simple example script demonstrating basic usage of the DataSourceManager.

This example shows:
1. Basic data retrieval for a single symbol
2. Using the caching mechanism
3. Asynchronous operations for data retrieval
4. Event-based completion detection

This serves as a simpler introduction to the system compared to the
more comprehensive verify_data_retrieval.py example.
"""

import asyncio
import time
import gc
import pandas as pd
from datetime import datetime, timezone, timedelta

from utils.logger_setup import logger
from rich import print
from core.data_source_manager import DataSourceManager, DataSource
from utils.market_constraints import MarketType, Interval, DataProvider
from utils.error_handling import cleanup_tasks
from utils.async_cleanup import cancel_and_wait

# Setup logging - change to DEBUG for more detailed logs
logger.setup_root(level="DEBUG", show_filename=True)

# Set maximum durations for operations
MAX_SINGLE_OPERATION_TIMEOUT = 15  # 15 seconds for single operations
MAX_CONCURRENT_OPERATION_TIMEOUT = 20  # 20 seconds for concurrent operations


class EventBasedFetcher:
    """
    A wrapper for data fetching operations that uses events to signal
    completion and provides precise monitoring of the operation's progress.
    """

    def __init__(
        self,
        symbol,
        interval,
        days_back,
        use_cache=True,
        fallback_timeout=MAX_SINGLE_OPERATION_TIMEOUT,
    ):
        """
        Initialize the event-based fetcher.

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT")
            interval: Time interval for the data
            days_back: Number of days to go back from current time
            use_cache: Whether to use the caching system
            fallback_timeout: Fallback timeout in seconds (only used if events fail)
        """
        self.symbol = symbol
        self.interval = interval
        self.days_back = days_back
        self.use_cache = use_cache
        self.fallback_timeout = fallback_timeout

        # Calculate time range
        self.end_time = datetime.now(timezone.utc)
        self.start_time = self.end_time - timedelta(days=days_back)

        # Event to signal completion
        self.completion_event = asyncio.Event()

        # Container for results and errors
        self.result = None
        self.error = None

        # Progress tracking
        self.progress = {
            "stage": "initializing",
            "chunks_total": 0,
            "chunks_completed": 0,
            "records": 0,
        }

        # Safety fallback timeout - still have this as a fallback
        self.safety_timeout = fallback_timeout

        # Keep track of tasks for proper cleanup
        self.tasks = set()

    async def monitor_progress(self):
        """Monitor and log the progress of the data retrieval operation."""
        try:
            start_time = time.time()
            while not self.completion_event.is_set():
                # Check if we've exceeded the fallback timeout
                elapsed = time.time() - start_time
                if elapsed > self.safety_timeout:
                    logger.warning(
                        f"Fallback timeout exceeded ({self.safety_timeout}s), forcing completion"
                    )
                    self.progress["stage"] = "timeout"
                    self.error = TimeoutError(
                        f"Operation for {self.symbol} exceeded safety timeout of {self.safety_timeout}s"
                    )
                    self.completion_event.set()
                    break

                logger.info(
                    f"Progress for {self.symbol}: Stage={self.progress['stage']}, "
                    f"Chunks={self.progress['chunks_completed']}/{self.progress['chunks_total'] or '?'}, "
                    f"Records={self.progress['records']}, "
                    f"Elapsed={elapsed:.1f}s/{self.safety_timeout}s"
                )
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.debug(f"Progress monitor for {self.symbol} was cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in progress monitor: {str(e)}")
            # Ensure completion event is set even if monitor fails
            if not self.completion_event.is_set():
                self.error = e
                self.completion_event.set()

    async def fetch(self):
        """
        Execute the data retrieval with event-based completion tracking.

        Returns:
            DataFrame with market data if successful, None otherwise
        """
        print(
            f"Fetching data for {self.symbol} with interval {self.interval.value}, "
            f"cache={'enabled' if self.use_cache else 'disabled'}"
        )
        print(
            f"Time range: {self.start_time.isoformat()} to {self.end_time.isoformat()}"
        )

        # Start the progress monitor
        monitor_task = asyncio.create_task(self.monitor_progress())
        self.tasks.add(monitor_task)
        monitor_task.add_done_callback(self.tasks.discard)

        # Start the main data retrieval task
        fetch_task = asyncio.create_task(self._fetch_impl())
        self.tasks.add(fetch_task)
        fetch_task.add_done_callback(self.tasks.discard)

        logger.debug(f"Started fetch and monitor tasks for {self.symbol}")

        try:
            # Wait for either the completion event or the fetch task to finish
            logger.debug(
                f"Waiting for fetch completion or event signal for {self.symbol}"
            )
            done, pending = await asyncio.wait(
                [fetch_task, asyncio.create_task(self.completion_event.wait())],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=self.fallback_timeout,
            )

            logger.debug(
                f"Wait completed for {self.symbol}. Done tasks: {len(done)}, Pending: {len(pending)}"
            )

            # Check which task completed
            if fetch_task in done:
                # Fetch task completed normally
                try:
                    self.result = fetch_task.result()
                    logger.info(f"Fetch task for {self.symbol} completed successfully")
                    logger.debug(
                        f"Result for {self.symbol}: {type(self.result)}, Empty: {self.result is None or (isinstance(self.result, pd.DataFrame) and self.result.empty)}"
                    )
                except Exception as e:
                    logger.error(f"Fetch task for {self.symbol} failed: {str(e)}")
                    self.error = e

                # Ensure completion event is set
                if not self.completion_event.is_set():
                    logger.debug(
                        f"Setting completion event for {self.symbol} after fetch task completion"
                    )
                    self.completion_event.set()
            else:
                # Completion event was signaled before fetch task completed
                logger.info(f"Completion event for {self.symbol} was signaled")

                # Cancel fetch task if still running
                if not fetch_task.done():
                    logger.warning(
                        f"Cancelling fetch task for {self.symbol} that's still running"
                    )
                    fetch_task.cancel()

                    # Wait a bit for cancellation to take effect
                    try:
                        await asyncio.wait_for(fetch_task, timeout=1.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass

            # If we timed out waiting for either task
            if not done and not self.completion_event.is_set():
                logger.warning(f"Operation timeout for {self.symbol}")
                self.error = TimeoutError(f"Operation for {self.symbol} timed out")
                self.completion_event.set()

                if not fetch_task.done():
                    logger.warning(f"Cancelling fetch task for {self.symbol}")
                    fetch_task.cancel()

            # If there was an error, log it
            if self.error:
                print(f"✗ Error retrieving {self.symbol}: {str(self.error)}")
                return None

            # Return the result
            return self.result

        except Exception as e:
            logger.error(f"Error in event-based operation for {self.symbol}: {str(e)}")
            self.error = e
            return None

        finally:
            # Cancel the monitor task if it's still running
            if not monitor_task.done():
                logger.debug(f"Cancelling progress monitor task for {self.symbol}")
                monitor_task.cancel()

            # If fetch task is somehow still running, cancel it
            if not fetch_task.done():
                logger.warning(
                    f"Fetch task for {self.symbol} still running after completion; forcing cancellation"
                )
                fetch_task.cancel()

            # Make sure completion event is set
            if not self.completion_event.is_set():
                logger.debug(
                    f"Setting completion event in finally block for {self.symbol}"
                )
                self.completion_event.set()

            # Cancel any remaining tasks that might be lingering
            for task in self.tasks:
                if not task.done():
                    task.cancel()

            # Wait for all tasks to finish (with timeout)
            if self.tasks:
                try:
                    remaining = [t for t in self.tasks if not t.done()]
                    if remaining:
                        await asyncio.wait(remaining, timeout=0.5)
                except Exception as e:
                    logger.error(f"Error waiting for tasks to cancel: {str(e)}")

            # Force garbage collection to clean up resources
            gc.collect()

    async def _fetch_impl(self):
        """
        Implementation of the data retrieval operation that signals
        completion through the event mechanism.
        """
        manager = None
        start_fetch = time.time()

        try:
            self.progress["stage"] = "connecting"
            logger.debug(f"Starting fetch implementation for {self.symbol}")

            # Create data manager - don't use async with here to have more control
            manager = DataSourceManager(
                market_type=MarketType.SPOT,
                provider=DataProvider.BINANCE,
                use_cache=self.use_cache,
            )

            # Enter the context manager manually
            await manager.__aenter__()
            logger.debug(f"Initialized DataSourceManager for {self.symbol}")

            self.progress["stage"] = "requesting"

            # Request data with timeout
            logger.debug(f"Creating fetch task for {self.symbol}")
            fetch_task = asyncio.create_task(
                manager.get_data(
                    symbol=self.symbol,
                    start_time=self.start_time,
                    end_time=self.end_time,
                    interval=self.interval,
                    enforce_source=DataSource.REST,
                )
            )

            # Register and track the task
            self.tasks.add(fetch_task)
            fetch_task.add_done_callback(self.tasks.discard)

            # Wait for the fetch to complete with a timeout
            logger.debug(f"Waiting for data retrieval to complete for {self.symbol}")
            df = await asyncio.wait_for(fetch_task, timeout=self.fallback_timeout * 0.8)
            logger.debug(
                f"Data retrieval completed for {self.symbol}, df is None: {df is None}, df is empty: {df is not None and df.empty}"
            )

            self.progress["stage"] = "processing_results"
            elapsed = time.time() - start_fetch

            # Process results
            if df is not None and not df.empty:
                self.progress["records"] = len(df)
                self.progress["stage"] = "completed"
                logger.debug(
                    f"Completed fetch for {self.symbol} with {len(df)} records"
                )

                # Store result
                self.result = df

                # Show results
                print(
                    f"✓ Retrieved {len(df)} records for {self.symbol} in {elapsed:.2f}s"
                )
                if len(df) > 0:
                    print(f"  First record: {df.index.min()}")
                    print(f"  Last record: {df.index.max()}")

                    # Display a few example records only for the first symbol
                    if self.symbol == "BTCUSDT":
                        print("\nSample data (first 3 records):")
                        print(df.head(3))
            else:
                self.progress["stage"] = "no_data"
                logger.debug(f"No data retrieved for {self.symbol}")
                print(f"✗ No data retrieved for {self.symbol}")

            logger.debug(f"Finished _fetch_impl for {self.symbol}, will return data")
            return df

        except asyncio.TimeoutError:
            self.progress["stage"] = "timeout"
            logger.error(f"Timeout in data retrieval for {self.symbol}")
            self.error = TimeoutError(f"Data retrieval for {self.symbol} timed out")
            return None

        except asyncio.CancelledError:
            self.progress["stage"] = "cancelled"
            logger.warning(f"Fetch operation for {self.symbol} was cancelled")
            raise

        except Exception as e:
            self.progress["stage"] = "error"
            logger.error(f"Error retrieving data for {self.symbol}: {str(e)}")
            self.error = e
            return None

        finally:
            # Signal completion in finally block to ensure it happens
            if not self.completion_event.is_set():
                logger.debug(
                    f"Setting completion event in _fetch_impl finally block for {self.symbol}"
                )
                self.completion_event.set()

            # Always clean up the manager
            if manager:
                try:
                    logger.debug(f"Cleaning up manager for {self.symbol}")
                    await manager.__aexit__(None, None, None)
                    logger.debug(f"Manager cleanup complete for {self.symbol}")
                except Exception as e:
                    logger.error(
                        f"Error during manager cleanup for {self.symbol}: {str(e)}"
                    )


async def demonstrate_caching_benefit(symbol, interval, days_back):
    """
    Demonstrate the benefit of caching by fetching the same data twice,
    first without cache and then with cache enabled.
    """
    print("\n" + "=" * 50)
    print("DEMONSTRATING CACHING BENEFIT")
    print("=" * 50)

    # First fetch: Without cache
    print("\n1. First fetch (cache disabled):")
    fetcher1 = EventBasedFetcher(symbol, interval, days_back, use_cache=False)
    await fetcher1.fetch()

    # Second fetch: With cache
    print("\n2. Second fetch (cache enabled):")
    fetcher2 = EventBasedFetcher(symbol, interval, days_back, use_cache=True)
    await fetcher2.fetch()

    print(
        "\nNote: The second fetch should be significantly faster if data was cached successfully."
    )


class ConcurrentFetcher(EventBasedFetcher):
    """Fetcher that handles multiple fetch operations concurrently."""

    def __init__(self):
        super().__init__()
        self.overall_statuses = {}
        self.all_complete_event = asyncio.Event()

    async def fetch_multiple(self, requests, timeout=20):
        """Fetch data for multiple symbols concurrently."""
        tasks = []
        results = {}

        # Initialize overall status tracking
        completed_count = 0
        total_count = len(requests)
        self.overall_statuses = {
            "total": total_count,
            "completed": completed_count,
            "success_count": 0,
            "error_count": 0,
            "results": {},
        }

        # Create the all_complete_event
        self.all_complete_event = asyncio.Event()

        # Start all fetch operations
        for req in requests:
            symbol = req["symbol"]
            interval = req["interval"]
            start_time = req.get("start_time")
            end_time = req.get("end_time")
            use_cache = req.get("use_cache", True)

            print(
                f"Fetching data for {symbol} with interval {interval}, cache={'enabled' if use_cache else 'disabled'}"
            )
            print(f"Time range: {start_time} to {end_time}")

            # Create task but don't wait for it yet
            task = asyncio.create_task(
                self.fetch(symbol, interval, start_time, end_time, timeout, use_cache)
            )
            tasks.append((symbol, task))

            # Add task to our tracking set
            self.tasks.add(task)
            task.add_done_callback(lambda t: self.tasks.discard(t))

            # Initialize result tracking
            self.overall_statuses["results"][symbol] = {
                "stage": "initializing",
                "error": None,
                "success": False,
            }

        # Start progress monitoring
        monitor_task = asyncio.create_task(self.monitor_overall_progress(timeout))

        self.tasks.add(monitor_task)
        monitor_task.add_done_callback(lambda t: self.tasks.discard(t))

        # Wait for all fetch operations to complete
        try:
            # Wait for all fetching to complete or timeout
            done, pending = await asyncio.wait(
                [task for _, task in tasks], timeout=timeout
            )

            # Process results
            for symbol, task in tasks:
                if task in done:
                    try:
                        results[symbol] = task.result()
                        success = results[symbol] is not None
                        self.overall_statuses["results"][symbol]["success"] = success
                        self.overall_statuses["success_count"] += 1 if success else 0
                        self.overall_statuses["error_count"] += 0 if success else 1
                    except Exception as e:
                        logger.exception(f"Error processing result for {symbol}: {e}")
                        results[symbol] = None
                        self.overall_statuses["results"][symbol]["error"] = str(e)
                        self.overall_statuses["error_count"] += 1
                else:
                    # Task timed out
                    task.cancel()
                    results[symbol] = None
                    self.overall_statuses["results"][symbol][
                        "error"
                    ] = f"Timeout fetching {symbol}"
                    self.overall_statuses["results"][symbol]["stage"] = "timeout"
                    self.overall_statuses["error_count"] += 1

                self.overall_statuses["completed"] += 1

            # Set the completion event
            self.all_complete_event.set()
            logger.info("All operations complete, setting all_complete_event")

            # Cancel the monitor task
            monitor_task.cancel()

            return results

        except asyncio.TimeoutError:
            # Overall timeout occurred
            logger.error(f"Overall timeout after {timeout} seconds")

            # Cancel all pending tasks
            for symbol, task in tasks:
                if not task.done():
                    task.cancel()
                    self.overall_statuses["results"][symbol][
                        "error"
                    ] = "Operation timed out"
                    self.overall_statuses["results"][symbol]["stage"] = "timeout"

            # Set the completion event
            self.all_complete_event.set()

            # Cancel the monitor task
            monitor_task.cancel()

            return results
        except Exception as e:
            logger.exception(f"Error in fetch_multiple: {e}")

            # Cancel all tasks
            for _, task in tasks:
                if not task.done():
                    task.cancel()

            # Set the completion event
            self.all_complete_event.set()

            # Cancel the monitor task
            monitor_task.cancel()

            return results


async def run_single_test():
    """Run only a single test case to diagnose issues"""
    print("\n" + "=" * 60)
    print("RUNNING SINGLE TEST CASE")
    print("=" * 60)

    # Record all running tasks at start for leak detection
    tasks_at_start = len(asyncio.all_tasks())
    logger.info(f"Starting with {tasks_at_start} active tasks")

    # Just one symbol
    symbol = "BTCUSDT"
    interval = Interval.HOUR_1
    days_back = 1

    # Create and run a single fetcher
    fetcher = EventBasedFetcher(symbol, interval, days_back, use_cache=False)
    result = await fetcher.fetch()

    print("\nTest completion status:")
    print(f"Symbol: {symbol}")
    print(f"Result: {'Retrieved' if result is not None else 'None'}")
    print(f"Error: {fetcher.error}")
    print(f"Final stage: {fetcher.progress['stage']}")

    # Check for task leakage
    tasks_at_end = len(asyncio.all_tasks())
    print(f"Tasks at start: {tasks_at_start}, Tasks at end: {tasks_at_end}")

    return result is not None


async def main():
    """Run all example operations."""
    print("\n" + "=" * 60)
    print("SIMPLE DATA RETRIEVAL EXAMPLE")
    print("=" * 60)

    # Record all running tasks at start for leak detection
    tasks_at_start = len(asyncio.all_tasks())
    logger.info(f"Starting with {tasks_at_start} active tasks")

    # First, run just a single test to diagnose issues
    success = await run_single_test()

    if not success:
        logger.warning("Single test failed. Not continuing with remaining tests.")
        return

    # Example parameters
    symbol = "BTCUSDT"
    interval = Interval.HOUR_1
    days_back = 3

    # Example 1: Basic data retrieval using event-based completion
    print("\n" + "=" * 50)
    print("BASIC DATA RETRIEVAL EXAMPLE")
    print("=" * 50)

    fetcher = EventBasedFetcher(symbol, interval, days_back)
    await fetcher.fetch()

    # Example 2: Caching benefit demonstration
    await demonstrate_caching_benefit(symbol, interval, days_back)

    # Example 3: Asynchronous operations with fewer symbols and less data
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]  # Reduced symbol count
    concurrent_fetcher = ConcurrentFetcher(symbols, interval, 1)
    await concurrent_fetcher.fetch_all()

    # Explicitly force garbage collection to clean up resources
    gc.collect()

    # Check for task leakage at the end
    tasks_at_end = len(asyncio.all_tasks())
    if tasks_at_end > tasks_at_start:
        logger.warning(
            f"Task leakage detected: {tasks_at_end - tasks_at_start} more tasks at end than at start"
        )
        print(
            f"Task leakage detected: {tasks_at_end - tasks_at_start} more tasks at end than at start"
        )
    else:
        logger.info(f"No task leakage detected. Tasks at end: {tasks_at_end}")
        print(f"No task leakage detected. Tasks at end: {tasks_at_end}")

    print("\n" + "=" * 60)
    print("EXAMPLE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    # Run the example
    asyncio.run(main())
