#!/usr/bin/env python3
"""
Verify gap detection on April 10-11, 2025 data with the new gap detector.

This script compares the results of the new gap detector with our previous manual analysis.
"""

from pathlib import Path
import pandas as pd
from datetime import datetime

from utils.logger_setup import logger
from rich import print
from utils.market_constraints import Interval
from utils.gap_detector import GapDetector

# Configuration
SYMBOL = "BTCUSDT"
DATA_PATH = Path("/workspaces/binance-data-services/cache/BINANCE/KLINES/spot")
APRIL_10 = "20250410"
APRIL_11 = "20250411"


def load_parquet_data(date_str: str, interval: Interval) -> pd.DataFrame:
    """Load parquet data for the given date and interval."""
    file_path = DATA_PATH / SYMBOL / interval.value / f"{date_str}.parquet"

    if not file_path.exists():
        logger.error(f"Data file not found: {file_path}")
        return pd.DataFrame()

    logger.info(f"Loading data from {file_path}")
    return pd.read_parquet(file_path)


def analyze_interval(interval: Interval):
    """Analyze data for the given interval."""
    logger.info(f"\n=== Analyzing {interval.value} data ===")

    # Load data
    df_april_10 = load_parquet_data(APRIL_10, interval)
    df_april_11 = load_parquet_data(APRIL_11, interval)

    if df_april_10.empty or df_april_11.empty:
        logger.error(f"Could not load data for {interval.value}")
        return

    logger.info(f"April 10: {len(df_april_10)} records")
    logger.info(f"April 11: {len(df_april_11)} records")

    # Determine timestamp column
    possible_timestamp_cols = ["timestamp", "open_time", "close_time", "time"]
    timestamp_col = None
    for col in possible_timestamp_cols:
        if col in df_april_10.columns:
            timestamp_col = col
            break

    if timestamp_col is None:
        logger.error(f"No timestamp column found. Columns: {list(df_april_10.columns)}")
        return

    logger.info(f"Using '{timestamp_col}' as timestamp column")

    # Create detector
    detector = GapDetector()

    # Analyze entire days
    april_10_result = detector.analyze_full_dataset(
        df_april_10, interval, timestamp_col=timestamp_col
    )
    april_11_result = detector.analyze_full_dataset(
        df_april_11, interval, timestamp_col=timestamp_col
    )

    logger.info(f"\nApril 10 analysis:")
    logger.info(f"  Total records: {april_10_result['total_records']}")
    logger.info(f"  Total gaps: {april_10_result['total_gaps']}")
    logger.info(f"  Day boundary gaps: {april_10_result['day_boundary_gaps']}")
    logger.info(f"  Non-boundary gaps: {april_10_result['non_boundary_gaps']}")

    logger.info(f"\nApril 11 analysis:")
    logger.info(f"  Total records: {april_11_result['total_records']}")
    logger.info(f"  Total gaps: {april_11_result['total_gaps']}")
    logger.info(f"  Day boundary gaps: {april_11_result['day_boundary_gaps']}")
    logger.info(f"  Non-boundary gaps: {april_11_result['non_boundary_gaps']}")

    # Analyze day boundary
    boundary_result = detector.analyze_day_boundary(
        df_april_10, df_april_11, interval, timestamp_col=timestamp_col
    )

    logger.info(f"\nDay boundary analysis:")
    logger.info(
        f"  Last record April 10: {boundary_result['boundary_info']['last_record_first_day']}"
    )
    logger.info(
        f"  First record April 11: {boundary_result['boundary_info']['first_record_second_day']}"
    )
    logger.info(
        f"  Time difference: {boundary_result['boundary_info']['time_diff_seconds']} seconds"
    )
    logger.info(
        f"  Expected interval: {boundary_result['boundary_info']['expected_interval_seconds']} seconds"
    )
    logger.info(
        f"  Midnight in April 10 data: {boundary_result['boundary_info']['midnight_in_first_day']}"
    )
    logger.info(
        f"  Midnight in April 11 data: {boundary_result['boundary_info']['midnight_in_second_day']}"
    )
    logger.info(f"  Number of boundary gaps: {len(boundary_result['gaps'])}")

    # Check midnight directly
    midnight_check_april_10 = detector.check_missing_midnight(
        df_april_10, "2025-04-11", interval, timestamp_col=timestamp_col
    )

    midnight_check_april_11 = detector.check_missing_midnight(
        df_april_11, "2025-04-11", interval, timestamp_col=timestamp_col
    )

    logger.info(f"\nMidnight check (2025-04-11 00:00:00):")
    logger.info(
        f"  Midnight exists in April 10 data: {midnight_check_april_10['midnight_exists']}"
    )
    logger.info(
        f"  Midnight exists in April 11 data: {midnight_check_april_11['midnight_exists']}"
    )


def main():
    """Main function to run the verification."""
    logger.info("Starting verification of April 10-11 data with new gap detector")

    # Analyze 1-minute data
    analyze_interval(Interval.MINUTE_1)

    # Analyze 1-hour data
    analyze_interval(Interval.HOUR_1)

    logger.info("\nVerification completed.")


if __name__ == "__main__":
    main()
