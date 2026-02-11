"""Tests for exception .details dict (machine-parseable error context).

GitHub Issue #23: Formalize exception .details dict.
Cross-repo analysis of gapless-crypto-data revealed the .details pattern
enables AI agents and downstream consumers to programmatically handle errors.
"""

from datetime import UTC, datetime

import pytest

from ckvd.utils.for_core.rest_exceptions import (
    APIError,
    HTTPError,
    JSONDecodeError,
    NetworkError,
    RateLimitError,
    RestAPIError,
    RestTimeoutError,
)
from ckvd.utils.for_core.vision_exceptions import (
    ChecksumVerificationError,
    DataFreshnessError,
    DataNotAvailableError,
    DownloadFailedError,
    UnsupportedIntervalError,
    VisionAPIError,
)


class TestRestBaseExceptionDetails:
    """Verify RestAPIError base class carries .details."""

    def test_default_details_is_empty_dict(self):
        """Default .details must be {} (not None)."""
        e = RestAPIError("some error")
        assert e.details == {}

    def test_details_accepts_dict(self):
        """Explicit details kwarg should be stored."""
        details = {"symbol": "BTCUSDT", "interval": "1h"}
        e = RestAPIError("some error", details=details)
        assert e.details == details

    def test_details_none_becomes_empty_dict(self):
        """Passing details=None should result in {}."""
        e = RestAPIError("some error", details=None)
        assert e.details == {}

    def test_details_preserved_through_raise(self):
        """Details must survive raise/except round-trip."""
        details = {"source": "REST", "http_status": 429}
        with pytest.raises(RestAPIError) as exc_info:
            raise RestAPIError("rate limited", details=details)
        assert exc_info.value.details == details

    def test_details_is_dict_not_none(self):
        """Default is {} — safe to access .details['key'] patterns."""
        e = RestAPIError()
        assert isinstance(e.details, dict)


class TestVisionBaseExceptionDetails:
    """Verify VisionAPIError base class carries .details."""

    def test_default_details_is_empty_dict(self):
        """Default .details must be {} (not None)."""
        e = VisionAPIError("some error")
        assert e.details == {}

    def test_details_accepts_dict(self):
        """Explicit details kwarg should be stored."""
        details = {"symbol": "ETHUSDT", "source": "VISION"}
        e = VisionAPIError("vision fail", details=details)
        assert e.details == details

    def test_details_preserved_through_raise(self):
        """Details must survive raise/except round-trip."""
        details = {"date": "2024-01-15", "reason": "403"}
        with pytest.raises(VisionAPIError) as exc_info:
            raise VisionAPIError("forbidden", details=details)
        assert exc_info.value.details == details


class TestRestSubclassesInheritDetails:
    """Verify all REST exception subclasses support .details via **kwargs."""

    def test_rate_limit_error_with_details(self):
        """RateLimitError should pass details to base."""
        details = {"endpoint": "/api/v3/klines", "weight_used": 6000}
        e = RateLimitError(retry_after=60, details=details)
        assert e.details == details
        assert e.retry_after == 60

    def test_http_error_with_details(self):
        """HTTPError should pass details to base."""
        details = {"url": "https://api.binance.com/api/v3/klines"}
        e = HTTPError(403, details=details)
        assert e.details == details
        assert e.status_code == 403

    def test_api_error_with_details(self):
        """APIError should pass details to base."""
        details = {"api_code": -1121}
        e = APIError(code=-1121, details=details)
        assert e.details == details

    def test_network_error_with_details(self):
        """NetworkError should pass details to base."""
        details = {"timeout_seconds": 30}
        e = NetworkError(details=details)
        assert e.details == details

    def test_rest_timeout_error_with_details(self):
        """RestTimeoutError should pass details to base."""
        details = {"endpoint": "/fapi/v1/klines"}
        e = RestTimeoutError(details=details)
        assert e.details == details

    def test_json_decode_error_with_details(self):
        """JSONDecodeError should pass details to base."""
        details = {"response_body": "<html>..."}
        e = JSONDecodeError(details=details)
        assert e.details == details


