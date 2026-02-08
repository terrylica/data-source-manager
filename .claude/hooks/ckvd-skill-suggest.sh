#!/usr/bin/env bash
# CKVD Skill Suggestion Hook (UserPromptSubmit)
# Analyzes user prompts and suggests relevant CKVD skills
#
# Exit codes:
#   0 = success (suggestions provided via feedback)
#
# Output: JSON to stderr with feedback field

set -euo pipefail

# Get the user's prompt from stdin (JSONL format)
INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""' 2>/dev/null || echo "")

# Convert to lowercase for matching
PROMPT_LOWER=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

SUGGESTIONS=()

# ckvd-usage triggers
if echo "$PROMPT_LOWER" | grep -qE 'fetch|data|klines|ohlcv|market data|datasourcemanager|binance|vision api|rest api|get_data'; then
    SUGGESTIONS+=("💡 Consider: /ckvd-usage [symbol] - Fetch market data with FCP")
fi

# ckvd-testing triggers
if echo "$PROMPT_LOWER" | grep -qE 'test|pytest|mock|fixture|coverage|unit test|integration test|marker'; then
    SUGGESTIONS+=("💡 Consider: /ckvd-testing [pattern] - Run tests or write new tests")
fi

# ckvd-fcp-monitor triggers
if echo "$PROMPT_LOWER" | grep -qE 'fcp|failover|cache (miss|hit|problem)|slow|performance|vision error|rest fallback|diagnos'; then
    SUGGESTIONS+=("💡 Consider: /ckvd-fcp-monitor [symbol] - Diagnose FCP behavior")
fi

# ckvd-research triggers
if echo "$PROMPT_LOWER" | grep -qE 'how does|understand|find|explore|architecture|pattern|implementation|code flow'; then
    SUGGESTIONS+=("💡 Consider: /ckvd-research [topic] - Research codebase architecture")
fi

# If no suggestions or prompt is empty, exit silently
if [[ ${#SUGGESTIONS[@]} -eq 0 ]] || [[ -z "$PROMPT" ]]; then
    exit 0
fi

# Build feedback message
FEEDBACK=$(printf "%s\n" "${SUGGESTIONS[@]}")

# Output JSON response to stderr
echo "{\"feedback\": \"$FEEDBACK\"}" >&2

exit 0
