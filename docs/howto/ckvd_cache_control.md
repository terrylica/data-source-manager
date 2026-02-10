# CKVD Cache Control Guide

## Overview

CKVD caches market data as Apache Arrow files for fast repeated access (~1ms vs 1-5s from API). Cache is enabled by default but can be disabled per-manager, per-environment, or per-request.

## Quick Reference

| Mechanism                        | Scope            | Example                                                 |
| -------------------------------- | ---------------- | ------------------------------------------------------- |
| `use_cache=False`                | Per-manager      | `CryptoKlineVisionData.create(..., use_cache=False)`    |
| `CKVD_ENABLE_CACHE=false`        | Global (env var) | `export CKVD_ENABLE_CACHE=false`                        |
| `enforce_source=DataSource.REST` | Per-request      | `manager.get_data(..., enforce_source=DataSource.REST)` |

**Precedence**: explicit `use_cache=False` > `CKVD_ENABLE_CACHE` env var > default `True`

## Method 1: Per-Manager (use_cache Parameter)

Disable cache for a specific manager instance:

```python
from ckvd import CryptoKlineVisionData, DataProvider, MarketType, Interval
from datetime import datetime, timedelta, timezone

# Cache disabled — no Arrow files read or written
manager = CryptoKlineVisionData.create(
    DataProvider.BINANCE,
    MarketType.FUTURES_USDT,
    use_cache=False,
)

end = datetime.now(timezone.utc)
start = end - timedelta(days=7)

# Every call fetches fresh from Vision/REST API
df = manager.get_data("BTCUSDT", start, end, Interval.HOUR_1)
manager.close()
```

Also works with the high-level API:

```python
from ckvd import fetch_market_data, DataProvider, MarketType, Interval, ChartType

df, elapsed, count = fetch_market_data(
    provider=DataProvider.BINANCE,
    market_type=MarketType.FUTURES_USDT,
    chart_type=ChartType.KLINES,
    symbol="BTCUSDT",
    interval=Interval.HOUR_1,
    start_time=start,
    end_time=end,
    use_cache=False,  # No cache for this fetch
)
```

## Method 2: Global Environment Variable

Disable cache for ALL CKVD instances without code changes:

```bash
# Any of these disable cache:
export CKVD_ENABLE_CACHE=false
export CKVD_ENABLE_CACHE=0
export CKVD_ENABLE_CACHE=no

# Run your script — all managers have cache disabled
python your_pipeline.py
```

Or set programmatically before import:

```python
import os
os.environ["CKVD_ENABLE_CACHE"] = "false"

from ckvd import CryptoKlineVisionData, DataProvider, MarketType

# Cache is disabled even though use_cache defaults to True
manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.SPOT)
assert manager.use_cache is False  # Overridden by env var
```

The env var is respected by all entry points:

- `CryptoKlineVisionData.__init__()` / `.create()`
- `fetch_market_data()`
- `BinanceFundingRateClient()`
- `CKVDConfig.create()`

## Method 3: Per-Request Source Control

Force data from a specific FCP source using `enforce_source`:

```python
from ckvd.core.sync.ckvd_types import DataSource

# Skip cache, fetch from REST API only (freshest data)
df = manager.get_data(
    "BTCUSDT", start, end, Interval.HOUR_1,
    enforce_source=DataSource.REST,
)

# Skip cache, fetch from Vision API only (bulk historical)
df = manager.get_data(
    "BTCUSDT", start, end, Interval.HOUR_1,
    enforce_source=DataSource.VISION,
)

# Use cache only (offline mode — fails if data not cached)
df = manager.get_data(
    "BTCUSDT", start, end, Interval.HOUR_1,
    enforce_source=DataSource.CACHE,
)
```

**Important**: `enforce_source` controls _which_ source. `use_cache` controls _whether_ cache exists at all.

## Error: enforce_source=CACHE + use_cache=False

This is a logical contradiction — "use only cache" + "don't use cache":

```python
manager = CryptoKlineVisionData.create(
    DataProvider.BINANCE, MarketType.SPOT,
    use_cache=False,
)

# Raises RuntimeError: Cannot use enforce_source=DataSource.CACHE when use_cache=False
manager.get_data(
    "BTCUSDT", start, end, Interval.HOUR_1,
    enforce_source=DataSource.CACHE,
)
```

Other `enforce_source` values work fine with `use_cache=False`:

| `enforce_source` | `use_cache=False` | Result                      |
| ---------------- | ----------------- | --------------------------- |
| `AUTO`           | Works             | Vision → REST (skips cache) |
| `VISION`         | Works             | Vision API only             |
| `REST`           | Works             | REST API only               |
| `CACHE`          | **RuntimeError**  | Logical contradiction       |

## When to Disable Cache

### Disable cache

- **Unit/integration tests** — isolation between test runs
- **API response validation** — verify data freshness
- **Performance benchmarking** — measure true API latency
- **CI/CD pipelines** — no persistent state between runs
- **Debugging FCP** — force Vision or REST to diagnose issues

### Keep cache enabled

- **Production backtesting** — ~1ms cache vs ~1-5s API
- **Feature engineering** — repeated symbol access across runs
- **Multi-symbol scans** — cache warms progressively
- **Development iteration** — fast feedback loops

## CKVDConfig Integration

`CKVDConfig` is an immutable configuration class that also respects `CKVD_ENABLE_CACHE`:

```python
from ckvd.core.sync.ckvd_types import CKVDConfig

# Explicit disable
config = CKVDConfig.create(
    provider=DataProvider.BINANCE,
    market_type=MarketType.FUTURES_USDT,
    use_cache=False,
)
assert config.use_cache is False

# Env var override (CKVD_ENABLE_CACHE=false in environment)
config = CKVDConfig.create(
    provider=DataProvider.BINANCE,
    market_type=MarketType.SPOT,
)
# config.use_cache is False if CKVD_ENABLE_CACHE=false
```

## Cache Location and Cleanup

Default cache directory: `~/.cache/ckvd/`

```bash
# Check cache size
du -sh ~/.cache/ckvd/

# Clear all cache
rm -rf ~/.cache/ckvd/

# Clear specific symbol
rm -rf ~/.cache/ckvd/binance/futures_usdt/klines/daily/BTCUSDT/
```

## Demo

```bash
# Run the cache control example
uv run -p 3.13 python examples/ckvd_cache_control_example.py

# Run with cache disabled via env var
CKVD_ENABLE_CACHE=false uv run -p 3.13 python examples/ckvd_cache_control_example.py
```

## Environment Variable Summary

| Variable                 | Purpose                 | Default           | Values                                          |
| ------------------------ | ----------------------- | ----------------- | ----------------------------------------------- |
| `CKVD_ENABLE_CACHE`      | Enable/disable cache    | `true` (cache on) | `false`, `0`, `no` to disable                   |
| `CKVD_LOG_LEVEL`         | Control log verbosity   | `ERROR`           | `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG` |
| `CKVD_USE_POLARS_OUTPUT` | Zero-copy Polars output | `true`            | `false` to return pandas always                 |
