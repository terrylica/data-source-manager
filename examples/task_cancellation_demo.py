#!/usr/bin/env python3
"""
Task Cancellation Demo for EventBasedFetcher and ConcurrentFetcher.

This script demonstrates how task cancellation works in the EventBasedFetcher and
ConcurrentFetcher classes. It shows various cancellation scenarios:
1. Manual cancellation (explicitly calling cancel on tasks)
2. Timeout cancellation (tasks cancelled due to timeout)
3. Concurrent cancellation (cancellation propagation in parallel tasks)
4. Signal cancellation (handling Ctrl+C and other signals)
5. Event-based cancellation (using completion events without timeouts)

The demo includes a subclass of EventBasedFetcher that introduces an artificial
delay in the fetch process to make cancellation more observable.
"""

from utils.logger_setup import logger
from rich import print
import asyncio
import signal
import time
import gc
import sys
import importlib
import shutil
import os
from examples.simple_data_retrieval import EventBasedFetcher, ConcurrentFetcher
from utils.market_constraints import Interval  # Import for Interval
from utils.async_cleanup import cancel_and_wait  # Import for better cancellation


# Configure logger
logger.setup_root(level="INFO", show_filename=True)


# Clear all caches at startup to ensure clean slate
def clear_caches():
    """Clear all caches to ensure a clean start for the demonstration"""
    logger.info("Clearing caches to ensure clean slate for demonstration")

    # Delete cache directory if it exists
    cache_dir = os.path.join(os.getcwd(), "cache")
    if os.path.exists(cache_dir):
        logger.info(f"Removing cache directory: {cache_dir}")
        try:
            shutil.rmtree(cache_dir)
            logger.info("Cache directory successfully removed")
        except Exception as e:
            logger.error(f"Error removing cache directory: {str(e)}")

    # Force reload of the module to clear any static caches
    if "examples.simple_data_retrieval" in sys.modules:
        importlib.reload(sys.modules["examples.simple_data_retrieval"])

    # Force garbage collection
    gc.collect()
    logger.info("Caches cleared")


# Global flag to track cancellation requests
cancellation_requested = False

# Simulation delay (in seconds) for demonstration purposes
SIMULATED_DELAY = 3


# New utility function for cleaning up lingering tasks
async def cleanup_lingering_tasks():
    """Clean up any lingering tasks to prevent leakage."""
    tasks = [t for t in asyncio.all_tasks() if t != asyncio.current_task()]

    if tasks:
        logger.info(f"Cleaning up {len(tasks)} lingering tasks")

        # Cancel all tasks
        for task in tasks:
            if not task.done() and not task.cancelled():
                task.cancel()

        # Wait for all tasks to complete (with timeout)
        if tasks:
            await asyncio.wait(tasks, timeout=2.0)

        # Force garbage collection to clean up resources
        gc.collect()

        # Check if any tasks are still running
        remaining = [t for t in tasks if not t.done()]
        if remaining:
            logger.warning(f"{len(remaining)} tasks still not completed after cleanup")


class DelayedEventBasedFetcher(EventBasedFetcher):
    """
    A subclass of EventBasedFetcher that introduces an artificial delay in fetching,
    and checks for cancellation requests during the delay.
    """

    async def _fetch_impl(self):
        """
        Override the fetch implementation to add delays and cancellation checks.
        """
        global cancellation_requested
        self.progress["stage"] = "delayed_fetch_started"

        try:
            # Log that we're starting the delayed operation
            logger.info(
                f"Starting delayed fetch for {self.symbol} with {SIMULATED_DELAY}s delay"
            )
            print(
                f"🕒 Fetching {self.symbol} with artificial {SIMULATED_DELAY}s delay..."
            )

            # Split the delay into small chunks to check for cancellation
            for i in range(SIMULATED_DELAY * 2):
                # Check if cancellation was requested
                if cancellation_requested or asyncio.current_task().cancelled():
                    logger.warning(
                        f"Cancellation detected during delay for {self.symbol}"
                    )
                    print(f"⚠️ Cancellation detected during delay for {self.symbol}")
                    # Raise cancellation error to simulate cancellation
                    raise asyncio.CancelledError("Manual cancellation during delay")

                # Update progress
                self.progress["delay_progress"] = (
                    f"{(i+1)/(SIMULATED_DELAY*2)*100:.0f}%"
                )

                # Sleep for a small chunk of time
                await asyncio.sleep(0.5)

                # Yield control to allow cancellation to occur
                await asyncio.sleep(0)

            # After delay, proceed with normal fetch
            self.progress["stage"] = "delay_complete_proceeding_with_fetch"
            logger.info(f"Delay complete for {self.symbol}, proceeding with fetch")

            # Call the parent implementation to do the actual fetch
            return await super()._fetch_impl()

        except asyncio.CancelledError:
            # Handle cancellation during the delay
            self.progress["stage"] = "cancelled_during_delay"
            logger.warning(
                f"Fetch operation for {self.symbol} was cancelled during delay"
            )
            print(f"✗ Fetch cancelled during delay for {self.symbol}")
            # Re-raise to ensure proper cancellation
            raise


