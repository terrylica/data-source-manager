#!/usr/bin/env bash
# DSM Bash Guard - PreToolUse hook for data-source-manager
# Validates bash commands before execution for DSM-specific safety
#
# Exit codes:
#   0 = allow execution
#   2 = block execution (sends stderr to Claude)

set -euo pipefail

# Read tool input from stdin
INPUT=$(cat)

# Extract command
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Skip if no command
if [[ -z "$COMMAND" ]]; then
    echo '{"decision": "allow"}'
    exit 0
fi

# Check 1: Block destructive cache operations without confirmation
if echo "$COMMAND" | grep -qE 'rm\s+-rf.*\.cache/data_source_manager'; then
    echo '{"decision": "block", "reason": "🛑 Destructive cache operation detected. Use mise run cache:clear instead."}' >&2
    exit 2
fi

# Check 2: Warn about Python version changes
if echo "$COMMAND" | grep -qE '(pyenv|mise)\s+(global|local)\s+python'; then
    echo '{"decision": "block", "reason": "🛑 Python version change detected. DSM requires Python 3.13 ONLY. Do not change the Python version."}' >&2
    exit 2
fi

# Check 3: Block force push to main/master
if echo "$COMMAND" | grep -qE 'git\s+push\s+.*(-f|--force).*\s+(main|master)'; then
    echo '{"decision": "block", "reason": "🛑 Force push to main/master is blocked. Use a feature branch instead."}' >&2
    exit 2
fi

# Check 4: Warn about direct pip install (prefer uv)
if echo "$COMMAND" | grep -qE '^pip\s+install'; then
    echo '{"decision": "block", "reason": "🛑 Direct pip install detected. Use uv for package management: uv add <package>"}' >&2
    exit 2
fi

# Check 5: Block git reset --hard without specific ref
if echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard\s*$'; then
    echo '{"decision": "block", "reason": "🛑 git reset --hard without ref is dangerous. Specify a commit hash or branch."}' >&2
    exit 2
fi

# Check 6: Ensure pytest uses Python 3.13
if echo "$COMMAND" | grep -qE 'pytest' && ! echo "$COMMAND" | grep -qE '(uv run -p 3\.13|uv run --python 3\.13)'; then
    if ! echo "$COMMAND" | grep -qE '^uv run'; then
        echo '{"decision": "allow", "message": "⚠️ pytest should use: uv run -p 3.13 pytest"}'
        exit 0
    fi
fi

# Allow the command
echo '{"decision": "allow"}'
exit 0
