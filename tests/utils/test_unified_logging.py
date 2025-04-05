#!/usr/bin/env python
"""
Test the unified logging abstraction with both sync and async tests.

This file demonstrates:
1. Using the unified caplog fixture with synchronous tests
2. Using the unified caplog fixture with asynchronous tests
3. Testing different log levels and capture behaviors
4. Using the at_level context manager for temporary level changes
5. Using helper assertion functions
"""

import asyncio
import logging
import pytest
from utils.logger_setup import logger
from tests.utils.unified_logging import assert_log_contains, UnifiedLogCapture


def test_basic_logging_unified(caplog_unified):
    """Test basic logging with the unified caplog fixture."""
    # Set the capture level to DEBUG to see all logs
    caplog_unified.set_level(logging.DEBUG)

    # Generate some log messages at different levels
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Print out caplog records for debugging
    print("\nCAPLOG RECORDS (UNIFIED):")
    for i, record in enumerate(caplog_unified.records):
        print(f"Record {i}: {record.levelname} - {record.message}")

    # Verify that messages are captured
    assert len(caplog_unified.records) >= 4, "Not all log records were captured!"

    # Use the helper function for assertions
    assert_log_contains(caplog_unified, "This is a debug message", logging.DEBUG)
    assert_log_contains(caplog_unified, "This is an info message", logging.INFO)
    assert_log_contains(caplog_unified, "This is a warning message", logging.WARNING)
    assert_log_contains(caplog_unified, "This is an error message", logging.ERROR)


def test_log_level_filtering_unified(caplog_unified):
    """Test log level filtering with the unified caplog fixture."""
    # Set the capture level to WARNING to filter out DEBUG and INFO
    caplog_unified.set_level(logging.WARNING)

    # Generate messages at different levels
    logger.debug("This debug message should be filtered out")
    logger.info("This info message should be filtered out")
    logger.warning("This warning message should be captured")
    logger.error("This error message should be captured")

    # Print out the captured records
    print("\nCAPLOG RECORDS (WARNING+ ONLY):")
    for record in caplog_unified.records:
        print(f"{record.levelname} - {record.message}")

    # Verify that only WARNING and ERROR messages were captured
    debug_records = [r for r in caplog_unified.records if r.levelno == logging.DEBUG]
    info_records = [r for r in caplog_unified.records if r.levelno == logging.INFO]
    warning_records = [
        r for r in caplog_unified.records if r.levelno == logging.WARNING
    ]
    error_records = [r for r in caplog_unified.records if r.levelno == logging.ERROR]

    assert len(debug_records) == 0, "Debug records were unexpectedly captured"
    assert len(info_records) == 0, "Info records were unexpectedly captured"
    assert len(warning_records) == 1, "Warning record was not captured"
    assert len(error_records) == 1, "Error record was not captured"


def test_context_manager_level_unified(caplog_unified):
    """Test the at_level context manager for temporary level changes."""
    # Set base level to ERROR (high threshold)
    caplog_unified.set_level(logging.ERROR)

    # Baseline - only ERROR should be captured
    logger.info("Info message outside context - should be filtered")
    logger.error("Error message outside context - should be captured")

    # Temporarily lower threshold to INFO within context
    with caplog_unified.at_level(logging.INFO):
        logger.info("Info message inside context - should be captured")
        logger.debug("Debug message inside context - should be filtered")
        logger.error("Error message inside context - should be captured")

    # After context, back to ERROR threshold
    logger.info("Another info message outside context - should be filtered")
    logger.error("Another error message outside context - should be captured")

    # Print records for visualization
    print("\nCAPLOG RECORDS (CONTEXT MANAGER):")
    for record in caplog_unified.records:
        print(f"{record.levelname} - {record.message}")

    # Verify the capture pattern
    info_records = [r for r in caplog_unified.records if r.levelno == logging.INFO]
    error_records = [r for r in caplog_unified.records if r.levelno == logging.ERROR]

    # Only the info log from within the context should be captured
    assert len(info_records) == 1, "Unexpected number of INFO records"
    assert "inside context" in info_records[0].message, "Wrong INFO message captured"

    # All error logs should be captured
    assert len(error_records) == 3, "Not all ERROR records were captured"


def test_clear_functionality_unified(caplog_unified):
    """Test the clear method to reset captured logs."""
    caplog_unified.set_level(logging.INFO)

    # Generate some initial logs
    logger.info("First batch - message 1")
    logger.info("First batch - message 2")

    # Verify they were captured
    assert len(caplog_unified.records) == 2, "Initial logs not captured"

    # Clear the logs
    caplog_unified.clear()

    # Verify they were cleared
    assert len(caplog_unified.records) == 0, "Logs weren't cleared"

    # Generate new logs
    logger.info("Second batch - message 1")
    logger.warning("Second batch - message 2")

    # Verify only the new logs are present
    assert len(caplog_unified.records) == 2, "New logs not captured correctly"
    messages = [r.message for r in caplog_unified.records]
    assert all("Second batch" in msg for msg in messages), "Old logs are still present"


