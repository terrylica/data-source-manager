#!/usr/bin/env python3
"""
Test file for the gap detector module.

This script runs tests for the gap_detector.py module to verify that
it correctly detects gaps for all interval types from market_constraints.py.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

from utils.logger_setup import logger
from utils.market_constraints import Interval
from utils.gap_detector import GapDetector, analyze_day_boundary


def create_synthetic_data(
    interval: Interval, start_time: datetime, periods: int, gaps: list = None
) -> pd.DataFrame:
    """
    Create synthetic data with specified gaps.

    Args:
        interval: Interval enum
        start_time: Start time for the data
        periods: Number of periods to generate
        gaps: List of tuples (gap_start_idx, gap_size) where gap_start_idx is the index
              after which to insert a gap, and gap_size is the number of periods to skip

    Returns:
        DataFrame with synthetic data and specified gaps
    """
    interval_seconds = interval.to_seconds()

    # Generate timestamps without gaps first
    timestamps = [
        start_time + timedelta(seconds=i * interval_seconds) for i in range(periods)
    ]

    # Apply gaps if specified
    if gaps:
        for gap_start_idx, gap_size in sorted(gaps, key=lambda x: x[0], reverse=True):
            if gap_start_idx < len(timestamps):
                # Insert gap after gap_start_idx
                gap_periods = int(gap_size)
                for i in range(gap_periods):
                    if gap_start_idx + 1 < len(timestamps):
                        timestamps.pop(gap_start_idx + 1)

    # Create DataFrame
    df = pd.DataFrame(
        {
            "timestamp": [
                int(t.timestamp() * 1000) for t in timestamps
            ],  # milliseconds
            "open": np.random.rand(len(timestamps)) * 100 + 30000,
            "high": np.random.rand(len(timestamps)) * 100 + 30000,
            "low": np.random.rand(len(timestamps)) * 100 + 30000,
            "close": np.random.rand(len(timestamps)) * 100 + 30000,
            "volume": np.random.rand(len(timestamps)) * 100,
        }
    )

    return df


def create_day_boundary_test_data(
    interval: Interval, first_day: str, second_day: str, missing_midnight: bool = True
) -> tuple:
    """
    Create synthetic data for day boundary tests.

    Args:
        interval: Interval enum
        first_day: First day date string (YYYY-MM-DD)
        second_day: Second day date string (YYYY-MM-DD)
        missing_midnight: Whether to create a gap at midnight

    Returns:
        Tuple of (first_day_df, second_day_df)
    """
    interval_seconds = interval.to_seconds()

    # Create start and end times
    first_day_start = datetime.strptime(
        f"{first_day} 00:00:00", "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=pytz.UTC)
    second_day_start = datetime.strptime(
        f"{second_day} 00:00:00", "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=pytz.UTC)

    # Determine number of periods based on interval
    secs_per_day = 24 * 60 * 60
    periods_per_day = secs_per_day // interval_seconds

    # Create first day data
    # If missing midnight, don't include the last record that would create midnight
    first_day_periods = periods_per_day
    first_day_df = create_synthetic_data(interval, first_day_start, first_day_periods)

    # Create second day data
    # If missing midnight, don't include the first record that would be midnight
    second_day_periods = periods_per_day

    if missing_midnight:
        # Skip the midnight record for the second day
        second_day_start_adjusted = second_day_start + timedelta(
            seconds=interval_seconds
        )
        second_day_df = create_synthetic_data(
            interval, second_day_start_adjusted, second_day_periods - 1
        )
    else:
        # Include midnight record
        second_day_df = create_synthetic_data(
            interval, second_day_start, second_day_periods
        )

    return first_day_df, second_day_df


def test_gap_detection_base():
    """Test basic gap detection functionality."""
    logger.info("Testing basic gap detection...")

    # Create test data with known gaps
    start_time = datetime(2025, 4, 1, tzinfo=pytz.UTC)

    # Test with 1-minute data
    df_1m = create_synthetic_data(
        Interval.MINUTE_1,
        start_time,
        100,
        gaps=[(10, 2), (50, 5)],  # 2 gaps of sizes 2 and 5
    )

    detector = GapDetector()
    gaps_1m = detector.find_gaps(df_1m, Interval.MINUTE_1)

    # Verify we found the expected gaps
    if len(gaps_1m) == 2:
        logger.info("✅ Found expected 2 gaps in 1-minute data")
    else:
        logger.error(f"❌ Found {len(gaps_1m)} gaps instead of 2 in 1-minute data")

    # Verify gap sizes
    if gaps_1m and gaps_1m[0]["missing_intervals"] == 3:
        logger.info("✅ First gap has correct size (3)")
    else:
        logger.error(
            f"❌ First gap has size {gaps_1m[0]['missing_intervals']} instead of 2"
        )

    if len(gaps_1m) > 1 and gaps_1m[1]["missing_intervals"] == 6:
        logger.info("✅ Second gap has correct size (6)")
    else:
        logger.error(
            f"❌ Second gap has size {gaps_1m[1]['missing_intervals']} instead of 5"
        )

    # Test with 1-hour data
    df_1h = create_synthetic_data(
        Interval.HOUR_1,
        start_time,
        48,
        gaps=[(5, 3), (20, 1)],  # 2 gaps of sizes 3 and 1
    )

    gaps_1h = detector.find_gaps(df_1h, Interval.HOUR_1)

    # Verify we found the expected gaps
    if len(gaps_1h) == 2:
        logger.info("✅ Found expected 2 gaps in 1-hour data")
    else:
        logger.error(f"❌ Found {len(gaps_1h)} gaps instead of 2 in 1-hour data")


def test_day_boundary_detection():
    """Test day boundary gap detection."""
    logger.info("\nTesting day boundary gap detection...")

    # Test with 1-minute data
    first_day = "2025-04-10"
    second_day = "2025-04-11"

    # Create day boundary data with missing midnight
    first_day_df, second_day_df = create_day_boundary_test_data(
        Interval.MINUTE_1, first_day, second_day, missing_midnight=True
    )

    detector = GapDetector()
    boundary_result = detector.analyze_day_boundary(
        first_day_df, second_day_df, Interval.MINUTE_1
    )

    # Verify missing midnight
    if len(boundary_result["gaps"]) >= 1:
        logger.info("✅ Found day boundary gap as expected")
        gap = boundary_result["gaps"][0]
        if gap["is_day_boundary"] and gap["midnight_missing"]:
            logger.info(
                "✅ Gap correctly identified as a day boundary with missing midnight"
            )
        else:
            logger.error(
                "❌ Gap not correctly identified as a day boundary with missing midnight"
            )
    else:
        logger.error("❌ Failed to detect day boundary gap")

    # Verify boundary info
    if (
        boundary_result["boundary_info"]["midnight_in_first_day"] == False
        and boundary_result["boundary_info"]["midnight_in_second_day"] == False
    ):
        logger.info("✅ Correctly identified missing midnight in both days")
    else:
        logger.error("❌ Failed to correctly identify missing midnight in the data")

    # Test with non-missing midnight
    first_day_df, second_day_df = create_day_boundary_test_data(
        Interval.MINUTE_1, first_day, second_day, missing_midnight=False
    )

    boundary_result = detector.analyze_day_boundary(
        first_day_df, second_day_df, Interval.MINUTE_1
    )

    # Verify no gaps
    if len(boundary_result["gaps"]) == 0:
        logger.info("✅ Correctly found no day boundary gap when midnight is present")
    else:
        logger.error(
            f"❌ Found {len(boundary_result['gaps'])} gaps when there should be none"
        )

    # Verify boundary info
    if boundary_result["boundary_info"]["midnight_in_second_day"] == True:
        logger.info("✅ Correctly identified midnight in second day")
    else:
        logger.error("❌ Failed to correctly identify midnight in the second day")


def test_all_interval_types():
    """Test gap detection for all interval types defined in market_constraints.py."""
    logger.info("\nTesting gap detection for all interval types...")

    # Get all interval types
    intervals = [
        Interval.SECOND_1,
        Interval.MINUTE_1,
        Interval.MINUTE_3,
        Interval.MINUTE_5,
        Interval.MINUTE_15,
        Interval.MINUTE_30,
        Interval.HOUR_1,
        Interval.HOUR_2,
        Interval.HOUR_4,
        Interval.HOUR_6,
        Interval.HOUR_8,
        Interval.HOUR_12,
        Interval.DAY_1,
        Interval.DAY_3,
        Interval.WEEK_1,
        Interval.MONTH_1,
    ]

    start_time = datetime(2025, 4, 1, tzinfo=pytz.UTC)
    detector = GapDetector()

    for interval in intervals:
        # Adjust periods for different intervals to avoid excessive data
        if "SECOND" in interval.name:
            periods = 100
        elif "MINUTE" in interval.name:
            periods = 60
        elif "HOUR" in interval.name:
            periods = 30
        else:
            periods = 20

        # Create test data with a single gap
        df = create_synthetic_data(
            interval,
            start_time,
            periods,
            gaps=[(periods // 2, 2)],  # One gap in the middle, size 2
        )

        # Detect gaps
        gaps = detector.find_gaps(df, interval)

        # Verify we found the expected gap
        if len(gaps) == 1 and gaps[0]["missing_intervals"] == 2:
            logger.info(f"✅ Successfully detected gap in {interval.value} data")
        else:
            logger.error(f"❌ Failed to detect gap in {interval.value} data")


def test_string_interval_input():
    """Test gap detection with string interval input."""
    logger.info("\nTesting gap detection with string interval input...")

    start_time = datetime(2025, 4, 1, tzinfo=pytz.UTC)
    df = create_synthetic_data(
        Interval.MINUTE_15, start_time, 100, gaps=[(10, 2)]  # 1 gap of size 2
    )

    detector = GapDetector()

    # Test with string interval like "15m"
    gaps = detector.find_gaps(df, "15m")
    if len(gaps) == 1 and gaps[0]["missing_intervals"] == 2:
        logger.info("✅ Successfully detected gap with string interval input (15m)")
    else:
        logger.error(
            f"❌ Failed to detect gap with string interval input: {len(gaps)} gaps found"
        )

    # Test with string interval like "1h"
    df_1h = create_synthetic_data(
        Interval.HOUR_1, start_time, 48, gaps=[(10, 3)]  # 1 gap of size 3
    )

    gaps_str = detector.find_gaps(df_1h, "1h")
    if len(gaps_str) == 1 and gaps_str[0]["missing_intervals"] == 3:
        logger.info("✅ Successfully detected gap with string interval input (1h)")
    else:
        logger.error(
            f"❌ Failed to detect gap with string interval input: {len(gaps_str)} gaps found"
        )

    # Test with manual second interval
    gaps_manual = detector.find_gaps(df_1h, 3600)  # 3600 seconds = 1 hour
    if len(gaps_manual) == 1 and gaps_manual[0]["missing_intervals"] == 3:
        logger.info("✅ Successfully detected gap with manual second interval (3600)")
    else:
        logger.error(
            f"❌ Failed to detect gap with manual second interval: {len(gaps_manual)} gaps found"
        )


def test_with_parquet_data():
    """Test gap detection with real data from parquet files."""
    logger.info("\nTesting gap detection with parquet file data...")

    try:
        from pathlib import Path
        import pyarrow.parquet as pq

        # Look for parquet test files in the same directory as this script
        script_dir = Path(__file__).parent
        test_data_dir = script_dir / "test_data"

        if not test_data_dir.exists():
            logger.warning(
                f"❌ Test data directory not found: {test_data_dir}. Skipping parquet test."
            )
            return

        # Look for parquet files
        parquet_files = list(test_data_dir.glob("*.parquet"))
        if not parquet_files:
            logger.warning(
                f"❌ No parquet files found in {test_data_dir}. Skipping parquet test."
            )
            return

        # Use the first parquet file found
        test_file = parquet_files[0]
        logger.info(f"Found test file: {test_file}")

        # Read the parquet file
        df = pq.read_table(test_file).to_pandas()

        # Verify we have the required columns
        if "timestamp" not in df.columns:
            logger.warning(
                f"❌ Parquet file does not contain 'timestamp' column. Skipping parquet test."
            )
            return

        logger.info(f"Loaded data with {len(df)} rows")

        # Try to determine interval from the data
        # Sort by timestamp first
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Calculate time differences
        df["time_diff"] = df["timestamp"].diff()
        median_diff = df["time_diff"].median()
        interval_seconds = median_diff / 1000  # Convert to seconds

        logger.info(f"Estimated interval: {interval_seconds:.1f} seconds")

        # Find the closest standard interval
        detector = GapDetector()
        gap_results = detector.find_gaps(df, interval_seconds)

        logger.info(f"Found {len(gap_results)} gaps in the data")

        # Log some information about the first gap if any
        if gap_results:
            gap = gap_results[0]
            logger.info("First gap details:")
            logger.info(f"  Start: {gap['start_dt']}")
            logger.info(f"  End: {gap['end_dt']}")
            logger.info(f"  Duration: {gap['duration_seconds']:.2f} seconds")
            logger.info(f"  Missing intervals: {gap['missing_intervals']}")
            if gap["is_day_boundary"]:
                logger.info(f"  Day boundary gap: {gap['is_day_boundary']}")
                logger.info(f"  Midnight missing: {gap['midnight_missing']}")

        logger.info("✅ Parquet data test completed")

    except ImportError:
        logger.warning("❌ pyarrow not installed. Skipping parquet test.")
    except Exception as e:
        logger.error(f"❌ Error in parquet test: {e}")


def test_convenience_functions():
    """Test the convenience functions: detect_gaps() and analyze_day_boundary()."""
    logger.info("\nTesting convenience functions...")

    # Create test data
    start_time = datetime(2025, 4, 1, tzinfo=pytz.UTC)
    df = create_synthetic_data(
        Interval.MINUTE_15, start_time, 100, gaps=[(10, 3)]  # 1 gap of size 3
    )

    # Test detect_gaps convenience function
    from utils.gap_detector import detect_gaps

    gaps = detect_gaps(df, Interval.MINUTE_15)

    if len(gaps) == 1 and gaps[0]["missing_intervals"] == 3:
        logger.info("✅ detect_gaps() convenience function works correctly")
    else:
        logger.error(
            f"❌ detect_gaps() convenience function failed: {len(gaps)} gaps found"
        )

    # Create day boundary data
    first_day_df, second_day_df = create_day_boundary_test_data(
        Interval.MINUTE_1, "2025-04-10", "2025-04-11", missing_midnight=True
    )

    # Test analyze_day_boundary function
    boundary_result = analyze_day_boundary(
        first_day_df, second_day_df, Interval.MINUTE_1
    )

    if len(boundary_result["gaps"]) >= 1:
        logger.info("✅ analyze_day_boundary function works correctly")
    else:
        logger.error(
            f"❌ analyze_day_boundary function failed to detect the boundary gap"
        )


def main():
    """Run all tests."""
    logger.info("Starting gap detector tests...")

    # Run tests
    test_gap_detection_base()
    test_day_boundary_detection()
    test_all_interval_types()
    test_string_interval_input()
    test_with_parquet_data()
    test_convenience_functions()

    logger.info("\nAll tests completed.")


if __name__ == "__main__":
    main()
