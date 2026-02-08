---
name: ckvd-testing
description: Run tests for crypto-kline-vision-data with proper markers and coverage. TRIGGERS - write tests, run tests, pytest, test coverage, unit tests, integration tests, mocking patterns.
argument-hint: "[test-pattern]"
user-invocable: true
allowed-tools: Read, Bash, Grep, Glob
---

# Testing Crypto Kline Vision Data

Run tests for: $ARGUMENTS

## Test Workflow Checklist

Copy this checklist and track progress:

```
Test Progress:
- [ ] Step 1: Run lint check (ruff check)
- [ ] Step 2: Run unit tests (fast, no network)
- [ ] Step 3: Verify import works
- [ ] Step 4: Run integration tests (if changing APIs)
- [ ] Step 5: Check coverage (if adding new code)
```

**Step 1**: `uv run -p 3.13 ruff check --fix .`
**Step 2**: `uv run -p 3.13 pytest tests/unit/ -v`
**Step 3**: `uv run -p 3.13 python -c "from ckvd import CryptoKlineVisionData; print('OK')"`
**Step 4**: `uv run -p 3.13 pytest tests/integration/ -v` (if needed)
**Step 5**: `uv run -p 3.13 pytest tests/unit/ --cov=src/ckvd`

## Test Organization

```
tests/
├── unit/                    # Fast, no network (~0.5s)
├── integration/             # External services
├── okx/                     # OKX API integration
└── fcp_pm/                  # FCP protocol tests
```

## Running Tests

### Unit Tests (Fast)

```bash
# Quick validation
uv run -p 3.13 pytest tests/unit/ -v

# With coverage
uv run -p 3.13 pytest tests/unit/ --cov=src/ckvd --cov-report=term-missing
```

### Integration Tests

```bash
# Requires network access
uv run -p 3.13 pytest tests/integration/ -v

# OKX-specific tests
uv run -p 3.13 pytest tests/okx/ -m okx -v
```

### All Tests

```bash
uv run -p 3.13 pytest tests/ -v
```

## Test Markers

| Marker                     | Purpose                       |
| -------------------------- | ----------------------------- |
| `@pytest.mark.integration` | Tests that call external APIs |
| `@pytest.mark.okx`         | OKX-specific tests            |
| `@pytest.mark.serial`      | Must run sequentially         |

## Writing New Tests

```python
import pytest
from ckvd import CryptoKlineVisionData, DataProvider, MarketType

class TestMyFeature:
    """Tests for MyFeature."""

    def test_basic_functionality(self):
        """Verify basic operation."""
        # Arrange
        manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.SPOT)

        # Act
        result = manager.some_method()

        # Assert
        assert result is not None
        manager.close()

    @pytest.mark.integration
    def test_with_network(self):
        """Test requiring network access."""
        # Mark with @pytest.mark.integration for external calls
        pass
```

## Mocking HTTP Calls

```python
from unittest.mock import patch, MagicMock

@patch("ckvd.core.sync.crypto_kline_vision_data.FSSpecVisionHandler")
@patch("ckvd.core.sync.crypto_kline_vision_data.UnifiedCacheManager")
def test_with_mocks(self, mock_cache, mock_handler):
    mock_handler.return_value = MagicMock()
    mock_cache.return_value = MagicMock()
    # Test logic...
```

## Examples

Practical test examples:

- @examples/unit-test-patterns.md - Basic tests, fixtures, mocking
- @examples/integration-test-patterns.md - API tests, markers, FCP testing

## Helper Scripts

Quick test runner:

```bash
# Run all quick checks (lint + unit tests + import)
./docs/skills/ckvd-testing/scripts/run_quick_tests.sh

# Run with test pattern filter
./docs/skills/ckvd-testing/scripts/run_quick_tests.sh test_timestamp
```

## Detailed References

For deeper information, see:

- @references/fixtures.md - Pytest fixtures and auto-cleanup patterns
- @references/coverage.md - Coverage configuration and thresholds
- @references/mocking-patterns.md - CKVD-specific mocking patterns
- @references/markers.md - Pytest markers and test categorization
