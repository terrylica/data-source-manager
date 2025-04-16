#!/usr/bin/env python3
"""
Simple demonstration of synchronous data retrieval using DataSourceManager.

This script shows how to retrieve 1-minute candlestick data for Bitcoin
in SPOT, USDT-margined futures (UM), or COIN-margined futures (CM) markets.
It also demonstrates data source merging capabilities across multiple sources:
1. Cache (for data already stored in local Arrow files)
2. VISION API (for historical data older than 48 hours)
3. REST API (for recent data within the last 48 hours)
"""

from datetime import datetime, timezone, timedelta
import pandas as pd
from pathlib import Path
import time
import os
import argparse
import sys
import importlib.util
import json

from utils.logger_setup import logger
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from utils.market_constraints import MarketType, Interval, DataProvider, ChartType
from utils.market_utils import get_market_type_str
from core.sync.data_source_manager import DataSourceManager, DataSource
from core.sync.cache_manager import UnifiedCacheManager
from utils.config import VISION_DATA_DELAY_HOURS
import demo_stats
from utils.gap_detector import detect_gaps

console = Console()

# We'll use this cache dir for all demos
CACHE_DIR = Path("./cache")

# Log timestamp at script initialization
logger.info(f"Script started at: {datetime.now(timezone.utc).isoformat()}")


def check_dependencies():
    """Check if required dependencies are installed."""
    # Check if matplotlib is installed (for statistics visualization)
    has_matplotlib = importlib.util.find_spec("matplotlib") is not None
    if not has_matplotlib:
        print(
            "[yellow]Warning: matplotlib is not installed. Statistics visualizations will not be available.[/yellow]"
        )
        print("You can install it using: pip install matplotlib")

    # Check if pandas is installed
    has_pandas = importlib.util.find_spec("pandas") is not None
    if not has_pandas:
        print(
            "[bold red]Error: pandas is not installed. This demo requires pandas.[/bold red]"
        )
        print("Please install it using: pip install pandas")
        sys.exit(1)

    # Check if rich is installed
    has_rich = importlib.util.find_spec("rich") is not None
    if not has_rich:
        print(
            "[bold red]Error: rich is not installed. This demo requires rich for formatting.[/bold red]"
        )
        print("Please install it using: pip install rich")
        sys.exit(1)


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


def show_help():
    """Display detailed help information."""
    console.print(
        Panel(
            "[bold green]Binance Real Data Diagnostics Tool[/bold green]",
            expand=False,
            border_style="green",
        )
    )

    print(
        "This script performs diagnostics on real market data retrieved directly from Binance APIs using DataSourceManager.\n"
    )

    print("[bold cyan]USAGE:[/bold cyan]")
    print("  python examples/dsm_sync_simple/demo.py [OPTIONS]")
    print(
        "  python examples/dsm_sync_simple/demo.py --market spot --symbol BTCUSDT --interval 1m --days 5\n"
    )

    print("[bold cyan]OPTIONS:[/bold cyan]")
    print("  -h, --help             Show this help message and exit")
    print("  --market               Market type: spot, um, or cm (default: spot)")
    print("  --symbol               Trading symbol (default: BTCUSDT)")
    print("  --interval             Time interval: 1m, 5m, etc. (default: 1m)")
    print("  --days                 Number of days to fetch (default: 3)")
    print("  --no-cache             Disable caching (cache is enabled by default)")
    print("  --clear-cache          Clear cache before fetching")
    print(
        "  --gap-threshold        Gap threshold as percentage above expected interval (default: 0.3 = 30%)"
    )
    print(
        "  --log-level            Set logging verbosity: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: DEBUG)"
    )
    print("\n")

    print("[bold cyan]EXAMPLES:[/bold cyan]")
    print(
        "  [yellow]python examples/dsm_sync_simple/demo.py[/yellow]                            # Run with default settings"
    )
    print(
        "  [yellow]python examples/dsm_sync_simple/demo.py --market spot --symbol ETHUSDT[/yellow]   # Run diagnostics for ETH in SPOT market"
    )
    print(
        "  [yellow]python examples/dsm_sync_simple/demo.py --interval 5m --days 7[/yellow]            # Analyze 5-minute data for last 7 days"
    )
    print(
        "  [yellow]python examples/dsm_sync_simple/demo.py --no-cache --clear-cache[/yellow]         # Run without cache and clear existing cache"
    )
    print(
        "  [yellow]python examples/dsm_sync_simple/demo.py --gap-threshold 0.5[/yellow]              # Use higher threshold (50%) for gap detection"
    )
    print(
        "  [yellow]python examples/dsm_sync_simple/demo.py --log-level INFO[/yellow]                 # Set less verbose logging with INFO level"
    )


def get_data_sync(
    market_type: MarketType,
    symbol: str,
    start_time: datetime,
    end_time: datetime,
    interval: Interval = Interval.MINUTE_1,
    provider: DataProvider = DataProvider.BINANCE,
    chart_type: ChartType = ChartType.KLINES,
    use_cache: bool = False,
    show_cache_path: bool = False,
    max_retries: int = 3,
    retry_delay: int = 1,
    enforce_source: DataSource = DataSource.AUTO,
):
    """
    Retrieve data synchronously using DataSourceManager.

    This function demonstrates the proper use of the synchronous DataSourceManager
    to retrieve market data with appropriate caching.

    Args:
        market_type: Market type (SPOT, FUTURES_USDT, FUTURES_COIN)
        symbol: Symbol to retrieve data for (e.g., "BTCUSDT")
        start_time: Start time for data retrieval
        end_time: End time for data retrieval
        interval: Time interval between data points
        provider: Data provider (currently only BINANCE is supported)
        chart_type: Type of chart data to retrieve (KLINES, FUNDING_RATE)
        use_cache: Whether to use caching
        show_cache_path: Whether to show the cache path
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        enforce_source: Force specific data source (AUTO, REST, VISION)

    Returns:
        Pandas DataFrame containing the retrieved data
    """
    logger.info(
        f"Retrieving {interval.value} {chart_type.name} data for {symbol} in {market_type.name} market using {provider.name}"
    )
    logger.info(f"Time range: {start_time.isoformat()} to {end_time.isoformat()}")
    logger.info(f"Cache enabled: {use_cache}")
    if enforce_source != DataSource.AUTO:
        logger.info(f"Enforcing data source: {enforce_source.name}")

    # If cache path display is requested
    if show_cache_path and use_cache:
        cache_dir = Path("./cache")
        # Create an instance of UnifiedCacheManager to get the cache path
        cache_manager = UnifiedCacheManager(cache_dir=cache_dir)
        market_type_str = get_market_type_str(market_type)

        cache_key = cache_manager.get_cache_key(
            symbol=symbol,
            interval=interval.value,
            date=start_time,
            provider=provider.name,
            chart_type=chart_type.name,
            market_type=market_type_str,
        )
        cache_path = cache_manager._get_cache_path(cache_key)

        print(f"[bold cyan]Cache path:[/bold cyan] {cache_path}")
        if os.path.exists(cache_path):
            print(
                f"[bold green]Cache file exists![/bold green] Size: {os.path.getsize(cache_path)/1024:.2f} KB"
            )
        else:
            print(
                f"[bold yellow]Cache file does not exist yet[/bold yellow] (will be created if cache enabled)"
            )

    start_time_retrieval = time.time()

    # Create a DataSourceManager instance with the specified parameters
    # Use context manager for proper resource management
    with DataSourceManager(
        market_type=market_type,
        provider=provider,
        chart_type=chart_type,
        use_cache=use_cache,
        retry_count=max_retries,
    ) as manager:
        # Retrieve data using the manager
        # The manager will handle the priority: cache → Vision API → REST API
        df = manager.get_data(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            interval=interval,
            chart_type=chart_type,
        )

    elapsed_time = time.time() - start_time_retrieval

    if df is None or df.empty:
        logger.warning(f"No data retrieved for {symbol}")
        return pd.DataFrame()

    logger.info(
        f"Retrieved {len(df)} records for {symbol} in {elapsed_time:.2f} seconds"
    )
    return df


