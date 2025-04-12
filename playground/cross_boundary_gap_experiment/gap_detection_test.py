#!/usr/bin/env python3
"""
Gap Detection Test Script

This script demonstrates the refined gap detection algorithm from utils/gap_detector.py,
focusing on identifying time series gaps using a fixed interval and 30% threshold approach.
"""

from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import argparse
import sys

from utils.logger_setup import logger
from utils.market_constraints import Interval
from rich import print

# Import the refined gap detector
from utils.gap_detector import (
    detect_gaps,
    format_gaps_for_display,
    analyze_file_for_gaps,
)


def create_test_data(
    start_time: datetime,
    end_time: datetime,
    interval: Interval,
    gap_positions: list = None,
    gap_sizes: list = None,
) -> pd.DataFrame:
    """
    Create test data with specified gaps for testing the gap detector.

    Args:
        start_time: Start time for the dataset
        end_time: End time for the dataset
        interval: Interval between data points
        gap_positions: List of positions (as datetime) where to insert gaps
        gap_sizes: List of gap sizes (in intervals) corresponding to gap_positions

    Returns:
        DataFrame with test data
    """
    if gap_positions is None:
        gap_positions = []
    if gap_sizes is None:
        gap_sizes = []

    # Calculate number of points based on interval
    interval_seconds = interval.to_seconds()
    interval_delta = timedelta(seconds=interval_seconds)

    # Generate regular time series
    current_time = start_time
    times = []

    while current_time <= end_time:
        times.append(current_time)
        current_time += interval_delta

    # Insert gaps by removing points
    if gap_positions and gap_sizes:
        for gap_pos, gap_size in zip(gap_positions, gap_sizes):
            # Find the closest time point
            closest_idx = min(range(len(times)), key=lambda i: abs(times[i] - gap_pos))

            # Remove gap_size points after the closest point
            if closest_idx < len(times) - gap_size:
                times = times[: closest_idx + 1] + times[closest_idx + 1 + gap_size :]

    # Create DataFrame
    df = pd.DataFrame(
        {
            "open_time": times,
            "open": np.random.random(len(times)) * 100
            + 20000,  # Random BTC-like prices
            "high": np.random.random(len(times)) * 100 + 20100,
            "low": np.random.random(len(times)) * 100 + 19900,
            "close": np.random.random(len(times)) * 100 + 20050,
            "volume": np.random.random(len(times)) * 10,
        }
    )

    return df