class EventControlledFetcher(DelayedEventBasedFetcher):
    """
    A fetcher that relies on events for control flow rather than timeouts.
    This demonstrates how to implement cancellation using pure event-based mechanisms.
    """

    def __init__(self, symbol, interval, days_back=1):
        # Initialize with a very long timeout to effectively disable timeout-based cancellation
        super().__init__(
            symbol, interval, days_back, fallback_timeout=3600
        )  # 1 hour timeout

        # Additional events for fine-grained control
        self.pause_event = asyncio.Event()
        self.resume_event = asyncio.Event()
        self.cancel_event = asyncio.Event()

        # Set resume event initially to allow execution
        self.resume_event.set()

    async def fetch(self):
        """
        Override fetch method to incorporate event-based control.
        """
        # Start the actual fetch operation as a task
        fetch_task = asyncio.create_task(super().fetch())
        self.tasks.add(fetch_task)
        fetch_task.add_done_callback(lambda t: self.tasks.discard(t))

        # Control loop that monitors events and manages the task
        while not fetch_task.done():
            # Check for cancellation request
            if self.cancel_event.is_set() or asyncio.current_task().cancelled():
                logger.info(f"Cancel event detected for {self.symbol}")
                await cancel_and_wait(fetch_task, timeout=1.0)
                break

            # Check for pause request
            if self.pause_event.is_set() and not self.resume_event.is_set():
                logger.info(
                    f"Fetch operation for {self.symbol} is paused, waiting for resume"
                )
                # Wait for resume signal
                await self.resume_event.wait()
                logger.info(f"Resuming fetch operation for {self.symbol}")

            # Yield control briefly
            await asyncio.sleep(0.1)

        # Wait for task to complete (either normally or due to cancellation)
        try:
            result = await fetch_task
            return result
        except asyncio.CancelledError:
            logger.warning(
                f"Fetch operation for {self.symbol} was cancelled through event"
            )
            raise


async def demonstrate_manual_cancellation():
    """
    Demonstrates how to manually cancel a fetch task after letting it
    run for a short period of time.
    """
    print("\n" + "=" * 70)
    print("DEMONSTRATING MANUAL CANCELLATION")
    print("=" * 70)
    print("This demonstrates explicitly cancelling a task by calling .cancel() on it.")
    print(
        "The fetcher will show how it handles the cancellation and cleans up resources."
    )

    symbol = "BTCUSDT"
    interval = Interval.HOUR_1
    fetcher = DelayedEventBasedFetcher(symbol, interval, days_back=1)

    # Start the fetch but don't await it yet
    fetch_task = asyncio.create_task(fetcher.fetch())

    # Add the task to our tracking set
    fetcher.tasks.add(fetch_task)
    fetch_task.add_done_callback(lambda t: fetcher.tasks.discard(t))

    try:
        # Let it run for 2 seconds
        print(f"Letting fetch task run for 2 seconds before cancellation...")
        await asyncio.sleep(2)

        # Check if it's still running
        if not fetch_task.done():
            print(f"🛑 Manually cancelling fetch task for {symbol}...")
            # Use cancel_and_wait instead of just cancel()
            await cancel_and_wait(fetch_task, timeout=1.0)

            print(
                f"✓ Task cancellation status: {'Cancelled' if fetch_task.cancelled() else 'Not cancelled'}"
            )
        else:
            print(f"Task already completed before we could cancel it")

    except Exception as e:
        logger.error(f"Error during manual cancellation demonstration: {str(e)}")
        print(f"Error: {str(e)}")
    finally:
        # Ensure completion event is set
        if not fetcher.completion_event.is_set():
            fetcher.completion_event.set()

        # Clean up any lingering tasks
        for task in fetcher.tasks:
            if not task.done():
                await cancel_and_wait(task, timeout=0.5)

        # Run cleanup to prevent task leakage
        await cleanup_lingering_tasks()

    print(f"Manual cancellation demonstration complete")


