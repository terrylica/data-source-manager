# DSM Hooks

Project-specific Claude Code hooks for data-source-manager.

## Available Hooks

### dsm-bash-guard.sh (PreToolUse)

Validates bash commands BEFORE execution for DSM-specific safety.

**Blocked Operations (exit code 2):**

| Pattern                               | Reason                             |
| ------------------------------------- | ---------------------------------- |
| `rm -rf .cache/data_source_manager`   | Use `mise run cache:clear` instead |
| Python version changes via pyenv/mise | DSM requires Python 3.13 ONLY      |
| Force push to main/master             | Use feature branches               |
| Direct `pip install`                  | Use `uv add <package>`             |
| `git reset --hard` without ref        | Dangerous without explicit commit  |

**Warnings:**

- pytest without `uv run -p 3.13`

### dsm-code-guard.sh (PostToolUse)

Detects silent failure patterns in Python code AFTER file writes.

**General Python Patterns:**

- **E722**: Bare `except:` clause
- **BLE001**: Generic `except Exception`
- **S110**: Silent `except: pass`
- **PLW1510**: subprocess without `check=True`

**DSM-Specific Patterns:**

- Naive `datetime.now()` without timezone
- HTTP requests without explicit `timeout=`
- `DataSourceManager.create()` without `manager.close()`
- Async functions using sync `DataSourceManager` (mixing patterns)
- COIN-margined symbol format (`_PERP`) with wrong market type

## Hook Configuration

The hooks are configured in `hooks.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "dsm-bash-guard.sh" }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [{ "type": "command", "command": "dsm-code-guard.sh" }]
      }
    ]
  }
}
```

## Exit Codes

| Code | Meaning                                   |
| ---- | ----------------------------------------- |
| 0    | Allow execution                           |
| 2    | Block execution (sends message to Claude) |

## Philosophy

Following the [Code Correctness Hook Policy](https://github.com/terrylica/cc-skills):

- **CHECK**: Silent failure patterns that can cause runtime bugs
- **DON'T CHECK**: Cosmetic issues like unused imports (IDE responsibility)

## Related

- [Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Code Hooks Best Practices](https://www.datacamp.com/tutorial/claude-code-hooks)
