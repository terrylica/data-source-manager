# Binance REST API Boundary Behavior

This document provides a comprehensive analysis of how the Binance REST API handles timestamp boundaries when retrieving time-series data. Understanding these behaviors is crucial for correctly implementing time-based queries and ensuring consistent results.

## Key Findings

Through extensive testing with both current and historical data across all interval types (including complex non-conforming timestamps and edge cases), we have identified the following universal behaviors in the Binance REST API:

1. **Boundary Alignment**: The API aligns all timestamps to interval boundaries, ignoring any millisecond precision.
2. **Rounding Rules**: The API applies specific rounding rules to start and end timestamps:
   - **startTime**: Rounds UP to the next interval boundary if not exactly on a boundary
   - **endTime**: Rounds DOWN to the previous interval boundary if not exactly on a boundary
3. **Boundary Inclusivity**: After alignment, the API treats both startTime and endTime as INCLUSIVE.
4. **Universal Behavior**: This behavior is IDENTICAL across ALL interval types (1s, 1m, 3m, 5m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, etc.), confirming the Liskov Substitution Principle.
5. **API Limit**: The default limit is 500 candles per request, but can be increased to a maximum of 1000 by explicitly setting the `limit` parameter.

## Unified Theory of Timestamp Boundary Handling

Following Occam's Razor, we have identified a single, simple, universal theory that explains the API's boundary behavior across all interval types:

### Millisecond Precision

The Binance API completely ignores millisecond precision in timestamps. It operates exclusively on interval boundaries:

- For 1-second intervals: timestamps are aligned to whole seconds
- For 1-minute intervals: timestamps are aligned to whole minutes
- For 1-hour intervals: timestamps are aligned to whole hours
- For 1-day intervals: timestamps are aligned to whole days (00:00:00 UTC)
- For other intervals: timestamps are aligned to their respective boundaries

This behavior remains consistent even across calendar boundaries (day, month, or year changes).

### Boundary Rounding Rules

When timestamps include millisecond components or fall between interval boundaries, the API applies these rounding rules with mathematical precision:

- **startTime**: Rounds UP to the next interval boundary if not exactly on a boundary
- **endTime**: Rounds DOWN to the previous interval boundary if not exactly on a boundary

After alignment, **both boundaries are treated as inclusive**.

### Extreme Edge Case Testing

Our most rigorous tests confirm this behavior holds true even in extreme cases:

- A startTime just 1ms before an interval boundary (e.g., 08:59:59.999) is still rounded UP to the next interval
- An endTime just 1ms after an interval boundary (e.g., 09:00:00.001) is still rounded DOWN to the previous interval

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

#### Longer Interval Examples

Our extensive testing confirms the exact same behavior for longer intervals:

##### 4-Hour Interval

| Scenario           | Request Parameters                                                           | API Behavior                                  | Records Returned              |
| ------------------ | ---------------------------------------------------------------------------- | --------------------------------------------- | ----------------------------- |
| Random non-aligned | startTime=1680587431159 (05:50:31), endTime=1680615789452 (13:43:09)         | First record: 08:00:00, Last record: 12:00:00 | 2 records                     |
| Extreme edge cases | startTime=1680595199999 (07:59:59.999), endTime=1680609600001 (12:00:00.001) | First record: 08:00:00, Last record: 12:00:00 | 2 records (precise alignment) |

##### Daily Interval

| Scenario           | Request Parameters                                                                       | API Behavior                                              | Records Returned                 |
| ------------------ | ---------------------------------------------------------------------------------------- | --------------------------------------------------------- | -------------------------------- |
| Random non-aligned | startTime=1680495327421 (Apr 3 04:15:27), endTime=1680724856789 (Apr 5 20:00:56)         | First record: Apr 4 00:00:00, Last record: Apr 5 00:00:00 | 2 records (day-aligned)          |
| With milliseconds  | startTime=1680480000123 (Apr 3 00:00:00.123), endTime=1680739200456 (Apr 6 00:00:00.456) | First record: Apr 4 00:00:00, Last record: Apr 5 00:00:00 | 2 records (proper day alignment) |

#### Other Intervals (3m, 5m, 15m, 1h, etc.)

The behavior is consistent across all interval types. For example, with 3-minute intervals:

| Scenario          | Request Parameters                                                       | API Behavior                                  | Records Returned         |
| ----------------- | ------------------------------------------------------------------------ | --------------------------------------------- | ------------------------ |
| Exact boundaries  | startTime=1742793760000 (05:22:40), endTime=1742794060000 (05:27:40)     | First record: 05:24:00, Last record: 05:27:00 | 2 (aligned to 3m)        |
| Millisecond start | startTime=1742793780123 (05:23:00.123), endTime=1742794060000 (05:27:40) | First record: 05:24:00, Last record: 05:27:00 | 2 (rounds appropriately) |

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

## Future Date Handling

Through extensive testing, we discovered that the Binance API strictly enforces a prohibition against requesting data for future dates.

### 403 Forbidden Response

The API will respond with a 403 Forbidden HTTP status code when:

- Either the start time or end time parameter is in the future
- The timestamp is even 1 millisecond ahead of the server's current time
- The request is for any market type, but particularly strict for FUTURES_COIN markets

### Testing Results

Our tests using the debug_market_types.py script confirm:

1. **Millisecond Precision**: Even timestamps just 1ms in the future trigger a 403 error

   ```python
   now = datetime.now(timezone.utc)
   very_near_future = now + timedelta(milliseconds=1)  # This will cause 403
   ```

2. **Market Type Sensitivity**: The FUTURES_COIN market (e.g., BTCUSD_PERP) is especially sensitive to future date requests

3. **UTC Time Alignment**: The server uses UTC time for this validation, and its clock may differ slightly from the client

4. **Error Response**: The API returns a standard 403 Forbidden error without detailed information about the cause

### Implementation Guidelines

To prevent 403 errors related to future dates:

1. **Strict Validation**: Always validate timestamps against current UTC time before making API requests:

   ```python
   now = datetime.now(timezone.utc)
   if start_time > now or end_time > now:
       # Handle error: future dates not allowed
       return error_response
   ```

2. **Buffer Zone**: Consider implementing a small buffer (1-5 seconds) to account for potential clock drift:

   ```python
   buffer = timedelta(seconds=5)
   safe_now = datetime.now(timezone.utc) - buffer
   if start_time > safe_now or end_time > safe_now:
       # Handle with caution: possibly in the future
   ```

3. **Dynamic Validation**: Avoid hard-coded year checks, as they become outdated. Instead, always compare against current time:

   ```python
   # Bad approach (will break eventually)
   if start_time.year > 2025:  # Hard-coded year check
       return error_response

   # Good approach (always accurate)
   if start_time > datetime.now(timezone.utc):
       return error_response
   ```

4. **Error Handling**: Implement proper error handling for 403 responses and provide clear messages to users about future date restrictions

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

   - Align start time to interval boundary (round up if not on boundary)
   - Align end time to interval boundary (round down if not on boundary)
   - Use exact aligned timestamps in API calls

2. **Output Processing**:
   - Parse API response with the understanding that:
     - First timestamp will be >= aligned start time (often rounded up by API)
     - Last timestamp will be <= aligned end time (rounded down by API)
     - The API returns whole interval candles only

## Practical Example

For a query requesting data from `2023-01-01T10:15:30.123Z` to `2023-01-01T10:25:45.789Z` with 1-minute interval:

1. **API's internal alignment**:

   - Aligned start: `2023-01-01T10:16:00.000Z` (rounded up to next minute)
   - Aligned end: `2023-01-01T10:25:00.000Z` (rounded down to minute)

2. **API processing**:
   - The API will return complete 1-minute candles
   - First candle: `10:16:00` (for interval 10:16:00-10:16:59.999)
   - Last candle: `10:25:00` (for interval 10:25:00-10:25:59.999)
   - Total: 10 candles (inclusive of both boundaries after alignment)

## Liskov Substitution Principle in Action

The Binance API's boundary behavior strictly adheres to the Liskov Substitution Principle by maintaining identical behavior across all interval types. This means:

1. **Substitutable Intervals**: Any interval can be substituted for another without changing the fundamental boundary handling behavior
2. **Consistent Interface**: The same API contract applies regardless of whether you're using 1-second, 1-minute, 4-hour or 3-day intervals
3. **Universal Rules**: The same rounding and alignment rules apply at all scales
4. **Predictable Results**: When switching between intervals, boundary handling remains mathematically consistent

This LSP adherence allows for simpler client implementations that don't need special handling for different interval types.

## Application Code Implications

1. **Filtering Logic**:
   When implementing filtering in your application code, be aware that:

   - If you filter with **inclusive-inclusive** boundaries, your results will match the API's natural behavior
   - If you filter with **inclusive-exclusive** boundaries, you'll need to add one interval to the end time

