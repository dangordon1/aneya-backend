#!/usr/bin/env python
"""
BNF Caching Module using Google Firestore

Provides persistent caching for BNF search results and page content
to reduce proxy usage and improve response times.
"""

import hashlib
import os
import sys
import contextlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from mcp_utils import print_stderr

# Try to import Firebase - if it fails, caching will be disabled
# This prevents protobuf error messages from corrupting MCP stdout
FIREBASE_AVAILABLE = False
firebase_admin = None
firestore = None

# Context manager to suppress ALL Firebase/Google Cloud SDK stderr output
@contextlib.contextmanager
def suppress_firebase_stderr():
    """Suppress Firebase/Google Cloud SDK stderr to prevent MCP stdout contamination"""
    # Redirect stderr to /dev/null
    devnull = open(os.devnull, 'w')
    old_stderr = sys.stderr
    try:
        sys.stderr = devnull
        yield
    finally:
        sys.stderr = old_stderr
        devnull.close()

try:
    # Suppress Firebase/protobuf stderr messages during import
    with suppress_firebase_stderr():
        import firebase_admin
        from firebase_admin import credentials, firestore as _firestore
        from google.cloud.firestore_v1.base_query import FieldFilter
    firestore = _firestore
    FIREBASE_AVAILABLE = True
except Exception:
    # Firebase not available - caching will be disabled
    pass