def run_test_scenarios():
    """Run various test scenarios to demonstrate gap detection."""
    logger.info("Running gap detection test scenarios")

    # Test Scenario 1: Regular intervals with no gaps
    logger.info("Test Scenario 1: Regular intervals with no gaps")
    start_time = datetime(2025, 4, 10, 23, 50, 0)
    end_time = datetime(2025, 4, 11, 0, 10, 0)

    df1 = create_test_data(start_time, end_time, Interval.MINUTE_1)

    # Set enforce_min_span to False for small test datasets
    gaps1, stats1 = detect_gaps(df1, Interval.MINUTE_1, enforce_min_span=False)

    print(f"[bold]Scenario 1 Results:[/bold]")
    print(f"Total records: {stats1['total_records']}")
    print(f"Total gaps: {stats1['total_gaps']}")
    print(f"Day boundary gaps: {stats1['day_boundary_gaps']}")
    print(f"Timespan (hours): {stats1.get('timespan_hours', 0):.2f}")
    print()

    # Test Scenario 2: Regular intervals with a single gap (non-boundary)
    logger.info("Test Scenario 2: Regular intervals with a single gap (non-boundary)")

    gap_positions = [datetime(2025, 4, 10, 23, 55, 0)]
    gap_sizes = [2]  # Skip 2 intervals

    df2 = create_test_data(
        start_time, end_time, Interval.MINUTE_1, gap_positions, gap_sizes
    )
    gaps2, stats2 = detect_gaps(df2, Interval.MINUTE_1, enforce_min_span=False)

    print(f"[bold]Scenario 2 Results:[/bold]")
    print(f"Total records: {stats2['total_records']}")
    print(f"Total gaps: {stats2['total_gaps']}")
    print(f"Day boundary gaps: {stats2['day_boundary_gaps']}")
    print(f"Timespan (hours): {stats2.get('timespan_hours', 0):.2f}")

    if gaps2:
        gaps_df = format_gaps_for_display(gaps2)
        print("\nGap details:")
        print(
            gaps_df[
                [
                    "start_time",
                    "end_time",
                    "duration_seconds",
                    "missing_points",
                    "crosses_day_boundary",
                ]
            ]
        )
    print()

    # Test Scenario 3: Gap at day boundary
    logger.info("Test Scenario 3: Gap at day boundary")

    gap_positions = [datetime(2025, 4, 10, 23, 59, 0)]
    gap_sizes = [2]  # Skip 2 intervals at day boundary

    df3 = create_test_data(
        start_time, end_time, Interval.MINUTE_1, gap_positions, gap_sizes
    )
    gaps3, stats3 = detect_gaps(df3, Interval.MINUTE_1, enforce_min_span=False)

    print(f"[bold]Scenario 3 Results:[/bold]")
    print(f"Total records: {stats3['total_records']}")
    print(f"Total gaps: {stats3['total_gaps']}")
    print(f"Day boundary gaps: {stats3['day_boundary_gaps']}")
    print(f"Timespan (hours): {stats3.get('timespan_hours', 0):.2f}")

    if gaps3:
        gaps_df = format_gaps_for_display(gaps3)
        print("\nGap details:")
        print(
            gaps_df[
                [
                    "start_time",
                    "end_time",
                    "duration_seconds",
                    "missing_points",
                    "crosses_day_boundary",
                ]
            ]
        )
    print()

    # Test Scenario 4: Multiple gaps of varying sizes
    logger.info("Test Scenario 4: Multiple gaps of varying sizes")

    gap_positions = [
        datetime(2025, 4, 10, 23, 52, 0),
        datetime(2025, 4, 10, 23, 56, 0),
        datetime(2025, 4, 11, 0, 3, 0),
    ]
    gap_sizes = [1, 3, 2]  # Different gap sizes

    df4 = create_test_data(
        start_time, end_time, Interval.MINUTE_1, gap_positions, gap_sizes
    )
    gaps4, stats4 = detect_gaps(df4, Interval.MINUTE_1, enforce_min_span=False)

    print(f"[bold]Scenario 4 Results:[/bold]")
    print(f"Total records: {stats4['total_records']}")
    print(f"Total gaps: {stats4['total_gaps']}")
    print(f"Day boundary gaps: {stats4['day_boundary_gaps']}")
    print(f"Timespan (hours): {stats4.get('timespan_hours', 0):.2f}")

    if gaps4:
        gaps_df = format_gaps_for_display(gaps4)
        print("\nGap details:")
        print(
            gaps_df[
                [
                    "start_time",
                    "end_time",
                    "duration_seconds",
                    "missing_points",
                    "crosses_day_boundary",
                ]
            ]
        )
    print()

    # Test Scenario 5: Test with different intervals (1 hour)
    logger.info("Test Scenario 5: Test with 1-hour intervals")

    start_time_h = datetime(2025, 4, 10, 20, 0, 0)
    end_time_h = datetime(2025, 4, 11, 4, 0, 0)

    gap_positions = [datetime(2025, 4, 10, 23, 0, 0)]
    gap_sizes = [2]  # Skip 2 hourly intervals at day boundary

    df5 = create_test_data(
        start_time_h, end_time_h, Interval.HOUR_1, gap_positions, gap_sizes
    )
    gaps5, stats5 = detect_gaps(df5, Interval.HOUR_1, enforce_min_span=False)

    print(f"[bold]Scenario 5 Results (1-hour interval):[/bold]")
    print(f"Total records: {stats5['total_records']}")
    print(f"Total gaps: {stats5['total_gaps']}")
    print(f"Day boundary gaps: {stats5['day_boundary_gaps']}")
    print(f"Timespan (hours): {stats5.get('timespan_hours', 0):.2f}")

    if gaps5:
        gaps_df = format_gaps_for_display(gaps5)
        print("\nGap details:")
        print(
            gaps_df[
                [
                    "start_time",
                    "end_time",
                    "duration_seconds",
                    "missing_points",
                    "crosses_day_boundary",
                ]
            ]
        )
    print()

    # Test Scenario 6: Multi-day data with 23+ hour span
    logger.info("Test Scenario 6: Multi-day data with 23+ hour span")

    # Create test data spanning 25 hours
    start_time_multiday = datetime(2025, 4, 10, 0, 0, 0)
    end_time_multiday = datetime(2025, 4, 11, 1, 0, 0)  # 25 hours span

    df6 = create_test_data(start_time_multiday, end_time_multiday, Interval.HOUR_1)

    # Create gap around 10:00-12:00 on first day
    df6 = df6[
        ~(
            (df6["open_time"] >= datetime(2025, 4, 10, 10, 0, 0))
            & (df6["open_time"] <= datetime(2025, 4, 10, 12, 0, 0))
        )
    ]

    # With enforce_min_span=True by default
    gaps6, stats6 = detect_gaps(df6, Interval.HOUR_1)

    print(f"[bold]Scenario 6 Results (Multi-day data):[/bold]")
    print(f"Total records: {stats6['total_records']}")
    print(f"Total gaps: {stats6['total_gaps']}")
    print(f"Day boundary gaps: {stats6['day_boundary_gaps']}")
    print(f"Timespan (hours): {stats6.get('timespan_hours', 0):.2f}")

    if gaps6:
        gaps_df = format_gaps_for_display(gaps6)
        print("\nGap details:")
        print(
            gaps_df[
                [
                    "start_time",
                    "end_time",
                    "duration_seconds",
                    "missing_points",
                    "crosses_day_boundary",
                ]
            ]
        )
    print()

    # Test Scenario 7: Demonstrating file combination before gap detection
    logger.info("Test Scenario 7: Demonstrating file combination")

    # Create two separate day files
    day1_start = datetime(2025, 4, 10, 0, 0, 0)
    day1_end = datetime(2025, 4, 10, 23, 59, 0)
    day1_df = create_test_data(day1_start, day1_end, Interval.HOUR_1)

    day2_start = datetime(2025, 4, 11, 0, 0, 0)
    day2_end = datetime(2025, 4, 11, 23, 59, 0)
    day2_df = create_test_data(day2_start, day2_end, Interval.HOUR_1)

    # Try to analyze each day separately - this would normally exit the program
    print(
        "\n[bold]Testing single-day file (should trigger minimum span requirement):[/bold]"
    )
    print(
        "This would normally exit the program, but we'll catch and display the error for demonstration."
    )

    try:
        # Save the standard exit function temporarily
        original_exit = sys.exit
        sys.exit = lambda code: print(
            f"[bold red]Would have exited with code {code}[/bold red]"
        )

        # This should trigger the minimum span requirement error
        gaps_day1, stats_day1 = detect_gaps(day1_df, Interval.HOUR_1)

        # Restore exit function
        sys.exit = original_exit
    except Exception as e:
        print(f"[bold red]Error: {str(e)}[/bold red]")
    finally:
        # Make sure exit function is restored
        sys.exit = original_exit

    # Demonstrate proper way: combine files first
    print("\n[bold]Demonstrating proper file combination before analysis:[/bold]")
    combined_df = (
        pd.concat([day1_df, day2_df]).sort_values("open_time").reset_index(drop=True)
    )
    gaps_combined, stats_combined = detect_gaps(combined_df, Interval.HOUR_1)

    print(
        f"Combined data timespan (hours): {stats_combined.get('timespan_hours', 0):.2f}"
    )
    print(f"Total records: {stats_combined['total_records']}")
    print(f"Total gaps: {stats_combined['total_gaps']}")

    # Test Scenario 8: Demonstrating strict Interval enum validation
    logger.info("Test Scenario 8: Demonstrating strict Interval enum validation")

    start_time = datetime(2025, 4, 10, 23, 50, 0)
    end_time = datetime(2025, 4, 11, 0, 10, 0)
    df8 = create_test_data(start_time, end_time, Interval.MINUTE_1)

    print("\n[bold]Testing invalid interval type:[/bold]")
    print(
        "This would normally exit the program, but we'll catch and display the error for demonstration."
    )

    # Test with a string interval instead of an Interval enum
    try:
        # Save the standard exit function temporarily
        original_exit = sys.exit
        sys.exit = lambda code: print(
            f"[bold red]Would have exited with code {code}[/bold red]"
        )

        # This should trigger the interval type validation error
        invalid_interval = "1m"  # String instead of Interval enum
        gaps_invalid, stats_invalid = detect_gaps(
            df8, invalid_interval, enforce_min_span=False
        )

        # Restore exit function
        sys.exit = original_exit
    except Exception as e:
        print(f"[bold red]Error: {str(e)}[/bold red]")
    finally:
        # Make sure exit function is restored
        sys.exit = original_exit

    # Test with a numeric interval instead of an Interval enum
    try:
        # Save the standard exit function temporarily
        original_exit = sys.exit
        sys.exit = lambda code: print(
            f"[bold red]Would have exited with code {code}[/bold red]"
        )

        # This should trigger the interval type validation error
        invalid_interval = 60  # 60 seconds instead of Interval.MINUTE_1
        gaps_invalid, stats_invalid = detect_gaps(
            df8, invalid_interval, enforce_min_span=False
        )

        # Restore exit function
        sys.exit = original_exit
    except Exception as e:
        print(f"[bold red]Error: {str(e)}[/bold red]")
    finally:
        # Make sure exit function is restored
        sys.exit = original_exit

    print("\n[bold]Example of correct Interval enum usage:[/bold]")
    # Using the correct Interval enum
    valid_interval = Interval.MINUTE_1
    print(f"Valid interval: {valid_interval} (type: {type(valid_interval)})")
    print(f"Available intervals: {', '.join([i.value for i in Interval])}")

    # Now add Scenario 8 to the summary
    print(f"\n[bold]Summary of all test scenarios:[/bold]")
    print(f"Scenario 1: {stats1['total_gaps']} gaps detected (regular intervals)")
    print(f"Scenario 2: {stats2['total_gaps']} gaps detected (single non-boundary gap)")
    print(f"Scenario 3: {stats3['total_gaps']} gaps detected (day boundary gap)")
    print(f"Scenario 4: {stats4['total_gaps']} gaps detected (multiple gaps)")
    print(f"Scenario 5: {stats5['total_gaps']} gaps detected (1-hour intervals)")
    print(f"Scenario 6: {stats6['total_gaps']} gaps detected (multi-day 25-hour span)")
    print(f"Scenario 7: {stats_combined['total_gaps']} gaps detected (combined files)")
    print(f"Scenario 8: Demonstrated strict Interval enum validation")

    # Test threshold variations
    print("\n[bold]Testing threshold variations:[/bold]")
    # Use scenario 4 data with different thresholds
    thresholds = [0.1, 0.3, 0.5, 1.0]

    for threshold in thresholds:
        gaps, stats = detect_gaps(
            df4, Interval.MINUTE_1, gap_threshold=threshold, enforce_min_span=False
        )
        print(f"Threshold {threshold*100}%: {stats['total_gaps']} gaps detected")


