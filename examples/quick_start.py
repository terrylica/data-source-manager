#!/usr/bin/env python3
# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
"""
Quick Start Example for Crypto Kline Vision Data.

Run with:
    uv run -p 3.13 python examples/quick_start.py

This demonstrates basic CKVD usage with automatic FCP fallback.
Emits structured NDJSON telemetry to examples/logs/events.jsonl.
"""

from datetime import datetime, timedelta, timezone

from ckvd import CryptoKlineVisionData, DataProvider, Interval, MarketType

from _telemetry import init_telemetry, timed_span


def main() -> None:
    """Fetch recent BTCUSDT hourly data."""
    tlog = init_telemetry("quick_start")

    # Create manager for USDT-margined futures
    manager = CryptoKlineVisionData.create(
        DataProvider.BINANCE,
        MarketType.FUTURES_USDT,
    )
    tlog.bind(
        event_type="manager_created",
        venue="binance",
        market_type="FUTURES_USDT",
    ).info("Manager created")

    # Time range: last 7 days (always UTC)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=7)

    # Fetch data with automatic failover (timed_span emits fetch_started/completed)
    with timed_span(tlog, "fetch", symbol="BTCUSDT", interval="1h", venue="binance"):
        df = manager.get_data(
            symbol="BTCUSDT",
            interval=Interval.HOUR_1,
            start_time=start_time,
            end_time=end_time,
        )

    # Emit result details (fetch_completed already emitted by timed_span)
    if df is not None and len(df) > 0:
        tlog.bind(
            event_type="fetch_detail",
            symbol="BTCUSDT",
            rows_returned=len(df),
            columns=list(df.columns),
            date_range_start=str(df.index.min()),
            date_range_end=str(df.index.max()),
        ).info(f"Loaded {len(df)} bars")
    else:
        tlog.bind(
            event_type="fetch_detail",
            symbol="BTCUSDT",
            rows_returned=0,
        ).warning("No data returned — check symbol format, date range, or connectivity")

    # Cleanup
    manager.close()

    tlog.bind(event_type="session_completed").info("quick_start completed")


if __name__ == "__main__":
    main()
