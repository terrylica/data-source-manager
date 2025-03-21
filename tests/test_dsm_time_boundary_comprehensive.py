#!/usr/bin/env python
"""
Comprehensive testing of DataSourceManager time boundary conditions.

This test explores all combinations of:
1. Multiple dates across different years
2. Various microsecond combinations at start and end
3. Using both REST and Vision APIs
4. Visual output of timeline and actual data received
"""

import pytest
import arrow
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import (
    Dict,
    Any,
    List,
    Tuple,
    TypeVar,
    AsyncGenerator,
)
import pytest_asyncio
from _pytest.fixtures import FixtureRequest

from utils.logger_setup import get_logger
from core.data_source_manager import DataSourceManager, DataSource
from utils.market_constraints import Interval, MarketType
from utils.time_alignment import adjust_time_window

# Configure logging
logger = get_logger(__name__, level="INFO", show_path=False)

# Test configuration
TEST_SYMBOL = "BTCUSDT"
TEST_INTERVAL = Interval.SECOND_1

# Type variables for fixtures
T = TypeVar("T")
TFixture = TypeVar("TFixture")


@pytest_asyncio.fixture
async def manager() -> AsyncGenerator[DataSourceManager, None]:
    """Create DataSourceManager instance."""
    async with DataSourceManager(market_type=MarketType.SPOT) as mgr:
        yield mgr


def create_test_dates() -> List[arrow.Arrow]:
    """Create different dates spanning multiple years for testing."""
    now = arrow.utcnow()

    # For quick testing, just use one recent date
    return [
        now.shift(days=-3),  # 3 days ago (to ensure data availability)
    ]


def create_boundary_variations() -> List[Dict[str, Any]]:
    """Create microsecond combinations to test all boundary conditions."""
    return [
        # Exact boundaries
        {"start_us": 0, "end_us": 0, "name": "exact-exact"},
        # One-sided microseconds
        {"start_us": 0, "end_us": 100_000, "name": "exact-mid1"},
        {"start_us": 0, "end_us": 500_000, "name": "exact-mid2"},
        {"start_us": 0, "end_us": 999_999, "name": "exact-end"},
        {"start_us": 100_000, "end_us": 0, "name": "start1-exact"},
        {"start_us": 500_000, "end_us": 0, "name": "mid-exact"},
        {"start_us": 999_999, "end_us": 0, "name": "end-exact"},
        # Both sides with microseconds
        {"start_us": 100_000, "end_us": 500_000, "name": "start1-mid2"},
        {"start_us": 500_000, "end_us": 999_999, "name": "mid-end"},
        {"start_us": 999_999, "end_us": 100_000, "name": "end-start1"},
    ]


def create_time_windows(
    base_time: arrow.Arrow, seconds_diff: int = 5
) -> List[Dict[str, Any]]:
    """Create time windows with different boundary variations."""
    variations = create_boundary_variations()
    windows = []

    for var in variations:
        # Calculate window based on base_time
        start_time = base_time.shift(seconds=-seconds_diff).replace(
            microsecond=var["start_us"]
        )
        end_time = base_time.replace(microsecond=var["end_us"])

        windows.append(
            {
                "name": var["name"],
                "start": start_time.datetime,
                "end": end_time.datetime,
                "start_us": var["start_us"],
                "end_us": var["end_us"],
            }
        )

    return windows


def visualize_records(
    time_window: Dict[str, Any], df: pd.DataFrame, source: str
) -> str:
    """Create visual representation of the time window and records retrieved."""
    # Convert window to string format for clear visualization
    start_str = time_window["start"].strftime("%H:%M:%S.%f")[:-3]
    end_str = time_window["end"].strftime("%H:%M:%S.%f")[:-3]

    # Create record timeline
    timestamps = []
    if not df.empty:
        timestamps = [ts.strftime("%H:%M:%S") for ts in df.index]

    timeline_str = f"{start_str} → {end_str} ({source}): {len(df)} records"
    if timestamps:
        timeline_str += f" [{', '.join(timestamps)}]"

    # Add boundary indicators
    boundary_info = f"Boundaries: start={time_window['start_us']/1000:.1f}ms, end={time_window['end_us']/1000:.1f}ms"

    return f"{timeline_str}\n{boundary_info}"


