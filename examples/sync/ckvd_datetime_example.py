#!/usr/bin/env python3
# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
"""Example demonstrating proper datetime handling with Crypto Kline Vision Data.

Shows best practices for:
1. Working with timezone-aware datetimes
2. Checking data completeness
3. Handling potential gaps in data
4. Safe reindexing for analysis

Emits structured NDJSON telemetry to examples/logs/events.jsonl.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow import of _telemetry from parent examples/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _telemetry import init_telemetry, timed_span

from ckvd import CryptoKlineVisionData, DataProvider, Interval, MarketType
from ckvd.utils.dataframe_utils import verify_data_completeness
from ckvd.utils.for_core.ckvd_utilities import (
    check_window_data_completeness,
    safely_reindex_dataframe,
)


def setup(tlog):
    """Set up CKVD manager."""
    manager = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.SPOT)
    tlog.bind(
        event_type="manager_created",
        venue="binance",
        market_type="SPOT",
    ).info("Manager created for SPOT market")
    return manager


def example_timezone_aware_retrieval(tlog, ckvd, start_time, end_time):
    """Demonstrate retrieval with proper timezone handling."""
    tlog.bind(event_type="section_started", section="timezone_retrieval").info("Example 1: Timezone-Aware DateTime Retrieval")

    with timed_span(tlog, "fetch", symbol="BTCUSDT", interval="15m", venue="binance"):
        df = ckvd.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.MINUTE_15,
        )

    # Emit structured result
    result = {
        "rows_returned": len(df),
        "first_timestamp": str(df.index[0]) if len(df) > 0 else None,
        "last_timestamp": str(df.index[-1]) if len(df) > 0 else None,
        "index_tz": str(df.index.tz) if len(df) > 0 else None,
    }

    # Track data source distribution
    if "_data_source" in df.columns:
        sources = df["_data_source"].value_counts().to_dict()
        result["data_sources"] = {str(k): int(v) for k, v in sources.items()}

    tlog.bind(
        event_type="fetch_detail",
        symbol="BTCUSDT",
        **result,
    ).info(f"Retrieved {len(df)} rows")

    return df


def example_check_data_completeness(tlog, df, start_time, end_time):
    """Demonstrate checking for data completeness."""
    tlog.bind(event_type="section_started", section="data_completeness").info("Example 2: Checking Data Completeness")

    is_complete, gaps = verify_data_completeness(df, start_time, end_time, interval="15m")

    gap_details = []
    if not is_complete:
        for start, end in gaps:
            duration_hours = (end - start).total_seconds() / 3600
            gap_details.append({
                "start": str(start),
                "end": str(end),
                "duration_hours": round(duration_hours, 1),
            })

    tlog.bind(
        event_type="validation_result",
        validation="data_completeness",
        is_complete=is_complete,
        gaps_count=len(gaps),
        gaps=gap_details,
    ).info(f"Data completeness: {'complete' if is_complete else f'{len(gaps)} gaps detected'}")


def example_window_calculations(tlog, df):
    """Demonstrate safe window-based calculations."""
    tlog.bind(event_type="section_started", section="window_calculations").info("Example 3: Window-Based Calculations")

    for window in [24, 48, 96]:
        has_enough, pct = check_window_data_completeness(df, window)

        result = {
            "window_size": window,
            "has_enough_data": has_enough,
            "data_completeness_pct": round(pct, 1),
        }

        if has_enough:
            ma = df["close"].rolling(window).mean()
            result["last_moving_average"] = round(float(ma.iloc[-1]), 2)

        tlog.bind(
            event_type="feature_computed",
            feature_name=f"MA_{window}",
            **result,
        ).info(f"Window {window}: {'sufficient' if has_enough else 'insufficient'} data ({pct:.1f}%)")


def example_reindexing(tlog, df, end_time):
    """Demonstrate safe reindexing for analysis."""
    tlog.bind(event_type="section_started", section="reindexing").info("Example 4: Safe Reindexing")

    subset_end = end_time
    subset_start = subset_end - timedelta(hours=24)

    subset_df = df[(df.index >= subset_start) & (df.index < subset_end)].copy()

    # Create gaps for demonstration
    rows_before = len(subset_df)
    if len(subset_df) > 10:
        indices_to_drop = subset_df.index[5:10]
        subset_df = subset_df.drop(indices_to_drop)

    tlog.bind(
        event_type="validation_result",
        validation="reindex_input",
        rows_before_drop=rows_before,
        rows_after_drop=len(subset_df),
        rows_removed=rows_before - len(subset_df),
    ).info(f"Created subset with {len(subset_df)} rows (removed {rows_before - len(subset_df)} for demo)")

    # Safely reindex
    complete_df = safely_reindex_dataframe(
        subset_df,
        subset_start,
        subset_end,
        interval="15m",
        fill_method="ffill",
    )

    missing_before = int(subset_df.isna().sum().sum())
    missing_after = int(complete_df.isna().sum().sum())

    tlog.bind(
        event_type="validation_result",
        validation="reindex_result",
        rows_after_reindex=len(complete_df),
        missing_values_before=missing_before,
        missing_values_after=missing_after,
    ).info(f"After reindexing: {len(complete_df)} rows, missing values: {missing_before} -> {missing_after}")


def main():
    """Run the examples."""
    tlog = init_telemetry("datetime_example")

    try:
        ckvd = setup(tlog)

        # Always use timezone-aware datetimes
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=3)

        df = example_timezone_aware_retrieval(tlog, ckvd, start_time, end_time)
        example_check_data_completeness(tlog, df, start_time, end_time)
        example_window_calculations(tlog, df)
        example_reindexing(tlog, df, end_time)

        ckvd.close()

    except (OSError, RuntimeError, ValueError) as e:
        tlog.bind(
            event_type="fetch_failed",
            error=str(e),
            error_type=type(e).__name__,
        ).error(f"Error: {e}")
        return 1

    tlog.bind(event_type="session_completed").info("datetime_example completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
