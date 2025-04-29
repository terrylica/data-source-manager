# OKX Data Download Guide

## Overview

This document provides information about OKX's historical market data available through their Alibaba OSS-backed CDN and REST API. OKX offers various datasets for download through their data download page at [https://www.okx.com/data-download](https://www.okx.com/data-download) and through their public REST API endpoints.

## Data Structure

Based on our investigation, OKX historical data follows this hierarchical structure:

```
https://www.okx.com/cdn/okex/traderecords/
├── trades/
│   └── daily/
│       └── YYYYMMDD/
│           └── SYMBOL-PAIR-trades-YYYY-MM-DD.zip
└── aggtrades/
    └── daily/
        └── YYYYMMDD/
            └── SYMBOL-PAIR-aggtrades-YYYY-MM-DD.zip
```

### URL Pattern

The URL pattern for accessing specific files follows this format:

- Trades: `https://www.okx.com/cdn/okex/traderecords/trades/daily/{date}/{symbol}-trades-{formatted-date}.zip`
- Aggregate Trades: `https://www.okx.com/cdn/okex/traderecords/aggtrades/daily/{date}/{symbol}-aggtrades-{formatted-date}.zip`

Where:

- `{date}` is in format `YYYYMMDD` (e.g., 20250419)
- `{formatted-date}` is in format `YYYY-MM-DD` (e.g., 2025-04-19)
- `{symbol}` is the trading pair (e.g., BTC-USDT)

## Available Data Types

From our exploration, we've identified these main data types:

1. **Trade Data (`trades`)**:

   - Individual trade records
   - Example: `BTC-USDT-trades-2025-04-19.zip`
   - Contains: trade_id, side, size, price, created_time

2. **Aggregate Trade Data (`aggtrades`)**:

   - Aggregated trade data that might combine multiple trades
   - Example: `BTC-USD-250926-aggtrades-2025-04-23.zip`
   - Contains: trade_id, side, size, price, created_time

3. **Candlestick Data (REST API)**:
   - Time-based OHLCV data available via REST API
   - Available for both SPOT (e.g., BTC-USDT) and SWAP (e.g., BTC-USD-SWAP) instruments
   - Supports multiple time intervals
   - Provides both current and historical data

Note: Directory listings are disabled on the CDN, so direct browsing of available files is not possible.

## Symbol Formatting

OKX uses a specific format for symbols that differs from some other exchanges:

### SPOT Markets

- Format: `BASE-QUOTE` (e.g., `BTC-USDT`)
- Examples: `BTC-USDT`, `ETH-USDT`, `SOL-USDT`
- Note: Binance-style symbols like `BTCUSDT` need to be converted to `BTC-USDT` format for OKX

### Perpetual Futures (SWAP) Markets

- Format: `BASE-USD-SWAP` (e.g., `BTC-USD-SWAP`)
- Examples: `BTC-USD-SWAP`, `ETH-USD-SWAP`, `SOL-USD-SWAP`
- Note: Binance-style symbols like `BTCUSDT` need to be converted to `BTC-USD-SWAP` format for OKX futures

## Data Format

### Trade Data CSV Format

Based on our sample investigation, the CSV files within the zip archives have the following structure:

```
trade_id/交易id,side/交易方向,size/数量,price/价格,created_time/成交时间
719977054,buy,0.00527188,84760.0,1745034103856
719977057,buy,0.0277,84760.0,1745034103856
...
```

Field descriptions:

- `trade_id`: Unique identifier for the trade
- `side`: Trade direction (buy/sell)
- `size`: Trade quantity
- `price`: Trade price
- `created_time`: Unix timestamp in milliseconds

### Aggregate Trade Data CSV Format

Similar to trade data but may represent aggregated trades:

```
trade_id/交易id,side/交易方向,size/数量,price/价格,created_time/成交时间
1236992,sell,50.0,93314.4,1745339279777
1236999,sell,7.0,93315.9,1745339283134
...
```

## Accessing the Data

### Direct Download

To download specific data files, use `curl` or any HTTP client:

```bash
curl -O https://www.okx.com/cdn/okex/traderecords/trades/daily/20250419/BTC-USDT-trades-2025-04-19.zip
```

### Processing Downloaded Data

