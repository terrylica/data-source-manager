# DataSourceManager Documentation

## Overview

The `DataSourceManager` serves as a mediator between different data sources across multiple providers. It provides intelligent source selection, caching, and fallback mechanisms to optimize data retrieval for various chart types.

### Core Responsibilities

1. Data source selection across multiple providers and chart types
2. Unified caching strategy across all data sources
3. Cache integrity validation and management
4. Data format standardization

### Module Location

```python
from data_source_manager.core.sync.data_source_manager import DataSourceManager, DataSource
from data_source_manager.utils.market_constraints import Interval, MarketType, ChartType, DataProvider
```

## System Architecture

### 1. Mediator Layer

#### Key Components

- `DataSource` Enum:
  - `AUTO`: Automatically select best source
  - `REST`: Force REST API usage
  - `VISION`: Force Vision API usage

- `DataProvider` Enum:
  - `BINANCE`: Binance data provider
  - `TRADESTATION`: TradeStation data provider

- `ChartType` Enum:
  - `KLINES`: Standard candlestick data
  - `FUNDING_RATE`: Funding rate data (futures)

- Dependencies:
  - `DataClientInterface` (Abstract base class for all data clients)
  - `DataClientFactory` (Factory for creating data clients based on provider, market type, and chart type)
  - `RestDataClient` from `rest_data_client.py`
  - `VisionDataClient` from `vision_data_client.py`
  - `BinanceFundingRateClient` from `binance_funding_rate_client.py`
  - `UnifiedCacheManager` from `cache_manager.py`
  - `Interval`, `MarketType` from `market_constraints.py`

#### Configuration Constants

```python
class DataSourceManager:
    VISION_DATA_DELAY_HOURS = 48  # Data newer than this isn't available in Vision API
    REST_CHUNK_SIZE = 1000        # Maximum records per REST API request
    REST_MAX_CHUNKS = 5           # Maximum number of chunks to request via REST
```

### 2. Data Layer

#### Output Format Specification

For KLines data:

```python
OUTPUT_DTYPES = {
    "open": "float64",
    "high": "float64",
    "low": "float64",
    "close": "float64",
    "volume": "float64",
    "close_time": "datetime64[ns]",
    "quote_asset_volume": "float64",
    "count": "int64",
    "taker_buy_volume": "float64",
    "taker_buy_quote_volume": "float64",
}
```

For Funding Rate data:

```python
FUNDING_RATE_DTYPES = {
    "contracts": "string",
    "funding_interval": "string",
    "funding_rate": "float64",
}
```

#### Data Requirements

1. Index Properties:
   - pd.DatetimeIndex in UTC timezone
   - Monotonically increasing
   - No duplicates
   - Aligned to interval boundaries

2. Column Requirements:
   - All required columns present based on chart type
   - Exact dtype matching
   - Consistent ordering
   - Normalized naming

### 3. Client Factory Layer

The `DataClientFactory` serves as a factory for creating appropriate data clients based on provider, market type, and chart type.

```python
# Example client registration
DataClientFactory.register_client(
    provider=DataProvider.BINANCE,
    market_type=MarketType.FUTURES_USDT,
    chart_type=ChartType.FUNDING_RATE,
    client_class=BinanceFundingRateClient
)

# Example client creation
client = DataClientFactory.create_data_client(
    provider=DataProvider.BINANCE,
    market_type=MarketType.FUTURES_USDT,
    chart_type=ChartType.FUNDING_RATE,
    symbol="BTCUSDT",
    interval=Interval.HOUR_8
)
```

### 4. Abstract Client Interface

All data clients implement the `DataClientInterface` abstract base class:

```python
class DataClientInterface(ABC):
    @property
    @abstractmethod
    def provider(self) -> DataProvider:
        """Get the data provider for this client."""
        pass

    @property
    @abstractmethod
    def market_type(self) -> MarketType:
        """Get the market type for this client."""
        pass

    @property
    @abstractmethod
    def chart_type(self) -> ChartType:
        """Get the chart type for this client."""
        pass

    @abstractmethod
    def fetch(
        self,
        start_time: datetime,
        end_time: datetime,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch data for the configured parameters."""
        pass

    # Additional abstract methods...
```

### 5. Cache Layer

The cache has been updated to support multiple providers and chart types:

```tree
/cache_dir
    /PROVIDER
        /CHART_TYPE
            /SYMBOL
                /INTERVAL
                    /YYYY-MM-DD.arrow
    cache_metadata.json
```

Features:

