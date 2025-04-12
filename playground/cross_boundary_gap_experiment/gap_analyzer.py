#!/usr/bin/env python3
"""
Binance Cross-Day Boundary Gap Analyzer

This script analyzes Binance data for potential gaps across day boundaries,
focusing on the dates around the samples analyzed in the Gap_Cross_Day_CSV_Examine.md document.
It downloads data for the week before and after the previously analyzed dates.
"""

from pathlib import Path
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
import logging
import httpx
from typing import Tuple, Dict, Any, Optional
import io
import pytz

from utils.logger_setup import logger
from utils.market_constraints import MarketType, Interval

# Configuration
SYMBOL = "BTCUSDT"
MARKET_TYPE = MarketType.SPOT
BASE_CACHE_DIR = Path(tempfile.gettempdir()) / "binance_gap_analysis"

# Time periods to analyze
# 1. Around March 15-16, 2025 (1s data)
MARCH_START_DATE = datetime(2025, 3, 15, tzinfo=timezone.utc)  # Full day
MARCH_END_DATE = datetime(2025, 3, 16, tzinfo=timezone.utc)  # Full day

# 2. Around March 20-21, 2025 (1h data)
MARCH_HOUR_START_DATE = datetime(2025, 3, 20, tzinfo=timezone.utc)  # Full day
MARCH_HOUR_END_DATE = datetime(2025, 3, 21, tzinfo=timezone.utc)  # Full day

# 3. Around April 10-11, 2025 (1m data)
APRIL_START_DATE = datetime(2025, 4, 10, tzinfo=timezone.utc)  # Full day
APRIL_END_DATE = datetime(2025, 4, 11, tzinfo=timezone.utc)  # Full day


