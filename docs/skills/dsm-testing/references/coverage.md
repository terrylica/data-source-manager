# Coverage Configuration Reference

pytest-cov configuration for DataSourceManager.

## Current Configuration

From `pyproject.toml`:

```toml
[tool.coverage.run]
branch = true
source = ["src/data_source_manager"]
omit = [
    "*/tests/*",
    "*/test_*.py",
    "*/__init__.py",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
show_missing = true
```

## Running Coverage

### Quick Coverage

```bash
# Unit tests only (fast)
uv run -p 3.13 pytest tests/unit/ --cov=src/data_source_manager --cov-report=term-missing

# All tests
uv run -p 3.13 pytest tests/ --cov=src/data_source_manager --cov-report=term-missing
```

### Coverage Reports

```bash
# Terminal report with missing lines
--cov-report=term-missing

# HTML report (opens in browser)
--cov-report=html

# XML report (for CI)
--cov-report=xml

# Combined reports
--cov-report=term-missing --cov-report=html
```

### Coverage Thresholds

```bash
# Fail if coverage drops below threshold
uv run -p 3.13 pytest tests/unit/ --cov=src/data_source_manager --cov-fail-under=80
```

## Module Coverage Breakdown

Key modules to maintain coverage for:

| Module                        | Target | Notes                        |
| ----------------------------- | ------ | ---------------------------- |
| `core/sync/`                  | 70%+   | Main DSM logic               |
| `utils/market_constraints.py` | 90%+   | Pure functions, easy to test |
| `providers/`                  | 60%+   | Provider-specific logic      |

## Excluding Code

Use `# pragma: no cover` for code that cannot be tested:

```python
def unreachable_branch():
    if impossible_condition:  # pragma: no cover
        return
```

## Branch Coverage

`branch = true` ensures both `if/else` paths are tested:

```python
def get_value(flag):
    if flag:  # Branch 1
        return "yes"
    else:     # Branch 2
        return "no"

# Both paths must be tested for 100% branch coverage
```
