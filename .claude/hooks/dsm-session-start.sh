#!/usr/bin/env bash
# DSM Session Start Hook
# Loads FCP context at session start for immediate awareness

set -euo pipefail

# Output context to stdout (added to Claude's context per SessionStart hook behavior)
cat << 'EOF'
## DSM Session Context

**Failover Control Protocol (FCP)**: Data retrieval uses Cache → Vision API → REST API priority.

**Key patterns**:
- Always use `datetime.now(timezone.utc)` for timestamps
- Always add explicit `timeout=` to HTTP requests
- Symbol format: BTCUSDT (spot/futures), BTCUSD_PERP (coin-margined)
- Always call `manager.close()` after using DataSourceManager

**Quick commands**:
- `/dsm-usage [symbol]` - Fetch data guide
- `/dsm-fcp-monitor [symbol]` - Debug FCP issues
- `/quick-test` - Run unit tests
EOF
