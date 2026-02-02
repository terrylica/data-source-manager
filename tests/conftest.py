"""
Root pytest conftest.py with shared fixtures for all test modules.

Fixtures defined here are automatically available to all tests in the tests/ directory.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# =============================================================================
# Time Fixtures
# =============================================================================


@pytest.fixture
def utc_now():
    """Current UTC time (timezone-aware).

    Use this instead of datetime.now() to ensure all tests use UTC.
    """
    return datetime.now(timezone.utc)


@pytest.fixture
def one_week_range(utc_now):
    """One week date range ending now.

    Returns:
        tuple: (start_time, end_time) both timezone-aware UTC.
    """
    return utc_now - timedelta(days=7), utc_now


@pytest.fixture
def one_day_range(utc_now):
    """One day date range ending now.

    Returns:
        tuple: (start_time, end_time) both timezone-aware UTC.
    """
    return utc_now - timedelta(days=1), utc_now


@pytest.fixture
def one_month_range(utc_now):
    """One month date range ending now.

    Returns:
        tuple: (start_time, end_time) both timezone-aware UTC.
    """
    return utc_now - timedelta(days=30), utc_now


@pytest.fixture
def historical_range(utc_now):
    """Historical date range suitable for Vision API (ends 3 days ago).

    Vision API has ~48h delay. This range is safe for Vision API tests.

    Returns:
        tuple: (start_time, end_time) both timezone-aware UTC.
    """
    end_time = utc_now - timedelta(days=3)
    start_time = end_time - timedelta(days=7)
    return start_time, end_time


@pytest.fixture
def recent_range(utc_now):
    """Very recent date range suitable for REST API tests (last 2 hours).

    This range is too recent for Vision API, forcing REST fallback.

    Returns:
        tuple: (start_time, end_time) both timezone-aware UTC.
    """
    return utc_now - timedelta(hours=2), utc_now


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_vision_handler():
    """Mock FSSpecVisionHandler for offline tests.

    Returns data via .fetch_data() method as empty DataFrame by default.
    """
    with patch("data_source_manager.core.sync.data_source_manager.FSSpecVisionHandler") as mock:
        handler_instance = MagicMock()
        handler_instance.fetch_data.return_value = pd.DataFrame()
        mock.return_value = handler_instance
        yield mock


@pytest.fixture
def mock_cache_manager():
    """Mock UnifiedCacheManager for offline tests.

    Returns None (cache miss) by default.
    """
    with patch("data_source_manager.core.sync.data_source_manager.UnifiedCacheManager") as mock:
        cache_instance = MagicMock()
        cache_instance.read.return_value = None  # Cache miss
        mock.return_value = cache_instance
        yield mock


@pytest.fixture
def mock_all_sources(mock_vision_handler, mock_cache_manager):
    """Combined mock for complete isolation from external services.

    Use this when you need full isolation for unit tests.
    """
    return {
        "vision": mock_vision_handler,
        "cache": mock_cache_manager,
    }


# =============================================================================
# Data Fixtures
# =============================================================================


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for testing.

    Returns:
        dict: Sample candle data with all standard fields.
    """
    return {
        "open_time": datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
        "open": 42000.0,
        "high": 42500.0,
        "low": 41800.0,
        "close": 42200.0,
        "volume": 1000.0,
    }


@pytest.fixture
def sample_symbol():
    """Standard test symbol for USDT futures."""
    return "BTCUSDT"


@pytest.fixture
def sample_coin_symbol():
    """Standard test symbol for coin-margined futures."""
    return "BTCUSD_PERP"
