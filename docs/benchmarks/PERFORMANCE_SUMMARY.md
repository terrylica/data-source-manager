# Performance Benchmark Summary: Pandas vs Polars FCP Path

**Date**: 2026-02-05

<!-- SSoT-OK: Version references are documentation of test environment -->

**CKVD Version**: 2.0.2
**Test Environment**: macOS darwin/arm64

---

## Executive Summary

The Polars Pipeline implementation provides **significant performance improvements** over the legacy Pandas FCP path:

| Metric              | Result           |
| ------------------- | ---------------- |
| **Overall Speedup** | **6.35x faster** |
| **Memory Savings**  | **92.1% less**   |
| **Best Case**       | 11.64x faster    |

---

## Detailed Benchmark Results

### Test Scenarios (BTCUSDT, 1-hour interval)

| Scenario    | Rows  | Pandas Time | Polars Time | Speedup | Pandas Memory | Polars Memory |
| ----------- | ----- | ----------- | ----------- | ------- | ------------- | ------------- |
| Small (1d)  | 24    | 0.353s      | 0.030s      | 11.64x  | 64.74 MB      | 0.62 MB       |
| Medium (7d) | 168   | 0.041s      | 0.033s      | 1.24x   | 0.62 MB       | 0.62 MB       |
| Large (30d) | 720   | 0.105s      | 0.062s      | 1.69x   | 1.02 MB       | 0.62 MB       |
| XL (90d)    | 2,160 | 1.774s      | 0.168s      | 10.53x  | 5.38 MB       | 1.49 MB       |
| XXL (180d)  | 4,320 | 1.991s      | 0.377s      | 5.29x   | 6.58 MB       | 2.82 MB       |

### Averages

| Metric | Pandas   | Polars  | Improvement |
| ------ | -------- | ------- | ----------- |
| Time   | 0.853s   | 0.134s  | 6.35x       |
| Memory | 15.67 MB | 1.23 MB | 92.1%       |

---

## Analysis by Data Size

### Small Requests (1-7 days, <200 rows)

- **Speedup**: 1.24x - 11.64x
- **Memory**: ~100x improvement for cold start
- **Observations**: The first request (cold start) shows dramatic improvement because Polars avoids pandas DataFrame initialization overhead

### Medium Requests (30 days, ~720 rows)

- **Speedup**: 1.69x
- **Memory**: 39% improvement
- **Observations**: Cache is warm, so improvement comes from processing efficiency

### Large Requests (90-180 days, 2,000-4,000+ rows)

- **Speedup**: 5.29x - 10.53x
- **Memory**: 57-72% improvement
- **Observations**: Polars shines at scale - lazy evaluation and streaming engine excel with larger datasets

---

## Why Polars is Faster

1. **Lazy Evaluation**: Operations are optimized and combined before execution
2. **Predicate Pushdown**: Filters applied at scan time, not after loading
3. **Streaming Engine**: `engine='streaming'` processes data in batches
4. **Zero-Copy Operations**: Arrow IPC files read directly without copying
5. **No Index Overhead**: Unlike pandas, Polars doesn't maintain a separate index

---

## Memory Efficiency Analysis

```
Pandas Memory Profile:
- DataFrame allocation: 3-5 MB baseline
- Index construction: Additional overhead
- Column operations: Copies on modification
- Result: Memory grows with data size

Polars Memory Profile:
- LazyFrame: Near-zero until collect()
- Memory-mapped IPC: Zero-copy reads
- Expression-based: No intermediate copies
- Result: Minimal memory footprint
```

---

## Recommendations

### Polars Pipeline (Always Active)

The Polars pipeline is always active — no configuration needed.
The `USE_POLARS_PIPELINE` flag was removed (see CHANGELOG for details).

### For Maximum Performance

```python
# Use return_polars=True for zero-copy output
df = manager.get_data(
    symbol="BTCUSDT",
    start_time=start,
    end_time=end,
    interval=Interval.HOUR_1,
    return_polars=True  # Skip pandas conversion
)
```

## Test Configuration

- **Pipeline**: Polars (always active)
- **Symbol**: BTCUSDT (Binance USDT-margined futures)
- **Interval**: 1 hour
- **Data Source**: Cache (for consistent comparison)
- **Memory Tracking**: Python tracemalloc

---

## Conclusion

The Polars Pipeline provides substantial improvements:

- **6.35x faster** average execution time
- **92.1% less** memory usage
- **Scales better** with larger data requests

The implementation is production-ready and enabled by default.
