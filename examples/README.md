# Examples

Runnable examples demonstrating Crypto Kline Vision Data functionality.

## Quick Start

```bash
# Basic usage (BTCUSDT hourly data)
uv run -p 3.13 python examples/quick_start.py
```

## Example Categories

### Basic Usage

| Example          | Description               |
| ---------------- | ------------------------- |
| `quick_start.py` | Minimal FCP usage example |

### Advanced Patterns

| Example                                | Description                    |
| -------------------------------------- | ------------------------------ |
| `ckvd_lazy_initialization_demo.py`     | Lazy manager initialization    |
| `clean_feature_engineering_example.py` | Feature engineering pipeline   |
| `ckvd_logging_demo.py`                 | Logging configuration patterns |
| `ckvd_cache_control_example.py`        | Cache toggle mechanisms        |

### Synchronous Examples

| Example                         | Description                          |
| ------------------------------- | ------------------------------------ |
| `sync/ckvd_datetime_example.py` | Timezone handling and gap detection  |
| `sync/ckvd_one_second_test.py`  | One-second interval retrieval (SPOT) |

### Reference

| Directory     | Description                              |
| ------------- | ---------------------------------------- |
| `sync/`       | Synchronous data retrieval patterns      |
| `lib_module/` | Library integration guide (demo removed) |

## Telemetry Output

All examples emit structured **NDJSON telemetry** to `examples/logs/events.jsonl` via a shared `_telemetry.py` module. This makes example output machine-readable for AI coding agents.

### Parsing Telemetry

```bash
# View all events from the last run
cat examples/logs/events.jsonl | jq .

# Filter by event type
cat examples/logs/events.jsonl | jq 'select(.event_type == "fetch_completed")'

# Extract latency metrics
cat examples/logs/events.jsonl | jq 'select(.latency_ms) | {event: .event_type, ms: .latency_ms}'

# Filter by example name
cat examples/logs/events.jsonl | jq 'select(.example == "quick_start")'
```

### NDJSON Schema (v2 -- flat records)

Records are flat JSON objects with no nesting. Core fields from loguru, plus all
bound extra fields merged at top level.

| Field        | Always | Description                                |
| ------------ | ------ | ------------------------------------------ |
| `ts`         | Yes    | ISO 8601 timestamp                         |
| `level`      | Yes    | Log level (`DEBUG`, `INFO`, `ERROR`, etc.) |
| `msg`        | Yes    | Human-readable message                     |
| `file`       | Yes    | Project-relative source file path          |
| `function`   | Yes    | Caller function name                       |
| `line`       | Yes    | Source line number                         |
| `service`    | Yes    | `"ckvd-examples"`                          |
| `version`    | Yes    | Package version from `ckvd.__version__`    |
| `git_sha`    | Yes    | Short git SHA (or `"unknown"`)             |
| `python`     | Yes    | Python version string                      |
| `platform`   | Yes    | OS + arch (e.g. `"darwin-arm64"`)          |
| `trace_id`   | Yes    | 16-char hex per example run                |
| `example`    | Yes    | Example name (e.g. `"quick_start"`)        |
| `event_type` | Yes    | Domain event type                          |
| `span_id`    | No     | 8-char hex per logical operation           |
| `venue`      | No     | Exchange name (e.g. `"binance"`)           |
| `symbol`     | No     | Trading pair (e.g. `"BTCUSDT"`)            |
| `latency_ms` | No     | Operation duration in milliseconds         |
| `exception`  | No     | Exception info (when present)              |

### Shared Module

`_telemetry.py` provides `init_telemetry(example_name)` and `timed_span(tlog, event_type, **extra)` context manager. Import from any example.

## Running Examples

All examples use Python 3.13:

```bash
# Run any example
uv run -p 3.13 python examples/<example_name>.py

# Run with debug logging
CKVD_LOG_LEVEL=DEBUG uv run -p 3.13 python examples/quick_start.py

# Run with cache disabled
CKVD_ENABLE_CACHE=false uv run -p 3.13 python examples/ckvd_cache_control_example.py

# Run with py-spy profiling hint
CKVD_PYSPY_PROFILE=true uv run -p 3.13 python examples/quick_start.py
```

## Key Patterns

### Always Use UTC

```python
from datetime import datetime, timezone, timedelta

# CORRECT - timezone-aware UTC
end_time = datetime.now(timezone.utc)
start_time = end_time - timedelta(days=7)

# WRONG - naive datetime
end_time = datetime.now()  # No timezone info!
```

### Always Close Manager

```python
manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.FUTURES_USDT)
try:
    df = manager.get_data(symbol="BTCUSDT", ...)
finally:
    manager.close()  # Always cleanup
```

### Symbol Format by Market Type

| Market Type  | Symbol Format | Example       |
| ------------ | ------------- | ------------- |
| SPOT         | BTCUSDT       | `ETHUSDT`     |
| FUTURES_USDT | BTCUSDT       | `SOLUSDT`     |
| FUTURES_COIN | BTCUSD_PERP   | `ETHUSD_PERP` |

## Related Documentation

- [CLAUDE.md](/CLAUDE.md) - Main project reference
- [docs/skills/ckvd-usage/](/docs/skills/ckvd-usage/) - Usage skill with examples
- [docs/howto/ckvd_cache_control.md](/docs/howto/ckvd_cache_control.md) - Cache control guide
- [docs/TROUBLESHOOTING.md](/docs/TROUBLESHOOTING.md) - Common issues
