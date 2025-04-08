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
       # Use REST API for small intervals like 1s that Vision doesn't support
       if interval.name == Interval.SECOND_1.name:
           logger.debug("Using REST API for 1s data (Vision API doesn't support it)")
           return False

       # Calculate data points to determine if the request exceeds REST API limits
       data_points = self._estimate_data_points(start_time, end_time, interval)

       # Use Vision API for large data ranges that would exceed REST chunk limits
       if data_points > self.REST_CHUNK_SIZE * self.REST_MAX_CHUNKS:
           logger.debug(
               f"Using Vision API due to large data request ({data_points} points, "
               f"exceeding REST max of {self.REST_CHUNK_SIZE * self.REST_MAX_CHUNKS})"
           )
           return True

       # For all other cases, prefer REST API which has better recent data
       logger.debug("Using REST API for data request (within REST API limits)")
       return False
   ```

2. This simplified logic:
   - Removes the arbitrary historical data threshold (`VISION_DATA_DELAY_HOURS`)
   - Keeps the chunk size constraint (REST_CHUNK_SIZE=1000, REST_MAX_CHUNKS=5)
   - Maintains the interval constraint (1s data uses REST API)
   - Defaults to REST API for all other cases

### 2. Design Updated Data Flow with Split Retrieval

**New Flow:**

1. Check cache first for any available data
2. For any missing data ranges:
   - Split the time range based on chunk size constraints
   - For large ranges (exceeding REST_CHUNK_SIZE \* REST_MAX_CHUNKS), use Vision API
   - For smaller ranges, use REST API
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
    """Split a time range into segments for Vision and REST APIs based on chunk size."""
    # Calculate data points in the range
    data_points = self._estimate_data_points(start_time, end_time, interval)

    # If the entire range is within REST API limits, use only REST
    if data_points <= self.REST_CHUNK_SIZE * self.REST_MAX_CHUNKS:
        return None, (start_time, end_time)

    # If using second-level data, always use REST API
    if interval.name == Interval.SECOND_1.name:
        return None, (start_time, end_time)

    # For large ranges, we need to split
    # Calculate how many data points we can get from REST API
    rest_points = self.REST_CHUNK_SIZE * self.REST_MAX_CHUNKS

    # Calculate the time range for REST API (latest data first)
    rest_duration = timedelta(seconds=rest_points * interval.to_seconds())

    # Use REST API for the most recent part of the data
    rest_start = max(start_time, end_time - rest_duration)

    # Use Vision API for the earlier part of the data if needed
    if rest_start > start_time:
        return (start_time, rest_start), (rest_start, end_time)
    else:
        # The entire range can fit in REST API
        return None, (start_time, end_time)
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
            vision_df = await self._fetch_from_source(
                symbol, vision_range[0], vision_range[1], interval, use_vision=True
            )
            if not vision_df.empty:
                # Add source metadata
                vision_df['_data_source'] = DataSource.VISION.name
                all_results.append(vision_df)

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

1. Decide whether to cache merged data or keep source-specific caches
2. Update cache key generation to handle split sources
3. Ensure cache validation works with multi-source data

### 6. Testing Plan

1. Unit tests:

   - Test time range splitting logic for various scenarios
   - Test missing ranges identification
   - Test merging logic for data from multiple sources
   - **Test the updated source selection logic without the historical threshold**

2. Integration tests:

   - Test end-to-end data retrieval with various time ranges
   - Test cache/Vision/REST interactions
   - Verify correct behavior when sources fail

3. Performance tests:
   - Measure overhead of split retrieval vs. current approach
   - Verify the approach scales with large data ranges
   - **Compare performance with and without the historical threshold**

### 7. Implementation Phases

1. **Phase 1: Update Source Selection Logic**

   - Remove the historical threshold rule from `_should_use_vision_api`
   - Update tests for this function
   - Review with team

2. **Phase 2: Core Splitting Logic**

   - Implement `_split_time_range()` based on chunk size
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

This refactoring will enhance the DataSourceManager to intelligently retrieve data from the most appropriate sources based on chunk size constraints rather than arbitrary time thresholds. By prioritizing cache, then smartly splitting requests between Vision API (for large ranges) and REST API (for smaller/recent ranges), we create a more robust and efficient data retrieval system that better aligns with API capabilities.
