#!/usr/bin/env python

"""Raw Data Service package for efficient market data retrieval.

This package provides tools for downloading and caching market data from Binance Vision.
The primary interface is the VisionDataClient, which uses Apache Arrow MMAP for
optimal performance in data storage and retrieval.

Key Features:
- Efficient data retrieval using Apache Arrow MMAP
- Automatic caching with zero-copy reads
- Timezone-aware timestamp handling
- Column-based data access
- Concurrent download management
"""

from core.providers.binance.vision_data_client import VisionDataClient
from utils.dataframe_types import TimestampedDataFrame
from core.sync.dsm_lib import fetch_market_data
from core.sync.data_source_manager import DataSourceConfig, DataSource
from utils.market_constraints import MarketType, DataProvider, ChartType, Interval

__all__ = [
    "TimestampedDataFrame",
    "VisionDataClient",
    "fetch_market_data",
    "DataSourceConfig",
    "MarketType",
    "DataProvider",
    "ChartType",
    "Interval",
    "DataSource",
]
