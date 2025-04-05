# Implementation Guide: Focused Resource Management

This guide provides a practical approach to implementing focused resource management techniques that solve the specific hanging cleanup issue in `vision_data_client.py` while minimizing complexity.

## Core Concepts

Our implementation focuses on three key concepts:

1. **Deadline-based cleanup**: Enforcing strict time limits on cleanup operations
2. **Immediate reference nullification**: Breaking reference cycles to aid garbage collection
3. **Direct task management**: Explicitly creating and managing cleanup tasks

## Implementation Details

### 1. Resource Management Utility

Create a new file at `utils/resource_management.py` containing a single, focused utility class:

```python
from utils.logger_setup import logger
import asyncio
import time
from typing import Dict, List, Optional, Set, Any, Callable, Coroutine
from contextlib import AbstractAsyncContextManager

class DeadlineCleanupManager(AbstractAsyncContextManager):
    """A context manager that enforces a deadline for cleanup operations.

    This class helps manage asynchronous cleanup operations that must complete
    within a specified deadline. It provides utility methods for tracking time
    remaining and managing cleanup tasks.
    """

    def __init__(self, timeout: float = 5.0):
        """Initialize the DeadlineCleanupManager.

        Args:
            timeout: Maximum time (in seconds) allowed for cleanup
        """
        self.timeout = timeout
        self.start_time: Optional[float] = None
        self.tasks: Set[asyncio.Task] = set()
        self.errors: List[Exception] = []

    async def __aenter__(self):
        """Enter the context manager."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager, ensuring all tasks are properly cleaned up.

        All tracked tasks will be cancelled if they haven't completed by the deadline.
        Errors from cleanup tasks are collected but don't prevent other cleanups.
        """
        try:
            # Cancel any remaining tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete or be cancelled
            if self.tasks:
                await asyncio.wait(self.tasks, timeout=self.time_remaining)

            # Collect any errors
            for task in self.tasks:
                if task.done() and not task.cancelled():
                    try:
                        # Get the result to surface any exceptions
                        task.result()
                    except Exception as e:
                        self.errors.append(e)
                        logger.warning(f"Error during cleanup: {e}")
        except Exception as e:
            logger.error(f"Error during cleanup task management: {e}")
            self.errors.append(e)

        # Log summary
        if self.errors:
            logger.warning(f"Completed cleanup with {len(self.errors)} errors")
        else:
            logger.debug("Completed cleanup successfully")

        # Return False to allow any incoming exception to propagate
        return False

    def start_deadline(self):
        """Start the deadline timer."""
        self.start_time = time.monotonic()

    @property
    def time_remaining(self) -> float:
        """Calculate the remaining time before the deadline.

        Returns:
            The time remaining in seconds, or 0 if the deadline has passed.
        """
        if self.start_time is None:
            return self.timeout

        elapsed = time.monotonic() - self.start_time
        remaining = max(0.0, self.timeout - elapsed)
        return remaining

    def create_task(self, coro: Coroutine) -> asyncio.Task:
        """Create and track an asyncio Task.

        Args:
            coro: The coroutine to run as a task

        Returns:
            The created asyncio Task
        """
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(lambda t: self.tasks.discard(t))
        return task
```

### 2. VisionDataClient.**aexit** Refactoring

Refactor the `__aexit__` method in `core/vision_data_client.py` to use the new utility:

```python
async def __aexit__(self, exc_type, exc_val, exc_tb):
    """Exit the context manager, ensuring all resources are properly cleaned up.

    This implementation ensures proper cleanup of all resources with strict deadline
    enforcement, preventing hanging during cleanup operations.
    """
    from utils.resource_management import DeadlineCleanupManager

    logger.debug("Starting VisionDataClient cleanup")

    # Immediately break reference cycles
    session = self._session
    http_client = self._http_client
    fetched_files = list(self._fetched_files.keys()) if self._fetched_files else []

    # Set references to None to help garbage collection
    self._session = None
    self._http_client = None
    self._fetched_files = None

    # No cleanup needed if resources weren't initialized
    if session is None and http_client is None and not fetched_files:
        logger.debug("No resources to clean up")
        return False

    # Use the DeadlineCleanupManager to enforce cleanup timeout
    async with DeadlineCleanupManager(timeout=5.0) as manager:
        manager.start_deadline()

        # Prioritize cleanup of synchronous operations first
        try:
            # Close HTTP client (this is a sync operation in some implementations)
            if http_client is not None:
                logger.debug("Cleaning up HTTP client")
                try:
                    if hasattr(http_client, 'close'):
                        if asyncio.iscoroutinefunction(http_client.close):
                            manager.create_task(http_client.close())
                        else:
                            http_client.close()
                except Exception as e:
                    logger.warning(f"Error closing HTTP client: {e}")
        except Exception as e:
            logger.error(f"Error during synchronous cleanup: {e}")

        # Clean up session resources asynchronously
        if session is not None:
            logger.debug("Cleaning up session")
            try:
                # Shield the task to prevent cancellation during critical cleanup
                manager.create_task(asyncio.shield(session.close()))
            except Exception as e:
                logger.warning(f"Error closing session: {e}")

        # Clean up any fetched files
        for file_path in fetched_files:
            try:
                if os.path.exists(file_path):
                    logger.debug(f"Removing temporary file: {file_path}")
                    manager.create_task(self._remove_file(file_path))
            except Exception as e:
                logger.warning(f"Error removing file {file_path}: {e}")

    # Log completion
    logger.debug("VisionDataClient cleanup completed")
    return False

async def _remove_file(self, file_path: str):
    """Remove a file asynchronously."""
    try:
        os.remove(file_path)
    except Exception as e:
        logger.warning(f"Failed to remove file {file_path}: {e}")
```

### 3. Example Script Compatibility

For `examples/data_retrieval_best_practices.py`, we need to ensure our resource management improvements don't break user-facing APIs while still benefiting from the enhanced cleanup reliability.

#### Key Considerations

1. **Transparent Resource Management**: Users shouldn't need to know about the internals of resource cleanup
2. **Consistent Error Handling**: Error patterns in example scripts must remain stable
3. **Backward Compatibility**: Existing patterns like async context managers must continue to work

#### Areas to Test and Verify

```python
# Key section in data_retrieval_best_practices.py to verify/update:

async def example_fetch_historical_data():
    # ...
    async with DataSourceManager(
        market_type=MarketType.SPOT,
        cache_dir=cache_dir,
        use_cache=True,
    ) as manager:
        try:
            # Store initial stats
            prev_stats = manager.get_cache_stats().copy()

            # For historical data, Vision API will automatically be selected
            # but we enforce it here to demonstrate the capability
            df = await manager.get_data(
                symbol="BTCUSDT",
                start_time=start_time,
                end_time=end_time,
                interval=Interval.SECOND_1,
                enforce_source=DataSource.VISION,  # Enforce Vision API
            )

            # [...rest of function...]

        except Exception as e:
            logger.error(f"[bold red]Error fetching historical data: {e}[/bold red]")
            return  # Exit the function to prevent further processing

        finally:
            # Ensure vision client is properly cleaned up
            if hasattr(manager, "vision_client") and manager.vision_client is not None:
                try:
                    logger.debug("Ensuring vision client is properly closed")
                    # Create task to close client, but don't wait for it
                    asyncio.create_task(
                        manager.vision_client.__aexit__(None, None, None)
                    )
                except Exception as e:
                    logger.warning(f"Error while cleaning up vision client: {e}")
```

#### Recommended Approach

1. **Keep Manual Cleanup Code**: The example script's explicit cleanup in `finally` blocks may be redundant but should be preserved for clarity of example
2. **Validation Comments**: Add explanatory comments about resource management within the example
3. **Clear Error Messages**: Ensure any resource-related errors are clearly logged

Suggested documentation update for the example script:

```python
# Add to example_fetch_historical_data() docstring:
"""
Note on resource management:
This example shows proper cleanup patterns with both automatic (via context manager)
and manual cleanup approaches. In practice, using the DataSourceManager as an async
context manager is sufficient, as it will handle cleanup of all underlying
resources, including Vision API clients.
"""
```

## Testing Strategy

### Unit Tests for DeadlineCleanupManager

Create a test file at `tests/utils/test_resource_management.py`:

```python
import asyncio
import pytest
import time
from utils.resource_management import DeadlineCleanupManager

@pytest.mark.asyncio
async def test_deadline_enforcement():
    """Test that the DeadlineCleanupManager enforces deadlines."""
    # Create a task that sleeps for longer than the deadline
    async with DeadlineCleanupManager(timeout=0.5) as manager:
        manager.start_deadline()

        # Create a task that will exceed the deadline
        async def long_running_task():
            await asyncio.sleep(2.0)

        task = manager.create_task(long_running_task())

        # Let the task run for a bit but not complete
        await asyncio.sleep(0.1)

    # After exiting the context manager, the task should be cancelled
    assert task.cancelled()

@pytest.mark.asyncio
async def test_error_collection():
    """Test that the DeadlineCleanupManager collects errors."""
    async with DeadlineCleanupManager(timeout=1.0) as manager:
        manager.start_deadline()

        # Create a task that raises an error
        async def failing_task():
            raise ValueError("Test error")

        manager.create_task(failing_task())

        # Give the task time to complete
        await asyncio.sleep(0.1)

    # After exiting, the error should be collected
    assert len(manager.errors) == 1
    assert isinstance(manager.errors[0], ValueError)
```

### Integration Tests for VisionDataClient

Create a test file at `tests/core/test_vision_data_client_cleanup.py`:

```python
import asyncio
import pytest
import os
from unittest.mock import patch, MagicMock
from core.vision_data_client import VisionDataClient

@pytest.mark.asyncio
async def test_vision_client_cleanup():
    """Test that VisionDataClient cleans up resources properly."""
    # Mock the necessary components
    mock_session = MagicMock()
    mock_session.close = MagicMock(return_value=asyncio.Future())
    mock_session.close.return_value.set_result(None)

    mock_http_client = MagicMock()

    # Create a temporary file to test cleanup
    tmp_file = os.path.join('tmp', 'test_cleanup.txt')
    os.makedirs('tmp', exist_ok=True)
    with open(tmp_file, 'w') as f:
        f.write('test')

    # Initialize the client with mocked components
    client = VisionDataClient(endpoint='test')
    client._session = mock_session
    client._http_client = mock_http_client
    client._fetched_files = {tmp_file: 'test_data'}

    # Exit the context manager
    await client.__aexit__(None, None, None)

    # Verify cleanup occurred
    mock_session.close.assert_called_once()
    assert client._session is None
    assert client._http_client is None
    assert client._fetched_files is None
    assert not os.path.exists(tmp_file)

@pytest.mark.asyncio
async def test_vision_client_cleanup_with_errors():
    """Test that VisionDataClient handles cleanup errors properly."""
    # Mock the session to raise an error
    mock_session = MagicMock()
    mock_session.close = MagicMock(side_effect=Exception("Test error"))

    # Initialize the client with mocked components
    client = VisionDataClient(endpoint='test')
    client._session = mock_session

    # Exit the context manager
    await client.__aexit__(None, None, None)

    # Verify cleanup completed despite errors
    mock_session.close.assert_called_once()
    assert client._session is None
```

### Example Script Integration Tests

Create a test file at `tests/examples/test_data_retrieval_best_practices.py`:

```python
import asyncio
import pytest
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
from unittest.mock import patch, MagicMock

# Import the example script functions
sys.path.append(str(Path(__file__).parent.parent.parent))
from examples.data_retrieval_best_practices import example_fetch_recent_data, example_fetch_historical_data

@pytest.mark.asyncio
async def test_example_fetch_recent_data():
    """Test that the recent data example works with the new resource management."""
    # This test will run the actual function, but we'll mock the DataSourceManager
    # to avoid making real API calls
    with patch('examples.data_retrieval_best_practices.DataSourceManager') as mock_dsm_class:
        # Configure the mock to return a DataFrame with some test data
        mock_manager = MagicMock()
        mock_dsm_class.return_value.__aenter__.return_value = mock_manager

        # Set up mock data and stats
        mock_df = pd.DataFrame({
            'open_time': [datetime.now(timezone.utc)],
            'open': [100.0],
            'high': [101.0],
            'low': [99.0],
            'close': [100.5],
            'volume': [1000.0],
            'close_time': [datetime.now(timezone.utc) + timedelta(minutes=1)],
        })
        mock_manager.get_data.return_value = mock_df
        mock_manager.get_cache_stats.return_value = {'hits': 1, 'misses': 0, 'errors': 0}

        # Run the example function
        await example_fetch_recent_data()

        # Verify the example called the expected functions
        mock_dsm_class.assert_called_once()
        assert mock_manager.get_data.call_count >= 1
        assert mock_manager.get_cache_stats.call_count >= 1

@pytest.mark.asyncio
async def test_example_fetch_historical_data():
    """Test that the historical data example works with the new resource management."""
    # Similar pattern to the recent data test
    with patch('examples.data_retrieval_best_practices.DataSourceManager') as mock_dsm_class:
        mock_manager = MagicMock()
        mock_dsm_class.return_value.__aenter__.return_value = mock_manager

        # Set up mock data and stats
        mock_df = pd.DataFrame({
            'open_time': [datetime.now(timezone.utc) - timedelta(days=90)],
            'open': [100.0],
            'high': [101.0],
            'low': [99.0],
            'close': [100.5],
            'volume': [1000.0],
            'close_time': [datetime.now(timezone.utc) - timedelta(days=90) + timedelta(minutes=1)],
        })
        mock_manager.get_data.return_value = mock_df
        mock_manager.get_cache_stats.return_value = {'hits': 0, 'misses': 1, 'errors': 0}

        # Run the example function
        await example_fetch_historical_data()

        # Verify the example called the expected functions and cleanup was attempted
        mock_dsm_class.assert_called_once()
        assert mock_manager.get_data.call_count >= 1

        # Check if cleanup was attempted
        # This test verifies our compatibility with the example's explicit cleanup code
        if hasattr(mock_manager, 'vision_client'):
            mock_manager.vision_client.__aexit__.assert_called()
```

## Stress Testing

Create a stress test file at `tests/resource_cleanup/test_stress_cleanup.py`:

```python
import asyncio
import pytest
from utils.resource_management import DeadlineCleanupManager

@pytest.mark.asyncio
async def test_parallel_cleanup():
    """Test cleanup of many resources in parallel."""
    # Create a list to track task completion
    completed = []

    async def cleanup_task(task_id, delay):
        await asyncio.sleep(delay)
        completed.append(task_id)

    # Create many cleanup tasks with varying delays
    async with DeadlineCleanupManager(timeout=1.0) as manager:
        manager.start_deadline()

        # Create 100 tasks with varying delays
        for i in range(100):
            # Some tasks will complete, some will be cancelled due to timeout
            delay = i / 100  # 0.0 to 0.99 seconds
            manager.create_task(cleanup_task(i, delay))

    # Verify that tasks with short delays completed
    # and tasks with longer delays were cancelled
    assert len(completed) > 0
    assert len(completed) < 100  # Some should be cancelled by the deadline
```

## End-to-End Testing

Create an end-to-end test file at `tests/integration/test_data_source_manager_cleanup.py`:

```python
import asyncio
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
from core.data_source_manager import DataSourceManager, DataSource
from utils.market_constraints import MarketType, Interval

@pytest.mark.asyncio
async def test_data_source_manager_cleanup():
    """End-to-end test of the data source manager with Vision API cleanup."""
    # Create a temporary cache directory
    cache_dir = Path("./tmp/test_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Define time range for historical data to force Vision API use
    now = datetime.now(timezone.utc)
    end_time = now - timedelta(days=90)
    start_time = end_time - timedelta(hours=1)

    # Use the manager to get data (this will use Vision API internally)
    async with DataSourceManager(
        market_type=MarketType.SPOT,
        cache_dir=cache_dir,
        use_cache=True,
    ) as manager:
        # Force Vision API usage
        df = await manager.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.MINUTE_1,
            enforce_source=DataSource.VISION,
        )

        # Verify we got some data
        assert not df.empty, "Failed to retrieve data using Vision API"

    # At this point, cleanup should have occurred automatically
    # Wait a short time to allow any background tasks to complete
    await asyncio.sleep(0.5)

    # Clean up the test cache
    for file in cache_dir.glob("*"):
        file.unlink()
    cache_dir.rmdir()
```

## Conclusion

This implementation guide provides a focused approach to solving the specific hanging issue in `VisionDataClient.__aexit__` without introducing unnecessary complexity. By creating a minimal utility class and applying it strategically to the critical component, we can achieve robust resource cleanup while adhering to the principles of simplicity and effectiveness, all while maintaining compatibility with user-facing example scripts.
