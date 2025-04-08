# HTTP Client Abstraction Roadmap

## Overview

This document outlines the plan for implementing an HTTP client abstraction layer that will reduce direct dependencies on curl_cffi and provide flexibility to use alternative HTTP clients. By decoupling our code from specific HTTP client implementations, we'll improve maintainability, enable easier testing, and mitigate risks associated with client-specific issues such as the curl_cffi memory leaks and hanging issues we've encountered.

## Goals and Objectives

1. **Decouple Business Logic from HTTP Client Implementation**

   - Create a standardized HTTP client interface
   - Enable transparent swapping of HTTP client backends
   - Mitigate curl_cffi-specific issues

2. **Client Diversity and Resilience**

   - Support multiple HTTP client implementations (curl_cffi, httpx, aiohttp)
   - Implement client selection strategies (failover, round-robin)
   - Add client-specific optimizations while maintaining common interface

3. **Enhanced Testing and Reliability**

   - Simplify mocking for HTTP client operations
   - Implement comprehensive client-agnostic tests
   - Provide consistent error handling across client implementations

4. **Performance Optimization**
   - Benchmark different client implementations
   - Implement client-specific performance optimizations
   - Enable runtime selection of optimal client for specific operations

## Timeline and Milestones

| Milestone              | Timeline    | Description                                                                |
| ---------------------- | ----------- | -------------------------------------------------------------------------- |
| Design                 | Weeks 1-2   | Define abstraction interface, client requirements, and transition strategy |
| Core Implementation    | Weeks 3-6   | Implement base abstraction and curl_cffi adapter                           |
| Alternative Clients    | Weeks 7-9   | Implement httpx and aiohttp adapters                                       |
| Integration            | Weeks 10-12 | Integrate with RestDataClient and VisionDataClient                         |
| Testing & Benchmarking | Weeks 13-14 | Comprehensive testing and performance benchmarking                         |
| Migration              | Weeks 15-16 | Migrate existing code to use the abstraction layer                         |

Total timeline: 4 months (Q3-Q4 2025)

## Implementation Details

### 1. HTTP Client Interface Definition

#### 1.1 `utils/http/client_interface.py`

Define a protocol for all HTTP client implementations:

```python
"""
HTTP client interface definitions.

This module defines the abstract interfaces that all HTTP client
implementations must adhere to, enabling transparent swapping.
"""
from typing import Dict, Any, Optional, Union, Protocol, runtime_checkable
from types import TracebackType
import ssl
import pathlib

@runtime_checkable
class HttpResponse(Protocol):
    """Protocol defining the interface for HTTP responses."""

    @property
    def status_code(self) -> int:
        """HTTP status code."""
        ...

    @property
    def headers(self) -> Dict[str, str]:
        """HTTP response headers."""
        ...

    @property
    def content(self) -> bytes:
        """Raw response content."""
        ...

    async def text(self) -> str:
        """Response content as text."""
        ...

    async def json(self) -> Any:
        """Response content parsed as JSON."""
        ...

@runtime_checkable
class HttpClient(Protocol):
    """Protocol defining the interface for HTTP clients."""

    async def __aenter__(self) -> 'HttpClient':
        """Enter async context."""
        ...

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        """Exit async context."""
        ...

    async def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        follow_redirects: bool = True,
    ) -> HttpResponse:
        """Perform HTTP GET request."""
        ...

    async def post(
        self,
        url: str,
        *,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        follow_redirects: bool = True,
    ) -> HttpResponse:
        """Perform HTTP POST request."""
        ...

    # Additional methods (put, delete, head, etc.)

    async def close(self) -> None:
        """Close the client and release resources."""
        ...

class HttpClientOptions:
    """Configuration options for HTTP clients."""

    def __init__(
        self,
        verify_ssl: bool = True,
        ssl_context: Optional[ssl.SSLContext] = None,
        cert: Optional[Union[str, pathlib.Path, tuple[str, str]]] = None,
        timeout: float = 30.0,
        max_redirects: int = 10,
        http2: bool = False,
        proxy: Optional[str] = None,
        auth: Optional[tuple[str, str]] = None,
        # Client-specific options can be passed in extras
        **extras: Any,
    ):
        """Initialize client options."""
        self.verify_ssl = verify_ssl
        self.ssl_context = ssl_context
        self.cert = cert
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.http2 = http2
        self.proxy = proxy
        self.auth = auth
        self.extras = extras
```

### 2. Client Factory and Configuration

#### 2.1 `utils/http/client_factory.py`

Implement a factory for creating HTTP clients:

```python
"""
HTTP client factory and configuration.

This module provides a factory for creating HTTP clients with
consistent configuration, while abstracting away specific implementations.
"""
from enum import Enum, auto
from typing import Optional, Dict, Any, Type
import importlib

from utils.http.client_interface import HttpClient, HttpClientOptions
from utils.config import DEFAULT_HTTP_CLIENT, HTTP_CLIENT_CONFIG

class HttpClientType(Enum):
    """Available HTTP client implementations."""
    CURL_CFFI = auto()
    HTTPX = auto()
    AIOHTTP = auto()

class HttpClientFactory:
    """Factory for creating HTTP clients."""

    _client_adapters: Dict[HttpClientType, Type[HttpClient]] = {}

    @classmethod
    def register_adapter(cls, client_type: HttpClientType, adapter_cls: Type[HttpClient]):
        """Register a client adapter."""
        cls._client_adapters[client_type] = adapter_cls

    @classmethod
    def create_client(
        cls,
        client_type: Optional[HttpClientType] = None,
        options: Optional[HttpClientOptions] = None,
    ) -> HttpClient:
        """Create an HTTP client of the specified type with given options."""

        # Use default client type if not specified
        client_type = client_type or getattr(HttpClientType, DEFAULT_HTTP_CLIENT, HttpClientType.HTTPX)

        # Create default options if not provided
        options = options or HttpClientOptions(**HTTP_CLIENT_CONFIG)

        # Get the adapter for the specified client type
        adapter_cls = cls._client_adapters.get(client_type)

        # If adapter not found, try to lazy-load it
        if adapter_cls is None:
            cls._load_adapter(client_type)
            adapter_cls = cls._client_adapters.get(client_type)

            if adapter_cls is None:
                # Fall back to httpx if available
                if HttpClientType.HTTPX in cls._client_adapters:
                    adapter_cls = cls._client_adapters[HttpClientType.HTTPX]
                else:
                    raise ValueError(f"No adapter available for HTTP client type: {client_type}")

        # Create and return the client
        return adapter_cls(options)

    @classmethod
    def _load_adapter(cls, client_type: HttpClientType):
        """Dynamically load adapter module for the specified client type."""
        adapter_module_name = f"utils.http.adapters.{client_type.name.lower()}_adapter"
        try:
            importlib.import_module(adapter_module_name)
        except ImportError:
            pass  # Adapter not available
```

### 3. Client Adapters

#### 3.1 `utils/http/adapters/curl_cffi_adapter.py`

Implement the curl_cffi adapter:

```python
"""
curl_cffi HTTP client adapter.

This module provides an adapter for the curl_cffi library that
implements the HttpClient interface.
"""
from typing import Dict, Any, Optional, Union, Type
from types import TracebackType

from curl_cffi.requests import Session, Response

from utils.http.client_interface import HttpClient, HttpResponse, HttpClientOptions
from utils.http.client_factory import HttpClientFactory, HttpClientType
from utils.async_cleanup import cleanup_client

class CurlCffiResponse(HttpResponse):
    """Adapter for curl_cffi Response objects."""

    def __init__(self, response: Response):
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self) -> Dict[str, str]:
        return dict(self._response.headers)

    @property
    def content(self) -> bytes:
        return self._response.content

    async def text(self) -> str:
        return self._response.text

    async def json(self) -> Any:
        return self._response.json()

class CurlCffiClient(HttpClient):
    """curl_cffi implementation of HttpClient."""

    def __init__(self, options: HttpClientOptions):
        self._options = options
        self._session = Session(
            verify=options.verify_ssl,
            cert=options.cert,
            timeout=options.timeout,
            proxies={"http": options.proxy, "https": options.proxy} if options.proxy else None,
            http2=options.http2,
            # Apply any curl_cffi-specific options from extras
            **{k: v for k, v in options.extras.items() if k in self._get_allowed_kwargs()}
        )

    async def __aenter__(self) -> 'CurlCffiClient':
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        await self.close()
        return None

    async def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        follow_redirects: bool = True,
    ) -> HttpResponse:
        response = self._session.get(
            url=url,
            params=params,
            headers=headers,
            timeout=timeout or self._options.timeout,
            follow_redirects=follow_redirects,
        )
        return CurlCffiResponse(response)

    async def post(
        self,
        url: str,
        *,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        json: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        follow_redirects: bool = True,
    ) -> HttpResponse:
        response = self._session.post(
            url=url,
            data=data,
            json=json,
            headers=headers,
            timeout=timeout or self._options.timeout,
            follow_redirects=follow_redirects,
        )
        return CurlCffiResponse(response)

    async def close(self) -> None:
        """Close the client and release resources using our enhanced cleanup."""
        if self._session is not None:
            # Use our specialized cleanup to prevent hanging issues
            await cleanup_client(self._session)
            self._session = None

    @staticmethod
    def _get_allowed_kwargs() -> set:
        """Get the set of allowed keyword arguments for curl_cffi Session."""
        # This method helps filter options passed to curl_cffi Session
        return {
            "impersonate", "intercept", "decode_content", "ssl_context",
            "force_http_1", "async_dns_resolver", "verbosity", "connection_timeout"
        }

# Register the adapter with the factory
HttpClientFactory.register_adapter(HttpClientType.CURL_CFFI, CurlCffiClient)
```

