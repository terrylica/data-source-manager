#!/usr/bin/env python3
"""
FCP Demo: Demonstrates the Failover Composition Priority (FCP) mechanism.

This script allows users to specify a time span and observe how the
DataSourceManager automatically retrieves data from different sources
following the Failover Composition Priority strategy:

1. Cache (Local Arrow files)
2. VISION API
3. REST API

It shows real-time source information about where each data point comes from,
and provides a summary of the data source breakdown.
"""

import argparse
from datetime import datetime, timezone, timedelta
import pandas as pd
from pathlib import Path
import time
import sys
import os

# Import the logger for logging and rich formatting
from utils.logger_setup import logger

# Set initial log level (will be overridden by command line args)
logger.setLevel("INFO")

# Rich components - import after enabling smart print
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from utils.market_constraints import MarketType, Interval, DataProvider, ChartType
from core.sync.data_source_manager import DataSourceManager, DataSource
from utils_for_debug.data_integrity import analyze_data_integrity
from utils_for_debug.dataframe_output import (
    log_dataframe_info,
    print_integrity_results,
    format_dataframe_for_display,
    save_dataframe_to_csv,
    print_no_data_message,
)


# We'll use this cache dir for all demos
CACHE_DIR = Path("./cache")


def verify_project_root():
    """Verify that we're running from the project root directory."""
    if os.path.isdir("core") and os.path.isdir("utils") and os.path.isdir("examples"):
        # Already in project root
        print("Running from project root directory")
        return True

    # Try to navigate to project root if we're in the example directory
    if os.path.isdir("../../core") and os.path.isdir("../../utils"):
        os.chdir("../..")
        print(f"Changed to project root directory: {os.getcwd()}")
        return True

    print("[bold red]Error: Unable to locate project root directory[/bold red]")
    print(
        "Please run this script from either the project root or the examples/dsm_sync_simple directory"
    )
    return False


def parse_datetime(dt_str):
    """Parse datetime string in ISO format or human readable format."""
    try:
        # Try ISO format first (YYYY-MM-DDTHH:MM:SS)
        return datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            # Try more flexible format (YYYY-MM-DD HH:MM:SS)
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            try:
                # Try date only format (YYYY-MM-DD)
                return datetime.strptime(dt_str, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                raise ValueError(
                    f"Unable to parse datetime: {dt_str}. Please use ISO format (YYYY-MM-DDTHH:MM:SS) or YYYY-MM-DD HH:MM:SS or YYYY-MM-DD"
                )


def fetch_data_with_fcp(
    market_type: MarketType,
    symbol: str,
    start_time: datetime,
    end_time: datetime,
    interval: Interval = Interval.MINUTE_1,
    provider: DataProvider = DataProvider.BINANCE,
    chart_type: ChartType = ChartType.KLINES,
    use_cache: bool = True,
    enforce_source: DataSource = DataSource.AUTO,
    max_retries: int = 3,
):
    """
    Fetch data using Failover Composition Priority (FCP) mechanism.

    Args:
        market_type: Market type (SPOT, FUTURES_USDT, FUTURES_COIN)
        symbol: Symbol to retrieve data for (e.g., "BTCUSDT")
        start_time: Start time for data retrieval
        end_time: End time for data retrieval
        interval: Time interval between data points
        provider: Data provider (currently only BINANCE is supported)
        chart_type: Type of chart data to retrieve (KLINES, FUNDING_RATE)
        use_cache: Whether to use caching
        enforce_source: Force specific data source (AUTO, REST, VISION)
        max_retries: Maximum number of retry attempts

    Returns:
        Pandas DataFrame containing the retrieved data
    """
    logger.info(
        f"Retrieving {interval.value} {chart_type.name} data for {symbol} in {market_type.name} market"
    )
    logger.info(f"Time range: {start_time.isoformat()} to {end_time.isoformat()}")
    logger.info(f"Cache enabled: {use_cache}")

    if enforce_source != DataSource.AUTO:
        logger.info(f"Enforcing data source: {enforce_source.name}")

    print(
        f"[bold yellow]Attempting to fetch data from {start_time.isoformat()} to {end_time.isoformat()}...[/bold yellow]"
    )

    # Calculate expected record count for validation
    interval_seconds = interval.to_seconds()
    expected_seconds = int((end_time - start_time).total_seconds())
    expected_records = (expected_seconds // interval_seconds) + 1
    logger.debug(
        f"Expected record count: {expected_records} for {expected_seconds} seconds range"
    )

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]Fetching data..."),
            transient=True,
        ) as progress:
            progress_task = progress.add_task("Fetching...", total=None)

            start_time_retrieval = time.time()

            # Create a DataSourceManager instance with the specified parameters
            with DataSourceManager(
                market_type=market_type,
                provider=provider,
                chart_type=chart_type,
                use_cache=use_cache,
                retry_count=max_retries,
            ) as manager:
                # Retrieve data using the manager
                # The manager will handle the FCP strategy: cache → Vision API → REST API
                df = manager.get_data(
                    symbol=symbol,
                    start_time=start_time,
                    end_time=end_time,
                    interval=interval,
                    chart_type=chart_type,
                    enforce_source=enforce_source,
                    include_source_info=True,  # Always include source information
                )

            elapsed_time = time.time() - start_time_retrieval
            progress.update(progress_task, completed=100)

        if df is None or df.empty:
            logger.warning(f"No data retrieved for {symbol}")
            print_no_data_message(
                symbol,
                market_type,
                interval,
                start_time,
                end_time,
                enforce_source,
                use_cache,
            )
            return pd.DataFrame()

        logger.info(
            f"Retrieved {len(df)} records for {symbol} in {elapsed_time:.2f} seconds"
        )

        # Analyze data integrity
        logger.debug("Analyzing data integrity...")
        integrity_result = analyze_data_integrity(df, start_time, end_time, interval)

        # Print the integrity results in a user-friendly format
        print_integrity_results(integrity_result)

        # Log DataFrame structure information for debugging
        log_dataframe_info(df)

        return df
    except Exception as e:
        print(f"[bold red]Error fetching data: {e}[/bold red]")
        import traceback

        traceback.print_exc()
        return pd.DataFrame()


