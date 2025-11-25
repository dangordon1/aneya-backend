#!/usr/bin/env python
"""
MCP Client Selector Factory

This module provides a factory function for creating and connecting the appropriate
country-specific MCP client based on an ISO country code.

The factory handles:
- Country code normalization (case-insensitive)
- Client instantiation
- Automatic connection establishment
- Fallback to international client for unsupported countries

Usage:
    ```python
    from mcp_client_selector import get_mcp_client_for_country

    # Get a connected client for the UK
    client = await get_mcp_client_for_country("GB", verbose=True)

    # Use the client
    result = await client.call_tool("search_nice_guidelines", {"query": "diabetes"})

    # Clean up when done
    await client.cleanup()
    ```

Supported Country Codes:
- GB, UK: United Kingdom (NICE, BNF)
- IN: India (FOGSI, ICMR, STG, RSSDI, CSI, NCG, IAP)
- US: United States (USPSTF, CDC, IDSA, ADA, AHA/ACC, AAP)
- AU: Australia (NHMRC)
- Others: International (PubMed)
"""

from typing import Optional
from mcp_clients_country import (
    MCPClient,
    UKMCPClient,
    IndiaMCPClient,
    USMCPClient,
    AustraliaMCPClient,
    InternationalMCPClient
)


# Country code mapping to client classes
COUNTRY_CLIENT_MAP = {
    # UK variants
    "GB": UKMCPClient,
    "UK": UKMCPClient,
    "UNITED KINGDOM": UKMCPClient,

    # India
    "IN": IndiaMCPClient,
    "INDIA": IndiaMCPClient,

    # United States
    "US": USMCPClient,
    "USA": USMCPClient,
    "UNITED STATES": USMCPClient,

    # Australia
    "AU": AustraliaMCPClient,
    "AUSTRALIA": AustraliaMCPClient,
}


async def get_mcp_client_for_country(
    country_code: str,
    verbose: bool = False
) -> MCPClient:
    """
    Factory function to create and connect the appropriate MCP client based on country code.

    This function:
    1. Normalizes the country code (uppercase, strip whitespace)
    2. Looks up the appropriate client class for the country
    3. Falls back to InternationalMCPClient for unsupported countries
    4. Instantiates the client
    5. Connects to all configured servers
    6. Returns the connected client

    Args:
        country_code: ISO country code (e.g., 'GB', 'IN', 'US', 'AU')
                     Case-insensitive, whitespace is stripped
        verbose: Whether to print connection progress and diagnostics

    Returns:
        Connected country-specific MCPClient instance, ready to use

    Raises:
        ConnectionError: If client fails to connect to any required servers
        Exception: If client initialization or connection fails

    Examples:
        >>> # Get UK client
        >>> uk_client = await get_mcp_client_for_country("GB")
        >>> # Get US client with verbose output
        >>> us_client = await get_mcp_client_for_country("US", verbose=True)
        >>> # Get fallback client for unsupported country
        >>> intl_client = await get_mcp_client_for_country("FR")

    Note:
        The returned client must be cleaned up when done:
        >>> await client.cleanup()

        Or use as an async context manager:
        >>> async with await get_mcp_client_for_country("GB") as client:
        ...     result = await client.call_tool(...)
    """
    # Normalize country code
    normalized_code = country_code.strip().upper()

    # Log country selection
    if verbose:
        print(f"\n🌍 Selecting MCP client for country: {country_code} ({normalized_code})")

    # Look up client class
    client_class = COUNTRY_CLIENT_MAP.get(normalized_code)

    if client_class is None:
        # Fallback to international client
        if verbose:
            print(f"⚠️  Country '{country_code}' not supported, using International client (PubMed)")
        client_class = InternationalMCPClient
    else:
        if verbose:
            client_name = client_class.__name__.replace("MCPClient", "")
            print(f"✓ Using {client_name} client")

    # Instantiate client
    client = client_class(verbose=verbose)

    # Connect to all servers
    try:
        await client.connect()

        if verbose:
            connected_servers = client.get_connected_servers()
            available_tools = client.get_available_tools()
            print(f"✓ Client ready with {len(connected_servers)} servers and {len(available_tools)} tools")
            print(f"  Servers: {', '.join(connected_servers)}")

        return client

    except Exception as e:
        # Clean up on connection failure
        if verbose:
            print(f"✗ Failed to connect client: {e}")
        await client.cleanup()
        raise


async def get_supported_countries() -> dict[str, str]:
    """
    Get a dictionary of supported country codes and their client types.

    Returns:
        Dictionary mapping country codes to client class names

    Example:
        >>> countries = await get_supported_countries()
        >>> print(countries)
        {'GB': 'UKMCPClient', 'IN': 'IndiaMCPClient', ...}
    """
    return {
        code: client_class.__name__
        for code, client_class in COUNTRY_CLIENT_MAP.items()
    }


def is_country_supported(country_code: str) -> bool:
    """
    Check if a country code has dedicated guideline server support.

    Args:
        country_code: ISO country code to check

    Returns:
        True if country has dedicated servers, False if will use international fallback

    Example:
        >>> is_country_supported("GB")
        True
        >>> is_country_supported("FR")
        False
    """
    normalized_code = country_code.strip().upper()
    return normalized_code in COUNTRY_CLIENT_MAP


# Convenience function for common use case
async def get_client(country_code: str, verbose: bool = False) -> MCPClient:
    """
    Alias for get_mcp_client_for_country for shorter imports.

    Args:
        country_code: ISO country code
        verbose: Whether to print connection progress

    Returns:
        Connected MCPClient instance
    """
    return await get_mcp_client_for_country(country_code, verbose=verbose)
