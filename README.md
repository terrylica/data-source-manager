# Binance Data Service

A high-performance, robust package for efficient market data retrieval from multiple data providers, including Binance Vision, using Apache Arrow MMAP for optimal performance.

## Features

- **Multi-Provider Support**: Supports multiple data providers (currently Binance with TradeStation coming soon)
- **Multiple Chart Types**: Supports various chart types including KLines and Funding Rates
- **Zero-copy Reads**: Uses Apache Arrow memory-mapped files for efficient data access
- **Automatic Caching**: Intelligent caching system with provider and chart type awareness
- **Timezone-aware Timestamps**: All timestamps are UTC with proper timezone handling
- **Connection Limit Enforcement**: Built-in rate limiting to prevent API throttling
- **Data Validation**: Comprehensive validation of all data sources
- **Exponential Backoff**: Retry mechanism for transient failures
- **Factory Pattern**: Extensible architecture for adding new data providers and chart types

## Installation

```bash
pip install binance-data-service
```

## Basic Usage

```python
from datetime import datetime, timezone, timedelta
from pathlib import Path
from utils.market_constraints import Interval, MarketType, ChartType, DataProvider
from core.data_source_manager import DataSourceManager

# Set time range for data retrieval
end_time = datetime.now(timezone.utc)
start_time = end_time - timedelta(days=5)

async def basic_example():
    # Initialize DataSourceManager
    async with DataSourceManager(
        market_type=MarketType.SPOT,
        provider=DataProvider.BINANCE,
        chart_type=ChartType.KLINES,
        cache_dir=Path("./cache"),
    ) as dsm:
        # Fetch data
        df = await dsm.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
        )

        print(f"Retrieved {len(df)} records")
        print(df.head())
```

## Advanced Usage

### Fetching Funding Rate Data

```python
async def funding_rate_example():
    # Initialize DataSourceManager for funding rate data
    async with DataSourceManager(
        market_type=MarketType.FUTURES_USDT,
        provider=DataProvider.BINANCE,
        chart_type=ChartType.FUNDING_RATE,
        cache_dir=Path("./cache"),
    ) as dsm:
        # Fetch funding rate data
        df = await dsm.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_8,  # Funding rates typically use 8h interval
        )

        print(f"Retrieved {len(df)} funding rate records")
        print(df.head())
```

### Working with Multiple Data Types

```python
async def multi_data_example():
    # Create a DataSourceManager that can handle all data types
    async with DataSourceManager(
        market_type=MarketType.FUTURES_USDT,
        provider=DataProvider.BINANCE,
        cache_dir=Path("./cache"),
    ) as dsm:
        # Fetch price data
        klines_df = await dsm.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_1,
            chart_type=ChartType.KLINES,  # Explicitly specify chart type
        )

        # Fetch funding rate data from the same manager
        funding_df = await dsm.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_8,
            chart_type=ChartType.FUNDING_RATE,  # Explicitly specify chart type
        )

        print(f"Retrieved {len(klines_df)} kline records and {len(funding_df)} funding rate records")
```

## Performance Characteristics

- **Memory Efficiency**: Zero-copy reads minimize memory usage
- **High Throughput**: Arrow-based columnar storage optimizes data access patterns
- **Optimal Caching**: Hierarchical cache structure optimizes storage and retrieval

## API Reference

### DataSourceManager

```python
class DataSourceManager:
    def __init__(
        market_type: MarketType = MarketType.SPOT,
        provider: DataProvider = DataProvider.BINANCE,
        chart_type: ChartType = ChartType.KLINES,
        rest_client: Optional[RestDataClient] = None,
        cache_dir: Optional[Path] = None,
        use_cache: bool = True,
        max_concurrent: int = 50,
        retry_count: int = 5,
        max_concurrent_downloads: Optional[int] = None,
    )

    async def get_data(
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        interval: Interval = Interval.SECOND_1,
        use_cache: bool = True,
        enforce_source: DataSource = DataSource.AUTO,
        provider: Optional[DataProvider] = None,
        chart_type: Optional[ChartType] = None,
    ) -> pd.DataFrame
```

## Architecture

The system is built with a layered architecture:

1. **Mediator Layer**: `DataSourceManager` orchestrates data access across providers and chart types
2. **Client Factory Layer**: `DataClientFactory` creates appropriate clients for each provider/chart type combination
3. **Data Client Layer**: Implements provider-specific API access logic
4. **Cache Layer**: Efficiently stores retrieved data with provider and chart type awareness
5. **Time Handling Layer**: Manages timezone-aware timestamps

## Error Handling

The system provides comprehensive error handling:

- **ApiError**: Represents errors from data provider APIs
- **CacheError**: Represents errors in cache operations
- **ValidationError**: Represents data validation failures
- **RequestError**: Represents errors in HTTP requests

All errors are properly propagated and logged with detailed context.

## Data Integrity

Data integrity is maintained through:

1. **Boundary Validation**: Validates time boundaries for data consistency
2. **Schema Validation**: Ensures data structure matches expected schema
3. **Type Validation**: Validates data types for all columns
4. **Missing Data Detection**: Identifies and reports missing data points

## Extending the Framework

### Adding a New Data Provider

1. Add the provider to the `DataProvider` enum in `market_constraints.py`
2. Create a new client implementation that implements `DataClientInterface`
3. Register the client with the `DataClientFactory`

### Adding a New Chart Type

1. Add the chart type to the `ChartType` enum in `market_constraints.py`
2. Add appropriate column definitions and DTYPEs in `config.py`
3. Create a client implementation for the new chart type
4. Register the client with the `DataClientFactory`

## License

MIT
