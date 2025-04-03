# Binance API Rate Limits

This document summarizes rate limiting across different Binance API endpoints, based on empirical testing and direct API queries.

## Methodology

To gather rate limit information, we performed direct queries to each Binance API endpoint's `exchangeInfo` resource using `curl` and filtered the results with `jq` to isolate the rate limit data:

```bash
curl -s "https://api.binance.com/api/v3/exchangeInfo" | jq '.rateLimits'
```

Similar queries were performed against multiple API endpoints to compare rate limit implementations across different Binance market types.

## Rate Limits by API Endpoint

### Spot API (api.binance.com)

```json
[
  {
    "rateLimitType": "REQUEST_WEIGHT",
    "interval": "MINUTE",
    "intervalNum": 1,
    "limit": 6000
  },
  {
    "rateLimitType": "ORDERS",
    "interval": "SECOND",
    "intervalNum": 10,
    "limit": 100
  },
  {
    "rateLimitType": "ORDERS",
    "interval": "DAY",
    "intervalNum": 1,
    "limit": 200000
  },
  {
    "rateLimitType": "RAW_REQUESTS",
    "interval": "MINUTE",
    "intervalNum": 5,
    "limit": 61000
  }
]
```

### USDT-Margined Futures (fapi.binance.com)

```json
[
  {
    "rateLimitType": "REQUEST_WEIGHT",
    "interval": "MINUTE",
    "intervalNum": 1,
    "limit": 2400
  },
  {
    "rateLimitType": "ORDERS",
    "interval": "MINUTE",
    "intervalNum": 1,
    "limit": 1200
  },
  {
    "rateLimitType": "ORDERS",
    "interval": "SECOND",
    "intervalNum": 10,
    "limit": 300
  }
]
```

### Coin-Margined Futures (dapi.binance.com)

```json
[
  {
    "rateLimitType": "REQUEST_WEIGHT",
    "interval": "MINUTE",
    "intervalNum": 1,
    "limit": 2400
  },
  {
    "rateLimitType": "ORDERS",
    "interval": "MINUTE",
    "intervalNum": 1,
    "limit": 1200
  }
]
```

### European Options (eapi.binance.com)

```json
[
  {
    "rateLimitType": "REQUEST_WEIGHT",
    "interval": "MINUTE",
    "intervalNum": 1,
    "limit": 400
  },
  {
    "rateLimitType": "ORDERS",
    "interval": "MINUTE",
    "intervalNum": 1,
    "limit": 100
  },
  {
    "rateLimitType": "ORDERS",
    "interval": "SECOND",
    "intervalNum": 10,
    "limit": 30
  }
]
```

## Rate Limit Types

Binance implements several rate limit types:

1. **REQUEST_WEIGHT**: Weight-based rate limiting per IP address

   - Each endpoint has a specific weight cost
   - Weight is accumulated per minute
   - Different markets have different weight limits

2. **ORDERS**: Order-based rate limiting per account

   - Limits the number of orders within a time interval
   - Applied across all API keys for the same account
   - Has both short-term (seconds) and long-term (day) constraints

3. **RAW_REQUESTS**: Total number of raw HTTP requests allowed
   - Only present in Spot API
   - Limits total requests regardless of weight

## Comparison Across Market Types

| Market Type  | REQUEST_WEIGHT Limit | ORDERS Limit (10s) | ORDERS Limit (1m) | ORDERS Limit (1d) |
| ------------ | -------------------- | ------------------ | ----------------- | ----------------- |
| Spot         | 6000/minute          | 100/10s            | N/A               | 200,000/day       |
| USDT Futures | 2400/minute          | 300/10s            | 1200/minute       | N/A               |
| Coin Futures | 2400/minute          | N/A                | 1200/minute       | N/A               |
| Options      | 400/minute           | 30/10s             | 100/minute        | N/A               |

## Rate Limit Tracking Headers

When making API requests, Binance returns headers that help track rate limit usage:

- `x-mbx-used-weight-1m`: Current used weight in the 1-minute interval
- `x-mbx-used-weight`: Legacy header showing cumulative weight
- `x-mbx-order-count-10s`: Order count for the 10-second interval (when applicable)
- `x-mbx-order-count-1d`: Order count for the 1-day interval (when applicable)

## Rate Limit Error Responses

When rate limits are exceeded, Binance returns:

- HTTP 429 status code for rate limit breaches
- HTTP 418 status code for IP bans (repeated violations)
- `Retry-After` header indicating when to retry (in seconds)

## Optimization Strategies

1. **Batch requests** when possible:

   - Get all price tickers at once (weight 2-4) rather than individually (weight 1-2 each)
   - Use maximum `limit` parameter values to reduce total requests

2. **Endpoint rotation**:

   - Distribute requests across multiple available endpoints:
     - api.binance.com, api1.binance.com, api2.binance.com, etc.
   - Use data-only endpoints for non-critical data: data-api.binance.vision

3. **Weight tracking**:

   - Monitor the weight headers in responses
   - Implement circuit breakers when approaching limits
   - Add exponential backoff for retries

4. **WebSocket alternatives**:

   - Use WebSockets instead of REST API polling for real-time data
   - No rate limits for public market data streams

5. **Symbol-specific optimizations**:
   - Use specific ticker endpoints based on needs:
     - Price ticker (lower weight) vs 24hr ticker (higher weight)
   - Request only needed symbols rather than all symbols

## Implementation Example

The following Python example demonstrates tracking and managing rate limits:

```python
# Track weight usage
last_weight = 0

def track_weight(response):
    global last_weight
    current_weight = int(response.headers.get('x-mbx-used-weight-1m', '0'))
    weight_used = current_weight - last_weight
    last_weight = current_weight

    print(f"Weight used: {weight_used}, Total: {current_weight}/6000")

    # Circuit breaker when approaching limit
    if current_weight > 5400:  # 90% of limit
        print("Warning: Close to rate limit, slowing down requests")
        time.sleep(5)  # Add delay to prevent hitting limits
```
