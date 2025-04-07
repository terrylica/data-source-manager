#!/usr/bin/env python
"""Task manager for data retrieval with structured concurrency.

This module provides a DataTaskManager class that uses Python 3.12's asyncio.TaskGroup
for structured concurrency, ensuring proper resource cleanup and error handling
for concurrent data retrieval operations.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Callable, Awaitable, TypeVar
import gc
from pathlib import Path
import pandas as pd
import functools
import inspect

from utils.logger_setup import logger
from utils.market_constraints import Interval, MarketType
from core.data_source_manager import DataSourceManager, DataSource
from utils.async_cleanup import cleanup_all_force_timeout_tasks
from utils.config import create_empty_dataframe

# Type variables for the decorator
T = TypeVar("T")
R = TypeVar("R")


def with_task_manager(func):
    """Decorator to automatically use DataTaskManager with a function.

    This decorator will create a DataTaskManager instance and pass it to the
    decorated coroutine function as the first argument after self (if present).

    Args:
        func: The coroutine function to decorate

    Returns:
        Wrapped function
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        """Wrapper function that injects a DataTaskManager instance."""
        # Determine if we're in a method (has self) or a regular function
        is_method = (
            inspect.getfullargspec(func).args
            and inspect.getfullargspec(func).args[0] == "self"
        )
        task_manager = DataTaskManager()

        try:
            # For methods, task_manager is the second arg after self
            if is_method:
                result = await func(args[0], task_manager, *args[1:], **kwargs)
            else:
                # For regular functions, task_manager is the first arg
                result = await func(task_manager, *args, **kwargs)
            return result
        except Exception as e:
            # Handle individual exceptions
            logger.error(f"Error in decorated function {func.__name__}: {e}")
            raise
        finally:
            # Always ensure cleanup is performed
            await cleanup_all_force_timeout_tasks()
            # Force garbage collection to help clean up resources
            gc.collect()

    return wrapper


