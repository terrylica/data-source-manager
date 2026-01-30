# Claude Code Settings Documentation

Human-readable documentation for DSM Claude Code configuration.

## Overview

This project uses Claude Code extensions for AI-assisted development:

- **5 Agents**: Specialized subagents for task delegation
- **6 Commands**: Slash commands for common workflows
- **7 Rules**: Domain-specific context loaded on demand
- **4 Skills**: Progressive disclosure documentation

## Active Configuration

### Agents

| Agent                 | Model  | Tools                  | Trigger Keywords                     |
| --------------------- | ------ | ---------------------- | ------------------------------------ |
| api-reviewer          | sonnet | Read, Grep, Glob       | "review", "API", "consistency"       |
| data-fetcher          | sonnet | Read, Grep, Glob, Bash | "fetch", "data", "market"            |
| fcp-debugger          | sonnet | Read, Grep, Glob, Bash | "FCP", "failover", "cache miss"      |
| silent-failure-hunter | sonnet | Read, Grep, Glob       | "silent", "except", "error handling" |
| test-writer           | sonnet | Read, Grep, Glob, Edit | "test", "pytest", "coverage"         |

### Commands

| Command        | Side Effects | Description                  |
| -------------- | ------------ | ---------------------------- |
| /debug-fcp     | Yes          | Run FCP diagnostic scripts   |
| /fetch-data    | Yes          | Fetch real market data       |
| /quick-test    | Yes          | Run actual tests             |
| /feature-dev   | No           | Guided feature development   |
| /review-dsm    | No           | Review code against patterns |
| /validate-data | No           | Validate DataFrame structure |

Commands with side effects have `disable-model-invocation: true`.

### Rules

Claude loads these rules on demand based on context:

| Rule                    | Triggers When Discussing             |
| ----------------------- | ------------------------------------ |
| binance-api.md          | API calls, rate limits, endpoints    |
| caching-patterns.md     | Cache, Arrow files, mmap             |
| dataframe-operations.md | DataFrame, Polars, OHLCV             |
| error-handling.md       | Exceptions, try/except, recovery     |
| fcp-protocol.md         | FCP, failover, data source selection |
| symbol-formats.md       | Symbol validation, market types      |
| timestamp-handling.md   | datetime, timezone, UTC              |

### Skills (in docs/skills/)

| Skill           | Context | Agent   | Purpose                        |
| --------------- | ------- | ------- | ------------------------------ |
| dsm-usage       | -       | -       | DataSourceManager API guide    |
| dsm-testing     | -       | -       | Testing patterns and pytest    |
| dsm-research    | fork    | Explore | Codebase research (subagent)   |
| dsm-fcp-monitor | -       | -       | FCP monitoring and diagnostics |

## Hooks Configuration

Project hooks are in `.claude/hooks/hooks.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_ROOT}/.claude/hooks/dsm-code-guard.sh"
          }
        ]
      }
    ]
  }
}
```

### Code Guard Checks

The `dsm-code-guard.sh` hook validates:

| Check             | Pattern              | Severity |
| ----------------- | -------------------- | -------- |
| Bare except       | `except:`            | CRITICAL |
| Generic Exception | `except Exception`   | HIGH     |
| Silent pass       | `except: pass`       | CRITICAL |
| Naive datetime    | `datetime.now()`     | HIGH     |
| Missing timeout   | HTTP without timeout | HIGH     |

## Verification

Run infrastructure validation:

```bash
# Verify Claude Code setup
uv run -p 3.13 python docs/skills/dsm-usage/scripts/validate_infrastructure.py
```

## Related

- [CLAUDE.md](/CLAUDE.md) - Main instructions
- [.claude/README.md](README.md) - Directory overview
- [Design spec](/docs/design/2026-01-30-claude-code-infrastructure/spec.md) - Full implementation details