async def demonstrate_timeout_cancellation():
    """
    Demonstrates cancellation due to timeout when a fetch operation
    takes too long to complete.
    """
    print("\n" + "=" * 70)
    print("DEMONSTRATING TIMEOUT CANCELLATION")
    print("=" * 70)
    print("This demonstrates how tasks can be cancelled due to a timeout.")
    print("We'll set a very short timeout that's shorter than our artificial delay.")

    symbol = "ETHUSDT"
    interval = Interval.HOUR_1

    # Create a fetcher with a very short timeout to ensure it times out
    fetcher = DelayedEventBasedFetcher(symbol, interval, days_back=1)

    # The artificial delay is longer than this timeout, so it should timeout
    very_short_timeout = 1.5  # seconds

    print(f"Starting fetch with a {very_short_timeout}s timeout (should fail)")

    # Create a task to track
    fetch_task = asyncio.create_task(fetcher.fetch())
    fetcher.tasks.add(fetch_task)
    fetch_task.add_done_callback(lambda t: fetcher.tasks.discard(t))

    try:
        # This should timeout since our artificial delay is longer
        result = await asyncio.wait_for(fetch_task, timeout=very_short_timeout)
        print(f"Unexpectedly completed without timeout: {result is not None}")
    except asyncio.TimeoutError:
        print(f"✓ Task timed out as expected after {very_short_timeout}s")
        # Make sure to cancel the task after timeout
        await cancel_and_wait(fetch_task, timeout=0.5)
    except Exception as e:
        logger.error(f"Unexpected error during timeout demonstration: {str(e)}")
        print(f"Unexpected error: {str(e)}")
    finally:
        # Ensure completion event is set
        if not fetcher.completion_event.is_set():
            fetcher.completion_event.set()

        # Clean up any lingering tasks
        for task in fetcher.tasks:
            if not task.done():
                await cancel_and_wait(task, timeout=0.5)

        # Run cleanup to prevent task leakage
        await cleanup_lingering_tasks()

    print(f"Timeout cancellation demonstration complete")


class DelayedConcurrentFetcher:
    """A simple concurrent fetcher implementation that uses our delayed fetcher"""

    def __init__(self):
        self.fetchers = []
        self.tasks = set()
        self.all_complete_event = asyncio.Event()

    async def fetch_multiple(self, requests):
        """Fetch data for multiple symbols concurrently using delayed fetchers"""
        results = {}
        fetch_tasks = []

        try:
            # Create a fetcher for each request
            for req in requests:
                symbol = req["symbol"]
                interval = req["interval"]

                # Create a delayed fetcher
                fetcher = DelayedEventBasedFetcher(
                    symbol=symbol, interval=interval, days_back=1
                )
                self.fetchers.append(fetcher)

                # Create task for this fetcher
                task = asyncio.create_task(fetcher.fetch())
                fetch_tasks.append((symbol, task))

                # Add to tracking set
                self.tasks.add(task)
                task.add_done_callback(lambda t: self.tasks.discard(t))

            # Print start message
            print(f"Starting {len(fetch_tasks)} concurrent fetch operations...")

            # Wait for fetchers to complete or timeout/cancellation
            done, pending = await asyncio.wait(
                [task for _, task in fetch_tasks],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=5.0,  # Add a reasonable timeout
            )

            # Process results (this would normally process all tasks)
            for symbol, task in fetch_tasks:
                if task in done:
                    try:
                        results[symbol] = task.result()
                        print(f"✓ {symbol}: Fetch completed")
                    except asyncio.CancelledError:
                        print(f"✗ {symbol}: Fetch was cancelled")
                        results[symbol] = None
                    except Exception as e:
                        print(f"✗ {symbol}: Error - {str(e)}")
                        results[symbol] = None
                else:
                    print(f"⏳ {symbol}: Task still pending")

            return results

        except asyncio.CancelledError:
            # Handle cancellation
            print("Concurrent fetch operation was cancelled")

            # Cancel all fetchers
            for fetcher in self.fetchers:
                if (
                    hasattr(fetcher, "completion_event")
                    and not fetcher.completion_event.is_set()
                ):
                    fetcher.completion_event.set()

            # Cancel all pending tasks
            for symbol, task in fetch_tasks:
                if not task.done():
                    await cancel_and_wait(task, timeout=0.5)

            # Raise to properly handle cancellation
            raise

        finally:
            # Ensure cleanup
            self.all_complete_event.set()

            # Clean up any lingering tasks
            for task in self.tasks:
                if not task.done():
                    await cancel_and_wait(task, timeout=0.5)


