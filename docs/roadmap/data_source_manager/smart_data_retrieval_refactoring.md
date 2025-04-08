# Smart Data Retrieval Refactoring Plan

## Overview

This document outlines a plan to enhance the DataSourceManager to intelligently split data retrieval between multiple sources:

1. **Cache** (highest priority)
2. **Vision API** (for historical data)
3. **REST API** (for recent data that Vision API doesn't have yet)

The goal is to optimize data retrieval by automatically using the most appropriate source for each time segment without requiring explicit configuration by the user.

## Current Implementation Analysis

### Current Data Flow

1. `get_data()` calls `_get_data_impl()`
2. Cache is checked for the entire time range if enabled
3. A single source (Vision or REST) is selected for the entire time range via `_determine_data_source()`
4. Data is fetched from the selected source
5. If Vision API fails, it falls back to REST API for the entire range

### Current Source Selection Logic

The `_should_use_vision_api` method currently uses the following rules to decide whether to use Vision API:

1. Use REST API for small intervals like 1s that Vision doesn't support
   - Note: This is incorrect for SPOT markets, which DO support 1s intervals in Vision API
2. Use Vision API for large time ranges that would exceed REST API's chunk limits:

   ```python
   if data_points > self.REST_CHUNK_SIZE * self.REST_MAX_CHUNKS:
       # Use Vision API
   ```

3. Use Vision API for historical data older than the VISION_DATA_DELAY_HOURS threshold:

   ```python
   if end_time < vision_threshold:  # vision_threshold = now - VISION_DATA_DELAY_HOURS
       # Use Vision API
   ```

4. Default to REST API for recent data

The fallback mechanism (if Vision API fails, try REST API) is already implemented but only works after a full Vision API failure.

### Key Limitations

1. **Binary Source Selection**: Currently uses either Vision API or REST API for the entire range
2. **Fallback Only on Failure**: REST API is only used if Vision API fails
3. **No Time Range Splitting**: Doesn't split the query across sources for partial time ranges
4. **Redundant Vision API Threshold**: The historical data threshold rule isn't necessary since:
   - Vision API automatically falls back to REST API on failure
   - The chunk size constraint already handles large data ranges
   - The threshold creates an arbitrary boundary that can lead to inefficient data retrieval
5. **No Source Identification**: No metadata to track which data came from which source

## Refactoring Plan

### 1. Redesign Source Selection Logic

**Main Change**: Remove the historical data threshold rule and prioritize the chunk size constraint.

1. New `_should_use_vision_api` implementation:

   ```python
   def _should_use_vision_api(
       self, start_time: datetime, end_time: datetime, interval: Interval
   ) -> bool:
       """Determine if Vision API should be used based on time range and interval."""
       # Use REST API for 1s intervals in non-SPOT markets (Vision API doesn't support it)
       if interval.name == Interval.SECOND_1.name and self.market_type != MarketType.SPOT:
           logger.debug("Using REST API for 1s data in non-SPOT markets (Vision API doesn't support it)")
           return False

       # Calculate data points to determine if the request exceeds REST API limits
       data_points = self._estimate_data_points(start_time, end_time, interval)

       # Always prefer Vision API for all data retrievals regardless of size
       # REST API will only be used if Vision API fails or for recent data not yet in Vision
       logger.debug(
           f"Using Vision API as preferred source for {data_points} data points"
       )
       return True
   ```

2. This simplified logic:
   - Corrects the inaccurate handling of 1s intervals, only rejecting them for non-SPOT markets
   - Removes the arbitrary historical data threshold (`VISION_DATA_DELAY_HOURS`)
   - Always prefers Vision API as the primary source after cache
   - Maintains the fallback mechanism where REST API is used if Vision API fails

### 2. Design Updated Data Flow with Split Retrieval

**New Flow:**

1. Check cache first for any available data
2. For any missing data ranges:
   - Try Vision API first for all ranges regardless of size
   - If Vision API fails or data is too recent, use REST API
   - For REST API requests exceeding 1000 data points, automatically chunk them
3. Merge all results and return a unified DataFrame

### 3. Core Function Modifications

#### A. Time Range Splitting Logic

Create a new method in `DataSourceManager`:

```python
def _split_time_range(
    self,
    start_time: datetime,
    end_time: datetime,
    interval: Interval
) -> Tuple[
    Optional[Tuple[datetime, datetime]],  # vision_range
    Optional[Tuple[datetime, datetime]]   # rest_range
]:
    """Split a time range into segments for Vision and REST APIs based on availability.

    Always tries Vision API first, falling back to REST API for recent data not in Vision.
    """
    # For 1s intervals in non-SPOT markets, always use REST API only
    if interval.name == Interval.SECOND_1.name and self.market_type != MarketType.SPOT:
        return None, (start_time, end_time)

    # For all other cases, try Vision API first for the entire range
    # If Vision API fails for any portion, the fallback mechanism will use REST API
    return (start_time, end_time), None
```

#### B. Update `_get_data_impl()`

Refactor `_get_data_impl()` to:

1. Maintain cache retrieval logic
2. Add new logic to handle split time ranges
3. Fetch from multiple sources if needed
4. Merge results

Core changes:

```python
# After cache retrieval but before current source selection
cached_df = ... # existing cache retrieval logic
missing_ranges = self._identify_missing_ranges(cached_df, start_time, end_time)

all_results = []
if cached_df is not None and not cached_df.empty:
    all_results.append(cached_df)

for missing_start, missing_end in missing_ranges:
    # Only process if user hasn't enforced a specific source
    if enforce_source == DataSource.AUTO:
        vision_range, rest_range = self._split_time_range(missing_start, missing_end, interval)

        if vision_range:
            # Try Vision API first
            try:
                vision_df = await self._fetch_from_source(
                    symbol, vision_range[0], vision_range[1], interval, use_vision=True
                )
                if not vision_df.empty:
                    # Add source metadata
                    vision_df['_data_source'] = DataSource.VISION.name
                    all_results.append(vision_df)
                else:
                    # If Vision API returned empty results, fall back to REST API for this range
                    rest_range = vision_range
            except Exception as e:
                logger.warning(f"Vision API fetch failed, falling back to REST API: {e}")
                rest_range = vision_range

        if rest_range:
            rest_df = await self._fetch_from_source(
                symbol, rest_range[0], rest_range[1], interval, use_vision=False
            )
            if not rest_df.empty:
                # Add source metadata
                rest_df['_data_source'] = DataSource.REST.name
                all_results.append(rest_df)
    else:
        # User enforced a specific source, respect that choice
        use_vision = (enforce_source == DataSource.VISION)
        df = await self._fetch_from_source(
            symbol, missing_start, missing_end, interval, use_vision=use_vision
        )
        if not df.empty:
            # Add source metadata
            df['_data_source'] = enforce_source.name
            all_results.append(df)

# Merge results
if all_results:
    final_df = pd.concat(all_results)
    final_df = final_df.sort_index().drop_duplicates()
    return final_df
else:
    return self.create_empty_dataframe()
```

#### C. Add Missing Ranges Identification

```python
def _identify_missing_ranges(
    self,
    df: Optional[pd.DataFrame],
    start_time: datetime,
    end_time: datetime,
    interval: Interval
) -> List[Tuple[datetime, datetime]]:
    """Identify missing time ranges in a DataFrame."""
    if df is None or df.empty:
        return [(start_time, end_time)]

    # Create a time series with the expected frequency
    expected_range = pd.date_range(
        start=start_time,
        end=end_time,
        freq=self._interval_to_freq(interval)
    )

    # Find missing timestamps
    missing_times = expected_range.difference(df.index)

    if len(missing_times) == 0:
        return []

    # Convert missing timestamps to continuous ranges
    return self._timestamps_to_ranges(missing_times, expected_range.freq)
```

#### D. Source Data Identification

Add a way to identify which source provided which data:

1. Add a temporary `_data_source` column to each DataFrame
2. After merging, optionally preserve this column or use it to generate diagnostics
3. Add a parameter to `get_data()` to control whether to keep source metadata:

```python
async def get_data(
    self,
    symbol: str,
    start_time: datetime,
    end_time: datetime,
    interval: Interval = Interval.SECOND_1,
    use_cache: bool = True,
    enforce_source: DataSource = DataSource.AUTO,
    provider: Optional[DataProvider] = None,
    chart_type: Optional[ChartType] = None,
    include_source_metadata: bool = False,  # New parameter
) -> pd.DataFrame:
    # ... existing code ...

    # Retain or remove source metadata based on user preference
    if not include_source_metadata and '_data_source' in df.columns:
        df = df.drop(columns=['_data_source'])

    return df
```

### 4. Helper Functions

Add helper functions:

```python
def _interval_to_freq(self, interval: Interval) -> str:
    """Convert Interval enum to pandas frequency string."""
    # Mapping logic from Interval to pandas freq

def _timestamps_to_ranges(
    self,
    timestamps: pd.DatetimeIndex,
    freq: pd.Timedelta
) -> List[Tuple[datetime, datetime]]:
    """Convert a set of timestamps to continuous date ranges."""
    # Logic to convert discrete timestamps to continuous ranges
```

### 5. Caching Strategy Updates

Update caching to work with split data sources:

1. Merge all data into a single cache entry regardless of source
2. Cache the final concatenated DataFrame from all sources
3. Maintain the existing cache validation logic for merged data

Note: Future enhancement could include metadata tracking of source information in the cache.

### 6. Testing Plan

1. Unit tests:

   - Test time range splitting logic for various scenarios
   - Test missing ranges identification
   - Test merging logic for data from multiple sources
   - **Test the updated source selection logic without the historical threshold**
   - **Test 1s interval handling for SPOT vs non-SPOT markets**

2. Integration tests:

   - Test end-to-end data retrieval with various time ranges
   - Test cache/Vision/REST interactions
   - Verify correct behavior when sources fail
   - **Verify proper handling of 1s data in SPOT markets via Vision API**

3. Performance tests:
   - Measure overhead of split retrieval vs. current approach
   - Verify the approach scales with large data ranges
   - **Compare performance with and without the historical threshold**

### 7. Implementation Phases

1. **Phase 1: Update Source Selection Logic**

   - Correct the handling of 1s intervals for SPOT markets
   - Remove the historical threshold rule from `_should_use_vision_api`
   - Update tests for this function
   - Review with team

2. **Phase 2: Core Splitting Logic**

   - Implement `_split_time_range()` based on the updated strategy
   - Add tests for this function
   - Review with team

3. **Phase 3: Modified Retrieval Flow**

   - Update `_get_data_impl()` to use splitting logic
   - Implement missing ranges detection
   - Add source tracking metadata
   - Keep backward compatibility

4. **Phase 4: Caching Refinements**

   - Update caching strategy for split sources
   - Optimize cache utilization
   - Implement single cache entry for merged data from all sources

5. **Phase 5: Testing and Validation**

   - Add comprehensive tests
   - Verify behavior in varied scenarios
   - Benchmark performance

6. **Phase 6: Documentation and Final Review**
   - Update documentation
   - Add examples
   - Final review with team

## Risks and Mitigations

1. **Complexity Increase**

   - Mitigation: Isolate new logic in clear, well-tested functions
   - Ensure backward compatibility

2. **Performance Overhead**

   - Mitigation: Implement optimizations to reduce duplicate work
   - Benchmark before/after

3. **Cache Coherence**

   - Mitigation: Develop clear rules for handling overlapping/conflicting data
   - Ensure validation checks for merged data

4. **Backward Compatibility**

   - Mitigation: Keep existing interfaces working
   - Add feature flags to enable/disable new behavior

5. **Loss of Historical Data Threshold**
   - Risk: Removing the VISION_DATA_DELAY_HOURS threshold might impact some edge cases
   - Mitigation: Thorough testing to ensure all scenarios are covered
   - Fallback mechanism ensures REST API is used if Vision API fails

## Conclusion

This refactoring will enhance the DataSourceManager to intelligently retrieve data from the most appropriate sources with an emphasis on cache first, then Vision API, followed by REST API as needed. By prioritizing cache, then using Vision API for historical data (including 1s intervals in SPOT markets), and falling back to REST API (with appropriate chunking) for any failures or gaps, we create a more robust and efficient data retrieval system that better aligns with API capabilities.
