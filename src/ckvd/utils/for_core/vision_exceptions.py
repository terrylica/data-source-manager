#!/usr/bin/env python3
# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
# Refactoring: Add D107 __init__ docstrings
"""Custom exceptions for Binance Vision API related operations.

This module defines specialized exceptions to provide more precise error handling
for the Binance Vision API component. By using custom exceptions, calling code can
catch specific error types and handle them appropriately.

All exceptions carry a `.details` dict (default `{}`) for machine-parseable error
context, enabling AI agents and downstream consumers to programmatically handle errors.
GitHub Issue #23.
"""

from __future__ import annotations

from typing import Any

from ckvd.utils.loguru_setup import logger


class VisionAPIError(Exception):
    """Base exception for all Vision API related errors.

    Attributes:
        message: Human-readable error message.
        details: Machine-parseable error context (dict, default ``{}``).
    """

    def __init__(self, message="Binance Vision API error occurred", *, details: dict[str, Any] | None = None) -> None:
        """Initialize VisionAPIError with error message.

        Args:
            message: Error description.
            details: Machine-parseable context (symbol, interval, source, etc.).
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
        logger.error(f"VisionAPIError: {message}")


class UnsupportedIntervalError(ValueError):
    """Exception raised when an interval is not supported by a market type.

    Attributes:
        message: Human-readable error message.
        details: Machine-parseable error context (dict, default ``{}``).
    """

    def __init__(
        self,
        message="The specified interval is not supported by this market type",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize UnsupportedIntervalError with error message.

        Args:
            message: Error description.
            details: Machine-parseable context (interval, market_type, etc.).
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
        logger.error(f"UnsupportedIntervalError: {message}")


class DataFreshnessError(VisionAPIError):
    """Exception raised when data is too fresh for Vision API."""

    def __init__(self, message="Data is too fresh for Vision API", **kwargs: Any) -> None:
        """Initialize DataFreshnessError with error message.

        Args:
            message: Error description.
            **kwargs: Passed to VisionAPIError (e.g. ``details=...``).
        """
        super().__init__(f"DataFreshnessError: {message}", **kwargs)


class ChecksumVerificationError(VisionAPIError):
    """Exception raised when checksum verification fails."""

    def __init__(self, message="Checksum verification failed", **kwargs: Any) -> None:
        """Initialize ChecksumVerificationError with error message.

        Args:
            message: Error description.
            **kwargs: Passed to VisionAPIError (e.g. ``details=...``).
        """
        super().__init__(f"ChecksumVerificationError: {message}", **kwargs)


class DownloadFailedError(VisionAPIError):
    """Exception raised when file download fails."""

    def __init__(self, message="Failed to download file from Vision API", **kwargs: Any) -> None:
        """Initialize DownloadFailedError with error message.

        Args:
            message: Error description.
            **kwargs: Passed to VisionAPIError (e.g. ``details=...``).
        """
        super().__init__(f"DownloadFailedError: {message}", **kwargs)


class DataNotAvailableError(VisionAPIError):
    """Raised when data is unavailable before symbol listing date.

    This is a FAIL-LOUD exception that provides detailed context for forensics:
    - symbol: The requested trading symbol
    - market_type: The market type (SPOT, FUTURES_USDT, FUTURES_COIN)
    - requested_start: When the user requested data from
    - earliest_available: When data actually becomes available

    The `.details` dict is auto-populated from these attributes.
    """

    def __init__(
        self,
        symbol: str,
        market_type: str,
        requested_start: object,
        earliest_available: object,
        **kwargs: Any,
    ) -> None:
        """Initialize DataNotAvailableError with detailed context.

        Args:
            symbol: The requested trading symbol (e.g., 'BTCUSDT').
            market_type: The market type name (e.g., 'FUTURES_USDT').
            requested_start: The start datetime requested by user (datetime object).
            earliest_available: The earliest datetime data is available (datetime object).
            **kwargs: Passed to VisionAPIError (e.g. ``details=...``).
        """
        self.symbol = symbol
        self.market_type = market_type
        self.requested_start = requested_start
        self.earliest_available = earliest_available
        message = (
            f"FAIL-LOUD: Data not available for {symbol} on {market_type}. "
            f"Requested: {requested_start.isoformat()}, "
            f"Earliest: {earliest_available.isoformat()}"
        )
        # Auto-populate details from structured attributes
        auto_details = {
            "symbol": symbol,
            "market_type": market_type,
            "requested_start": str(requested_start),
            "earliest_available": str(earliest_available),
        }
        # Merge with any explicitly provided details (explicit wins)
        if "details" in kwargs:
            auto_details.update(kwargs.pop("details") or {})
        super().__init__(message, details=auto_details, **kwargs)