def display_results(df, symbol, market_type, interval, chart_type):
    """Display the results of the FCP data retrieval."""
    if df is None or df.empty:
        print("[bold red]No data to display[/bold red]")
        return

    print(f"\n[bold green]Successfully retrieved {len(df)} records[/bold green]")

    # Create a table for source breakdown
    if "_data_source" in df.columns:
        source_counts = df["_data_source"].value_counts()

        source_table = Table(title="Data Source Breakdown")
        source_table.add_column("Source", style="cyan")
        source_table.add_column("Records", style="green", justify="right")
        source_table.add_column("Percentage", style="yellow", justify="right")

        for source, count in source_counts.items():
            percentage = count / len(df) * 100
            source_table.add_row(source, f"{count:,}", f"{percentage:.1f}%")

        print(source_table)

        # Show sample data from each source
        print(f"\n[bold cyan]Sample Data by Source:[/bold cyan]")
        for source in source_counts.index:
            source_df = df[df["_data_source"] == source].head(2)
            if not source_df.empty:
                print(f"\n[bold green]Records from {source} source:[/bold green]")
                # Format the display for better readability
                display_df = format_dataframe_for_display(source_df)
                # Display in a clean format
                print(display_df)
    else:
        print(
            "[bold yellow]Warning: Source information not available in the data[/bold yellow]"
        )

    # Save data to CSV
    csv_path = save_dataframe_to_csv(df, market_type, symbol, interval)
    if csv_path:
        print(f"\n[bold green]Data saved to: {csv_path}[/bold green]")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="FCP Demo: Demonstrate the Failover Composition Priority mechanism",
    )

    # Required arguments
    parser.add_argument(
        "--symbol", type=str, default="BTCUSDT", help="Trading symbol (e.g., BTCUSDT)"
    )

    parser.add_argument(
        "--market",
        type=str,
        default="spot",
        choices=["spot", "um", "cm", "futures_usdt", "futures_coin"],
        help="Market type: spot, um (USDT-M futures), cm (Coin-M futures)",
    )

    parser.add_argument(
        "--interval", type=str, default="1m", help="Time interval (e.g., 1m, 5m, 1h)"
    )

    # Time range arguments
    time_group = parser.add_argument_group("Time Range")
    time_group.add_argument(
        "--start-time",
        type=str,
        help="Start time in ISO format (YYYY-MM-DDTHH:MM:SS) or YYYY-MM-DD",
    )

    time_group.add_argument(
        "--end-time",
        type=str,
        help="End time in ISO format (YYYY-MM-DDTHH:MM:SS) or YYYY-MM-DD",
    )

    time_group.add_argument(
        "--days",
        type=int,
        default=3,
        help="Number of days to fetch (used if start-time and end-time not provided)",
    )

    # Cache options
    cache_group = parser.add_argument_group("Cache Options")
    cache_group.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching (cache is enabled by default)",
    )

    # Source options
    source_group = parser.add_argument_group("Source Options")
    source_group.add_argument(
        "--enforce-source",
        type=str,
        choices=["AUTO", "REST", "VISION"],
        default="AUTO",
        help="Force specific data source (default: AUTO)",
    )

    # Other options
    parser.add_argument(
        "--retries", type=int, default=3, help="Maximum number of retry attempts"
    )

    parser.add_argument(
        "--chart-type",
        type=str,
        choices=["klines", "fundingRate"],
        default="klines",
        help="Type of chart data",
    )

    # Add a log level option to demonstrate rich output control
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the log level (default: INFO)",
    )

    return parser.parse_args()


