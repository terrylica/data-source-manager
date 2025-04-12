#!/usr/bin/env python3
"""
Binance Cross-Day Boundary Gap Analyzer for April 10-11, 2025 Data

This script analyzes Binance data for potential gaps across day boundaries,
specifically for April 10-11, 2025 with 1-minute interval data.
"""

from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import pytz
from typing import List, Dict, Any

from utils.logger_setup import logger
from utils.market_constraints import Interval

# Configuration
SYMBOL = "BTCUSDT"
DATA_PATH = Path("/workspaces/binance-data-services/cache/BINANCE/KLINES/spot")
APRIL_10 = "20250410"
APRIL_11 = "20250411"
INTERVAL = Interval.MINUTE_1
INTERVAL_SECONDS = INTERVAL.to_seconds()  # 60 seconds for 1 minute


def load_parquet_data(date_str: str) -> pd.DataFrame:
    """
    Load data from a parquet file for a specific date.

    Args:
        date_str: Date string in format YYYYMMDD

    Returns:
        DataFrame containing the data
    """
    file_path = DATA_PATH / SYMBOL / INTERVAL.value / f"{date_str}.parquet"

    if not file_path.exists():
        logger.error(f"Data file not found: {file_path}")
        return pd.DataFrame()

    try:
        logger.info(f"Loading data from {file_path}")
        df = pd.read_parquet(file_path)

        # Ensure we have timestamp column
        if "open_time" in df.columns and "timestamp" not in df.columns:
            df["timestamp"] = df["open_time"]

        # Convert timestamps to datetime
        if isinstance(df["timestamp"].iloc[0], (int, float)):
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        else:
            df["datetime"] = df["timestamp"]

        # Sort by timestamp
        df = df.sort_values("timestamp").reset_index(drop=True)

        logger.info(f"Loaded {len(df)} records for {date_str}")
        return df

    except Exception as e:
        logger.error(f"Error loading data from {file_path}: {e}")
        return pd.DataFrame()


def find_gaps(df: pd.DataFrame, interval_seconds: int) -> List[Dict[str, Any]]:
    """
    Find gaps in a DataFrame based on the expected time interval.

    Args:
        df: DataFrame with 'timestamp' and 'datetime' columns
        interval_seconds: Expected interval between records in seconds

    Returns:
        List of dictionaries with gap information
    """
    if df.empty or len(df) < 2:
        return []

    # Calculate time differences
    df = df.copy()
    df["next_timestamp"] = df["timestamp"].shift(-1)
    df["next_datetime"] = df["datetime"].shift(-1)

    if isinstance(df["timestamp"].iloc[0], pd.Timestamp):
        df["time_diff_seconds"] = (
            df["next_timestamp"] - df["timestamp"]
        ).dt.total_seconds()
    else:
        df["time_diff_seconds"] = (
            df["next_timestamp"] - df["timestamp"]
        ) / 1000  # ms to seconds

    # Find gaps (where time difference is greater than expected interval + 10% tolerance)
    gaps_df = df[df["time_diff_seconds"] > interval_seconds * 1.1].copy()

    # Format gaps for output
    gaps = []
    for _, row in gaps_df.iterrows():
        start_time = row["datetime"]
        end_time = row["next_datetime"]
        missing_points = int((row["time_diff_seconds"] / interval_seconds) - 1)

        # Check if this is a day boundary gap
        next_day = start_time.replace(hour=0, minute=0, second=0) + timedelta(days=1)
        is_day_boundary = start_time < next_day < end_time

        # Check if midnight is exactly missing
        missing_midnight = False
        if is_day_boundary:
            # If there's a gap across midnight, check if midnight itself is missing
            if (
                next_day.timestamp() - start_time.timestamp() > interval_seconds
                and end_time.timestamp() - next_day.timestamp() > interval_seconds
            ):
                missing_midnight = True

        gap = {
            "from": start_time,
            "to": end_time,
            "duration_seconds": row["time_diff_seconds"],
            "missing_points": missing_points,
            "is_day_boundary": is_day_boundary,
            "missing_midnight": missing_midnight,
        }

        gaps.append(gap)

    return gaps


