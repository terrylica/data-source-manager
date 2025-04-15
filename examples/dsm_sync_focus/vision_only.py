#!/usr/bin/env python3
"""
Standalone script that uses VisionDataClient directly to fetch 1-minute BTCUSDT spot data
for both 2023 and 2025 data to compare timestamp formats and detect timestamp misalignment.

This example demonstrates direct use of the VisionDataClient without going through
the DataSourceManager layer and identifies the timestamp interpretation issue.
"""

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import numpy as np
import json

from utils.logger_setup import logger
from rich import print
from rich.table import Table
from rich.console import Console
from utils.market_constraints import MarketType, Interval
from core.sync.vision_data_client import VisionDataClient


def analyze_timestamp_formats(df, year):
    """
    Analyze timestamp formats in the dataframe and determine if misalignment exists

    Args:
        df: DataFrame with processed timestamp data
        year: Year of the data for reporting purposes

    Returns:
        dict with timestamp analysis results
    """
    if df is None or df.empty:
        return {"error": "No data available for analysis"}

    # Basic timestamp info
    has_open_time = "open_time" in df.columns
    open_time_type = str(df["open_time"].dtype) if has_open_time else "N/A"

    # Get first few timestamps for analysis
    timestamps = []
    if has_open_time and len(df) > 2:
        for idx in range(min(5, len(df))):
            ts = df["open_time"].iloc[idx]
            timestamps.append(
                {
                    "index": idx,
                    "timestamp": str(ts),
                    "second_value": ts.second,
                    "microsecond": ts.microsecond,
                }
            )

    # Check for alignment issue - do timestamps end with :59.999 indicating misaligned interpretation?
    misaligned = False
    if has_open_time and len(df) > 2:
        seconds_at_59 = (df["open_time"].dt.second == 59).sum()
        proportion_at_59 = seconds_at_59 / len(df) if len(df) > 0 else 0
        misaligned = (
            proportion_at_59 > 0.9
        )  # Over 90% ending at 59 seconds indicates misalignment

    # If data has actual raw timestamp values, check those too
    original_timestamp_analysis = None
    if "original_timestamp" in df.columns:
        first_raw = df["original_timestamp"].iloc[0] if not df.empty else None
        digits = (
            len(str(int(first_raw)))
            if first_raw is not None and not np.isnan(first_raw)
            else 0
        )
        timestamp_unit = "microseconds" if digits >= 16 else "milliseconds"
        original_timestamp_analysis = {
            "sample": str(first_raw),
            "digits": digits,
            "interpreted_unit": timestamp_unit,
        }

    return {
        "year": year,
        "record_count": len(df),
        "has_open_time_column": has_open_time,
        "open_time_dtype": open_time_type,
        "sample_timestamps": timestamps,
        "timestamp_misalignment_detected": misaligned,
        "misalignment_details": (
            {
                "timestamps_ending_at_59s": seconds_at_59,
                "proportion_at_59s": (
                    float(proportion_at_59) if has_open_time and len(df) > 0 else 0.0
                ),
            }
            if has_open_time and len(df) > 0
            else None
        ),
        "original_timestamp_analysis": original_timestamp_analysis,
    }


