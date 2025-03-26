#!/usr/bin/env python
"""Root conftest.py that imports fixtures from time_boundary for backwards compatibility."""

import sys
from pathlib import Path

# Import fixtures from time_boundary
try:
    # Using explicit import with full path
    sys.path.insert(0, str(Path(__file__).parent))
    from tests.time_boundary.conftest import (
        time_window,
        default_symbol,
        api_session,
        test_symbol,
        test_interval,
        temp_cache_dir,
        # sample_ohlcv_data,  # Removed to avoid import error
    )
except ImportError:
    # Fallback approach for import
    try:
        from .time_boundary.conftest import (
            time_window,
            default_symbol,
            api_session,
            test_symbol,
            test_interval,
            temp_cache_dir,
            # sample_ohlcv_data,  # Removed to avoid import error
        )
    except ImportError as e:
        print(f"Warning: Could not import fixtures from time_boundary: {e}")

# Also import root level conftest functionality
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from conftest import pytest_configure, pytest_collection_modifyitems
except ImportError as e:
    print(f"Warning: Could not import root conftest functionality: {e}")
