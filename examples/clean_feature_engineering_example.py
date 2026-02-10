#!/usr/bin/env python3
# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
"""
Clean Feature Engineering Example

Demonstrates how to use CKVD with suppressed logging for clean,
professional output in feature engineering workflows.

Before: 15+ lines of logging boilerplate + cluttered output
After: 1 line of configuration + structured NDJSON telemetry

Usage:
    uv run -p 3.13 python examples/clean_feature_engineering_example.py

Emits structured NDJSON telemetry to examples/logs/events.jsonl.
"""

import os
from datetime import datetime, timedelta, timezone

# Suppress CKVD internal logging noise for clean pipeline output
os.environ["CKVD_LOG_LEVEL"] = "CRITICAL"

from ckvd import CryptoKlineVisionData, DataProvider, Interval, MarketType

from _telemetry import init_telemetry, timed_span


def main():
    """Demonstrate clean feature engineering workflow."""
    tlog = init_telemetry("feature_engineering")

    tlog.bind(
        event_type="config_state",
        config_key="ckvd_log_level",
        ckvd_log_level="CRITICAL",
        reason="Suppress internal CKVD logs for clean feature engineering output",
    ).info("Feature engineering workflow starting with CKVD_LOG_LEVEL=CRITICAL")

    # Create CKVD instance
    manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.SPOT)
    tlog.bind(
        event_type="manager_created",
        venue="binance",
        market_type="SPOT",
    ).info("Manager created")

    # Define time range for feature extraction
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=1)

    symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]

    tlog.bind(
        event_type="config_documented",
        config_key="pipeline_params",
        start_time=str(start_time),
        end_time=str(end_time),
        symbols=symbols,
        interval="1m",
    ).info(f"Processing {len(symbols)} symbols for last 24 hours")

    # Process each symbol with structured telemetry
    results = {}

    for symbol in symbols:
        try:
            with timed_span(tlog, "fetch", symbol=symbol, interval="1m", venue="binance"):
                data = manager.get_data(
                    symbol=symbol,
                    start_time=start_time,
                    end_time=end_time,
                    interval=Interval.MINUTE_1,
                )

            if not data.empty:
                features = {
                    "records": len(data),
                    "avg_price": round(float(data["close"].mean()), 2) if "close" in data.columns else 0,
                    "volatility": round(float(data["close"].std()), 2) if "close" in data.columns else 0,
                    "volume_total": round(float(data["volume"].sum()), 0) if "volume" in data.columns else 0,
                }
                results[symbol] = features

                tlog.bind(
                    event_type="feature_computed",
                    symbol=symbol,
                    **features,
                ).info(f"{symbol}: {features['records']} records, avg=${features['avg_price']}")
            else:
                results[symbol] = None
                tlog.bind(
                    event_type="fetch_result",
                    symbol=symbol,
                    rows_returned=0,
                ).warning(f"{symbol}: No data available")

        except (OSError, RuntimeError, ValueError) as e:
            results[symbol] = None
            tlog.bind(
                event_type="fetch_failed",
                symbol=symbol,
                error=str(e)[:100],
                error_type=type(e).__name__,
            ).error(f"{symbol}: Error: {e!s:.50s}")

    # Clean up resources
    manager.close()

    # Emit summary
    successful = sum(1 for v in results.values() if v is not None)
    tlog.bind(
        event_type="session_completed",
        symbols_processed=len(symbols),
        symbols_successful=successful,
        symbols_failed=len(symbols) - successful,
        results={k: v for k, v in results.items() if v is not None},
    ).info(f"Feature engineering completed: {successful}/{len(symbols)} symbols")


if __name__ == "__main__":
    main()
