# Data Source Manager Overview

## Data Retrieval Process

The Data Source Manager (DSM) acts as a central mediator between the application and various data sources across different providers. It supports flexible data retrieval for multiple market types and chart types, ensuring a unified interface regardless of the underlying data source.

### Architecture Overview

```diagram
┌─────────────────┐     ┌───────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                   │     │                 │     │                 │
│  Application    │────▶│  DataSourceManager│────▶│ DataClientFactory ───▶│Specific DataClient│
│                 │     │                   │     │                 │     │                 │
└─────────────────┘     └───────────────────┘     └─────────────────┘     └─────────────────┘
                                                                                   │
                                                                                   ▼
                                                              ┌─────────────────────────────────┐
                                                              │                                 │
                                          ┌──────────────────▶│      REST API (Recent Data)     │
                                          │                   │                                 │
                                          │                   └─────────────────────────────────┘
                                          │                   ┌─────────────────────────────────┐
                                          │                   │                                 │
                                          └──────────────────▶│      Vision API (Historical)    │
                                          │                   │                                 │
                                          │                   └─────────────────────────────────┘
                                          │                   ┌─────────────────────────────────┐
                                          │                   │                                 │
                                          └──────────────────▶│   Custom API (Funding Rates)    │
                                                              │                                 │
                                                              └─────────────────────────────────┘
```

### Multi-Provider Support

The DSM now supports multiple data providers through:

1. **Provider Enum**: A hierarchical enum structure in `market_constraints.py` defines available providers
2. **Abstract Interface**: All data clients implement the `DataClientInterface` abstract base class
3. **Client Factory**: The `DataClientFactory` creates appropriate clients based on provider, market type, and chart type

### Multi-Chart Type Support

Different chart types are supported through:

1. **Chart Type Enum**: A comprehensive enum of available chart types (klines, funding rates)
2. **Specialized Clients**: Each chart type has dedicated client implementations
3. **Dynamic Column Definitions**: Configuration-driven column definitions in `config.py`

### REST API Pathway

For recent data, DSM utilizes REST API clients:

1. Start and end timestamps are passed directly to the REST API
2. Appropriate API endpoint is selected based on market type, provider, and chart type
3. Response data is formatted according to chart type specifications

### Vision API Pathway

For historical data, DSM utilizes Vision API clients:

1. Vision API is used for data older than `VISION_DATA_DELAY_HOURS` (48 hours)
2. Organized by provider, market type, and chart type
3. Uses standardized Arrow-based format for efficient storage

### Specialized API Pathways

For specialized data types (e.g., funding rates):

1. Custom API clients implement the `DataClientInterface`
2. Provider-specific implementations handle unique API patterns
3. Data is transformed to match standardized output format

### Validation and Verification

All data retrieved through any client undergoes validation:

1. **Structure Validation**: Checks for required columns based on chart type
2. **Type Validation**: Ensures correct data types for each column
3. **Index Validation**: Verifies proper DatetimeIndex properties
4. **Consistency Validation**: Ensures consistent data shape and properties

### Unified Caching Strategy

The cache structure supports multi-provider, multi-chart type operation:

```tree
/cache_dir
    /PROVIDER
        /CHART_TYPE
            /SYMBOL
                /INTERVAL
                    /YYYY-MM-DD.arrow
    cache_metadata.json
```

This hierarchical structure allows efficient storage and retrieval across all supported data types and providers.

## Revised Architecture

The revised architecture offers several improvements:

1. **Extensibility**: Easy addition of new providers and chart types
2. **Separation of Concerns**: Clear boundaries between components
3. **Unified Interface**: Consistent API regardless of underlying provider
4. **Optimized Performance**: Provider-specific optimizations without interface changes

By using a factory pattern with abstract interfaces, the DSM isolates clients from the specifics of data retrieval while maintaining a consistent, predictable interface.
