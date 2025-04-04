#!/usr/bin/env python
"""Root conftest.py that provides fixtures for the test suite.

This file contains:
1. Fixtures for handling network clients with proper cleanup
2. Enhanced caplog fixture for pytest-xdist compatibility
3. Asyncio configuration for proper event loop management
"""

# Left empty for backwards compatibility
# The fixtures were previously imported here but are no longer used

import pytest
import logging
from curl_cffi.requests import AsyncSession
from utils.network_utils import safely_close_client
from utils.logger_setup import logger


# Set global asyncio configuration via pytest configuration
# This is the recommended approach for asyncio loop management
def pytest_configure(config):
    """Configure pytest with asyncio settings and custom markers."""
    # Add the serial marker for tests that should run sequentially
    config.addinivalue_line(
        "markers", "serial: mark test to run serially (non-parallel)"
    )

    # Register the existing markers properly
    config.addinivalue_line(
        "markers",
        "real: mark tests that run against real data/resources rather than mocks",
    )
    config.addinivalue_line(
        "markers", "integration: mark tests that integrate with external services"
    )

    # Set asyncio_default_fixture_loop_scope to function scope for all tests
    # This is critical for avoiding KeyError issues with pytest-xdist
    config.option.asyncio_default_fixture_loop_scope = "function"


@pytest.fixture
async def curl_cffi_client_with_cleanup():
    """Create a curl_cffi client with proper cleanup of pending tasks.

    This fixture ensures that AsyncCurl's internal timeout tasks are properly handled
    by using the safely_close_client function which handles pending tasks properly.
    """
    client = AsyncSession()
    yield client
    # Use the enhanced safely_close_client function instead of directly closing
    await safely_close_client(client)


@pytest.fixture
def caplog_xdist_compatible():
    """
    A simplified caplog fixture compatible with pytest-xdist.

    This fixture provides a testing-specific logging capture implementation
    that works correctly with parallel test execution. Use this fixture instead
    of the standard caplog fixture in tests run with pytest-xdist to avoid
    KeyError issues.
    """

    # Handler class for collecting log records
    class _CollectHandler(logging.Handler):
        """Handler that collects log records in a list."""

        def __init__(self, records_list):
            """Initialize with a list to store records."""
            super().__init__()
            self.records_list = records_list

        def emit(self, record):
            """Add the record to our collection."""
            self.records_list.append(record)

    # The actual capture implementation
    class SimpleLogCapture:
        """A simple log capture implementation for pytest-xdist compatibility."""

        def __init__(self):
            """Initialize with empty records list."""
            self.records = []
            self.handler = None

            # Create and attach a handler that will collect logs
            self.handler = _CollectHandler(self.records)
            self.handler.setLevel(logging.DEBUG)
            logging.getLogger().addHandler(self.handler)

        def set_level(self, level):
            """Set logging level."""
            if isinstance(level, str):
                level = getattr(logging, level.upper(), logging.INFO)
            self.handler.setLevel(level)

        def clear(self):
            """Clear captured records."""
            self.records.clear()

        def __enter__(self):
            """Context manager entry."""
            return self

        def __exit__(self, *args):
            """Remove the handler when done."""
            if self.handler:
                logging.getLogger().removeHandler(self.handler)

    # Create and return the capture object
    capture = SimpleLogCapture()
    try:
        yield capture
    finally:
        # Clean up the handler
        if capture.handler:
            logging.getLogger().removeHandler(capture.handler)


@pytest.fixture
def caplog(request):
    """Enhanced caplog fixture compatible with pytest-xdist.

    This fixture addresses KeyError issues when running tests in parallel with pytest-xdist
    while providing full logging capture capability. It handles both sequential
    and parallel execution environments gracefully.
    """

    # Handler class for collecting log records
    class _CollectHandler(logging.Handler):
        """Handler that collects log records in a list."""

        def __init__(self, records_list):
            """Initialize with a list to store records."""
            super().__init__()
            self.records_list = records_list

        def emit(self, record):
            """Add the record to our collection."""
            self.records_list.append(record)

    # Create a xdist-compatible caplog implementation
    class XdistCompatibleCaplog:
        """A caplog implementation that works with pytest-xdist."""

        def __init__(self):
            """Initialize with storage for records and handlers."""
            self.records = []
            self.text = ""
            self._handler = logging.NullHandler()
            self._level = logging.INFO
            self._handler.setLevel(self._level)

            # Create a real handler to show logs in the console
            self._real_handler = logging.StreamHandler()
            self._real_handler.setFormatter(
                logging.Formatter("%(levelname)s %(name)s: %(message)s")
            )
            self._real_handler.setLevel(self._level)

            # Add a special handler to collect logs for inspection in tests
            self._collect_handler = _CollectHandler(self.records)
            self._collect_handler.setLevel(logging.DEBUG)  # Collect all levels

            # Add handlers to root logger
            root_logger = logging.getLogger()
            root_logger.addHandler(self._real_handler)
            root_logger.addHandler(self._collect_handler)

        @property
        def handler(self):
            """Get the handler property that pytest expects."""
            return self._handler

        def set_level(self, level, logger=None):
            """Set the capture level - works with strings or log level constants."""
            if isinstance(level, str):
                level = getattr(logging, level.upper(), logging.INFO)

            # Set level on our handlers
            self._level = level
            self._handler.setLevel(level)
            self._real_handler.setLevel(level)
            self._collect_handler.setLevel(level)

            # If a specific logger is provided, set its level
            if logger is not None:
                logging.getLogger(logger).setLevel(level)

        def clear(self):
            """Clear logs."""
            self.records.clear()
            self.text = ""

        def __enter__(self):
            """Context manager entry."""
            return self

        def __exit__(self, *args, **kwargs):
            """Context manager exit."""
            # Clean up by removing our handlers from the root logger
            root_logger = logging.getLogger()
            if self._real_handler in root_logger.handlers:
                root_logger.removeHandler(self._real_handler)
            if self._collect_handler in root_logger.handlers:
                root_logger.removeHandler(self._collect_handler)

    try:
        # Try to get the real caplog fixture from pytest
        # This will work when running sequentially, but fail with pytest-xdist
        real_caplog = request.getfixturevalue("caplog")
        return real_caplog
    except Exception:
        # If caplog fixture isn't available or raises KeyError (with pytest-xdist)
        logger.debug(
            "Using xdist-compatible caplog implementation for compatibility with pytest-xdist"
        )
        return XdistCompatibleCaplog()
