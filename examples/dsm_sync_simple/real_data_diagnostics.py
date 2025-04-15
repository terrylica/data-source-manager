#!/usr/bin/env python3
"""
Real Data Diagnostics Tool for analyzing genuine market data.

This script connects directly to the Binance API through DataSourceManager
to retrieve and analyze actual market data without any synthetic test scenarios.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import time

# Add parent directory to path for imports
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from utils.logger_setup import logger
from rich import print
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from core.sync.data_source_manager import DataSourceManager
from utils.market_constraints import MarketType, Interval, DataProvider, ChartType
from utils.gap_detector import detect_gaps

console = Console()


def verify_project_root():
    """Verify that we're running from the project root directory."""
    if not os.path.exists("utils") or not os.path.exists("core"):
        print("❌ Not running from project root directory!")
        print("Please run this script from the root directory of the project.")
        sys.exit(1)
    print("Running from project root directory")
    return True


def fetch_real_market_data(
    market_type_str="spot",
    symbol="BTCUSDT",
    interval_str="1m",
    days=3,
    use_cache=True,
    enforce_cache_clear=False,
):
    """
    Fetch real market data directly from the API using DataSourceManager.

    Args:
        market_type_str: Market type (spot, um, cm)
        symbol: Symbol to fetch data for
        interval_str: Interval (e.g., 1m, 5m)
        days: Number of days to fetch
        use_cache: Whether to use cache
        enforce_cache_clear: If True, clear cache before fetching

    Returns:
        DataFrame with market data
    """
    # Convert string parameters to enum types
    market_type = MarketType.from_string(market_type_str)
    interval = Interval(interval_str)

    # Set up time range for data retrieval
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    print(f"[bold cyan]Fetching Real Market Data[/bold cyan]")
    print(f"Market: {market_type.name}, Symbol: {symbol}, Interval: {interval.value}")
    print(f"Date Range: {start_time.isoformat()} to {end_time.isoformat()}")
    print(f"Using Cache: {use_cache}")

    # If enforcing cache clear, delete cache files for this symbol/interval
    if enforce_cache_clear and use_cache:
        clear_cache_for_symbol(market_type_str, symbol, interval_str)

    # Create DataSourceManager and fetch data
    start_fetch = time.time()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Fetching data...", total=None)

        with DataSourceManager(
            market_type=market_type,
            provider=DataProvider.BINANCE,
            chart_type=ChartType.KLINES,
            use_cache=use_cache,
            retry_count=3,
        ) as manager:
            df = manager.get_data(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                interval=interval,
                include_source_info=True,
            )

        progress.update(task, completed=True)

    fetch_time = time.time() - start_fetch

    if df is None or df.empty:
        print(f"[bold red]No data retrieved for {symbol}[/bold red]")
        return None

    print(
        f"[bold green]Retrieved {len(df)} records in {fetch_time:.2f} seconds[/bold green]"
    )

    # Analyze source distribution if available
    if "_data_source" in df.columns:
        source_counts = df["_data_source"].value_counts()

        table = Table(title="Data Source Distribution")
        table.add_column("Source", style="cyan")
        table.add_column("Records", justify="right", style="green")
        table.add_column("Percentage", justify="right", style="yellow")

        for source, count in source_counts.items():
            percentage = (count / len(df)) * 100
            table.add_row(source, f"{count:,}", f"{percentage:.1f}%")

        console.print(table)

    return df


def clear_cache_for_symbol(market_type, symbol, interval):
    """
    Clear cache files for a specific symbol.

    Args:
        market_type: Market type string
        symbol: Symbol
        interval: Interval string
    """
    cache_dir = Path(f"cache/binance/klines/{market_type}/{symbol}/{interval}")
    if cache_dir.exists():
        print(
            f"[yellow]Clearing cache for {market_type}/{symbol}/{interval}...[/yellow]"
        )
        for file in cache_dir.glob("*.arrow"):
            file.unlink()
            print(f"  Removed {file}")
    else:
        print(f"[yellow]No cache directory found at {cache_dir}[/yellow]")