def setup_logging():
    """Configure logging for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def get_binance_vision_url(
    symbol: str,
    interval: Interval,
    date: datetime,
    market_type: MarketType = MarketType.SPOT,
) -> str:
    """
    Generate Binance Vision API URL for daily kline data.

    Args:
        symbol: Trading pair symbol (e.g., BTCUSDT)
        interval: Kline interval (e.g., 1m, 1h)
        date: Date to retrieve data for
        market_type: Type of market (SPOT, FUTURES_USDT, or FUTURES_COIN)

    Returns:
        URL for the specified data
    """
    date_str = date.strftime("%Y-%m-%d")

    if market_type == MarketType.SPOT:
        return f"https://data.binance.vision/data/spot/daily/klines/{symbol}/{interval.value}/{symbol}-{interval.value}-{date_str}.zip"
    elif market_type == MarketType.FUTURES_USDT:
        return f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/{interval.value}/{symbol}-{interval.value}-{date_str}.zip"
    elif market_type == MarketType.FUTURES_COIN:
        return f"https://data.binance.vision/data/futures/cm/daily/klines/{symbol}_PERP/{interval.value}/{symbol}_PERP-{interval.value}-{date_str}.zip"
    else:
        raise ValueError(f"Unsupported market type: {market_type}")


def download_binance_data(
    symbol: str,
    interval: Interval,
    start_date: datetime,
    end_date: datetime,
    market_type: MarketType = MarketType.SPOT,
    cache_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """
    Download Binance data for the specified symbol, interval, and date range.

    Args:
        symbol: Trading pair symbol (e.g., BTCUSDT)
        interval: Kline interval (e.g., 1m, 1h)
        start_date: Start date for data retrieval
        end_date: End date for data retrieval
        market_type: Type of market (SPOT, FUTURES_USDT, or FUTURES_COIN)
        cache_dir: Directory to store downloaded data (uses temp dir if None)

    Returns:
        DataFrame containing the concatenated data for the date range
    """
    if cache_dir is None:
        cache_dir = BASE_CACHE_DIR / symbol / interval.value

    os.makedirs(cache_dir, exist_ok=True)

    # Generate list of dates to download
    current_date = start_date
    all_dfs = []

    # Create httpx client with timeout
    client = httpx.Client(timeout=30.0)

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        cache_file = cache_dir / f"{symbol}-{interval.value}-{date_str}.csv"

        if cache_file.exists():
            logger.info(f"Using cached data for {date_str}")
            df = pd.read_csv(cache_file)
        else:
            url = get_binance_vision_url(symbol, interval, current_date, market_type)

            try:
                logger.info(f"Downloading data for {date_str} from {url}")
                response = client.get(url)
                response.raise_for_status()

                # Use pandas to read directly from the ZIP file
                df = pd.read_csv(
                    io.BytesIO(response.content), compression="zip", header=None
                )

                # Save the CSV for future use
                df.to_csv(cache_file, index=False, header=False)

                # Add a small delay to avoid rate limiting
                time.sleep(0.5)

            except Exception as e:
                logger.warning(f"Failed to download data for {date_str}: {str(e)}")
                # Continue to next date if this one fails
                current_date += timedelta(days=1)
                continue

        # Check if the data has headers (some futures data has headers)
        if "open_time" not in df.columns:
            if df.shape[1] == 12:  # Standard kline format with 12 columns
                # Assume data follows standard Binance kline format
                df.columns = [
                    "open_time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "close_time",
                    "quote_asset_volume",
                    "count",
                    "taker_buy_volume",
                    "taker_buy_quote_volume",
                    "ignore",
                ]
            else:
                logger.warning(f"Unexpected number of columns: {df.shape[1]}")
                current_date += timedelta(days=1)
                continue

        # Convert timestamps to datetime
        # Check if we're dealing with microsecond precision (2025+ data)
        if len(str(df["open_time"].iloc[0])) > 15:  # microsecond precision
            df["open_time"] = pd.to_datetime(
                df["open_time"] / 1000000, unit="s", utc=True
            )
            df["close_time"] = pd.to_datetime(
                df["close_time"] / 1000000, unit="s", utc=True
            )
        else:  # millisecond precision
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
            df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

        all_dfs.append(df)
        current_date += timedelta(days=1)

    # Close the HTTP client
    client.close()

    if not all_dfs:
        logger.warning(
            f"No data found for {symbol} {interval.value} from {start_date} to {end_date}"
        )
        return pd.DataFrame()

    # Concatenate all DataFrames
    combined_df = pd.concat(all_dfs, ignore_index=True)

    # Sort by open_time and remove duplicates
    combined_df = combined_df.sort_values("open_time").drop_duplicates(
        subset=["open_time"]
    )

    return combined_df


def analyze_time_gaps(
    df: pd.DataFrame, interval: Interval, name: str = ""
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Analyze a DataFrame for gaps in time sequence using our refined gap detection algorithm.

    This implementation uses the streamlined approach from utils/gap_detector.py, with a 30%
    threshold for gap detection based on the expected interval.

    Args:
        df: DataFrame with an 'open_time' column to analyze
        interval: Expected interval between records
        name: Name for this analysis (for logging)

    Returns:
        Tuple of (gaps_df, stats_dict) where:
            - gaps_df: DataFrame with details of each gap found
            - stats_dict: Dictionary with gap statistics
    """
    if df.empty:
        logger.warning(f"Empty DataFrame provided for {name}")
        return pd.DataFrame(), {"total_gaps": 0, "max_gap": 0, "total_records": 0}

    # Import the gap detector functions
    from utils.gap_detector import detect_gaps, format_gaps_for_display

    # Use the refined gap detection algorithm
    gaps, stats = detect_gaps(df, interval, time_column="open_time", gap_threshold=0.3)

    # Format gaps DataFrame for display if gaps were found
    display_gaps = format_gaps_for_display(gaps) if gaps else pd.DataFrame()

    # Ensure stats has the expected format for backward compatibility
    stats["max_gap"] = stats.get("max_gap_duration", pd.Timedelta(0))

    return display_gaps, stats