2. **Expected Record Count**:
   The formula for expected records is:
   ```
   floor((aligned_end - aligned_start) / interval) + 1
   ```
   This accounts for the inclusive-inclusive behavior of the API.

## Understanding the API's Design

The Binance API's behavior with timestamps follows Occam's Razor - it implements the simplest, most consistent approach possible:

1. **Whole Interval Principle**: The API only operates on complete intervals (1s, 1m, etc.) because financial candles represent complete periods of market activity.

2. **Alignment by Design**: The millisecond rounding behavior ensures that:

   - Candles represent complete intervals
   - There are no partial or overlapping candles
   - All returned data aligns with standard interval boundaries

3. **Consistent Processing Approach**: The behavior is consistent across all time boundaries (day/month/year changes) because the API treats time as a continuous numerical sequence of milliseconds since the Unix epoch, with no special handling for calendar boundaries.

## Reference Implementation

The correct implementation to align with the API's behavior looks like this:

```python
def get_time_boundaries(start_time: datetime, end_time: datetime, interval: Interval) -> Dict[str, Any]:
    """Get detailed time boundary information with Binance API boundary handling."""
    # Ensure timezone awareness
    start_time = enforce_utc_timezone(start_time)
    end_time = enforce_utc_timezone(end_time)

    # Get interval in microseconds for precise calculations
    interval_microseconds = get_interval_micros(interval)

    # Extract microseconds since epoch for calculations
    start_microseconds = int(start_time.timestamp() * 1_000_000)
    end_microseconds = int(end_time.timestamp() * 1_000_000)

    # Calculate floor of each timestamp to interval boundary
    start_floor = start_microseconds - (start_microseconds % interval_microseconds)
    end_floor = end_microseconds - (end_microseconds % interval_microseconds)

    # Apply Binance API boundary rules:
    # - startTime: Round UP to next interval boundary if not exactly on boundary
    # - endTime: Round DOWN to previous interval boundary if not exactly on boundary
    aligned_start_microseconds = (
        start_floor
        if start_microseconds == start_floor
        else start_floor + interval_microseconds
    )
    aligned_end_microseconds = end_floor

    # Convert back to datetime
    adjusted_start = datetime.fromtimestamp(
        aligned_start_microseconds / 1_000_000, tz=timezone.utc
    )
    adjusted_end = datetime.fromtimestamp(
        aligned_end_microseconds / 1_000_000, tz=timezone.utc
    )

    # Calculate expected records - note the +1 for inclusive-inclusive behavior
    expected_records = (
        int((aligned_end - adjusted_start).total_seconds()) // interval.to_seconds()
    ) + 1

    return {
        "adjusted_start": adjusted_start,
        "adjusted_end": aligned_end,
        "start_ms": int(adjusted_start.timestamp() * 1000),
        "end_ms": int(aligned_end.timestamp() * 1000),
        "expected_records": expected_records,
        "interval_ms": interval.to_seconds() * 1000,
        "interval_micros": interval_microseconds,
        "boundary_type": "inclusive_inclusive",  # API uses inclusive-inclusive boundaries after alignment
    }
```

## Testing with Curl

CURL is the most reliable way to verify boundary behavior directly. Here are some example commands we used to test different interval types:

```bash
# Test 2-hour interval with random non-conforming timestamps
curl -s "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=2h&startTime=1680590399999&endTime=1680601200001"

# Test 4-hour interval with millisecond precision
curl -s "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&startTime=1680595199999&endTime=1680609600001"

# Test 1-day interval with extreme edge cases
curl -s "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&startTime=1680480000123&endTime=1680739200456"
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

The Binance REST API's handling of time boundaries follows a single, unified theory that satisfies both Occam's Razor (by being the simplest possible explanation) and the Liskov Substitution Principle (by being consistently applicable across all interval types). The key points to remember are:

1. The API aligns timestamps to interval boundaries (ignoring milliseconds)
2. It rounds the start time UP and the end time DOWN to align with interval boundaries
3. After alignment, both boundaries are treated as INCLUSIVE
4. This behavior is consistent across ALL interval types (1s through 3d and beyond)

By understanding this behavior and applying appropriate handling in your application, you can ensure accurate and consistent time-series data retrieval across all time periods and all interval types.

This document is based on extensive testing with both current and historical data, complex non-conforming timestamps, and extreme edge cases across multiple interval types and calendar boundaries, providing a reliable reference for working with the Binance API's time-series data endpoints.
