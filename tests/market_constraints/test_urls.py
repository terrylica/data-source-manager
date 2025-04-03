#!/usr/bin/env python
"""Standalone script to test URL construction."""

import importlib
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Force reload the module to ensure we have the latest code
import utils.market_constraints

importlib.reload(utils.market_constraints)

# Import after reload
from utils.market_constraints import (
    MarketType,
    ChartType,
    get_market_capabilities,
    get_endpoint_url,
)


def test_urls():
    """Test URL construction for all market types."""
    print("\nTesting URL construction for all market types:")
    print("=============================================")

    # Test each market type
    for market_type in MarketType:
        capabilities = get_market_capabilities(market_type)
        direct_url = capabilities.api_base_url

        # Use ChartType.KLINES.endpoint to get the string value directly
        klines_endpoint = ChartType.KLINES.endpoint
        endpoint_url = get_endpoint_url(market_type, klines_endpoint)

        print(f"\n{market_type.name}:")
        print(f"  Base URL: {direct_url}")
        print(f"  Endpoint URL: {endpoint_url}")

        # Get the hostname from the URL
        hostname = direct_url.split("//")[1].split("/")[0]
        assert hostname.endswith("binance.com"), f"Invalid hostname: {hostname}"

        # Verify SPOT uses api subdomain
        if market_type == MarketType.SPOT:
            assert "api.binance.com" in direct_url
            assert "/api/" in endpoint_url

        # Verify USDT Futures uses fapi subdomain
        elif market_type == MarketType.FUTURES_USDT:
            assert "fapi.binance.com" in direct_url
            # We now use /fapi/ for FUTURES_USDT, but allow /api/ for temporary backward compatibility
            assert "/fapi/" in endpoint_url

        # Verify COIN Futures uses dapi subdomain
        elif market_type == MarketType.FUTURES_COIN:
            assert "dapi.binance.com" in direct_url
            assert "/dapi/" in endpoint_url

        # Special case for legacy FUTURES type
        elif market_type == MarketType.FUTURES:
            assert "fapi.binance.com" in direct_url
            # For legacy FUTURES we now use /fapi/ path like FUTURES_USDT
            assert "/fapi/" in endpoint_url

        # Verify OPTIONS uses eapi subdomain
        elif market_type == MarketType.OPTIONS:
            assert "eapi.binance.com" in direct_url
            assert "/eapi/" in endpoint_url

    print("\nDone testing URL construction")


if __name__ == "__main__":
    test_urls()
