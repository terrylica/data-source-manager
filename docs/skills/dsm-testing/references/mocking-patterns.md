# Mocking Patterns Reference

DSM-specific mocking patterns for unit tests.

## Core Component Mocks

### FSSpec Vision Handler

Mock Vision API (S3 access) for offline tests:

```python
from unittest.mock import patch, MagicMock
import pandas as pd

@patch("data_source_manager.core.sync.data_source_manager.FSSpecVisionHandler")
def test_without_vision(mock_handler):
    # Configure mock to return empty DataFrame
    # Note: DSM returns pd.DataFrame for API compatibility
    handler_instance = MagicMock()
    handler_instance.fetch_data.return_value = pd.DataFrame()
    mock_handler.return_value = handler_instance

    # Test logic...
```

### Unified Cache Manager

Mock cache operations:

```python
@patch("data_source_manager.core.sync.data_source_manager.UnifiedCacheManager")
def test_without_cache(mock_cache):
    cache_instance = MagicMock()
    cache_instance.read.return_value = None  # Cache miss
    mock_cache.return_value = cache_instance

    # Test logic...
```

### Combined Mocks

For complete isolation:

```python
@patch("data_source_manager.core.sync.data_source_manager.FSSpecVisionHandler")
@patch("data_source_manager.core.sync.data_source_manager.UnifiedCacheManager")
def test_isolated(mock_cache, mock_handler):
    # Note: decorator order reverses parameter order
    mock_cache.return_value = MagicMock()
    mock_handler.return_value = MagicMock()

    # Test logic...
```

## HTTP Request Mocks

### requests Library

```python
from unittest.mock import patch

@patch("requests.get")
def test_rest_fallback(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {
        "data": [[1704067200000, "42000", "42100", "41900", "42050", "100"]]
    }

    # Test REST API fallback...
```

### httpx Library

```python
from unittest.mock import patch, MagicMock

@patch("httpx.Client.get")
def test_httpx_request(mock_get):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"data": [...]}
    mock_get.return_value = response

    # Test logic...
```

## Time Mocking

### Freeze Time

```python
from unittest.mock import patch
from datetime import datetime, timezone

@patch("data_source_manager.utils.time.datetime")
def test_time_sensitive(mock_datetime):
    frozen_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    mock_datetime.now.return_value = frozen_time
    mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

    # Test logic...
```

## Best Practices

1. **Mock at the boundary** - Mock external services, not internal logic
2. **Use `spec=True`** - Catch attribute errors: `MagicMock(spec=ClassName)`
3. **Reset mocks** - Use `mock.reset_mock()` between assertions if needed
4. **Check call counts** - Verify mocks were called: `mock.assert_called_once()`

## Anti-Patterns

```python
# ❌ Don't mock internal implementation details
@patch("data_source_manager.core.sync.data_source_manager._internal_method")

# ✅ Mock at service boundaries
@patch("data_source_manager.core.sync.data_source_manager.FSSpecVisionHandler")
```