class BNFCache:
    """
    Firestore-based cache for BNF results with TTL and hit tracking.

    Cache keys are based on search terms:
    - search_drug:<drug_name> - for drug searches
    - search_condition:<condition> - for condition searches
    - page:<url_path> - for page content
    """

    def __init__(self, collection_name: str = "bnf_cache", default_ttl_days: int = 30):
        """
        Initialize BNF cache with Firestore.

        Args:
            collection_name: Firestore collection name
            default_ttl_days: Default TTL for cached entries (days)
        """
        self.collection_name = collection_name
        self.default_ttl_days = default_ttl_days
        self.enabled = False
        self.db = None

        # Check if Firebase is available
        if not FIREBASE_AVAILABLE:
            print_stderr(f"⚠️  BNF cache disabled: Firebase Admin SDK not available")
            print_stderr("   Cache will be bypassed (searches will use proxy/direct connection)")
            return

        # Initialize Firebase Admin SDK
        try:
            # Check if already initialized (suppress stderr for all Firebase operations)
            with suppress_firebase_stderr():
                if not firebase_admin._apps:
                    # Try to use default credentials (works on Cloud Run)
                    firebase_admin.initialize_app()

                self.db = firestore.client()

            self.enabled = True
            print_stderr(f"✅ BNF cache enabled (Firestore collection: {collection_name}, TTL: {default_ttl_days} days)")

        except Exception as e:
            print_stderr(f"⚠️  BNF cache disabled: {str(e)}")
            print_stderr("   Cache will be bypassed (searches will use proxy/direct connection)")

    def _generate_cache_key(self, key_type: str, value: str) -> str:
        """
        Generate a cache key from search term or URL.

        Args:
            key_type: Type of key (search_drug, search_condition, page)
            value: The search term or URL path

        Returns:
            Sanitized cache key suitable for Firestore document ID
        """
        # Normalize the value: lowercase, remove extra whitespace
        normalized = " ".join(value.lower().strip().split())

        # Create a hash for very long values (Firestore doc IDs have 1500 char limit)
        if len(normalized) > 100:
            hash_suffix = hashlib.md5(normalized.encode()).hexdigest()[:8]
            normalized = f"{normalized[:90]}_{hash_suffix}"

        # Combine type and normalized value
        cache_key = f"{key_type}:{normalized}"

        # Replace invalid Firestore document ID characters
        cache_key = cache_key.replace('/', '_')

        return cache_key

    def get(self, key_type: str, value: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached data if it exists and hasn't expired.

        Args:
            key_type: Type of key (search_drug, search_condition, page)
            value: The search term or URL path

        Returns:
            Cached data dictionary or None if not found/expired
        """
        if not self.enabled:
            return None

        try:
            cache_key = self._generate_cache_key(key_type, value)

            # Suppress Firebase stderr for all database operations
            with suppress_firebase_stderr():
                doc_ref = self.db.collection(self.collection_name).document(cache_key)
                doc = doc_ref.get()

                if not doc.exists:
                    return None

                data = doc.to_dict()

                # Check if expired
                created_at = data.get('created_at')
                ttl_days = data.get('ttl_days', self.default_ttl_days)

                if created_at:
                    expiry_date = created_at + timedelta(days=ttl_days)
                    if datetime.now(timezone.utc) > expiry_date:
                        print_stderr(f"🗑️  Cache expired: {cache_key}")
                        # Delete expired entry
                        doc_ref.delete()
                        return None

                # Increment hit count
                doc_ref.update({
                    'hit_count': firestore.Increment(1),
                    'last_accessed': datetime.now(timezone.utc)
                })

            print_stderr(f"💾 Cache hit: {cache_key} (hits: {data.get('hit_count', 0) + 1})")
            return data.get('content')

        except Exception as e:
            print_stderr(f"⚠️  Cache get error: {str(e)}")
            return None

    def set(self, key_type: str, value: str, content: Any, ttl_days: Optional[int] = None):
        """
        Store data in cache with metadata.

        Args:
            key_type: Type of key (search_drug, search_condition, page)
            value: The search term or URL path
            content: The data to cache
            ttl_days: Optional TTL override (uses default if not specified)
        """
        if not self.enabled:
            return

        try:
            cache_key = self._generate_cache_key(key_type, value)
            now = datetime.now(timezone.utc)

            doc_data = {
                'content': content,
                'created_at': now,
                'last_updated': now,
                'last_accessed': now,
                'ttl_days': ttl_days or self.default_ttl_days,
                'hit_count': 0,
                'key_type': key_type,
                'search_term': value
            }

            # Suppress Firebase stderr for database write
            with suppress_firebase_stderr():
                doc_ref = self.db.collection(self.collection_name).document(cache_key)
                doc_ref.set(doc_data)

            print_stderr(f"💾 Cache set: {cache_key}")

        except Exception as e:
            print_stderr(f"⚠️  Cache set error: {str(e)}")

    def invalidate(self, key_type: str, value: str):
        """
        Remove a specific entry from cache.

        Args:
            key_type: Type of key (search_drug, search_condition, page)
            value: The search term or URL path
        """
        if not self.enabled:
            return

        try:
            cache_key = self._generate_cache_key(key_type, value)

            # Suppress Firebase stderr for database delete
            with suppress_firebase_stderr():
                doc_ref = self.db.collection(self.collection_name).document(cache_key)
                doc_ref.delete()

            print_stderr(f"🗑️  Cache invalidated: {cache_key}")

        except Exception as e:
            print_stderr(f"⚠️  Cache invalidate error: {str(e)}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        if not self.enabled:
            return {'enabled': False}

        try:
            # Suppress Firebase stderr for database queries
            with suppress_firebase_stderr():
                collection = self.db.collection(self.collection_name)

                # Get total count
                docs = collection.stream()
                total = sum(1 for _ in docs)

                # Get top hits
                top_hits = collection.order_by('hit_count', direction=firestore.Query.DESCENDING).limit(10).stream()
                top_list = [
                    {
                        'key': doc.id,
                        'hits': doc.to_dict().get('hit_count', 0),
                        'created': doc.to_dict().get('created_at'),
                    }
                    for doc in top_hits
                ]

            return {
                'enabled': True,
                'total_entries': total,
                'collection': self.collection_name,
                'default_ttl_days': self.default_ttl_days,
                'top_hits': top_list
            }

        except Exception as e:
            print_stderr(f"⚠️  Cache stats error: {str(e)}")
            return {'enabled': True, 'error': str(e)}

    def clear_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries deleted
        """
        if not self.enabled:
            return 0

        try:
            now = datetime.now(timezone.utc)

            # Suppress Firebase stderr for database operations
            with suppress_firebase_stderr():
                collection = self.db.collection(self.collection_name)

                # Find expired documents
                docs = collection.stream()
                deleted = 0

                for doc in docs:
                    data = doc.to_dict()
                    created_at = data.get('created_at')
                    ttl_days = data.get('ttl_days', self.default_ttl_days)

                    if created_at:
                        expiry_date = created_at + timedelta(days=ttl_days)
                        if now > expiry_date:
                            doc.reference.delete()
                            deleted += 1

            print_stderr(f"🗑️  Cleared {deleted} expired cache entries")
            return deleted

        except Exception as e:
            print_stderr(f"⚠️  Cache clear error: {str(e)}")
            return 0


# Global cache instance
_cache = None

def get_cache() -> BNFCache:
    """Get or create the global BNF cache instance."""
    global _cache
    if _cache is None:
        _cache = BNFCache()
    return _cache
