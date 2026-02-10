# Claude Code Infrastructure

This directory contains Claude Code extensions for AI-assisted development of crypto-kline-vision-data.

## Directory Structure

```
.claude/
├── settings.json    # Permission rules (team-shared)
├── settings.md      # Human-readable config documentation
├── agents/          # Specialized subagents
└── commands/        # Slash commands
```

## Settings

**`.claude/settings.json`** - Permission rules for tool access control.

| Rule Type | Effect                          | Example            |
| --------- | ------------------------------- | ------------------ |
| allow     | Permit matching tool calls      | `Bash(uv run *)`   |
| deny      | Block regardless of other rules | `Read(.env*)`      |
| ask       | Prompt for approval             | `Bash(git push *)` |

**Key denials**:

- `.env*`, `.mise.local.toml` - Secret files
- `Bash(pip install *)` - Use uv instead
- `Bash(git push --force *)` - Dangerous git operations
- `Bash(python3.14 *)`, `Bash(python3.12 *)` - Wrong Python version

**Personal overrides**: Use `.claude/settings.local.json` (gitignored).

**Plugin marketplace**: `cc-skills` is configured via `extraKnownMarketplaces`.

## Agents

Agents run in separate context windows for specialized tasks.

| Agent                 | Color  | Purpose                                | Tools                        |
| --------------------- | ------ | -------------------------------------- | ---------------------------- |
| api-reviewer          | red    | Reviews code for API consistency       | Read, Grep, Glob             |
| data-fetcher          | green  | Fetches data with proper FCP handling  | Read, Grep, Glob, Bash       |
| test-writer           | blue   | Writes tests following CKVD patterns   | Read, Write, Edit, Bash, ... |
| silent-failure-hunter | red    | Finds silent failures and bare excepts | Read, Grep, Glob             |
| fcp-debugger          | yellow | Diagnoses FCP issues                   | Read, Grep, Glob, Bash       |

**Usage:**

```
"Use the silent-failure-hunter agent to review this code"
"Launch fcp-debugger to investigate the cache miss"
```

## Commands

Slash commands for common workflows.

| Command      | Purpose                           |
| ------------ | --------------------------------- |
| /review-ckvd | Review code against CKVD patterns |
| /feature-dev | Guided feature development        |

## Domain Context

Domain-specific rules (Binance API, exceptions, symbols, timestamps, caching, FCP) are in [src/CLAUDE.md](/src/CLAUDE.md) — loaded on demand when working with source code.

## Architecture Pattern

This infrastructure follows the **CKVD Claude Code Infrastructure Pattern**, which can be adopted by other projects.

### Component Hierarchy

```
.claude/                    # Claude Code extensions (team-shared)
├── settings.json           # Permission rules (committed)
├── settings.local.json     # Personal overrides (gitignored)
├── agents/                 # 5 specialized subagents
│   ├── {name}.md           # YAML frontmatter + instructions
│   └── ...
└── commands/               # 2 slash commands
    ├── {name}.md           # YAML frontmatter + workflow
    └── ...
```

Domain-specific context (Binance API, FCP, exceptions, symbols, timestamps, caching) lives in nested CLAUDE.md spokes — see [src/CLAUDE.md](/src/CLAUDE.md).

### Adoption Checklist

| Component     | Required | Purpose                           |
| ------------- | -------- | --------------------------------- |
| settings.json | Yes      | Team permission rules             |
| agents/       | Optional | Specialized task delegation       |
| commands/     | Optional | Repeatable workflows              |
| CLAUDE.md     | Yes      | Hub-and-spoke progressive context |

### Design Principles

1. **Separation of concerns**: Each component has single responsibility
2. **Team-shareable**: Commit settings.json, gitignore settings.local.json
3. **Progressive disclosure**: Domain context in nested CLAUDE.md spokes, loaded on demand
4. **Safety first**: Deny rules for secrets, dangerous operations

## Related Documentation

- [CLAUDE.md](/CLAUDE.md) - Main project instructions
- [docs/INDEX.md](/docs/INDEX.md) - Documentation navigation
- [docs/skills/](/docs/skills/) - Progressive disclosure skills
- [ADR](/docs/adr/2026-01-30-claude-code-infrastructure.md) - Infrastructure decision record
