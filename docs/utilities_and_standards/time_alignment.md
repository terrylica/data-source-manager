# Time Alignment in Data Services

## Overview

This document explains the standardized approach to time alignment in the data services codebase. Time alignment is critical for ensuring consistent handling of time boundaries across different components of the system.

## Core Principles

1. **REST API Behavior is the Source of Truth** - The Binance REST API's boundary behavior is our definitive standard
2. **No Manual Alignment for REST API Calls** - We rely on the REST API's documented boundary behavior instead of manual alignment
3. **Manual Alignment for Vision API and Cache** - We implement manual time alignment for Vision API and cache to match REST API behavior
4. **Validation Against Real API** - All alignment logic is verified through integration tests against the actual Binance REST API

## Alignment Rules (As per Binance REST API)

1. **The API completely ignores millisecond precision** - It operates exclusively on interval boundaries
2. **Start time boundary rounding** - Start timestamps are rounded UP to the next interval boundary if not exactly on a boundary
3. **End time boundary rounding** - End timestamps are rounded DOWN to the previous interval boundary if not exactly on a boundary
4. **Both boundaries are inclusive** - After API boundary alignment, both start and end times are inclusive
5. **No special handling at time boundaries** - The API maintains perfect continuity across all time boundaries (second, minute, hour, day, month, year)

## Centralized Validation Class

The `ApiBoundaryValidator` class in `utils/api_boundary_validator.py` is responsible for validating time boundaries and data ranges against the Binance REST API. It provides methods to:

- Validate if a given time range and interval are valid
- Determine actual boundaries returned by the API
- Validate if a DataFrame's time range matches what is expected from the API

## Implementation Strategy

### For REST API Calls

- Pass timestamps directly to the API without manual alignment
- Let the API handle boundary alignment according to its rules

### For Vision API and Cache Operations

- Implement manual time alignment that mirrors REST API behavior
- Use `ApiBoundaryValidator` to verify alignment correctness
- Ensure caching strategy aligns with API boundary behavior

## Example

For a query requesting data from `2023-01-01T10:15:30.123Z` to `2023-01-01T10:25:45.789Z` with 1-minute interval:

1. **API Aligned timestamps**:

   - Aligned start: `2023-01-01T10:16:00.000Z` (rounded UP from 10:15:30.123)
   - Aligned end: `2023-01-01T10:25:00.000Z` (rounded DOWN from 10:25:45.789)

2. **Records returned by API**: 10 candles (inclusive of both boundaries)
   - First candle: `10:16:00`
   - Last candle: `10:25:00`

## Testing and Verification

All time alignment logic is tested via integration tests against the actual Binance REST API to ensure accuracy. These tests verify:

1. **Exact boundary handling** - Tests timestamps at exact interval boundaries
2. **Millisecond precision** - Tests timestamps with millisecond components
3. **Cross-boundary behavior** - Tests timestamps that cross day, month, and year boundaries
4. **Vision API and cache alignment** - Tests that manual alignment matches REST API behavior

## References

- [Binance REST API Boundary Behavior](../api/binance_rest_api_boundary_behaviour.md)
- [API Boundary Validator](../../utils/api_boundary_validator.py)