- Apache Arrow for efficient storage
- Provider and chart type support in cache keys
- Hierarchical directory structure
- JSON-based metadata tracking
- Cache validation for all data types

## Usage Guide

### 1. Basic Interface

#### Constructor

```python
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
```

#### Main Method

```python
def get_data(
    symbol: str,                                 # Trading pair (e.g., "BTCUSDT")
    start_time: datetime,                        # Start time in UTC
    end_time: datetime,                          # End time in UTC
    interval: Interval = Interval.SECOND_1,      # Time interval
    use_cache: bool = True,                      # Whether to use caching
    enforce_source: DataSource = DataSource.AUTO, # Force specific data source
    provider: Optional[DataProvider] = None,      # Optional override for data provider
    chart_type: Optional[ChartType] = None,       # Optional override for chart type
) -> pd.DataFrame:
    """Get data for symbol within time range with smart source selection."""
```

### 2. Examples

#### Getting Funding Rate Data

```python
# Create a DataSourceManager for funding rate data
with DataSourceManager(
    market_type=MarketType.FUTURES_USDT,
    provider=DataProvider.BINANCE,
    chart_type=ChartType.FUNDING_RATE,
    cache_dir=Path("./cache"),
    use_cache=True,
) as dsm:
    # Fetch funding rate data
    funding_df = dsm.get_data(
        symbol="BTCUSDT",
        start_time=start_time,
        end_time=end_time,
        interval=Interval.HOUR_8,  # Funding rates typically use 8h interval
    )
```

#### Getting Multiple Data Types from a Single Manager

```python
# Create a DataSourceManager that can handle all data types
with DataSourceManager(
    market_type=MarketType.FUTURES_USDT,
    provider=DataProvider.BINANCE,
    cache_dir=Path("./cache"),
    use_cache=True,
) as dsm:
    # Fetch price data
    klines_df = dsm.get_data(
        symbol="BTCUSDT",
        start_time=start_time,
        end_time=end_time,
        interval=Interval.HOUR_1,
        chart_type=ChartType.KLINES,  # Explicitly specify chart type
    )

    # Fetch funding rate data from the same manager
    funding_df = dsm.get_data(
        symbol="BTCUSDT",
        start_time=start_time,
        end_time=end_time,
        interval=Interval.HOUR_8,
        chart_type=ChartType.FUNDING_RATE,  # Explicitly specify chart type
    )
```

## Extending the Framework

### 1. Adding a New Data Provider

To add support for a new data provider:

1. Add the provider to the `DataProvider` enum in `market_constraints.py`
2. Create a new client implementation that implements `DataClientInterface`
3. Register the client with the `DataClientFactory`

```python
# Add provider to enum
class DataProvider(Enum):
    BINANCE = auto()
    TRADESTATION = auto()
    NEW_PROVIDER = auto()  # Add new provider

# Create client implementation
class NewProviderClient(DataClientInterface):
    # Implement abstract methods

# Register client with factory
DataClientFactory.register_client(
    provider=DataProvider.NEW_PROVIDER,
    market_type=MarketType.SPOT,
    chart_type=ChartType.KLINES,
    client_class=NewProviderClient
)
```

### 2. Adding a New Chart Type

To add support for a new chart type:

1. Add the chart type to the `ChartType` enum in `market_constraints.py`
2. Add appropriate column definitions and DTYPEs in `config.py`
3. Create a client implementation for the new chart type
4. Register the client with the `DataClientFactory`

```python
# Add chart type to enum
class ChartType(Enum):
    KLINES = "klines"
    NEW_CHART_TYPE = "newChartType"  # Add new chart type

# Add column definitions
NEW_CHART_TYPE_COLUMNS = [
    "time",
    "value1",
    "value2",
]

# Add DTYPEs
NEW_CHART_TYPE_DTYPES = {
    "value1": "float64",
    "value2": "string",
}

# Create client implementation
class NewChartTypeClient(DataClientInterface):
    # Implement abstract methods

# Register client with factory
DataClientFactory.register_client(
    provider=DataProvider.BINANCE,
    market_type=MarketType.SPOT,
    chart_type=ChartType.NEW_CHART_TYPE,
    client_class=NewChartTypeClient
)
```

## Conclusion

The `DataSourceManager` has been redesigned to be a flexible, extensible framework that can handle multiple data providers and chart types. The factory pattern and abstract interface allow for easy addition of new data sources and chart types without modifying existing code, adhering to the Liskov Substitution Principle and Occam's Razor philosophy.
