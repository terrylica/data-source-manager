#!/usr/bin/env python3
"""
Simplified script to compare raw Vision API data with processed output.
This script:
1. Downloads raw data from Binance Vision API
2. Processes the same data through VisionDataClient
3. Displays both side by side for direct comparison
"""

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import httpx
import zipfile
import io
from rich.console import Console
from rich.table import Table
from rich import print

from utils.logger_setup import logger
from utils.market_constraints import MarketType, Interval
from core.sync.vision_data_client import VisionDataClient


def download_raw_data(symbol, date, interval):
    """
    Download raw data directly from Binance Vision API using httpx

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        date: Date string in YYYY-MM-DD format
        interval: Interval string (e.g., "1m")

    Returns:
        Path to downloaded raw data or None if error
    """
    url = f"https://data.binance.vision/data/spot/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{date}.zip"

    output_dir = Path("./examples/dsm_sync_focus/simple/output")
    output_dir.mkdir(exist_ok=True, parents=True)

    raw_file = output_dir / f"{symbol}-{interval}-{date}-raw.csv"

    try:
        print(f"[bold]Downloading raw data from:[/bold] {url}")

        with httpx.Client() as client:
            response = client.get(url)

            if response.status_code != 200:
                print(
                    f"[bold red]Failed to download raw data: HTTP {response.status_code}[/bold red]"
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
            print(f"[bold green]Raw data saved to:[/bold green] {raw_file}")

            return raw_file

    except Exception as e:
        print(f"[bold red]Error downloading raw data: {e}[/bold red]")
        return None


def fetch_processed_data(symbol, date_obj, interval_enum):
    """
    Fetch data from Binance Vision API using VisionDataClient

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        date_obj: datetime object for the date to fetch
        interval_enum: Interval enum from market_constraints

    Returns:
        DataFrame with processed data or None if error
    """
    # Configure logger
    logger.use_rich(True)
    # logger.setLevel("INFO")
    logger.setLevel("DEBUG")

    # Calculate time range - use first 10 minutes of the day for comparison
    start_time = datetime(
        date_obj.year, date_obj.month, date_obj.day, 0, 0, 0, 0, tzinfo=timezone.utc
    )
    end_time = datetime(
        date_obj.year,
        date_obj.month,
        date_obj.day,
        0,
        9,
        59,
        999999,
        tzinfo=timezone.utc,
    )

    try:
        # Use context manager for proper resource cleanup
        with VisionDataClient(
            symbol=symbol,
            interval=interval_enum.value,
            market_type=MarketType.SPOT,
        ) as client:
            print(
                f"[bold]Fetching data through VisionDataClient:[/bold] {start_time} to {end_time}"
            )

            # Fetch data for the specified time range
            df = client.fetch(
                symbol=symbol,
                interval=interval_enum.value,
                start_time=start_time,
                end_time=end_time,
            )

            # Check if we have data
            if df is None or df.empty:
                print(f"[bold red]No data retrieved from Vision API[/bold red]")
                return None

            # Save to CSV for inspection
            output_dir = Path("./examples/dsm_sync_focus/simple/output")
            output_dir.mkdir(exist_ok=True)

            output_file = output_dir / f"{symbol}_{interval_enum.value}_processed.csv"
            df.to_csv(output_file)
            print(f"[bold green]Processed data saved to:[/bold green] {output_file}")

            return df
    except Exception as e:
        print(f"[bold red]Error fetching data from VisionDataClient: {e}[/bold red]")
        return None


def display_comparison(raw_file, processed_df, n_rows=5):
    """
    Display a side-by-side comparison of raw and processed data

    Args:
        raw_file: Path to raw CSV file
        processed_df: DataFrame with processed data
        n_rows: Number of rows to display
    """
    console = Console()

    if raw_file is None or not raw_file.exists():
        print("[bold red]Raw file not available for comparison[/bold red]")
        return

    if processed_df is None or processed_df.empty:
        print("[bold red]Processed data not available for comparison[/bold red]")
        return

    # Read raw CSV data
    raw_df = pd.read_csv(raw_file, header=None)
    # Use standard kline column names from Binance documentation
    raw_df.columns = [
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

    # Create comparison table for timestamps
    print("\n[bold yellow]===== TIMESTAMP COMPARISON =====[/bold yellow]")

    table = Table(title=f"First {n_rows} Rows Comparison")
    table.add_column("Row", style="cyan")
    table.add_column("Raw open_time", style="green")
    table.add_column("Raw timestamp (human)", style="green")
    table.add_column("Raw close", style="green")
    table.add_column("Processed open_time", style="yellow")
    table.add_column("Processed close", style="yellow")

    # Determine timestamp format based on the first row
    first_ts = raw_df.iloc[0, 0]  # First column is open_time
    digits = len(str(int(first_ts)))

    # Correctly determine timestamp unit based on digits
    is_microseconds = digits >= 16
    divisor = 1000000 if is_microseconds else 1000

    print(f"\n[bold]Raw Data Format:[/bold]")
    if is_microseconds:
        print("- Using microsecond precision (16 digits)")
    else:
        print("- Using millisecond precision (13 digits)")

    for i in range(min(n_rows, len(raw_df), len(processed_df))):
        # Get raw timestamp
        raw_ts = raw_df.iloc[i, 0]  # First column is open_time
        raw_close = raw_df.iloc[i, 4]  # Fifth column is close price

        # Convert to datetime
        raw_dt = datetime.fromtimestamp(raw_ts / divisor, tz=timezone.utc)

        # Get processed timestamp
        if "open_time" in processed_df.columns:
            proc_ts = processed_df["open_time"].iloc[i]
        else:
            # If open_time is index, use index
            proc_ts = processed_df.index[i]

        # Get processed close price
        proc_close = (
            processed_df["close"].iloc[i] if "close" in processed_df.columns else "N/A"
        )

        # Add row to table
        table.add_row(
            str(i),
            str(raw_ts),
            raw_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            str(raw_close),
            str(proc_ts),
            str(proc_close),
        )

    console.print(table)

    # Analyze timestamp difference
    if "open_time" in processed_df.columns:
        proc_first = processed_df["open_time"].iloc[0]
    else:
        proc_first = processed_df.index[0]

    raw_first = datetime.fromtimestamp(raw_df.iloc[0, 0] / divisor, tz=timezone.utc)
    time_diff = (proc_first - raw_first).total_seconds()

    print(f"\n[bold]Timestamp Difference Analysis:[/bold]")
    print(f"- Time difference: {time_diff:.3f} seconds")

    # Determine if there's a systematic shift
    if abs(time_diff) < 0.1:
        print("[bold green]✓ Timestamps are perfectly aligned[/bold green]")
    elif abs(time_diff - 60) < 0.1:
        print(
            "[bold red]! Timestamps appear to be shifted by exactly 1 minute[/bold red]"
        )
    elif abs(time_diff - 1) < 0.1:
        print(
            "[bold yellow]! Timestamps appear to be shifted by exactly 1 second[/bold yellow]"
        )
    else:
        print(
            f"[bold red]! Irregular timestamp shift detected: {time_diff:.3f} seconds[/bold red]"
        )


def main():
    """Main function to run the comparison"""
    # Define parameters
    symbol = "BTCUSDT"
    # Use March 15, 2025 for testing with μs precision data
    date_str = "2025-03-15"
    date_obj = datetime(2025, 3, 15)
    interval_enum = Interval.MINUTE_1

    print(f"[bold cyan]===== VISION API TIMESTAMP COMPARISON =====[/bold cyan]")
    print(f"Symbol: {symbol}")
    print(f"Date: {date_str}")
    print(f"Interval: {interval_enum.value}")

    # Create output directory
    output_dir = Path("./examples/dsm_sync_focus/simple/output")
    output_dir.mkdir(exist_ok=True, parents=True)

    # Step 1: Download raw data
    raw_file = download_raw_data(symbol, date_str, interval_enum.value)

    # Step 2: Fetch processed data
    processed_df = fetch_processed_data(symbol, date_obj, interval_enum)

    # Step 3: Display comparison
    display_comparison(raw_file, processed_df)

    print("\n[bold]Files saved for further inspection:[/bold]")
    print(
        f"- Raw data: {output_dir / f'{symbol}-{interval_enum.value}-{date_str}-raw.csv'}"
    )
    print(
        f"- Processed data: {output_dir / f'{symbol}_{interval_enum.value}_processed.csv'}"
    )


if __name__ == "__main__":
    main()