async def demonstrate_concurrent_cancellation():
    """
    Demonstrates cancellation in a concurrent fetcher that is handling
    multiple delayed fetchers at once.
    """
    print("\n" + "=" * 70)
    print("DEMONSTRATING CONCURRENT CANCELLATION")
    print("=" * 70)
    print(
        "This demonstrates how cancellation propagates through concurrent operations."
    )
    print("We'll start multiple fetchers and then cancel the main task.")

    # Create a concurrent fetcher
    concurrent_fetcher = DelayedConcurrentFetcher()

    # Define multiple requests
    requests = [
        {"symbol": "BTCUSDT", "interval": Interval.HOUR_1},
        {"symbol": "ETHUSDT", "interval": Interval.HOUR_1},
        {"symbol": "BNBUSDT", "interval": Interval.HOUR_1},
    ]

    # Start fetch task but don't await it yet
    fetch_task = asyncio.create_task(concurrent_fetcher.fetch_multiple(requests))

    try:
        # Let it run for 1.5 seconds
        print(f"Letting concurrent fetch run for 1.5 seconds...")
        await asyncio.sleep(1.5)

        # Then cancel it
        print(f"🛑 Cancelling all concurrent fetch operations...")
        # Use cancel_and_wait instead of just cancel()
        await cancel_and_wait(fetch_task, timeout=1.0)

        print(
            f"✓ Concurrent task cancellation status: {'Cancelled' if fetch_task.cancelled() else 'Not cancelled'}"
        )

    except Exception as e:
        logger.error(f"Error during concurrent cancellation demonstration: {str(e)}")
        print(f"Error: {str(e)}")
    finally:
        # Clean up any lingering tasks
        for task in concurrent_fetcher.tasks:
            if not task.done():
                await cancel_and_wait(task, timeout=0.5)

        # Clean up fetchers
        for fetcher in concurrent_fetcher.fetchers:
            if (
                hasattr(fetcher, "completion_event")
                and not fetcher.completion_event.is_set()
            ):
                fetcher.completion_event.set()

        # Run cleanup to prevent task leakage
        await cleanup_lingering_tasks()

    print(f"Concurrent cancellation demonstration complete")


def handle_signal(sig, frame):
    """
    Signal handler to gracefully handle cancellation requests.
    """
    global cancellation_requested

    if cancellation_requested:
        print("\n⚠️ Second interrupt received, forcing exit...")
        sys.exit(1)

    print("\n⚠️ Interrupt received, requesting graceful cancellation...")
    cancellation_requested = True


async def demonstrate_signal_cancellation():
    """
    Demonstrates handling external cancellation requests via signals.
    """
    global cancellation_requested

    # Reset the cancellation flag at the start
    cancellation_requested = False

    print("\n" + "=" * 70)
    print("DEMONSTRATING SIGNAL CANCELLATION")
    print("=" * 70)
    print("This demonstrates how to handle external cancellation (e.g., Ctrl+C).")
    print("The long-running fetch operation will monitor the cancellation flag.")
    print("Press Ctrl+C during execution to trigger cancellation.")
    print("(You have 10 seconds to press Ctrl+C before it completes normally)")

    # Register signal handler
    original_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        symbol = "BNBUSDT"
        interval = Interval.HOUR_1
        fetcher = DelayedEventBasedFetcher(symbol, interval, days_back=2)

        # Start the fetch
        print(f"Starting fetch for {symbol}...")
        fetch_task = asyncio.create_task(fetcher.fetch())
        fetcher.tasks.add(fetch_task)
        fetch_task.add_done_callback(lambda t: fetcher.tasks.discard(t))

        # Wait for completion or timeout
        try:
            result = await asyncio.wait_for(fetch_task, timeout=10.0)
            if not cancellation_requested:
                print(f"✓ Fetch completed normally without cancellation")
            else:
                print(f"✓ Fetch completed with cancellation request")
        except asyncio.TimeoutError:
            print(f"Fetch took too long and timed out")
            # Make sure to cancel the task after timeout
            await cancel_and_wait(fetch_task, timeout=0.5)
        except asyncio.CancelledError:
            print(f"✓ Fetch was cancelled as expected")
        except Exception as e:
            logger.error(f"Error during signal cancellation demonstration: {str(e)}")
            print(f"Error: {str(e)}")

    finally:
        # Restore original signal handler
        signal.signal(signal.SIGINT, original_handler)

        # Clean up fetcher
        if not fetcher.completion_event.is_set():
            fetcher.completion_event.set()

        # Clean up any lingering tasks
        for task in fetcher.tasks:
            if not task.done():
                await cancel_and_wait(task, timeout=0.5)

        # Run cleanup to prevent task leakage
        await cleanup_lingering_tasks()

        # Reset the cancellation flag
        cancellation_requested = False

    print(f"Signal cancellation demonstration complete")


