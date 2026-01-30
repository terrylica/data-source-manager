#!/usr/bin/env bash
# DSM Final Validation Hook (Stop)
# Runs final checks when Claude Code session ends or task completes
#
# Exit codes:
#   0 = success (summary provided via feedback)
#
# Output: JSON to stderr with feedback field

set -euo pipefail

# Change to project root
cd "${CLAUDE_PROJECT_ROOT:-$(pwd)}"

CHECKS_PASSED=0
CHECKS_FAILED=0
MESSAGES=()

# Check 1: Verify imports work
if uv run -p 3.13 python -c "from data_source_manager import DataSourceManager" >/dev/null 2>&1; then
    ((CHECKS_PASSED++))
else
    ((CHECKS_FAILED++))
    MESSAGES+=("❌ Import check failed - run: uv run -p 3.13 python -c 'from data_source_manager import DataSourceManager'")
fi

# Check 2: Quick lint check (non-blocking, just informational)
LINT_ERRORS=$(uv run -p 3.13 ruff check --select E722,BLE001,S110 . 2>/dev/null | wc -l || echo "0")
if [[ "$LINT_ERRORS" -gt 0 ]]; then
    MESSAGES+=("⚠️ Found $LINT_ERRORS silent failure patterns - run: mise run check:lint")
fi

# Only output feedback if there were issues
if [[ ${#MESSAGES[@]} -gt 0 ]]; then
    FEEDBACK="Session Summary:\\n"
    for msg in "${MESSAGES[@]}"; do
        FEEDBACK+="$msg\\n"
    done
    echo "{\"feedback\": \"$FEEDBACK\"}" >&2
fi

exit 0
