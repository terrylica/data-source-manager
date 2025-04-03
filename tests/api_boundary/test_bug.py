#!/usr/bin/env python
"""Simplified test to reproduce endpoint URL issues."""

import pytest
import asyncio
import inspect
import sys
import importlib
from datetime import datetime, timezone, timedelta
from utils.market_constraints import MarketType, ChartType, Interval, get_endpoint_url
from utils.api_boundary_validator import ApiBoundaryValidator


@pytest.mark.asyncio
async def test_direct_url_construction():
    """Test direct URL construction with different approaches."""
    print("\n=== Environment Information ===")
    print(f"Python version: {sys.version}")
    print(f"pytest version: {pytest.__version__}")

    # Check module sources to identify any potential module loading issues
    print("\n=== Module Sources ===")
    for name in ["utils.market_constraints", "utils.api_boundary_validator"]:
        module = importlib.import_module(name)
        print(f"{name} loaded from: {module.__file__}")

    print("\n=== ChartType Definition ===")
    chart_type_src = inspect.getsource(ChartType)
    print(chart_type_src[:200] + "..." if len(chart_type_src) > 200 else chart_type_src)

    # Test with string literal
    url_from_string = get_endpoint_url(MarketType.SPOT, "klines")
    print(f"\n=== URL Construction ===")
    print(f"URL from string: {url_from_string}")

    # Test with enum value
    url_from_enum = get_endpoint_url(MarketType.SPOT, ChartType.KLINES.endpoint)
    print(f"URL from enum: {url_from_enum}")

    # Test string interpolation with enum
    url_with_string_interp = get_endpoint_url(
        MarketType.SPOT, ChartType.KLINES.endpoint
    )
    print(f"URL with string interpolation: {url_with_string_interp}")

    # Get _call_api method from ApiBoundaryValidator to examine it
    print("\n=== ApiBoundaryValidator._call_api ===")
    call_api_src = inspect.getsource(ApiBoundaryValidator._call_api)
    print(call_api_src[:200] + "..." if len(call_api_src) > 200 else call_api_src)

    # Assert they should be the same
    assert (
        url_from_string == url_from_enum
    ), "URLs should match whether using string or enum"
    assert "ChartType.KLINES" not in url_from_enum, "Enum name should not appear in URL"

    # Test in the context where API validator uses it
    validator = ApiBoundaryValidator(MarketType.SPOT)
    try:
        # Get a URL from _call_api method indirectly (can't call directly as it's private)
        # Call a harmless method that uses _call_api
        print("\n=== Testing URL construction via ApiBoundaryValidator ===")

        # Use a past time range to avoid issues with future data
        end_time = datetime.now(timezone.utc) - timedelta(days=2)
        start_time = end_time - timedelta(minutes=5)

        print(f"Time range: {start_time} to {end_time}")

        valid = await validator.is_valid_time_range(
            start_time, end_time, Interval.MINUTE_1
        )
        print(f"is_valid_time_range returned {valid}")
    finally:
        await validator.close()


if __name__ == "__main__":
    asyncio.run(test_direct_url_construction())
