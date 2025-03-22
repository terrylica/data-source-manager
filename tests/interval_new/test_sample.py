#!/usr/bin/env python
"""Sample test file for interval_new tests."""

import pytest


def test_sample():
    """Simple test to verify test discovery works."""
    assert True, "This test should always pass"


def test_interval_fixture(test_interval):
    """Test that the interval fixture works."""
    assert test_interval == "1m", f"Expected '1m', got '{test_interval}'"


@pytest.mark.asyncio
async def test_async_api_session(api_session):
    """Test that async session fixture works."""
    assert api_session is not None, "API session fixture should not be None"