def run_analysis():
    """Run the complete gap analysis for all configured time periods and intervals."""
    logger.info("Starting Binance cross-day boundary gap analysis")

    # Create list of analyses to run
    analyses = [
        {
            "name": "March 1-second data",
            "symbol": SYMBOL,
            "interval": Interval.SECOND_1,
            "start_date": MARCH_START_DATE,
            "end_date": MARCH_END_DATE,
            "market_type": MARKET_TYPE,
        },
        {
            "name": "March 1-hour data",
            "symbol": SYMBOL,
            "interval": Interval.HOUR_1,
            "start_date": MARCH_HOUR_START_DATE,
            "end_date": MARCH_HOUR_END_DATE,
            "market_type": MARKET_TYPE,
        },
        {
            "name": "April 1-minute data",
            "symbol": SYMBOL,
            "interval": Interval.MINUTE_1,
            "start_date": APRIL_START_DATE,
            "end_date": APRIL_END_DATE,
            "market_type": MARKET_TYPE,
        },
    ]

    results = []

    for analysis in analyses:
        logger.info(f"Running analysis for {analysis['name']}")

        # Download data
        df = download_binance_data(
            symbol=analysis["symbol"],
            interval=analysis["interval"],
            start_date=analysis["start_date"],
            end_date=analysis["end_date"],
            market_type=analysis["market_type"],
        )

        # Analyze gaps
        gaps_df, stats = analyze_time_gaps(df, analysis["interval"], analysis["name"])

        # Debug: print the timestamps around day boundaries
        if "day_boundary" in df.columns:
            day_boundary_records = df[df["day_boundary"]].sort_values("open_time")
            if not day_boundary_records.empty:
                logger.debug(f"Day boundary records for {analysis['name']}:")
                for i, row in day_boundary_records.iterrows():
                    logger.debug(
                        f"  {row['open_time']} -> {row.get('next_time', 'N/A')}"
                    )

        # Store results
        result = {
            "name": analysis["name"],
            "interval": analysis["interval"].value,
            "start_date": analysis["start_date"],
            "end_date": analysis["end_date"],
            "market_type": analysis["market_type"].name,
            "stats": stats,
            "gaps_df": gaps_df,
        }

        results.append(result)

        # Log summary
        logger.info(f"Analysis completed for {analysis['name']}:")
        logger.info(f"  Total records: {stats['total_records']}")
        logger.info(f"  Total gaps: {stats['total_gaps']}")
        logger.info(f"  Day boundary gaps: {stats['day_boundary_gaps']}")
        logger.info(f"  Non-boundary gaps: {stats['non_boundary_gaps']}")
        logger.info(f"  Max gap: {stats['max_gap']}")

        # Detailed report on gaps
        if not gaps_df.empty:
            logger.info("Detected gaps:")
            for _, row in gaps_df.iterrows():
                gap_msg = (
                    f"  Gap detected from {row['open_time']} to {row['next_time']} "
                    f"(duration: {row['gap_duration_str']}, missing points: {row['missing_points']})"
                )
                day_boundary = " [DAY BOUNDARY]" if row["day_boundary"] else ""
                logger.info(f"{gap_msg}{day_boundary}")
                logger.info(
                    f"    Expected next: {row['expected_next_time']}, Actual next: {row['next_time']}"
                )
        else:
            logger.info("  No gaps detected!")

    return results


def analyze_common_patterns(results):
    """Analyze results for common patterns across different intervals."""
    logger.info("Analyzing common patterns across all intervals:")

    # Count total gaps by type
    total_day_boundary_gaps = sum(r["stats"]["day_boundary_gaps"] for r in results)
    total_non_boundary_gaps = sum(r["stats"]["non_boundary_gaps"] for r in results)

    logger.info(
        f"Total day boundary gaps across all analyses: {total_day_boundary_gaps}"
    )
    logger.info(
        f"Total non-boundary gaps across all analyses: {total_non_boundary_gaps}"
    )

    # Analyze if there are any specific days with gaps across multiple intervals
    gap_dates = {}

    for result in results:
        gaps_df = result["gaps_df"]
        if not gaps_df.empty:
            for _, row in gaps_df.iterrows():
                prev_date = row["open_time"].date()
                next_date = row["next_time"].date()

                # For day boundary gaps, record both dates
                if row["day_boundary"]:
                    key = f"{prev_date}-{next_date}"
                    if key not in gap_dates:
                        gap_dates[key] = []
                    gap_dates[key].append(result["interval"])
                else:
                    # For non-boundary gaps, just record the date
                    key = str(prev_date)
                    if key not in gap_dates:
                        gap_dates[key] = []
                    gap_dates[key].append(result["interval"])

    # Report dates that appear in multiple analyses
    common_dates = {k: v for k, v in gap_dates.items() if len(v) > 1}
    if common_dates:
        logger.info("Dates with gaps in multiple intervals:")
        for date_key, intervals in common_dates.items():
            logger.info(f"  {date_key}: {', '.join(intervals)}")
    else:
        logger.info("No dates with gaps in multiple intervals found")


