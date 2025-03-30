#!/usr/bin/env python
"""Root conftest.py that imports fixtures from time_boundary for backwards compatibility."""

# Left empty for backwards compatibility
# The fixtures were previously imported here but are no longer used

import asyncio
import pytest
from curl_cffi.requests import AsyncSession


@pytest.fixture
async def curl_cffi_client_with_cleanup():
    """Create a curl_cffi client with proper cleanup of pending tasks.

    This fixture ensures that AsyncCurl's internal timeout tasks are properly handled
    by adding a small delay after closing the client to allow pending tasks to complete.
    """
    client = AsyncSession()
    yield client
    await client.close()
    # Small delay to allow pending AsyncCurl timeout tasks to complete
    await asyncio.sleep(0.1)
