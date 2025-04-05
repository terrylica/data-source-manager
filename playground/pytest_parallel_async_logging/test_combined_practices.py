#!/usr/bin/env python
"""
Integration test demonstrating combined best practices from:
- pytest-asyncio and pytest-xdist integration
- Logging with unified caplog fixtures in parallel execution

This file shows how to properly handle both async tests and logging
in a parallel execution environment using the unified logging abstraction.
"""

import asyncio
import logging
import pytest
from utils.logger_setup import logger
from tests.utils.unified_logging import assert_log_contains

# Avoid using pytestmark for asyncio as it can cause issues with synchronous tests
# Each async test will be explicitly marked instead


@pytest.mark.asyncio
async def test_async_logging_with_unified_caplog(caplog_unified):
    """Test basic async operation with the unified caplog fixture."""
    # Set the capture level to DEBUG to see all logs
    caplog_unified.set_level(logging.DEBUG)

    # Log some messages
    logger.debug("Async debug message")
    logger.info("Starting async operation")

    # Perform async operation
    await asyncio.sleep(0.1)
    logger.info("Async operation completed")

    # Verify logs were captured properly using the helper assertion function
    assert_log_contains(caplog_unified, "Async debug message", logging.DEBUG)
    assert_log_contains(caplog_unified, "Starting async operation", logging.INFO)
    assert_log_contains(caplog_unified, "Async operation completed", logging.INFO)


@pytest.mark.asyncio
async def test_async_concurrent_logging_with_unified(caplog_unified):
    """Test concurrent async operations with the unified caplog fixture."""
    # Clear any existing logs and set log level
    caplog_unified.clear()
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

    # Filter logs to only include those from our module (avoiding asyncio logs)
    our_module_logs = [
        r
        for r in caplog_unified.records
        if r.name == "playground.pytest_parallel_async_logging.test_combined_practices"
    ]

    # Verify all task logs were captured
    task_start_logs = [r for r in our_module_logs if "started" in r.message]
    task_complete_logs = [r for r in our_module_logs if "completed" in r.message]

    assert len(task_start_logs) == 3, "Not all task start logs were captured"
    assert len(task_complete_logs) == 3, "Not all task completion logs were captured"


# Mark specifically to run serially if needed
@pytest.mark.serial
@pytest.mark.asyncio
async def test_logging_intensive_serial(caplog_unified):
    """Test with intensive logging that should run serially."""
    # Set capture level to DEBUG
    caplog_unified.set_level(logging.DEBUG)

    # Generate a large number of log messages
    for i in range(10):
        logger.debug(f"Detailed debug log {i}")
        if i % 2 == 0:
            logger.info(f"Progress update: {i/10:.0%} complete")

    # Simulate work
    await asyncio.sleep(0.2)
    logger.info("Intensive logging test completed")

    # Verify logs were captured
    debug_logs = [r for r in caplog_unified.records if r.levelno == logging.DEBUG]
    info_logs = [r for r in caplog_unified.records if r.levelno == logging.INFO]

    assert len(debug_logs) >= 10, "Not all debug logs were captured"
    assert len(info_logs) >= 6, "Not all info logs were captured"
    assert_log_contains(
        caplog_unified, "Intensive logging test completed", logging.INFO
    )


# Regular synchronous test with logging
def test_sync_with_unified_logging(caplog_unified):
    """Regular synchronous test with the unified caplog fixture."""
    # Set capture level to INFO
    caplog_unified.set_level(logging.INFO)

    # Log some messages
    logger.info("This is a sync test")
    logger.warning("This is a warning")

    # Verify logs were captured
    assert_log_contains(caplog_unified, "This is a sync test", logging.INFO)
    assert_log_contains(caplog_unified, "This is a warning", logging.WARNING)


# Demonstrate the context manager for temporary log level changes
def test_context_manager_with_unified_logging(caplog_unified):
    """Test the at_level context manager for temporary log level changes."""
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

    # Verify the capture pattern
    info_records = [r for r in caplog_unified.records if r.levelno == logging.INFO]
    error_records = [r for r in caplog_unified.records if r.levelno == logging.ERROR]

    # Only the info log from within the context should be captured
    assert len(info_records) == 1, "Unexpected number of INFO records"
    assert "inside context" in info_records[0].message, "Wrong INFO message captured"

    # All error logs should be captured
    assert len(error_records) == 3, "Not all ERROR records were captured"


# For backward compatibility demonstration
def test_backward_compatibility_with_xdist_compatible(caplog_xdist_compatible):
    """Demonstrate backward compatibility with caplog_xdist_compatible fixture."""
    # Set capture level
    caplog_xdist_compatible.set_level(logging.INFO)

    # Generate logs
    logger.info("Using legacy caplog_xdist_compatible fixture")
    logger.warning("This should also be captured")

    # Verify logs are captured
    assert len(caplog_xdist_compatible.records) >= 2, "Logs weren't captured"

    # Check specific messages
    messages = [r.message for r in caplog_xdist_compatible.records]
    assert any("legacy caplog_xdist_compatible" in msg for msg in messages)
    assert any("This should also be captured" in msg for msg in messages)
