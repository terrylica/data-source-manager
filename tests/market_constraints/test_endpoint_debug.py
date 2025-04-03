#!/usr/bin/env python

"""Debug script for testing endpoint URL construction."""

import asyncio
from utils.market_constraints import (
    MarketType,
    ChartType,
    get_endpoint_url,
)
from utils.network_utils import create_client, test_connectivity


async def test_endpoint_url():
    """Test endpoint URL construction with and without pytest."""

    # Test direct construction
    direct_endpoint_url = get_endpoint_url(MarketType.SPOT, ChartType.KLINES)
    print(f"Direct endpoint URL: {direct_endpoint_url}")
    print(f"Direct endpoint URL type: {type(direct_endpoint_url)}")
    print(f"Direct endpoint URL repr: {direct_endpoint_url!r}")

    # Test creating URL using f-string
    direct_url = f"{direct_endpoint_url}?symbol=BTCUSDT&interval=1m&limit=5"
    print(f"Direct URL: {direct_url}")
    print(f"Direct URL repr: {direct_url!r}")

    # Test connectivity
    client = create_client(timeout=5.0)
    try:
        is_ok = await test_connectivity(client=client, url=direct_url, timeout=5.0)
        print(f"Direct URL connectivity: {is_ok}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_endpoint_url())