def analyze_day_boundary() -> Dict[str, Any]:
    """
    Analyze the day boundary between April 10 and April 11, 2025.

    Returns:
        Dictionary with analysis results
    """
    # Load data for both days
    df_april_10 = load_parquet_data(APRIL_10)
    df_april_11 = load_parquet_data(APRIL_11)

    if df_april_10.empty or df_april_11.empty:
        logger.error("Could not load data for one or both days")
        return {"error": "Data loading failed"}

    # Get the last few records from April 10
    april_10_tail = df_april_10.tail(5)

    # Get the first few records from April 11
    april_11_head = df_april_11.head(5)

    # Combine and sort the boundary data
    boundary_df = pd.concat([april_10_tail, april_11_head])
    boundary_df = boundary_df.sort_values("timestamp").reset_index(drop=True)

    # Find gaps in the boundary data
    gaps = find_gaps(boundary_df, INTERVAL_SECONDS)

    # Get the last record of April 10 and first record of April 11
    last_april_10 = df_april_10.iloc[-1]
    first_april_11 = df_april_11.iloc[0]

    # Calculate the expected midnight timestamp
    midnight = datetime.strptime("2025-04-11 00:00:00", "%Y-%m-%d %H:%M:%S").replace(
        tzinfo=pytz.UTC
    )

    # Check if midnight timestamp exists in either day's data
    midnight_ts = int(midnight.timestamp() * 1000)  # Convert to milliseconds

    # For pandas timestamp comparison
    if isinstance(df_april_10["timestamp"].iloc[0], pd.Timestamp):
        midnight_in_april_10 = any(
            abs((t - midnight).total_seconds()) < 1 for t in df_april_10["datetime"]
        )
        midnight_in_april_11 = any(
            abs((t - midnight).total_seconds()) < 1 for t in df_april_11["datetime"]
        )
    else:
        # For millisecond timestamp comparison
        midnight_in_april_10 = any(
            abs(t - midnight_ts) < 1000 for t in df_april_10["timestamp"]
        )
        midnight_in_april_11 = any(
            abs(t - midnight_ts) < 1000 for t in df_april_11["timestamp"]
        )

    # Calculate the time difference between last record of April 10 and first record of April 11
    if isinstance(last_april_10["datetime"], pd.Timestamp):
        time_diff_seconds = (
            first_april_11["datetime"] - last_april_10["datetime"]
        ).total_seconds()
    else:
        time_diff_seconds = (
            first_april_11["timestamp"] - last_april_10["timestamp"]
        ) / 1000

    boundary_info = {
        "last_record_april_10": last_april_10["datetime"],
        "first_record_april_11": first_april_11["datetime"],
        "midnight": midnight,
        "midnight_in_april_10": midnight_in_april_10,
        "midnight_in_april_11": midnight_in_april_11,
        "time_diff_seconds": time_diff_seconds,
        "expected_interval_seconds": INTERVAL_SECONDS,
    }

    return {
        "interval": INTERVAL,
        "gaps": gaps,
        "boundary_info": boundary_info,
        "boundary_data": boundary_df[
            ["timestamp", "datetime", "open", "close"]
        ].to_dict("records"),
    }


