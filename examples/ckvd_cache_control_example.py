#!/usr/bin/env python3
# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
"""
CKVD Cache Control Example

Demonstrates all cache toggle mechanisms:
1. Per-manager: use_cache=False in .create() or constructor
2. Per-environment: CKVD_ENABLE_CACHE=false env var
3. Per-request: enforce_source to bypass specific FCP stages
4. Combined: env var + explicit parameter interactions

Run with:
    uv run -p 3.13 python examples/ckvd_cache_control_example.py

    # Or with cache globally disabled via env var:
    CKVD_ENABLE_CACHE=false uv run -p 3.13 python examples/ckvd_cache_control_example.py

Emits structured NDJSON telemetry to examples/logs/events.jsonl.
"""

import os
from datetime import datetime, timedelta, timezone

from _telemetry import init_telemetry, timed_span

from ckvd import CryptoKlineVisionData, DataProvider, Interval, MarketType
from ckvd.core.sync.ckvd_types import CKVDConfig, DataSource


def example_1_disable_cache_per_manager(tlog) -> None:
    """Disable cache for a specific manager instance."""
    tlog.bind(event_type="section_started", section="example_1").info("Example 1: Disable cache per manager (use_cache=False)")

    manager = CryptoKlineVisionData.create(
        DataProvider.BINANCE,
        MarketType.FUTURES_USDT,
        use_cache=False,
    )

    tlog.bind(
        event_type="manager_created",
        venue="binance",
        market_type="FUTURES_USDT",
        use_cache=False,
        fcp_path="Vision API -> REST API (no cache)",
    ).info(f"Manager created with use_cache={manager.use_cache}")

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=2)

    with timed_span(tlog, "fetch", symbol="BTCUSDT", interval="1h", venue="binance", use_cache=False, cache_hit=False):
        df = manager.get_data("BTCUSDT", start, end, Interval.HOUR_1)

    tlog.bind(
        event_type="fetch_detail",
        symbol="BTCUSDT",
        rows_returned=len(df),
    ).info(f"Fetched {len(df)} bars (always from API, never from cache)")

    manager.close()


def example_2_env_var_global_disable(tlog) -> None:
    """Disable cache globally via environment variable."""
    tlog.bind(event_type="section_started", section="example_2").info("Example 2: Disable cache via CKVD_ENABLE_CACHE env var")

    env_value = os.environ.get("CKVD_ENABLE_CACHE", "(not set)")

    manager = CryptoKlineVisionData.create(
        DataProvider.BINANCE,
        MarketType.SPOT,
    )

    tlog.bind(
        event_type="config_state",
        config_key="cache_env_var",
        ckvd_enable_cache_env=env_value,
        effective_use_cache=manager.use_cache,
        override_active=not manager.use_cache and env_value != "(not set)",
    ).info(f"CKVD_ENABLE_CACHE={env_value}, effective use_cache={manager.use_cache}")

    manager.close()


def example_3_enforce_source(tlog) -> None:
    """Force data from a specific FCP source."""
    tlog.bind(event_type="section_started", section="example_3").info("Example 3: Force specific data source (enforce_source)")

    manager = CryptoKlineVisionData.create(
        DataProvider.BINANCE,
        MarketType.FUTURES_USDT,
    )

    end = datetime.now(timezone.utc) - timedelta(hours=1)
    start = end - timedelta(hours=2)

    # Force REST API
    with timed_span(tlog, "fetch", symbol="BTCUSDT", interval="1h", venue="binance", enforce_source="REST"):
        df = manager.get_data(
            "BTCUSDT", start, end, Interval.HOUR_1,
            enforce_source=DataSource.REST,
        )

    tlog.bind(
        event_type="fetch_detail",
        symbol="BTCUSDT",
        rows_returned=len(df),
        fcp_source="REST",
    ).info(f"REST: {len(df)} bars")

    # Force Vision API (may fail for recent data — no timed_span, manual handling)
    try:
        df = manager.get_data(
            "BTCUSDT", start, end, Interval.HOUR_1,
            enforce_source=DataSource.VISION,
        )
        tlog.bind(
            event_type="fetch_detail",
            symbol="BTCUSDT",
            rows_returned=len(df),
            fcp_source="VISION",
        ).info(f"Vision: {len(df)} bars")
    except RuntimeError as e:
        tlog.bind(
            event_type="fetch_failed",
            symbol="BTCUSDT",
            fcp_source="VISION",
            error=str(e)[:60],
            error_type="RuntimeError",
        ).warning(f"Vision unavailable for recent data: {e!s:.60s}")

    manager.close()


