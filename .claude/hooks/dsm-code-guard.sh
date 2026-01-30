#!/usr/bin/env bash
# DSM Code Guard - PostToolUse hook for data-source-manager
# Detects silent failure patterns specific to market data code

set -euo pipefail

# Read tool input from stdin
INPUT=$(cat)

# Extract file path and content
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
CONTENT=$(echo "$INPUT" | jq -r '.tool_input.content // .tool_input.new_string // empty')

# Skip if no Python file
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
    echo '{"decision": "allow"}'
    exit 0
fi

WARNINGS=()

# Check 1: Bare except (E722)
if echo "$CONTENT" | grep -q 'except:$'; then
    WARNINGS+=("⚠️ Bare 'except:' detected - catch specific exceptions")
fi

# Check 2: except Exception (BLE001)
if echo "$CONTENT" | grep -qE 'except\s+Exception(\s|:)'; then
    WARNINGS+=("⚠️ 'except Exception' detected - use specific exceptions in production")
fi

# Check 3: except: pass (S110)
if echo "$CONTENT" | grep -qE 'except.*:\s*pass'; then
    WARNINGS+=("⚠️ 'except: pass' silently swallows errors")
fi

# Check 4: subprocess without check=True (PLW1510)
if echo "$CONTENT" | grep -qE 'subprocess\.(run|call|check_output)\(' && ! echo "$CONTENT" | grep -q 'check=True'; then
    WARNINGS+=("⚠️ subprocess call without check=True - errors may be silently ignored")
fi

# Check 5: Naive datetime (DSM-specific)
if echo "$CONTENT" | grep -qE 'datetime\.now\(\)' && ! echo "$CONTENT" | grep -q 'timezone'; then
    WARNINGS+=("⚠️ datetime.now() without timezone - use datetime.now(timezone.utc)")
fi

# Check 6: HTTP without timeout (DSM-specific)
if echo "$CONTENT" | grep -qE '(requests|httpx)\.(get|post|put|delete|patch)\(' && ! echo "$CONTENT" | grep -qE 'timeout\s*='; then
    WARNINGS+=("⚠️ HTTP request without explicit timeout parameter")
fi

# Check 7: DataSourceManager without close() (DSM-specific)
# Detect manager creation without matching close() call
if echo "$CONTENT" | grep -qE 'DataSourceManager\.create\(' && ! echo "$CONTENT" | grep -q '\.close()'; then
    # Only warn if not using context manager pattern
    if ! echo "$CONTENT" | grep -qE 'with\s+.*DataSourceManager'; then
        WARNINGS+=("⚠️ DataSourceManager.create() without manager.close() - consider using context manager or explicit close")
    fi
fi

# Check 8: Mixing sync and async patterns (DSM-specific)
if echo "$CONTENT" | grep -qE 'async\s+def' && echo "$CONTENT" | grep -qE 'DataSourceManager\.create\('; then
    WARNINGS+=("⚠️ Async function using sync DataSourceManager - consider async patterns for better performance")
fi

# Check 9: Hardcoded symbol format issues (DSM-specific)
# Check for BTCUSD_PERP with SPOT/FUTURES_USDT market type
if echo "$CONTENT" | grep -qE 'MarketType\.(SPOT|FUTURES_USDT)' && echo "$CONTENT" | grep -qE '"[A-Z]+USD_PERP"'; then
    WARNINGS+=("⚠️ COIN-margined symbol format (_PERP) used with SPOT/FUTURES_USDT market type")
fi

# Output result
if [[ ${#WARNINGS[@]} -gt 0 ]]; then
    MESSAGE=$(printf '%s\n' "${WARNINGS[@]}")
    echo "{\"decision\": \"allow\", \"message\": \"$MESSAGE\"}"
else
    echo '{"decision": "allow"}'
fi