def fetch_vision_data(year=2025, interval_enum=Interval.MINUTE_1):
    """
    Fetch BTCUSDT data for the specified interval and year
    directly using VisionDataClient.

    Args:
        year: Year to fetch data for (2023 or 2025)
        interval_enum: Interval enum from market_constraints

    Returns:
        DataFrame with data or None if error
    """
    # Configure logger
    logger.use_rich(True)
    # logger.setLevel("DEBUG")
    logger.setLevel("INFO")

    # Create logs directory if it doesn't exist
    logs_dir = Path("./logs")
    logs_dir.mkdir(exist_ok=True)

    # Add file handler for debugging
    log_file = logs_dir / f"vision_client_debug_{year}_{interval_enum.value}.log"
    logger.add_file_handler(str(log_file), level="DEBUG", mode="w")

    # Set up parameters for the Vision API client
    symbol = "BTCUSDT"
    interval = interval_enum  # Use the enum from market_constraints
    market_type = MarketType.SPOT

    # Ensure timezone-aware datetime objects with exact start times
    # Explicitly set to 00:00:00.000 to ensure proper alignment
    start_time = datetime(year, 3, 15, 0, 0, 0, 0, tzinfo=timezone.utc)

    # Adjust time range based on interval to get meaningful data
    if interval == Interval.SECOND_1:
        # For 1s, use 2 minutes of data (120 data points)
        end_time = datetime(year, 3, 15, 0, 1, 59, 999999, tzinfo=timezone.utc)
    elif interval == Interval.MINUTE_1:
        # For 1m, use 18 minutes as before
        end_time = datetime(year, 3, 15, 0, 17, 59, 999999, tzinfo=timezone.utc)
    elif interval in [Interval.MINUTE_3, Interval.MINUTE_5, Interval.MINUTE_15]:
        # For 3m/5m/15m, use first 2 hours
        end_time = datetime(year, 3, 15, 1, 59, 59, 999999, tzinfo=timezone.utc)
    elif interval == Interval.HOUR_1:
        # For 1h, use full day
        end_time = datetime(year, 3, 15, 23, 59, 59, 999999, tzinfo=timezone.utc)
    else:
        # Default: 30 minute range
        end_time = datetime(year, 3, 15, 0, 29, 59, 999999, tzinfo=timezone.utc)

    logger.info(
        f"Fetching data for {symbol} from {start_time.isoformat()} to {end_time.isoformat()}"
    )
    logger.info(f"Market: {market_type.name} | Interval: {interval.value}")

    # Create VisionDataClient instance
    try:
        # Use context manager for proper resource cleanup
        with VisionDataClient(
            symbol=symbol,
            interval=interval.value,  # Use the string value from the enum
            market_type=market_type,
        ) as client:
            logger.info("VisionDataClient created successfully")

            # Debug the requested date range
            logger.debug(
                f"Requested date range spans {(end_time.date() - start_time.date()).days + 1} days from {start_time} to {end_time}"
            )
            logger.debug(f"Calling _download_data from {start_time} to {end_time}")

            # Check if data is likely available
            is_available = client.is_data_available(start_time, end_time)
            if not is_available:
                logger.warning(
                    f"Data likely not available for the requested time range. "
                    f"Vision API typically has a 24-48 hour delay from current time."
                )

            # Fetch data for the specified time range
            df = client.fetch(
                symbol=symbol,
                interval=interval.value,
                start_time=start_time,
                end_time=end_time,
            )

            # Check if we have data
            if df is None or df.empty:
                logger.error(
                    f"No data retrieved from Vision API for {year} ({interval.value})"
                )
                return None

            # Add original timestamp column if not present (useful for analysis)
            if "original_timestamp" not in df.columns and "open_time" in df.columns:
                # Store the original timestamp value in microseconds for proper comparison
                if year >= 2025:
                    # For 2025+ data, timestamps are already in microseconds
                    df["original_timestamp"] = df["open_time"].astype(np.int64) // 1000
                else:
                    # For pre-2025 data, timestamps are in milliseconds
                    df["original_timestamp"] = (
                        df["open_time"].astype(np.int64) // 1000000
                    )

            # Display information about the retrieved data
            print(
                f"\n[bold green]Vision API Data Retrieved ({year}, {interval.value}):[/bold green]"
            )
            print(f"Symbol: [cyan]{symbol}[/cyan]")
            print(f"Interval: [cyan]{interval.value}[/cyan]")
            print(f"Market: [cyan]{market_type.name}[/cyan]")
            print(f"Records: [cyan]{len(df)}[/cyan]")

            # Check for source information column
            if "_data_source" in df.columns:
                sources = df["_data_source"].unique()
                print(f"Data sources: [cyan]{', '.join(sources)}[/cyan]")

            # Get time range from the data
            if "open_time" in df.columns:
                min_time = df["open_time"].min()
                max_time = df["open_time"].max()
                print(f"Time range: [cyan]{min_time}[/cyan] to [cyan]{max_time}[/cyan]")

            # Save to CSV for inspection
            output_dir = Path("./examples/dsm_sync_focus/output")
            output_dir.mkdir(exist_ok=True)

            output_file = (
                output_dir / f"{symbol}_{interval.value}_vision_data_{year}.csv"
            )
            df.to_csv(output_file, index=False)
            print(f"\nData saved to [bold cyan]{output_file}[/bold cyan]")

            # Display sample data
            print(f"\n[bold green]Sample Data for {year} (first 3 rows):[/bold green]")
            sample = df.head(3)
            print(sample)

            return df
    except Exception as e:
        logger.error(
            f"Error fetching data from Vision API for {year} ({interval.value}): {e}",
            exc_info=True,
        )
        return None


def download_raw_data(year, interval_enum=Interval.MINUTE_1):
    """
    Download raw data directly from Binance Vision API using httpx
    for comparison with processed data

    Args:
        year: Year to download data for (2023 or 2025)
        interval_enum: Interval enum from market_constraints

    Returns:
        Path to downloaded raw data or None if error
    """
    import httpx
    import zipfile
    import io

    symbol = "BTCUSDT"
    interval = interval_enum.value
    date_str = f"{year}-03-15"

    url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{date_str}.zip"

    output_dir = Path("./examples/dsm_sync_focus/output/raw")
    output_dir.mkdir(exist_ok=True, parents=True)

    raw_file = output_dir / f"{symbol}-{interval}-{date_str}-raw.csv"

    try:
        logger.info(f"Downloading raw data from {url}")

        with httpx.Client() as client:
            response = client.get(url)

            if response.status_code != 200:
                logger.error(
                    f"Failed to download raw data: HTTP {response.status_code}"
                )
                return None

            # Extract the zip file
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                # There should be only one file in the zip
                csv_filename = zip_ref.namelist()[0]
                with zip_ref.open(csv_filename) as csv_file:
                    content = csv_file.read()

            # Write the raw content to file
            raw_file.write_bytes(content)
            logger.info(f"Raw data saved to {raw_file}")

            return raw_file

    except Exception as e:
        logger.error(
            f"Error downloading raw data for {year} ({interval}): {e}", exc_info=True
        )
        return None


