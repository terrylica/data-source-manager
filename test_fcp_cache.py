#!/usr/bin/env python3
"""
Test script for Failover Control Protocol (FCP) Mechanism.

This script tests the cache functionality of the DataSourceManager,
ensuring that the progressive data retrieval and merging properly works.
"""

from datetime import datetime, timezone, timedelta
import pandas as pd
import time
from pathlib import Path
import shutil
import typer
from typing import Optional
from typing_extensions import Annotated

from utils.logger_setup import logger
from rich import print

from utils.market_constraints import MarketType, Interval, DataProvider, ChartType
from core.sync.data_source_manager import DataSourceManager, DataSource

# Set up cache directory
CACHE_DIR = Path("./cache")


def verify_project_root():
    """Check if we're running from the project root directory."""
    import os

    if os.path.isdir("core") and os.path.isdir("utils"):
        print("[green]Running from project root directory[/green]")
        return True
    print(
        "[red]Not running from project root directory. Please cd to project root.[/red]"
    )
    return False


def test_fcp_cache(
    symbol: str = "BTCUSDT",
    interval_str: str = "1m",
    days: int = 3,
    verbose: bool = False,
    clear_cache_first: bool = True,
):
    """
    Test the FCP caching mechanism.

    Args:
        symbol: Trading symbol to test with (e.g. BTCUSDT)
        interval_str: Time interval (1m, 3m, 5m, etc.)
        days: Number of days to fetch
        verbose: Enable verbose debug logging
        clear_cache_first: Clear the cache before the first run
    """
    # Set log level based on verbose flag
    if verbose:
        logger.setLevel("DEBUG")
    else:
        logger.setLevel("INFO")

    # Check if we're in the right directory
    if not verify_project_root():
        return

    # Parse interval
    try:
        interval = Interval.from_string(interval_str)
    except ValueError:
        print(f"[red]Invalid interval: {interval_str}[/red]")
        return

    # Set up time range - use fixed dates for consistency
    end_time = datetime(2025, 4, 15, tzinfo=timezone.utc)
    start_time = end_time - timedelta(days=days)

    # Initialize market type
    market_type = MarketType.SPOT

    print(f"[bold blue]Test FCP Cache Mechanism[/bold blue]")
    print(f"Symbol: {symbol}")
    print(f"Interval: {interval.value}")
    print(f"Time range: {start_time.isoformat()} to {end_time.isoformat()}")

    # Clear cache if requested
    if clear_cache_first and CACHE_DIR.exists():
        print(f"[yellow]Clearing cache directory: {CACHE_DIR}[/yellow]")
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
        print(f"[green]Cache directory cleared[/green]")

    # STEP 1: First run - should populate cache
    print(
        "\n[bold]STEP 1: First run (should fetch from network and populate cache)[/bold]"
    )
    with DataSourceManager(
        market_type=market_type,
        provider=DataProvider.BINANCE,
        use_cache=True,
        cache_dir=CACHE_DIR,
        retry_count=3,
    ) as manager:
        print("[yellow]Running initial query to populate cache...[/yellow]")
        start_time_1 = time.time()
        df1 = manager.get_data(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            interval=interval,
            include_source_info=True,
        )
        elapsed_1 = time.time() - start_time_1

        # Display source info from the first run
        if not df1.empty and "_data_source" in df1.columns:
            source_counts = df1["_data_source"].value_counts()
            print(
                f"[green]Retrieved {len(df1)} records in {elapsed_1:.2f} seconds[/green]"
            )
            print("Source breakdown:")
            for source, count in source_counts.items():
                percentage = (count / len(df1)) * 100
                print(f"  {source}: {count} records ({percentage:.1f}%)")
        else:
            print(f"[red]No data retrieved or missing source information[/red]")

    # STEP 2: Second run - should use cache
    print("\n[bold]STEP 2: Second run (should fetch from cache)[/bold]")
    with DataSourceManager(
        market_type=market_type,
        provider=DataProvider.BINANCE,
        use_cache=True,
        cache_dir=CACHE_DIR,
        retry_count=3,
    ) as manager:
        print("[yellow]Running second query to test cache usage...[/yellow]")
        start_time_2 = time.time()
        df2 = manager.get_data(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            interval=interval,
            include_source_info=True,
        )
        elapsed_2 = time.time() - start_time_2

        # Display source info from the second run
        if not df2.empty and "_data_source" in df2.columns:
            source_counts = df2["_data_source"].value_counts()
            print(
                f"[green]Retrieved {len(df2)} records in {elapsed_2:.2f} seconds[/green]"
            )
            print("Source breakdown:")
            for source, count in source_counts.items():
                percentage = (count / len(df2)) * 100
                print(f"  {source}: {count} records ({percentage:.1f}%)")

            # Check if cache was used
            cache_count = source_counts.get("CACHE", 0)
            cache_percentage = (cache_count / len(df2)) * 100 if len(df2) > 0 else 0

            if cache_percentage > 90:
                print(
                    f"[bold green]SUCCESS: Cache was used for {cache_percentage:.1f}% of records[/bold green]"
                )
            elif cache_percentage > 0:
                print(
                    f"[bold yellow]PARTIAL: Cache was only used for {cache_percentage:.1f}% of records[/bold yellow]"
                )
            else:
                print(
                    f"[bold red]FAILURE: Cache was not used (0% from cache)[/bold red]"
                )

            # Compare timing
            if elapsed_2 < elapsed_1 * 0.5:
                print(
                    f"[green]Second run was {elapsed_1/elapsed_2:.1f}x faster (Good!)[/green]"
                )
            else:
                print(
                    f"[yellow]Second run timing: {elapsed_2:.2f}s vs first run: {elapsed_1:.2f}s[/yellow]"
                )
        else:
            print(f"[red]No data retrieved or missing source information[/red]")

    # STEP 3: Test partial cache hit (half overlapping time range)
    print("\n[bold]STEP 3: Partial cache test (half overlapping range)[/bold]")
    # Adjust time range to be half new, half from cache
    mid_point = start_time + (end_time - start_time) / 2
    new_start_time = mid_point - timedelta(days=days / 4)
    new_end_time = end_time + timedelta(days=days / 4)

    print(f"New time range: {new_start_time.isoformat()} to {new_end_time.isoformat()}")
    print(f"  Expected: ~50% from cache, ~50% from network")

    with DataSourceManager(
        market_type=market_type,
        provider=DataProvider.BINANCE,
        use_cache=True,
        cache_dir=CACHE_DIR,
        retry_count=3,
    ) as manager:
        print("[yellow]Running partial overlap query...[/yellow]")
        start_time_3 = time.time()
        df3 = manager.get_data(
            symbol=symbol,
            start_time=new_start_time,
            end_time=new_end_time,
            interval=interval,
            include_source_info=True,
        )
        elapsed_3 = time.time() - start_time_3

        # Display source info from the partial run
        if not df3.empty and "_data_source" in df3.columns:
            source_counts = df3["_data_source"].value_counts()
            print(
                f"[green]Retrieved {len(df3)} records in {elapsed_3:.2f} seconds[/green]"
            )
            print("Source breakdown:")
            for source, count in source_counts.items():
                percentage = (count / len(df3)) * 100
                print(f"  {source}: {count} records ({percentage:.1f}%)")

            # Verify we got a mix of cache and other sources
            cache_count = source_counts.get("CACHE", 0)
            if "VISION" in source_counts or "REST" in source_counts:
                print(
                    "[green]SUCCESS: Retrieved mix of cached and fresh data, as expected[/green]"
                )
            else:
                print(
                    "[yellow]Warning: Did not retrieve fresh data from network[/yellow]"
                )
        else:
            print(f"[red]No data retrieved or missing source information[/red]")

    # Summary
    print("\n[bold]Test Summary[/bold]")
    if not df1.empty and not df2.empty:
        print(f"Retrieval timing comparison:")
        print(f"  First run (no cache): {elapsed_1:.2f} seconds")
        print(f"  Second run (with cache): {elapsed_2:.2f} seconds")
        if elapsed_1 > 0 and elapsed_2 > 0:
            speedup = elapsed_1 / elapsed_2
            print(f"  Speedup factor: {speedup:.1f}x")
    print("\n[bold]Test completed.[/bold]")


def main(
    symbol: Annotated[
        str, typer.Option("--symbol", "-s", help="Trading symbol")
    ] = "BTCUSDT",
    interval: Annotated[
        str, typer.Option("--interval", "-i", help="Time interval")
    ] = "1m",
    days: Annotated[
        int, typer.Option("--days", "-d", help="Number of days to fetch")
    ] = 3,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
    clear_cache: Annotated[
        bool, typer.Option("--clear-cache", "-c", help="Clear cache before test")
    ] = True,
):
    """Test the FCP cache mechanism."""
    test_fcp_cache(symbol, interval, days, verbose, clear_cache)


if __name__ == "__main__":
    typer.run(main)
