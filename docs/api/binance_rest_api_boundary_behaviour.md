# Binance REST API Boundary Behavior

This document provides a comprehensive analysis of how the Binance REST API handles timestamp boundaries when retrieving time-series data. Understanding these behaviors is crucial for correctly implementing time-based queries and ensuring consistent results.

## Key Findings

Through extensive testing with both current and historical data (including cross-boundary periods), we have identified the following behaviors in the Binance REST API:

1. **Boundary Alignment**: The API aligns all timestamps to interval boundaries, ignoring any millisecond precision.
2. **Rounding Rules**: Specific rounding is applied to start and end timestamps.
3. **Interval Completeness**: The API only returns complete interval candles.
4. **Consistent Behavior**: This behavior is identical across all interval types and remains consistent across day, month, and year boundaries.
5. **API Limit**: The default limit is 500 candles per request, but can be increased to a maximum of 1000 by explicitly setting the `limit` parameter.

## Timestamp Boundary Handling

### Millisecond Precision

The Binance API completely ignores millisecond precision in timestamps. It operates exclusively on interval boundaries:

- For 1-second intervals: timestamps are aligned to whole seconds
- For 1-minute intervals: timestamps are aligned to whole minutes
- For other intervals: timestamps are aligned to their respective boundaries

This behavior remains consistent even across calendar boundaries (day, month, or year changes).

### Boundary Rounding Rules

When timestamps include millisecond components or fall between interval boundaries, the API applies specific rounding:

- **startTime**: Rounds UP to the next interval boundary if not exactly on a boundary
- **endTime**: Rounds DOWN to the previous interval boundary if not exactly on a boundary

### Examples

#### 1-Second Interval Examples

| Scenario               | Request Parameters                                                           | API Behavior                                  | Records Returned         |
| ---------------------- | ---------------------------------------------------------------------------- | --------------------------------------------- | ------------------------ |
| Exact boundaries       | startTime=1742793800000 (05:23:20), endTime=1742793810000 (05:23:30)         | First record: 05:23:20, Last record: 05:23:30 | 11 (inclusive-inclusive) |
| Millisecond start      | startTime=1742793800123 (05:23:20.123), endTime=1742793810000 (05:23:30)     | First record: 05:23:21, Last record: 05:23:30 | 10 (rounds up start)     |
| Millisecond end        | startTime=1742793800000 (05:23:20), endTime=1742793810456 (05:23:30.456)     | First record: 05:23:20, Last record: 05:23:30 | 11 (rounds down end)     |
| Both with milliseconds | startTime=1742793800123 (05:23:20.123), endTime=1742793810456 (05:23:30.456) | First record: 05:23:21, Last record: 05:23:30 | 10                       |
| Edge case (999ms)      | startTime=1742793800999 (05:23:20.999), endTime=1742793810001 (05:23:30.001) | First record: 05:23:21, Last record: 05:23:30 | 10                       |
| Cross-midnight         | startTime=1742774395000 (23:59:55), endTime=1742774405000 (00:00:05)         | First record: 23:59:55, Last record: 00:00:05 | 11 (seamless transition) |

#### 1-Minute Interval Examples

| Scenario          | Request Parameters                                                           | API Behavior                                  | Records Returned             |
| ----------------- | ---------------------------------------------------------------------------- | --------------------------------------------- | ---------------------------- |
| Exact boundaries  | startTime=1742793760000 (05:22:40), endTime=1742794060000 (05:27:40)         | First record: 05:23:00, Last record: 05:27:00 | 5 (minute-aligned)           |
| Millisecond start | startTime=1742793760123 (05:22:40.123), endTime=1742794060000 (05:27:40)     | First record: 05:23:00, Last record: 05:27:00 | 5 (rounds to minute)         |
| Mid-minute start  | startTime=1742793780123 (05:23:00.123), endTime=1742794060456 (05:27:40.456) | First record: 05:24:00, Last record: 05:27:00 | 4 (rounds up to next minute) |
| Edge boundaries   | startTime=1742793759999 (05:22:39.999), endTime=1742794060001 (05:27:40.001) | First record: 05:23:00, Last record: 05:27:00 | 5                            |
| Cross-midnight    | startTime=1742774280000 (23:58:00), endTime=1742774520000 (00:02:00)         | First record: 23:58:00, Last record: 00:02:00 | 5 (seamless transition)      |

## Cross-Boundary Behavior

We conducted extensive testing on how the API handles data queries that cross significant time boundaries:

### Day Boundary (Midnight)

For queries spanning midnight (23:59:59 to 00:00:01):

- The API maintains complete continuity across the boundary
- No special handling or gaps occur at midnight
- Millisecond precision is handled consistently (same rounding rules apply)
- For 1-second intervals: all seconds remain represented
- For 1-minute intervals: 23:59:00 and 00:00:00 candles are properly included

### Year Boundary

For queries spanning year changes (December 31 to January 1):

- The API maintains perfect continuity across year boundaries
- No special handling or gaps occur at year transitions
- Time alignment and interval boundaries are preserved
- The behavior is identical to any other time period

### Important Observations

1. **Seamless Transitions**: The API treats all time transitions (second, minute, hour, day, month, year) as continuous with no special cases or gaps.