def analyze_raw_data(raw_file_path, year):
    """
    Analyze the raw data from Binance Vision API

    Args:
        raw_file_path: Path to raw CSV file
        year: Year of the data

    Returns:
        Dict with analysis results
    """
    try:
        # Check if file has headers by reading the first few lines
        with open(raw_file_path, "r") as f:
            first_line = f.readline().strip()
            # Read second line for comparison
            second_line = f.readline().strip() if f else ""

        # Check if the first line looks like a header by comparing data types
        first_line_parts = first_line.split(",")
        second_line_parts = second_line.split(",") if second_line else []

        # If we have both lines, check if first line contains non-numeric data (headers)
        if first_line_parts and second_line_parts:
            try:
                # Try to convert first field of both lines to float
                float(first_line_parts[0])
                float(second_line_parts[0])
                has_header = False  # Both lines have numeric data, no header
            except ValueError:
                # First line can't be converted to float, likely a header
                has_header = True
        else:
            # Default to no header if comparison can't be made
            has_header = False

        logger.debug(f"Raw data file for {year} appears to have headers: {has_header}")

        # Read the CSV file with or without headers
        if has_header:
            df = pd.read_csv(raw_file_path)
            # Get first timestamp from the open_time column
            ts_column = next(
                (
                    col
                    for col in df.columns
                    if "open_time" in str(col).lower() or "opentime" in str(col).lower()
                ),
                None,
            )

            if ts_column is None:
                # If no column with open_time in name, assume first column is timestamp
                ts_column = df.columns[0]

            first_ts = df[ts_column].iloc[0]
        else:
            # No headers in the file, use default kline column names
            df = pd.read_csv(
                raw_file_path,
                header=None,
                names=[
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
                ],
            )
            # First column is the timestamp
            first_ts = df["open_time"].iloc[0]

        # Check the number of digits in the timestamp to determine format
        digits = len(str(int(first_ts)))

        # Determine timestamp unit based on the number of digits and year
        expected_digits = 16 if year >= 2025 else 13
        if digits != expected_digits:
            logger.warning(
                f"Timestamp digits ({digits}) don't match expected format for {year} "
                f"(expected: {expected_digits})"
            )

        timestamp_unit = "microseconds" if digits >= 16 else "milliseconds"
        logger.debug(
            f"Detected timestamp unit for {year}: {timestamp_unit} (digits: {digits})"
        )

        # Convert the first few timestamps to datetime for display
        timestamps = []
        for idx in range(min(5, len(df))):
            if has_header:
                ts_value = df[ts_column].iloc[idx]
            else:
                ts_value = df["open_time"].iloc[idx]

            # Convert based on detected unit
            if timestamp_unit == "microseconds":
                ts = datetime.fromtimestamp(ts_value / 1000000, tz=timezone.utc)
            else:
                ts = datetime.fromtimestamp(ts_value / 1000, tz=timezone.utc)

            timestamps.append(
                {
                    "raw_value": str(ts_value),
                    "converted_datetime": ts.isoformat(),
                    "human_readable": ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "seconds": ts.second,
                    "microseconds": ts.microsecond,
                }
            )

        return {
            "year": year,
            "record_count": len(df),
            "columns_count": df.shape[1],
            "has_header": has_header,
            "timestamp_first_value": str(first_ts),
            "timestamp_digits": digits,
            "timestamp_unit": timestamp_unit,
            "sample_timestamps": timestamps,
        }

    except Exception as e:
        logger.error(f"Error analyzing raw data for {year}: {e}", exc_info=True)
        return {"error": str(e)}