def examine_boundary_data(df: pd.DataFrame, interval: Interval, name: str = ""):
    """
    Examine the raw data around day boundaries to help debug gap detection issues.

    Args:
        df: DataFrame with timestamp data
        interval: Interval being analyzed
        name: Name for this analysis
    """
    logger.info(f"Examining boundary data for {name}")

    # Sort by open_time
    df_sorted = df.sort_values("open_time").copy()

    # Add day information
    df_sorted["day"] = df_sorted["open_time"].dt.date

    # Get unique days
    days = df_sorted["day"].unique()
    logger.info(f"Days in dataset: {days}")

    # Find day boundaries
    for i in range(len(days) - 1):
        current_day = days[i]
        next_day = days[i + 1]

        logger.info(f"Examining boundary between {current_day} and {next_day}")

        # Get last 3 records of current day
        last_records = df_sorted[df_sorted["day"] == current_day].tail(3)
        # Get first 3 records of next day
        first_records = df_sorted[df_sorted["day"] == next_day].head(3)

        # Print details
        if not last_records.empty:
            logger.info(f"Last records of {current_day}:")
            for _, row in last_records.iterrows():
                logger.info(f"  {row['open_time']}")
        else:
            logger.info(f"No records for {current_day}")

        if not first_records.empty:
            logger.info(f"First records of {next_day}:")
            for _, row in first_records.iterrows():
                logger.info(f"  {row['open_time']}")
        else:
            logger.info(f"No records for {next_day}")

        # Calculate time difference between last of current day and first of next day
        if not last_records.empty and not first_records.empty:
            last_time = last_records["open_time"].iloc[-1]
            first_time = first_records["open_time"].iloc[0]
            time_diff = first_time - last_time
            logger.info(f"Time difference: {time_diff}")

            # Calculate expected interval
            expected_seconds = interval.to_seconds()
            expected_interval = pd.Timedelta(seconds=expected_seconds)
            logger.info(f"Expected interval: {expected_interval}")

            # Check if the time difference matches expected interval
            is_expected = abs((time_diff - expected_interval).total_seconds()) < 1
            logger.info(f"Is expected interval? {is_expected}")

            # Check expected next time
            expected_next_time = last_time + pd.Timedelta(seconds=expected_seconds)
            logger.info(f"Expected next time: {expected_next_time}")
            logger.info(f"Actual next time: {first_time}")

            # Check if expected next time exists in the data
            expected_time_exists = (
                abs((df_sorted["open_time"] - expected_next_time).dt.total_seconds())
                < 1
            ).any()
            logger.info(
                f"Does expected next time exist in data? {expected_time_exists}"
            )

    return


def run_iterative_tests():
    """Run an iterative test with the refined gap detection algorithm to ensure correctness."""
    logger.info("Starting iterative gap detection test with refined algorithm")

    # Import the gap detector functions
    from utils.gap_detector import detect_gaps, format_gaps_for_display

    # Create list of test cases to validate gap detection
    test_cases = [
        # 1-second data for March 15-16 (day boundary)
        {
            "name": "1-second day boundary",
            "symbol": SYMBOL,
            "interval": Interval.SECOND_1,
            "start_date": MARCH_START_DATE,
            "end_date": MARCH_END_DATE,
            "market_type": MARKET_TYPE,
            "expected_gaps": 0,  # We expect no gaps
        },
        # 1-hour data for March 20-21 (day boundary)
        {
            "name": "1-hour day boundary",
            "symbol": SYMBOL,
            "interval": Interval.HOUR_1,
            "start_date": MARCH_HOUR_START_DATE,
            "end_date": MARCH_HOUR_END_DATE,
            "market_type": MARKET_TYPE,
            "expected_gaps": 0,  # We expect no gaps
        },
        # 1-minute data for April 10-11 (day boundary)
        {
            "name": "1-minute day boundary",
            "symbol": SYMBOL,
            "interval": Interval.MINUTE_1,
            "start_date": APRIL_START_DATE,
            "end_date": APRIL_END_DATE,
            "market_type": MARKET_TYPE,
            "expected_gaps": 0,  # Confirmed no gaps
        },
    ]

    tests_passed = True

    for test_case in test_cases:
        logger.info(f"Testing refined gap detection for {test_case['name']}")

        # Download data (using our cache from previous runs)
        df = download_binance_data(
            symbol=test_case["symbol"],
            interval=test_case["interval"],
            start_date=test_case["start_date"],
            end_date=test_case["end_date"],
            market_type=test_case["market_type"],
        )

        # Analyze gaps with refined logic
        gaps, stats = detect_gaps(
            df, test_case["interval"], time_column="open_time", gap_threshold=0.3
        )

        # Verify if results match expectations
        logger.info(f"Test results for {test_case['name']}:")
        logger.info(f"  Expected gaps: {test_case['expected_gaps']}")
        logger.info(f"  Detected gaps: {stats['total_gaps']}")

        if stats["total_gaps"] == test_case["expected_gaps"]:
            logger.info(f"  ✅ Test PASSED: Gap detection is correct")
        else:
            tests_passed = False
            logger.error(
                f"  ❌ Test FAILED: Gap detection found {stats['total_gaps']} gaps instead of {test_case['expected_gaps']}"
            )

            # If we found unexpected gaps, print details
            if gaps:
                logger.info("  Detected gaps:")
                gaps_df = format_gaps_for_display(gaps)
                for _, row in gaps_df.iterrows():
                    gap_msg = (
                        f"    Gap from {row['start_time']} to {row['end_time']} "
                        f"(duration: {row['duration']}, missing points: {row['missing_points']})"
                    )
                    day_boundary = (
                        " [DAY BOUNDARY]" if row["crosses_day_boundary"] else ""
                    )
                    logger.info(f"{gap_msg}{day_boundary}")

    # Test with a deliberately introduced gap to ensure algorithm properly detects gaps
    logger.info("Testing with deliberate gap:")

    # Create test data with a gap
    start_time = datetime(2025, 4, 10, 23, 50, 0, tzinfo=timezone.utc)
    end_time = datetime(2025, 4, 11, 0, 10, 0, tzinfo=timezone.utc)

    # Create a clean dataset first
    base_time = start_time
    times = []
    for i in range(21):  # 20 minute span with 1-minute interval
        times.append(base_time)
        base_time += timedelta(minutes=1)

    # Remove 2 points to create a gap
    del times[5:7]  # This creates a 3-minute gap (instead of 1-minute)

    # Create a DataFrame
    df_with_gap = pd.DataFrame(
        {
            "open_time": times,
            "open": np.random.random(len(times)) * 100 + 20000,
        }
    )

    # Detect gaps in the manufactured data
    gaps, stats = detect_gaps(
        df_with_gap, Interval.MINUTE_1, time_column="open_time", gap_threshold=0.3
    )

    logger.info(f"  Deliberate gap test - Expected 1 gap, found: {stats['total_gaps']}")

    if stats["total_gaps"] == 1:
        logger.info("  ✅ Deliberate gap test PASSED")
    else:
        tests_passed = False
        logger.error("  ❌ Deliberate gap test FAILED")

    return tests_passed