@pytest.mark.asyncio
async def test_async_logging_unified(caplog_unified):
    """Test logging capture in an asynchronous test."""
    caplog_unified.set_level(logging.DEBUG)

    # Log before async operation
    logger.info("Starting async operation")

    # Perform async operation with logging
    await asyncio.sleep(0.1)
    logger.debug("Async operation in progress")

    # Another async operation
    await asyncio.sleep(0.1)
    logger.info("Async operation completed")

    # Verify logs were captured properly
    assert_log_contains(caplog_unified, "Starting async operation", logging.INFO)
    assert_log_contains(caplog_unified, "Async operation in progress", logging.DEBUG)
    assert_log_contains(caplog_unified, "Async operation completed", logging.INFO)


@pytest.mark.asyncio
async def test_async_concurrent_logging_unified(caplog_unified):
    """Test logging capture with concurrent async tasks."""
    # Clear any existing logs
    caplog_unified.clear()

    # Set capture level to INFO
    caplog_unified.set_level(logging.INFO)

    async def task_with_logging(task_id):
        """Async task that produces logs."""
        logger.info(f"Task {task_id} started")
        await asyncio.sleep(0.1)
        logger.info(f"Task {task_id} completed")
        return task_id

    # Run multiple concurrent tasks
    tasks = [task_with_logging(i) for i in range(3)]
    results = await asyncio.gather(*tasks)

    # Verify all tasks completed
    assert results == [0, 1, 2], "Async tasks did not complete correctly"

    # Filter logs to only include those from our module
    # This avoids counting asyncio infrastructure logs
    our_module_logs = [
        r
        for r in caplog_unified.records
        if r.name == "tests.utils.test_unified_logging"
    ]

    # Print the filtered logs for debugging
    print("\nFILTERED LOGS FROM OUR MODULE:")
    for record in our_module_logs:
        print(f"{record.levelname} - {record.message}")

    # There should be 6 messages from our module (start + complete for each task)
    assert (
        len(our_module_logs) == 6
    ), f"Expected 6 test module log messages, got {len(our_module_logs)}"

    # Check for specific message patterns
    task_start_logs = [r for r in our_module_logs if "started" in r.message]
    task_complete_logs = [r for r in our_module_logs if "completed" in r.message]

    assert len(task_start_logs) == 3, "Not all task start logs were captured"
    assert len(task_complete_logs) == 3, "Not all task completion logs were captured"


@pytest.mark.asyncio
async def test_compatibility_with_standard_caplog(caplog):
    """Test that our unified implementation works with the standard fixture name."""
    # This test uses the enhanced 'caplog' fixture which should use our
    # UnifiedLogCapture implementation when running with pytest-xdist

    caplog.set_level(logging.INFO)

    # Generate logs in an async context
    logger.info("Using standard caplog fixture name")
    await asyncio.sleep(0.1)
    logger.warning("This should still be captured")

    # Verify capture works
    assert len(caplog.records) >= 2, "Logs weren't captured with standard fixture"

    # If this is our implementation, it will have these properties
    if isinstance(caplog, UnifiedLogCapture):
        print("\nUsing UnifiedLogCapture implementation for caplog")
    else:
        print("\nUsing standard pytest implementation for caplog")

    # Either way, these assertions should work
    messages = [r.message for r in caplog.records]
    assert any("standard caplog fixture name" in msg for msg in messages)
    assert any("This should still be captured" in msg for msg in messages)


@pytest.mark.asyncio
async def test_async_logging_with_unified_caplog(caplog_unified):
    """Test logging in an asynchronous context with unified caplog."""
    # Set the capture level to DEBUG
    caplog_unified.set_level(logging.DEBUG)

    # Generate logs before, during, and after async operations
    logger.info("Starting async operation")

    # Log during async operation
    await asyncio.sleep(0.1)
    logger.debug("Async operation in progress")

    # Log after async operation
    logger.info("Async operation completed")

    # Print captured logs for debugging
    print("\nCAPLOG RECORDS (ASYNC):")
    for i, record in enumerate(caplog_unified.records):
        print(f"Record {i}: {record.levelname} - {record.message}")

    # Verify logs were captured in the correct order
    assert len(caplog_unified.records) >= 3, "Not all async log records were captured!"

    # Use helper function for assertions
    assert_log_contains(caplog_unified, "Starting async operation", logging.INFO)
    assert_log_contains(caplog_unified, "Async operation in progress", logging.DEBUG)
    assert_log_contains(caplog_unified, "Async operation completed", logging.INFO)
