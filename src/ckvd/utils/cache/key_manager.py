#!/usr/bin/env python
"""Cache key and path generation utilities.

# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
# Refactoring: Extract from cache_validator.py for modularity
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ckvd.utils.cache.options import CachePathOptions

__all__ = [
    "CacheKeyManager",
]


class CacheKeyManager:
    """Utilities for generating consistent cache keys and paths."""

    @staticmethod
    def get_cache_key(symbol: str, interval: str, date: datetime) -> str:
        """Generate a unique cache key.

        Args:
            symbol: Trading pair symbol
            interval: Time interval
            date: Target date

        Returns:
            Unique cache key string
        """
        date_str = date.strftime("%Y-%m-%d")
        return f"{symbol.upper()}_{interval}_{date_str}"

    @staticmethod
    def get_cache_path(
        cache_dir: Path,
        symbol: str,
        interval: str,
        date: datetime,
        options: CachePathOptions | None = None,
        exchange: str | None = None,
        market_type: str | None = None,
        data_nature: str | None = None,
        packaging_frequency: str | None = None,
    ) -> Path:
        """Generate standardized cache path.

        Generates a path that follows the structure:
        cache_dir/{exchange}/{market_type}/{data_nature}/{packaging_frequency}/{SYMBOL}/{INTERVAL}/YYYYMMDD.arrow

        Args:
            cache_dir: Root cache directory
            symbol: Trading pair symbol
            interval: Time interval
            date: Target date
            options: Cache path options with exchange, market type, data nature, etc.
            exchange: Optional custom exchange (overrides options if provided)
            market_type: Optional custom market type (overrides options if provided)
            data_nature: Optional custom data nature (overrides options if provided)
            packaging_frequency: Optional custom packaging frequency (overrides options if provided)

        Returns:
            Path object for cache file
        """
        if options is None:
            options = CachePathOptions()

        # Override options with individual parameters if provided
        if exchange is not None:
            options.exchange = exchange
        if market_type is not None:
            options.market_type = market_type
        if data_nature is not None:
            options.data_nature = data_nature
        if packaging_frequency is not None:
            options.packaging_frequency = packaging_frequency

        # Format date for filename
        year_month_day = date.strftime("%Y%m%d")

        # Standardize symbol and interval format
        symbol = symbol.upper()
        interval = interval.lower()

        # Generate path with standardized structure
        path = cache_dir / options.exchange / options.market_type / options.data_nature / options.packaging_frequency / symbol / interval
        path.mkdir(parents=True, exist_ok=True)

        # Generate filename with standardized format
        filename = f"{year_month_day}.arrow"

        return path / filename