def analyze_data_continuity(df):
    """
    Analyze data for continuity and identify any gaps.

    Args:
        df: DataFrame with market data

    Returns:
        Dictionary with analysis results
    """
    if df is None or len(df) < 2:
        print("[bold red]Not enough data for continuity analysis[/bold red]")
        return None

    # Ensure data is sorted by open_time
    df = df.sort_values("open_time").reset_index(drop=True)

    # Calculate time differences between consecutive records
    df["next_time"] = df["open_time"].shift(-1)
    df["time_diff"] = df["next_time"] - df["open_time"]
    df["time_diff_seconds"] = df["time_diff"].dt.total_seconds()

    # Get interval from the data (most common time difference)
    interval_seconds = df["time_diff_seconds"].value_counts().index[0]
    print(f"[cyan]Detected interval: {interval_seconds} seconds[/cyan]")

    # Identify gaps (more than 1.5x the normal interval)
    threshold = interval_seconds * 1.5
    df["is_gap"] = df["time_diff_seconds"] > threshold

    # Count gaps
    total_gaps = df["is_gap"].sum()

    # Analyze gaps by data source if available
    gaps_by_source = {}
    if "_data_source" in df.columns:
        for source in df["_data_source"].unique():
            source_gaps = df[df["_data_source"] == source]["is_gap"].sum()
            gaps_by_source[source] = int(source_gaps)

    # Find the largest gaps
    if total_gaps > 0:
        largest_gaps = df[df["is_gap"]].nlargest(5, "time_diff_seconds")

        table = Table(title="Largest Data Gaps")
        table.add_column("Start Time", style="cyan")
        table.add_column("End Time", style="cyan")
        table.add_column("Gap Duration", style="red")
        table.add_column("Missing Points", justify="right", style="yellow")
        table.add_column("Source", style="green")

        for _, row in largest_gaps.iterrows():
            missing_points = int(row["time_diff_seconds"] / interval_seconds) - 1
            source = row.get("_data_source", "Unknown")

            table.add_row(
                row["open_time"].strftime("%Y-%m-%d %H:%M:%S"),
                row["next_time"].strftime("%Y-%m-%d %H:%M:%S"),
                str(timedelta(seconds=row["time_diff_seconds"])),
                str(missing_points),
                source,
            )

        console.print(table)

    # Analyze day boundary transitions
    print("\n[bold cyan]Analyzing Day Boundary Transitions[/bold cyan]")
    day_transitions = []

    # Add date column for grouping
    df["date"] = df["open_time"].dt.date

    # Get unique dates
    dates = sorted(df["date"].unique())

    # Check transitions between days
    if len(dates) > 1:
        day_boundary_table = Table(title="Day Boundary Transitions")
        day_boundary_table.add_column("From Date", style="cyan")
        day_boundary_table.add_column("To Date", style="cyan")
        day_boundary_table.add_column("Last Timestamp", style="yellow")
        day_boundary_table.add_column("Next Timestamp", style="yellow")
        day_boundary_table.add_column("Time Gap", style="red")
        day_boundary_table.add_column("Is Gap?", style="magenta")

        for i in range(len(dates) - 1):
            current_date = dates[i]
            next_date = dates[i + 1]

            # Get last record of current day and first record of next day
            last_record = df[df["date"] == current_date].iloc[-1]
            first_record = df[df["date"] == next_date].iloc[0]

            time_diff = first_record["open_time"] - last_record["open_time"]
            time_diff_seconds = time_diff.total_seconds()

            # Check if this transition is a gap
            is_gap = time_diff_seconds > threshold

            day_boundary_table.add_row(
                current_date.strftime("%Y-%m-%d"),
                next_date.strftime("%Y-%m-%d"),
                last_record["open_time"].strftime("%H:%M:%S"),
                first_record["open_time"].strftime("%H:%M:%S"),
                str(time_diff),
                "✓" if is_gap else "✗",
            )

            # Track day transitions
            day_transitions.append(
                {
                    "from_date": current_date.strftime("%Y-%m-%d"),
                    "to_date": next_date.strftime("%Y-%m-%d"),
                    "last_timestamp": last_record["open_time"].isoformat(),
                    "next_timestamp": first_record["open_time"].isoformat(),
                    "time_diff_seconds": time_diff_seconds,
                    "is_gap": bool(is_gap),
                }
            )

        console.print(day_boundary_table)

    # Compile results
    results = {
        "total_records": len(df),
        "time_range": {
            "start": df["open_time"].min().isoformat(),
            "end": df["open_time"].max().isoformat(),
        },
        "interval_seconds": interval_seconds,
        "total_gaps": int(total_gaps),
        "gaps_by_source": gaps_by_source,
        "day_boundary_transitions": day_transitions,
    }

    # Save results to file
    output_dir = Path("./logs/real_data_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"data_analysis_{timestamp}.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"[bold green]Analysis results saved to {output_file}[/bold green]")

    return results


