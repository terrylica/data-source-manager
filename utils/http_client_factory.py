#!/usr/bin/env python
"""HTTP client factory functions for creating standardized client instances.

This module centralizes the creation of HTTP clients, ensuring consistent configuration
across different parts of the application. It supports both aiohttp and httpx clients
with standardized headers, timeouts, and connection settings.
"""

import aiohttp
import httpx
from utils.config import (
    DEFAULT_USER_AGENT,
    DEFAULT_ACCEPT_HEADER,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
)


def create_aiohttp_client(
    timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS, max_connections: int = 20
) -> aiohttp.ClientSession:
    """Factory function to create a pre-configured aiohttp ClientSession.

    Args:
        timeout: Total timeout in seconds
        max_connections: Maximum number of connections

    Returns:
        Configured aiohttp ClientSession with standardized settings
    """
    default_headers = {
        "Accept": DEFAULT_ACCEPT_HEADER,
        "User-Agent": DEFAULT_USER_AGENT,
    }

    client_timeout = aiohttp.ClientTimeout(
        total=timeout, connect=3, sock_connect=3, sock_read=5
    )
    connector = aiohttp.TCPConnector(limit=max_connections, force_close=False)

    return aiohttp.ClientSession(
        timeout=client_timeout,
        connector=connector,
        headers=default_headers,
    )


def create_httpx_client(
    timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS, max_connections: int = 13
) -> httpx.AsyncClient:
    """Factory function to create a pre-configured httpx AsyncClient.

    Args:
        timeout: Total timeout in seconds
        max_connections: Maximum number of connections

    Returns:
        Configured httpx AsyncClient with standardized settings
    """
    limits = httpx.Limits(
        max_connections=max_connections, max_keepalive_connections=max_connections
    )
    timeout_config = httpx.Timeout(timeout)
    default_headers = {
        "Accept": DEFAULT_ACCEPT_HEADER,
        "User-Agent": DEFAULT_USER_AGENT,
    }

    return httpx.AsyncClient(
        limits=limits, timeout=timeout_config, headers=default_headers
    )
