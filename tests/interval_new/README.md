# New Interval Tests

## Status

Several tests that previously depended on the deprecated `vision_data_client_enhanced.py` file have been moved to `tests/deprecated/interval_new/`.

The following files have been moved to the deprecated directory:

- `test_vision_client_batch.py`
- `test_vision_client_enhanced.py`
- `test_vision_client_intervals.py`
- `test_vision_client_markets.py`
- `test_vision_client_schema.py`

The tests that remain in this directory:

- `test_time_filtering.py` - Tests direct data filtering without the enhanced client
- `test_sample.py` - Contains sample tests that do not depend on the enhanced client
- `conftest.py` - Contains fixtures for the remaining tests

This is part of the effort to remove dependency on `vision_data_client_enhanced.py` as described in the migration plan.

## Running Tests

As per the project guidelines, use the `scripts/run_tests_parallel.sh` script to run these tests:

```bash
scripts/run_tests_parallel.sh tests/interval_new INFO
```

## Test Migration Plan

For details on the plan to deprecate and remove `vision_data_client_enhanced.py`, see the migration plan in the root of this directory.
