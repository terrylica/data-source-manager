# OKX Data Download Guide

## Overview

This document provides information about OKX's historical market data available through their Alibaba OSS-backed CDN. OKX offers various datasets for download through their data download page at [https://www.okx.com/data-download](https://www.okx.com/data-download).

## Data Structure

Based on our investigation, OKX historical data follows this hierarchical structure:

```url
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

Note: Directory listings are disabled on the CDN, so direct browsing of available files is not possible.

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

## Limitations

1. **No Directory Listing**: The OKX CDN has directory listings disabled, meaning you cannot browse available files directly.
2. **No API Access**: There is no documented API to programmatically discover available datasets.
3. **Authentication**: The CDN uses Alibaba OSS with authentication, but public access is granted to specific files.
4. **Date Range Constraints**: Files appear to be organized by date, but without documentation on what date ranges are available.

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

## Conclusion

OKX offers valuable historical market data through their CDN, but without comprehensive documentation on available datasets or date ranges. This guide provides a starting point for accessing and using the data based on observed patterns and samples. For the most up-to-date information, check OKX's official documentation or contact their support.

## Further Investigation

Further investigation could involve:

1. Programmatically testing various date ranges to determine data availability
2. Checking for additional data types beyond trades and aggtrades
3. Exploring other potential hierarchical patterns
4. Contacting OKX support for official documentation on their historical data
