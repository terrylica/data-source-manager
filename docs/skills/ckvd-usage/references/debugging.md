# DSM Debugging Reference

Comprehensive debugging techniques for DataSourceManager issues.

## Enable Debug Logging

### Method 1: Environment Variable

```bash
DSM_LOG_LEVEL=DEBUG uv run -p 3.13 python your_script.py
```

### Method 2: Programmatic

```python
import logging
logging.getLogger("data_source_manager").setLevel(logging.DEBUG)

# Or with structlog
import structlog
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG)
)
```

### Method 3: Manager Configuration

```python
from data_source_manager import DataSourceManager, DataProvider, MarketType

manager = DataSourceManager.create(
    DataProvider.BINANCE,
    MarketType.FUTURES_USDT,
    log_level="DEBUG"
)
```

## Common Issues

### 1. Empty DataFrame Returned

**Symptoms**: `df` is empty, no error raised.

**Diagnostic steps**:

```python
# Check if symbol exists
from data_source_manager.utils.market_constraints import validate_symbol_for_market_type

try:
    validate_symbol_for_market_type("BTCUSDT", MarketType.FUTURES_USDT)
except ValueError as e:
    print(f"Invalid symbol: {e}")

# Check time range
from datetime import datetime, timezone
print(f"Start: {start_time} (UTC: {start_time.tzinfo})")
print(f"End: {end_time} (UTC: {end_time.tzinfo})")
print(f"Now: {datetime.now(timezone.utc)}")

# Verify symbol was listed by start_time
# Some symbols don't have full historical data
```

### 2. Cache Not Being Used

**Symptoms**: Always hitting REST API, slow performance.

**Diagnostic steps**:

```bash
# Check cache directory
ls -la ~/.cache/data_source_manager/binance/futures_usdt/klines/daily/BTCUSDT/1h/

# Run FCP diagnostic
uv run -p 3.13 python docs/skills/dsm-usage/scripts/diagnose_fcp.py BTCUSDT futures_usdt 1h
```

**Common causes**:

- Cache directory permissions
- Different interval than cached
- Date range outside cached data

### 3. Vision API 403 Errors

**Symptoms**: "403 Forbidden" in debug logs.

**Cause**: Binance Vision API has IP restrictions.

**Solution**: FCP automatically falls back to REST. If you need Vision:

- Verify IP is not blocked
- Check if Vision bucket is accessible from your region

### 4. Rate Limit Errors

**Symptoms**: `RateLimitError` or 429 responses.

**Diagnostic**:

```python
# Check current rate limit status
import httpx
response = httpx.get("https://api.binance.com/api/v3/exchangeInfo")
print(f"X-MBX-USED-WEIGHT: {response.headers.get('x-mbx-used-weight-1m')}")
```

**Solution**:

```python
import time
# Wait before retrying
time.sleep(60)

# Or use smaller batches
for chunk in date_chunks(start, end, chunk_days=30):
    df_chunk = manager.get_data(symbol="BTCUSDT", start_time=chunk[0], end_time=chunk[1])
    time.sleep(1)  # Rate limit friendly
```

### 5. Timezone Issues

**Symptoms**: Wrong data returned, off-by-hours errors.

**Diagnostic**:

```python
from datetime import datetime, timezone

# Always check timezone awareness
dt = datetime.now()
print(f"Naive: {dt}, tzinfo: {dt.tzinfo}")  # None = BAD

dt_utc = datetime.now(timezone.utc)
print(f"UTC: {dt_utc}, tzinfo: {dt_utc.tzinfo}")  # timezone.utc = GOOD
```

**Fix**: Always use `timezone.utc`:

```python
from datetime import datetime, timezone, timedelta

end_time = datetime.now(timezone.utc)
start_time = end_time - timedelta(days=7)
```

## Performance Profiling

### Time Individual Operations

```python
import time

start = time.perf_counter()
df = manager.get_data(symbol="BTCUSDT", ...)
elapsed = time.perf_counter() - start
print(f"Fetch took {elapsed:.2f}s")
```

### Profile FCP Sources

```python
import logging
logging.getLogger("data_source_manager").setLevel(logging.DEBUG)

# Watch for log entries like:
# DEBUG - Cache hit for BTCUSDT 1h 2024-01-15
# DEBUG - Vision fetch for BTCUSDT 1h 2024-01-14
# DEBUG - REST fetch for BTCUSDT 1h 2024-01-16
```

## Diagnostic Scripts

Available in `docs/skills/dsm-usage/scripts/`:

| Script               | Purpose                     |
| -------------------- | --------------------------- |
| `validate_symbol.py` | Check symbol format         |
| `check_cache.py`     | Inspect local cache         |
| `diagnose_fcp.py`    | Full FCP diagnostic logging |
