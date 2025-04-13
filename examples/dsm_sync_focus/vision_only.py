#!/usr/bin/env python3
"""
Standalone script that uses VisionDataClient directly to fetch 1-minute BTCUSDT spot data
for both 2023 and 2025 data to compare timestamp formats and detect timestamp misalignment.

This example demonstrates direct use of the VisionDataClient without going through
the DataSourceManager layer and identifies the timestamp interpretation issue.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
import json

from utils.logger_setup import logger
from rich import print
from rich.table import Table
from rich.console import Console
from utils.market_constraints import MarketType, Interval, DataProvider, ChartType
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

    # Adjust time range based on interval to get meaningful data
    # For larger intervals like 1h, we need a wider time range
    if interval == Interval.SECOND_1:
        # For 1s, just use 2 minutes of data (120 data points)
        start_time = datetime(year, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(year, 3, 15, 0, 1, 59, tzinfo=timezone.utc)
    elif interval == Interval.MINUTE_1:
        # For 1m, use 18 minutes as before
        start_time = datetime(year, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(year, 3, 15, 0, 17, 59, tzinfo=timezone.utc)
    elif interval in [Interval.MINUTE_3, Interval.MINUTE_5, Interval.MINUTE_15]:
        # For 3m/5m/15m, use first 2 hours
        start_time = datetime(year, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(year, 3, 15, 1, 59, 59, tzinfo=timezone.utc)
    elif interval == Interval.HOUR_1:
        # For 1h, use full day
        start_time = datetime(year, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(year, 3, 15, 23, 59, 59, tzinfo=timezone.utc)
    else:
        # Default: 30 minute range
        start_time = datetime(year, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(year, 3, 15, 0, 29, 59, tzinfo=timezone.utc)

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
            if "_original_timestamp" not in df.columns and "open_time" in df.columns:
                df["original_timestamp"] = (
                    df["open_time"].astype(np.int64) // 1000000
                )  # Convert ns to ms

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
        # Read the raw data - no headers in the file
        df = pd.read_csv(raw_file_path, header=None)

        # Check the number of digits in the timestamp to determine format
        first_ts = df.iloc[0, 0]  # First timestamp in first column
        digits = len(str(int(first_ts)))

        # Determine timestamp unit based on the number of digits
        timestamp_unit = "microseconds" if digits >= 16 else "milliseconds"

        # Convert the first few timestamps to datetime for display
        timestamps = []
        for idx in range(min(5, len(df))):
            ts_value = df.iloc[idx, 0]
            if timestamp_unit == "microseconds":
                ts = datetime.fromtimestamp(ts_value / 1000000, tz=timezone.utc)
            else:
                ts = datetime.fromtimestamp(ts_value / 1000, tz=timezone.utc)

            timestamps.append(
                {
                    "raw_value": str(ts_value),
                    "converted_datetime": ts.isoformat(),
                    "human_readable": ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                }
            )

        return {
            "year": year,
            "record_count": len(df),
            "columns_count": df.shape[1],
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

    first_processed_ts = processed_df["open_time"].iloc[0]

    # Get first timestamp from raw data
    raw_first_ts_str = raw_analysis["sample_timestamps"][0]["converted_datetime"]
    raw_first_ts = datetime.fromisoformat(raw_first_ts_str)

    # Calculate the difference in seconds
    time_diff = (first_processed_ts - raw_first_ts).total_seconds()

    # Get the second component of processed timestamps
    processed_seconds = processed_df["open_time"].dt.second.value_counts().to_dict()

    # Check for misalignment patterns
    seconds_at_59 = processed_seconds.get(59, 0)
    proportion_at_59 = seconds_at_59 / len(processed_df) if len(processed_df) > 0 else 0

    # Missing first candle check - if first raw timestamp doesn't appear in processed data
    first_raw_dt = datetime.fromisoformat(
        raw_analysis["sample_timestamps"][0]["converted_datetime"]
    )
    missing_first_candle = not any(
        (processed_df["open_time"] - first_raw_dt).abs().dt.total_seconds() < 1
    )

    # Check for consistent time shift
    time_shift = None
    if abs(time_diff) > 0:
        if abs(time_diff - 60) < 1:  # Approximately 60 seconds shift
            time_shift = "one_interval_forward"
        elif abs(time_diff + 60) < 1:  # Approximately -60 seconds shift
            time_shift = "one_interval_backward"
        else:
            time_shift = f"irregular_shift_{time_diff:.1f}_seconds"

    return {
        "year": year,
        "first_raw_timestamp": raw_first_ts_str,
        "first_processed_timestamp": first_processed_ts.isoformat(),
        "time_difference_seconds": time_diff,
        "detected_time_shift": time_shift,
        "missing_first_candle": missing_first_candle,
        "processed_timestamp_seconds_distribution": processed_seconds,
        "timestamps_ending_at_59s": seconds_at_59,
        "proportion_at_59s": float(proportion_at_59),
        "timestamp_misalignment_detected": proportion_at_59 > 0.9
        or missing_first_candle
        or time_shift == "one_interval_forward",
    }


def generate_timestamp_report(comparison_2023, comparison_2025):
    """
    Generate a report on timestamp misalignment issues

    Args:
        comparison_2023: Results of 2023 data comparison
        comparison_2025: Results of 2025 data comparison

    Returns:
        None, prints report to console
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
        f"{comparison_2023['time_difference_seconds']:.1f}",
        f"{comparison_2025['time_difference_seconds']:.1f}",
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
    table.add_row(
        "% Timestamps Ending at :59",
        f"{comparison_2023['proportion_at_59s']*100:.1f}%",
        f"{comparison_2025['proportion_at_59s']*100:.1f}%",
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

    # Generate conclusion
    print("\n[bold]Conclusion:[/bold]")

    misalignment_2023 = comparison_2023["timestamp_misalignment_detected"]
    misalignment_2025 = comparison_2025["timestamp_misalignment_detected"]

    if misalignment_2023 and misalignment_2025:
        print(
            "[bold red]Timestamp misalignment detected in both 2023 and 2025 data.[/bold red]"
        )
        print(
            "The issue appears to be consistent across both timestamp formats (milliseconds and microseconds)."
        )
    elif misalignment_2023:
        print(
            "[bold yellow]Timestamp misalignment detected in 2023 data only.[/bold yellow]"
        )
        print("The 2025 data appears to be correctly aligned.")
    elif misalignment_2025:
        print(
            "[bold yellow]Timestamp misalignment detected in 2025 data only.[/bold yellow]"
        )
        print("The 2023 data appears to be correctly aligned.")
    else:
        print(
            "[bold green]No timestamp misalignment detected in either dataset.[/bold green]"
        )
        print("Both 2023 and 2025 data are correctly aligned.")

    # Save detailed report to JSON for further analysis
    output_dir = Path("./examples/dsm_sync_focus/output")
    report_file = output_dir / "timestamp_analysis_report.json"

    with open(report_file, "w") as f:
        json.dump(
            {
                "analysis_2023": comparison_2023,
                "analysis_2025": comparison_2025,
                "summary": {
                    "misalignment_detected_2023": misalignment_2023,
                    "misalignment_detected_2025": misalignment_2025,
                    "overall_issue_detected": misalignment_2023 or misalignment_2025,
                },
            },
            f,
            indent=2,
        )

    print(f"\nDetailed analysis saved to [cyan]{report_file}[/cyan]")


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
