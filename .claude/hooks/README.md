# CKVD Hooks

Project-specific Claude Code hooks for crypto-kline-vision-data.

## Available Hooks

### ckvd-session-start.sh (SessionStart)

Loads FCP context at session start for immediate awareness.

**Context Injected:**

- FCP priority (Cache → Vision → REST)
- Key code patterns (UTC, timeouts, symbol formats)
- Quick command references

**Behavior**: Adds context to Claude's initial state (stdout → context).

### ckvd-skill-suggest.sh (UserPromptSubmit)

Analyzes user prompts and suggests relevant CKVD skills based on keywords.

**Trigger Keywords:**

| Skill           | Keywords                                          |
| --------------- | ------------------------------------------------- |
| ckvd-usage       | fetch, data, klines, OHLCV, market data, Binance  |
| ckvd-testing     | test, pytest, mock, fixture, coverage             |
| ckvd-fcp-monitor | FCP, failover, cache miss/hit, slow, diagnos      |
| ckvd-research    | how does, understand, find, explore, architecture |

**Behavior**: Provides suggestions via feedback (non-blocking).

### ckvd-bash-guard.sh (PreToolUse)

Validates bash commands BEFORE execution for CKVD-specific safety.

**Blocked Operations (exit code 2):**

| Pattern                               | Reason                             |
| ------------------------------------- | ---------------------------------- |
| `rm -rf .cache/ckvd`   | Use `mise run cache:clear` instead |
| Python version changes via pyenv/mise | CKVD requires Python 3.13 ONLY      |
| Force push to main/master             | Use feature branches               |
| Direct `pip install`                  | Use `uv add <package>`             |
| `git reset --hard` without ref        | Dangerous without explicit commit  |

**Warnings:**

- pytest without `uv run -p 3.13`

### ckvd-code-guard.sh (PostToolUse)

Detects silent failure patterns in Python code AFTER file writes.

**General Python Patterns:**

- **E722**: Bare `except:` clause
- **BLE001**: Generic `except Exception`
- **S110**: Silent `except: pass`
- **PLW1510**: subprocess without `check=True`

**CKVD-Specific Patterns:**

- Naive `datetime.now()` without timezone
- HTTP requests without explicit `timeout=`
- `CryptoKlineVisionData.create()` without `manager.close()`
- Async functions using sync `CryptoKlineVisionData` (mixing patterns)
- COIN-margined symbol format (`_PERP`) with wrong market type
- Returning DataFrame without validation (`len(df) > 0` or `df.empty`)
- Using Pandas when Polars preferred (informational, use `# polars-exception` to suppress)

## Hook Configuration

The hooks are configured in `hooks.json` with descriptions and notes:

```json
{
  "description": "CKVD-specific hooks - enforces FCP patterns, silent failure detection",
  "notes": [
    "SessionStart: Loads FCP context into every session",
    "PreToolUse: BLOCKS dangerous operations",
    "PostToolUse: WARNS about silent failure patterns"
  ],
  "hooks": {
    "SessionStart": [
      {
        "description": "Load FCP context at session start",
        "hooks": [{ "command": "ckvd-session-start.sh" }]
      }
    ],
    "PreToolUse": [
      {
        "description": "Block dangerous Bash commands",
        "matcher": "Bash",
        "hooks": [{ "command": "ckvd-bash-guard.sh" }]
      }
    ]
  }
}
```

Each hook entry supports a `description` field for documentation purposes.

## Exit Codes

| Code | Meaning                                   |
| ---- | ----------------------------------------- |
| 0    | Allow execution                           |
| 2    | Block execution (sends message to Claude) |

## Code Correctness Philosophy

**Principle**: Only check for **silent failure patterns** - code that fails without visible errors.

### Rules Checked (Runtime Bugs)

| Rule    | Pattern                    | Why Checked                      |
| ------- | -------------------------- | -------------------------------- |
| E722    | Bare `except:`             | Swallows SystemExit, KeyboardInt |
| S110    | `except: pass`             | Silent failure, data integrity   |
| BLE001  | `except Exception`         | Too broad, hides specific errors |
| PLW1510 | subprocess without `check` | Silent command failures          |

### Rules NOT Checked (Cosmetic)

| Rule | Pattern          | Why NOT Checked                     |
| ---- | ---------------- | ----------------------------------- |
| F401 | Unused imports   | Development-in-progress, re-exports |
| F841 | Unused variables | IDE responsibility                  |
| I    | Import sorting   | Pre-commit/IDE handles              |
| E/W  | PEP8 style       | Not a runtime issue                 |

### Rationale

**Unused imports are NOT checked** because:

1. Development-in-progress (imports before code)
2. Intentional re-exports (`__init__.py`)
3. Type-only imports (`TYPE_CHECKING`)
4. IDE/pre-commit responsibility, not interactive hooks

Following [cc-skills Code Correctness Policy](https://github.com/terrylica/cc-skills/blob/main/plugins/itp-hooks/CLAUDE.md#code-correctness-philosophy)

### ckvd-final-check.sh (Stop)

Runs final validation when Claude Code session ends or task completes.

**Checks Performed:**

| Check        | Purpose                               |
| ------------ | ------------------------------------- |
| Import check | Verify `CryptoKlineVisionData` importable |
| Lint check   | Report silent failure patterns        |

**Behavior**: Provides summary via feedback (non-blocking).

## Related

- [Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Code Hooks Best Practices](https://www.datacamp.com/tutorial/claude-code-hooks)