class TestVisionSubclassesInheritDetails:
    """Verify all Vision exception subclasses support .details via **kwargs."""

    def test_data_freshness_error_with_details(self):
        """DataFreshnessError should pass details to base."""
        details = {"symbol": "BTCUSDT", "data_age_hours": 12}
        e = DataFreshnessError(details=details)
        assert e.details == details

    def test_checksum_verification_error_with_details(self):
        """ChecksumVerificationError should pass details to base."""
        details = {"expected": "abc123", "actual": "def456"}
        e = ChecksumVerificationError(details=details)
        assert e.details == details

    def test_download_failed_error_with_details(self):
        """DownloadFailedError should pass details to base."""
        details = {"url": "https://data.binance.vision/...", "status": 404}
        e = DownloadFailedError(details=details)
        assert e.details == details

    def test_unsupported_interval_error_with_details(self):
        """UnsupportedIntervalError should carry .details."""
        details = {"interval": "2h", "market_type": "SPOT"}
        e = UnsupportedIntervalError("2h not supported", details=details)
        assert e.details == details


class TestDataNotAvailableErrorAutoDetails:
    """Verify DataNotAvailableError auto-populates .details."""

    def test_auto_populates_details(self):
        """DataNotAvailableError should auto-populate .details from attributes."""
        now = datetime.now(UTC)
        e = DataNotAvailableError(
            symbol="BTCUSDT",
            market_type="FUTURES_USDT",
            requested_start=now,
            earliest_available=now,
        )
        assert e.details["symbol"] == "BTCUSDT"
        assert e.details["market_type"] == "FUTURES_USDT"
        assert "requested_start" in e.details
        assert "earliest_available" in e.details

    def test_explicit_details_merged(self):
        """Explicit details should merge with auto-populated ones."""
        now = datetime.now(UTC)
        e = DataNotAvailableError(
            symbol="ETHUSDT",
            market_type="SPOT",
            requested_start=now,
            earliest_available=now,
            details={"extra_key": "extra_value"},
        )
        assert e.details["symbol"] == "ETHUSDT"
        assert e.details["extra_key"] == "extra_value"


class TestBackwardCompatibility:
    """Verify existing exception usage still works without details."""

    def test_rest_api_error_no_details(self):
        """raise RestAPIError('msg') still works."""
        e = RestAPIError("something broke")
        assert str(e) == "something broke"
        assert e.details == {}

    def test_vision_api_error_no_details(self):
        """raise VisionAPIError('msg') still works."""
        e = VisionAPIError("vision broke")
        assert "vision broke" in str(e)
        assert e.details == {}

    def test_rate_limit_error_positional_args(self):
        """Existing positional-arg usage still works."""
        e = RateLimitError(60)
        assert e.retry_after == 60
        assert e.details == {}

    def test_http_error_positional_args(self):
        """Existing positional-arg usage still works."""
        e = HTTPError(404)
        assert e.status_code == 404
        assert e.details == {}

    def test_api_error_positional_args(self):
        """Existing positional-arg usage still works."""
        e = APIError(-1121)
        assert e.code == -1121
        assert e.details == {}

    def test_data_not_available_error_positional_args(self):
        """Existing positional-arg usage still works."""
        now = datetime.now(UTC)
        e = DataNotAvailableError("BTCUSDT", "SPOT", now, now)
        assert e.symbol == "BTCUSDT"
        assert isinstance(e.details, dict)


class TestAllExceptionClassesSupportDetails:
    """Programmatically verify every exception class supports .details."""

    @pytest.mark.parametrize(
        "exc_cls,args",
        [
            (RestAPIError, ("msg",)),
            (RateLimitError, (60,)),
            (HTTPError, (500,)),
            (APIError, (-1,)),
            (NetworkError, ()),
            (RestTimeoutError, ()),
            (JSONDecodeError, ()),
            (VisionAPIError, ("msg",)),
            (DataFreshnessError, ()),
            (ChecksumVerificationError, ()),
            (DownloadFailedError, ()),
        ],
    )
    def test_all_have_details_attribute(self, exc_cls, args):
        """Every exception class must have a .details attribute that is a dict."""
        e = exc_cls(*args)
        assert hasattr(e, "details")
        assert isinstance(e.details, dict)