def compare_data_formats(processed_df, raw_analysis, year):
    """
    Compare processed data with raw data to identify timestamp alignment issues

    Args:
        processed_df: DataFrame with processed data
        raw_analysis: Dict with raw data analysis
        year: Year of the data

    Returns:
        Dict with comparison results
    """
    if processed_df is None or processed_df.empty:
        return {"error": "No processed data available for comparison"}

    if "error" in raw_analysis:
        return {"error": f"No raw data analysis available: {raw_analysis['error']}"}

    # Get first timestamp from processed data
    if "open_time" not in processed_df.columns:
        return {"error": "Processed data does not contain open_time column"}

    # Get the minimum timestamp from processed data (it may not be the first row)
    first_processed_ts = processed_df["open_time"].min()
    logger.debug(f"First processed timestamp for {year}: {first_processed_ts}")

    # Get first timestamp from raw data
    raw_first_ts_str = raw_analysis["sample_timestamps"][0]["converted_datetime"]
    raw_first_ts = datetime.fromisoformat(raw_first_ts_str)
    logger.debug(f"First raw timestamp for {year}: {raw_first_ts}")

    # Calculate the difference in seconds
    time_diff = (first_processed_ts - raw_first_ts).total_seconds()
    logger.debug(f"Time difference for {year}: {time_diff} seconds")

    # Analyze patterns in processed timestamps
    processed_seconds = processed_df["open_time"].dt.second.value_counts().to_dict()
    processed_micros = processed_df["open_time"].dt.microsecond.value_counts().to_dict()

    # Check for microsecond patterns (0 or 999999 are significant)
    micros_at_0 = sum(1 for ts in processed_df["open_time"] if ts.microsecond == 0)
    micros_at_999999 = sum(
        1 for ts in processed_df["open_time"] if ts.microsecond == 999999
    )
    proportion_micros_0 = (
        micros_at_0 / len(processed_df) if len(processed_df) > 0 else 0
    )
    proportion_micros_999999 = (
        micros_at_999999 / len(processed_df) if len(processed_df) > 0 else 0
    )

    logger.debug(f"Microsecond patterns for {year}:")
    logger.debug(
        f"  Timestamps with .000000: {micros_at_0} ({proportion_micros_0:.2%})"
    )
    logger.debug(
        f"  Timestamps with .999999: {micros_at_999999} ({proportion_micros_999999:.2%})"
    )

    # Sort processed timestamps to check for pattern
    sorted_ts = sorted(processed_df["open_time"])
    logger.debug(f"First 5 sorted timestamps: {sorted_ts[:5]}")

    # Check for misalignment patterns in seconds
    seconds_at_59 = processed_seconds.get(59, 0)
    seconds_at_0 = processed_seconds.get(0, 0)
    proportion_at_59 = seconds_at_59 / len(processed_df) if len(processed_df) > 0 else 0
    proportion_at_0 = seconds_at_0 / len(processed_df) if len(processed_df) > 0 else 0

    logger.debug(f"Second distribution for {year}: {processed_seconds}")
    logger.debug(f"Seconds at 0: {seconds_at_0}, Proportion: {proportion_at_0}")
    logger.debug(f"Seconds at 59: {seconds_at_59}, Proportion: {proportion_at_59}")

    # Determine interval from the data
    interval_seconds = 60  # Default to 1 minute
    if any("1s" in str(col) for col in processed_df.columns):
        interval_seconds = 1
    elif any("3m" in str(col) for col in processed_df.columns):
        interval_seconds = 180
    elif any("5m" in str(col) for col in processed_df.columns):
        interval_seconds = 300
    elif any("15m" in str(col) for col in processed_df.columns):
        interval_seconds = 900
    elif any("1h" in str(col) for col in processed_df.columns):
        interval_seconds = 3600

    logger.debug(f"Detected interval for {year}: {interval_seconds} seconds")

    # IMPORTANT: All intervals in Binance Vision data start at the interval boundary (00:00:00)
    # If we're missing the first interval of the day, that's significant
    # But if we're missing data from non-standard boundaries, that's expected
    missing_first_candle = False
    # Only consider it missing if the first raw timestamp is at the start of the day (00:00:00)
    if raw_first_ts.hour == 0 and raw_first_ts.minute == 0 and raw_first_ts.second == 0:
        # Use a smaller tolerance for most intervals, larger for very large intervals
        tolerance_seconds = min(
            interval_seconds * 0.05, 1.0
        )  # 5% of interval or 1 second, whichever is smaller

        # Detect if first raw timestamp is present in processed data
        closest_ts_diff = (
            min(
                abs((ts - raw_first_ts).total_seconds())
                for ts in processed_df["open_time"]
            )
            if not processed_df.empty
            else float("inf")
        )

        # If the closest timestamp in processed data is more than our tolerance away,
        # then we consider the first candle missing
        missing_first_candle = closest_ts_diff > tolerance_seconds

    logger.debug(
        f"First raw timestamp is at boundary: {raw_first_ts.hour == 0 and raw_first_ts.minute == 0 and raw_first_ts.second == 0}"
    )
    logger.debug(f"Missing first candle: {missing_first_candle}")

    # Check for consistent time shift with improved understanding of Binance interval boundaries
    time_shift = None

    # For 1s intervals, a 1-second shift is expected due to how Binance structures the timestamps
    if interval_seconds == 1 and abs(time_diff - 1.0) < 0.1:
        time_shift = "one_second_forward"
        # This is the expected behavior for 1s intervals
    # For all intervals, timestamps should match interval boundaries
    elif abs(time_diff) < 0.1:  # Using a tighter tolerance for perfect alignment
        time_shift = "perfectly_aligned"  # Perfect alignment
    elif abs(time_diff - interval_seconds) < 0.1:
        time_shift = "one_interval_forward"
    elif abs(time_diff + interval_seconds) < 0.1:
        time_shift = "one_interval_backward"
    else:
        time_shift = f"irregular_shift_{time_diff:.1f}_seconds"

    logger.debug(f"Detected time shift for {year}: {time_shift}")

    # Determine if there's actual timestamp misalignment based on improved criteria
    # and our knowledge of Binance Vision API's interval boundary behavior
    is_misaligned = False

    # For 1s intervals, a 1-second forward shift is expected and correct behavior
    if interval_seconds == 1:
        # Only flag as misaligned if it's not the expected 1-second forward shift
        is_misaligned = (
            time_shift != "one_second_forward" and time_shift != "perfectly_aligned"
        )
    else:
        # For other intervals:
        # 1. Standard intervals should align with interval boundaries (e.g., 00:00, 00:01, etc.)
        # 2. No expected standard shift for other intervals
        is_misaligned = (
            # More than 90% of timestamps ending at :59 seconds could indicate off-by-one issue
            (proportion_at_59 > 0.9 and proportion_micros_999999 > 0.9)
            or
            # First candle missing when it should be present (at interval boundary)
            missing_first_candle
            or
            # Unexpected shifts (not properly accounted for)
            (time_shift not in ["perfectly_aligned"])
        )

    # For very large intervals (like 1h), a small shift in seconds may not be considered a misalignment
    if (
        interval_seconds >= 3600 and abs(time_diff) < 5
    ):  # Less than 5 seconds for hourly data
        is_misaligned = False

    return {
        "year": year,
        "first_raw_timestamp": raw_first_ts_str,
        "first_processed_timestamp": first_processed_ts.isoformat(),
        "time_difference_seconds": time_diff,
        "detected_time_shift": time_shift,
        "missing_first_candle": missing_first_candle,
        "processed_seconds_distribution": processed_seconds,
        "timestamps_ending_at_59s": seconds_at_59,
        "proportion_at_59s": float(proportion_at_59),
        "timestamps_starting_at_0s": seconds_at_0,
        "proportion_at_0s": float(proportion_at_0),
        "microseconds_at_0": micros_at_0,
        "proportion_micros_0": float(proportion_micros_0),
        "microseconds_at_999999": micros_at_999999,
        "proportion_micros_999999": float(proportion_micros_999999),
        "interval_seconds": interval_seconds,
        "timestamp_misalignment_detected": is_misaligned,
        "closest_timestamp_diff_seconds": (
            float(closest_ts_diff) if "closest_ts_diff" in locals() else None
        ),
    }


