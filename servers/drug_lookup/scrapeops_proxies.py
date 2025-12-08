"""
ScrapeOps Proxy Configuration and Round Robin Selection

Manages a pool of ScrapeOps residential proxies for the BNF server.
Provides round-robin selection to distribute requests across proxy endpoints.
"""

import threading
from typing import Dict

# ScrapeOps proxy pool (GB/London residential proxies)
# Format: username:password:host:port
SCRAPEOPS_PROXIES = [
    "scrapeops.country=gb.city=london:b47fbecb-8312-45ea-906c-e587c9827252:residential-proxy.scrapeops.io:8181",
    "scrapeops.country=gb.city=london:b47fbecb-8312-45ea-906c-e587c9827252:residential-proxy.scrapeops.io:8181",
    "scrapeops.country=gb.city=london:b47fbecb-8312-45ea-906c-e587c9827252:residential-proxy.scrapeops.io:8181",
    "scrapeops.country=gb.city=london:b47fbecb-8312-45ea-906c-e587c9827252:residential-proxy.scrapeops.io:8181",
    "scrapeops.country=gb.city=london:b47fbecb-8312-45ea-906c-e587c9827252:residential-proxy.scrapeops.io:8181",
    "scrapeops.country=gb.city=london:b47fbecb-8312-45ea-906c-e587c9827252:residential-proxy.scrapeops.io:8181",
    "scrapeops.country=gb.city=london:b47fbecb-8312-45ea-906c-e587c9827252:residential-proxy.scrapeops.io:8181",
    "scrapeops.country=gb.city=london:b47fbecb-8312-45ea-906c-e587c9827252:residential-proxy.scrapeops.io:8181",
    "scrapeops.country=gb.city=london:b47fbecb-8312-45ea-906c-e587c9827252:residential-proxy.scrapeops.io:8181",
    "scrapeops.country=gb.city=london:b47fbecb-8312-45ea-906c-e587c9827252:residential-proxy.scrapeops.io:8181",
]

# Thread-safe counter for round-robin selection
_proxy_index = 0
_proxy_lock = threading.Lock()


def get_proxy() -> Dict[str, str]:
    """
    Get the next proxy in round-robin fashion.

    Returns a proxy configuration dictionary formatted for use with
    requests library or Playwright.

    Thread-safe implementation ensures each request gets a different proxy
    in a rotating pattern.

    Returns:
        dict: Proxy configuration with keys:
            - 'http': HTTP proxy URL
            - 'https': HTTPS proxy URL
            - 'username': Proxy username
            - 'password': Proxy password (API key)
            - 'server': Proxy server for Playwright

    Example:
        >>> proxy = get_proxy()
        >>> response = requests.get(url, proxies={"http": proxy["http"], "https": proxy["https"]})
    """
    global _proxy_index

    with _proxy_lock:
        # Get current proxy
        proxy_string = SCRAPEOPS_PROXIES[_proxy_index]

        # Increment index for next call (round-robin)
        _proxy_index = (_proxy_index + 1) % len(SCRAPEOPS_PROXIES)

    # Parse proxy string: username:password:host:port
    parts = proxy_string.split(":")
    if len(parts) != 4:
        raise ValueError(f"Invalid proxy format: {proxy_string}")

    username, password, host, port = parts

    # Return proxy configuration in multiple formats for compatibility
    proxy_url = f"http://{username}:{password}@{host}:{port}"

    return {
        # For requests library
        "http": proxy_url,
        "https": proxy_url,

        # For Playwright
        "server": f"http://{host}:{port}",
        "username": username,
        "password": password,

        # Raw components
        "host": host,
        "port": int(port),
    }


def get_proxy_url() -> str:
    """
    Get the next proxy URL in round-robin fashion.

    Simplified version that returns just the proxy URL string.

    Returns:
        str: Proxy URL in format http://username:password@host:port

    Example:
        >>> proxy_url = get_proxy_url()
        >>> session.proxies = {"http": proxy_url, "https": proxy_url}
    """
    proxy = get_proxy()
    return proxy["http"]


def get_proxy_count() -> int:
    """
    Get the total number of proxies in the pool.

    Returns:
        int: Number of available proxies
    """
    return len(SCRAPEOPS_PROXIES)


def reset_proxy_index():
    """
    Reset the round-robin counter to start from the beginning.

    Useful for testing or if you want to restart the rotation.
    """
    global _proxy_index

    with _proxy_lock:
        _proxy_index = 0