def get_historical_data_test(
    market_type: MarketType,
    symbol: str = "BTCUSDT",
    interval: Interval = Interval.MINUTE_1,
    provider: DataProvider = DataProvider.BINANCE,
    chart_type: ChartType = ChartType.KLINES,
    use_cache: bool = True,
    show_cache_path: bool = False,
    max_retries: int = 3,
    debug: bool = False,
    enforce_source: DataSource = DataSource.AUTO,
):
    """
    Run a long-term historical data test for DataSourceManager orchestration.

    This test retrieves data from Dec 24, 2024 12:09:03 to Feb 25, 2025 23:56:56
    and demonstrates the Failover Control Protocol (FCP) strategy of the orchestrator.

    Args:
        market_type: Market type (SPOT, FUTURES_USDT, FUTURES_COIN)
        symbol: Symbol to retrieve data for (defaults to "BTCUSDT")
        interval: Time interval between data points (defaults to 1 minute)
        provider: Data provider (currently only BINANCE is supported)
        chart_type: Type of chart data to retrieve (KLINES, FUNDING_RATE)
        use_cache: Whether to use caching
        show_cache_path: Whether to show the cache path
        max_retries: Maximum number of retry attempts
        debug: Whether to enable additional debug output
        enforce_source: Force specific data source (AUTO, REST, VISION)

    Returns:
        Pandas DataFrame containing the retrieved data
    """
    # Define the precise time range as specified in the request
    # Today is April 11, 2025, so these dates are in the past
    start_time = datetime(2024, 12, 24, 12, 15, 3, tzinfo=timezone.utc)
    end_time = datetime(2025, 2, 25, 23, 56, 56, tzinfo=timezone.utc)

    logger.info("Running long-term historical data test")
    logger.info(f"Today's date: April 11, 2025")
    logger.info(f"Using date range: {start_time.isoformat()} to {end_time.isoformat()}")
    logger.info(
        f"Market: {market_type.name} | Symbol: {symbol} | Chart Type: {chart_type.name} | Interval: {interval.value}"
    )
    logger.info(
        f"Total duration: {(end_time - start_time).days} days, {(end_time - start_time).seconds // 3600} hours"
    )
    if enforce_source != DataSource.AUTO:
        logger.info(f"Enforcing data source: {enforce_source.name}")

    # Adjust symbol for CM (Coin-Margined Futures) market if needed
    if market_type == MarketType.FUTURES_COIN and symbol == "BTCUSDT":
        symbol = "BTCUSD_PERP"
        print(f"[yellow]Adjusted symbol for CM market: {symbol}[/yellow]")

    # If cache path display is requested
    if show_cache_path and use_cache:
        cache_dir = Path("./cache")
        # Create an instance of UnifiedCacheManager to get the cache path
        cache_manager = UnifiedCacheManager(cache_dir=cache_dir)
        market_type_str = get_market_type_str(market_type)

        # Display expected cache paths for a few sample dates throughout the range
        sample_dates = [
            start_time,
            datetime(2025, 1, 8, 0, 0, 0, tzinfo=timezone.utc),  # Early January
            datetime(2025, 1, 23, 0, 0, 0, tzinfo=timezone.utc),  # Late January
            datetime(2025, 2, 10, 0, 0, 0, tzinfo=timezone.utc),  # Early February
            end_time,
        ]

        print(f"[bold cyan]Sample cache paths for historical data:[/bold cyan]")
        for date in sample_dates:
            cache_key = cache_manager.get_cache_key(
                symbol=symbol,
                interval=interval.value,
                date=date,
                provider=provider.name,
                chart_type=chart_type.name,
                market_type=market_type_str,
            )
            cache_path = cache_manager._get_cache_path(cache_key)
            print(f"[cyan]Cache path for {date.date()}:[/cyan] {cache_path}")
            if os.path.exists(cache_path):
                print(
                    f"[bold green]Cache file exists![/bold green] Size: {os.path.getsize(cache_path)/1024:.2f} KB"
                )
            else:
                print(
                    f"[bold yellow]Cache file does not exist yet[/bold yellow] (will be created if cache enabled)"
                )

    start_time_retrieval = time.time()

    # Create a DataSourceManager instance with the specified parameters
    # Use context manager for proper resource management
    with DataSourceManager(
        market_type=market_type,
        provider=provider,
        chart_type=chart_type,
        use_cache=use_cache,
        retry_count=max_retries,
    ) as manager:
        # If debug mode is enabled, we'll fetch data in smaller chunks to better observe
        # the Failover Control Protocol (FCP) strategy at work
        if debug:
            print(
                "[bold yellow]Debug mode enabled - fetching data in multiple chunks[/bold yellow]"
            )

            # Split the date range into multiple chunks (approximately weekly)
            date_ranges = []
            current_start = start_time

            while current_start < end_time:
                # Create a chunk of about 7 days or less for the last chunk
                current_end = min(current_start + timedelta(days=7), end_time)
                date_ranges.append((current_start, current_end))
                current_start = current_end

            all_dfs = []

            for i, (chunk_start, chunk_end) in enumerate(date_ranges):
                print(
                    f"[cyan]Fetching chunk {i+1}/{len(date_ranges)}: {chunk_start.date()} to {chunk_end.date()}[/cyan]"
                )

                chunk_start_time = time.time()
                chunk_df = manager.get_data(
                    symbol=symbol,
                    start_time=chunk_start,
                    end_time=chunk_end,
                    interval=interval,
                    chart_type=chart_type,
                    enforce_source=enforce_source,
                )
                chunk_time = time.time() - chunk_start_time

                if chunk_df is not None and not chunk_df.empty:
                    # Count data source breakdown
                    if "_data_source" in chunk_df.columns:
                        source_counts = chunk_df["_data_source"].value_counts()
                        print(f"Data source breakdown: {source_counts.to_dict()}")

                    print(
                        f"Retrieved {len(chunk_df)} records in {chunk_time:.2f} seconds"
                    )
                    all_dfs.append(chunk_df)
                else:
                    print(f"[bold red]No data retrieved for chunk {i+1}[/bold red]")

            # Concatenate all DataFrames and sort by open_time
            if all_dfs:
                df = pd.concat(all_dfs)
                df = df.sort_values("open_time").reset_index(drop=True)
            else:
                df = pd.DataFrame()
        else:
            # Retrieve data in a single call for the entire range
            df = manager.get_data(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time,
                interval=interval,
                chart_type=chart_type,
                enforce_source=enforce_source,
            )

    elapsed_time = time.time() - start_time_retrieval

    if df is None or df.empty:
        logger.warning(f"No data retrieved for {symbol}")
        print("[bold red]No data retrieved for the specified time range[/bold red]")
        return pd.DataFrame()

    logger.info(
        f"Retrieved {len(df)} records for {symbol} in {elapsed_time:.2f} seconds"
    )

    # Print source breakdown
    if "_data_source" in df.columns:
        source_counts = df["_data_source"].value_counts()
        print(f"\n[bold cyan]Data Source Breakdown:[/bold cyan]")
        for source, count in source_counts.items():
            print(f"{source}: {count} records ({count/len(df)*100:.1f}%)")

        # Get sample data from each actual source
        print(f"\n[bold yellow]Sample Data By Actual Source:[/bold yellow]")
        for source in source_counts.index:
            print(f"\n[bold green]Records from {source} source:[/bold green]")
            source_data = df[df["_data_source"] == source].head(3)
            print(source_data)
    else:
        print(
            f"\n[bold red]WARNING: DataFrame doesn't have a _data_source column![/bold red]"
        )
        print(
            f"Cannot determine actual data sources - falling back to time-based analysis only."
        )

    # For comparison, also show time-based range analysis
    print(
        f"\n[bold cyan]Time Range-Based Analysis (may not match actual sources):[/bold cyan]"
    )
    print(f"Note: This is based on time ranges, not actual data sources")

    # Create masks for each range
    cache_mask = (df.index >= start_time) & (df.index <= end_time)

    # Count records in each range
    cache_count = cache_mask.sum()
    other_count = len(df) - cache_count

    print(f"Cache time range records: {cache_count}")
    print(f"Other time range records: {other_count}")
    print(f"Total records: {len(df)}")

    # NEW: Display detailed statistics using our demo_stats module
    demo_stats.display_detailed_stats(
        df=df,
        cache_range=(start_time, end_time),
        vision_range=(start_time, end_time),
        rest_range=(start_time, end_time),
        symbol=symbol,
        market_type=market_type.name,
        interval=interval.value,
        chart_type=chart_type.name,
        save_to_file=True,
    )

    return df


