#!/usr/bin/env python
"""
Enhanced conftest.py that incorporates best practices from:
- pytest-asyncio and pytest-xdist KeyError resolution
- Logging in parallel execution environments
"""

import logging
import pytest
from utils.logger_setup import logger


# Set global asyncio configuration via pytest configuration
# This is the recommended approach instead of defining a custom event_loop fixture
def pytest_configure(config):
    """Configure pytest with asyncio settings and custom markers."""
    # Add the serial marker
    config.addinivalue_line(
        "markers", "serial: mark test to run serially (non-parallel)"
    )

    # Set asyncio_default_fixture_loop_scope to function scope for all tests
    # This is critical for avoiding KeyError issues with pytest-xdist
    config.option.asyncio_default_fixture_loop_scope = "function"


@pytest.fixture
def caplog_xdist_compatible():
    """
    A simplified caplog fixture compatible with pytest-xdist.

    Instead of trying to use the standard caplog fixture which has issues with
    pytest-xdist, this provides a minimal implementation that collects logs
    during test execution.
    """

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

    # Create and return the capture object
    capture = SimpleLogCapture()
    try:
        yield capture
    finally:
        # Clean up the handler
        if capture.handler:
            logging.getLogger().removeHandler(capture.handler)
