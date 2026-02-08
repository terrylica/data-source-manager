# Funding Rate Data Client

## Overview

The `BinanceFundingRateClient` implements the `DataClientInterface` to provide access to funding rate data from Binance's futures markets. Funding rates are essential data points for futures traders, representing the periodic payments between long and short position holders to maintain the market price close to the index price.

## Architecture

The funding rate client follows the same architectural principles as other data clients:

1. Implements the `DataClientInterface` abstract base class
2. Registered with the `DataClientFactory` for provider and chart type
3. Manages its own data retrieval and formatting logic

## Client Registration

```python
DataClientFactory.register_client(
    provider=DataProvider.BINANCE,
    market_type=MarketType.FUTURES_USDT,
    chart_type=ChartType.FUNDING_RATE,
    client_class=BinanceFundingRateClient
)
```

## Data Structure

### Funding Rate Data Format

Funding rate data is structured differently from standard KLines:

```python
FUNDING_RATE_COLUMNS = [
    "time",             # Funding timestamp (UTC)
    "contracts",        # Symbol (e.g., "BTCUSDT")
    "funding_interval", # Funding interval (e.g., "8h")
    "funding_rate",     # Funding rate value
]

FUNDING_RATE_DTYPES = {
    "contracts": "string",
    "funding_interval": "string",
    "funding_rate": "float64",
}
```

The data is indexed by the `time` column, which is converted to a timezone-aware DatetimeIndex in UTC.

## API Endpoints

The client uses different API endpoints based on whether it's accessing historical or recent data:

### Historical Data (Vision API)

For historical funding rate data, the client accesses the Binance Vision API:

```url
https://data.binance.vision/data/futures/um/daily/fundingRate/{symbol}/{symbol}-fundingRate-{date}.zip
```

### Recent Data (REST API)

For recent funding rate data, the client uses the Binance Futures REST API:

```url
https://fapi.binance.com/fapi/v1/fundingRate
```

Parameters:

- `symbol`: The futures contract symbol (e.g., "BTCUSDT")
- `startTime`: Start timestamp in milliseconds
- `endTime`: End timestamp in milliseconds
- `limit`: Maximum number of records to return (default: 100, max: 1000)

## Usage Example

```python
from datetime import datetime, timezone, timedelta
from pathlib import Path
from data_source_manager.utils.market_constraints import Interval, MarketType, ChartType, DataProvider
from data_source_manager.core.sync.data_source_manager import DataSourceManager

# Set time range for data retrieval
end_time = datetime.now(timezone.utc)
start_time = end_time - timedelta(days=30)  # Last 30 days of funding rate data

def funding_rate_example():
    # Initialize DataSourceManager for funding rate data
    with DataSourceManager(
        market_type=MarketType.FUTURES_USDT,
        provider=DataProvider.BINANCE,
        chart_type=ChartType.FUNDING_RATE,
        cache_dir=Path("./cache"),
        use_cache=True,
    ) as dsm:
        # Fetch funding rate data
        df = dsm.get_data(
            symbol="BTCUSDT",
            start_time=start_time,
            end_time=end_time,
            interval=Interval.HOUR_8,  # Funding rates typically use 8h interval
        )

        print(f"Retrieved {len(df)} funding rate records")
        print(df.head())

        # Calculate average funding rate
        avg_rate = df["funding_rate"].mean()
        print(f"Average funding rate: {avg_rate:.6f}")

        # Find highest funding rate
        max_rate = df["funding_rate"].max()
        max_time = df.loc[df["funding_rate"] == max_rate].index[0]
        print(f"Highest funding rate: {max_rate:.6f} at {max_time}")
```

## Caching

Funding rate data follows the same caching structure as other data types:

```tree
/cache_dir
    /BINANCE
        /FUNDING_RATE
            /BTCUSDT
                /8h
                    /YYYY-MM-DD.arrow
    cache_metadata.json
```

## Time Handling

Funding rates are typically published every 8 hours (at 00:00, 08:00, and 16:00 UTC). The client handles this by:

1. Always using the `Interval.HOUR_8` interval for funding rate data
2. Aligning timestamps to funding rate boundaries
3. Ensuring all timestamps are in UTC timezone

## Implementation Details

### Data Transformation

The client transforms the raw API response into a standardized DataFrame:

1. Converts timestamps to datetime objects with UTC timezone
2. Sets the time column as the DataFrame index
3. Ensures proper data types for all columns
4. Sorts the data by timestamp

### Error Handling

The client implements specialized error handling:

1. Funding rate-specific validation rules
2. Detection of missing funding rate periods
3. Rate limiting awareness
4. Recovery mechanisms for partial data retrieval

## Extension Points

The design allows for easy extension:

1. Adding support for other futures markets (COIN-M, etc.)
2. Supporting other funding rate intervals
3. Adding additional funding-related metrics
4. Supporting other data providers' funding rate formats

## Related Components

- `DataClientInterface`: Abstract base class implemented by this client
- `DataClientFactory`: Factory that creates instances of this client
- `DataSourceManager`: Uses this client via the factory
- `src/data_source_manager/utils/config.py`: Contains funding rate column definitions
- `src/data_source_manager/utils/market_constraints.py`: Contains enum definitions