def analyze_merged_data(
    df: pd.DataFrame,
    cache_range: tuple,
    vision_range: tuple,
    rest_range: tuple,
    symbol: str = "BTCUSDT",
    market_type: str = "SPOT",
    interval: str = "1m",
    chart_type: str = "KLINES",
    gap_report: bool = False,
    gap_threshold: float = 0.3,
):
    """Analyze the merged data to show which parts came from which source.

    Args:
        df: DataFrame with merged data
        cache_range: Tuple of (start_time, end_time) for cache data
        vision_range: Tuple of (start_time, end_time) for Vision API data
        rest_range: Tuple of (start_time, end_time) for REST API data
        symbol: Symbol that was analyzed (default: BTCUSDT)
        market_type: Market type that was analyzed (default: SPOT)
        interval: Interval that was analyzed (default: 1m)
        chart_type: Chart type that was analyzed (default: KLINES)
        gap_report: Whether to generate a gap analysis report (default: False)
        gap_threshold: Threshold for gap detection (default: 0.3 = 30%)
    """
    cache_start, cache_end = cache_range
    vision_start, vision_end = vision_range
    rest_start, rest_end = rest_range

    # Ensure the index is properly set
    if df.index.name != "open_time":
        # If index is not properly set, try to use the open_time column
        if "open_time" in df.columns:
            df = df.set_index("open_time")
        else:
            print(
                "[bold red]ERROR: DataFrame doesn't have an open_time index or column![/bold red]"
            )
            return

    # First, show the true data source breakdown based on the _data_source column
    if "_data_source" in df.columns:
        source_counts = df["_data_source"].value_counts()
        print(
            f"\n[bold cyan]Actual Data Source Breakdown (from _data_source column):[/bold cyan]"
        )
        for source, count in source_counts.items():
            print(f"{source}: {count} records ({count/len(df)*100:.1f}%)")

        # Get sample data from each actual source
        print(f"\n[bold yellow]Sample Data By Actual Source:[/bold yellow]")
        for source in source_counts.index:
            print(f"\n[bold green]Records from {source} source:[/bold green]")
            source_data = df[df["_data_source"] == source].head(3)
            print(source_data)
    else:
        print(
            f"\n[bold red]WARNING: DataFrame doesn't have a _data_source column![/bold red]"
        )
        print(
            f"Cannot determine actual data sources - falling back to time-based analysis only."
        )

    # For comparison, also show time-based range analysis
    print(
        f"\n[bold cyan]Time Range-Based Analysis (may not match actual sources):[/bold cyan]"
    )
    print(f"Note: This is based on time ranges, not actual data sources")

    # Create masks for each range
    cache_mask = (df.index >= cache_start) & (df.index <= cache_end)
    vision_mask = (df.index >= vision_start) & (df.index <= vision_end)
    rest_mask = (df.index >= rest_start) & (df.index <= rest_end)

    # Count records in each range
    cache_count = cache_mask.sum()
    vision_count = vision_mask.sum()
    rest_count = rest_mask.sum()
    other_count = len(df) - cache_count - vision_count - rest_count

    print(f"Cache time range records: {cache_count}")
    print(f"Vision API time range records: {vision_count}")
    print(f"REST API time range records: {rest_count}")
    print(f"Other time range records: {other_count}")
    print(f"Total records: {len(df)}")

    # NEW: Display detailed statistics using our demo_stats module
    demo_stats.display_detailed_stats(
        df=df,
        cache_range=cache_range,
        vision_range=vision_range,
        rest_range=rest_range,
        symbol=symbol,
        market_type=market_type,
        interval=interval,
        chart_type=chart_type,
        save_to_file=True,
    )

    # NEW: Generate gap analysis report if requested
    if gap_report:
        generate_gap_report(
            df=df,
            symbol=symbol,
            market_type=market_type,
            interval=interval,
            chart_type=chart_type,
            gap_threshold=gap_threshold,
        )


