#!/usr/bin/env python3
# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
"""FCP test fixtures for Failover Control Protocol tests.

Fixtures defined here are available to all tests in the fcp_pm/ directory.
Time fixtures (utc_now, one_week_range, etc.) are inherited from tests/conftest.py.
"""

import pytest

from data_source_manager.core.sync.data_source_manager import DataSourceManager
from data_source_manager.utils.market_constraints import (
    ChartType,
    DataProvider,
    MarketType,
)


# =============================================================================
# DataSourceManager Fixtures
# =============================================================================


@pytest.fixture
def fcp_manager_spot():
    """DataSourceManager for SPOT market with cache enabled."""
    manager = DataSourceManager(
        provider=DataProvider.BINANCE,
        market_type=MarketType.SPOT,
        chart_type=ChartType.KLINES,
        use_cache=True,
    )
    yield manager
    manager.close()


@pytest.fixture
def fcp_manager_futures():
    """DataSourceManager for USDT futures with cache enabled."""
    manager = DataSourceManager(
        provider=DataProvider.BINANCE,
        market_type=MarketType.FUTURES_USDT,
        chart_type=ChartType.KLINES,
        use_cache=True,
    )
    yield manager
    manager.close()


@pytest.fixture
def fcp_manager_coin():
    """DataSourceManager for coin-margined futures with cache enabled."""
    manager = DataSourceManager(
        provider=DataProvider.BINANCE,
        market_type=MarketType.FUTURES_COIN,
        chart_type=ChartType.KLINES,
        use_cache=True,
    )
    yield manager
    manager.close()


@pytest.fixture
def fcp_manager_no_cache():
    """DataSourceManager with cache disabled for isolation."""
    manager = DataSourceManager(
        provider=DataProvider.BINANCE,
        market_type=MarketType.FUTURES_USDT,
        chart_type=ChartType.KLINES,
        use_cache=False,
    )
    yield manager
    manager.close()
