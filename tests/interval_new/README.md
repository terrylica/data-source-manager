# New Interval Tests

## Overview

This directory contains tests for interval-based data retrieval functionality.

The tests focus on:

- Direct data filtering from Binance Vision API
- Basic API session handling
- Sample tests for interval functionality

## Tests in this Directory

The tests in this directory:

- `test_time_filtering.py` - Tests direct data filtering without relying on internal filtering functions
- `test_sample.py` - Contains sample tests for verification
- `conftest.py` - Contains fixtures for the tests

## Running Tests

As per the project guidelines, use the `scripts/run_tests_parallel.sh` script to run these tests:

```bash
scripts/run_tests_parallel.sh tests/interval_new INFO
```

## Test Migration Plan

For details on the plan to deprecate and remove `vision_data_client_enhanced.py`, see the migration plan in the root of this directory.