class GapAnalyzer:
    """Analyzes data for gaps at day boundaries and across entire datasets."""

    def __init__(self, data_path):
        self.data_path = Path(data_path)

    def find_gaps(self, df, interval_seconds, is_boundary_check=False):
        """
        Find gaps in a DataFrame based on the expected time interval.

        Args:
            df: DataFrame with 'timestamp' column (in milliseconds)
            interval_seconds: Expected interval between records in seconds
            is_boundary_check: Whether this is a day boundary check

        Returns:
            List of dictionaries with gap information
        """
        if df.empty or len(df) < 2:
            return []

        # Convert timestamp to datetime for better readability
        df = df.copy()
        df["datetime"] = pd.to_datetime(df["timestamp"] / 1000, unit="s", utc=True)
        df = df.sort_values("timestamp")

        # Calculate time differences in seconds
        df["next_timestamp"] = df["timestamp"].shift(-1)
        df["time_diff"] = (
            df["next_timestamp"] - df["timestamp"]
        ) / 1000  # Convert ms to seconds

        # Expected interval with a small tolerance (for floating point comparisons)
        expected_interval = interval_seconds

        # Identify gaps where time difference is greater than expected
        gaps_df = df[df["time_diff"] > expected_interval * 1.1].copy()  # 10% tolerance

        # Format gaps for output
        gaps = []
        for _, row in gaps_df.iterrows():
            start_time = row["datetime"]
            end_time = pd.to_datetime(row["next_timestamp"] / 1000, unit="s", utc=True)
            missing_points = int((row["time_diff"] / expected_interval) - 1)

            # Determine if this is a day boundary gap (exact midnight)
            is_day_boundary = False
            missing_midnight = False

            # Check if the gap includes exactly midnight (00:00:00)
            next_day = start_time.replace(hour=0, minute=0, second=0) + timedelta(
                days=1
            )
            if start_time < next_day < end_time:
                is_day_boundary = True
                # Check if exactly midnight is missing
                if (
                    next_day.timestamp() - start_time.timestamp() > expected_interval
                    and end_time.timestamp() - next_day.timestamp() > expected_interval
                ):
                    missing_midnight = True

            gap = {
                "from": start_time,
                "to": end_time,
                "duration_seconds": row["time_diff"],
                "missing_points": missing_points,
                "is_day_boundary": is_day_boundary,
                "missing_midnight": missing_midnight,
            }

            # If it's a boundary check, only include day boundary gaps
            if not is_boundary_check or (is_boundary_check and is_day_boundary):
                gaps.append(gap)

        return gaps

    def analyze_day_boundary(self, first_day, second_day, interval_str):
        """
        Analyze the day boundary between two consecutive days.

        Args:
            first_day: Date string for the first day (e.g., '2025-03-15')
            second_day: Date string for the second day (e.g., '2025-03-16')
            interval_str: Interval string ('1s', '1m', '1h')

        Returns:
            Dictionary with analysis results
        """
        # Determine paths for the two days
        symbol = "BTCUSDT"
        if interval_str == "1s":
            interval_seconds = 1
            first_file = (
                self.data_path
                / f"{symbol}/klines/{interval_str}/{symbol}-{interval_str}-{first_day}.csv"
            )
            second_file = (
                self.data_path
                / f"{symbol}/klines/{interval_str}/{symbol}-{interval_str}-{second_day}.csv"
            )
        elif interval_str == "1m":
            interval_seconds = 60
            first_file = (
                self.data_path
                / f"{symbol}/klines/{interval_str}/{symbol}-{interval_str}-{first_day}.csv"
            )
            second_file = (
                self.data_path
                / f"{symbol}/klines/{interval_str}/{symbol}-{interval_str}-{second_day}.csv"
            )
        elif interval_str == "1h":
            interval_seconds = 3600
            first_file = (
                self.data_path
                / f"{symbol}/klines/{interval_str}/{symbol}-{interval_str}-{first_day}.csv"
            )
            second_file = (
                self.data_path
                / f"{symbol}/klines/{interval_str}/{symbol}-{interval_str}-{second_day}.csv"
            )
        else:
            raise ValueError(f"Unsupported interval: {interval_str}")

        # Read the files
        if not first_file.exists() or not second_file.exists():
            raise FileNotFoundError(
                f"Could not find files: {first_file} or {second_file}"
            )

        cols = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "count",
            "taker_buy_volume",
            "taker_buy_quote_volume",
            "ignore",
        ]

        # Read last few records from first day
        first_df = pd.read_csv(first_file, names=cols)
        first_df_tail = first_df.tail(5)  # Use more records for stability

        # Read first few records from second day
        second_df = pd.read_csv(second_file, names=cols)
        second_df_head = second_df.head(5)  # Use more records for stability

        # Combine the boundary data
        boundary_df = pd.concat([first_df_tail, second_df_head])
        boundary_df = boundary_df.sort_values("timestamp")

        # Find gaps
        gaps = self.find_gaps(boundary_df, interval_seconds, is_boundary_check=True)

        # Detailed analysis of the boundary
        first_day_last = first_df.iloc[-1]
        second_day_first = second_df.iloc[0]

        last_datetime = pd.to_datetime(
            first_day_last["timestamp"] / 1000, unit="s", utc=True
        )
        first_datetime = pd.to_datetime(
            second_day_first["timestamp"] / 1000, unit="s", utc=True
        )

        # Calculate the expected timestamp for midnight
        midnight = datetime.strptime(
            f"{second_day} 00:00:00", "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=pytz.UTC)
        midnight_ts = int(midnight.timestamp() * 1000)  # Convert to milliseconds

        # Check if midnight is missing
        midnight_missing = True
        for _, row in boundary_df.iterrows():
            if row["timestamp"] == midnight_ts:
                midnight_missing = False
                break

        boundary_info = {
            "last_record_first_day": last_datetime,
            "first_record_second_day": first_datetime,
            "midnight": midnight,
            "midnight_missing": midnight_missing,
            "time_diff_seconds": (first_datetime - last_datetime).total_seconds(),
            "expected_interval_seconds": interval_seconds,
        }

        # Return combined results
        return {
            "interval": interval_str,
            "first_day": first_day,
            "second_day": second_day,
            "gaps": gaps,
            "boundary_info": boundary_info,
        }

    def analyze_full_file(self, date, interval_str):
        """
        Analyze a full daily file for any gaps.

        Args:
            date: Date string for the day (e.g., '2025-03-15')
            interval_str: Interval string ('1s', '1m', '1h')

        Returns:
            Dictionary with analysis results
        """
        # Determine file path
        symbol = "BTCUSDT"
        file_path = (
            self.data_path
            / f"{symbol}/klines/{interval_str}/{symbol}-{interval_str}-{date}.csv"
        )

        if not file_path.exists():
            raise FileNotFoundError(f"Could not find file: {file_path}")

        # Determine interval in seconds
        if interval_str == "1s":
            interval_seconds = 1
        elif interval_str == "1m":
            interval_seconds = 60
        elif interval_str == "1h":
            interval_seconds = 3600
        else:
            raise ValueError(f"Unsupported interval: {interval_str}")

        # Read the file
        cols = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "count",
            "taker_buy_volume",
            "taker_buy_quote_volume",
            "ignore",
        ]
        df = pd.read_csv(file_path, names=cols)

        # Find gaps
        gaps = self.find_gaps(df, interval_seconds)

        # Count day boundary gaps
        day_boundary_gaps = sum(1 for gap in gaps if gap["is_day_boundary"])
        non_boundary_gaps = len(gaps) - day_boundary_gaps

        # Find maximum gap duration
        max_duration = 0
        if gaps:
            max_duration = max(gap["duration_seconds"] for gap in gaps)

        return {
            "interval": interval_str,
            "date": date,
            "total_records": len(df),
            "total_gaps": len(gaps),
            "day_boundary_gaps": day_boundary_gaps,
            "non_boundary_gaps": non_boundary_gaps,
            "max_gap_duration": max_duration,
            "gaps": gaps,
        }

    def examine_boundary_data(self, first_day, second_day, interval_str):
        """
        Directly examine and print the data around day boundary.

        Args:
            first_day: Date string for the first day (e.g., '2025-03-15')
            second_day: Date string for the second day (e.g., '2025-03-16')
            interval_str: Interval string ('1s', '1m', '1h')

        Returns:
            None (prints information)
        """
        # Determine paths for the two days
        symbol = "BTCUSDT"
        if interval_str in ("1s", "1m", "1h"):
            first_file = (
                self.data_path
                / f"{symbol}/klines/{interval_str}/{symbol}-{interval_str}-{first_day}.csv"
            )
            second_file = (
                self.data_path
                / f"{symbol}/klines/{interval_str}/{symbol}-{interval_str}-{second_day}.csv"
            )
        else:
            raise ValueError(f"Unsupported interval: {interval_str}")

        # Read the files
        if not first_file.exists() or not second_file.exists():
            raise FileNotFoundError(
                f"Could not find files: {first_file} or {second_file}"
            )

        cols = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "count",
            "taker_buy_volume",
            "taker_buy_quote_volume",
            "ignore",
        ]

        # Read last few records from first day
        first_df = pd.read_csv(first_file, names=cols)
        first_df_tail = first_df.tail(3)
        first_df_tail["datetime"] = pd.to_datetime(
            first_df_tail["timestamp"] / 1000, unit="s", utc=True
        )

        # Read first few records from second day
        second_df = pd.read_csv(second_file, names=cols)
        second_df_head = second_df.head(3)
        second_df_head["datetime"] = pd.to_datetime(
            second_df_head["timestamp"] / 1000, unit="s", utc=True
        )

        # Calculate expected midnight timestamp
        midnight = datetime.strptime(
            f"{second_day} 00:00:00", "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=pytz.UTC)
        midnight_ts = int(midnight.timestamp() * 1000)  # Convert to milliseconds

        # Print the boundary data
        logger.info(
            f"Examining {interval_str} data boundary between {first_day} and {second_day}"
        )
        logger.info(f"Last 3 records from {first_day}:")
        for _, row in first_df_tail.iterrows():
            logger.info(f"  {row['datetime']} (ts: {row['timestamp']})")

        logger.info(f"First 3 records from {second_day}:")
        for _, row in second_df_head.iterrows():
            logger.info(f"  {row['datetime']} (ts: {row['timestamp']})")

        logger.info(f"Expected midnight timestamp: {midnight} (ts: {midnight_ts})")

        # Check if midnight timestamp exists in either file
        midnight_in_first = midnight_ts in first_df["timestamp"].values
        midnight_in_second = midnight_ts in second_df["timestamp"].values

        if midnight_in_first:
            logger.info(f"Midnight record EXISTS in {first_day} file")
        else:
            logger.info(f"Midnight record MISSING from {first_day} file")

        if midnight_in_second:
            logger.info(f"Midnight record EXISTS in {second_day} file")
        else:
            logger.info(f"Midnight record MISSING from {second_day} file")

        # Calculate time difference between last record of first day and first record of second day
        if not first_df_tail.empty and not second_df_head.empty:
            last_first_day = first_df_tail.iloc[-1]["datetime"]
            first_second_day = second_df_head.iloc[0]["datetime"]
            time_diff = (first_second_day - last_first_day).total_seconds()
            logger.info(
                f"Time difference between last record of {first_day} and first record of {second_day}: {time_diff} seconds"
            )

        return {
            "midnight_in_first_day": midnight_in_first,
            "midnight_in_second_day": midnight_in_second,
            "last_records_first_day": first_df_tail[["datetime", "timestamp"]].to_dict(
                "records"
            ),
            "first_records_second_day": second_df_head[
                ["datetime", "timestamp"]
            ].to_dict("records"),
        }


def main():
    """Main function to run the gap analysis."""
    logger.info("Starting gap analysis...")

    # Run iterative tests
    tests_passed = run_iterative_tests()
    logger.info(f"Iterative tests {'PASSED' if tests_passed else 'FAILED'}")

    # Initialize the analyzer
    data_path = Path("../data")
    if not data_path.exists():
        data_path = Path("data")  # Try alternative path

    analyzer = GapAnalyzer(data_path)

    # Test cases for day boundary analysis
    test_cases = [
        # 1-second data
        {"first_day": "2025-03-15", "second_day": "2025-03-16", "interval": "1s"},
        # 1-hour data
        {"first_day": "2025-03-20", "second_day": "2025-03-21", "interval": "1h"},
        # 1-minute data
        {"first_day": "2025-04-10", "second_day": "2025-04-11", "interval": "1m"},
    ]

    # Run day boundary analysis for each test case
    logger.info("Running day boundary gap analysis...")
    boundary_results = []
    for case in test_cases:
        try:
            logger.info(
                f"Analyzing {case['interval']} data between {case['first_day']} and {case['second_day']}"
            )

            # First examine the actual boundary data
            boundary_data = analyzer.examine_boundary_data(
                case["first_day"], case["second_day"], case["interval"]
            )

            # Then perform the gap analysis
            result = analyzer.analyze_day_boundary(
                case["first_day"], case["second_day"], case["interval"]
            )

            # Add boundary data information
            result["boundary_examination"] = boundary_data

            # Summarize the result
            gaps_count = len(result["gaps"])
            logger.info(
                f"Found {gaps_count} gaps at day boundary for {case['interval']} data"
            )

            if gaps_count > 0:
                for i, gap in enumerate(result["gaps"]):
                    from_time = gap["from"].strftime("%Y-%m-%d %H:%M:%S%z")
                    to_time = gap["to"].strftime("%Y-%m-%d %H:%M:%S%z")
                    logger.info(
                        f"  Gap {i+1}: From {from_time} to {to_time}, duration: {gap['duration_seconds']} seconds, missing points: {gap['missing_points']}"
                    )

            boundary_info = result["boundary_info"]
            logger.info(f"Boundary info:")
            logger.info(
                f"  Last record of {case['first_day']}: {boundary_info['last_record_first_day']}"
            )
            logger.info(
                f"  First record of {case['second_day']}: {boundary_info['first_record_second_day']}"
            )
            logger.info(f"  Expected midnight: {boundary_info['midnight']}")
            logger.info(
                f"  Midnight record missing: {boundary_info['midnight_missing']}"
            )
            logger.info(
                f"  Time difference: {boundary_info['time_diff_seconds']} seconds"
            )
            logger.info(
                f"  Expected interval: {boundary_info['expected_interval_seconds']} seconds"
            )

            boundary_results.append(result)

        except Exception as e:
            logger.error(
                f"Error analyzing {case['interval']} data between {case['first_day']} and {case['second_day']}: {e}"
            )

    # Run full file analysis for each test case
    logger.info("\nRunning full file gap analysis...")
    full_file_results = []
    for case in test_cases:
        try:
            # Analyze the second day file (which would contain first hour/minute/second of the day)
            logger.info(
                f"Analyzing full {case['interval']} data for {case['second_day']}"
            )
            result = analyzer.analyze_full_file(case["second_day"], case["interval"])

            # Summarize the result
            logger.info(
                f"Analysis for {case['interval']} data on {case['second_day']}:"
            )
            logger.info(f"  Total records: {result['total_records']}")
            logger.info(f"  Total gaps: {result['total_gaps']}")
            logger.info(f"  Day boundary gaps: {result['day_boundary_gaps']}")
            logger.info(f"  Non-boundary gaps: {result['non_boundary_gaps']}")
            logger.info(f"  Maximum gap duration: {result['max_gap_duration']} seconds")

            if result["gaps"]:
                for i, gap in enumerate(result["gaps"]):
                    from_time = gap["from"].strftime("%Y-%m-%d %H:%M:%S%z")
                    to_time = gap["to"].strftime("%Y-%m-%d %H:%M:%S%z")
                    boundary_str = (
                        "at day boundary"
                        if gap["is_day_boundary"]
                        else "not at boundary"
                    )
                    logger.info(
                        f"  Gap {i+1}: From {from_time} to {to_time}, {boundary_str}, duration: {gap['duration_seconds']} seconds"
                    )

            full_file_results.append(result)

        except Exception as e:
            logger.error(
                f"Error analyzing {case['interval']} data for {case['second_day']}: {e}"
            )

    # Compile summary statistics
    total_day_boundary_gaps = sum(len(result["gaps"]) for result in boundary_results)
    total_full_file_gaps = sum(result["total_gaps"] for result in full_file_results)
    total_non_boundary_gaps = sum(
        result["non_boundary_gaps"] for result in full_file_results
    )

    logger.info("\nSummary Statistics:")
    logger.info(f"Total day boundary gaps: {total_day_boundary_gaps}")
    logger.info(f"Total non-boundary gaps: {total_non_boundary_gaps}")
    logger.info(
        f"Total gaps across all analyses: {total_day_boundary_gaps + total_non_boundary_gaps}"
    )

    logger.info("\nConclusion:")
    if total_day_boundary_gaps > 0:
        logger.info(
            f"Found {total_day_boundary_gaps} gaps at day boundaries. The midnight (00:00:00) timestamp appears to be consistently missing in Binance Vision API data files."
        )
    else:
        logger.info("No day boundary gaps found.")

    if total_non_boundary_gaps > 0:
        logger.info(
            f"Found {total_non_boundary_gaps} gaps not related to day boundaries."
        )
    else:
        logger.info("No non-boundary gaps found.")

    logger.info("Gap analysis complete.")


if __name__ == "__main__":
    main()