def generate_gap_report(
    df: pd.DataFrame,
    symbol: str,
    market_type: str,
    interval: str,
    chart_type: str,
    gap_threshold: float = 0.3,
):
    """Generate a detailed gap analysis report.

    Args:
        df: DataFrame with market data
        symbol: Trading symbol
        market_type: Market type string
        interval: Interval string
        chart_type: Chart type string
        gap_threshold: Threshold for gap detection (default: 0.3 = 30%)
    """
    # Convert interval string to Interval enum
    try:
        interval_enum = Interval(interval)
    except ValueError:
        print(f"[bold red]ERROR: Invalid interval: {interval}[/bold red]")
        return

    print(f"\n[bold cyan]Generating Gap Analysis Report[/bold cyan]")
    print(f"Symbol: {symbol}")
    print(f"Market Type: {market_type}")
    print(f"Interval: {interval}")
    print(f"Chart Type: {chart_type}")
    print(f"Gap Threshold: {gap_threshold:.1f} ({gap_threshold*100:.0f}%)")

    # DEBUG: Log the actual threshold value used for calculations
    expected_seconds = interval_enum.to_seconds()
    expected_interval = pd.Timedelta(seconds=expected_seconds)
    gap_interval_threshold = expected_interval * (1 + gap_threshold)

    # Apply the same gap threshold for day boundaries instead of the default 1.5
    day_boundary_threshold = gap_threshold  # Use the same threshold for day boundaries
    day_boundary_threshold_value = expected_interval * (1 + day_boundary_threshold)

    print(f"[bold magenta]DEBUG: Gap Detection Parameters[/bold magenta]")
    print(f"Expected interval: {expected_interval} ({expected_seconds} seconds)")
    print(
        f"Regular gap threshold: {gap_interval_threshold} ({expected_seconds * (1 + gap_threshold):.1f} seconds)"
    )
    print(
        f"Day boundary threshold: {day_boundary_threshold_value} ({expected_seconds * (1 + day_boundary_threshold):.1f} seconds)"
    )

    # Reset index if needed
    if df.index.name == "open_time":
        df_copy = df.reset_index()
    else:
        df_copy = df.copy()

    # Check if we have the open_time column
    if "open_time" not in df_copy.columns:
        print("[bold red]ERROR: DataFrame doesn't have an open_time column![/bold red]")
        return

    # Sort by open_time
    df_copy = df_copy.sort_values("open_time")

    # Split analysis by source if available
    if "_data_source" in df_copy.columns:
        sources = df_copy["_data_source"].unique().tolist()
        sources.append("COMBINED")  # Add combined analysis
    else:
        sources = ["COMBINED"]

    # Prepare result structure
    results = {
        "metadata": {
            "symbol": symbol,
            "market_type": market_type,
            "interval": interval,
            "chart_type": chart_type,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report_type": "gap_analysis",
        },
        "statistics": {
            "overall": {},
            "by_source": {},
        },
        "gaps": [],
    }

    # Analyze gaps for each source
    for source in sources:
        print(f"\n[bold cyan]Analyzing gaps for source: {source}[/bold cyan]")

        if source == "COMBINED":
            source_df = df_copy.copy()
        else:
            source_df = df_copy[df_copy["_data_source"] == source].copy()

        if len(source_df) < 2:
            print(
                f"[yellow]Not enough data points for source: {source} - skipping[/yellow]"
            )
            continue

        # Debug: Create sorted dataframe to analyze time differences before detecting gaps
        debug_df = source_df.sort_values("open_time").copy()
        debug_df["next_time"] = debug_df["open_time"].shift(-1)
        debug_df["time_diff"] = debug_df["next_time"] - debug_df["open_time"]
        debug_df["time_diff_seconds"] = debug_df["time_diff"].dt.total_seconds()
        debug_df["curr_date"] = debug_df["open_time"].dt.date
        debug_df["next_date"] = debug_df["next_time"].dt.date
        debug_df["crosses_day_boundary"] = (
            debug_df["curr_date"] != debug_df["next_date"]
        )

        # Debug: Calculate which transitions exceed thresholds
        debug_df["exceeds_regular_threshold"] = (~debug_df["crosses_day_boundary"]) & (
            debug_df["time_diff"] > gap_interval_threshold
        )
        debug_df["exceeds_day_boundary_threshold"] = debug_df[
            "crosses_day_boundary"
        ] & (debug_df["time_diff"] > day_boundary_threshold_value)
        debug_df["is_gap"] = (
            debug_df["exceeds_regular_threshold"]
            | debug_df["exceeds_day_boundary_threshold"]
        )

        # Print some statistics about potentially problematic time differences
        print(
            f"[bold magenta]DEBUG: Time Difference Analysis for {source}[/bold magenta]"
        )
        print(f"Total transitions: {len(debug_df) - 1}")
        print(f"Day boundary transitions: {debug_df['crosses_day_boundary'].sum()}")

        print(
            f"Regular transitions exceeding threshold ({gap_interval_threshold}): "
            f"{debug_df['exceeds_regular_threshold'].sum()}"
        )
        print(
            f"Day boundary transitions exceeding threshold ({day_boundary_threshold_value}): "
            f"{debug_df['exceeds_day_boundary_threshold'].sum()}"
        )

        # Show the largest time differences
        largest_diffs = debug_df.nlargest(5, "time_diff_seconds")
        if not largest_diffs.empty:
            print(
                f"\n[bold magenta]DEBUG: Top 5 largest time differences for {source}:[/bold magenta]"
            )
            for _, row in largest_diffs.iterrows():
                boundary_str = (
                    " [CROSSES DAY BOUNDARY]" if row["crosses_day_boundary"] else ""
                )
                gap_str = " [DETECTED AS GAP]" if row["is_gap"] else ""
                print(
                    f"From {row['open_time']} to {row['next_time']}: "
                    f"{row['time_diff']} ({row['time_diff_seconds']} seconds){boundary_str}{gap_str}"
                )

        # Detect gaps with custom day boundary threshold
        gaps, stats = detect_gaps(
            source_df,
            interval_enum,
            time_column="open_time",
            gap_threshold=gap_threshold,
            day_boundary_threshold=gap_threshold,  # Use the same threshold for day boundaries
            enforce_min_span=source != "COMBINED",  # Only enforce for combined analysis
        )

        # Detailed logging of each detected gap
        if gaps:
            print(
                f"\n[bold magenta]DEBUG: Detailed Analysis of {len(gaps)} Detected Gaps:[/bold magenta]"
            )
            for i, gap in enumerate(gaps):
                print(f"Gap {i+1}:")
                print(f"  Start time: {gap.start_time}")
                print(f"  End time: {gap.end_time}")
                print(
                    f"  Duration: {gap.duration} ({gap.duration.total_seconds()} seconds)"
                )
                print(f"  Missing points: {gap.missing_points}")
                print(f"  Crosses day boundary: {gap.crosses_day_boundary}")

                # Calculate gap ratio compared to expected interval
                gap_ratio = gap.duration.total_seconds() / expected_seconds
                print(f"  Gap ratio to expected interval: {gap_ratio:.2f}x")
                # Note: Both regular and day boundary gaps now use the same threshold
                print(f"  Threshold that triggered detection: {(1 + gap_threshold)}")
                print(
                    f"  Condition for detection: {gap_ratio:.2f} > {(1 + gap_threshold)}"
                )
                print("")

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

        # Display summary
        print(f"Total records: {stats['total_records']}")
        print(f"Total gaps: {stats['total_gaps']}")
        print(f"Day boundary gaps: {stats.get('day_boundary_gaps', 0)}")
        print(f"Non-boundary gaps: {stats.get('non_boundary_gaps', 0)}")
        print(f"Maximum gap duration: {stats.get('max_gap_duration', '0')}")

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

            # Display gap details (limit to first 10 gaps to avoid excessive output)
            if len(results["gaps"]) <= 10:
                if gap.crosses_day_boundary:
                    boundary_str = "[yellow](crosses day boundary)[/yellow]"
                else:
                    boundary_str = ""

                print(
                    f"Gap from {gap.start_time} to {gap.end_time}: "
                    f"{gap.duration} ({gap.missing_points} points) {boundary_str}"
                )

        if stats["total_gaps"] > 10:
            print(
                f"[yellow]... and {stats['total_gaps'] - 10} more gaps (omitted for brevity)[/yellow]"
            )

    # Save to JSON file
    output_dir = Path("./logs/gap_reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = (
        output_dir
        / f"gap_report_{market_type.lower()}_{symbol}_{interval}_{timestamp}.json"
    )

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[bold green]Gap analysis report saved to: {output_file}[/bold green]")

    # Display summary using rich tables if we have gaps
    if results["gaps"]:
        print(f"\n[bold cyan]Gap Analysis Summary Table:[/bold cyan]")

        # Create a table for overall statistics
        summary_table = Table(title="Gap Analysis Summary")
        summary_table.add_column("Source", style="cyan")
        summary_table.add_column("Records", style="green", justify="right")
        summary_table.add_column("Total Gaps", style="yellow", justify="right")
        summary_table.add_column("Day Boundary", style="yellow", justify="right")
        summary_table.add_column("Max Duration", style="red", justify="right")

        # Add row for overall stats
        overall = results["statistics"]["overall"]
        summary_table.add_row(
            "COMBINED",
            f"{overall['total_records']:,}",
            f"{overall['total_gaps']:,}",
            f"{overall['day_boundary_gaps']:,}",
            f"{overall['max_gap_duration']}",
        )

        # Add rows for each source
        for source, stats in results["statistics"]["by_source"].items():
            summary_table.add_row(
                source,
                f"{stats['total_records']:,}",
                f"{stats['total_gaps']:,}",
                f"{stats['day_boundary_gaps']:,}",
                f"{stats['max_gap_duration']}",
            )

        console.print(summary_table)

        # Create a table for detailed gap information (limit to 20 gaps)
        if len(results["gaps"]) > 0:
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
                    gap["start_time"],
                    gap["end_time"],
                    duration_str,
                    str(gap["missing_points"]),
                    "✓" if gap["crosses_day_boundary"] else "✗",
                )

            console.print(gap_table)

            if len(results["gaps"]) > 20:
                print(
                    f"[yellow]Showing 20 of {len(results['gaps'])} gaps. Full details available in the JSON report.[/yellow]"
                )


