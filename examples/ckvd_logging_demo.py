#!/usr/bin/env python3
# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
"""
CKVD Logging Control Demo

Demonstrates how to control CKVD logging levels for clean workflows.
Emits structured NDJSON telemetry to examples/logs/events.jsonl.

Usage:
    # Clean output for feature engineering (suppress CKVD logs)
    CKVD_LOG_LEVEL=CRITICAL uv run -p 3.13 python examples/ckvd_logging_demo.py

    # Normal output with CKVD info logs
    CKVD_LOG_LEVEL=INFO uv run -p 3.13 python examples/ckvd_logging_demo.py

    # Using command line options
    uv run -p 3.13 python examples/ckvd_logging_demo.py --log-level CRITICAL
    uv run -p 3.13 python examples/ckvd_logging_demo.py --log-level DEBUG --show-all
"""

import os
from datetime import datetime, timedelta, timezone

import typer

from ckvd import CryptoKlineVisionData, DataProvider, Interval, MarketType
from ckvd.utils.loguru_setup import logger

from _telemetry import init_telemetry, timed_span


def demonstrate_logging_levels(tlog):
    """Document CKVD log level effects as structured data."""
    levels = [
        {"level": "CRITICAL", "shows": "Only critical errors", "use_case": "Feature engineering - clean output"},
        {"level": "ERROR", "shows": "Errors + critical (DEFAULT)", "use_case": "Production monitoring"},
        {"level": "WARNING", "shows": "Data quality warnings + errors", "use_case": "Development with visibility"},
        {"level": "INFO", "shows": "Basic operation info + warnings", "use_case": "Detailed development"},
        {"level": "DEBUG", "shows": "Detailed debugging + all above", "use_case": "Deep troubleshooting"},
    ]
    tlog.bind(
        event_type="config_documented",
        config_key="log_levels",
        levels=levels,
    ).info("CKVD log level reference documented")


def demonstrate_environment_control(tlog):
    """Document environment variable configuration state."""
    current_level = os.getenv("CKVD_LOG_LEVEL", "ERROR")
    effective_level = logger.getEffectiveLevel()

    tlog.bind(
        event_type="config_state",
        config_key="environment",
        ckvd_log_level_env=current_level,
        effective_level=effective_level,
        ckvd_log_file=os.getenv("CKVD_LOG_FILE", "(not set)"),
        ckvd_disable_colors=os.getenv("CKVD_DISABLE_COLORS", "(not set)"),
    ).info(f"Environment state: CKVD_LOG_LEVEL={current_level}, effective={effective_level}")

    control_methods = [
        {"method": "env_var", "command": "export CKVD_LOG_LEVEL=CRITICAL", "scope": "global"},
        {"method": "programmatic", "command": "logger.configure_level('CRITICAL')", "scope": "runtime"},
        {"method": "default", "command": "(none needed)", "scope": "ERROR is default"},
    ]
    tlog.bind(
        event_type="config_documented",
        config_key="control_methods",
        methods=control_methods,
    ).info("Logging control methods documented")


def demonstrate_programmatic_control(tlog):
    """Document programmatic logging control patterns."""
    patterns = [
        {
            "option": "configure_logger",
            "code": "from ckvd.utils.loguru_setup import logger; logger.configure_level('CRITICAL')",
        },
        {
            "option": "env_before_import",
            "code": "import os; os.environ['CKVD_LOG_LEVEL'] = 'CRITICAL'; from ckvd import CryptoKlineVisionData",
        },
    ]
    tlog.bind(
        event_type="config_documented",
        config_key="programmatic_control",
        patterns=patterns,
    ).info("Programmatic logging control patterns documented")


def demonstrate_feature_engineering_workflow(tlog):
    """Document the before/after of CKVD logging suppression."""
    tlog.bind(
        event_type="config_documented",
        config_key="feature_engineering_workflow",
        before="15+ lines of logging boilerplate + cluttered output",
        after="1 line: os.environ['CKVD_LOG_LEVEL'] = 'CRITICAL'",
        suppressed_logs=["cache_checking", "fcp_steps", "dataframe_processing", "api_debug"],
    ).info("Feature engineering workflow: CKVD_LOG_LEVEL=CRITICAL suppresses internal logs")


def test_actual_ckvd_logging(tlog, log_level: str):
    """Test actual CKVD logging with the specified level."""
    logger.configure_level(log_level)

    tlog.bind(
        event_type="config_state",
        config_key="test_log_level",
        log_level=log_level,
        effective_level=logger.getEffectiveLevel(),
    ).info(f"Set CKVD log level to: {log_level}")

    try:
        tlog.bind(event_type="manager_creating").info("Creating CryptoKlineVisionData manager...")
        manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.SPOT)

        tlog.bind(
            event_type="manager_created",
            venue="binance",
            market_type="SPOT",
        ).info("Manager created")

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=1)

        with timed_span(tlog, "fetch", symbol="BTCUSDT", interval="1m", venue="binance"):
            df = manager.get_data(
                symbol="BTCUSDT",
                start_time=start_time,
                end_time=end_time,
                interval=Interval.MINUTE_1,
            )

        if not df.empty:
            tlog.bind(
                event_type="fetch_detail",
                symbol="BTCUSDT",
                rows_returned=len(df),
            ).info(f"Retrieved {len(df)} records")
        else:
            tlog.bind(
                event_type="fetch_detail",
                symbol="BTCUSDT",
                rows_returned=0,
            ).warning("No data retrieved")

        manager.close()

    except (OSError, RuntimeError, ValueError) as e:
        tlog.bind(
            event_type="fetch_failed",
            error=str(e),
            error_type=type(e).__name__,
        ).error(f"Error during CKVD test: {e}")


def main(
    log_level: str = typer.Option("INFO", "--log-level", "-l", help="Log level to demonstrate"),
    show_all: bool = typer.Option(False, "--show-all", "-a", help="Show all demonstrations"),
    test_ckvd: bool = typer.Option(False, "--test-ckvd", "-t", help="Test actual CKVD logging"),
):
    """Demonstrate CKVD logging control capabilities."""
    tlog = init_telemetry("logging_demo")

    tlog.bind(
        event_type="config_documented",
        config_key="solution_summary",
        benefits=[
            "Easy Control: CKVD_LOG_LEVEL=CRITICAL vs 15+ lines of boilerplate",
            "Clean Output: No more cluttered console logs in feature engineering",
            "Configurable: Different log levels for different use cases",
            "No Code Changes: Existing CKVD code works unchanged",
        ],
    ).info("CKVD Logging Control Demo — solution for clean feature engineering workflows")

    # Always show the main demonstrations
    demonstrate_logging_levels(tlog)
    demonstrate_environment_control(tlog)

    if show_all:
        demonstrate_programmatic_control(tlog)
        demonstrate_feature_engineering_workflow(tlog)

    if test_ckvd:
        test_actual_ckvd_logging(tlog, log_level)

    tlog.bind(
        event_type="config_documented",
        config_key="implementation_status",
        features={
            "env_var_control": True,
            "programmatic_control": True,
            "centralized_loguru": True,
            "cleaner_default": True,
            "feature_engineering_ready": True,
        },
    ).info("Implementation status: all logging control features available")

    tlog.bind(event_type="session_completed").info("logging_demo completed")


if __name__ == "__main__":
    typer.run(main)
