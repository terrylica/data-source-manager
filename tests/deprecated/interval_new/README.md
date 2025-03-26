# Deprecated Vision Client Enhanced Tests

## Status

These test files have been deprecated because they depend on the deprecated `vision_data_client_enhanced.py` file. The functionality of `vision_data_client_enhanced.py` has been consolidated into `vision_data_client.py` and `data_source_manager.py`.

## Deprecated Files

The following files are deprecated:

- `test_vision_client_batch.py`
- `test_vision_client_enhanced.py`
- `test_vision_client_intervals.py`
- `test_vision_client_markets.py`
- `test_vision_client_schema.py`

## Migration Plan

The functionality tested by these files is now covered by the consolidated tests:

- API Boundary Tests: `tests/api_boundary/test_api_boundary.py`
- Market Data Tests: `tests/interval_1s/test_market_data_validation.py`
- Cache Tests: `tests/interval_1s/test_cache_unified.py`

## Timeline

1. ✅ Deprecate `vision_data_client_enhanced.py` with notices
2. ✅ Move dependent tests to deprecated directory
3. ⏳ After all consolidated tests pass, remove `vision_data_client_enhanced.py`
4. ⏳ Remove deprecated test files

## Running Tests

These tests should not be run as they depend on deprecated code. If needed for reference, they can be run using:

```bash
scripts/run_tests_parallel.sh tests/deprecated/interval_new INFO
```

However, it's recommended to use the consolidated tests instead.