def analyze_full_days() -> Dict[str, Any]:
    """
    Analyze the full days of April 10 and April 11, 2025.

    Returns:
        Dictionary with analysis results
    """
    # Load data for both days
    df_april_10 = load_parquet_data(APRIL_10)
    df_april_11 = load_parquet_data(APRIL_11)

    if df_april_10.empty or df_april_11.empty:
        logger.error("Could not load data for one or both days")
        return {"error": "Data loading failed"}

    # Find gaps in each day
    gaps_april_10 = find_gaps(df_april_10, INTERVAL_SECONDS)
    gaps_april_11 = find_gaps(df_april_11, INTERVAL_SECONDS)

    # Count day boundary gaps
    boundary_gaps_april_10 = sum(1 for gap in gaps_april_10 if gap["is_day_boundary"])
    boundary_gaps_april_11 = sum(1 for gap in gaps_april_11 if gap["is_day_boundary"])

    # Find maximum gap duration
    max_duration_april_10 = max(
        [gap["duration_seconds"] for gap in gaps_april_10], default=0
    )
    max_duration_april_11 = max(
        [gap["duration_seconds"] for gap in gaps_april_11], default=0
    )

    return {
        "interval": INTERVAL,
        "april_10": {
            "total_records": len(df_april_10),
            "total_gaps": len(gaps_april_10),
            "boundary_gaps": boundary_gaps_april_10,
            "non_boundary_gaps": len(gaps_april_10) - boundary_gaps_april_10,
            "max_gap_duration": max_duration_april_10,
            "gaps": gaps_april_10,
        },
        "april_11": {
            "total_records": len(df_april_11),
            "total_gaps": len(gaps_april_11),
            "boundary_gaps": boundary_gaps_april_11,
            "non_boundary_gaps": len(gaps_april_11) - boundary_gaps_april_11,
            "max_gap_duration": max_duration_april_11,
            "gaps": gaps_april_11,
        },
    }


def main():
    """Main function to run the analysis"""
    logger.info("Starting analysis of April 10-11, 2025 data with 1-minute interval")

    # Analyze the full days
    logger.info("\n=== Analyzing full days ===")
    full_days_results = analyze_full_days()

    if "error" in full_days_results:
        logger.error(f"Full days analysis failed: {full_days_results['error']}")
    else:
        april_10_data = full_days_results["april_10"]
        april_11_data = full_days_results["april_11"]

        logger.info(
            f"April 10: {april_10_data['total_records']} records, {april_10_data['total_gaps']} gaps"
        )
        if april_10_data["total_gaps"] > 0:
            logger.info(f"  Boundary gaps: {april_10_data['boundary_gaps']}")
            logger.info(f"  Non-boundary gaps: {april_10_data['non_boundary_gaps']}")
            logger.info(
                f"  Max gap duration: {april_10_data['max_gap_duration']} seconds"
            )

        logger.info(
            f"April 11: {april_11_data['total_records']} records, {april_11_data['total_gaps']} gaps"
        )
        if april_11_data["total_gaps"] > 0:
            logger.info(f"  Boundary gaps: {april_11_data['boundary_gaps']}")
            logger.info(f"  Non-boundary gaps: {april_11_data['non_boundary_gaps']}")
            logger.info(
                f"  Max gap duration: {april_11_data['max_gap_duration']} seconds"
            )

    # Analyze the day boundary
    logger.info("\n=== Analyzing day boundary ===")
    boundary_results = analyze_day_boundary()

    if "error" in boundary_results:
        logger.error(f"Day boundary analysis failed: {boundary_results['error']}")
    else:
        boundary_info = boundary_results["boundary_info"]
        gaps = boundary_results["gaps"]

        logger.info(f"Last record April 10: {boundary_info['last_record_april_10']}")
        logger.info(f"First record April 11: {boundary_info['first_record_april_11']}")
        logger.info(f"Time difference: {boundary_info['time_diff_seconds']} seconds")
        logger.info(
            f"Midnight record in April 10 data: {boundary_info['midnight_in_april_10']}"
        )
        logger.info(
            f"Midnight record in April 11 data: {boundary_info['midnight_in_april_11']}"
        )

        logger.info(f"Boundary gaps found: {len(gaps)}")
        for i, gap in enumerate(gaps):
            logger.info(f"\nGap {i+1}:")
            logger.info(f"  From: {gap['from']}")
            logger.info(f"  To: {gap['to']}")
            logger.info(f"  Duration: {gap['duration_seconds']} seconds")
            logger.info(f"  Missing points: {gap['missing_points']}")
            logger.info(f"  Is day boundary: {gap['is_day_boundary']}")
            logger.info(f"  Missing midnight: {gap['missing_midnight']}")

    logger.info("\nAnalysis completed.")


if __name__ == "__main__":
    main()
