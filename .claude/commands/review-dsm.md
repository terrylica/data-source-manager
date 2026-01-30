---
name: review-dsm
description: Review DSM code changes for common issues
---

# DSM Code Review

Review code changes against DSM-specific patterns and anti-patterns.

## Review Checklist

Use this checklist when reviewing changes to data-source-manager:

### Critical Checks

- [ ] **HTTP Timeout**: All HTTP requests have explicit `timeout=` parameter
- [ ] **UTC Timestamps**: Using `datetime.now(timezone.utc)`, not `datetime.now()`
- [ ] **Exception Handling**: No bare `except:` or `except Exception` in production
- [ ] **Symbol Format**: Symbol matches market type (BTCUSDT vs BTCUSD_PERP)

### Data Integrity

- [ ] **Index Validation**: DataFrames have monotonic increasing index
- [ ] **No Duplicates**: Index has no duplicate timestamps
- [ ] **UTC Timezone**: Index is timezone-aware (UTC)
- [ ] **OHLCV Sanity**: high >= low, volume >= 0

### FCP Compliance

- [ ] **Source Priority**: Respects Cache → Vision → REST order
- [ ] **Cache Updates**: New data is cached after retrieval
- [ ] **Error Fallback**: Errors trigger fallback to next source

## Commands

Review staged changes:

```bash
git diff --staged
```

Review specific file against patterns:

```bash
uv run -p 3.13 ruff check path/to/file.py --select E722,BLE001,S110
```

Run unit tests to verify changes:

```bash
uv run -p 3.13 pytest tests/unit/ -v -x
```

## Anti-Patterns to Flag

```python
# ❌ Missing timeout
response = requests.get(url)

# ❌ Naive datetime
now = datetime.now()

# ❌ Bare except
try:
    fetch()
except:
    pass

# ❌ Wrong symbol format
manager.get_data("BTCUSDT", ...)  # for FUTURES_COIN market
```

## Review Output

After reviewing, provide:

1. **Critical Issues** - Must fix before merge
2. **Warnings** - Should fix, but not blocking
3. **Suggestions** - Nice to have improvements
