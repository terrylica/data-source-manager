#!/usr/bin/env python
"""Centralized cache validation utilities.

DEPRECATED: This module is a backward-compatibility re-export from the cache/ subpackage.
Import directly from ckvd.utils.cache for new code.

# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
# Refactoring: Original 808-line module split into cache/ subpackage
"""

# Re-export everything from the cache subpackage
from ckvd.utils.cache import (
    ERROR_TYPES,
    TEST_SYMBOL,
    AlignmentOptions,
    CacheKeyManager,
    CachePathOptions,
    CacheValidationError,
    CacheValidator,
    SafeMemoryMap,
    ValidationOptions,
    VisionCacheManager,
    safely_read_arrow_file_async,
    validate_cache_checksum,
    validate_cache_integrity,
    validate_cache_metadata,
    validate_cache_records,
)

__all__ = [
    "ERROR_TYPES",
    "TEST_SYMBOL",
    "AlignmentOptions",
    "CacheKeyManager",
    "CachePathOptions",
    "CacheValidationError",
    "CacheValidator",
    "SafeMemoryMap",
    "ValidationOptions",
    "VisionCacheManager",
    "safely_read_arrow_file_async",
    "validate_cache_checksum",
    "validate_cache_integrity",
    "validate_cache_metadata",
    "validate_cache_records",
]
