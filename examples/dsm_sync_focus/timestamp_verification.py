#!/usr/bin/env python3
"""
Timestamp Verification Script for Vision API Data

This script demonstrates the timestamp interpretation issue by comparing:
1. Raw data downloaded directly from the Vision API
2. Processed data from the VisionDataClient

The script converts both timestamp formats to human-readable format for clear comparison.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import zipfile
import httpx
import pandas as pd
import subprocess
import os

from utils.logger_setup import logger
from rich import print
from utils.market_constraints import MarketType, Interval
from core.sync.vision_data_client import VisionDataClient


def download_raw_data(symbol, date, interval):
    """
    Download raw data directly from the Vision API without using VisionDataClient.

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        date: Date to download (datetime object)
        interval: Time interval (e.g., "1m")

    Returns:
        DataFrame with raw data
    """
    # Format date string
    date_str = date.strftime("%Y-%m-%d")

    # Create Vision API URL (following the pattern in the documentation)
    url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{date_str}.zip"

    print(f"[cyan]Downloading raw data from:[/cyan] {url}")

    # Create temporary directory for downloads
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / f"{symbol}-{interval}-{date_str}.zip"

        # Download the file using httpx
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)

            if response.status_code != 200:
                print(f"[red]Error downloading data: HTTP {response.status_code}[/red]")
                return None

            # Save the ZIP file
            with open(zip_path, "wb") as f:
                f.write(response.content)

            # Extract the ZIP file
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                csv_file = zip_ref.namelist()[0]  # Get the first file in the ZIP
                zip_ref.extract(csv_file, temp_dir)
                csv_path = Path(temp_dir) / csv_file

                # Read the CSV file (no headers in Vision API data)
                df = pd.read_csv(csv_path, header=None)

                # Return the raw data
                return df


def process_data_with_client(symbol, date, interval, market_type=MarketType.SPOT):
    """
    Process data using the VisionDataClient.

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        date: Date to download (datetime object)
        interval: Time interval (e.g., "1m")
        market_type: Market type (default: SPOT)

    Returns:
        DataFrame with processed data
    """
    # Define time range (first 18 minutes of the day)
    start_time = datetime(date.year, date.month, date.day, 0, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(date.year, date.month, date.day, 0, 17, 59, tzinfo=timezone.utc)

    print(f"[cyan]Fetching data using VisionDataClient:[/cyan]")
    print(f"Time range: {start_time.isoformat()} to {end_time.isoformat()}")

    # Use VisionDataClient to fetch data
    with VisionDataClient(
        symbol=symbol, interval=interval, market_type=market_type
    ) as client:
        # Fetch data for the specified time range
        df = client.fetch(
            symbol=symbol,
            interval=interval,
            start_time=start_time,
            end_time=end_time,
        )

        return df


def compare_timestamps(raw_df, processed_df):
    """
    Compare raw and processed timestamps and display the differences.

    Args:
        raw_df: DataFrame with raw data
        processed_df: DataFrame with processed data

    Returns:
        None
    """
    if raw_df is None or processed_df is None:
        print(
            "[red]Cannot compare timestamps: One or both DataFrames are missing[/red]"
        )
        return

    print("\n[bold green]Timestamp Comparison:[/bold green]")

    # Keep only the rows for the first 18 minutes from raw data
    raw_df_filtered = raw_df.iloc[:18].copy()

    # For raw data, convert the timestamps (first column)
    raw_df_filtered["human_timestamp"] = raw_df_filtered.iloc[:, 0].apply(
        lambda x: datetime.fromtimestamp(x / 1000000, tz=timezone.utc).isoformat()
    )

    # For processed data, use the open_time column
    if "open_time" in processed_df.columns:
        # Already a datetime, just convert to ISO format for consistency
        processed_df["human_timestamp"] = processed_df["open_time"].apply(
            lambda x: x.isoformat() if pd.notna(x) else None
        )

    # Create a side-by-side comparison table
    raw_timestamps = raw_df_filtered["human_timestamp"].tolist()

    # Get processed timestamps
    if "human_timestamp" in processed_df.columns:
        proc_timestamps = processed_df["human_timestamp"].tolist()
    else:
        proc_timestamps = []

    # Print comparison table
    print("\n[bold yellow]Raw vs Processed Timestamps:[/bold yellow]")
    print(f"{'Minute':>6} | {'Raw Timestamp':^26} | {'Processed Timestamp':^26}")
    print(f"{'-'*6} | {'-'*26} | {'-'*26}")

    # Process all 18 minutes, even if some are missing from one dataset
    for i in range(18):
        raw_ts = raw_timestamps[i] if i < len(raw_timestamps) else "N/A"
        proc_ts = proc_timestamps[i] if i < len(proc_timestamps) else "N/A"

        # Extract just the minute portion for better readability
        if raw_ts != "N/A":
            raw_min = raw_ts.split("T")[1][:5]  # Extract HH:MM
        else:
            raw_min = "N/A"

        if proc_ts != "N/A":
            proc_min = proc_ts.split("T")[1][:5]  # Extract HH:MM
        else:
            proc_min = "N/A"

        # Highlight discrepancies
        if raw_min != proc_min:
            minute_str = f"[bold red]{i:02d}[/bold red]"
            raw_str = f"[bold red]{raw_min}[/bold red]"
            proc_str = f"[bold red]{proc_min}[/bold red]"
        else:
            minute_str = f"{i:02d}"
            raw_str = raw_min
            proc_str = proc_min

        print(f"{minute_str:>6} | {raw_str:^26} | {proc_str:^26}")

    # Count missing entries
    raw_count = len(raw_timestamps)
    proc_count = len(proc_timestamps)

    print(f"\nRaw data entries: {raw_count}")
    print(f"Processed data entries: {proc_count}")

    if raw_count != proc_count:
        print(
            f"[bold red]Discrepancy in entry count: {abs(raw_count - proc_count)}[/bold red]"
        )


def analyze_timestamp_difference():
    """
    Run the timestamp analysis and display the results.
    """
    # Configuration
    symbol = "BTCUSDT"
    interval = "1m"
    date = datetime(2025, 3, 15, tzinfo=timezone.utc)

    print(f"[bold cyan]Vision API Timestamp Analysis[/bold cyan]")
    print(f"Symbol: {symbol}")
    print(f"Interval: {interval}")
    print(f"Date: {date.strftime('%Y-%m-%d')}")

    # Download raw data directly
    raw_df = download_raw_data(symbol, date, interval)

    if raw_df is None:
        print("[red]Failed to download raw data. Exiting.[/red]")
        return

    print(f"[green]Successfully downloaded raw data: {len(raw_df)} rows[/green]")

    # Process data using VisionDataClient
    processed_df = process_data_with_client(symbol, date, interval)

    if processed_df is None or processed_df.empty:
        print("[red]Failed to process data using VisionDataClient. Exiting.[/red]")
        return

    print(f"[green]Successfully processed data: {len(processed_df)} rows[/green]")

    # Compare timestamps
    compare_timestamps(raw_df, processed_df)

    # Save comparison results
    output_dir = Path("./output")
    output_dir.mkdir(exist_ok=True)

    # Create a simple HTML with a comparison table
    html_output = f"""
    <html>
    <head>
        <title>Vision API Timestamp Comparison</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #0066cc; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
            th, td {{ padding: 8px; text-align: left; border: 1px solid #ddd; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
            .mismatch {{ background-color: #ffcccc; }}
            .summary {{ margin-top: 20px; padding: 10px; background-color: #f2f2f2; }}
        </style>
    </head>
    <body>
        <h1>Vision API Timestamp Comparison</h1>
        <p><strong>Symbol:</strong> {symbol} | <strong>Interval:</strong> {interval} | <strong>Date:</strong> {date.strftime('%Y-%m-%d')}</p>
        
        <h2>Timestamp Comparison</h2>
        <table>
            <tr>
                <th>Minute</th>
                <th>Raw Timestamp</th>
                <th>Processed Timestamp</th>
                <th>Discrepancy</th>
            </tr>
    """

    # Add rows to HTML
    raw_timestamps = []
    if raw_df is not None and not raw_df.empty:
        for i in range(min(18, len(raw_df))):
            ts = raw_df.iloc[i, 0]
            dt = datetime.fromtimestamp(ts / 1000000, tz=timezone.utc)
            raw_timestamps.append(dt)

    processed_timestamps = []
    if (
        processed_df is not None
        and not processed_df.empty
        and "open_time" in processed_df.columns
    ):
        processed_timestamps = processed_df["open_time"].tolist()

    # Process all 18 minutes
    for i in range(18):
        raw_ts = raw_timestamps[i] if i < len(raw_timestamps) else None
        proc_ts = processed_timestamps[i] if i < len(processed_timestamps) else None

        raw_str = raw_ts.strftime("%Y-%m-%d %H:%M:%S") if raw_ts else "N/A"
        proc_str = proc_ts.strftime("%Y-%m-%d %H:%M:%S") if proc_ts else "N/A"

        if raw_ts and proc_ts:
            # Calculate discrepancy in seconds
            diff_seconds = (proc_ts - raw_ts).total_seconds()
            discrepancy = f"{diff_seconds:.2f} seconds"
            mismatch_class = ' class="mismatch"' if abs(diff_seconds) > 1 else ""
        else:
            discrepancy = "N/A"
            mismatch_class = ' class="mismatch"'

        html_output += f"""
            <tr{mismatch_class}>
                <td>{i:02d}</td>
                <td>{raw_str}</td>
                <td>{proc_str}</td>
                <td>{discrepancy}</td>
            </tr>
        """

    # Add summary to HTML
    html_output += f"""
        </table>
        
        <div class="summary">
            <h3>Summary</h3>
            <p>Raw data entries: {len(raw_timestamps)}</p>
            <p>Processed data entries: {len(processed_timestamps)}</p>
            
            <h3>Observations</h3>
            <ul>
                <li>The VisionDataClient interprets timestamps as the end of each minute period, 
                    while the raw data marks timestamps at the beginning of the period.</li>
                <li>This creates a "one-minute shift" in the data when comparing raw Vision API data 
                    with processed data.</li>
                <li>The first candle of the requested period is typically missing in the processed output.</li>
            </ul>
        </div>
    </body>
    </html>
    """

    # Save HTML report
    html_path = output_dir / f"{symbol}_{interval}_timestamp_comparison.html"
    with open(html_path, "w") as f:
        f.write(html_output)

    print(f"\n[green]Report saved to: {html_path}[/green]")

    # Try to open HTML file if running in an environment with a browser
    try:
        # On macOS/Linux/Windows
        if os.name == "posix":
            os.system(f"open {html_path}")
        elif os.name == "nt":  # Windows
            os.system(f"start {html_path}")
    except Exception:
        pass  # Silently ignore if we can't open the browser


if __name__ == "__main__":
    # Configure logger
    logger.use_rich(True)
    logger.setLevel("INFO")

    # Run the analysis
    analyze_timestamp_difference()
