#!/usr/bin/env python
"""
Unified logging utilities for tests that work seamlessly with pytest-xdist.

This module provides a robust logging abstraction that:
1. Works consistently in both sequential and parallel test execution
2. Is compatible with pytest-xdist without special configuration
3. Handles both synchronous and asynchronous tests
4. Provides a clean interface consistent with pytest's native caplog
5. Automatically cleans up resources after test execution
6. Properly captures all log levels with configurable filtering
"""

import logging
import pytest
from typing import List, Union, Optional, Any
from contextlib import contextmanager

# Use our custom logger from the main application


class LogCaptureHandler(logging.Handler):
    """A specialized handler that captures log records in a thread-safe manner.

    This handler collects log records in a list for later inspection while
    ensuring thread safety for parallel test execution.
    """

    def __init__(self, records_list: List[logging.LogRecord]):
        """Initialize with a list to store records.

        Args:
            records_list: A list that will store captured log records
        """
        super().__init__()
        self.records_list = records_list

    def emit(self, record: logging.LogRecord) -> None:
        """Add the log record to the collection.

        Args:
            record: The log record to capture
        """
        self.records_list.append(record)


class UnifiedLogCapture:
    """A unified log capture implementation that works in all test environments.

    This class provides a consistent interface for capturing logs during test
    execution that works with:
    - Regular pytest
    - pytest-xdist parallel execution
    - Synchronous and asynchronous tests
    - Multiple test worker processes

    It implements the core functionality expected from pytest's caplog fixture
    while ensuring compatibility with parallel test execution.
    """

    def __init__(self, initial_level: Union[str, int] = logging.DEBUG):
        """Initialize the log capture with empty records list and handlers.

        Args:
            initial_level: The initial logging level to set for capture
        """
        self.records: List[logging.LogRecord] = []
        self.handler: Optional[LogCaptureHandler] = None
        self._saved_root_level = None

        # Store the original root logger level
        root_logger = logging.getLogger()
        self._saved_root_level = root_logger.level

        # Create and attach a handler that will collect logs
        self.handler = LogCaptureHandler(self.records)
        self._set_handler_level(initial_level)

        # Add our handler to the root logger to capture all logs
        root_logger.addHandler(self.handler)

        # Also ensure root logger level is set to at least DEBUG
        # This is necessary to capture DEBUG logs
        if root_logger.level > logging.DEBUG:
            root_logger.setLevel(logging.DEBUG)

    def _set_handler_level(self, level: Union[str, int]) -> None:
        """Set the level on the handler, handling both string and int levels.

        Args:
            level: The logging level as either a string name or int constant
        """
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        self.handler.setLevel(level)

    def set_level(
        self, level: Union[str, int], logger_name: Optional[str] = None
    ) -> None:
        """Set the capture level with support for string level names.

        Args:
            level: The logging level to set (e.g., "DEBUG", "INFO", logging.DEBUG)
            logger_name: Optional logger name to set level on specific logger
        """
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)

        # Set level on our capture handler
        self.handler.setLevel(level)

        # If a specific logger is provided, set its level
        if logger_name is not None:
            logging.getLogger(logger_name).setLevel(level)
        else:
            # If setting DEBUG level, ensure root logger allows it to pass through
            if level <= logging.DEBUG:
                logging.getLogger().setLevel(logging.DEBUG)

    def clear(self) -> None:
        """Clear all captured records."""
        self.records.clear()

    @contextmanager
    def at_level(self, level: Union[str, int], logger_name: Optional[str] = None):
        """Temporarily change the logging level as a context manager.

        Args:
            level: The logging level to set for the duration of the context
            logger_name: Optional logger name to set level on specific logger

        Yields:
            The log capture object itself for method chaining
        """
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)

        old_level = self.handler.level
        old_logger_level = None
        old_root_level = None

        # Set levels for the duration of the context
        self.handler.setLevel(level)

        # If setting DEBUG level, ensure root logger allows it to pass through
        if level <= logging.DEBUG:
            root_logger = logging.getLogger()
            old_root_level = root_logger.level
            if old_root_level > logging.DEBUG:
                root_logger.setLevel(logging.DEBUG)

        if logger_name is not None:
            target_logger = logging.getLogger(logger_name)
            old_logger_level = target_logger.level
            target_logger.setLevel(level)

        try:
            yield self
        finally:
            # Restore original levels
            self.handler.setLevel(old_level)
            if logger_name is not None and old_logger_level is not None:
                logging.getLogger(logger_name).setLevel(old_logger_level)
            if old_root_level is not None:
                logging.getLogger().setLevel(old_root_level)

    def __enter__(self) -> "UnifiedLogCapture":
        """Context manager entry point.

        Returns:
            self: The log capture object
        """
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit that ensures handler cleanup.

        Args:
            *args: The standard context manager exit arguments
        """
        self.cleanup()

    def cleanup(self) -> None:
        """Remove handlers and perform cleanup.

        This method ensures all resources are properly released after testing.
        """
        if self.handler:
            root_logger = logging.getLogger()
            if self.handler in root_logger.handlers:
                root_logger.removeHandler(self.handler)
            self.handler = None

            # Restore the original root logger level
            if self._saved_root_level is not None:
                root_logger.setLevel(self._saved_root_level)


# Configure the root logger to allow all levels during test execution
def configure_root_logger_for_testing():
    """
    Configure the root logger to allow all levels during test execution.

    This function ensures that DEBUG logs will be captured by the root
    logger, which is necessary for proper log capture during testing.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Also ensure all non-root loggers can pass through log messages
    for name in logging.root.manager.loggerDict:
        logger = logging.getLogger(name)
        if logger.level == logging.NOTSET:
            continue  # Skip loggers that are using parent's level
        # Only lower the level if it's more restrictive than DEBUG
        if logger.level > logging.DEBUG:
            logger.setLevel(logging.DEBUG)


