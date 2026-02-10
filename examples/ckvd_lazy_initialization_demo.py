#!/usr/bin/env python3
# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
"""Demonstration of CKVD Import and Initialization Performance.

Shows:
1. Fast imports (similar to pandas, SQLAlchemy)
2. Factory creation pattern
3. Performance benchmarks vs industry standards

Run with:
    uv run -p 3.13 python examples/ckvd_lazy_initialization_demo.py

Emits structured NDJSON telemetry to examples/logs/events.jsonl.
"""

import time


def benchmark_import_speed() -> tuple[float, float, float]:
    """Benchmark CKVD import speed vs industry standards.

    Runs BEFORE telemetry init to avoid _telemetry.py pre-loading ckvd
    into sys.modules (which would invalidate the measurement).

    Returns:
        Tuple of (ckvd_time, pandas_time, ratio).
    """
    # Benchmark CKVD import
    start_time = time.time()
    from ckvd import CryptoKlineVisionData, DataProvider, Interval, MarketType  # noqa: F401

    ckvd_import_time = time.time() - start_time

    # Compare with pandas
    start_time = time.time()
    import pandas  # noqa: F401

    pandas_import_time = time.time() - start_time

    ratio = ckvd_import_time / pandas_import_time if pandas_import_time > 0.001 else 0.0

    return ckvd_import_time, pandas_import_time, ratio


def demonstrate_factory_creation(tlog) -> None:
    """Demonstrate the factory creation pattern."""
    tlog.bind(event_type="section_started", section="factory_creation").info("Benchmark: Factory Creation")

    from ckvd import CryptoKlineVisionData, DataProvider, MarketType

    managers = []
    market_types = [MarketType.SPOT, MarketType.FUTURES_USDT, MarketType.FUTURES_COIN]

    total_start = time.time()
    for market_type in market_types:
        create_start = time.time()
        manager = CryptoKlineVisionData.create(DataProvider.BINANCE, market_type)
        managers.append(manager)
        create_time = time.time() - create_start

        tlog.bind(
            event_type="benchmark_result",
            operation="factory_create",
            venue="binance",
            market_type=market_type.name,
            duration_ms=round(create_time * 1000, 1),
        ).info(f"Created {market_type.name} manager in {create_time:.4f}s")

    total_create_time = time.time() - total_start

    # Cleanup
    for manager in managers:
        manager.close()

    tlog.bind(
        event_type="benchmark_result",
        operation="factory_create_total",
        managers_created=len(managers),
        total_duration_ms=round(total_create_time * 1000, 1),
        avg_duration_ms=round((total_create_time / len(managers)) * 1000, 1),
    ).info(f"Total: {len(managers)} managers in {total_create_time:.3f}s (avg {total_create_time / len(managers):.4f}s)")


def demonstrate_configuration_patterns(tlog) -> None:
    """Demonstrate different configuration patterns."""
    tlog.bind(event_type="section_started", section="configuration").info("Configuration Patterns")

    from ckvd import CryptoKlineVisionData, DataProvider, MarketType
    from ckvd.core.sync.crypto_kline_vision_data import DataSource

    manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.SPOT)

    tlog.bind(
        event_type="config_documented",
        config_key="fcp_default",
        provider="BINANCE",
        market_type="SPOT",
        fcp_path="Cache -> Vision -> REST",
    ).info("Basic Configuration: FCP Cache -> Vision -> REST (default)")

    enforce_source_options = [
        {"source": ds.name, "description": {
            "AUTO": "Use FCP priority (default)",
            "VISION": "Skip cache, only Vision API",
            "REST": "Skip cache and Vision, only REST",
            "CACHE": "Only local cache (offline mode)",
        }.get(ds.name, "")} for ds in DataSource
    ]

    tlog.bind(
        event_type="config_documented",
        config_key="enforce_source_options",
        options=enforce_source_options,
    ).info(f"Available enforce_source options: {[ds.name for ds in DataSource]}")

    manager.close()