def demonstrate_data_source_merging(
    market_type: MarketType,
    symbol: str = "BTCUSDT",
    interval: Interval = Interval.MINUTE_1,
    provider: DataProvider = DataProvider.BINANCE,
    chart_type: ChartType = ChartType.KLINES,
    max_retries: int = 3,
    enforce_source: DataSource = DataSource.AUTO,
    gap_report: bool = False,
    gap_threshold: float = 0.3,
):
    """
    Demonstrate data source merging with DataSourceManager.

    This function shows how DataSourceManager retrieves and merges data from multiple sources:
    1. Cache (for data already stored in local Arrow files)
    2. VISION API (for historical data older than 48 hours)
    3. REST API (for recent data within the last 48 hours)

    It creates a scenario that spans multiple data sources and shows how they are
    seamlessly merged together based on the open_time index.

    Args:
        market_type: Market type (SPOT, FUTURES_USDT, FUTURES_COIN)
        symbol: Symbol to retrieve data for (defaults to "BTCUSDT")
        interval: Time interval between data points (defaults to 1 minute)
        provider: Data provider (currently only BINANCE is supported)
        chart_type: Type of chart data to retrieve (KLINES, FUNDING_RATE)
        max_retries: Maximum number of retry attempts
        enforce_source: Force specific data source (AUTO, REST, VISION)
        gap_report: Whether to generate a gap analysis report (default: False)
        gap_threshold: Threshold for gap detection (default: 0.3 = 30%)

    Returns:
        Pandas DataFrame containing the merged data
    """
    print(f"[bold green]Data Source Merging Demonstration[/bold green]")
    print(f"Market: {market_type.name}")
    print(f"Symbol: {symbol}")
    print(f"Interval: {interval.value}")
    print(f"Chart Type: {chart_type.name}")
    print(f"Data Provider: {provider.name}")
    print(f"Vision API delay hours: {VISION_DATA_DELAY_HOURS}")

    if enforce_source != DataSource.AUTO:
        print(
            f"[bold yellow]Enforcing data source: {enforce_source.name}[/bold yellow]"
        )

    # Set up test scenario with pre-cached data ranges
    ranges = setup_test_scenario(symbol, market_type, interval, chart_type)
    cache_range = ranges[0:2]
    vision_range = ranges[2:4]
    rest_range = ranges[4:6]

    # Fetch and merge data
    df = fetch_and_merge_data(
        symbol,
        market_type,
        interval,
        chart_type,
        provider,
        cache_range,
        vision_range,
        rest_range,
        max_retries,
        enforce_source,
    )

    # Analyze merged data with additional parameters for better reporting
    analyze_merged_data(
        df,
        cache_range,
        vision_range,
        rest_range,
        symbol=symbol,
        market_type=market_type.name,
        interval=interval.value,
        chart_type=chart_type.name,
        gap_report=gap_report,
        gap_threshold=gap_threshold,
    )

    return df


