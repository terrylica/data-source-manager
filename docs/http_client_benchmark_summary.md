# HTTP Client Benchmark Results and Best Practices

## Overview

This document summarizes our benchmarking of HTTP client libraries for three critical operations with Binance Vision data:

1. Checking URL availability in the Binance Vision data API
2. Downloading data files at maximum speed
3. Comparing performance across different data granularities (1s for spot and 1m for futures)

## Key Recommendations

Based on our comprehensive testing, here are our key recommendations:

1. **Use `curl_cffi` with AsyncSession for optimal maintainability and performance**

   - AsyncSession provides similar or better performance than the synchronous API in most cases
   - The `async`/`await` pattern offers better maintainability, resource management, and composability
   - Lower CPU usage with better connection pooling
   - Excellent for both spot (1s) and futures (1m) data
   - Prefer AsyncSession for new code even if you're not yet using other async libraries

2. **Use the "download-first" approach rather than checking before downloading**

   - 2.2-2.4x faster than separate check-then-download
   - Detects non-existent files 10-15% faster
   - Simplifies code and improves performance

3. **Use concurrency for multiple file downloads**

   - AsyncSession with semaphores provides clean concurrency control
   - Use concurrency level 50 for optimal performance with multiple files
   - Adjust concurrency based on batch size:
     - Small batches (1-10 files): concurrency 10
     - Medium batches (11-50 files): concurrency 50
     - Large batches (50+ files): concurrency 50-100

4. **Configure timeouts appropriately**
   - 3.0 seconds is optimal for Binance Vision API
   - No need for retries in most cases

## Libraries Tested

We benchmarked the following HTTP client libraries:

1. **curl_cffi (sync & async)** - Python bindings for libcurl via CFFI
2. **httpx** - Modern async-compatible HTTP client
3. **aiohttp** - Popular async HTTP client
4. **AWS CLI** - Command-line interface for AWS
5. **boto3/s3fs** - AWS SDK for Python/Filesystem interface to S3
6. **tls_client** - TLS fingerprinting client

## Latest Granularity Benchmarks

Our latest benchmarks included a comparison of performance with different data granularities:

### Spot Data (1s granularity)

- With 5 files (1 symbol × 5 dates):
  - curl_cffi AsyncSession: 0.9351s at concurrency 50
  - curl_cffi synchronous: 0.9071s at concurrency 100
  - httpx: 0.9169s at concurrency 50
  - AWS CLI: 1.3102s at concurrency 100

### Combined Spot (1s) and Futures (1m) Data

- With 4 files (2 symbols × 1 date × 2 markets):
  - curl_cffi AsyncSession: 0.745s at concurrency 50 (12% faster than sync version)
  - curl_cffi synchronous: 0.831s at concurrency 50
  - httpx: 0.853s at concurrency 50
  - AWS CLI: 1.551s at concurrency 50

### AWS CLI Comparison

- AWS CLI was significantly slower, especially at lower concurrency levels
- AWS CLI showed dramatic improvement from concurrency 10 to 50 (5.36s → 1.68s)
- All methods achieved 100% success rate on valid files

## Part 1: URL Availability Checking

### Testing Methodology

The benchmarking involved several dimensions:

1. **Approaches tested:**

   - Traditional check-then-download (HEAD request followed by GET if available)
   - Download-first (direct GET without checking first)
   - Partial download (range request for first 1KB to quickly detect availability)

2. **Request patterns:**
   - With and without retry logic
   - HEAD vs GET requests
   - Various timeout values (0.5s, 2.0s, 3.0s, 5.0s)

### Results for URL Availability Checking

**For Download-First vs Check-Then-Download:**

- **Download-first approach is 2.2-2.4x faster** for existing files
- Download-first approach detects non-existent files 10-15% faster
- Small downloads (partial content) offered minimal benefits over direct downloads

**For Individual Clients:**

- curl_cffi showed dramatically faster individual request times in micro-benchmarks
- Individual HEAD requests completed in ~0.001s with curl_cffi vs ~0.3s with httpx/aiohttp
- For complete URL availability checking applications, network latency dominates
- curl_cffi showed lower CPU usage (7-9% vs 10-13% for aiohttp)

**For Retry vs No-Retry:**

- No-retry implementations were 15-20% faster
- Both achieved 100% success rate with proper timeout settings
- Retry logic only valuable for unstable networks

## Part 2: File Download Performance

### Testing Methodology for File Downloads

We tested download performance using multiple approaches:

1. **Different download methods**
   - Single file downloads with various clients
   - Concurrent downloads (4, 10, 50, 100 parallel downloads)
   - Various chunk sizes (256KB, 1MB, 8MB, 16MB)
   - Different data granularities (1s for spot and 1m for futures)

### Results for Download Performance

**Async vs Synchronous Downloads:**

- Performance comparisons between curl_cffi AsyncSession and synchronous API showed mixed results
- AsyncSession performed 5-10% better in specific workloads and configurations
- Both versions performed best at concurrency 50-100, with diminishing returns beyond that
- AsyncSession provides cleaner code and better maintainability for all applications

**Concurrency vs Single-threaded Downloads:**

- AsyncSession with concurrency control showed significant speedups
- AWS CLI showed dramatic improvement from concurrency 10 to 50 (5.36s → 1.68s), but limited gains beyond that