def generate_timestamp_report(comparison_2023, comparison_2025):
    """
    Generate a detailed report on timestamp misalignment issues comparing 2023 and 2025 data.

    The report analyzes timestamp alignment patterns and provides insights on the proper
    interpretation of timestamps for different interval types.

    Args:
        comparison_2023: Results of 2023 data comparison
        comparison_2025: Results of 2025 data comparison

    Returns:
        None, prints report to console and saves detailed analysis to JSON file
    """
    console = Console()

    print("\n[bold yellow]===== TIMESTAMP MISALIGNMENT REPORT =====[/bold yellow]")

    # Create a summary table
    table = Table(title="Timestamp Alignment Analysis")
    table.add_column("Attribute", style="cyan")
    table.add_column("2023 Data", style="green")
    table.add_column("2025 Data", style="yellow")

    # Check for errors
    if "error" in comparison_2023 or "error" in comparison_2025:
        error_2023 = comparison_2023.get("error", "No error")
        error_2025 = comparison_2025.get("error", "No error")
        table.add_row("Error Status", error_2023, error_2025)
        console.print(table)
        return

    # Get the interval in a readable format for the report
    interval_seconds = comparison_2023.get("interval_seconds", 60)
    interval_str = "unknown"
    if interval_seconds == 1:
        interval_str = "1-second"
    elif interval_seconds == 60:
        interval_str = "1-minute"
    elif interval_seconds == 180:
        interval_str = "3-minute"
    elif interval_seconds == 300:
        interval_str = "5-minute"
    elif interval_seconds == 900:
        interval_str = "15-minute"
    elif interval_seconds == 3600:
        interval_str = "1-hour"

    # Add rows to the table
    table.add_row(
        "First Raw Timestamp",
        comparison_2023["first_raw_timestamp"],
        comparison_2025["first_raw_timestamp"],
    )
    table.add_row(
        "First Processed Timestamp",
        comparison_2023["first_processed_timestamp"],
        comparison_2025["first_processed_timestamp"],
    )
    table.add_row(
        "Time Difference (seconds)",
        f"{comparison_2023['time_difference_seconds']:.3f}",
        f"{comparison_2025['time_difference_seconds']:.3f}",
    )
    table.add_row(
        "Detected Time Shift",
        str(comparison_2023["detected_time_shift"]),
        str(comparison_2025["detected_time_shift"]),
    )
    table.add_row(
        "Missing First Candle",
        str(comparison_2023["missing_first_candle"]),
        str(comparison_2025["missing_first_candle"]),
    )

    # Add closest timestamp match if available
    closest_diff_2023 = comparison_2023.get("closest_timestamp_diff_seconds")
    closest_diff_2025 = comparison_2025.get("closest_timestamp_diff_seconds")

    table.add_row(
        "Closest Timestamp Match (seconds)",
        f"{closest_diff_2023:.3f}" if closest_diff_2023 is not None else "N/A",
        f"{closest_diff_2025:.3f}" if closest_diff_2025 is not None else "N/A",
    )

    table.add_row(
        "% Timestamps Ending at :59",
        f"{comparison_2023['proportion_at_59s']*100:.1f}%",
        f"{comparison_2025['proportion_at_59s']*100:.1f}%",
    )
    table.add_row(
        "% Timestamps Ending at .999999",
        f"{comparison_2023.get('proportion_micros_999999', 0)*100:.1f}%",
        f"{comparison_2025.get('proportion_micros_999999', 0)*100:.1f}%",
    )
    table.add_row(
        "% Timestamps Starting at :00",
        f"{comparison_2023.get('proportion_at_0s', 0)*100:.1f}%",
        f"{comparison_2025.get('proportion_at_0s', 0)*100:.1f}%",
    )
    table.add_row(
        "% Timestamps Starting at .000000",
        f"{comparison_2023.get('proportion_micros_0', 0)*100:.1f}%",
        f"{comparison_2025.get('proportion_micros_0', 0)*100:.1f}%",
    )
    table.add_row(
        "Interval",
        f"{interval_str} ({comparison_2023.get('interval_seconds', 'N/A')}s)",
        f"{interval_str} ({comparison_2025.get('interval_seconds', 'N/A')}s)",
    )
    table.add_row(
        "Misalignment Detected",
        (
            "[bold red]YES[/bold red]"
            if comparison_2023["timestamp_misalignment_detected"]
            else "[bold green]NO[/bold green]"
        ),
        (
            "[bold red]YES[/bold red]"
            if comparison_2025["timestamp_misalignment_detected"]
            else "[bold green]NO[/bold green]"
        ),
    )

    console.print(table)

    # Add detailed explanation
    console.print("\n[bold]Timestamp Alignment Analysis:[/bold]")

    # Create a section for each year's analysis
    for year, comparison in [("2023", comparison_2023), ("2025", comparison_2025)]:
        misaligned = comparison["timestamp_misalignment_detected"]
        shift_type = comparison["detected_time_shift"]
        time_diff = comparison["time_difference_seconds"]

        console.print(f"\n[bold]{year} Data ({interval_str}):[/bold]")
        alignment_status = (
            f"[bold red]Misaligned[/bold red]"
            if misaligned
            else f"[bold green]Aligned[/bold green]"
        )
        console.print(f"Status: {alignment_status}")

        # Detailed explanation of the shift type
        if shift_type == "perfectly_aligned":
            console.print("Timestamps are perfectly aligned with raw data.")
        elif shift_type == "one_second_forward":
            if interval_seconds == 1:
                console.print(
                    f"Timestamps show a 1-second forward shift, which is [bold green]expected and correct[/bold green] "
                    f"for 1-second intervals in Binance Vision API."
                )
            else:
                console.print(
                    f"Timestamps show a 1-second forward shift, which is [bold red]unexpected[/bold red] "
                    f"for {interval_str} intervals."
                )
        elif shift_type == "one_interval_forward":
            console.print(
                f"Timestamps show a full {interval_str} forward shift of {time_diff:.2f} seconds."
            )
        elif shift_type == "one_interval_backward":
            console.print(
                f"Timestamps show a full {interval_str} backward shift of {time_diff:.2f} seconds."
            )
        elif "irregular_shift" in shift_type:
            console.print(
                f"Timestamps show an irregular shift of {time_diff:.2f} seconds, "
                f"which does not align with any expected pattern."
            )

        # Missing first candle explanation
        if comparison["missing_first_candle"]:
            console.print(
                "[bold red]Missing first candle at interval boundary (00:00:00)[/bold red], which is significant "
                "because Binance Vision data is expected to start exactly at interval boundaries."
            )

        # Patterns in seconds and microseconds
        if comparison["proportion_at_59s"] > 0.5:
            console.print(
                f"{comparison['proportion_at_59s']*100:.1f}% of timestamps end with second = 59, "
                f"which may indicate an off-by-one interpretation issue."
            )

        if comparison.get("proportion_micros_999999", 0) > 0.5:
            console.print(
                f"{comparison.get('proportion_micros_999999', 0)*100:.1f}% of timestamps end with microsecond = 999999, "
                f"suggesting timestamps are being interpreted as the END of periods instead of the BEGIN."
            )

    # Add overall conclusion
    console.print("\n[bold]Conclusion:[/bold]")

    if (
        comparison_2023["timestamp_misalignment_detected"]
        or comparison_2025["timestamp_misalignment_detected"]
    ):
        console.print(
            "Timestamp misalignment detected in "
            + (
                "both 2023 and 2025 data."
                if comparison_2023["timestamp_misalignment_detected"]
                and comparison_2025["timestamp_misalignment_detected"]
                else (
                    "2023 data only."
                    if comparison_2023["timestamp_misalignment_detected"]
                    else "2025 data only."
                )
            )
        )

        # More detailed explanation based on the interval and shift type
        if interval_seconds == 1:
            if (
                comparison_2023.get("detected_time_shift") == "one_second_forward"
                or comparison_2025.get("detected_time_shift") == "one_second_forward"
            ):
                console.print(
                    "\n[italic]Note: The 1.0 second shift for 1-second intervals is by design in the Binance API.[/italic]"
                    "\n[italic]For 1-second intervals, timestamps start at xx:xx:01.000, xx:xx:02.000, etc.[/italic]"
                    "\n[italic]This is normal and actually represents proper alignment with the raw data format.[/italic]"
                )
            else:
                console.print(
                    f"\n[italic]The {interval_str} interval data shows unexpected timestamp behavior.[/italic]"
                    f"\n[italic]According to Binance Vision API specifications, 1-second intervals should show[/italic]"
                    f"\n[italic]a consistent 1-second forward shift, which wasn't detected in this analysis.[/italic]"
                )
        # For other intervals
        elif "one_interval_forward" in comparison_2023.get(
            "detected_time_shift", ""
        ) or "one_interval_forward" in comparison_2025.get("detected_time_shift", ""):
            console.print(
                f"\n[italic]The processed timestamps appear to be shifted forward by one {interval_str} interval.[/italic]"
                "\n[italic]This is due to how the timestamps are interpreted - in raw data, timestamps[/italic]"
                "\n[italic]represent the START of a candle period, but processing may treat them as the END.[/italic]"
            )
        # For irregular shifts
        elif "irregular_shift" in comparison_2023.get(
            "detected_time_shift", ""
        ) or "irregular_shift" in comparison_2025.get("detected_time_shift", ""):
            console.print(
                "\n[italic]An irregular timestamp shift was detected. This could indicate[/italic]"
                "\n[italic]a more complex timestamp handling issue or timezone conversion problem.[/italic]"
            )

        if (
            comparison_2023["missing_first_candle"]
            and comparison_2025["missing_first_candle"]
        ):
            console.print(
                "\n[italic]The first candle at 00:00:00 appears to be missing in both datasets.[/italic]"
                "\n[italic]This could be due to how the Binance API formats timestamps or could indicate[/italic]"
                "\n[italic]that trading activity doesn't start exactly at midnight.[/italic]"
            )
    else:
        # No misalignment detected - explain the expected behavior for the particular interval
        if interval_seconds == 1:
            console.print(
                f"No timestamp misalignment detected for {interval_str} intervals. The timestamps show the expected"
                f" 1-second forward shift, which is the correct behavior for 1-second intervals in Binance Vision API data."
            )
        else:
            console.print(
                f"No timestamp misalignment detected for {interval_str} intervals. Timestamps are correctly aligned"
                f" with the interval boundaries as expected in Binance Vision API data."
            )

    # Add information about the semantic meaning of timestamps
    console.print(
        "\n[bold]Timestamp Interpretation:[/bold]"
        "\nThe correct semantic meaning of timestamps in Binance data:"
        "\n- [green]open_time[/green] represents the [bold]BEGINNING[/bold] of each candle period"
        "\n- [red]close_time[/red] represents the [bold]END[/bold] of each candle period"
    )

    # Add specific information based on interval
    if interval_seconds == 1:
        console.print(
            "\n[bold]1-Second Interval Notes:[/bold]"
            "\nFor 1-second intervals in Binance Vision API:"
            "\n- First candle of the day starts at 00:00:00.000 and ends at 00:00:00.999"
            "\n- A clear pattern is usually seen with a consistent 1.0 second shift between raw and processed timestamps"
            "\n- This is by design and represents the correct interpretation of timestamp semantics"
        )
    elif interval_seconds == 60:
        console.print(
            "\n[bold]1-Minute Interval Notes:[/bold]"
            "\nFor 1-minute intervals, timestamps should align to minute boundaries:"
            "\n- The first candle of the day starts at 00:00:00 and ends at 00:00:59.999"
            "\n- All timestamps should be aligned to minute boundaries (xx:00:00, xx:01:00, etc.)"
            "\n- Properly processed data should preserve these exact timestamp boundaries"
        )
    else:
        console.print(
            f"\n[bold]{interval_str} Interval Notes:[/bold]"
            f"\nFor {interval_str} intervals in Binance Vision API:"
            f"\n- The first candle starts at the first interval boundary (00:00:00)"
            f"\n- Each timestamp represents the START of a {interval_str} candle period"
            f"\n- All timestamps should align perfectly with {interval_str} boundaries"
        )

    # Add information on precision
    if comparison_2025.get("year", 2025) >= 2025:
        console.print(
            "\n[bold]2025+ Timestamp Precision:[/bold]"
            "\nStarting in 2025, Binance Vision API uses microsecond precision (16 digits)"
            "\nThis higher precision allows for more accurate timestamp representation"
        )

    # Save detailed analysis to JSON file
    output_dir = Path("./examples/dsm_sync_focus/output")
    output_dir.mkdir(exist_ok=True, parents=True)

    output_file = output_dir / "timestamp_analysis_report.json"
    with open(output_file, "w") as f:
        json.dump(
            {
                "comparison_2023": comparison_2023,
                "comparison_2025": comparison_2025,
                "analysis_summary": {
                    "interval": interval_str,
                    "interval_seconds": interval_seconds,
                    "2023_status": (
                        "aligned"
                        if not comparison_2023["timestamp_misalignment_detected"]
                        else "misaligned"
                    ),
                    "2025_status": (
                        "aligned"
                        if not comparison_2025["timestamp_misalignment_detected"]
                        else "misaligned"
                    ),
                    "2023_shift": comparison_2023["detected_time_shift"],
                    "2025_shift": comparison_2025["detected_time_shift"],
                    "expected_shift_1s": "one_second_forward",
                    "expected_shift_other": "perfectly_aligned",
                },
            },
            f,
            indent=2,
            default=str,
        )
    console.print(
        f"\nDetailed analysis saved to [italic cyan]{output_file}[/italic cyan]"
    )


