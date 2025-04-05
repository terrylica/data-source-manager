#!/usr/bin/env python
"""
Enhanced conftest.py that incorporates best practices from:
- pytest-asyncio and pytest-xdist KeyError resolution
- Logging in parallel execution environments
"""


# Import our unified logging implementation
from tests.utils.unified_logging import (
    configure_root_logger_for_testing,
)


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

    # Configure root logger to ensure all log levels pass through
    configure_root_logger_for_testing()


# Note: We're now importing caplog_xdist_compatible and caplog_unified from
# tests/utils/unified_logging.py instead of defining them here.
# This ensures consistent behavior across all tests.