class DataTaskManager:
    """Task manager for data retrieval with structured concurrency.

    This class provides a clean interface for fetching multiple data sets concurrently
    while ensuring proper resource cleanup even in error conditions.

    Example:
        ```python
        # Create task manager
        task_manager = DataTaskManager(market_type=MarketType.SPOT)

        # Define requests
        requests = [
            {"symbol": "BTCUSDT", "interval": Interval.MINUTE_1, "start_time": start, "end_time": end},
            {"symbol": "ETHUSDT", "interval": Interval.MINUTE_1, "start_time": start, "end_time": end},
        ]

        # Fetch multiple datasets concurrently
        results = await task_manager.fetch_multiple(requests)

        # Access results by key
        btc_data = results["BTCUSDT_1m"]
        eth_data = results["ETHUSDT_1m"]
        ```
    """

    def __init__(
        self,
        market_type: MarketType = MarketType.SPOT,
        cache_dir: Optional[Path] = None,
        use_httpx: bool = True,
        **config,
    ):
        """Initialize the task manager.

        Args:
            market_type: Default market type for data retrieval
            cache_dir: Directory for caching data (default: ./cache)
            use_httpx: DEPRECATED - Always using curl_cffi instead for stability
            **config: Additional configuration parameters for DataSourceManager
        """
        self.market_type = market_type

        # Handle cache directory
        if cache_dir is None:
            cache_dir = Path("./cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir

        # Always set use_httpx to False to ensure curl_cffi is used
        if use_httpx:
            logger.warning(
                "The use_httpx parameter is deprecated - using curl_cffi for stability"
            )
        self.use_httpx = False
        self.config = config

    @asynccontextmanager
    async def session(self):
        """Create a managed session with proper cleanup.

        This context manager provides a DataSourceManager instance and a TaskGroup
        for concurrent operations with guaranteed resource cleanup.

        Yields:
            Tuple of (TaskGroup, DataSourceManager)
        """
        manager = None
        try:
            # Create and enter DataSourceManager context
            manager = DataSourceManager(
                market_type=self.market_type,
                cache_dir=self.cache_dir,
                use_cache=True,
                use_httpx=self.use_httpx,
                **self.config,
            )

            try:
                async with manager:
                    # Create TaskGroup for structured concurrency (Python 3.11+)
                    try:
                        # Use standard try/except around TaskGroup to ensure compatibility
                        async with asyncio.TaskGroup() as tg:
                            yield tg, manager
                    except ExceptionGroup as eg:
                        # Handle the exception group in a Python 3.11+ compatible way
                        logger.error(f"Error in TaskGroup: {eg}")
                        # Reraise as standard exception for backward compatibility
                        raise Exception(f"TaskGroup error: {eg}")
                    except Exception as e:
                        # Catch other exceptions from TaskGroup
                        logger.error(f"Error in TaskGroup: {e}")
                        raise
            except Exception as e:
                logger.error(f"Error in manager context: {e}")
                raise
        except Exception as e:
            logger.error(f"Error in task manager session: {e}")
            raise
        finally:
            # Ensure cleanup of any lingering resources
            if manager is not None:
                # Break potential circular references
                manager = None

            # Force cleanup of any hanging tasks
            try:
                await cleanup_all_force_timeout_tasks()
            except Exception as e:
                logger.error(f"Error during force timeout tasks cleanup: {e}")

            try:
                # Force garbage collection
                gc.collect()
            except Exception as e:
                logger.error(f"Error during garbage collection: {e}")

            logger.debug("Task manager session cleanup completed")

    async def fetch_multiple(
        self, requests: List[Dict[str, Any]]
    ) -> Dict[str, pd.DataFrame]:
        """Fetch multiple datasets concurrently with proper error handling.

        Args:
            requests: List of dictionaries containing request parameters:
                - symbol: Trading symbol (required)
                - start_time: Start time (required)
                - end_time: End time (required)
                - interval: Time interval (default: Interval.MINUTE_1)
                - market_type: Override default market type
                - enforce_source: Force specific data source
                - key: Custom key for the result (default: "{symbol}_{interval.value}")

        Returns:
            Dictionary mapping request keys to DataFrames
        """
        results = {}

        try:
            async with self.session() as (tg, manager):
                # Create tasks for each request
                for req in requests:
                    # Validate required parameters
                    if not all(k in req for k in ["symbol", "start_time", "end_time"]):
                        logger.warning(
                            f"Skipping invalid request missing required fields: {req}"
                        )
                        continue

                    # Generate default key if not provided
                    interval = req.get("interval", Interval.MINUTE_1)
                    interval_str = (
                        interval.value if hasattr(interval, "value") else str(interval)
                    )
                    key = req.get("key", f"{req['symbol']}_{interval_str}")

                    # Create a task with proper capture of key
                    tg.create_task(
                        self._fetch_with_error_handling(manager, req, key, results)
                    )
        except Exception as e:
            # Standard exception handling that works in all Python versions
            logger.error(f"Error in task manager session: {e}")
            # Ensure we have a valid results dictionary to return even on error
            if not results:
                results = {}
        finally:
            # Ensure cleanup happens regardless of how we exit
            await cleanup_all_force_timeout_tasks()
            gc.collect()

        return results

    async def _fetch_with_error_handling(
        self,
        manager: DataSourceManager,
        req: Dict[str, Any],
        key: str,
        results: Dict[str, pd.DataFrame],
    ) -> None:
        """Fetch single dataset with error handling.

        Args:
            manager: DataSourceManager instance
            req: Request parameters
            key: Result key
            results: Dictionary to store the result
        """
        try:
            # Use market_type from request if specified, otherwise use manager's default
            market_type = req.get("market_type", manager.market_type)

            # Only override manager's market_type if necessary
            if market_type != manager.market_type:
                # This is a rare case where we need a separate manager for a different market type
                async with DataSourceManager(
                    market_type=market_type,
                    cache_dir=self.cache_dir,
                    use_cache=True,
                    use_httpx=self.use_httpx,
                    **self.config,
                ) as specific_manager:
                    results[key] = await specific_manager.get_data(
                        symbol=req["symbol"],
                        start_time=req["start_time"],
                        end_time=req["end_time"],
                        interval=req.get("interval", Interval.MINUTE_1),
                        enforce_source=req.get("enforce_source", DataSource.AUTO),
                    )
            else:
                # Normal case - use the shared manager
                results[key] = await manager.get_data(
                    symbol=req["symbol"],
                    start_time=req["start_time"],
                    end_time=req["end_time"],
                    interval=req.get("interval", Interval.MINUTE_1),
                    enforce_source=req.get("enforce_source", DataSource.AUTO),
                )

            logger.debug(f"Successfully fetched data for {key}")
        except Exception as e:
            logger.error(f"Error fetching {key}: {e}")
            # Store empty DataFrame with correct structure instead of failing
            results[key] = create_empty_dataframe()

    async def fetch_batch(
        self,
        symbols: List[str],
        start_time: datetime,
        end_time: datetime,
        interval: Interval = Interval.MINUTE_1,
        market_type: Optional[MarketType] = None,
        enforce_source: DataSource = DataSource.AUTO,
    ) -> Dict[str, pd.DataFrame]:
        """Convenience method to fetch data for multiple symbols with same parameters.

        Args:
            symbols: List of trading symbols
            start_time: Start time for all requests
            end_time: End time for all requests
            interval: Time interval (default: Interval.MINUTE_1)
            market_type: Override default market type
            enforce_source: Force specific data source

        Returns:
            Dictionary mapping symbol keys to DataFrames
        """
        # Build requests list
        requests = []
        for symbol in symbols:
            requests.append(
                {
                    "symbol": symbol,
                    "start_time": start_time,
                    "end_time": end_time,
                    "interval": interval,
                    "market_type": market_type or self.market_type,
                    "enforce_source": enforce_source,
                    "key": f"{symbol}_{interval.value}",
                }
            )

        return await self.fetch_multiple(requests)


async def ensure_cleanup(func=None, *, force_gc=True):
    """Utility function to ensure proper cleanup after an async operation.

    This can be used as:
    1. A decorator: @ensure_cleanup
    2. A parameterized decorator: @ensure_cleanup(force_gc=True)
    3. A context manager: async with ensure_cleanup()
    4. A direct awaitable: await ensure_cleanup()

    Examples:
        As a simple decorator:
        ```python
        @ensure_cleanup
        async def my_function():
            # Your code here
            pass
        ```

        As a parameterized decorator:
        ```python
        @ensure_cleanup(force_gc=True)
        async def my_function():
            # Your code here
            pass
        ```

        As a context manager:
        ```python
        async with ensure_cleanup():
            # Your code here
            pass
        ```

        As a direct awaitable:
        ```python
        # Just perform cleanup
        await ensure_cleanup()
        ```
    """
    # When called directly without arguments and not as a decorator
    if func is None and not hasattr(ensure_cleanup, "_is_recalling"):
        # This is a direct call: await ensure_cleanup()
        # Create a dummy context manager and use it
        temp_cm = CleanupContextManager(force_gc)
        try:
            # Return the context manager's __aenter__ result
            return await temp_cm.__aenter__()
        finally:
            # Ensure cleanup happens
            await temp_cm.__aexit__(None, None, None)

    # Create a context manager class for reuse
    class CleanupContextManager:
        def __init__(self, force_gc_flag=force_gc):
            self.force_gc = force_gc_flag

        async def __aenter__(self):
            return None

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            try:
                # Always try to clean up timeout tasks
                await cleanup_all_force_timeout_tasks()
            except Exception as e:
                # Just log errors, don't propagate them
                logger.error(f"Error during cleanup_all_force_timeout_tasks: {e}")

            if self.force_gc:
                try:
                    # Try to force garbage collection
                    gc.collect()
                except Exception as e:
                    # Just log errors, don't propagate them
                    logger.error(f"Error during force gc: {e}")

            return False  # Don't suppress exceptions

    # Create decorator function for reuse
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                # Execute the decorated function
                return await fn(*args, **kwargs)
            finally:
                # Ensure cleanup happens
                cm = CleanupContextManager(force_gc)
                await cm.__aexit__(None, None, None)

        return wrapper

    # When used directly as a decorator: @ensure_cleanup
    if func is not None:
        return decorator(func)

    # When used as a parameterized decorator: @ensure_cleanup(force_gc=True)
    # Or when used as a context manager: async with ensure_cleanup()
    return CleanupContextManager()
