#!/usr/bin/env python
"""Demonstration of the Vision API timestamp interpretation fix.

This script demonstrates how the VisionDataClient now correctly interprets
timestamps from the Binance Vision API, preserving the semantic meaning of
open_time as the START of each candle period.
"""

from datetime import datetime, timezone, timedelta
import pandas as pd
from rich import print
from rich.table import Table
from rich.console import Console
from rich.panel import Panel

from utils.logger_setup import logger
from utils.market_constraints import Interval, MarketType
from utils.config import KLINE_COLUMNS
from core.sync.vision_data_client import VisionDataClient


def create_demo_data():
    """Create sample data in the 2025 Vision API format (microsecond timestamps)."""
    # Sample data from March 15, 2025
    raw_data = [
        # First candle: 2025-03-15 00:00:00 - 00:00:59.999999
        [
            1741996800000000,
            83983.19,
            84052.93,
            83983.19,
            84045.49,
            21.71669,
            1741996859999999,
            1824732.53,
            2993,
            10.49778,
            881995.95,
            0,
        ],
        # Second candle: 2025-03-15 00:01:00 - 00:01:59.999999
        [
            1741996860000000,
            84045.49,
            84045.49,
            83964.57,
            83971.29,
            7.41994,
            1741996919999999,
            623260.91,
            1804,
            1.19858,
            100661.29,
            0,
        ],
        # Third candle: 2025-03-15 00:02:00 - 00:02:59.999999
        [
            1741996920000000,
            83971.29,
            83999.00,
            83971.29,
            83992.19,
            4.18731,
            1741996979999999,
            351644.10,
            1245,
            2.13368,
            179214.27,
            0,
        ],
    ]

    # Create DataFrame with column names
    return pd.DataFrame(raw_data, columns=KLINE_COLUMNS)


def demonstrate_timestamp_interpretation():
    """Demonstrate correct timestamp interpretation."""
    console = Console()

    console.print(
        Panel.fit(
            "[bold green]Vision API Timestamp Interpretation Demo[/bold green]\n"
            "Demonstrating the fixed timestamp interpretation in VisionDataClient"
        )
    )

    # Create demo data
    demo_df = create_demo_data()

    # Display raw timestamps
    raw_table = Table(title="Raw Timestamps from Vision API (2025 Format)")
    raw_table.add_column("Row", style="cyan")
    raw_table.add_column("open_time (microseconds)", style="green")
    raw_table.add_column("close_time (microseconds)", style="red")
    raw_table.add_column("Human-readable open_time", style="green")
    raw_table.add_column("Human-readable close_time", style="red")

    for i, row in demo_df.iterrows():
        raw_open = datetime.fromtimestamp(row["open_time"] / 1000000, tz=timezone.utc)
        raw_close = datetime.fromtimestamp(row["close_time"] / 1000000, tz=timezone.utc)
        raw_table.add_row(
            str(i + 1),
            str(row["open_time"]),
            str(row["close_time"]),
            raw_open.strftime("%Y-%m-%d %H:%M:%S.%f"),
            raw_close.strftime("%Y-%m-%d %H:%M:%S.%f"),
        )

    console.print(raw_table)
    console.print()

    # Process with VisionDataClient
    with VisionDataClient(
        symbol="BTCUSDT", interval="1m", market_type=MarketType.SPOT
    ) as client:
        # Process the timestamps
        processed_df = client._process_timestamp_columns(demo_df.copy())

        # Display processed timestamps
        processed_table = Table(title="Processed Timestamps (with Fix)")
        processed_table.add_column("Row", style="cyan")
        processed_table.add_column("open_time", style="green")
        processed_table.add_column("close_time", style="red")
        processed_table.add_column("Semantic Meaning", style="yellow")

        for i, row in processed_df.iterrows():
            processed_table.add_row(
                str(i + 1),
                row["open_time"].strftime("%Y-%m-%d %H:%M:%S.%f"),
                row["close_time"].strftime("%Y-%m-%d %H:%M:%S.%f"),
                f"Candle period {i+1} [green](START)[/green] → [red](END)[/red]",
            )

        console.print(processed_table)
        console.print()

        # Display key insights
        console.print(
            Panel.fit(
                "[bold yellow]Key Insights[/bold yellow]\n\n"
                "1. Raw timestamps from Vision API mark:\n"
                "   - [green]open_time[/green] as the [bold]BEGINNING[/bold] of each candle period\n"
                "   - [red]close_time[/red] as the [bold]END[/bold] of each candle period\n\n"
                "2. The fixed implementation preserves this semantic meaning, ensuring:\n"
                "   - Accurate time range representation\n"
                "   - No missing candles at period boundaries\n"
                "   - Consistent behavior across all interval types\n\n"
                "3. Example: A request for data from 00:00:00 to 00:02:59 will now correctly include\n"
                "   ALL three candles, instead of incorrectly shifting by one interval."
            )
        )

        # Demonstrate time filtering
        start_time = datetime(2025, 3, 15, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 3, 15, 0, 2, 59, 999999, tzinfo=timezone.utc)

        filtered_df = processed_df[
            (processed_df["open_time"] >= start_time)
            & (processed_df["open_time"] <= end_time)
        ]

        console.print(f"\n[bold cyan]Time filtering demonstration:[/bold cyan]")
        console.print(
            f"Requesting data from [green]{start_time}[/green] to [red]{end_time}[/red]"
        )
        console.print(
            f"Number of candles returned: [bold yellow]{len(filtered_df)}[/bold yellow]"
        )
        console.print(
            f"First candle open_time: [green]{filtered_df['open_time'].iloc[0]}[/green]"
        )
        console.print(
            f"Last candle open_time: [green]{filtered_df['open_time'].iloc[-1]}[/green]"
        )


if __name__ == "__main__":
    demonstrate_timestamp_interpretation()
