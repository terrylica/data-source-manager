# Market Data Retrieval Workflow

```mermaid
graph LR
    A["Start: Data Request<br/>symbol, time range, interval"] --> B["**Check Cache (Daily)?**<br/>use_cache=True<br/><br/><sup>User preference & config</sup>"]
    B -- Yes --> C["**Cache Hit (Daily)?**<br/>Valid & Recent Data for Day?<br/><br/><sup>Metadata & checksum validation</sup><br/><sup>Data freshness threshold</sup>"]
    B -- No --> D["**Data Source Selection**<br/>_should_use_vision_api<br/><br/><sup>Estimate data points</sup><br/><sup>Vision API for large requests</sup>"]
    C -- Yes --> E["**Load Data from Cache**<br/>UnifiedCacheManager.load_from_cache<br/><br/><sup>Fast daily retrieval</sup><br/><sup>REST API boundary aligned</sup>"] --> F["Return Data<br/>DataFrame from Cache"]
    C -- No --> D
    D --> D1["**Vision API (Primary)**<br/>VisionDataClient.fetch<br/><br/><sup>Uses ApiBoundaryValidator</sup><br/><sup>to align boundaries to REST API</sup>"]
    D --> D2["**REST API (Fallback)**<br/>RestDataClient.fetch<br/><br/><sup>No manual time alignment</sup><br/><sup>Relies on API's boundary handling</sup>"]
    D1 --> G{"**Vision API Fetch**<br/>VisionDataClient._download_and_cache<br/><br/><sup>Applies boundary alignment via</sup><br/><sup>ApiBoundaryValidator.align_time_boundaries</sup><br/><sup>Downloads daily files & combines</sup>"}
    G -- Success --> I{"**Save to Cache (Daily)?**<br/>UnifiedCacheManager.save_to_cache<br/><br/><sup>Saves with REST API-aligned boundaries</sup><br/><sup>using TimeRangeManager.align_vision_api_to_rest</sup>"}
    G -- Fail --> H["**REST API Fetch**<br/>RestDataClient.fetch<br/><br/><sup>Passes timestamps directly to API</sup><br/><sup>API handles boundary alignment</sup><br/><sup>Chunking with original time boundaries</sup>"]
    H -- Success --> K{"**Save to Cache (Daily)?**<br/>UnifiedCacheManager.save_to_cache<br/><br/><sup>Caches with REST API boundaries</sup>"}
    H -- Fail --> M["**Error Handling**<br/>raise Exception<br/><br/><sup>Retrieval failure</sup><br/><sup>Logged error details</sup>"]
    I --> J["Return Data<br/>DataFrame from Vision API<br/><br/><sup>Aligned with REST API boundaries</sup>"]
    K --> L["Return Data<br/>DataFrame from REST API"]
    E --> N["End: Data Retrieval<br/>Returns DataFrame"]
    F --> N
    J --> N
    L --> N
    M --> N
    style I fill:#f9f,stroke:#333,stroke-width:2px,color:#000
    style K fill:#f9f,stroke:#333,stroke-width:2px,color:#000
    style B fill:#ccf,stroke:#333,stroke-width:2px,color:#000,shape:rect
    style C fill:#ccf,stroke:#333,stroke-width:2px,color:#000,shape:rect
    style D fill:#ccf,stroke:#333,stroke-width:2px,color:#000,shape:rect
    style D1 fill:#cfc,stroke:#333,stroke-width:2px,color:#000
    style D2 fill:#cfc,stroke:#333,stroke-width:2px,color:#000
    style E fill:#cfc,stroke:#333,stroke-width:2px,color:#000
    style G fill:#eee,stroke:#333,stroke-width:2px,color:#000
    style H fill:#eee,stroke:#333,stroke-width:2px,color:#000
    style M fill:#fee,stroke:#333,stroke-width:2px,color:#000
```

## Updated Workflow Overview

This diagram illustrates the market data retrieval workflow, with a specific focus on the time alignment strategy. Key aspects include:

1. **REST API Path**: When using the REST API, timestamps are passed directly without manual alignment. The API inherently handles boundary alignment according to its documented behavior.

2. **Vision API Path**: When using the Vision API, manual time alignment is applied via `ApiBoundaryValidator.align_time_boundaries()` to match REST API behavior. This ensures consistent results across data sources.

3. **Cache Operations**: Cache keys and data validation use REST API-aligned timestamps, ensuring consistency between cached data and what would be returned by direct API calls.

4. **Boundary Alignment**: The system uses two complementary alignment approaches:
   - `ApiBoundaryValidator.align_time_boundaries()` - Used directly in Vision API fetch operations
   - `TimeRangeManager.align_vision_api_to_rest()` - Used for cache operations and data filtering

## Process Description

The data retrieval process begins with a user request for market data. The system first checks if REST API-aligned cached data is available and valid. If valid cache exists, it is loaded.

Otherwise, the system selects the data source based on request parameters:

- **Vision API Path (Primary)**: The system typically prefers Vision API for most requests, especially larger ones. It applies precise time boundary alignment using `ApiBoundaryValidator.align_time_boundaries()`, downloads data by day, combines results, and caches with REST API-aligned boundaries.

- **REST API Path (Fallback)**: Passes timestamps directly to the API without manual alignment, allowing the API to handle boundary alignment inherently. Chunks requests with original time boundaries.

All data sources are now aligned with Binance REST API's boundary behavior, whether through direct API calls or manual alignment for Vision API and cache operations.

This approach provides several advantages:

- **Consistency**: All data sources (REST API, Vision API, and cache) deliver identical results for the same time range query
- **Efficiency**: REST API calls are simplified by removing unnecessary manual alignment
- **Precision**: Vision API alignment accurately mirrors REST API behavior for exact data compatibility
- **Validation**: Uses real-time API alignment information through `ApiBoundaryValidator` rather than hard-coded rules
- **Resilient Caching**: Cache operations use consistent boundary alignment for reliable lookups