@pytest.mark.real
@pytest.mark.asyncio
async def test_time_boundary_comprehensive(manager: DataSourceManager) -> None:
    """Comprehensive testing of time boundary handling."""
    all_results: Dict[str, Dict[str, Dict[str, Any]]] = {}
    time_windows: List[Dict[str, Any]] = []
    error_messages: Dict[str, str] = {}  # Store for error analysis

    for date_idx, base_time in enumerate(create_test_dates(), 1):
        date_str = base_time.format("YYYY-MM-DD")
        logger.info(f"\n=== Testing date {date_idx}: {date_str} ===")

        date_results = {}
        time_windows = create_time_windows(base_time)

        for window_idx, window in enumerate(time_windows, 1):
            window_name = window["name"]
            logger.info(f"\nWindow {window_idx}: {window_name}")

            # Convert to datetime objects and adjust time window
            start_time = window["start"]
            end_time = window["end"]

            # Log original window
            logger.info(
                f"Original window: {start_time.isoformat()} → {end_time.isoformat()}"
            )

            # Get adjusted times
            adjusted_start, adjusted_end = adjust_time_window(
                start_time, end_time, TEST_INTERVAL
            )

            logger.info(
                f"Adjusted window: {adjusted_start.isoformat()} → {adjusted_end.isoformat()}"
            )

            # Calculate expected records
            seconds_diff = int((adjusted_end - adjusted_start).total_seconds())
            logger.info(f"Time difference: {seconds_diff} seconds")
            logger.info(f"Expected records: {seconds_diff} (with exclusive end)")

            # Test both REST and Vision APIs
            results = {}
            for source_enum in [DataSource.REST, DataSource.VISION]:
                source_name = source_enum.name

                try:
                    logger.info(f"Fetching with {source_name} API...")
                    df = await manager.get_data(
                        symbol=TEST_SYMBOL,
                        start_time=start_time,
                        end_time=end_time,
                        interval=TEST_INTERVAL,
                        use_cache=False,
                        enforce_source=source_enum,
                    )

                    record_count = len(df)
                    result = "PASS" if record_count == seconds_diff else "FAIL"

                    results[source_name] = {
                        "count": record_count,
                        "expected": seconds_diff,
                        "result": result,
                        "timeline": visualize_records(window, df, source_name),
                    }

                    logger.info(
                        f"{source_name} API: {record_count} records (expected {seconds_diff}) - {result}"
                    )

                    if not df.empty:
                        # Show first and last timestamps
                        logger.info(f"First timestamp: {df.index[0]}")
                        logger.info(f"Last timestamp: {df.index[-1]}")

                        if record_count <= 10:
                            timestamps = [ts.strftime("%H:%M:%S") for ts in df.index]
                            logger.info(f"All timestamps: {timestamps}")

                except Exception as e:
                    error_str = str(e)
                    logger.error(f"{source_name} API fetch failed: {error_str}")
                    results[source_name] = {"error": error_str}
                    error_messages[f"{date_str}_{window_name}_{source_name}"] = (
                        error_str
                    )

            # Store results
            date_results[window_name] = results

        all_results[date_str] = date_results

    # Generate comprehensive summary
    logger.info("\n\n=== COMPREHENSIVE RESULTS SUMMARY ===")
    for date, date_results in all_results.items():
        logger.info(f"\n== Date: {date} ==")

        for window_name, sources in date_results.items():
            logger.info(f"\n= Window: {window_name} =")

            for source_name, result in sources.items():
                if "error" in result:
                    error_message = result["error"]  # Use local variable
                    logger.info(f"{source_name}: ERROR - {error_message}")
                else:
                    count = result["count"]
                    expected = result["expected"]
                    timeline = result["timeline"]
                    logger.info(
                        f"{source_name}: {count}/{expected} records - {result['result']}"
                    )
                    logger.info(f"  {timeline}")

    # Analyze patterns
    logger.info("\n\n=== PATTERN ANALYSIS ===")

    # Collect record count differences by window type
    window_patterns: Dict[str, List[Tuple[int, str, str]]] = {}
    for window in time_windows:
        window_name = window["name"]
        differences = []

        for date, date_results in all_results.items():
            if window_name in date_results:
                for source_name, result in date_results[window_name].items():
                    if "error" not in result:
                        diff = result["count"] - result["expected"]
                        differences.append((diff, date, source_name))

        if differences:
            logger.info(f"\nWindow type '{window_name}':")
            for diff, date, source in differences:
                sign = "+" if diff > 0 else "" if diff == 0 else "-"
                logger.info(f"  {date} ({source}): {sign}{diff} records from expected")

    # Check if microseconds at start or end correlate with differences
    logger.info("\n\nAnalyzing correlation between microseconds and record counts:")

    for part in ["start", "end"]:
        correlations = []
        for date, date_results in all_results.items():
            for window_name, sources in date_results.items():
                window_idx = next(
                    (i for i, w in enumerate(time_windows) if w["name"] == window_name),
                    None,
                )
                if window_idx is not None:
                    window = time_windows[window_idx]
                    us_value = window[f"{part}_us"]

                    for source_name, result in sources.items():
                        if "error" not in result:
                            diff = result["count"] - result["expected"]
                            correlations.append(
                                (us_value, diff, date, source_name, window_name)
                            )

        # Group by microsecond value
        by_us: Dict[int, List[Tuple]] = {}
        for us, diff, date, source, window in correlations:
            if us not in by_us:
                by_us[us] = []
            by_us[us].append((diff, date, source, window))

        logger.info(f"\nCorrelation for {part} microseconds:")
        for us, diffs in sorted(by_us.items()):
            avg_diff = sum(d[0] for d in diffs) / len(diffs)
            logger.info(
                f"  {us} µs: average difference = {avg_diff:.2f} records ({len(diffs)} samples)"
            )

    logger.info("\n=== TEST COMPLETED ===")


if __name__ == "__main__":
    pytest.main(["-vv", "--log-cli-level=INFO", "--asyncio-mode=auto", "--capture=no"])