def perform_gap_analysis(df, interval_str="1m", gap_threshold=0.3):
    """
    Perform detailed gap analysis using the gap_detector module.

    Args:
        df: DataFrame with market data
        interval_str: Interval string
        gap_threshold: Gap threshold (default: 0.3 = 30%)
    """
    if df is None or len(df) < 2:
        print("[bold red]Not enough data for gap analysis[/bold red]")
        return

    print(
        f"\n[bold cyan]Performing Gap Analysis (threshold: {gap_threshold:.1f})[/bold cyan]"
    )

    # Convert interval string to enum
    interval = Interval(interval_str)

    # Reset index if needed
    if df.index.name == "open_time":
        df_copy = df.reset_index()
    else:
        df_copy = df.copy()

    # Ensure open_time column exists
    if "open_time" not in df_copy.columns:
        print("[bold red]ERROR: DataFrame doesn't have an open_time column![/bold red]")
        return

    # Split analysis by source if available
    if "_data_source" in df_copy.columns:
        sources = df_copy["_data_source"].unique().tolist()
        sources.append("COMBINED")  # Add combined analysis
    else:
        sources = ["COMBINED"]

    # Prepare result structure
    results = {
        "metadata": {
            "interval": interval_str,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "gap_threshold": gap_threshold,
        },
        "statistics": {
            "overall": {},
            "by_source": {},
        },
        "gaps": [],
    }

    # Create a table for results
    summary_table = Table(title="Gap Analysis Summary")
    summary_table.add_column("Source", style="cyan")
    summary_table.add_column("Records", style="green", justify="right")
    summary_table.add_column("Total Gaps", style="yellow", justify="right")
    summary_table.add_column("Day Boundary", style="yellow", justify="right")
    summary_table.add_column("Non-Boundary", style="yellow", justify="right")
    summary_table.add_column("Max Duration", style="red", justify="right")

    # Analyze gaps for each source
    for source in sources:
        if source == "COMBINED":
            source_df = df_copy.copy()
        else:
            source_df = df_copy[df_copy["_data_source"] == source].copy()

        if len(source_df) < 2:
            print(
                f"[yellow]Not enough data points for source: {source} - skipping[/yellow]"
            )
            continue

        print(f"[bold]Analyzing gaps for source: {source}[/bold]")

        # Detect gaps using the gap_detector module
        gaps, stats = detect_gaps(
            source_df,
            interval,
            time_column="open_time",
            gap_threshold=gap_threshold,
        )

        # Save statistics
        source_stats = {
            "total_gaps": stats["total_gaps"],
            "day_boundary_gaps": stats.get("day_boundary_gaps", 0),
            "non_boundary_gaps": stats.get("non_boundary_gaps", 0),
            "max_gap_duration": str(stats.get("max_gap_duration", "0")),
            "total_records": stats["total_records"],
            "first_timestamp": (
                stats.get("first_timestamp", "").isoformat()
                if stats.get("first_timestamp")
                else None
            ),
            "last_timestamp": (
                stats.get("last_timestamp", "").isoformat()
                if stats.get("last_timestamp")
                else None
            ),
            "timespan_hours": stats.get("timespan_hours", 0),
        }

        if source == "COMBINED":
            results["statistics"]["overall"] = source_stats
        else:
            results["statistics"]["by_source"][source] = source_stats

        # Add row to the summary table
        summary_table.add_row(
            source,
            f"{source_stats['total_records']:,}",
            str(source_stats["total_gaps"]),
            str(source_stats["day_boundary_gaps"]),
            str(source_stats["non_boundary_gaps"]),
            source_stats["max_gap_duration"],
        )

        # Save detailed gap information
        for gap in gaps:
            gap_info = {
                "source": source,
                "start_time": gap.start_time.isoformat(),
                "end_time": gap.end_time.isoformat(),
                "duration_seconds": gap.duration.total_seconds(),
                "missing_points": gap.missing_points,
                "crosses_day_boundary": gap.crosses_day_boundary,
            }
            results["gaps"].append(gap_info)

    # Print the summary table
    console.print(summary_table)

    # Create a table for detailed gap information (limit to 20 gaps)
    if results["gaps"]:
        gap_table = Table(title="Detailed Gap Information (Top 20)")
        gap_table.add_column("Source", style="cyan")
        gap_table.add_column("Start Time", style="white")
        gap_table.add_column("End Time", style="white")
        gap_table.add_column("Duration", style="yellow", justify="right")
        gap_table.add_column("Missing", style="red", justify="right")
        gap_table.add_column("Day Boundary", style="green", justify="center")

        # Sort gaps by start_time
        sorted_gaps = sorted(results["gaps"], key=lambda x: x["start_time"])
        display_gaps = sorted_gaps[:20]

        for gap in display_gaps:
            duration_str = (
                f"{gap['duration_seconds'] // 60}m {gap['duration_seconds'] % 60}s"
            )
            gap_table.add_row(
                gap["source"],
                gap["start_time"].split("T")[0]
                + " "
                + gap["start_time"].split("T")[1].split("+")[0],
                gap["end_time"].split("T")[0]
                + " "
                + gap["end_time"].split("T")[1].split("+")[0],
                duration_str,
                str(gap["missing_points"]),
                "✓" if gap["crosses_day_boundary"] else "✗",
            )

        console.print(gap_table)

    # Save to JSON file
    output_dir = Path("./logs/real_data_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"gap_analysis_{timestamp}.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"[bold green]Gap analysis saved to {output_file}[/bold green]")


