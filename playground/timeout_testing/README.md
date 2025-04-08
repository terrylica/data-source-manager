# Timeout Testing Playground

This directory contains scripts and utilities for testing and demonstrating the timeout handling improvements in the `DataSourceManager` class. The enhancements focus on properly handling background tasks from the `curl_cffi` library to prevent false timeout errors.

## Background

The `curl_cffi` library is used as an HTTP client for improved performance, but it sometimes leaves background tasks running after a request completes. When these tasks aren't properly cleaned up, they can cause:

1. False timeout errors
2. Resource leaks
3. Event loop pollution
4. Unpredictable behavior in subsequent operations

## Fix Implementation

The fix involves several key improvements:

1. **Enhanced Task Cleanup**: Proactively identifying and cancelling lingering `curl_cffi` tasks
2. **Improved Logging**: Adding detailed diagnostic logging for timeout incidents with context
3. **Resource Management**: Properly closing HTTP clients and cleaning up resources
4. **Context-Specific Timeouts**: Moving from global wrapper timeouts to operation-specific timeouts

## Test Scripts

This directory contains the following test scripts:

### 1. `verify_data_retrieval.py`

A comprehensive verification script that tests data retrieval with the timeout fixes:

- Tests sequential data retrieval for multiple symbols
- Tests concurrent data retrieval with multiple parallel operations
- Tests extended historical data retrieval
- Tests retrieval of very recent data that may not be fully consolidated
- Tests partial data retrieval spanning from available past data to recent data
- Captures and analyzes warnings and errors

### 2. `demonstrate_timeout_fix.py`

A script specifically designed to demonstrate the robustness of the timeout fix by:

- Running multiple concurrent operations with different symbols and time ranges
- Testing sequential operations with cleanup in between
- Verifying that no false timeouts occur
- Testing proper resource cleanup and management

### 3. `data_retrieval_samples.py`

A comprehensive demo script showing:

- Retrieving spot data at 1-minute intervals
- Retrieving futures data at 1-minute intervals
- Working with multiple market types
- Different approaches to data retrieval (direct, fluent API, context manager)

## Running the Tests

To run the demonstration scripts:

```bash
# Run the comprehensive verification
python playground/timeout_testing/verify_data_retrieval.py

# Run the timeout fix demonstration
python playground/timeout_testing/demonstrate_timeout_fix.py

# Run the data retrieval samples
python playground/timeout_testing/data_retrieval_samples.py
```

## Timeout Logs

Timeout incidents are logged to `logs/timeout_incidents/timeout_log.txt` with detailed diagnostic information including:

- Timestamp
- Operation context
- Input parameters
- Task information
- Event loop state

## Key Improvements

1. **Reliability**: Eliminated false timeout errors
2. **Performance**: Maintained original timeout duration for genuinely slow operations
3. **Resource Efficiency**: Prevented resource leaks from lingering tasks
4. **Diagnostics**: Enhanced logging for better troubleshooting
5. **Robustness**: Improved overall stability for long-running applications
