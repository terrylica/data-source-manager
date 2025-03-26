#!/bin/bash
# Script to mark original test files as deprecated

set -e
echo "Marking original test files as deprecated..."

# API Boundary Tests
for file in tests/api_boundary/test_api_boundary_validator.py \
           tests/api_boundary/test_api_boundary_alignment.py \
           tests/api_boundary/test_api_boundary_edge_cases.py; do
    if [ -f "$file" ]; then
        echo "Marking as deprecated: $file"
        sed -i '1i# DEPRECATED: This file has been consolidated into test_api_boundary.py\n# Please use the consolidated test file instead\n' "$file"
    else
        echo "File not found: $file"
    fi
done

# Market Data Tests
for file in tests/interval_1s/test_market_api_integrity.py \
           tests/interval_1s/test_market_data_structure_validation.py; do
    if [ -f "$file" ]; then
        echo "Marking as deprecated: $file"
        sed -i '1i# DEPRECATED: This file has been consolidated into test_market_data_validation.py\n# Please use the consolidated test file instead\n' "$file"
    else
        echo "File not found: $file"
    fi
done

# Cache Tests
for file in tests/interval_1s/test_cache_core_functionality.py \
           tests/interval_1s/test_cache_dsm_core_operations.py \
           tests/interval_1s/test_dsm_vision_client_cache.py; do
    if [ -f "$file" ]; then
        echo "Marking as deprecated: $file"
        sed -i '1i# DEPRECATED: This file has been consolidated into test_cache_unified.py\n# Please use the consolidated test file instead\n' "$file"
    else
        echo "File not found: $file"
    fi
done

echo "All original test files have been marked as deprecated."
echo "After verifying the consolidated tests work correctly, remove these files using:"
echo "scripts/remove_deprecated_tests.sh" 