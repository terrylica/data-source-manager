#!/usr/bin/env python3
"""
Cache Diagnostic Tool for analyzing cache gaps in DataSourceManager.

This script helps diagnose the root causes of gaps in cache files by analyzing
the day boundaries and data transitions between cache files.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

# Add parent directory to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from utils.logger_setup import logger
from rich import print
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from core.sync.cache_manager import UnifiedCacheManager
from utils.market_constraints import MarketType, Interval
from utils.market_utils import get_market_type_str

console = Console()


def verify_project_root():
    """Verify that we're running from the project root directory."""
    if not os.path.exists("utils") or not os.path.exists("core"):
        print("❌ Not running from project root directory!")
        print("Please run this script from the root directory of the project.")
        sys.exit(1)
    print("Running from project root directory")
    return True


def check_date_transitions(
    data_dir, market_type="spot", symbol="BTCUSDT", interval="1m"
):
    """
    Analyze day transitions between cache files to identify gap causes.

    This is the key function for diagnosing day boundary gaps. It specifically examines
    the last records of each day and the first records of the next day.
    """
    cache_dir = Path(f"cache/binance/klines/{market_type}/{symbol}/{interval}")
    if not cache_dir.exists():
        print(f"[bold red]Cache directory {cache_dir} does not exist[/bold red]")
        return

    # Get sorted list of cache files (sorted by date in filename)
    cache_files = sorted([f for f in os.listdir(cache_dir) if f.endswith(".arrow")])
    if not cache_files:
        print(f"[bold yellow]No cache files found in {cache_dir}[/bold yellow]")
        return

    print(f"[bold cyan]Analyzing Day Transitions in Cache Files[/bold cyan]")
    print(f"Market: {market_type}, Symbol: {symbol}, Interval: {interval}")
    print(f"Found {len(cache_files)} cache files: {', '.join(cache_files)}")

    # Create a table for transition analysis
    table = Table(title="Day Boundary Transitions Analysis")
    table.add_column("From Date", style="cyan")
    table.add_column("To Date", style="green")
    table.add_column("Last Timestamp", style="yellow")
    table.add_column("Next Timestamp", style="yellow")
    table.add_column("Time Gap", style="red")
    table.add_column("Missing Points", style="red", justify="right")
    table.add_column("Is Gap?", style="magenta")

    # Track gaps for detailed reporting
    gaps = []

    # Analyze consecutive day transitions
    for i in range(len(cache_files) - 1):
        current_file = cache_files[i]
        next_file = cache_files[i + 1]

        # Extract dates from filenames
        current_date = current_file.split(".")[0]
        next_date = next_file.split(".")[0]

        # Load the data
        current_df = pd.read_feather(cache_dir / current_file)
        next_df = pd.read_feather(cache_dir / next_file)

        # Ensure data is sorted by open_time
        current_df = current_df.sort_values("open_time")
        next_df = next_df.sort_values("open_time")

        # Get last timestamp of current day and first timestamp of next day
        last_timestamp = current_df["open_time"].max()
        next_timestamp = next_df["open_time"].min()

        # Calculate time difference
        time_diff = next_timestamp - last_timestamp
        time_diff_seconds = time_diff.total_seconds()

        # Calculate expected interval in seconds
        expected_interval = 60  # Default for 1m
        if interval == "3m":
            expected_interval = 180
        elif interval == "5m":
            expected_interval = 300
        # Add more intervals as needed

        # Determine if this is a gap (more than 2 intervals missing)
        missing_points = max(0, int(time_diff_seconds / expected_interval) - 1)
        is_gap = missing_points > 0

        # Add to table
        table.add_row(
            current_date,
            next_date,
            last_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            next_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            f"{time_diff}",
            str(missing_points),
            "✓" if is_gap else "✗",
        )

        # Track gaps for detailed reporting
        if is_gap:
            gaps.append(
                {
                    "from_date": current_date,
                    "to_date": next_date,
                    "last_timestamp": last_timestamp.isoformat(),
                    "next_timestamp": next_timestamp.isoformat(),
                    "time_diff_seconds": time_diff_seconds,
                    "missing_points": missing_points,
                }
            )

    # Print the table
    console.print(table)

    # Print detailed analysis of gaps if any were found
    if gaps:
        print("\n[bold red]Detailed Analysis of Day Boundary Gaps:[/bold red]")
        for i, gap in enumerate(gaps):
            print(f"[bold]Gap {i+1}:[/bold]")
            print(f"  From {gap['from_date']} to {gap['to_date']}")
            print(f"  Last timestamp: {gap['last_timestamp']}")
            print(f"  Next timestamp: {gap['next_timestamp']}")
            print(f"  Time difference: {gap['time_diff_seconds']} seconds")
            print(f"  Missing points: {gap['missing_points']}")
            print("")

        # Save gap information to file
        os.makedirs("logs/cache_diagnostics", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"logs/cache_diagnostics/day_boundary_gaps_{market_type}_{symbol}_{interval}_{timestamp}.json"
        with open(output_file, "w") as f:
            json.dump(gaps, f, indent=2)
        print(f"[bold green]Saved gap analysis to {output_file}[/bold green]")
    else:
        print(
            "\n[bold green]No day boundary gaps detected between cache files![/bold green]"
        )


def analyze_cache_file(file_path):
    """Analyze a single cache file to identify internal gaps and missing data."""
    try:
        df = pd.read_feather(file_path)

        if df.empty:
            print(f"[bold yellow]Empty cache file: {file_path}[/bold yellow]")
            return None

        # Ensure data is sorted by open_time
        df = df.sort_values("open_time")

        # Calculate basic statistics
        min_time = df["open_time"].min()
        max_time = df["open_time"].max()
        record_count = len(df)
        time_span = max_time - min_time
        time_span_hours = time_span.total_seconds() / 3600

        # Calculate time differences between consecutive records
        df["next_time"] = df["open_time"].shift(-1)
        df["time_diff"] = df["next_time"] - df["open_time"]
        df["time_diff_seconds"] = df["time_diff"].dt.total_seconds()

        # Identify gaps (more than 2x expected interval)
        expected_interval = 60  # Default for 1m
        df["is_gap"] = df["time_diff_seconds"] > (expected_interval * 2)

        # Count gaps
        gaps_count = df["is_gap"].sum()

        # Get the largest gaps
        if gaps_count > 0:
            largest_gaps = df[df["is_gap"]].nlargest(5, "time_diff_seconds")
            largest_gap_seconds = largest_gaps["time_diff_seconds"].max()
        else:
            largest_gap_seconds = 0

        return {
            "file_path": str(file_path),
            "record_count": record_count,
            "time_range": {"start": min_time.isoformat(), "end": max_time.isoformat()},
            "time_span_hours": time_span_hours,
            "gaps_count": int(gaps_count),
            "largest_gap_seconds": largest_gap_seconds,
        }

    except Exception as e:
        print(f"[bold red]Error analyzing cache file {file_path}: {e}[/bold red]")
        return None


def diagnose_cache_files(market_type="spot", symbol="BTCUSDT", interval="1m"):
    """
    Diagnose all cache files to identify gaps and potential issues.

    This function analyzes each individual cache file and also the transitions
    between consecutive cache files to identify the root causes of gaps.
    """
    cache_dir = Path(f"cache/binance/klines/{market_type}/{symbol}/{interval}")
    if not cache_dir.exists():
        print(f"[bold red]Cache directory {cache_dir} does not exist[/bold red]")
        return

    # Get sorted list of cache files
    cache_files = sorted([f for f in os.listdir(cache_dir) if f.endswith(".arrow")])
    if not cache_files:
        print(f"[bold yellow]No cache files found in {cache_dir}[/bold yellow]")
        return

    print(f"[bold cyan]Running Comprehensive Cache Diagnostics[/bold cyan]")
    print(f"Market: {market_type}, Symbol: {symbol}, Interval: {interval}")
    print(f"Found {len(cache_files)} cache files")

    # Analyze each cache file
    file_results = []
    for file_name in cache_files:
        file_path = cache_dir / file_name
        print(f"Analyzing {file_name}...")
        result = analyze_cache_file(file_path)
        if result:
            file_results.append(result)

            # Print a summary of the analysis
            print(f"  Records: {result['record_count']}")
            print(
                f"  Time range: {result['time_range']['start']} to {result['time_range']['end']}"
            )
            print(f"  Duration: {result['time_span_hours']:.2f} hours")
            print(f"  Internal gaps: {result['gaps_count']}")
            if result["gaps_count"] > 0:
                print(f"  Largest gap: {result['largest_gap_seconds']:.1f} seconds")
            print("")

    # Create and print a summary table
    table = Table(title="Cache Files Analysis Summary")
    table.add_column("File", style="cyan")
    table.add_column("Records", justify="right", style="green")
    table.add_column("Start Time", style="yellow")
    table.add_column("End Time", style="yellow")
    table.add_column("Duration (h)", justify="right", style="blue")
    table.add_column("Gaps", justify="right", style="red")

    for result in file_results:
        file_name = os.path.basename(result["file_path"])
        table.add_row(
            file_name,
            str(result["record_count"]),
            result["time_range"]["start"].split("T")[0]
            + " "
            + result["time_range"]["start"].split("T")[1].split("+")[0],
            result["time_range"]["end"].split("T")[0]
            + " "
            + result["time_range"]["end"].split("T")[1].split("+")[0],
            f"{result['time_span_hours']:.2f}",
            str(result["gaps_count"]),
        )

    console.print(table)

    # Now analyze day transitions
    check_date_transitions(cache_dir, market_type, symbol, interval)

    # Save results to file
    os.makedirs("logs/cache_diagnostics", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"logs/cache_diagnostics/cache_analysis_{market_type}_{symbol}_{interval}_{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump(file_results, f, indent=2)
    print(f"[bold green]Saved cache file analysis to {output_file}[/bold green]")


def diagnose_daily_caching_strategy():
    """
    Explain the root cause of day boundary gaps in the cache.

    This function provides a detailed explanation about why gaps appear
    at day boundaries in cache files and what causes them.
    """
    panel = Panel(
        """[bold]Root Cause Analysis: Day Boundary Gaps in Cache Files[/bold]
        
The cache system stores data in separate files for each day (YYYYMMDD.arrow). When data is loaded from
multiple days, each day is loaded as a separate chunk and then concatenated. This design introduces
natural gaps at day boundaries due to the following reasons:

1. [bold cyan]Day-Based File Organization:[/bold cyan]
   Data is stored in separate files per day (20250406.arrow, 20250407.arrow, etc.)
   
2. [bold cyan]Independent Data Sources:[/bold cyan]
   Each day's data might come from different sources (CACHE, VISION, REST)
   
3. [bold cyan]Time Alignment Issues:[/bold cyan]
   The last timestamp of one day and the first timestamp of the next day
   may not be perfectly consecutive with exactly one interval difference
   
4. [bold cyan]Day Boundary Transitions:[/bold cyan]
   Special handling may occur when crossing from 23:59 to 00:00
   
5. [bold cyan]Timezone Considerations:[/bold cyan]
   The data uses UTC, but day boundaries may be defined differently
   
This diagnostic tool helps identify these gaps by analyzing the transitions between
consecutive cache files and looking for missing data points at day boundaries.
        """,
        title="Cache Organization and Day Boundary Gaps",
        border_style="green",
        padding=(1, 2),
    )

    console.print(panel)


def main():
    """Main function for the cache diagnostic tool."""
    verify_project_root()

    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(
        description="Cache Diagnostic Tool for analyzing cache gaps"
    )
    parser.add_argument(
        "--market", type=str, default="spot", help="Market type (spot, um, cm)"
    )
    parser.add_argument(
        "--symbol", type=str, default="BTCUSDT", help="Symbol (e.g., BTCUSDT)"
    )
    parser.add_argument(
        "--interval", type=str, default="1m", help="Interval (e.g., 1m, 5m)"
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Explain the root cause of day boundary gaps",
    )
    args = parser.parse_args()

    if args.explain:
        diagnose_daily_caching_strategy()
        return

    # Run diagnostics
    diagnose_cache_files(args.market, args.symbol, args.interval)


if __name__ == "__main__":
    main()
