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

| Agent                 | Color  | Tools                  | Trigger Keywords                     |
| --------------------- | ------ | ---------------------- | ------------------------------------ |
| api-reviewer          | red    | Read, Grep, Glob       | "review", "API", "consistency"       |
| data-fetcher          | green  | Read, Grep, Glob, Bash | "fetch", "data", "market"            |
| fcp-debugger          | yellow | Read, Grep, Glob, Bash | "FCP", "failover", "cache miss"      |
| silent-failure-hunter | red    | Read, Grep, Glob       | "silent", "except", "error handling" |
| test-writer           | blue   | Read, Bash, Grep, Glob | "test", "pytest", "coverage"         |

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

| Skill           | Context | Agent   | allowed-tools          | Purpose                        |
| --------------- | ------- | ------- | ---------------------- | ------------------------------ |
| dsm-usage       | -       | -       | Read, Bash             | DataSourceManager API guide    |
| dsm-testing     | -       | -       | Read, Bash, Grep, Glob | Testing patterns and pytest    |
| dsm-research    | fork    | Explore | (agent's tools)        | Codebase research (subagent)   |
| dsm-fcp-monitor | fork    | -       | Read, Bash, Grep, Glob | FCP monitoring and diagnostics |

## Hooks Configuration

Project hooks are in `.claude/hooks/hooks.json`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "matcher": ".*", "hooks": [{ "command": "dsm-skill-suggest.sh" }] }
    ],
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [{ "command": "dsm-bash-guard.sh" }] }
    ],
    "PostToolUse": [
      { "matcher": "Write|Edit", "hooks": [{ "command": "dsm-code-guard.sh" }] }
    ],
    "Stop": [{ "hooks": [{ "command": "dsm-final-check.sh" }] }]
  }
}
```

### Skill Suggest (UserPromptSubmit)

The `dsm-skill-suggest.sh` hook provides suggestions based on prompt keywords:

| Keyword             | Suggested Skill  |
| ------------------- | ---------------- |
| fetch, data, klines | /dsm-usage       |
| test, pytest, mock  | /dsm-testing     |
| FCP, cache miss     | /dsm-fcp-monitor |
| how does, explore   | /dsm-research    |

### Bash Guard (PreToolUse)

The `dsm-bash-guard.sh` blocks dangerous operations:

| Blocked               | Reason                     |
| --------------------- | -------------------------- |
| Cache deletion        | Use `mise run cache:clear` |
| Python version change | DSM requires 3.13 ONLY     |
| Force push to main    | Use feature branches       |
| Direct pip install    | Use `uv add`               |

### Code Guard (PostToolUse)

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

# Or via mise
mise run claude:validate
```

## Authoring Checklist

From [Anthropic best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):

### Core Quality

- [x] Descriptions include what skill does AND when to use it
- [x] SKILL.md body under 500 lines (largest: 154 lines)
- [x] Consistent terminology throughout
- [x] File references one level deep
- [x] Third-person descriptions (not "I" or "You")
- [x] Workflow checklists for complex operations

### Structure

- [x] CLAUDE.md under 300 lines (currently 290)
- [x] Side-effect commands have `disable-model-invocation: true`
- [x] Skills have `user-invocable: true` and `$ARGUMENTS`
- [x] Agents have explicit `tools` field (prevents inheriting all tools)
- [x] Domain-specific CLAUDE.md files (src/, docs/, examples/, tests/) for lazy loading
- [x] 5 hooks: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop

### Testing

- [x] Unit tests pass (19/19)
- [x] Infrastructure validation passes (23/23 checks)

## Related

- [CLAUDE.md](/CLAUDE.md) - Main instructions
- [.claude/README.md](README.md) - Directory overview
- [Design spec](/docs/design/2026-01-30-claude-code-infrastructure/spec.md) - Full implementation details
