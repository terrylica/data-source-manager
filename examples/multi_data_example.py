#!/usr/bin/env python
"""Example of fetching multiple data types using the unified data source manager."""

import asyncio
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timezone, timedelta
from pathlib import Path

from utils.logger_setup import logger
from utils.market_constraints import MarketType, ChartType, Interval, DataProvider
from core.data_source_manager import DataSourceManager


async def fetch_klines_and_funding():
    """Fetch and display multiple data types for analysis."""
    # Create a temporary cache directory
    cache_dir = Path("tmp/multi_data_cache")
    cache_dir.mkdir(exist_ok=True, parents=True)

    logger.info("Creating DataSourceManager for unified data access")

    # Define time range (10 days ago until now)
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=10)
    symbol = "BTCUSDT"

    # Create a single DataSourceManager that can handle all data types
    async with DataSourceManager(
        market_type=MarketType.FUTURES_USDT,
        provider=DataProvider.BINANCE,
        cache_dir=cache_dir,
        use_cache=True,
    ) as dsm:
        # Fetch candlestick (klines) data
        logger.info(f"Fetching price data for {symbol}")
        klines_df = await dsm.get_data(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            chart_type=ChartType.KLINES,  # Explicitly specify chart type
        )

        # Fetch funding rate data
        logger.info(f"Fetching funding rate data for {symbol}")
        funding_df = await dsm.get_data(
            symbol=symbol,
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_8,
            chart_type=ChartType.FUNDING_RATE,  # Explicitly specify chart type
        )

        # Display info about the retrieved data
        if not klines_df.empty:
            logger.info(f"Retrieved {len(klines_df)} price data points")
            print("\nPrice Data Sample:")
            print(klines_df.head())
        else:
            logger.warning("No price data found")

        if not funding_df.empty:
            logger.info(f"Retrieved {len(funding_df)} funding rate data points")
            print("\nFunding Rate Data Sample:")
            print(funding_df.head())
        else:
            logger.warning("No funding rate data found")

        # If we have both datasets, perform analysis
        if not klines_df.empty and not funding_df.empty:
            # Create a visualization
            try:
                # Plot price
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

                # Plot price on top subplot
                ax1.plot(klines_df.index, klines_df["close"], label="Close Price")
                ax1.set_title(f"{symbol} Price and Funding Rate")
                ax1.set_ylabel("Price (USDT)")
                ax1.legend()
                ax1.grid(True)

                # Plot funding rate on bottom subplot
                ax2.plot(
                    funding_df.index,
                    funding_df["funding_rate"],
                    label="Funding Rate",
                    color="green",
                )
                ax2.axhline(y=0, color="r", linestyle="-", alpha=0.3)
                ax2.set_ylabel("Funding Rate")
                ax2.set_xlabel("Date")
                ax2.legend()
                ax2.grid(True)

                # Adjust layout and save
                plt.tight_layout()
                plt.savefig("tmp/btc_price_and_funding.png")
                logger.info("Saved visualization to tmp/btc_price_and_funding.png")

                # Calculate correlation
                # Resample funding rate to hourly to match price data
                hourly_funding = funding_df["funding_rate"].resample("1H").ffill()

                # Align the datasets
                aligned_data = pd.DataFrame(
                    {"price": klines_df["close"], "funding_rate": hourly_funding}
                ).dropna()

                correlation = aligned_data["price"].corr(aligned_data["funding_rate"])
                print(
                    f"\nCorrelation between price and funding rate: {correlation:.4f}"
                )

                # Find periods of extreme funding rates
                high_funding = funding_df[funding_df["funding_rate"] > 0.0005]  # 0.05%
                low_funding = funding_df[funding_df["funding_rate"] < -0.0005]  # -0.05%

                print(f"\nPeriods of high funding rates (>0.05%):")
                print(high_funding)

                print(f"\nPeriods of low funding rates (<-0.05%):")
                print(low_funding)

            except Exception as e:
                logger.error(f"Error creating visualization: {e}")

        # Get cache statistics
        if dsm.cache_manager:
            cache_stats = await dsm.cache_manager.get_cache_statistics()
            print("\nCache Statistics:")
            for key, value in cache_stats.items():
                if key not in ("symbols", "intervals"):  # These can be lengthy
                    print(f"{key}: {value}")


if __name__ == "__main__":
    asyncio.run(fetch_klines_and_funding())
