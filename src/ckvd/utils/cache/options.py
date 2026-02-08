#!/usr/bin/env python
"""Cache validation and path configuration options.

# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
# Refactoring: Extract from cache_validator.py for modularity
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ckvd.utils.market_constraints import Interval

__all__ = [
    "AlignmentOptions",
    "CachePathOptions",
    "ValidationOptions",
]


@dataclass
class ValidationOptions:
    """Options for cache data validation."""

    allow_empty: bool = False
    start_time: datetime | None = None
    end_time: datetime | None = None
    interval: Interval | None = None
    symbol: str = "BTCUSDT"


@dataclass
class AlignmentOptions:
    """Options for aligning cache data to API boundaries."""

    start_time: datetime
    end_time: datetime
    interval: Interval
    symbol: str = "BTCUSDT"


@dataclass
class CachePathOptions:
    """Options for cache path generation."""

    exchange: str = "binance"
    market_type: str = "spot"
    data_nature: str = "klines"
    packaging_frequency: str = "daily"
