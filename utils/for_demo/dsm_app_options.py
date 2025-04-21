#!/usr/bin/env python3
"""
Application options for DSM Demo CLI applications.

This module contains Typer app options and argument definitions for DSM Demo CLI tools.
"""

from typing import Dict, Any
import typer
from enum import Enum

from utils.for_demo.dsm_cli_utils import (
    MarketTypeChoice,
    DataSourceChoice,
    ChartTypeChoice,
    LogLevel,
)


class DocFormatChoice(str, Enum):
    """Documentation format choices."""

    TYPER_CLI = "typer-cli"
    GITHUB = "github"
    CONSOLE = "console"


def create_typer_app(app_name="DSM Demo"):
    """Create a preconfigured Typer app with consistent styling and settings.

    Args:
        app_name: Name of the application

    Returns:
        typer.Typer: Configured Typer app
    """
    return typer.Typer(
        help=f"{app_name}: Demonstrate the Failover Control Protocol (FCP) mechanism",
        rich_markup_mode="rich",
        add_completion=False,
        context_settings={
            "help_option_names": ["-h", "--help"],
            "allow_extra_args": False,  # Don't allow unknown args
            "ignore_unknown_options": False,  # Error on unknown options
        },
        epilog="Use the -h or --help flag to see sample commands and examples.",
    )


def get_standard_options() -> Dict[str, Any]:
    """Get standard CLI options for DSM Demo applications.

    Returns:
        Dict: Dictionary of standard options with their default values
    """
    return {
        # Data Selection options
        "symbol": typer.Option(
            "BTCUSDT", "--symbol", "-s", help="Symbol to fetch data for"
        ),
        "market": typer.Option(
            MarketTypeChoice.SPOT,
            "--market",
            "-m",
            help="Market type (spot, um, cm)",
        ),
        "interval": typer.Option(
            "1m", "--interval", "-i", help="Time interval for klines/premiums"
        ),
        "chart_type": typer.Option(
            ChartTypeChoice.KLINES,
            "--chart-type",
            "-ct",
            help="Chart type (klines, premiums)",
        ),
        # Time Range options
        "start_time": typer.Option(
            None,
            "--start-time",
            "-st",
            help="Start time in ISO format (YYYY-MM-DDTHH:MM:SS) or YYYY-MM-DD. Can be used alone with --days to fetch forward, or with --end-time for exact range",
        ),
        "end_time": typer.Option(
            None,
            "--end-time",
            "-et",
            help="End time in ISO format (YYYY-MM-DDTHH:MM:SS) or YYYY-MM-DD. Can be used alone with --days to fetch backward, or with --start-time for exact range",
        ),
        "days": typer.Option(
            3,
            "--days",
            "-d",
            help="Number of days of data to fetch. If used with --end-time, fetches data backward from end time. If used with --start-time, fetches data forward from start time. If used alone, fetches data backward from current time",
        ),
        # Data Source options
        "enforce_source": typer.Option(
            DataSourceChoice.AUTO,
            "--enforce-source",
            "-es",
            help="Force specific data source (default: AUTO)",
        ),
        "retries": typer.Option(
            3, "--retries", "-r", help="Maximum number of retry attempts"
        ),
        # Cache Control options
        "no_cache": typer.Option(
            False,
            "--no-cache",
            "-nc",
            help="Disable caching (cache is enabled by default)",
        ),
        "clear_cache": typer.Option(
            False,
            "--clear-cache",
            "-cc",
            help="Clear the cache directory before running",
        ),
        # Documentation options
        "gen_doc": typer.Option(
            False,
            "--gen-doc",
            "-gd",
            help="Generate Markdown documentation from Typer help into docs/dsm_demo/ directory",
        ),
        "gen_lint_config": typer.Option(
            False,
            "--gen-lint-config",
            "-glc",
            help="Generate markdown linting configuration files along with documentation (only used with --gen-doc)",
        ),
        "doc_format": typer.Option(
            DocFormatChoice.TYPER_CLI,
            "--doc-format",
            "-df",
            help="Documentation format to use (typer-cli, github, console). typer-cli uses the official Typer CLI tool, github optimizes for GitHub display, console uses plain console output.",
        ),
        # Other options
        "log_level": typer.Option(
            LogLevel.INFO,
            "--log-level",
            "-l",
            help="Set the log level (default: INFO). Shorthand options: D=DEBUG, I=INFO, W=WARNING, E=ERROR, C=CRITICAL",
        ),
    }