def test_import_after_scipy(tlog) -> None:
    """Test that CKVD imports work after scipy (original problem)."""
    tlog.bind(event_type="section_started", section="scipy_test").info("Test: Import After SciPy")

    try:
        import scipy.stats  # noqa: F401

        start_time = time.time()
        from ckvd import CryptoKlineVisionData, DataProvider, MarketType

        import_time = time.time() - start_time

        manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.SPOT)
        tlog.bind(
            event_type="manager_created",
            venue="binance",
            market_type="SPOT",
        ).info("Manager created after scipy import")
        manager.close()

        tlog.bind(
            event_type="benchmark_result",
            operation="import_after_scipy",
            duration_ms=round(import_time * 1000, 1),
            pass_threshold=import_time < 1.0,
            scipy_available=True,
        ).info(f"CKVD import after scipy: {import_time:.3f}s ({'PASS' if import_time < 1.0 else 'WARN'})")

    except ImportError:
        tlog.bind(
            event_type="benchmark_result",
            operation="import_after_scipy",
            scipy_available=False,
            skipped=True,
        ).info("SciPy not available, test skipped")


def demonstrate_industry_comparisons(tlog) -> None:
    """Compare CKVD patterns with industry standards."""
    comparisons = [
        {"pattern": "SQLAlchemy", "ckvd": "CryptoKlineVisionData.create()", "industry": "create_engine(...)"},
        {"pattern": "AWS SDK", "ckvd": "CKVDConfig", "industry": "boto3.client('s3', config=Config(...))"},
        {"pattern": "Requests", "ckvd": "manager.close()", "industry": "session = requests.Session()"},
    ]

    benchmarks = [
        {"metric": "Import Speed", "target": "<500ms", "comparable_to": "pandas"},
        {"metric": "Factory Creation", "target": "<2s", "comparable_to": "SQLAlchemy"},
        {"metric": "First Fetch", "target": "<5s", "comparable_to": "first API call"},
        {"metric": "Subsequent", "target": "<500ms", "comparable_to": "cache hit"},
    ]

    tlog.bind(
        event_type="config_documented",
        config_key="industry_comparisons",
        comparisons=comparisons,
        performance_benchmarks=benchmarks,
    ).info("Industry standard comparisons documented")


def demonstrate_backwards_compatibility(tlog) -> None:
    """Show that the high-level API still works."""
    apis = [
        {
            "api": "CryptoKlineVisionData.create() + get_data()",
            "type": "primary",
            "features": ["Factory pattern", "FCP-enabled", "Explicit cleanup"],
        },
        {
            "api": "fetch_market_data()",
            "type": "convenience",
            "features": ["Single function", "Uses CKVD internally with FCP"],
        },
    ]

    tlog.bind(
        event_type="config_documented",
        config_key="api_compatibility",
        apis=apis,
    ).info("Both primary and convenience APIs follow industry standard patterns")


def main() -> None:
    """Run the complete demonstration."""
    # Run import benchmark BEFORE importing _telemetry (which loads ckvd)
    ckvd_time, pandas_time, ratio = benchmark_import_speed()

    # Now safe to import telemetry (ckvd already in sys.modules from benchmark)
    from _telemetry import init_telemetry

    tlog = init_telemetry("lazy_initialization")

    tlog.bind(event_type="section_started", section="overview").info("CKVD Import and Initialization Demo")

    # Log the benchmark results retroactively
    tlog.bind(
        event_type="benchmark_result",
        operation="import",
        ckvd_import_ms=round(ckvd_time * 1000, 1),
        pandas_import_ms=round(pandas_time * 1000, 1),
        ratio=round(ratio, 2),
        pass_threshold=ckvd_time < 0.5,
    ).info(
        f"Import: CKVD={ckvd_time:.3f}s, Pandas={pandas_time:.3f}s, "
        f"ratio={ratio:.2f}x, {'PASS' if ckvd_time < 0.5 else 'WARN'} (<500ms)"
    )

    # Run remaining demonstrations
    demonstrate_factory_creation(tlog)
    demonstrate_configuration_patterns(tlog)
    test_import_after_scipy(tlog)
    demonstrate_industry_comparisons(tlog)
    demonstrate_backwards_compatibility(tlog)

    tlog.bind(
        event_type="session_completed",
        summary={
            "import_speed_ms": round(ckvd_time * 1000, 1),
            "pandas_speed_ms": round(pandas_time * 1000, 1),
            "factory_creation": "working",
            "configuration": "complete",
            "industry_patterns": "implemented",
        },
    ).info(f"Demo completed: import={ckvd_time:.3f}s, pandas={pandas_time:.3f}s")


if __name__ == "__main__":
    main()
