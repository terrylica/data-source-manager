#!/usr/bin/env python
"""Cache validation error types and constants.

# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
# Refactoring: Extract from cache_validator.py for modularity
"""

from typing import NamedTuple

__all__ = [
    "ERROR_TYPES",
    "TEST_SYMBOL",
    "CacheValidationError",
]

# Default symbol for tests
TEST_SYMBOL = "BTCUSDT"


class CacheValidationError(NamedTuple):
    """Standardized cache validation error details."""

    error_type: str
    message: str
    is_recoverable: bool


# Error type constants for consistent error reporting
ERROR_TYPES = {
    "FILE_SYSTEM": "file_system_error",
    "DATA_INTEGRITY": "data_integrity_error",
    "CACHE_INVALID": "cache_invalid",
    "VALIDATION": "validation_error",
    "API_BOUNDARY": "api_boundary_error",
}
