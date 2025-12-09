"""
Simple cache module for DrugBank server.
Falls back gracefully if Firebase is not available.
"""

class SimpleCache:
    """Simple in-memory cache for DrugBank results."""

    def __init__(self):
        self.cache = {}
        self.enabled = True

    def get(self, collection: str, key: str = None):
        """
        Get value from cache.
        Supports two signatures:
        - get(key) - single key
        - get(collection, key) - collection and key
        """
        if key is None:
            # Single argument case: collection is actually the key
            cache_key = collection
        else:
            # Two argument case: combine collection and key
            cache_key = f"{collection}:{key}"
        return self.cache.get(cache_key)

    def set(self, collection: str, key: str, value=None, ttl: int = 3600):
        """
        Set value in cache (ttl is ignored in simple cache).
        Supports two signatures:
        - set(key, value) - single key
        - set(collection, key, value) - collection, key, and value
        """
        if value is None:
            # Two argument case: collection is key, key is value
            cache_key = collection
            cache_value = key
        else:
            # Three argument case: combine collection and key
            cache_key = f"{collection}:{key}"
            cache_value = value
        self.cache[cache_key] = cache_value


def get_cache():
    """Get cache instance."""
    return SimpleCache()
