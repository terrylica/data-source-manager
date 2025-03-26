# Overview

This document details the timestamp behavior of the Binance API. Understanding these behaviors is crucial for accurate data collection and processing.

## Key Behaviors

### 1. Millisecond Precision

#### Timestamp Alignment

- The API completely ignores millisecond precision in timestamps
- It operates exclusively on interval boundaries
- Start timestamps are rounded UP to the next interval boundary if not exactly on a boundary
- End timestamps are rounded DOWN to the previous interval boundary if not exactly on a boundary
- For 1-second intervals: aligned to whole seconds
- For 1-minute intervals: aligned to whole minutes
- For other intervals: aligned to their respective boundaries

#### Bar Boundaries

- Each bar represents exactly one complete interval
- For 1-second intervals:
  - Bar open: Always at exact second boundary (`.000` ms)
  - Bar close: 999ms after the open time
  - Example: Open: `2024-01-01 00:00:00.000`, Close: `2024-01-01 00:00:00.999`

### 2. Timestamp Inclusivity

#### Request Windows

- After API boundary alignment:
  - Start time is inclusive (`>=`)
  - End time is inclusive (`<=`)
- This behavior is consistent across all interval types
- The API treats both boundaries as inclusive after its internal alignment

#### Edge Cases

- A timestamp of `23:59:59.999` as startTime will be treated as the next second (`00:00:00`)
- A timestamp of `00:00:00.001` as endTime will be treated as the current second (`00:00:00`)
- The API maintains perfect continuity across all time boundaries (second, minute, hour, day, month, year)

### 3. Cross-Boundary Behavior

- The API handles data queries that cross significant time boundaries (midnight, year) with complete continuity
- No special handling or gaps occur at any boundary
- Millisecond precision is handled consistently with the same rounding rules
- The behavior is identical across day, month, and year boundaries

### 4. Record Counting Logic

For a given time range with start time `S` and end time `E` for interval `I`:

1. After boundary alignment (rounding up start, rounding down end)
2. The API will return approximately `(E - S)/I + 1` records
3. The exact count may differ due to:
   - Missing data points (no trading during certain intervals)
   - API limits (default 500 records per request, maximum 1000 with `limit` parameter)
   - Boundary rounding effects

## Implementation Considerations

### 1. Time Window Validation

- **For REST API calls**: Do not perform manual time alignment. The API handles this automatically.
- **For Vision API and cache operations**: Implement manual time alignment that mirrors the REST API behavior.

### 2. Chunk Size Calculation

```python
def calculate_chunks(start_ms: int, end_ms: int, interval: Interval) -> List[Tuple[int, int]]:
    """Calculate chunk ranges based on start and end times."""
    chunks = []
    current_start = start_ms
    while current_start < end_ms:
        chunk_end = min(current_start + CHUNK_SIZE_MS - 1, end_ms)
        chunks.append((current_start, chunk_end))
        current_start = chunk_end + 1
    return chunks
```

## Best Practices

1. **API Calls**

   - For REST API: Pass timestamps directly without manual alignment
   - For Vision API and cache: Implement manual time alignment to match REST API behavior

2. **Time Validation**

   - Use `ApiBoundaryValidator` to validate time boundaries and data ranges
   - Verify all alignment logic through integration tests against the REST API

3. **Data Processing**

   - Parse API responses with the understanding of the API's boundary behavior
   - First timestamp will be >= aligned start time (possibly rounded up by API)
   - Last timestamp will be <= aligned end time (rounded down by API)

4. **API Limits**
   - Default limit: 500 candles per request
   - Maximum limit: 1000 candles (use `limit=1000` parameter)
   - Plan data retrieval with appropriate chunking for larger ranges

## References

- [Binance REST API Boundary Behavior](binance_rest_api_boundary_behaviour.md)
- [Time Alignment Roadmap](../roadmap/revamp_time_alignment.md)
- [Binance API Documentation](https://binance-docs.github.io/apidocs/spot/en/)
