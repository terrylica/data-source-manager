# dsm-fcp-monitor Evolution Log

Reverse-chronological log of skill improvements.

---

## 2026-01-30: Added adr field and evolution-log

**Trigger**: Adopting cc-skills patterns for skill self-evolution

**Changes**:

- Added `adr: docs/adr/2025-01-30-failover-control-protocol.md` to frontmatter
- Created `references/evolution-log.md` for tracking improvements
- Added link to evolution-log in Related section

**Rationale**: Skills should link to architectural decisions and track their own improvement history for maintainability.

---

## 2026-01-30: Initial skill creation

**Source**: Claude Code infrastructure ADR

**Features**:

- FCP decision flow diagram
- Common issues and diagnostics
- Performance optimization patterns
- Cache warm-up examples
- Script references (cache_health.py, fcp_stats.py, warm_cache.py)

**Frontmatter**:

- `context: fork` for diagnostic isolation
- `allowed-tools: Read, Bash, Grep, Glob`
- `TRIGGERS` keywords for Claude invocation matching