#### 3.2 `utils/http/adapters/httpx_adapter.py`

Implement the httpx adapter (similar structure to curl_cffi adapter).

#### 3.3 `utils/http/adapters/aiohttp_adapter.py`

Implement the aiohttp adapter (similar structure to curl_cffi adapter).

### 4. Client Selection Strategy

#### 4.1 `utils/http/client_strategy.py`

Implement client selection strategies:

```python
"""
HTTP client selection strategies.

This module provides strategies for selecting HTTP clients
based on different criteria such as failover, round-robin, etc.
"""
from enum import Enum, auto
from typing import List, Optional, Dict
import random
import time

from utils.http.client_interface import HttpClient, HttpResponse
from utils.http.client_factory import HttpClientFactory, HttpClientType

class ClientSelectionStrategy(Enum):
    """Available client selection strategies."""
    SINGLE = auto()  # Use a single client
    FAILOVER = auto()  # Try clients in order, failing over to next
    ROUND_ROBIN = auto()  # Rotate through clients
    RANDOM = auto()  # Select a random client for each request

class MultiClient:
    """Client that implements a selection strategy across multiple clients."""

    def __init__(
        self,
        client_types: List[HttpClientType],
        strategy: ClientSelectionStrategy = ClientSelectionStrategy.FAILOVER,
        options_by_type: Optional[Dict[HttpClientType, Dict]] = None,
    ):
        """Initialize with multiple client types and a selection strategy."""
        self.client_types = client_types
        self.strategy = strategy

        # Create clients
        self.clients = []
        options_by_type = options_by_type or {}

        for client_type in client_types:
            options = options_by_type.get(client_type)
            client = HttpClientFactory.create_client(client_type, options)
            self.clients.append(client)

        # Strategy-specific state
        self._current_index = 0
        self._failure_counts = {i: 0 for i in range(len(self.clients))}

    async def __aenter__(self) -> 'MultiClient':
        """Enter async context."""
        for client in self.clients:
            await client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        for client in self.clients:
            await client.__aexit__(exc_type, exc_val, exc_tb)

    async def _select_client_index(self) -> int:
        """Select a client index based on the strategy."""
        if self.strategy == ClientSelectionStrategy.SINGLE:
            return 0

        elif self.strategy == ClientSelectionStrategy.ROUND_ROBIN:
            index = self._current_index
            self._current_index = (self._current_index + 1) % len(self.clients)
            return index

        elif self.strategy == ClientSelectionStrategy.RANDOM:
            return random.randint(0, len(self.clients) - 1)

        # Default to FAILOVER strategy
        return 0  # Start with the first client

    async def get(self, *args, **kwargs) -> HttpResponse:
        """Perform HTTP GET request using the selected client strategy."""
        if self.strategy == ClientSelectionStrategy.FAILOVER:
            # Try clients in order, failing over on exception
            for i, client in enumerate(self.clients):
                try:
                    return await client.get(*args, **kwargs)
                except Exception as e:
                    self._failure_counts[i] += 1
                    # If this is the last client, re-raise
                    if i == len(self.clients) - 1:
                        raise

            # Should not reach here
            raise RuntimeError("No HTTP clients available")

        else:
            # For other strategies, select a client and use it
            index = await self._select_client_index()
            return await self.clients[index].get(*args, **kwargs)

    # Similar implementations for post(), put(), etc.

    async def close(self) -> None:
        """Close all clients."""
        for client in self.clients:
            await client.close()
```

### 5. Integration with Existing Code

#### 5.1 REST Data Client Integration

Update `RestDataClient` to use the abstraction layer:

```python
class RestDataClient:
    """RestDataClient for market data with abstracted HTTP client."""

    def __init__(
        self,
        base_url: str,
        client: Optional[HttpClient] = None,
        client_type: Optional[HttpClientType] = None,
        # Other parameters...
    ):
        """Initialize with configurable HTTP client."""
        self._base_url = base_url

        if client is not None:
            # Use provided client
            self._client = client
            self._client_is_external = True
        else:
            # Create client of specified type (or default)
            self._client = HttpClientFactory.create_client(client_type)
            self._client_is_external = False

        # Other initialization...

    async def __aenter__(self):
        """Enter async context."""
        # Let the client handle its own context entry
        if not self._client_is_external:
            await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context."""
        if self._client and not self._client_is_external:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    # Use self._client for HTTP requests in methods
```

#### 5.2 Vision Data Client Integration

Update `VisionDataClient` similarly to `RestDataClient`.

### 6. Testing and Benchmarking

#### 6.1 Client-Agnostic Tests

Implement tests that work with any client implementation:

```python
async def test_client_interface_compliance():
    """Test that all client implementations comply with the interface."""
    # Test with each client type
    for client_type in HttpClientType:
        try:
            client = HttpClientFactory.create_client(client_type)

            # Basic interface tests
            assert hasattr(client, "get")
            assert hasattr(client, "post")
            assert hasattr(client, "close")

            # Simple functionality test
            async with client:
                response = await client.get("https://httpbin.org/status/200")
                assert response.status_code == 200

                json_response = await client.get("https://httpbin.org/json")
                data = await json_response.json()
                assert "slideshow" in data

        except ImportError:
            # Skip if client library not installed
            continue
```

#### 6.2 Performance Benchmarking

Implement benchmarks for comparing performance:

```python
async def benchmark_clients():
    """Benchmark different HTTP client implementations."""
    results = {}

    # Benchmark parameters
    url = "https://httpbin.org/stream-bytes/1000000"
    repeats = 10

    for client_type in HttpClientType:
        try:
            client = HttpClientFactory.create_client(client_type)

            # Measure connection time
            start_time = time.time()
            async with client:
                # Measure request time (average over repeats)
                request_times = []
                for _ in range(repeats):
                    req_start = time.time()
                    response = await client.get(url)
                    content = await response.text()
                    req_time = time.time() - req_start
                    request_times.append(req_time)

                conn_time = time.time() - start_time

            results[client_type.name] = {
                "connection_time": conn_time,
                "avg_request_time": sum(request_times) / len(request_times),
                "min_request_time": min(request_times),
                "max_request_time": max(request_times),
            }

        except ImportError:
            # Skip if client library not installed
            continue

    return results
```

## Technical Considerations

### Backward Compatibility

- Provide drop-in replacements for direct curl_cffi usage
- Maintain the same response interface as currently expected
- Allow gradual migration rather than requiring all-at-once changes

### Performance

- Avoid unnecessary abstractions that could impact performance
- Implement client-specific optimizations where appropriate
- Use benchmarking to validate abstraction overhead is minimal

### Dependency Management

- Make client libraries optional dependencies
- Implement lazy loading to avoid import errors
- Provide graceful fallbacks when preferred clients are unavailable

### Error Handling

- Normalize error types across different client implementations
- Provide consistent retry behavior regardless of client
- Maintain detailed error information for debugging

## Testing Strategy

1. **Interface Compliance Tests** - Ensure all clients implement the interface correctly
2. **Functional Tests** - Verify all HTTP operations work as expected with each client
3. **Performance Tests** - Benchmark different clients and verify abstraction overhead
4. **Integration Tests** - Verify integration with RestDataClient and VisionDataClient
5. **Migration Tests** - Verify backward compatibility during migration

## Risk Assessment and Mitigation

| Risk                    | Impact | Likelihood | Mitigation                                         |
| ----------------------- | ------ | ---------- | -------------------------------------------------- |
| Performance degradation | High   | Medium     | Minimal abstraction, client-specific optimizations |
| Inconsistent behavior   | High   | Medium     | Comprehensive testing, normalized error handling   |
| Dependency conflicts    | Medium | Low        | Optional dependencies, lazy loading                |
| Migration complexity    | Medium | High       | Gradual approach, backward compatibility           |
| New client bugs         | Medium | Low        | Thorough testing, failover strategies              |

## Success Criteria

1. All HTTP operations work with at least 3 different client implementations
2. Performance overhead from abstraction < 5% compared to direct client usage
3. 100% backward compatibility with existing code
4. No curl_cffi-specific hanging issues when using alternative clients
5. Comprehensive test coverage for all client implementations

## Future Enhancements (Post-Implementation)

1. Advanced client selection strategies based on request characteristics
2. Automatic client performance benchmarking and optimization
3. More client implementations (such as curl_cffi's HTTP/3 support)
4. Runtime performance monitoring and automatic adaptation
5. Client-specific feature utilization (HTTP/2 push, connection pooling, etc.)