def main():
    """Run the FCP demo."""
    try:
        print(
            Panel(
                "[bold green]FCP Demo: Failover Composition Priority[/bold green]\n"
                "This script demonstrates how DataSourceManager automatically retrieves data\n"
                "from different sources using the Failover Composition Priority strategy:\n"
                "1. Cache (Local Arrow files)\n"
                "2. VISION API\n"
                "3. REST API",
                expand=False,
                border_style="green",
            )
        )

        # Verify project root
        if not verify_project_root():
            sys.exit(1)

        # Parse arguments
        args = parse_arguments()
        print(f"[bold cyan]Command line arguments:[/bold cyan] {args}")

        # Set the log level
        logger.setLevel(args.log_level)
        print(f"[bold cyan]Log level set to:[/bold cyan] {args.log_level}")

        # Validate and process arguments
        try:
            # Convert market type string to enum
            market_type = MarketType.from_string(args.market)

            # Convert interval string to enum
            interval = Interval(args.interval)

            # Convert chart type string to enum
            chart_type = ChartType.from_string(args.chart_type)

            # Determine time range
            if args.start_time and args.end_time:
                # Use specified time range
                start_time = parse_datetime(args.start_time)
                end_time = parse_datetime(args.end_time)
            else:
                # Use days parameter to calculate time range
                end_time = datetime.now(timezone.utc)
                start_time = end_time - timedelta(days=args.days)

            # Process caching option
            use_cache = not args.no_cache

            # Process enforce source option
            if args.enforce_source == "AUTO":
                enforce_source = DataSource.AUTO
            elif args.enforce_source == "REST":
                enforce_source = DataSource.REST
            elif args.enforce_source == "VISION":
                enforce_source = DataSource.VISION
            else:
                enforce_source = DataSource.AUTO

            # Adjust symbol for CM market if needed
            symbol = args.symbol
            if market_type == MarketType.FUTURES_COIN and symbol == "BTCUSDT":
                symbol = "BTCUSD_PERP"
                print(f"[yellow]Adjusted symbol for CM market: {symbol}[/yellow]")

            # Display configuration
            print(f"[bold cyan]Configuration:[/bold cyan]")
            print(f"Market type: {market_type.name}")
            print(f"Symbol: {symbol}")
            print(f"Interval: {interval.value}")
            print(f"Chart type: {chart_type.name}")
            print(f"Time range: {start_time.isoformat()} to {end_time.isoformat()}")
            print(f"Cache enabled: {use_cache}")
            print(f"Enforce source: {args.enforce_source}")
            print(f"Max retries: {args.retries}")
            print()

            # Fetch data using FCP
            df = fetch_data_with_fcp(
                market_type=market_type,
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                interval=interval,
                provider=DataProvider.BINANCE,
                chart_type=chart_type,
                use_cache=use_cache,
                enforce_source=enforce_source,
                max_retries=args.retries,
            )

            # Display results
            display_results(
                df,
                symbol,
                market_type.name.lower(),
                interval.value,
                chart_type.name.lower(),
            )

            # Add note about log level and rich output
            print(
                Panel(
                    "[bold cyan]Note about Log Level and Rich Output:[/bold cyan]\n"
                    "- When log level is DEBUG, INFO, or WARNING: Rich output is visible\n"
                    "- When log level is ERROR or CRITICAL: Rich output is suppressed\n\n"
                    "Try running with different log levels to see the difference:\n"
                    "  python examples/dsm_sync_simple/fcp_demo.py --log-level ERROR",
                    title="Rich Output Control",
                    border_style="blue",
                )
            )

        except ValueError as e:
            print(f"[bold red]Error: {e}[/bold red]")
            import traceback

            traceback.print_exc()
            sys.exit(1)
        except Exception as e:
            print(f"[bold red]Unexpected error: {e}[/bold red]")
            import traceback

            traceback.print_exc()
            sys.exit(1)
    except Exception as e:
        print(f"[bold red]CRITICAL ERROR: {e}[/bold red]")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
