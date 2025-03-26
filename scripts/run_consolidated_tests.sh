#!/bin/bash
# Script to run all consolidated test files

set -e
echo "Running all consolidated test files..."

# Run API boundary tests
echo "======================================"
echo "Running API Boundary Tests"
echo "======================================"
./scripts/run_tests_parallel.sh tests/api_boundary/test_api_boundary.py

# Run Market Data Validation tests
echo "======================================"
echo "Running Market Data Validation Tests"
echo "======================================"
./scripts/run_tests_parallel.sh tests/interval_1s/test_market_data_validation.py

# Run Cache Unified tests
echo "======================================"
echo "Running Cache Unified Tests"
echo "======================================"
./scripts/run_tests_parallel.sh tests/interval_1s/test_cache_unified.py

echo "======================================"
echo "All consolidated tests completed"
echo "======================================" 