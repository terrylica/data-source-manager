"""Interval-specific tests for data retrieval across different market types.

This package contains tests that verify data retrieval functionality
across all supported intervals and market types:

Intervals:
- 1s (SPOT only)
- 1m
- 1h
- 1d

Market Types:
- SPOT (api.binance.com)
- FUTURES_USDT/UM (fapi.binance.com)
- FUTURES_COIN/CM (dapi.binance.com)
"""

from utils.market_constraints import Interval, MarketType

# Test symbols for each market type
SPOT_SYMBOL = "BTCUSDT"
FUTURES_USDT_SYMBOL = "BTCUSDT"
FUTURES_COIN_SYMBOL = "BTCUSD_PERP"

# Consolidate test parameters for reuse across test modules
MARKET_TEST_PARAMS = [
    (MarketType.SPOT, SPOT_SYMBOL, 1000),  # SPOT market with 1000 record limit
    (
        MarketType.FUTURES_USDT,
        FUTURES_USDT_SYMBOL,
        1500,
    ),  # UM futures with 1500 record limit
    (
        MarketType.FUTURES_COIN,
        FUTURES_COIN_SYMBOL,
        1500,
    ),  # CM futures with 1500 record limit
]

# Define intervals supported by each market type
# SPOT supports all intervals including 1s
# Futures markets don't support 1s interval
SPOT_INTERVALS = [
    Interval.SECOND_1,
    Interval.MINUTE_1,
    Interval.HOUR_1,
    Interval.DAY_1,
]

FUTURES_INTERVALS = [
    Interval.MINUTE_1,
    Interval.HOUR_1,
    Interval.DAY_1,
]
