# Test Fixtures Reference

Common pytest fixtures for DataSourceManager testing.

## OKX Fixtures

Located in `tests/okx/conftest.py`:

```python
@pytest.fixture(scope="function")
def instrument():
    """Trading instrument for OKX tests."""
    return "BTC-USDT"

@pytest.fixture(scope="function")
def interval():
    """Trading interval for OKX tests."""
    return "1m"
```

## Recommended Fixtures

Create these fixtures in your test files or `conftest.py`:

### Manager Fixtures

```python
import pytest
from data_source_manager import DataSourceManager, DataProvider, MarketType

@pytest.fixture
def spot_manager():
    """Spot market manager (auto-close)."""
    manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.SPOT)
    yield manager
    manager.close()

@pytest.fixture
def futures_manager():
    """USDT futures manager (auto-close)."""
    manager = DataSourceManager.create(DataProvider.BINANCE, MarketType.FUTURES_USDT)
    yield manager
    manager.close()
```

### Time Fixtures

```python
from datetime import datetime, timedelta, timezone

@pytest.fixture
def utc_now():
    """Current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

@pytest.fixture
def one_week_range(utc_now):
    """One week date range ending now."""
    return utc_now - timedelta(days=7), utc_now
```

## Fixture Scopes

| Scope      | When Used               | DSM Pattern                    |
| ---------- | ----------------------- | ------------------------------ |
| `function` | Default, per-test       | Manager instances, time ranges |
| `class`    | Shared across class     | Test data fixtures             |
| `module`   | Shared across module    | Expensive setup (cache init)   |
| `session`  | Shared across all tests | Rarely needed                  |

## Auto-Cleanup Pattern

Always use `yield` for resources that need cleanup:

```python
@pytest.fixture
def manager_with_cache():
    """Manager with cache directory."""
    import tempfile
    cache_dir = tempfile.mkdtemp()
    manager = DataSourceManager.create(
        DataProvider.BINANCE,
        MarketType.SPOT,
        cache_dir=cache_dir
    )
    yield manager
    manager.close()
    # Cleanup cache
    import shutil
    shutil.rmtree(cache_dir)
```
