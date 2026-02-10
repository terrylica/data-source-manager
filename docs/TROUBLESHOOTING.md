# Troubleshooting Guide

Common issues and solutions for Crypto Kline Vision Data.

## Quick Diagnostics

```bash
# Check imports
uv run -p 3.13 python -c "from ckvd import CryptoKlineVisionData; print('OK')"

# Check cache status
mise run cache:stats

# Enable debug logging
CKVD_LOG_LEVEL=DEBUG uv run -p 3.13 python your_script.py
```

## Common Issues

### Empty DataFrame Returned

**Symptoms**: `get_data()` returns DataFrame with 0 rows.

**Causes**:

1. Wrong symbol format for market type
2. Requesting future timestamps
3. Date range with no trading data

**Solutions**:

```python
# Check symbol format - raises ValueError with suggestion if invalid
from ckvd import MarketType
from ckvd.utils.market_constraints import validate_symbol_for_market_type

try:
    validate_symbol_for_market_type("BTCUSDT", MarketType.FUTURES_COIN)
except ValueError as e:
    print(e)  # "Invalid symbol format... Try using 'BTCUSD_PERP' instead."

# Check time range is in past
from datetime import datetime, timezone
assert end_time <= datetime.now(timezone.utc), "Cannot request future data"
```

### HTTP 403 Forbidden

**Symptoms**: Vision or REST API returns 403 error.

**Causes**:

1. Requesting data for future timestamps
2. Symbol doesn't exist on exchange
3. IP banned (rare)

**Solutions**:

- Verify timestamps are UTC and in the past
- Check symbol exists on Binance
- Wait 15 minutes if IP banned

### HTTP 429 Rate Limited

**Symptoms**: REST API returns 429 error.

**Causes**: Exceeded weight/minute limit (Spot: 6,000 / Futures: 2,400).

**Solutions**:

- Wait 60 seconds before retrying
- Use Vision API for bulk historical data
- Enable caching to reduce API calls

### Naive Datetime Errors

**Symptoms**: `TypeError: can't compare offset-naive and offset-aware datetimes`

**Cause**: Using `datetime.now()` instead of `datetime.now(timezone.utc)`.

**Solution**:

```python
# Wrong
from datetime import datetime
now = datetime.now()

# Correct
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
```

### Import Errors

**Symptoms**: `ModuleNotFoundError: No module named 'ckvd'`

**Solutions**:

```bash
# Reinstall in editable mode
uv pip install -e ".[dev]"

# Or sync dependencies
uv sync --dev
```

### Cache Corruption

**Symptoms**: Unexpected data, partial results, or read errors from cache.

**Solutions**:

```bash
# Clear cache
mise run cache:clear

# Or manually (macOS path via platformdirs)
rm -rf ~/Library/Caches/crypto-kline-vision-data
```

## Debug Mode

Enable verbose logging to see FCP decisions:

```python
import os
os.environ["CKVD_LOG_LEVEL"] = "DEBUG"

from ckvd import CryptoKlineVisionData, DataProvider, MarketType

# Now get_data() logs:
# DEBUG - Cache hit for 2024-01-01
# DEBUG - Cache miss for 2024-01-02, trying Vision
# DEBUG - Vision API downloaded 2024-01-02
# DEBUG - REST fallback for 2024-01-03 (recent data)
```

## FCP Source Verification

Force specific data source for debugging by passing `enforce_source` to `get_data()`:

```python
from datetime import datetime, timedelta, timezone
from ckvd import CryptoKlineVisionData, DataProvider, MarketType, Interval
from ckvd.core.sync.ckvd_types import DataSource

manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.FUTURES_USDT)

end = datetime.now(timezone.utc)
start = end - timedelta(days=7)

# Force Vision only (skip cache)
df = manager.get_data(
    symbol="BTCUSDT",
    start_time=start,
    end_time=end,
    interval=Interval.HOUR_1,
    enforce_source=DataSource.VISION
)

# Force REST only (skip cache and Vision)
df = manager.get_data(
    symbol="BTCUSDT",
    start_time=start,
    end_time=end,
    interval=Interval.HOUR_1,
    enforce_source=DataSource.REST
)

# Force cache only (offline mode - no API calls)
df = manager.get_data(
    symbol="BTCUSDT",
    start_time=start,
    end_time=end,
    interval=Interval.HOUR_1,
    enforce_source=DataSource.CACHE
)

manager.close()
```

## Cache Toggle Issues

### Cache Not Disabled by Environment Variable

**Symptoms**: `CKVD_ENABLE_CACHE=false` set but cache still active.

**Causes**:

1. Env var set **after** importing CKVD
2. Typo in variable name or value

**Solutions**:

```python
# Set BEFORE importing CKVD
import os
os.environ["CKVD_ENABLE_CACHE"] = "false"

from ckvd import CryptoKlineVisionData  # Now picks up env var

# Accepted disable values (case-insensitive): "false", "0", "no"
```

### enforce_source=CACHE + use_cache=False Contradiction

**Symptoms**: `RuntimeError: Cannot use enforce_source=DataSource.CACHE when use_cache=False`

**Cause**: Requesting cache-only mode on a manager with cache disabled.

**Solution**: Use a compatible combination:

| `enforce_source` | `use_cache=False` | Result                       |
| ---------------- | ----------------- | ---------------------------- |
| `AUTO`           | Works             | Vision -> REST (skips cache) |
| `VISION`         | Works             | Vision API only              |
| `REST`           | Works             | REST API only                |
| `CACHE`          | **RuntimeError**  | Logical contradiction        |

### Cache Disabled Unexpectedly

**Symptoms**: Data always fetched from API, no cache files created.

**Diagnostic**:

```python
# Check if env var is set somewhere
import os
print(f"CKVD_ENABLE_CACHE = {os.environ.get('CKVD_ENABLE_CACHE', '(not set)')}")

# Check manager state
manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.SPOT)
print(f"use_cache = {manager.use_cache}")
manager.close()
```

See [Cache Control Guide](howto/ckvd_cache_control.md) for comprehensive usage.

## Telemetry Issues

### No events.jsonl File Created

**Symptoms**: Running an example produces no `examples/logs/events.jsonl`.

**Causes**:

1. Example not using `_telemetry.py` (pre-telemetry example)
2. File permission issue on `examples/logs/` directory

**Solutions**:

```bash
# Verify telemetry output
uv run -p 3.13 python examples/quick_start.py
cat examples/logs/events.jsonl | jq . | head -5
```

### Telemetry Stops After CryptoKlineVisionData.create()

**Symptoms**: Events stop appearing in `events.jsonl` after manager creation.

**Cause**: CKVD's `loguru_setup.py` calls `logger.remove()` which destroys all sinks.

**Solution**: This is handled automatically by `ResilientLogger` in `_telemetry.py`. Ensure you use `init_telemetry()` (not raw loguru) in examples. See [examples/CLAUDE.md](/examples/CLAUDE.md#resilientlogger) for details.

### Correlating Events Across Runs

Use `trace_id` to group events from a single run, and `span_id` to match fetch start/complete pairs:

```bash
# All events from one run
cat examples/logs/events.jsonl | jq 'select(.trace_id == "YOUR_TRACE_ID")'

# Match fetch spans
cat examples/logs/events.jsonl | jq 'select(.span_id == "cb72ce8f")'
```

## Getting Help

1. Check [FCP Protocol Reference](skills/ckvd-usage/references/fcp-protocol.md)
2. Review [Market Types](skills/ckvd-usage/references/market-types.md)
3. Enable debug logging and check output
4. Run `/debug-fcp SYMBOL` command in Claude Code