def example_4_contradiction_error(tlog) -> None:
    """Show the error when enforce_source=CACHE conflicts with use_cache=False."""
    tlog.bind(event_type="section_started", section="example_4").info("Example 4: enforce_source=CACHE + use_cache=False -> error")

    manager = CryptoKlineVisionData.create(
        DataProvider.BINANCE,
        MarketType.SPOT,
        use_cache=False,
    )

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=1)

    try:
        manager.get_data(
            "BTCUSDT", start, end, Interval.HOUR_1,
            enforce_source=DataSource.CACHE,
        )
    except RuntimeError as e:
        tlog.bind(
            event_type="fetch_failed",
            symbol="BTCUSDT",
            error=str(e),
            error_type="RuntimeError",
            expected=True,
            reason="enforce_source=CACHE contradicts use_cache=False",
        ).info(f"Expected error: {e}")

    manager.close()


def example_5_ckvdconfig_cache_control(tlog) -> None:
    """Use CKVDConfig for structured configuration."""
    tlog.bind(event_type="section_started", section="example_5").info("Example 5: CKVDConfig with cache control")

    config_disabled = CKVDConfig.create(
        provider=DataProvider.BINANCE,
        market_type=MarketType.FUTURES_USDT,
        use_cache=False,
    )

    config_default = CKVDConfig.create(
        provider=DataProvider.BINANCE,
        market_type=MarketType.SPOT,
    )

    env_value = os.environ.get("CKVD_ENABLE_CACHE", "(not set)")

    tlog.bind(
        event_type="config_state",
        config_key="ckvdconfig_cache",
        explicit_disabled=config_disabled.use_cache,
        default_value=config_default.use_cache,
        ckvd_enable_cache_env=env_value,
    ).info(
        f"CKVDConfig(use_cache=False) -> {config_disabled.use_cache}, "
        f"CKVDConfig() -> {config_default.use_cache}"
    )


def example_6_when_to_disable_cache(tlog) -> None:
    """Practical scenarios for disabling cache."""
    tlog.bind(
        event_type="config_documented",
        config_key="cache_disable_scenarios",
        disable_when=[
            "Running unit/integration tests (isolation)",
            "Validating live API responses (freshness)",
            "Benchmarking API performance (no cache advantage)",
            "Debugging FCP source selection (force Vision/REST)",
            "CI/CD pipelines (no persistent state)",
        ],
        keep_enabled_when=[
            "Production backtesting (speed: ~1ms vs ~1-5s)",
            "Feature engineering (repeated symbol access)",
            "Multi-symbol scans (cache warms across runs)",
            "Development iteration (fast feedback loops)",
        ],
    ).info("Cache disable/enable scenarios documented")


def main() -> None:
    """Run all cache control examples."""
    tlog = init_telemetry("cache_control")

    example_6_when_to_disable_cache(tlog)
    example_1_disable_cache_per_manager(tlog)
    example_2_env_var_global_disable(tlog)
    example_5_ckvdconfig_cache_control(tlog)
    example_3_enforce_source(tlog)
    example_4_contradiction_error(tlog)

    # Emit summary
    mechanisms = [
        {"mechanism": "use_cache=False", "scope": "Per-manager", "how": ".create(use_cache=False)"},
        {"mechanism": "CKVD_ENABLE_CACHE=false", "scope": "Global", "how": "Environment variable"},
        {"mechanism": "enforce_source=REST", "scope": "Per-request", "how": ".get_data(enforce_source=..)"},
        {"mechanism": "enforce_source=VISION", "scope": "Per-request", "how": ".get_data(enforce_source=..)"},
    ]

    tlog.bind(
        event_type="config_documented",
        config_key="cache_mechanisms_summary",
        mechanisms=mechanisms,
        precedence="explicit use_cache=False > CKVD_ENABLE_CACHE env var > default True",
    ).info("Cache control mechanisms summary")

    tlog.bind(event_type="session_completed").info("cache_control completed")


if __name__ == "__main__":
    main()
