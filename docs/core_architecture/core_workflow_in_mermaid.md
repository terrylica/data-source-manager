# Mermaid Flowchat

```mermaid
graph LR
    A["Start: Data Request<br/>symbol, time range, interval"] --> B["**Check Cache (Daily)?**<br/>use_cache=True<br/><br/><sup>User preference & config</sup><br/><sup>Checks cache daily</sup>"]
    B -- Yes --> C["**Cache Hit (Daily)?**<br/>Valid & Recent Data for Day?<br/><br/><sup>Metadata & checksum validation</sup><br/><sup>Data freshness threshold</sup><br/><sup>Time range & interval match</sup>"]
    B -- No --> D["**Data Source Selection**<br/>_should_use_vision_api<br/><br/><sup>Estimate data points</sup><br/><sup>Vision API for large requests</sup><br/><sup>Default Vision API</sup>"]
    C -- Yes --> E["**Load Data from Cache**<br/>UnifiedCacheManager.load_from_cache<br/><br/><sup>Fast daily retrieval</sup><br/><sup>Arrow format</sup>"] --> F["Return Data<br/>DataFrame from Cache<br/><br/><sup>Returns cache for first day hit</sup><br/><sup>Full range might not be covered</sup>"]
    C -- No --> D
    D --> D1["**Vision API (Preferred)**<br/>VisionDataClient.fetch<br/><br/><sup>Comprehensive history</sup><br/><sup>Best for large datasets</sup><br/><sup>Supports all intervals</sup><br/><sup>Fetches entire range</sup>"]
    D --> D2["**REST API (Fallback)**<br/>EnhancedRetriever.fetch<br/><br/><sup>If Vision API fails</sup><br/><sup>Suitable for recent data</sup><br/><sup>Subject to rate limits</sup><br/><sup>Fetches entire range</sup>"]
    D1 --> G{"**Vision API Fetch**<br/>VisionDataClient.fetch<br/><br/><sup>Downloads from Binance Vision API</sup><br/><sup>Handles errors & retries</sup><br/><sup>Data parsing & validation</sup><br/><sup>Fetches entire range</sup>"}
    G -- Success --> I{"**Save to Cache (Daily)?**<br/>UnifiedCacheManager.save_to_cache<br/><br/><sup>Saves fetched data</sup><br/><sup>Caches daily</sup><br/><sup>If cache enabled & data not empty</sup><br/><sup>Updates metadata</sup>"}
    G -- Fail --> H["**REST API Fetch**<br/>EnhancedRetriever.fetch<br/><br/><sup>Fetches from Binance REST API</sup><br/><sup>Chunking large ranges</sup><br/><sup>Rate limit management</sup><br/><sup>Data processing & validation</sup><br/><sup>Fetches entire range</sup>"]
    H -- Success --> K{"**Save to Cache (Daily)?**<br/>UnifiedCacheManager.save_to_cache<br/><br/><sup>Caches REST data</sup><br/><sup>Caches daily</sup><br/><sup>If cache enabled & data not empty</sup><br/><sup>Same caching process</sup>"}
    H -- Fail --> M["**Error Handling**<br/>raise Exception<br/><br/><sup>Retrieval failure</sup><br/><sup>Logged error details</sup><br/><sup>User informed</sup>"]
    I --> J["Return Data<br/>DataFrame from Vision API<br/><br/><sup>Returns data for entire range</sup>"]
    K --> L["Return Data<br/>DataFrame from REST API<br/><br/><sup>Returns data for entire range</sup>"]
    E --> N["End: Data Retrieval<br/>Returns DataFrame for entire range"]
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

This diagram illustrates the core workflow for retrieving market data. It starts with a data request, checks for daily cached data, and if not available, selects between Vision API (preferred) and REST API (fallback) to fetch the data. Fetched data can be saved to the cache for future use. The process concludes by returning the requested DataFrame or handling errors if data retrieval fails.

Below is a prose explanation of the workflow depicted in the diagram:

> The data retrieval process begins with a user request for market data, specifying the symbol, time range, and interval. The system first checks if daily cached data is available and valid. If a valid daily cache exists, it is loaded for fast retrieval. Otherwise, the system intelligently selects the data source, preferring the Vision API for its comprehensive historical data and large dataset capabilities. If the Vision API fetch fails, the system falls back to the REST API. Data fetched from either API is then processed, validated, and returned to the user as a DataFrame. Optionally, the fetched data can be saved to the cache on a daily basis to expedite future requests. Error handling is integrated throughout the process to manage potential issues and inform the user of any retrieval failures.

**Key Changes:**

- **Block H Label Corrected**: Block `H` now correctly displays "**REST API Fetch**" and its descriptive text, clarifying its role in fetching data from the REST API.
- **Prose Explanation Added**: A paragraph explaining the overall workflow in prose format is included below the Mermaid diagram, providing a textual summary of the visual representation.

This updated `docs/core_workflow_in_mermaid.md` file should now be complete with a clear diagram and a helpful textual overview of the data retrieval workflow.