**Other Findings:**

- 1MB chunk size was optimal for curl_cffi
- All methods performed consistently across both spot (1s) and futures (1m) data types
- Network bandwidth, not disk I/O, was the primary bottleneck

## Implementation Examples

### Recommended Implementation (Async Download-First Approach)

```python
import os
import asyncio
from curl_cffi.requests import AsyncSession
from datetime import datetime, timedelta

async def get_latest_data_async(symbol, interval, market="spot", max_days_back=5, output_dir="downloads"):
    """Get the latest available data file using async download-first approach.

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSDT")
        interval: Time interval (e.g., "1h", "1d", "1s" for spot, "1m" for futures)
        market: Market type ("spot", "um" for USDT-M futures, "cm" for COIN-M futures)
        max_days_back: Maximum days to check backward
        output_dir: Directory to save downloaded files

    Returns:
        Tuple of (date found, path to downloaded file) or (None, None) if not found
    """
    os.makedirs(output_dir, exist_ok=True)
    current_date = datetime.utcnow()

    # Handle interval based on market type
    actual_interval = interval
    if market != "spot" and interval == "1s":
        actual_interval = "1m"  # Use 1m for futures markets (minimum granularity)

    # Construct base URL
    base_url = "https://data.binance.vision"
    if market == "spot":
        url_path = f"data/spot/daily/klines/{symbol}/{actual_interval}"
    elif market == "um":
        url_path = f"data/futures/um/daily/klines/{symbol}/{actual_interval}"
    elif market == "cm":
        url_path = f"data/futures/cm/daily/klines/{symbol}/{actual_interval}"
    else:
        raise ValueError(f"Invalid market type: {market}")

    async with AsyncSession() as session:
        for i in range(max_days_back + 1):
            check_date = (current_date - timedelta(days=i)).strftime("%Y-%m-%d")
            url = f"{base_url}/{url_path}/{symbol}-{actual_interval}-{check_date}.zip"
            output_path = os.path.join(output_dir, f"{symbol}-{actual_interval}-{check_date}.zip")

            try:
                response = await session.get(url, timeout=3.0)

                if response.status_code == 200:
                    # File exists and download was successful
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    return check_date, output_path

            except Exception:
                # Continue to next date on error
                continue

    return None, None

async def download_multiple_files_async(url_list, output_dir="downloads", max_concurrent=50):
    """Download multiple files concurrently using curl_cffi's AsyncSession.

    Args:
        url_list: List of URLs to download
        output_dir: Directory to save downloaded files
        max_concurrent: Maximum number of concurrent downloads
                        (adjust based on batch size)

    Returns:
        List of successfully downloaded file paths
    """
    os.makedirs(output_dir, exist_ok=True)
    successful_downloads = []

    # Adjust concurrency based on number of files
    batch_size = len(url_list)
    if batch_size <= 10:
        # Small batch optimization
        adjusted_concurrency = min(10, max_concurrent)
    elif batch_size <= 50:
        # Medium batch optimization (optimal concurrency)
        adjusted_concurrency = min(50, max_concurrent)
    else:
        # Large batch optimization
        adjusted_concurrency = min(100, max_concurrent)

    # Use semaphore to limit concurrency
    sem = asyncio.Semaphore(adjusted_concurrency)

    async def download_single_file(url):
        async with sem:
            try:
                filename = os.path.basename(url)
                output_path = os.path.join(output_dir, filename)

                async with AsyncSession() as session:
                    response = await session.get(url, timeout=3.0)

                    if response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            f.write(response.content)
                        return output_path
            except Exception:
                return None

    # Create tasks for all URLs
    tasks = [download_single_file(url) for url in url_list]

    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks)

    # Filter successful downloads
    successful_downloads = [path for path in results if path]

    return successful_downloads
```

### Integration with Synchronous Applications

If you need to use these async functions in a synchronous context:

```python
import asyncio

def find_latest_data(symbol, interval, market="spot", max_days_back=5, output_dir="downloads"):
    """Synchronous wrapper around the async get_latest_data_async function."""
    return asyncio.run(get_latest_data_async(symbol, interval, market, max_days_back, output_dir))

def download_multiple_files(url_list, output_dir="downloads", max_concurrent=50):
    """Synchronous wrapper around the async download_multiple_files_async function."""
    return asyncio.run(download_multiple_files_async(url_list, output_dir, max_concurrent))
```

## Conclusion

Our comprehensive benchmarking shows that:

1. **curl_cffi with AsyncSession** provides the best combination of performance and maintainability
2. The **async API** offers better code organization, resource management, and composability
3. The **download-first approach** is significantly faster than checking before downloading
4. **Concurrency level 50-100** provides the optimal performance for multiple downloads
5. **AWS CLI** can be an alternative when integrating with other AWS services, but with significantly lower performance
6. Optimal **timeout settings** (3.0s) and no retries are suitable for most applications

By implementing these best practices, applications can achieve:

- Up to 2.4x faster file availability checking
- Up to 10% faster downloads with AsyncSession in specific workloads
- Consistent performance across different data granularities (1s for spot and 1m for futures)
- More maintainable code with the async download-first approach