def setup_test_scenario(
    symbol: str, market_type: MarketType, interval: Interval, chart_type: ChartType
):
    """Set up test scenario for demonstrating data source merging.

    This function creates date ranges for demonstrating the DataSourceManager's
    ability to fetch and merge data from multiple sources. It uses real, continuous
    date ranges to avoid creating artificial gaps.

    Args:
        symbol: Symbol to set up test for
        market_type: Market type
        interval: Interval to set up test for
        chart_type: Type of chart data to retrieve (KLINES, FUNDING_RATE)

    Returns:
        Tuple of (cache_start, cache_end, vision_start, vision_end, rest_start, rest_end)
    """
    now = datetime.now(timezone.utc)

    # Create continuous time ranges that demonstrate different data sources

    # Range 1: Data that should be in cache (5-7 days old)
    cache_end = now - timedelta(days=5)
    cache_start = cache_end - timedelta(hours=4)  # 4 hour window

    # Range 2: Data that should come from Vision API
    # This connects directly to the first range to avoid gaps
    vision_start = cache_end
    vision_end = vision_start + timedelta(hours=6)  # 6 hour window

    # Range 3: Recent data that should come from REST API
    # This is more recent data, but we'll ensure it's continuous with the Vision range
    rest_start = now - timedelta(hours=24)  # Last 24 hours
    rest_end = now - timedelta(hours=1)  # Up to 1 hour ago

    print(f"[bold cyan]Setting up test scenario with 3 data sources[/bold cyan]")
    print(f"Cache data: {cache_start.isoformat()} to {cache_end.isoformat()}")
    print(f"Vision data: {vision_start.isoformat()} to {vision_end.isoformat()}")
    print(f"REST data: {rest_start.isoformat()} to {rest_end.isoformat()}")

    # Pre-cache the first range without clearing existing data
    print(f"\n[bold yellow]Pre-caching data for Range 1...[/bold yellow]")
    with DataSourceManager(
        market_type=market_type,
        provider=DataProvider.BINANCE,
        chart_type=chart_type,
        use_cache=True,  # Enable caching
        retry_count=3,
        cache_dir=CACHE_DIR,  # Explicitly set cache directory
    ) as manager:
        # Fetch and cache the first range
        df_cache = manager.get_data(
            symbol=symbol,
            start_time=cache_start,
            end_time=cache_end,
            interval=interval,
            chart_type=chart_type,
        )

        if df_cache is not None and len(df_cache) > 0:
            print(
                f"Pre-cached {len(df_cache)} records from {cache_start} to {cache_end}"
            )

            # Verify data is in the cache by checking for cache file
            cache_manager = UnifiedCacheManager(cache_dir=CACHE_DIR)
            market_type_str = get_market_type_str(market_type)

            # Print debug info
            print(f"[yellow]Verifying cache creation...[/yellow]")
            print(f"Cache directory: {CACHE_DIR}")
            print(f"Market type string: {market_type_str}")
            print(f"Symbol: {symbol}, Interval: {interval.value}")
            print(f"Date: {cache_start.date()}")
            print(
                f"Provider: {DataProvider.BINANCE.name}, Chart type: {chart_type.name}"
            )

            # Check if cache was created
            cache_key = cache_manager.get_cache_key(
                symbol=symbol,
                interval=interval.value,
                date=cache_start.date(),
                provider=DataProvider.BINANCE.name,
                chart_type=chart_type.name,
                market_type=market_type_str,
            )
            print(f"Generated cache key: {cache_key}")

            cache_path = cache_manager._get_cache_path(cache_key)
            print(f"Cache path: {cache_path}")

            # Check if the directory exists
            if os.path.exists(cache_path.parent):
                print(f"[green]Directory exists: {cache_path.parent}[/green]")
                print(f"Directory contents:")
                for f in os.listdir(cache_path.parent):
                    print(f"  - {f}")
            else:
                print(f"[red]Directory does not exist: {cache_path.parent}[/red]")

            if os.path.exists(cache_path):
                print(
                    f"[bold green]Cache file successfully created! Path: {cache_path}[/bold green]"
                )
                print(f"File size: {os.path.getsize(cache_path)} bytes")
            else:
                print(
                    f"[bold red]WARNING: Cache file was not created at {cache_path}[/bold red]"
                )
        else:
            print(f"[bold red]WARNING: Failed to pre-cache data for range 1[/bold red]")

    return (cache_start, cache_end, vision_start, vision_end, rest_start, rest_end)


def fetch_and_merge_data(
    symbol: str,
    market_type: MarketType,
    interval: Interval,
    chart_type: ChartType,
    provider: DataProvider,
    cache_range: tuple,
    vision_range: tuple,
    rest_range: tuple,
    max_retries: int,
    enforce_source: DataSource = DataSource.AUTO,
):
    """Fetch data from multiple ranges and merge them.

    Args:
        symbol: Symbol to fetch data for
        market_type: Market type
        interval: Time interval
        chart_type: Type of chart data to retrieve (KLINES, FUNDING_RATE)
        provider: Data provider
        cache_range: Tuple of (start_time, end_time) for cache data
        vision_range: Tuple of (start_time, end_time) for Vision API data
        rest_range: Tuple of (start_time, end_time) for REST API data
        max_retries: Maximum number of retry attempts
        enforce_source: Force specific data source (AUTO, REST, VISION)

    Returns:
        DataFrame with merged data
    """
    # Create a single time range that spans all three ranges
    overall_start = min(cache_range[0], vision_range[0], rest_range[0])
    overall_end = max(cache_range[1], vision_range[1], rest_range[1])

    print(f"\n[bold green]Fetching data across all ranges...[/bold green]")
    print(
        f"Overall time range: {overall_start.isoformat()} to {overall_end.isoformat()}"
    )

    if enforce_source != DataSource.AUTO:
        print(
            f"[bold yellow]Enforcing data source: {enforce_source.name}[/bold yellow]"
        )

    # Create DataSourceManager with cache enabled
    start_time = time.time()
    with DataSourceManager(
        market_type=market_type,
        provider=provider,
        chart_type=chart_type,
        use_cache=True,  # Enable caching
        retry_count=max_retries,
    ) as manager:
        # Fetch data from the entire range
        df = manager.get_data(
            symbol=symbol,
            start_time=overall_start,
            end_time=overall_end,
            interval=interval,
            chart_type=chart_type,
            enforce_source=enforce_source,
            include_source_info=True,  # Explicitly set to include source information
        )
    elapsed_time = time.time() - start_time

    print(f"Retrieved and merged {len(df)} records in {elapsed_time:.2f} seconds")

    # Column standardization is now handled by DataSourceManager internally

    return df


