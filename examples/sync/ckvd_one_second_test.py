#!/usr/bin/env python3
# ADR: docs/adr/2026-01-30-claude-code-infrastructure.md
"""One-second data retrieval test script.

Tests CKVD's ability to handle one-second data intervals without
deprecation warnings related to frequency strings.

Emits structured NDJSON telemetry to examples/logs/events.jsonl.
"""

import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow import of _telemetry from parent examples/ directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _telemetry import init_telemetry, timed_span

from ckvd import CryptoKlineVisionData, DataProvider, Interval, MarketType
from ckvd.utils.dataframe_utils import verify_data_completeness
from ckvd.utils.for_core.ckvd_utilities import safely_reindex_dataframe


def main():
    """Test one-second data retrieval and processing."""
    tlog = init_telemetry("one_second_test")

    # Filter out all warnings to see if our fixes worked
    warnings.filterwarnings("error")

    # Create CKVD instance
    ckvd = CryptoKlineVisionData.create(DataProvider.BINANCE, MarketType.SPOT)
    tlog.bind(
        event_type="manager_created",
        venue="binance",
        market_type="SPOT",
    ).info("Manager created")

    # Use one-second interval
    interval = Interval.SECOND_1

    # Define a small time window (just 2 minutes of data)
    end_time = datetime.now(timezone.utc).replace(microsecond=0)
    start_time = end_time - timedelta(minutes=2)

    try:
        # Retrieve data
        with timed_span(tlog, "fetch", symbol="BTCUSDT", interval="1s", venue="binance"):
            df = ckvd.get_data(
                symbol="BTCUSDT",
                start_time=start_time,
                end_time=end_time,
                interval=interval,
            )

        tlog.bind(
            event_type="fetch_detail",
            symbol="BTCUSDT",
            rows_returned=len(df),
        ).info(f"Retrieved {len(df)} rows of one-second data")

        # Check data completeness
        is_complete, gaps = verify_data_completeness(df, start_time, end_time, interval="1s")
        tlog.bind(
            event_type="validation_result",
            validation="data_completeness",
            is_complete=is_complete,
            gaps_count=len(gaps),
        ).info(f"Data completeness: {'complete' if is_complete else f'{len(gaps)} gaps'}")

        # Test reindexing
        with timed_span(tlog, "reindex", symbol="BTCUSDT", interval="1s"):
            reindexed_df = safely_reindex_dataframe(
                df,
                start_time,
                end_time,
                interval="1s",
                fill_method="ffill",
            )

        tlog.bind(
            event_type="validation_result",
            validation="reindex_result",
            rows_after_reindex=len(reindexed_df),
        ).info(f"Reindexed to {len(reindexed_df)} rows")

        # Emit sample data
        if not df.empty:
            sample_rows = []
            for row in df.head(5).itertuples():
                time_str = row.Index.strftime("%Y-%m-%d %H:%M:%S") if hasattr(row.Index, "strftime") else str(row.Index)
                sample_rows.append({
                    "time": time_str,
                    "open": round(float(row.open), 2),
                    "close": round(float(row.close), 2),
                })
            tlog.bind(
                event_type="data_sample",
                symbol="BTCUSDT",
                sample_rows=sample_rows,
                sample_size=len(sample_rows),
            ).info(f"Sample: {len(sample_rows)} rows of one-second data")

        tlog.bind(event_type="session_completed", success=True).info("one_second_test completed successfully with no warnings")

    except Warning as w:
        tlog.bind(
            event_type="fetch_failed",
            error=str(w),
            error_type="Warning",
        ).warning(f"Warning occurred: {w}")
        tlog.bind(event_type="session_completed", success=False).info("one_second_test completed with warning")
    except (OSError, RuntimeError, ValueError) as e:
        tlog.bind(
            event_type="fetch_failed",
            error=str(e),
            error_type=type(e).__name__,
        ).error(f"Error occurred: {e}")
        tlog.bind(event_type="session_completed", success=False).info("one_second_test completed with error")


if __name__ == "__main__":
    main()