def get_cmd_help_text():
    """Get a standardized help text for DSM Demo command.

    Returns:
        str: Help text for the command with examples
    """
    return """
    DSM Demo: Demonstrates the Failover Control Protocol (FCP) mechanism.

    This script shows how DataSourceManager automatically retrieves data from different sources:

    1. Cache (Local Arrow files)
    2. VISION API
    3. REST API

    It displays real-time source information about where each data point comes from.

    [bold cyan]Time Range Options:[/bold cyan]

    [green]1. End Time with Days:[/green]
      - Use --end-time with --days to fetch data backward from a specific end time
      - Calculates range as [end_time - days, end_time]
      - Example: --end-time 2025-04-15 --days 5 will fetch data from April 10-15, 2025

    [green]2. Start Time with Days:[/green]
      - Use --start-time with --days to fetch data forward from a specific start time
      - Calculates range as [start_time, start_time + days]
      - Example: --start-time 2025-04-10 --days 5 will fetch data from April 10-15, 2025

    [green]3. Exact Time Range:[/green]
      - Provide both --start-time and --end-time for an exact time range
      - Example: --start-time 2025-04-10 --end-time 2025-04-15

    [green]4. Days Only:[/green]
      - Use --days alone to fetch data relative to current time
      - Calculates range as [current_time - days, current_time]
      - Example: --days 5 will fetch data from 5 days ago until now

    [green]5. Default Behavior (No Options):[/green]
      - If no time options provided, uses default of 3 days from current time
      - Equivalent to --days 3

    [bold cyan]Sample Commands:[/bold cyan]

    [green]Basic Usage:[/green]
      ./examples/sync/dsm_demo.py
      ./examples/sync/dsm_demo.py --symbol ETHUSDT --market spot

    [green]Time Range Options:[/green]
      # End time with days (fetch backward from end time)
      ./examples/sync/dsm_demo.py -s BTCUSDT -et 2025-04-15 -d 7
      
      # Start time with days (fetch forward from start time)
      ./examples/sync/dsm_demo.py -s BTCUSDT -st 2025-04-05 -d 10
      
      # Exact time range (start time to end time)
      ./examples/sync/dsm_demo.py -s BTCUSDT -st 2025-04-05 -et 2025-04-15
      
      # Days only (fetch backward from current time)
      ./examples/sync/dsm_demo.py -s BTCUSDT -d 7
      
      # Default (3 days backward from current time)
      ./examples/sync/dsm_demo.py -s BTCUSDT

    [green]Market Types:[/green]
      ./examples/sync/dsm_demo.py -s BTCUSDT -m um
      ./examples/sync/dsm_demo.py -s BTCUSD_PERP -m cm

    [green]Different Intervals:[/green]
      ./examples/sync/dsm_demo.py -s BTCUSDT -i 5m
      ./examples/sync/dsm_demo.py -s BTCUSDT -i 1h
      ./examples/sync/dsm_demo.py -s SOLUSDT -m spot -i 1s  -cc -l D -st 2025-04-14T15:31:01 -et 2025-04-14T15:32:01

    [green]Data Source Options:[/green]
      ./examples/sync/dsm_demo.py -s BTCUSDT -es REST
      ./examples/sync/dsm_demo.py -s BTCUSDT -nc
      ./examples/sync/dsm_demo.py -s BTCUSDT -cc
      
    [green]Documentation Generation:[/green]
      # Generate documentation with typer-cli format (default)
      ./examples/sync/dsm_demo.py -gd
      
      # Generate GitHub-optimized documentation
      ./examples/sync/dsm_demo.py -gd -df github
      
      # Generate documentation with linting configuration files
      ./examples/sync/dsm_demo.py -gd -glc

    [green]Combined Examples:[/green]
      ./examples/sync/dsm_demo.py -s ETHUSDT -m um -i 15m -st 2025-04-01 -et 2025-04-10 -r 5 -l DEBUG
      ./examples/sync/dsm_demo.py -s ETHUSD_PERP -m cm -i 5m -d 10 -l D -cc
    """
