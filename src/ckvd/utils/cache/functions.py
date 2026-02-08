#!/usr/bin/env python
"""Standalone cache validation functions.

These functions provide direct access to CacheValidator methods
for backward compatibility with existing imports.

# polars-exception: Functions return pandas DataFrames for compatibility
# with existing consumers that expect pandas

# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
# Refactoring: Extract from cache_validator.py for modularity
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from ckvd.utils.cache.errors import CacheValidationError
from ckvd.utils.cache.validator import CacheValidator

__all__ = [
    "safely_read_arrow_file_async",
    "validate_cache_checksum",
    "validate_cache_integrity",
    "validate_cache_metadata",
    "validate_cache_records",
]


def validate_cache_integrity(
    cache_path: Path,
    max_age: timedelta | None = None,
    min_size: int | None = None,
) -> CacheValidationError | None:
    """Standalone version of CacheValidator.validate_cache_integrity.

    Args:
        cache_path: Path to cache file
        max_age: Maximum allowed age of cache
        min_size: Minimum valid file size

    Returns:
        Error details if validation fails, None if valid
    """
    return CacheValidator.validate_cache_integrity(cache_path, max_age, min_size)


def validate_cache_checksum(cache_path: Path, stored_checksum: str) -> bool:
    """Standalone version of CacheValidator.validate_cache_checksum.

    Args:
        cache_path: Path to cache file
        stored_checksum: Previously stored checksum

    Returns:
        True if checksum matches, False otherwise
    """
    return CacheValidator.validate_cache_checksum(cache_path, stored_checksum)


def validate_cache_metadata(
    cache_info: dict[str, Any] | None,
    required_fields: list | None = None,
) -> bool:
    """Standalone version of CacheValidator.validate_cache_metadata.

    Args:
        cache_info: Cache metadata dictionary
        required_fields: List of required fields in metadata

    Returns:
        True if metadata is valid, False otherwise
    """
    return CacheValidator.validate_cache_metadata(cache_info, required_fields)


def validate_cache_records(record_count: int | str) -> bool:
    """Standalone version of CacheValidator.validate_cache_records.

    Args:
        record_count: Number of records in cache (as int or str)

    Returns:
        True if record count is valid, False otherwise
    """
    try:
        if isinstance(record_count, str):
            record_count = int(record_count)
        return record_count > 0
    except (ValueError, TypeError):
        return False


async def safely_read_arrow_file_async(file_path: Path, columns: list | None = None) -> pd.DataFrame | None:
    """Standalone version of CacheValidator.safely_read_arrow_file_async.

    Args:
        file_path: Path to Arrow file
        columns: Optional list of columns to read

    Returns:
        DataFrame or None if read fails
    """
    return await CacheValidator.safely_read_arrow_file_async(file_path, columns)
