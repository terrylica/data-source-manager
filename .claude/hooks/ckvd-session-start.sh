#!/usr/bin/env bash
# CKVD Session Start Hook
# Loads FCP context at session start for immediate awareness

set -euo pipefail

# Output context to stdout (added to Claude's context per SessionStart hook behavior)
cat << 'EOF'
## CKVD Session Context

**Failover Control Protocol (FCP)**: Data retrieval uses Cache → Vision API → REST API priority.

**Key patterns**:
- Always use `datetime.now(timezone.utc)` for timestamps
- Always add explicit `timeout=` to HTTP requests
- Symbol format: BTCUSDT (spot/futures), BTCUSD_PERP (coin-margined)
- Always call `manager.close()` after using CryptoKlineVisionData

**Quick commands**:
- `/ckvd-usage [symbol]` - Fetch data guide
- `/ckvd-fcp-monitor [symbol]` - Debug FCP issues
- `/quick-test` - Run unit tests
EOF
