"""
Simple cache module for MIMS India server.
Falls back gracefully if Firebase is not available.
"""

class SimpleCache:
    """Simple in-memory cache for MIMS results."""

    def __init__(self):
        self.cache = {}
        self.enabled = True

    def get(self, key: str):
        """Get value from cache."""
        return self.cache.get(key)

    def set(self, key: str, value, ttl: int = 3600):
        """Set value in cache (ttl is ignored in simple cache)."""
        self.cache[key] = value


def get_cache():
    """Get cache instance."""
    return SimpleCache()
