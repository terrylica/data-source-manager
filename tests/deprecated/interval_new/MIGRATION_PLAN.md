# Test Migration Plan

## Overview

The `vision_data_client_enhanced.py` file is being deprecated and will be removed in a future update. Tests in this directory were previously dependent on this file and have been moved here as part of the deprecation process.

## Files to Update (If Needed)

The following test files need to be updated if they are to be retained:

1. `test_vision_client_batch.py`
2. `test_vision_client_enhanced.py`
3. `test_vision_client_intervals.py`
4. `test_vision_client_markets.py`
5. `test_vision_client_schema.py`

## Migration Steps

If these tests are to be migrated rather than removed, follow these steps:

1. **Update imports**:

   - Replace `from core.vision_data_client_enhanced import VisionDataClient` with `from core.vision_data_client import VisionDataClient`
   - For tests that rely on caching functionality, add `from core.data_source_manager import DataSourceManager`

2. **Update fixture definitions**:

   - Modify any fixtures that create `VisionDataClient` instances to use the version from `vision_data_client.py`
   - For tests requiring caching, create a `DataSourceManager` instance instead

3. **Update test assertions**:

   - Ensure assertions align with the behavior of `vision_data_client.py`
   - For caching tests, verify the behavior with `DataSourceManager` and `UnifiedCacheManager`

4. **Mock updates**:
   - Change any mocks from `@mock.patch("core.vision_data_client_enhanced.TimeRangeManager")` to `@mock.patch("core.vision_data_client.TimeRangeManager")`

## Sample Migration Example

### Before:

```python
from core.vision_data_client_enhanced import VisionDataClient

@pytest.fixture
async def client():
    async with VisionDataClient("BTCUSDT", interval="1m", use_cache=True) as client:
        yield client

@pytest.mark.asyncio
async def test_fetch_data(client):
    df = await client.fetch(start_time, end_time)
    assert not df.empty
```

### After:

```python
from core.vision_data_client import VisionDataClient
from core.data_source_manager import DataSourceManager
from core.cache_manager import UnifiedCacheManager
from utils.market_constraints import MarketType, DataSource

@pytest.fixture
async def client():
    async with VisionDataClient("BTCUSDT", interval="1m") as client:
        yield client

@pytest.fixture
async def dsm():
    # For tests that need caching
    manager = DataSourceManager(
        cache_manager=UnifiedCacheManager(use_cache=True),
        market_type=MarketType.SPOT
    )
    yield manager
    await manager.close()

@pytest.mark.asyncio
async def test_fetch_data(client):
    df = await client.fetch(start_time, end_time)
    assert not df.empty

@pytest.mark.asyncio
async def test_fetch_with_cache(dsm):
    df = await dsm.get_data(
        symbol="BTCUSDT",
        interval="1m",
        start_time=start_time,
        end_time=end_time,
        enforce_source=DataSource.VISION
    )
    assert not df.empty
```

## Recommended Approach

Rather than migrating these tests, it's recommended to rely on the consolidated test files that already cover this functionality:

- API Boundary Tests: `tests/api_boundary/test_api_boundary.py`
- Market Data Tests: `tests/interval_1s/test_market_data_validation.py`
- Cache Tests: `tests/interval_1s/test_cache_unified.py`
