#!/usr/bin/env python3
"""
MCP Server for IP Geolocation.

Provides tools to get user's country based on IP address.
Uses ip-api.com for geolocation lookups (45 req/min, no API key required)
and ipify.org for IP detection.
"""

import requests
from typing import Optional
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    "Geolocation",
    instructions="IP-based geolocation service that determines user's country from IP addresses"
)


def get_public_ip() -> str:
    """Get the public IP address using external API."""
    response = requests.get('https://api.ipify.org?format=json', timeout=5)
    response.raise_for_status()
    return response.json()['ip']


@mcp.tool(
    name="get_country_from_ip",
    description="Get country information for a given IP address or auto-detect current IP"
)
def get_country_from_ip(ip_address: Optional[str] = None) -> dict:
    """
    Get country information from an IP address.

    Args:
        ip_address: IPv4 address to lookup (e.g., "8.8.8.8"). If None, automatically
                   detects and uses the current public IP address.

    Returns:
        Dictionary containing:
            - ip (str): The IP address that was looked up
            - country (str): Full country name (e.g., "United States")
            - country_code (str): Two-letter ISO country code (e.g., "US")
    """
    # Get IP if not provided
    if not ip_address:
        ip_address = get_public_ip()

    # Use ip-api.com for geolocation (45 req/min, no API key needed)
    response = requests.get(f'http://ip-api.com/json/{ip_address}?fields=status,message,country,countryCode', timeout=5)
    response.raise_for_status()
    data = response.json()

    # Check if we got an error response
    if data.get('status') == 'fail':
        raise ValueError(f"Geolocation API error: {data.get('message', 'Unknown error')}")

    return {
        'ip': ip_address,
        'country': data['country'],
        'country_code': data['countryCode']
    }


@mcp.tool(
    name="get_user_country",
    description="Automatically detect the current user's country by looking up their public IP address"
)
def get_user_country() -> dict:
    """
    Get the current user's country based on their public IP address.

    Returns:
        Dictionary containing:
            - ip: The detected public IP address
            - country: Full country name
            - country_code: Two-letter ISO country code
    """
    # Get current public IP
    ip_address = get_public_ip()

    # Use ip-api.com for geolocation (45 req/min, no API key needed)
    response = requests.get(f'http://ip-api.com/json/{ip_address}?fields=status,message,country,countryCode', timeout=5)
    response.raise_for_status()
    data = response.json()

    # Check if we got an error response
    if data.get('status') == 'fail':
        raise ValueError(f"Geolocation API error: {data.get('message', 'Unknown error')}")

    return {
        'ip': ip_address,
        'country': data['country'],
        'country_code': data['countryCode']
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
