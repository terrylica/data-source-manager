#!/usr/bin/env python
"""Cache validation and management subpackage.

This subpackage provides centralized cache validation utilities including:
- Error types and constants
- Safe memory map handling for Arrow files
- Validation options and configuration
- Cache key and path generation
- Core validation logic
- Vision-specific cache management
- Standalone validation functions

# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
# Refactoring: Split from cache_validator.py (808 lines) for modularity
"""

from data_source_manager.utils.cache.errors import (
    ERROR_TYPES,
    TEST_SYMBOL,
    CacheValidationError,
)
from data_source_manager.utils.cache.functions import (
    safely_read_arrow_file_async,
    validate_cache_checksum,
    validate_cache_integrity,
    validate_cache_metadata,
    validate_cache_records,
)
from data_source_manager.utils.cache.key_manager import CacheKeyManager
from data_source_manager.utils.cache.memory_map import SafeMemoryMap
from data_source_manager.utils.cache.options import (
    AlignmentOptions,
    CachePathOptions,
    ValidationOptions,
)
from data_source_manager.utils.cache.validator import CacheValidator
from data_source_manager.utils.cache.vision_manager import VisionCacheManager

__all__ = [
    "ERROR_TYPES",
    "TEST_SYMBOL",
    # Classes
    "AlignmentOptions",
    "CacheKeyManager",
    "CachePathOptions",
    # Errors
    "CacheValidationError",
    "CacheValidator",
    "SafeMemoryMap",
    "ValidationOptions",
    "VisionCacheManager",
    # Functions
    "safely_read_arrow_file_async",
    "validate_cache_checksum",
    "validate_cache_integrity",
    "validate_cache_metadata",
    "validate_cache_records",
]