1. Unzip the downloaded file:

   ```bash
   unzip BTC-USDT-trades-2025-04-19.zip -d extracted_data
   ```

2. The CSV file can then be processed using standard data analysis tools such as pandas:

   ```python
   import pandas as pd

   # Load the CSV file
   df = pd.read_csv('extracted_data/BTC-USDT-trades-2025-04-19.csv')

   # Display basic information
   print(df.info())
   print(df.head())
   ```

## REST API Access

OKX provides a comprehensive REST API for accessing market data in real-time. This section details the REST endpoints for fetching candlestick data for both SPOT and SWAP instruments.

### REST API Endpoints

The primary endpoints for candlestick data are:

1. **Current Candles**: `https://www.okx.com/api/v5/market/candles`

   - Returns the most recent candlestick data for a given instrument and interval

2. **Historical Candles**: `https://www.okx.com/api/v5/market/history-candles`
   - Returns historical candlestick data for a given instrument and interval
   - Allows fetching data from specific timestamps

### Supported Time Intervals

Both SPOT and SWAP instruments support the following time intervals:

| Interval | Description | Parameter Value |
| -------- | ----------- | --------------- |
| 1m       | 1 minute    | `1m`            |
| 3m       | 3 minutes   | `3m`            |
| 5m       | 5 minutes   | `5m`            |
| 15m      | 15 minutes  | `15m`           |
| 30m      | 30 minutes  | `30m`           |
| 1H       | 1 hour      | `1H`            |
| 2H       | 2 hours     | `2H`            |
| 4H       | 4 hours     | `4H`            |
| 6H       | 6 hours     | `6H`            |
| 12H      | 12 hours    | `12H`           |
| 1D       | 1 day       | `1D`            |
| 1W       | 1 week      | `1W`            |
| 1M       | 1 month     | `1M`            |

### Request Parameters

#### Candles Endpoint

```
GET https://www.okx.com/api/v5/market/candles
```

Required parameters:

- `instId`: Instrument ID (e.g., `BTC-USDT` for SPOT, `BTC-USD-SWAP` for SWAP)
- `bar`: Time interval (e.g., `1m`, `1D`)

Optional parameters:

- `limit`: Number of candles to return (default: 100, max: 300)
- `before`: Pagination of data before a timestamp (Unix timestamp in milliseconds)
- `after`: Pagination of data after a timestamp (Unix timestamp in milliseconds)

#### History Candles Endpoint

```
GET https://www.okx.com/api/v5/market/history-candles
```

Required parameters:

- `instId`: Instrument ID (e.g., `BTC-USDT` for SPOT, `BTC-USD-SWAP` for SWAP)
- `bar`: Time interval (e.g., `1m`, `1D`)

Optional parameters:

- `limit`: Number of candles to return (default: 100, max: 300)
- `before`: Pagination of data before a timestamp (Unix timestamp in milliseconds)
- `after`: Pagination of data after a timestamp (Unix timestamp in milliseconds)

### Request Limits

Our testing has shown that:

- The maximum number of records returned per request is **300**
- Requesting more than 300 records will still return only 300 records

### Candlestick Data Format

The OKX REST API returns candlestick (Kline) data as an array of arrays in the `data` field. Each sub-array represents a single candlestick with the following structure:

| Index | Field     | Description                      | Type   |
| ----- | --------- | -------------------------------- | ------ |
| 0     | timestamp | Unix timestamp in milliseconds   | string |
| 1     | open      | Opening price                    | string |
| 2     | high      | Highest price                    | string |
| 3     | low       | Lowest price                     | string |
| 4     | close     | Closing price                    | string |
| 5     | volume    | Trading volume                   | string |
| 6     | volumeUSD | Volume in USD                    | string |
| 7     | turnover  | Turnover (quote currency volume) | string |
| 8     | confirm   | Candle confirmation flag         | string |

Note: All fields are returned as strings and need to be converted to appropriate types for processing.

### Sample API Requests

#### Fetching SPOT Data (BTC-USDT)

```bash
# Fetch 1-minute candles for BTC-USDT
curl -H "Accept: application/json" "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1m&limit=100"

# Fetch daily candles for BTC-USDT
curl -H "Accept: application/json" "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1D&limit=100"

# Fetch historical 1-day candles for BTC-USDT from 30 days ago
curl -H "Accept: application/json" "https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT&bar=1D&limit=100&after=1743356217705"
```

