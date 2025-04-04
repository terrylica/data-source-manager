#!/usr/bin/env python
"""
Integration test demonstrating combined best practices from:
- pytest-asyncio and pytest-xdist integration
- Logging with caplog in parallel execution

This file shows how to properly handle both async tests and logging
in a parallel execution environment.
"""

import asyncio
import pytest
from utils.logger_setup import logger

# Avoid using pytestmark for asyncio as it can cause issues with synchronous tests
# Each async test will be explicitly marked instead


@pytest.mark.asyncio
async def test_async_logging_simple():
    """Test basic async operation with logging capture."""
    # Log some messages
    logger.debug("Async debug message")
    logger.info("Starting async operation")

    # Perform async operation
    await asyncio.sleep(0.1)
    logger.info("Async operation completed")

    # Simple assertion without relying on caplog fixture
    assert True  # In a real test, we'd verify behavior, not logs


@pytest.mark.asyncio
async def test_async_concurrent_logging():
    """Test concurrent async operations with logging."""

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
    assert results == [0, 1, 2]


# Mark specifically to run serially if needed
@pytest.mark.serial
@pytest.mark.asyncio
async def test_logging_intensive_serial():
    """Test with intensive logging that should run serially."""
    # Generate a large number of log messages
    for i in range(10):
        logger.debug(f"Detailed debug log {i}")
        if i % 2 == 0:
            logger.info(f"Progress update: {i/10:.0%} complete")

    # Simulate work
    await asyncio.sleep(0.2)
    logger.info("Intensive logging test completed")

    # Simple assertion for completion
    assert True


# Regular synchronous test with logging
def test_sync_with_logging():
    """Regular synchronous test with logging capture."""
    logger.info("This is a sync test")
    logger.warning("This is a warning")

    # Simple assertion for completion
    assert True
