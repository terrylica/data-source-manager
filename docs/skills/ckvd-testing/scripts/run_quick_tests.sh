#!/usr/bin/env bash
# Quick test runner for DSM
# Usage: ./run_quick_tests.sh [test_pattern]

set -euo pipefail

PATTERN="${1:-}"

echo "=== DSM Quick Test Runner ==="
echo ""

# Run lint check first
echo "1. Running lint check..."
if uv run -p 3.13 ruff check . --quiet 2>/dev/null; then
    echo "   ✓ Lint check passed"
else
    echo "   ✗ Lint check failed"
    echo "   Run: uv run -p 3.13 ruff check --fix ."
    exit 1
fi

echo ""

# Run unit tests
echo "2. Running unit tests..."
if [ -n "$PATTERN" ]; then
    echo "   Pattern: $PATTERN"
    uv run -p 3.13 pytest tests/unit/ -v -k "$PATTERN" --tb=short
else
    uv run -p 3.13 pytest tests/unit/ -v --tb=short
fi

echo ""

# Verify imports
echo "3. Verifying imports..."
if uv run -p 3.13 python -c "from data_source_manager import DataSourceManager; print('   ✓ Import OK')" 2>/dev/null; then
    :
else
    echo "   ✗ Import failed"
    exit 1
fi

echo ""
echo "=== All checks passed ==="