def run_file_analysis(file_path: str, interval_str: str):
    """Analyze a specific file for gaps."""
    file_path = Path(file_path)

    # Convert interval string to Interval enum
    try:
        interval = next(i for i in Interval if i.value == interval_str)
    except StopIteration:
        logger.error(f"Invalid interval: {interval_str}")
        return

    logger.info(f"Analyzing file {file_path} with interval {interval.value}")

    gaps, stats = analyze_file_for_gaps(file_path, interval)

    print(f"[bold]Analysis Results for {file_path}:[/bold]")
    print(f"Interval: {interval.value}")
    print(f"Total records: {stats.get('total_records', 'N/A')}")
    print(f"First timestamp: {stats.get('first_timestamp', 'N/A')}")
    print(f"Last timestamp: {stats.get('last_timestamp', 'N/A')}")
    print(f"Total gaps: {stats.get('total_gaps', 'N/A')}")
    print(f"Day boundary gaps: {stats.get('day_boundary_gaps', 'N/A')}")
    print(f"Non-boundary gaps: {stats.get('non_boundary_gaps', 'N/A')}")
    print(f"Max gap duration: {stats.get('max_gap_duration', 'N/A')}")

    if "error" in stats:
        print(f"Error: {stats['error']}")
        return

    if gaps:
        gaps_df = format_gaps_for_display(gaps)
        print("\n[bold]Gap details:[/bold]")
        print(
            gaps_df[
                [
                    "start_time",
                    "end_time",
                    "duration_seconds",
                    "missing_points",
                    "crosses_day_boundary",
                ]
            ]
        )
    else:
        print("\nNo gaps detected!")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test the gap detection algorithm")
    parser.add_argument("--file", "-f", help="Path to a CSV file to analyze")
    parser.add_argument(
        "--interval", "-i", default="1m", help="Interval for analysis (1s, 1m, 1h)"
    )
    parser.add_argument(
        "--run-tests", "-t", action="store_true", help="Run test scenarios"
    )

    args = parser.parse_args()

    if args.run_tests:
        run_test_scenarios()
    elif args.file:
        run_file_analysis(args.file, args.interval)
    else:
        print("No action specified. Use --run-tests or --file.")
        parser.print_help()


if __name__ == "__main__":
    main()