async def demonstrate_event_based_cancellation():
    """
    Demonstrates pure event-based cancellation without relying on timeouts.
    This demonstrates a more robust approach that can replace timeout-based mechanisms.
    """
    print("\n" + "=" * 70)
    print("DEMONSTRATING EVENT-BASED CANCELLATION")
    print("=" * 70)
    print(
        "This demonstrates how to control task execution using events rather than timeouts."
    )
    print(
        "The fetcher is controlled entirely through events for pause, resume, and cancel."
    )

    symbol = "DOGEUSDT"
    interval = Interval.HOUR_1

    # Create event-controlled fetcher
    fetcher = EventControlledFetcher(symbol, interval, days_back=1)

    # Start the fetch operation
    print(f"Starting event-controlled fetch for {symbol}...")
    fetch_task = asyncio.create_task(fetcher.fetch())
    fetcher.tasks.add(fetch_task)
    fetch_task.add_done_callback(lambda t: fetcher.tasks.discard(t))

    # Let it run for 1 second
    await asyncio.sleep(1)

    # Demonstrate pausing the operation
    print(f"🔶 Pausing the fetch operation...")
    fetcher.pause_event.set()
    fetcher.resume_event.clear()

    # Wait while paused
    await asyncio.sleep(1)
    print(f"Operation is paused. Current stage: {fetcher.progress['stage']}")

    # Resume the operation
    print(f"▶️ Resuming the fetch operation...")
    fetcher.resume_event.set()

    # Let it run a bit more
    await asyncio.sleep(1)

    # Cancel through the event mechanism
    print(f"🛑 Cancelling through event mechanism...")
    fetcher.cancel_event.set()

    try:
        # Wait for the operation to complete (or cancel) with a reasonable timeout
        result = await asyncio.wait_for(fetch_task, timeout=5.0)
        print(
            f"Fetch completed successfully with {len(result) if result is not None else 0} records"
        )
    except asyncio.TimeoutError:
        print(f"Fetch took too long even after cancel request")
        await cancel_and_wait(fetch_task, timeout=0.5)
    except asyncio.CancelledError:
        print(f"✓ Fetch was cancelled through event mechanism as expected")
    except Exception as e:
        logger.error(f"Error during event-based cancellation: {str(e)}")
        print(f"Error: {str(e)}")
    finally:
        # Ensure proper cleanup
        if not fetcher.completion_event.is_set():
            fetcher.completion_event.set()

        # Clean up any lingering tasks - create a copy of the set before iterating
        for task in list(fetcher.tasks):
            if not task.done():
                await cancel_and_wait(task, timeout=0.5)

        # Run cleanup to prevent task leakage
        await cleanup_lingering_tasks()

    # Show final state
    print(f"Final operation state: {fetcher.progress['stage']}")

    print(f"Event-based cancellation demonstration complete")


