# Synchronous Examples

Python examples demonstrating synchronous CKVD data retrieval patterns.

## Examples

| Script                     | Purpose                                                     |
| -------------------------- | ----------------------------------------------------------- |
| `ckvd_datetime_example.py` | Timezone-aware datetime handling, gap detection, reindexing |
| `ckvd_one_second_test.py`  | One-second interval data retrieval (SPOT only)              |

## Running

```bash
# DateTime handling patterns
uv run -p 3.13 python examples/sync/ckvd_datetime_example.py

# One-second interval test
uv run -p 3.13 python examples/sync/ckvd_one_second_test.py
```

## Telemetry Output

Both examples emit structured NDJSON telemetry to `examples/logs/events.jsonl` via the shared `_telemetry.py` module (imported from parent `examples/` directory).

```bash
# Parse telemetry from sync examples
cat examples/logs/events.jsonl | jq 'select(.example == "datetime_example")'
cat examples/logs/events.jsonl | jq 'select(.example == "one_second_test")'
```

## Key Patterns

These examples demonstrate:

1. **Timezone-aware datetimes** - Always `datetime.now(timezone.utc)`
2. **Data completeness checks** - Detecting gaps in retrieved data
3. **Safe reindexing** - Forward-filling missing data for analysis
4. **Window calculations** - Moving averages with completeness checks
5. **Sub-minute intervals** - One-second data (SPOT market only)
6. **Structured telemetry** - Machine-readable NDJSON event output

## Related

- [Root examples/](../README.md) - All example categories
- [Cache control](../ckvd_cache_control_example.py) - Cache toggle mechanisms
- [docs/howto/](../../docs/howto/) - Step-by-step guides