# Define the unified caplog fixture
@pytest.fixture
def caplog_unified():
    """A pytest fixture that provides unified log capturing for tests.

    This fixture works in both sequential and parallel test execution environments
    and properly handles asyncio tests through pytest-xdist.

    Yields:
        UnifiedLogCapture: The log capture object for use in tests
    """
    # Ensure root logger is configured properly
    configure_root_logger_for_testing()

    capture = UnifiedLogCapture()
    try:
        yield capture
    finally:
        capture.cleanup()


# Also create a compatibility fixture with the same name used in tests
@pytest.fixture
def caplog_xdist_compatible():
    """A pytest fixture for backward compatibility with existing tests.

    This fixture has the same name as the original but uses our improved implementation.

    Yields:
        UnifiedLogCapture: The log capture object for use in tests
    """
    # Ensure root logger is configured properly
    configure_root_logger_for_testing()

    capture = UnifiedLogCapture()
    try:
        yield capture
    finally:
        capture.cleanup()


# Export a simple function for logging verification
def assert_log_contains(
    caplog: UnifiedLogCapture, expected_message: str, level: Optional[int] = None
) -> bool:
    """Assert that a specific log message was captured.

    Args:
        caplog: The log capture object from a test
        expected_message: The message text to look for
        level: Optional log level to filter by

    Returns:
        bool: True if the message was found, else AssertionError is raised

    Raises:
        AssertionError: If the expected message wasn't found
    """
    if level is not None:
        filtered_records = [r for r in caplog.records if r.levelno == level]
        messages = [r.message for r in filtered_records]
        found = any(expected_message in msg for msg in messages)
        if not found:
            level_name = logging.getLevelName(level)
            raise AssertionError(
                f"Log message '{expected_message}' not found in {level_name} records. "
                f"Captured {level_name} messages: {messages}"
            )
    else:
        messages = [r.message for r in caplog.records]
        found = any(expected_message in msg for msg in messages)
        if not found:
            raise AssertionError(
                f"Log message '{expected_message}' not found in any records. "
                f"Captured messages: {messages}"
            )

    return True
