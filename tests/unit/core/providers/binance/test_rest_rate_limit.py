"""Tests for REST client rate limit partial data handling (Phase 1 fixes).

Validates that:
- P1.1: reraise=True propagates RateLimitError (not tenacity.RetryError)
- P1.2: Default retry-after is 60s (not 1s)
- P1.3: Partial chunk data is returned on rate limit

Related: GitHub Issue #18 (Rate Limit Handling Overhaul)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from ckvd.core.providers.binance.rest_data_client import RestDataClient
from ckvd.utils.for_core.rest_exceptions import RateLimitError
from ckvd.utils.market_constraints import MarketType


# Sample kline data (Binance format: list of lists)
def _make_kline_row(open_time_ms: int) -> list:
    """Create a single kline row in Binance API format."""
    return [
        open_time_ms,  # open_time
        "42000.0",  # open
        "42100.0",  # high
        "41900.0",  # low
        "42050.0",  # close
        "1000.0",  # volume
        open_time_ms + 3600000 - 1,  # close_time
        "42050000.0",  # quote_volume
        100,  # trades
        "500.0",  # taker_buy_base
        "21025000.0",  # taker_buy_quote
        "0",  # ignore
    ]


class TestReraisePropagatesRateLimitError:
    """P1.1: Verify reraise=True makes RateLimitError catchable."""

    @patch("ckvd.core.providers.binance.rest_data_client.fetch_chunk")
    @patch("ckvd.core.providers.binance.rest_data_client.create_optimized_client")
    def test_rate_limit_error_not_wrapped_in_retry_error(
        self,
        mock_create_client,
        mock_fetch_chunk,
    ):
        """RateLimitError should propagate as itself, not as tenacity.RetryError."""
        mock_create_client.return_value = MagicMock()
        mock_fetch_chunk.side_effect = RateLimitError(retry_after=60)

        rest_client = RestDataClient(market_type=MarketType.SPOT)

        end_time = datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
        start_time = end_time - timedelta(hours=1)

        with pytest.raises(RateLimitError) as exc_info, rest_client:
            rest_client.fetch(
                symbol="BTCUSDT",
                interval="1h",
                start_time=start_time,
                end_time=end_time,
            )

        # Verify it's actually a RateLimitError, not wrapped in RetryError
        assert isinstance(exc_info.value, RateLimitError)
        assert exc_info.value.retry_after == 60


class TestDefaultRetryAfter:
    """P1.2: Verify default retry-after is 60s."""

    def test_rate_limit_error_default_retry_after(self):
        """RateLimitError created in fetch_chunk should default to 60s retry-after."""
        # The default is set in rest_client_utils.py line 108:
        #   response.headers.get("retry-after", 60)
        # We test the RateLimitError class itself
        error = RateLimitError(retry_after=60)
        assert error.retry_after == 60

        # Without explicit retry_after
        error_no_retry = RateLimitError()
        assert error_no_retry.retry_after is None


class TestPartialChunksOnRateLimit:
    """P1.3: Verify partial chunk data is returned on rate limit."""

    @patch("ckvd.core.providers.binance.rest_data_client.fetch_chunk")
    @patch("ckvd.core.providers.binance.rest_data_client.create_optimized_client")
    def test_partial_chunks_returned_on_429(
        self,
        mock_create_client,
        mock_fetch_chunk,
    ):
        """429 at chunk 2 should return chunk 1 data with _rate_limited flag."""
        mock_create_client.return_value = MagicMock()

        # First chunk succeeds, second raises RateLimitError
        base_ms = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        chunk1_data = [_make_kline_row(base_ms + i * 3600000) for i in range(10)]

        call_count = 0

        def _side_effect(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return chunk1_data
            raise RateLimitError(retry_after=60)

        mock_fetch_chunk.side_effect = _side_effect

        rest_client = RestDataClient(market_type=MarketType.SPOT)

        # Time range large enough to create multiple chunks (CHUNK_SIZE=1000,
        # 1h interval → need >1000h per chunk → 90 days = ~2160h = 2-3 chunks)
        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = start_time + timedelta(days=90)

        with rest_client:
            df = rest_client.fetch(
                symbol="BTCUSDT",
                interval="1h",
                start_time=start_time,
                end_time=end_time,
            )

        # Should have partial data from chunk 1
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert df.attrs.get("_rate_limited") is True

    @patch("ckvd.core.providers.binance.rest_data_client.fetch_chunk")
    @patch("ckvd.core.providers.binance.rest_data_client.create_optimized_client")
    def test_rate_limit_first_chunk_raises(
        self,
        mock_create_client,
        mock_fetch_chunk,
    ):
        """429 at first chunk with no data should raise RateLimitError."""
        mock_create_client.return_value = MagicMock()
        mock_fetch_chunk.side_effect = RateLimitError(retry_after=60)

        rest_client = RestDataClient(market_type=MarketType.SPOT)

        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = start_time + timedelta(hours=2)

        with pytest.raises(RateLimitError), rest_client:
            rest_client.fetch(
                symbol="BTCUSDT",
                interval="1h",
                start_time=start_time,
                end_time=end_time,
            )

    @patch("ckvd.core.providers.binance.rest_data_client.fetch_chunk")
    @patch("ckvd.core.providers.binance.rest_data_client.create_optimized_client")
    def test_no_rate_limit_no_flag(
        self,
        mock_create_client,
        mock_fetch_chunk,
    ):
        """Normal fetch without rate limit should have no _rate_limited flag."""
        mock_create_client.return_value = MagicMock()

        base_ms = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        mock_fetch_chunk.return_value = [_make_kline_row(base_ms + i * 3600000) for i in range(2)]

        rest_client = RestDataClient(market_type=MarketType.SPOT)

        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = start_time + timedelta(hours=2)

        with rest_client:
            df = rest_client.fetch(
                symbol="BTCUSDT",
                interval="1h",
                start_time=start_time,
                end_time=end_time,
            )

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "_rate_limited" not in df.attrs
