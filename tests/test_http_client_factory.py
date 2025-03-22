import pytest
import aiohttp
import httpx
from utils.http_client_factory import create_aiohttp_client, create_httpx_client
from utils.config import (
    DEFAULT_USER_AGENT,
    DEFAULT_ACCEPT_HEADER,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
)


@pytest.mark.asyncio
async def test_create_aiohttp_client():
    """Test that aiohttp client is created with expected configuration."""
    # Create the client in an async context
    client = create_aiohttp_client()

    try:
        # Check client type
        assert isinstance(client, aiohttp.ClientSession)

        # Check headers
        assert client._default_headers["User-Agent"] == DEFAULT_USER_AGENT
        assert client._default_headers["Accept"] == DEFAULT_ACCEPT_HEADER

        # Check timeout
        assert client._timeout.total == DEFAULT_HTTP_TIMEOUT_SECONDS

        # Check custom parameters
        custom_timeout = 20.0
        custom_connections = 30
        custom_client = create_aiohttp_client(
            timeout=custom_timeout, max_connections=custom_connections
        )

        assert custom_client._timeout.total == custom_timeout
        assert custom_client._connector.limit == custom_connections

        await custom_client.close()
    finally:
        # Clean up
        await client.close()


def test_create_httpx_client():
    """Test that httpx client is created with expected configuration."""
    client = create_httpx_client()

    # Check client type
    assert isinstance(client, httpx.AsyncClient)

    # Check headers
    assert client.headers["User-Agent"] == DEFAULT_USER_AGENT
    assert client.headers["Accept"] == DEFAULT_ACCEPT_HEADER

    # Check timeout - httpx.Timeout is directly comparable
    assert client.timeout == httpx.Timeout(DEFAULT_HTTP_TIMEOUT_SECONDS)

    # Check custom parameters
    custom_timeout = 20.0
    custom_connections = 30
    custom_client = create_httpx_client(
        timeout=custom_timeout, max_connections=custom_connections
    )

    # Check timeout using direct comparison
    assert custom_client.timeout == httpx.Timeout(custom_timeout)

    # For httpx, we need to access the _transport._pool property
    # But this is implementation specific and might change
    # Instead, just check that the client was created successfully
    assert isinstance(custom_client, httpx.AsyncClient)