2. **Consistent Rounding**: Millisecond precision is always ignored, with the same rounding rules applying at all times:

   - A timestamp of 23:59:59.999 will be treated as the next second (00:00:00) when used as startTime
   - A timestamp of 00:00:00.001 will be treated as the current second (00:00:00) when used as endTime

3. **Boundary Edge Cases**: Our most extreme test cases (1ms after interval start to 1ms before next interval) confirmed that the API strictly enforces whole interval boundaries.

## Implications for Time-Series Data Retrieval

### Record Counting Logic

For a given time range with start time `S` and end time `E` for interval `I`:

1. After boundary alignment (rounding up start, rounding down end)
2. The API will return approximately `(E - S)/I + 1` records
3. The exact count may differ due to:
   - Missing data points (no trading during certain intervals)
   - API limits (default 500 records per request, maximum 1000 with `limit` parameter)
   - Boundary rounding effects

### Implementation Strategy

To correctly handle the API's boundary behavior:

1. **Input Preparation**:

   - Align start time to interval boundary (floor)
   - Align end time to interval boundary (floor)
   - Use exact aligned timestamps in API calls

2. **Output Processing**:
   - Parse API response with the understanding that:
     - First timestamp will be >= aligned start time (possibly rounded up by API)
     - Last timestamp will be <= aligned end time (rounded down by API)
     - The API returns whole interval candles only

## Practical Example

For a query requesting data from `2023-01-01T10:15:30.123Z` to `2023-01-01T10:25:45.789Z` with 1-minute interval:

1. **Aligned timestamps**:

   - Aligned start: `2023-01-01T10:15:00.000Z` (floor to minute)
   - Aligned end: `2023-01-01T10:25:00.000Z` (floor to minute)

2. **API processing**:
   - The API will return complete 1-minute candles
   - First candle: `10:15:00` (for interval 10:15:00-10:15:59.999)
   - Last candle: `10:25:00` (for interval 10:25:00-10:25:59.999)
   - Total: 11 candles (inclusive of both boundaries)

## Understanding the API's Design

The Binance API's behavior with timestamps is consistent with how time-series data is typically processed in financial systems:

1. **Whole Interval Principle**: The API only operates on complete intervals (1s, 1m, etc.) because financial candles represent complete periods of market activity.

2. **Alignment by Design**: The millisecond rounding behavior ensures that:

   - Candles represent complete intervals
   - There are no partial or overlapping candles
   - All returned data aligns with standard interval boundaries

3. **Consistent Processing Approach**: The behavior is consistent across all time boundaries (day/month/year changes) because the API treats time as a continuous numerical sequence of milliseconds since the Unix epoch, with no special handling for calendar boundaries.

## Reference Implementation

The `time_alignment.py` module in our codebase implements these concepts with the `get_time_boundaries()` function:

```python
def get_time_boundaries(start_time: datetime, end_time: datetime, interval: Interval) -> Dict[str, Any]:
    """Get detailed time boundary information with Binance API boundary handling."""
    # Apply time window adjustment
    adjusted_start, adjusted_end = adjust_time_window(start_time, end_time, interval)

    # Calculate interval details
    interval_seconds = interval.to_seconds()
    interval_ms = interval_seconds * 1000
    interval_micros = interval_seconds * 1_000_000

    # Calculate timestamps for API calls - API will handle boundary alignment
    start_ms = int(adjusted_start.timestamp() * 1000)
    end_ms = int(adjusted_end.timestamp() * 1000)

    # Calculate expected records
    expected_records = (
        int((adjusted_end - adjusted_start).total_seconds()) // interval_seconds
    )

    return {
        "adjusted_start": adjusted_start,
        "adjusted_end": adjusted_end,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "expected_records": expected_records,
        "interval_ms": interval_ms,
        "interval_micros": interval_micros,
        "boundary_type": "inclusive_start_exclusive_end",
    }
```

## Best Practices

1. **Alignment Awareness**:

   - Always be aware that timestamps will be aligned to interval boundaries
   - Design queries with these alignment rules in mind

2. **Inclusive Boundaries**:

   - The API treats both startTime and endTime as inclusive after its internal boundary alignment
   - If you use an exclusive end time model in your application, adjust accordingly

3. **Testing with Curl**:

   - When debugging time-related issues, use curl to directly test API behavior
   - Include millisecond precision in test cases to verify boundary handling

4. **Validation**:

   - Always validate received data to ensure you got the expected time range
   - Check first and last timestamps to confirm proper boundary handling

5. **API Limits**:
   - The default limit is 500 candles per request
   - Use the `limit=1000` parameter to retrieve up to 1000 candles in a single request
   - 1000 is a strict maximum - requesting more than 1000 candles (e.g., limit=1001, limit=5000) will still return exactly 1000 candles
   - Plan your data retrieval strategy with appropriate chunking for larger ranges

## Conclusion

The Binance REST API's handling of time boundaries is consistent and follows logical principles for financial time-series data. By understanding its boundary alignment behavior and applying appropriate handling in your application, you can ensure accurate and consistent time-series data retrieval across all time periods, including day, month, and year boundaries.

This document is based on extensive testing with both current and historical data across multiple interval types and calendar boundaries, providing a reliable reference for working with the Binance API's time-series data endpoints.
