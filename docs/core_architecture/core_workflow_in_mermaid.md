# Market Data Retrieval Workflow

```mermaid
graph LR
    A["Start: Data Request<br/>symbol, time range, interval"] --> B["**Check Cache (Daily)?**<br/>use_cache=True<br/><br/><sup>User preference & config</sup>"]
    B -- Yes --> C["**Cache Hit (Daily)?**<br/>Valid & Recent Data for Day?<br/><br/><sup>Metadata & checksum validation</sup><br/><sup>Data freshness threshold</sup>"]
    B -- No --> D["**Data Source Selection**<br/>_should_use_vision_api<br/><br/><sup>Estimate data points</sup><br/><sup>Vision API for large requests</sup>"]
    C -- Yes --> E["**Load Data from Cache**<br/>UnifiedCacheManager.load_from_cache<br/><br/><sup>Fast daily retrieval</sup><br/><sup>REST API boundary aligned</sup>"] --> F["Return Data<br/>DataFrame from Cache"]
    C -- No --> D
    D --> D1["**Vision API (Preferred)**<br/>VisionDataClient.fetch<br/><br/><sup>Uses manual time alignment</sup><br/><sup>to match REST API behavior</sup>"]
    D --> D2["**REST API (Fallback)**<br/>EnhancedRetriever.fetch<br/><br/><sup>No manual time alignment</sup><br/><sup>Relies on API's boundary handling</sup>"]
    D1 --> G{"**Vision API Fetch**<br/>VisionDataClient.fetch<br/><br/><sup>Applies manual alignment</sup><br/><sup>to match REST API behavior</sup><br/><sup>Validated with ApiBoundaryValidator</sup>"}
    G -- Success --> I{"**Save to Cache (Daily)?**<br/>UnifiedCacheManager.save_to_cache<br/><br/><sup>Saves with REST API-aligned boundaries</sup><br/><sup>Uses ApiBoundaryValidator</sup>"}
    G -- Fail --> H["**REST API Fetch**<br/>EnhancedRetriever.fetch<br/><br/><sup>Passes timestamps directly to API</sup><br/><sup>API handles boundary alignment</sup><br/><sup>Chunking with original time boundaries</sup>"]
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

This diagram illustrates the revamped market data retrieval workflow, with a specific focus on the updated time alignment strategy. Key changes include:

1. **REST API Path**: When using the REST API, timestamps are passed directly without manual alignment. The API inherently handles boundary alignment according to its documented behavior.

2. **Vision API Path**: When using the Vision API, manual time alignment is applied to mirror REST API behavior. This ensures consistent results across data sources.

3. **Cache Operations**: Cache keys and data validation use REST API-aligned timestamps, ensuring consistency between cached data and what would be returned by direct API calls.

4. **Validation**: The `ApiBoundaryValidator` is used to validate time boundaries and data ranges against the REST API's behavior, ensuring consistency.

## Process Description

The data retrieval process begins with a user request for market data. The system first checks if REST API-aligned cached data is available and valid. If valid cache exists, it is loaded.

Otherwise, the system selects the data source based on request parameters:

- **Vision API Path**: Applies manual time alignment to match REST API behavior, downloads data, validates with `ApiBoundaryValidator`, and caches with REST API-aligned boundaries.

- **REST API Path**: Passes timestamps directly to the API without manual alignment, allowing the API to handle boundary alignment inherently. Chunks requests with original time boundaries.

All data sources are now aligned with Binance REST API's boundary behavior, whether through direct API calls or manual alignment for Vision API and cache operations.

This updated approach:

- Simplifies REST API calls by removing unnecessary manual alignment
- Ensures Vision API and cache operations precisely mirror REST API behavior
- Uses real-world API validation through `ApiBoundaryValidator` to verify alignment
- Provides consistent results regardless of data source
