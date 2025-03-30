# Using curl_cffi

## Basic Usage

```python
from curl_cffi.requests import AsyncSession, Request

async def fetch_data(url: str) -> dict:
    async with AsyncSession() as session:
        response = await session.get(url)
        return response.json()
```

## Recommended Patterns

### Session Reuse

```python
session = AsyncSession()

async def fetch_multiple():
    resp1 = await session.get("https://api.example.com/endpoint1")
    resp2 = await session.get("https://api.example.com/endpoint2")
    return resp1.json(), resp2.json()
```

### Custom Headers

```python
headers = {
    "Content-Type": "application/json",
    "User-Agent": "YourAppName/1.0"
}

async def fetch_with_headers(url: str) -> dict:
    async with AsyncSession() as session:
        response = await session.get(url, headers=headers)
        return response.json()
```

### Timeout Configuration

```python
async def fetch_with_timeout(url: str) -> dict:
    async with AsyncSession() as session:
        response = await session.get(
            url,
            timeout=30  # 30 seconds timeout
        )
        return response.json()
```

### Error Handling

```python
from curl_cffi.requests import RequestsError, Response

async def fetch_with_error_handling(url: str) -> dict:
    try:
        async with AsyncSession() as session:
            response = await session.get(url)
            response.raise_for_status()  # Raise exception for 4xx/5xx
            return response.json()
    except RequestsError as e:
        logger.error(f"Request failed: {e}")
        raise
```

## Performance Considerations

- Reuse sessions when making multiple requests
- Use connection pooling for high-throughput scenarios
- Set appropriate timeouts to avoid hanging requests
- Consider using streaming responses for large payloads
