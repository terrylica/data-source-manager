# Overview of DataSourceManager

## Data Retrieval Process

The `DataSourceManager` orchestrates the data retrieval process, intelligently navigating between cache and live data sources (Vision API and REST API). This overview focuses on how the manager handles time alignment in accordance with our revised approach.

### Core Principles of Time Alignment

Following our roadmap to revamp time alignment:

1. **REST API Behavior is the Source of Truth** - The Binance REST API's boundary behavior is our definitive standard
2. **No Manual Alignment for REST API Calls** - For REST API calls, we pass timestamps directly without manual alignment
3. **Manual Alignment for Vision API and Cache** - We implement manual time alignment for Vision API and cache to match REST API behavior

### REST API Pathway

When the `DataSourceManager` determines that the REST API is the appropriate source:

1. The `get_data` method passes timestamps directly to the REST API without manual alignment
2. The `_fetch_from_source` method invokes the `fetch` method of `RestDataClient` with original timestamps
3. The REST API handles time boundary alignment according to its documented behavior:

   - Ignores millisecond precision
   - Rounds start timestamps UP to the next interval boundary if not exact
   - Rounds end timestamps DOWN to the previous interval boundary if not exact
   - Treats both boundaries as inclusive after alignment

4. The `RestDataClient` employs a chunking mechanism to divide the requested time range into manageable chunks, respecting the original time boundaries
5. Each chunk is fetched with retry logic and endpoint failover for resilience
6. The raw API response is processed into a standardized DataFrame

### Vision API Pathway

When Vision API is the appropriate source:

1. The `get_data` method passes timestamps to the `VisionDataClient`
2. The `VisionDataClient.fetch` method applies manual time alignment to mirror REST API behavior
3. This manual alignment is validated using `ApiBoundaryValidator` to ensure it matches REST API behavior
4. The aligned timestamps are used for:

   - Cache key generation
   - Data downloading from Vision API
   - Time boundary validation

5. The `_download_and_cache` method breaks down the requested time range into daily segments
6. For each day, data is downloaded, verified, and parsed
7. The timestamps are processed to maintain consistency with REST API behavior

### Validation and Verification

The `ApiBoundaryValidator` is used throughout the process to:

1. Validate if a given time range and interval are valid according to REST API boundaries
2. Determine actual boundaries that would be returned by the REST API
3. Verify that Vision API and cache data ranges match what the REST API would return

This ensures consistent behavior across all data sources.

### Data Standardization and Return

For both pathways, once data is fetched and validated, the `DataSourceManager`:

1. Applies final formatting using the `_format_dataframe` method
2. Standardizes the DataFrame with consistent column names, data types, and index structures
3. Returns the formatted DataFrame via the `get_data` method

## Conclusion

The revised `DataSourceManager` architecture adopts a cleaner approach to time alignment by:

1. Using the Binance REST API's boundary behavior as the definitive standard
2. Passing timestamps directly to REST API without manual adjustment
3. Implementing manual alignment for Vision API and cache that mirrors REST API behavior
4. Validating all time boundary handling against real REST API responses using `ApiBoundaryValidator`

This approach ensures consistent data retrieval across sources while simplifying the codebase by removing unnecessary manual alignment for REST API calls.