def main():
    """Main function for the real data diagnostics tool."""
    verify_project_root()

    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Real Market Data Diagnostics Tool")
    parser.add_argument(
        "--market", type=str, default="spot", help="Market type (spot, um, cm)"
    )
    parser.add_argument(
        "--symbol", type=str, default="BTCUSDT", help="Symbol (e.g., BTCUSDT)"
    )
    parser.add_argument(
        "--interval", type=str, default="1m", help="Interval (e.g., 1m, 5m)"
    )
    parser.add_argument("--days", type=int, default=3, help="Number of days to fetch")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache")
    parser.add_argument(
        "--clear-cache", action="store_true", help="Clear cache before fetching"
    )
    parser.add_argument(
        "--gap-threshold",
        type=float,
        default=0.3,
        help="Gap threshold (default: 0.3 = 30%%)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="DEBUG",
        help="Set the logging level (default: DEBUG)",
    )
    args = parser.parse_args()

    # Set the logging level based on the command line argument
    logger.setLevel(args.log_level)
    print(f"[bold cyan]Log level set to: {args.log_level}[/bold cyan]")

    # Fetch real market data
    df = fetch_real_market_data(
        market_type_str=args.market,
        symbol=args.symbol,
        interval_str=args.interval,
        days=args.days,
        use_cache=not args.no_cache,
        enforce_cache_clear=args.clear_cache,
    )

    if df is not None:
        # Analyze data continuity
        analyze_data_continuity(df)

        # Perform gap analysis
        perform_gap_analysis(df, args.interval, args.gap_threshold)

        # Save data to CSV for reference
        output_dir = Path("./logs/real_data_analysis")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = (
            output_dir
            / f"market_data_{args.market}_{args.symbol}_{args.interval}_{timestamp}.csv"
        )

        df.to_csv(csv_path, index=False)
        print(f"[bold green]Raw data saved to {csv_path}[/bold green]")


if __name__ == "__main__":
    main()