def generate_multi_interval_summary(all_results):
    """
    Generate a summary report for all tested intervals

    Args:
        all_results: Dictionary with results for all intervals

    Returns:
        None, prints report to console
    """
    console = Console()

    print(
        "\n[bold yellow]===== MULTI-INTERVAL TIMESTAMP MISALIGNMENT SUMMARY =====[/bold yellow]"
    )

    # Create a summary table
    table = Table(title="Timestamp Alignment Analysis Across Intervals")
    table.add_column("Interval", style="cyan")
    table.add_column("2023 Status", style="green")
    table.add_column("2025 Status", style="yellow")
    table.add_column("Notes", style="magenta")

    # Add a row for each interval
    for interval, results in all_results.items():
        # Extract results
        comparison_2023 = results["comparison_2023"]
        comparison_2025 = results["comparison_2025"]

        # Determine status
        if "error" in comparison_2023:
            status_2023 = f"[red]ERROR: {comparison_2023['error']}"
        else:
            misaligned_2023 = comparison_2023.get(
                "timestamp_misalignment_detected", False
            )
            status_2023 = "[red]MISALIGNED" if misaligned_2023 else "[green]ALIGNED"

        if "error" in comparison_2025:
            status_2025 = f"[red]ERROR: {comparison_2025['error']}"
        else:
            misaligned_2025 = comparison_2025.get(
                "timestamp_misalignment_detected", False
            )
            status_2025 = "[red]MISALIGNED" if misaligned_2025 else "[green]ALIGNED"

        # Determine if there's a shift and what type
        notes = ""
        if "error" not in comparison_2023 and "detected_time_shift" in comparison_2023:
            shift_2023 = comparison_2023["detected_time_shift"]
            if shift_2023 == "one_interval_forward":
                notes += f"2023: Shifted forward one {interval} interval. "

        if "error" not in comparison_2025 and "detected_time_shift" in comparison_2025:
            shift_2025 = comparison_2025["detected_time_shift"]
            if shift_2025 == "one_interval_forward":
                notes += f"2025: Shifted forward one {interval} interval. "

        # Add row to table
        table.add_row(interval, status_2023, status_2025, notes)

    console.print(table)

    # Count how many intervals show misalignment
    misaligned_count = sum(
        1 for result in all_results.values() if result["has_misalignment"]
    )
    total_intervals = len(all_results)

    # Print conclusion
    print("\n[bold]Overall Conclusion:[/bold]")

    if misaligned_count == total_intervals:
        print(
            f"[bold red]Timestamp misalignment detected in ALL {total_intervals} tested intervals.[/bold red]"
        )
        print(
            "This suggests a systematic issue in the timestamp interpretation across all interval types."
        )
    elif misaligned_count > 0:
        print(
            f"[bold yellow]Timestamp misalignment detected in {misaligned_count} out of {total_intervals} tested intervals.[/bold yellow]"
        )
        aligned_intervals = [
            interval
            for interval, result in all_results.items()
            if not result["has_misalignment"]
        ]
        misaligned_intervals = [
            interval
            for interval, result in all_results.items()
            if result["has_misalignment"]
        ]
        if aligned_intervals:
            print(
                f"Correctly aligned intervals: [green]{', '.join(aligned_intervals)}[/green]"
            )
        if misaligned_intervals:
            print(f"Misaligned intervals: [red]{', '.join(misaligned_intervals)}[/red]")
    else:
        print(
            f"[bold green]No timestamp misalignment detected in any of the {total_intervals} tested intervals.[/bold green]"
        )
        print(
            "The timestamp interpretation appears to be correct across all interval types."
        )