def main():
    """Run the demo."""
    # First check dependencies and verify project root
    check_dependencies()
    if not verify_project_root():
        sys.exit(1)

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Demonstrate DataSourceManager with Failover Control Protocol (FCP) for Binance data retrieval",
        add_help=False,  # We'll handle help display ourselves
    )

    # Add our custom help option
    parser.add_argument("-h", "--help", action="store_true", help="Show detailed help")

    # Special action modes - these are exclusive with each other
    action_group = parser.add_argument_group("Action modes")
    action_group.add_argument(
        "--cache-demo",
        action="store_true",
        help="Demonstrate cache behavior by running the data retrieval twice",
    )
    action_group.add_argument(
        "--historical-test",
        action="store_true",
        help="Run long-term historical data test with specific dates (Dec 2024-Feb 2025)",
    )
    action_group.add_argument(
        "--detailed-stats",
        action="store_true",
        help="Show detailed statistics after the run and save to JSON file",
    )
    action_group.add_argument(
        "--gap-report",
        action="store_true",
        help="Generate a detailed gap report identifying missing data points",
    )

    # Market type selection (explicitly list all options from MarketType enum)
    parser.add_argument(
        "--market",
        type=str,
        default=None,  # No default here to handle positional args
        choices=[
            "spot",
            "um",
            "futures_usdt",
            "cm",
            "futures_coin",
            "futures",
            "options",
        ],
        help="Market type: spot (SPOT), um/futures_usdt (USDT-margined futures), "
        + "cm/futures_coin (Coin-margined futures), futures (legacy), options (Options market)",
    )

    # Symbol selection
    parser.add_argument(
        "--symbol",
        type=str,
        default=None,  # No default here to handle positional args
        help="Trading symbol (e.g., BTCUSDT for spot/UM, BTCUSD_PERP for CM)",
    )

    # Interval selection (explicitly list all options from Interval enum)
    parser.add_argument(
        "--interval",
        type=str,
        default=None,  # No default here to handle positional args
        choices=[interval.value for interval in Interval],
        help="Time interval between data points",
    )

    # Chart type selection (explicitly list all options from ChartType enum)
    parser.add_argument(
        "--chart-type",
        type=str,
        default=None,  # No default here to handle positional args
        choices=["klines", "fundingRate"],
        help="Chart data type: klines (candlestick data), fundingRate (funding rate data for futures)",
    )

    # Data provider selection (explicitly list all options from DataProvider enum)
    parser.add_argument(
        "--provider",
        type=str,
        default="binance",
        choices=["binance", "tradestation"],
        help="Data provider (currently only binance is fully implemented)",
    )

    # Time range options (for legacy mode)
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of days to fetch (used for legacy mode only)",
    )

    # Cache options
    parser.add_argument(
        "--use-cache",
        action="store_true",
        help="Enable caching of retrieved data to local Arrow files",
    )

    parser.add_argument(
        "--show-cache", action="store_true", help="Show cache file paths and status"
    )

    # Retry options
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of retry attempts for API requests",
    )

    # Debug options
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode with additional output and chunked data retrieval",
    )

    # Add enforce_source parameter to the argument parser
    parser.add_argument(
        "--enforce-source",
        type=str,
        choices=["AUTO", "REST", "VISION"],
        default="AUTO",
        help="Force specific data source (default: AUTO - uses the optimal source)",
    )

    # Add a special gap_threshold parameter for gap reports
    parser.add_argument(
        "--gap-threshold",
        type=float,
        default=0.3,
        help="Gap threshold as a fraction above expected interval (default: 0.3 = 30%%)",
    )

    # Add log level parameter
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="DEBUG",
        help="Set the logging level (default: DEBUG)",
    )

    # Add positional arguments list (optional)
    parser.add_argument(
        "positional",
        nargs="*",
        help="Optional positional arguments: [market] [symbol] [interval] [chart_type]",
    )

    args = parser.parse_args()

    # Process help flag first
    if args.help:
        show_help()
        return

    # Handle positional arguments like demo.sh does
    positional_args = args.positional

    # Initialize with defaults
    market_str = "spot"
    symbol_str = "BTCUSDT"
    interval_str = "1m"
    chart_type_str = "klines"

    # Apply named arguments if specified
    if args.market:
        market_str = args.market
    if args.symbol:
        symbol_str = args.symbol
    if args.interval:
        interval_str = args.interval
    if args.chart_type:
        chart_type_str = args.chart_type

    # Override with positional arguments if provided
    if len(positional_args) >= 1:
        market_str = positional_args[0]
    if len(positional_args) >= 2:
        symbol_str = positional_args[1]
    if len(positional_args) >= 3:
        interval_str = positional_args[2]
    if len(positional_args) >= 4:
        chart_type_str = positional_args[3]

    # Set the logging level based on the command line argument
    logger.setLevel(args.log_level)
    print(f"[bold cyan]Log level set to: {args.log_level}[/bold cyan]")
    print(f"Current time when Script Started: {datetime.now(timezone.utc).isoformat()}")

    # Convert special mode parameters
    if args.cache_demo and len(positional_args) >= 1:
        market_str = positional_args[0]
        if len(positional_args) >= 2:
            symbol_str = positional_args[1]
        if len(positional_args) >= 3:
            interval_str = positional_args[2]
        if len(positional_args) >= 4:
            chart_type_str = positional_args[3]

    if args.historical_test and len(positional_args) >= 1:
        market_str = positional_args[0]
        if len(positional_args) >= 2:
            symbol_str = positional_args[1]
        if len(positional_args) >= 3:
            interval_str = positional_args[2]
        if len(positional_args) >= 4:
            chart_type_str = positional_args[3]

    if args.detailed_stats and len(positional_args) >= 1:
        market_str = positional_args[0]
        if len(positional_args) >= 2:
            symbol_str = positional_args[1]
        if len(positional_args) >= 3:
            interval_str = positional_args[2]
        if len(positional_args) >= 4:
            chart_type_str = positional_args[3]

    # Convert string arguments to enums
    try:
        market_type = MarketType.from_string(market_str)
    except ValueError:
        print(f"[bold red]Invalid market type: {market_str}[/bold red]")
        print(
            f"Valid market types: spot, um, futures_usdt, cm, futures_coin, futures, options"
        )
        return

    try:
        provider = DataProvider.from_string(args.provider)
    except ValueError:
        print(f"[bold red]Invalid provider: {args.provider}[/bold red]")
        print(f"Valid providers: binance, tradestation")
        return

    try:
        chart_type = ChartType.from_string(chart_type_str)
    except ValueError:
        print(f"[bold red]Invalid chart type: {chart_type_str}[/bold red]")
        print(f"Valid chart types: klines, fundingRate")
        return

    # Convert interval string to enum
    try:
        interval_enum = Interval(interval_str)
    except ValueError:
        print(f"[bold red]Invalid interval: {interval_str}[/bold red]")
        print(f"Valid intervals: {', '.join([i.value for i in Interval])}")
        return

    # Convert enforce_source string to enum
    if args.enforce_source == "AUTO":
        enforce_source = DataSource.AUTO
    elif args.enforce_source == "REST":
        enforce_source = DataSource.REST
    elif args.enforce_source == "VISION":
        enforce_source = DataSource.VISION
    else:
        enforce_source = DataSource.AUTO

    # Handle special action modes - these mirror the demo.sh behavior

    # Run cache demo if requested
    if args.cache_demo:
        print(
            f"[bold green]################################################[/bold green]"
        )
        print(f"[bold green]# Cache Performance Demonstration #[/bold green]")
        print(
            f"[bold green]################################################[/bold green]"
        )
        print(
            f"Demonstrating cache behavior for {market_str} market with {symbol_str}\n"
        )

        # First run - should fetch from the source
        print("\n[bold yellow]First run - fetching from source...[/bold yellow]")
        first_start = time.time()
        df_first = get_data_sync(
            market_type=market_type,
            symbol=symbol_str,
            start_time=datetime.now(timezone.utc) - timedelta(days=args.days),
            end_time=datetime.now(timezone.utc),
            interval=interval_enum,
            provider=provider,
            chart_type=chart_type,
            use_cache=True,
            show_cache_path=args.show_cache,
            max_retries=args.retries,
            enforce_source=enforce_source,
        )
        first_elapsed = time.time() - first_start

        # Second run - should use cache
        print("\n[bold yellow]Second run - should use cache...[/bold yellow]")
        second_start = time.time()
        df_second = get_data_sync(
            market_type=market_type,
            symbol=symbol_str,
            start_time=datetime.now(timezone.utc) - timedelta(days=args.days),
            end_time=datetime.now(timezone.utc),
            interval=interval_enum,
            provider=provider,
            chart_type=chart_type,
            use_cache=True,
            show_cache_path=args.show_cache,
            max_retries=args.retries,
            enforce_source=enforce_source,
        )
        second_elapsed = time.time() - second_start

        # Compare results
        print("\n[bold green]Results comparison:[/bold green]")
        print(
            f"First run (from source): {len(df_first)} records in {first_elapsed:.2f}s"
        )
        print(
            f"Second run (from cache): {len(df_second)} records in {second_elapsed:.2f}s"
        )
        print(
            f"Speed improvement: {(first_elapsed/second_elapsed):.1f}x faster with cache"
        )

        if not df_first.equals(df_second):
            print("[bold red]Warning: The two dataframes are not identical![/bold red]")
        else:
            print(
                "[bold green]Both dataframes are identical - cache is working perfectly![/bold green]"
            )

        return

    # Run historical data test if requested
    elif args.historical_test:
        print(
            f"[bold green]################################################[/bold green]"
        )
        print(f"[bold green]# Long-Term Historical Data Test Mode #[/bold green]")
        print(
            f"[bold green]################################################[/bold green]"
        )
        print(f"Running historical test for {market_str} market with {symbol_str}\n")

        df = get_historical_data_test(
            market_type=market_type,
            symbol=symbol_str,
            interval=interval_enum,
            provider=provider,
            chart_type=chart_type,
            use_cache=args.use_cache,
            show_cache_path=args.show_cache,
            max_retries=args.retries,
            debug=args.debug,
            enforce_source=enforce_source,
        )

        # Save data to CSV if retrieved successfully
        if df is not None and not df.empty:
            output_dir = Path("./logs/historical_tests")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create a filename with relevant info
            filename = f"{market_type.name.lower()}_{symbol_str}_{interval_str}_{chart_type.name.lower()}_historical_test.csv"
            output_path = output_dir / filename

            df.to_csv(output_path, index=False)
            print(f"[bold green]Saved {len(df)} records to {output_path}[/bold green]")

        return

    # Run detailed statistics mode if requested
    elif args.detailed_stats:
        print(
            f"\n[bold cyan]=================================================[/bold cyan]"
        )
        print(
            f"[bold cyan]Running Data Source Merge Demo with Detailed Stats[/bold cyan]"
        )
        print(
            f"[bold cyan]Market: {market_str} | Symbol: {symbol_str} | Interval: {interval_str} | Chart Type: {chart_type_str}[/bold cyan]"
        )
        print(
            f"[bold cyan]=================================================[/bold cyan]"
        )

        df = demonstrate_data_source_merging(
            market_type=market_type,
            symbol=symbol_str,
            interval=interval_enum,
            provider=provider,
            chart_type=chart_type,
            max_retries=args.retries,
            enforce_source=enforce_source,
            gap_report=args.gap_report,
            gap_threshold=args.gap_threshold,
        )

        # Additional detailed statistics would be automatically shown
        # in the demonstrate_data_source_merging function

        # Save data to CSV if retrieved successfully
        if df is not None and not df.empty:
            output_dir = Path("./logs/merge_tests")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create a filename with relevant info
            filename = f"{market_type.name.lower()}_{symbol_str}_{interval_str}_{chart_type.name.lower()}_merge_test.csv"
            output_path = output_dir / filename

            df.to_csv(output_path, index=False)
            print(f"[bold green]Saved {len(df)} records to {output_path}[/bold green]")

        return

    # NEW: Run gap report mode if requested
    elif args.gap_report:
        print(
            f"\n[bold cyan]=================================================[/bold cyan]"
        )
        print(
            f"[bold cyan]Running Data Source Merge Demo with Gap Analysis[/bold cyan]"
        )
        print(
            f"[bold cyan]Market: {market_str} | Symbol: {symbol_str} | Interval: {interval_str} | Chart Type: {chart_type_str}[/bold cyan]"
        )
        print(
            f"[bold cyan]=================================================[/bold cyan]"
        )

        df = demonstrate_data_source_merging(
            market_type=market_type,
            symbol=symbol_str,
            interval=interval_enum,
            provider=provider,
            chart_type=chart_type,
            max_retries=args.retries,
            enforce_source=enforce_source,
            gap_report=True,
            gap_threshold=args.gap_threshold,
        )

        # Additional gap analysis would be automatically shown
        # in the demonstrate_data_source_merging function

        # Save data to CSV if retrieved successfully
        if df is not None and not df.empty:
            output_dir = Path("./logs/merge_tests")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create a filename with relevant info
            filename = f"{market_type.name.lower()}_{symbol_str}_{interval_str}_{chart_type.name.lower()}_merge_test.csv"
            output_path = output_dir / filename

            df.to_csv(output_path, index=False)
            print(f"[bold green]Saved {len(df)} records to {output_path}[/bold green]")

        return

    # Default behavior: run data source merge demo
    else:
        print(
            f"\n[bold cyan]=================================================[/bold cyan]"
        )
        print(f"[bold cyan]Running Data Source Merge Demo with FCP[/bold cyan]")
        print(
            f"[bold cyan]Market: {market_str} | Symbol: {symbol_str} | Interval: {interval_str} | Chart Type: {chart_type_str}[/bold cyan]"
        )
        print(
            f"[bold cyan]=================================================[/bold cyan]"
        )

        df = demonstrate_data_source_merging(
            market_type=market_type,
            symbol=symbol_str,
            interval=interval_enum,
            provider=provider,
            chart_type=chart_type,
            max_retries=args.retries,
            enforce_source=enforce_source,
            gap_report=args.gap_report,
            gap_threshold=args.gap_threshold,
        )

        # Save data to CSV if retrieved successfully
        if df is not None and not df.empty:
            output_dir = Path("./logs/merge_tests")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create a filename with relevant info
            filename = f"{market_type.name.lower()}_{symbol_str}_{interval_str}_{chart_type.name.lower()}_merge_test.csv"
            output_path = output_dir / filename

            df.to_csv(output_path, index=False)
            print(f"[bold green]Saved {len(df)} records to {output_path}[/bold green]")


if __name__ == "__main__":
    main()
