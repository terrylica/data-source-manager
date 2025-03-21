# DataSourceManager Boundary Conditions

This document explains the time alignment behavior in the DataSourceManager.

## Time Adjustment Rules

The `adjust_time_window` function in `time_alignment.py` follows these key rules:

1. Start times are ALWAYS rounded DOWN to include the full interval
2. End times are rounded DOWN to the current interval (exclusive - the end interval is not included)
3. Start timestamp is inclusive, end timestamp is exclusive

This means that for a timestamp range:

- `[10.5s, 15.0s]` → Records for seconds 10, 11, 12, 13, 14 (not 15)
- `[10.0s, 15.0s]` → Records for seconds 10, 11, 12, 13, 14 (not 15)
- `[10.5s, 15.5s]` → Records for seconds 10, 11, 12, 13, 14 (not 15)

## Benefits of this Approach

### 1. Inclusive Start Time (Always Floor)

By always flooring the start time regardless of microseconds, we ensure:

- More comprehensive data inclusion
- Consistent start point regardless of microsecond precision
- Better alignment with historical data retrieval needs

For example, if requesting data from 10.5s, we include the full 10s interval because:

- The data for that interval is already complete
- Including more data is preferable to missing data

### 2. Exclusive End Time

By making the end time exclusive (not including the end interval):

- We avoid including potentially incomplete intervals
- We match common programming paradigms where ranges are [inclusive, exclusive)
- We get consistent behavior regardless of microsecond precision in the end time

For example, requesting data up to 15.0s means we include data up to but not including the 15s interval, because that interval might not be fully formed.

## Test Cases and Expected Results

With this approach, all our test cases now have consistent behavior:

1. **Case 1** (microseconds in both start and end):

   - Start: `base_time - 10.5s` → Floored to 10s
   - End: `base_time - 5.25s` → Floored to 5s (exclusive)
   - Expected: 5 records (10, 11, 12, 13, 14)

2. **Case 2** (exact second boundaries):

   - Start: `base_time - 10.0s` → Already at 10s
   - End: `base_time - 5.0s` → Stays at 5s (exclusive)
   - Expected: 5 records (10, 11, 12, 13, 14)

3. **Case 3** (microsecond at start only):

   - Start: `base_time - 10.5s` → Floored to 10s
   - End: `base_time - 5.0s` → Stays at 5s (exclusive)
   - Expected: 5 records (10, 11, 12, 13, 14)

4. **Case 4** (microsecond at end only):
   - Start: `base_time - 10.0s` → Already at 10s
   - End: `base_time - 5.25s` → Floored to 5s (exclusive)
   - Expected: 5 records (10, 11, 12, 13, 14)

## Implementation

The adjustment is done in the `adjust_time_window` function:

```python
# For start time: ALWAYS floor
adjusted_start = get_interval_floor(start_time, interval)

# For end time: Use floor time directly (exclusive end)
adjusted_end = get_interval_floor(end_time, interval)
```

## Benefits Over Previous Approach

The previous approach had inconsistent behavior when timestamps contained microseconds:

- Start times with microseconds were rounded UP
- End times with microseconds were treated inconsistently
- Both boundaries were inclusive, leading to varying record counts

The new approach ensures:

1. Consistent record counts for the same time span
2. More predictable and intuitive behavior
3. Better alignment with historical data retrieval needs
