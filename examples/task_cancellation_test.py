#!/usr/bin/env python3
"""
Focused test for the task cancellation demo script.
This runs just the test_for_warnings function to verify the fixes.
"""

from utils.logger_setup import logger
from rich import print
import asyncio
import gc
import os
import sys
import importlib
import shutil

# Add parent directory to path to ensure imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the necessary functions from task_cancellation_demo
from examples.task_cancellation_demo import (
    test_for_warnings,
    cleanup_lingering_tasks,
    clear_caches,
)


async def main():
    """Run only the warnings test from the demo script."""
    # Clear caches at startup
    clear_caches()

    print("\n" + "=" * 70)
    print("FOCUSED TASK CANCELLATION WARNING TEST")
    print("=" * 70)
    print("Running only the test_for_warnings function to check if fixes are working.")

    # Record all running tasks at start for leak detection
    tasks_at_start = len(asyncio.all_tasks())
    logger.info(f"Starting with {tasks_at_start} active tasks")

    # Run the focused test for warnings
    await test_for_warnings()

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
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    # Run the test
    asyncio.run(main())