#### Fetching SWAP Data (BTC-USD-SWAP)

```bash
# Fetch 1-minute candles for BTC-USD-SWAP
curl -H "Accept: application/json" "https://www.okx.com/api/v5/market/candles?instId=BTC-USD-SWAP&bar=1m&limit=100"

# Fetch daily candles for BTC-USD-SWAP
curl -H "Accept: application/json" "https://www.okx.com/api/v5/market/candles?instId=BTC-USD-SWAP&bar=1D&limit=100"

# Fetch historical 1-day candles for BTC-USD-SWAP from 30 days ago
curl -H "Accept: application/json" "https://www.okx.com/api/v5/market/history-candles?instId=BTC-USD-SWAP&bar=1D&limit=100&after=1743356217928"
```

### Processing API Response in Python

```python
import httpx
import pandas as pd
from datetime import datetime

# Function to fetch candlestick data
def fetch_okx_candles(instrument, interval, limit=100):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": instrument, "bar": interval, "limit": limit}

    response = httpx.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    if data.get("code") == "0":
        # Convert array data to DataFrame
        df = pd.DataFrame(data.get("data", []),
                          columns=["timestamp", "open", "high", "low", "close",
                                  "volume", "volumeUSD", "turnover", "confirm"])

        # Convert types
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
        for col in ["open", "high", "low", "close", "volume", "volumeUSD", "turnover"]:
            df[col] = df[col].astype(float)

        return df
    else:
        raise Exception(f"API error: {data.get('msg')}")

# Example usage
btc_usdt_df = fetch_okx_candles("BTC-USDT", "1D", 30)
btc_swap_df = fetch_okx_candles("BTC-USD-SWAP", "1D", 30)

print(btc_usdt_df.head())
print(btc_swap_df.head())
```

## Limitations

1. **No Directory Listing**: The OKX CDN has directory listings disabled, meaning you cannot browse available files directly.
2. **No API Access**: There is no documented API to programmatically discover available datasets.
3. **Authentication**: The CDN uses Alibaba OSS with authentication, but public access is granted to specific files.
4. **Date Range Constraints**: Files appear to be organized by date, but without documentation on what date ranges are available.
5. **API Request Limit**: The REST API has a limit of 300 records per request.
6. **Data Delay**: Recent data may be delayed or unavailable through the history-candles endpoint.

## Example Use Cases

### Downloading Historical Trade Data for a Specific Day

```bash
# Download trade data for BTC-USDT on April 19, 2025
curl -O https://www.okx.com/cdn/okex/traderecords/trades/daily/20250419/BTC-USDT-trades-2025-04-19.zip

# Unzip the file
unzip BTC-USDT-trades-2025-04-19.zip

# Preview the data
head BTC-USDT-trades-2025-04-19.csv
```

### Batch Downloading Multiple Days

For downloading multiple consecutive days, you can use a script like this:

```bash
#!/bin/bash

# Define parameters
SYMBOL="BTC-USDT"
START_DATE="20250419"
DAYS=5

# Convert to date object for iteration
start_date=$(date -d "${START_DATE:0:4}-${START_DATE:4:2}-${START_DATE:6:2}" +%s)

for (( i=0; i<$DAYS; i++ )); do
  # Calculate current date
  current_date=$(date -d "@$((start_date + i*86400))" +%Y%m%d)
  formatted_date=$(date -d "@$((start_date + i*86400))" +%Y-%m-%d)

  # Build URL
  url="https://www.okx.com/cdn/okex/traderecords/trades/daily/${current_date}/${SYMBOL}-trades-${formatted_date}.zip"

  echo "Downloading $url"
  curl -O "$url"

  # Optional: Extract immediately
  # unzip "${SYMBOL}-trades-${formatted_date}.zip" -d "data/${formatted_date}"
done
```

### Fetching and Comparing SPOT vs SWAP Data

This example shows how to fetch and compare data from both SPOT and SWAP markets for the same asset:

```python
import httpx
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Function to fetch candlestick data
def fetch_okx_candles(instrument, interval, limit=100):
    url = "https://www.okx.com/api/v5/market/candles"
    params = {"instId": instrument, "bar": interval, "limit": limit}

    response = httpx.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    if data.get("code") == "0":
        # Convert array data to DataFrame
        df = pd.DataFrame(data.get("data", []),
                          columns=["timestamp", "open", "high", "low", "close",
                                  "volume", "volumeUSD", "turnover", "confirm"])

        # Convert types
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms")
        for col in ["open", "high", "low", "close", "volume", "volumeUSD", "turnover"]:
            df[col] = df[col].astype(float)

        # Sort by timestamp
        df = df.sort_values("timestamp")

        return df
    else:
        raise Exception(f"API error: {data.get('msg')}")

# Fetch data for both SPOT and SWAP
btc_spot = fetch_okx_candles("BTC-USDT", "1D", 30)
btc_swap = fetch_okx_candles("BTC-USD-SWAP", "1D", 30)

# Plot price comparison
plt.figure(figsize=(12, 6))
plt.plot(btc_spot["timestamp"], btc_spot["close"], label="BTC-USDT (SPOT)")
plt.plot(btc_swap["timestamp"], btc_swap["close"], label="BTC-USD-SWAP (FUTURES)")
plt.title("BTC Price Comparison: SPOT vs SWAP")
plt.xlabel("Date")
plt.ylabel("Price")
plt.legend()
plt.grid(True)
plt.savefig("btc_comparison.png")
plt.close()

# Calculate funding rate (premium/discount)
merged_df = pd.merge(
    btc_spot[["timestamp", "close"]],
    btc_swap[["timestamp", "close"]],
    on="timestamp",
    suffixes=("_spot", "_swap")
)

merged_df["premium"] = (merged_df["close_swap"] - merged_df["close_spot"]) / merged_df["close_spot"] * 100

print("Average Premium/Discount:", merged_df["premium"].mean(), "%")
print("Max Premium:", merged_df["premium"].max(), "%")
print("Max Discount:", merged_df["premium"].min(), "%")
```

## Instrument Analysis

OKX offers both SPOT and SWAP (perpetual futures) instruments for many cryptocurrencies. Our analysis shows that there are 30 cryptocurrencies that have both SPOT-USD and corresponding SWAP-USD-SWAP instruments.

### Key Pairs Available in Both SPOT and SWAP Markets

The following major cryptocurrencies have both SPOT and SWAP instruments available:

- BTC (Bitcoin): `BTC-USDT` and `BTC-USD-SWAP`
- ETH (Ethereum): `ETH-USDT` and `ETH-USD-SWAP`
- SOL (Solana): `SOL-USDT` and `SOL-USD-SWAP`
- TON (TON): `TON-USDT` and `TON-USD-SWAP`
- XRP (Ripple): `XRP-USDT` and `XRP-USD-SWAP`
- DOGE (Dogecoin): `DOGE-USDT` and `DOGE-USD-SWAP`
- ADA (Cardano): `ADA-USDT` and `ADA-USD-SWAP`
- AVAX (Avalanche): `AVAX-USDT` and `AVAX-USD-SWAP`

### Script for Analyzing Available Instruments

For a comprehensive analysis of available instruments, refer to our script (`playground/okx/analyze_instruments.py`) that identifies all cryptocurrencies available in both SPOT and SWAP markets.

## Conclusion

OKX offers comprehensive market data access through both CDN downloads and REST API endpoints. This guide provides a starting point for accessing and using this data based on our testing and exploration.

Key takeaways:

- Use the proper symbol format: `BASE-QUOTE` for SPOT and `BASE-USD-SWAP` for futures
- REST API provides access to candlestick data with up to 300 records per request
- Multiple time intervals are supported, from 1-minute to 1-month
- Both SPOT (USDT) and perpetual futures (USD-SWAP) data is available
- Historical data can be accessed through both CDN downloads and the history-candles endpoint

For the most up-to-date information, check OKX's official documentation or contact their support.

## Further Investigation

Further investigation could involve:

1. Programmatically testing various date ranges to determine data availability
2. Checking for additional data types beyond trades, aggtrades, and candles
3. Exploring other potential hierarchical patterns in the CDN structure
4. Contacting OKX support for official documentation on their historical data
5. Developing comprehensive back-testing frameworks using the available data
