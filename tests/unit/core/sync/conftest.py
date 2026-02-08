"""Local conftest for ckvd unit tests.

This provides auto-use fixtures that mock the factory pattern,
allowing legacy @patch decorators to work with the new architecture.

ADR: docs/adr/2025-01-30-failover-control-protocol.md
Related: Factory pattern wiring to CKVD (Task #99)
"""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def mock_provider_factory():
    """Auto-mock the provider factory for all tests in this directory.

    This fixture automatically patches get_provider_clients so that
    CryptoKlineVisionData can be instantiated without actual provider clients.
    The legacy @patch decorators for FSSpecVisionHandler and UnifiedCacheManager
    will be no-ops but the factory mock handles initialization.
    """
    from ckvd import DataProvider, MarketType
    from ckvd.core.providers import ProviderClients

    def _create_mock_clients(provider=DataProvider.BINANCE, market_type=MarketType.SPOT, **kwargs):
        """Create mock ProviderClients for testing."""
        mock_vision = MagicMock()
        mock_vision.fetch_data.return_value = pd.DataFrame()
        mock_rest = MagicMock()
        mock_cache = MagicMock()
        mock_cache.read.return_value = None  # Cache miss by default
        return ProviderClients(
            vision=mock_vision,
            rest=mock_rest,
            cache=mock_cache,
            provider=provider,
            market_type=market_type,
        )

    with patch("ckvd.core.sync.crypto_kline_vision_data.get_provider_clients") as mock:
        mock.side_effect = _create_mock_clients
        yield mock