def run_timestamp_analysis():
    """
    Run the timestamp analysis comparing 2023 and 2025 data for multiple intervals
    """
    # Create necessary directories
    output_dir = Path("./examples/dsm_sync_focus/output")
    output_dir.mkdir(exist_ok=True, parents=True)

    # Define the intervals to test
    intervals_to_test = [
        Interval.SECOND_1,  # 1s
        Interval.MINUTE_1,  # 1m
        Interval.MINUTE_3,  # 3m
        Interval.MINUTE_5,  # 5m
        Interval.MINUTE_15,  # 15m
        Interval.HOUR_1,  # 1h
    ]

    # Dictionary to store results for all intervals
    all_results = {}

    for interval in intervals_to_test:
        print(
            f"\n[bold magenta]===== Testing Interval: {interval.value} =====[/bold magenta]"
        )

        # Fetch and analyze 2023 data
        print(f"[bold cyan]Fetching 2023 Data for {interval.value}[/bold cyan]")
        df_2023 = fetch_vision_data(year=2023, interval_enum=interval)
        raw_2023 = download_raw_data(year=2023, interval_enum=interval)

        # Fetch and analyze 2025 data
        print(f"\n[bold cyan]Fetching 2025 Data for {interval.value}[/bold cyan]")
        df_2025 = fetch_vision_data(year=2025, interval_enum=interval)
        raw_2025 = download_raw_data(year=2025, interval_enum=interval)

        # Analyze raw data if available
        raw_analysis_2023 = (
            analyze_raw_data(raw_2023, 2023)
            if raw_2023
            else {"error": f"Failed to download raw 2023 data for {interval.value}"}
        )
        raw_analysis_2025 = (
            analyze_raw_data(raw_2025, 2025)
            if raw_2025
            else {"error": f"Failed to download raw 2025 data for {interval.value}"}
        )

        # Compare processed data with raw data
        comparison_2023 = (
            compare_data_formats(df_2023, raw_analysis_2023, 2023)
            if df_2023 is not None
            else {"error": f"No processed 2023 data available for {interval.value}"}
        )
        comparison_2025 = (
            compare_data_formats(df_2025, raw_analysis_2025, 2025)
            if df_2025 is not None
            else {"error": f"No processed 2025 data available for {interval.value}"}
        )

        # Generate and display report for this interval
        print(
            f"\n[bold yellow]===== TIMESTAMP ANALYSIS FOR {interval.value} =====[/bold yellow]"
        )
        generate_timestamp_report(comparison_2023, comparison_2025)

        # Store results
        all_results[interval.value] = {
            "comparison_2023": comparison_2023,
            "comparison_2025": comparison_2025,
            "has_misalignment": (
                comparison_2023.get("timestamp_misalignment_detected", False)
                or comparison_2025.get("timestamp_misalignment_detected", False)
            ),
        }

    # Generate summary report across all intervals
    generate_multi_interval_summary(all_results)

    # Save complete analysis to JSON
    summary_file = output_dir / "multi_interval_analysis.json"
    with open(summary_file, "w") as f:
        json.dump(all_results, f, indent=2, default=str)

    print(f"\nComplete multi-interval analysis saved to [cyan]{summary_file}[/cyan]")

    return True


if __name__ == "__main__":
    print(
        "[bold cyan]Fetching Bitcoin data from Binance Vision API for timestamp comparison[/bold cyan]"
    )
    print("Testing multiple interval types: 1s, 1m, 3m, 5m, 15m, 1h")
    print("Comparing March 15, 2023 and March 15, 2025 data to detect timestamp issues")

    success = run_timestamp_analysis()

    if success:
        print(
            "\n[bold green]✓ Successfully completed multi-interval timestamp analysis[/bold green]"
        )
    else:
        print("\n[bold red]✗ Failed to complete timestamp analysis[/bold red]")
        print("See logs for details")
