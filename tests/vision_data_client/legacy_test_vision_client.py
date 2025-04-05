#!/usr/bin/env python
"""
LEGACY: Simple test script for VisionDataClient with the updated validation methods.

This file is kept for reference only. For proper testing of the VisionDataClient,
please use the pytest-based tests in the tests/vision_data_client directory:
- test_validation.py: Tests future date handling and validation

This legacy script demonstrates basic usage of the VisionDataClient and manual testing
of future date handling. It's not integrated with pytest and doesn't use proper fixtures
or assertions.
"""

import sys
import os
from datetime import datetime, timezone, timedelta
import asyncio

# Add the project root to the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.vision_data_client import VisionDataClient
from utils.logger_setup import logger


async def test():
    logger.info("Testing VisionDataClient with updated validation methods")
    client = VisionDataClient("BTCUSDT", "1d")
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    end = now

    logger.info(f"Fetching data from {start.isoformat()} to {end.isoformat()}")

    try:
        result = await client.fetch(start, end)
        logger.info(f"Successfully retrieved {len(result)} records")

        # Try with a date range that goes into the future
        future_end = now + timedelta(days=1)
        logger.info(f"Testing with future date: {future_end.isoformat()}")

        try:
            result = await client.fetch(start, future_end)
            logger.info(
                f"Successfully retrieved {len(result)} records with future handling"
            )
        except ValueError as e:
            logger.info(f"Expected validation error for future date: {str(e)}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test())
