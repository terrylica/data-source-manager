#!/usr/bin/env python3
"""
Backward From Date Demo: Demonstrates fetching data backward from a specified end date.

This script is a wrapper around dsm_demo.py that demonstrates how to fetch
data backward from a specific end date for a specified number of days.
"""

import sys
import typer
import pendulum

# Import needed for executing the dsm_demo.py script
import subprocess
from pathlib import Path
from utils.logger_setup import logger

# Add import
from core.sync.data_source_manager import DataSourceManager
from utils.market_constraints import Interval

app = typer.Typer(
    help="Demonstrates fetching data backward from a specified end date",
    rich_markup_mode="rich",
)


@app.command()
def main(
    symbol: str = typer.Option(
        "BTCUSDT", "-s", "--symbol", help="Symbol to fetch data for"
    ),
    days: int = typer.Option(
        5, "-d", "--days", help="Number of days to fetch backward from end date"
    ),
    end_date: str = typer.Option(
        None, "-e", "--end-date", help="End date in YYYY-MM-DD format"
    ),
    end_time: str = typer.Option(
        None,
        "-t",
        "--end-time",
        help="Optional time in HH:MM:SS format to append to end date",
    ),
    market: str = typer.Option(
        "spot", "-m", "--market", help="Market type (spot, um, cm)"
    ),
    interval: str = typer.Option(
        "1m", "-i", "--interval", help="Time interval for klines"
    ),
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="Show verbose output (uses DEBUG log level)"
    ),
):
    """Fetch data backward from a specific end date for a specified number of days."""
    # Set end date to today if not provided
    if not end_date:
        now = pendulum.now()
        end_date = now.format("YYYY-MM-DD")
        print(f"[yellow]No end date specified, using today: {end_date}[/yellow]")

    # Combine end date and time
    end_datetime = end_date
    if end_time:
        end_datetime = f"{end_date}T{end_time}"
    else:
        # Default to end of day if no time specified
        end_datetime = f"{end_date}T23:59:59"
        print(
            f"[yellow]No end time specified, using end of day: {end_datetime}[/yellow]"
        )

    # Calculate date range using core utility
    try:
        et = pendulum.parse(end_datetime)

        # Use the DataSourceManager utility to calculate the range
        start_dt, end_dt = DataSourceManager.calculate_time_range(
            start_time=None, end_time=et, days=days, interval=Interval(interval)
        )

        # Show the exact date range being used
        print(
            f"[bold cyan]Fetching {days} days of {interval} data for {symbol} from {market} market[/bold cyan]"
        )
        print(
            f"[bold cyan]Date range: {start_dt.format('YYYY-MM-DD HH:mm:ss')} to {end_dt.format('YYYY-MM-DD HH:mm:ss')}[/bold cyan]"
        )
    except Exception as e:
        print(f"[bold red]Error calculating date range: {e}[/bold red]")
        sys.exit(1)

    # Prepare the dsm_demo.py command
    script_path = Path(__file__).parent / "dsm_demo.py"
    if not script_path.exists():
        print(f"[bold red]Error: dsm_demo.py not found at {script_path}[/bold red]")
        sys.exit(1)

    # Build command arguments with the calculated date range
    cmd = [
        sys.executable,
        str(script_path),
        "-s",
        symbol,
        "-m",
        market,
        "-i",
        interval,
        "-et",
        end_dt.isoformat(),
        "-d",
        str(days),
        "-l",
        "DEBUG" if verbose else "INFO",
    ]

    print("\n[bold cyan]Executing dsm_demo.py...[/bold cyan]\n")

    # Execute the command
    subprocess.run(cmd)


if __name__ == "__main__":
    app()