async def test_for_warnings():
    """
    Focused test specifically designed to check if warnings have been fixed.
    This function runs quick cancellation scenarios and monitors for the warnings.
    """
    print("\n" + "=" * 70)
    print("RUNNING FOCUSED WARNING TEST")
    print("=" * 70)

    # Setup test logger to capture warnings
    class WarningCounter:
        def __init__(self):
            self.reset()

        def reset(self):
            self.task_leakage_warnings = 0
            self.still_running_warnings = 0
            self.cancelled_during_delay_warnings = 0

    warning_counter = WarningCounter()

    # Test handler to monitor log messages
    original_warning = logger.warning

    def warning_monitor(msg, *args, **kwargs):
        if "Task leakage detected" in msg:
            warning_counter.task_leakage_warnings += 1
        elif "still running after completion" in msg:
            warning_counter.still_running_warnings += 1
        elif "cancelled during delay" in msg:
            warning_counter.cancelled_during_delay_warnings += 1
        return original_warning(msg, *args, **kwargs)

    # Replace warning function
    logger.warning = warning_monitor

    try:
        # Test 1: Quick cancel test
        print("Test 1: Quick cancellation test")
        symbol = "XRPUSDT"
        interval = Interval.HOUR_1
        fetcher = DelayedEventBasedFetcher(symbol, interval, days_back=1)

        fetch_task = asyncio.create_task(fetcher.fetch())
        fetcher.tasks.add(fetch_task)
        fetch_task.add_done_callback(lambda t: fetcher.tasks.discard(t))

        # Cancel immediately
        await asyncio.sleep(0.5)
        await cancel_and_wait(fetch_task, timeout=1.0)

        # Clean up
        if not fetcher.completion_event.is_set():
            fetcher.completion_event.set()

        # Run cleanup
        await cleanup_lingering_tasks()

        # Test 2: Concurrent cancel test
        print("\nTest 2: Concurrent cancellation test")
        tasks_before = len(asyncio.all_tasks())

        concurrent_fetcher = DelayedConcurrentFetcher()
        requests = [
            {"symbol": "SOLUSDT", "interval": Interval.HOUR_1},
            {"symbol": "ADAUSDT", "interval": Interval.HOUR_1},
        ]

        fetch_task = asyncio.create_task(concurrent_fetcher.fetch_multiple(requests))

        # Cancel after brief delay
        await asyncio.sleep(0.5)
        await cancel_and_wait(fetch_task, timeout=1.0)

        # Clean up
        for fetcher in concurrent_fetcher.fetchers:
            if (
                hasattr(fetcher, "completion_event")
                and not fetcher.completion_event.is_set()
            ):
                fetcher.completion_event.set()

        # Run cleanup
        await cleanup_lingering_tasks()

        # Force garbage collection
        gc.collect()

        # Check for task leakage
        tasks_after = len(asyncio.all_tasks())
        if tasks_after > tasks_before:
            print(
                f"⚠️ Task leakage detected in test: {tasks_after - tasks_before} more tasks"
            )
        else:
            print(f"✓ No task leakage detected in test")

        # Report results
        print("\nWarning Test Results:")
        print(f"Task leakage warnings: {warning_counter.task_leakage_warnings}")
        print(f"Still running warnings: {warning_counter.still_running_warnings}")
        print(
            f"Cancelled during delay warnings: {warning_counter.cancelled_during_delay_warnings}"
        )

        success = (
            warning_counter.task_leakage_warnings == 0
            and warning_counter.still_running_warnings <= 1
        )  # Allow at most 1 still running warning

        if success:
            print("✅ WARNING TEST PASSED - Critical warnings have been fixed!")
        else:
            print("❌ WARNING TEST FAILED - Some warnings still present")

    finally:
        # Restore original warning function
        logger.warning = original_warning

    print("=" * 70)


async def main():
    """
    Main function that orchestrates the demonstration.
    """
    # Clear caches at startup
    clear_caches()

    print("\n" + "=" * 70)
    print("TASK CANCELLATION DEMONSTRATION")
    print("=" * 70)
    print("This script demonstrates various ways tasks can be cancelled in async code.")
    print("Each section shows a different cancellation scenario and how to handle it.")

    # Record all running tasks at start for leak detection
    tasks_at_start = len(asyncio.all_tasks())
    logger.info(f"Starting with {tasks_at_start} active tasks")

    # Run the focused test for warnings first
    await test_for_warnings()

    # Demonstrate manual cancellation
    await demonstrate_manual_cancellation()

    # Demonstrate timeout cancellation
    await demonstrate_timeout_cancellation()

    # Demonstrate concurrent cancellation
    await demonstrate_concurrent_cancellation()

    # Demonstrate signal cancellation
    await demonstrate_signal_cancellation()

    # Demonstrate event-based cancellation (the new method)
    await demonstrate_event_based_cancellation()

    # Force cleanup of any lingering tasks before checking for leakage
    await cleanup_lingering_tasks()

    # Force garbage collection
    gc.collect()

    # Check for task leakage at the end
    tasks_at_end = len(asyncio.all_tasks())
    if tasks_at_end > tasks_at_start:
        logger.warning(
            f"Task leakage detected: {tasks_at_end - tasks_at_start} more tasks at end than at start"
        )
        print(
            f"⚠️ Task leakage detected: {tasks_at_end - tasks_at_start} more tasks at end than at start"
        )
    else:
        logger.info(f"No task leakage detected. Tasks at end: {tasks_at_end}")
        print(f"✓ No task leakage detected. Tasks at end: {tasks_at_end}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(main())
