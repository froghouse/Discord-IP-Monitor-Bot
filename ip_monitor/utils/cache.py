"""
Intelligent caching system for the Discord IP Monitor Bot.

This module provides a comprehensive caching layer that reduces API calls
through intelligent TTL management, cache invalidation, and persistence.
"""

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import logging
from pathlib import Path
from threading import Lock
import time
from typing import Any

logger = logging.getLogger(__name__)


class CacheType(Enum):
    """Cache types for different data categories."""

    IP_RESULT = "ip_result"
    API_RESPONSE = "api_response"
    DNS_LOOKUP = "dns_lookup"
    PERFORMANCE_DATA = "performance_data"


@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata."""

    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int
    ttl: float
    cache_type: CacheType
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def is_expired(self) -> bool:
        """Check if the cache entry has expired."""
        return time.time() - self.created_at > self.ttl

    def is_stale(self, stale_threshold: float = 0.8) -> bool:
        """Check if the cache entry is approaching expiration."""
        age = time.time() - self.created_at
        return age > (self.ttl * stale_threshold)

    def touch(self) -> None:
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert cache entry to dictionary for serialization."""
        return {
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "ttl": self.ttl,
            "cache_type": self.cache_type.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create cache entry from dictionary."""
        return cls(
            key=data["key"],
            value=data["value"],
            created_at=data["created_at"],
            last_accessed=data["last_accessed"],
            access_count=data["access_count"],
            ttl=data["ttl"],
            cache_type=CacheType(data["cache_type"]),
            metadata=data.get("metadata", {}),
        )


class IntelligentCache:
    """
    Intelligent caching system with TTL management, persistence, and adaptive policies.

    Features:
    - Configurable TTL per cache type
    - Memory and persistent storage
    - Cache invalidation strategies
    - Performance metrics
    - Adaptive refresh policies
    - Thread-safe operations
    """

    def __init__(self, cache_file: str = "cache.json", max_memory_size: int = 1000):
        """
        Initialize the intelligent cache.

        Args:
            cache_file: Path to persistent cache file
            max_memory_size: Maximum number of entries in memory cache
        """
        self.cache_file = Path(cache_file)
        self.max_memory_size = max_memory_size
        self.memory_cache: dict[str, CacheEntry] = {}
        self.lock = Lock()

        # Default TTL values (in seconds)
        self.default_ttl = {
            CacheType.IP_RESULT: 300,  # 5 minutes
            CacheType.API_RESPONSE: 180,  # 3 minutes
            CacheType.DNS_LOOKUP: 3600,  # 1 hour
            CacheType.PERFORMANCE_DATA: 600,  # 10 minutes
        }

        # Cache statistics
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "invalidations": 0,
            "refreshes": 0,
            "saves": 0,
            "loads": 0,
        }

        # Load existing cache
        self._load_cache()

    def _generate_key(self, namespace: str, identifier: str) -> str:
        """Generate a unique cache key."""
        combined = f"{namespace}:{identifier}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _get_original_key(self, namespace: str, identifier: str) -> str:
        """Get the original namespace:identifier key."""
        return f"{namespace}:{identifier}"

    def _evict_expired(self) -> None:
        """Remove expired entries from memory cache."""
        expired_keys = []

        for key, entry in self.memory_cache.items():
            if entry.is_expired():
                expired_keys.append(key)

        for key in expired_keys:
            del self.memory_cache[key]
            self.stats["evictions"] += 1

    def _evict_lru(self) -> None:
        """Evict least recently used entries when cache is full."""
        if len(self.memory_cache) >= self.max_memory_size:
            # Sort by last accessed time and remove oldest
            sorted_items = sorted(
                self.memory_cache.items(), key=lambda x: x[1].last_accessed
            )

            # Remove 10% of cache or at least 1 entry
            evict_count = max(1, len(sorted_items) // 10)

            for i in range(evict_count):
                key, _ = sorted_items[i]
                del self.memory_cache[key]
                self.stats["evictions"] += 1

    def get(
        self,
        namespace: str,
        identifier: str,
        cache_type: CacheType = CacheType.IP_RESULT,
    ) -> Any | None:
        """
        Get a value from the cache.

        Args:
            namespace: Cache namespace (e.g., "ip_check", "api_response")
            identifier: Unique identifier within namespace
            cache_type: Type of cache entry

        Returns:
            Cached value or None if not found/expired
        """
        key = self._generate_key(namespace, identifier)

        with self.lock:
            entry = self.memory_cache.get(key)

            if entry is None:
                self.stats["misses"] += 1
                return None

            if entry.is_expired():
                del self.memory_cache[key]
                self.stats["misses"] += 1
                self.stats["evictions"] += 1
                return None

            entry.touch()
            self.stats["hits"] += 1
            logger.debug(f"Cache hit for {namespace}:{identifier}")
            return entry.value

    def set(
        self,
        namespace: str,
        identifier: str,
        value: Any,
        cache_type: CacheType = CacheType.IP_RESULT,
        ttl: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Set a value in the cache.

        Args:
            namespace: Cache namespace
            identifier: Unique identifier within namespace
            value: Value to cache
            cache_type: Type of cache entry
            ttl: Time to live in seconds (uses default if None)
            metadata: Additional metadata to store
        """
        key = self._generate_key(namespace, identifier)
        original_key = self._get_original_key(namespace, identifier)

        if ttl is None:
            ttl = self.default_ttl.get(cache_type, 300)

        current_time = time.time()
        entry = CacheEntry(
            key=original_key,  # Store original key for namespace operations
            value=value,
            created_at=current_time,
            last_accessed=current_time,
            access_count=1,
            ttl=ttl,
            cache_type=cache_type,
            metadata=metadata or {},
        )

        with self.lock:
            # Clean up expired entries
            self._evict_expired()

            # Evict LRU if cache is full
            if len(self.memory_cache) >= self.max_memory_size:
                self._evict_lru()

            self.memory_cache[key] = entry
            logger.debug(f"Cache set for {namespace}:{identifier}, TTL: {ttl}s")

    def invalidate(self, namespace: str, identifier: str | None = None) -> int:
        """
        Invalidate cache entries.

        Args:
            namespace: Cache namespace
            identifier: Specific identifier (if None, invalidates entire namespace)

        Returns:
            Number of entries invalidated
        """
        with self.lock:
            if identifier is not None:
                key = self._generate_key(namespace, identifier)
                if key in self.memory_cache:
                    del self.memory_cache[key]
                    self.stats["invalidations"] += 1
                    return 1
                return 0
            # Invalidate entire namespace
            keys_to_remove = []
            for key, entry in self.memory_cache.items():
                if entry.key.startswith(namespace + ":"):
                    keys_to_remove.append(key)

            for key in keys_to_remove:
                del self.memory_cache[key]
                self.stats["invalidations"] += 1

            return len(keys_to_remove)

    def get_stale_entries(self, namespace: str | None = None) -> list[CacheEntry]:
        """
        Get entries that are approaching expiration.

        Args:
            namespace: Optional namespace filter

        Returns:
            List of stale cache entries
        """
        with self.lock:
            stale_entries = []
            for entry in self.memory_cache.values():
                if entry.is_stale() and not entry.is_expired():
                    if namespace is None or entry.key.startswith(namespace + ":"):
                        stale_entries.append(entry)
            return stale_entries

    def refresh_entry(
        self, namespace: str, identifier: str, new_value: Any, extend_ttl: bool = True
    ) -> bool:
        """
        Refresh an existing cache entry with new value.

        Args:
            namespace: Cache namespace
            identifier: Unique identifier
            new_value: New value to cache
            extend_ttl: Whether to reset TTL to full duration

        Returns:
            True if entry was refreshed, False if not found
        """
        key = self._generate_key(namespace, identifier)

        with self.lock:
            entry = self.memory_cache.get(key)
            if entry is None:
                return False

            entry.value = new_value
            entry.touch()

            if extend_ttl:
                entry.created_at = time.time()

            self.stats["refreshes"] += 1
            logger.debug(f"Cache refreshed for {namespace}:{identifier}")
            return True

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_requests = self.stats["hits"] + self.stats["misses"]
            hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0

            return {
                **self.stats,
                "memory_entries": len(self.memory_cache),
                "hit_rate": hit_rate,
                "memory_usage_mb": self._estimate_memory_usage(),
            }

    def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics (alias for get_stats for backward compatibility)."""
        return self.get_stats()

    def _estimate_memory_usage(self) -> float:
        """Estimate memory usage in MB."""
        # Rough estimation based on average entry size
        avg_entry_size = 1024  # 1KB per entry estimate
        return (len(self.memory_cache) * avg_entry_size) / (1024 * 1024)

    def cleanup(self) -> dict[str, int]:
        """Clean up expired entries and optimize cache."""
        with self.lock:
            initial_count = len(self.memory_cache)
            self._evict_expired()
            final_count = len(self.memory_cache)

            cleaned = initial_count - final_count

            # Save to disk after cleanup
            self._save_cache()

            return {"entries_cleaned": cleaned, "entries_remaining": final_count}

    def _save_cache(self) -> None:
        """Save cache to persistent storage."""
        try:
            cache_data = {
                "entries": [entry.to_dict() for entry in self.memory_cache.values()],
                "stats": self.stats,
                "saved_at": time.time(),
            }

            with open(self.cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)

            self.stats["saves"] += 1
            logger.debug(f"Cache saved to {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _load_cache(self) -> None:
        """Load cache from persistent storage."""
        try:
            if not self.cache_file.exists():
                return

            with open(self.cache_file) as f:
                cache_data = json.load(f)

            # Load entries, filtering out expired ones
            loaded_count = 0

            for entry_data in cache_data.get("entries", []):
                entry = CacheEntry.from_dict(entry_data)
                if not entry.is_expired():
                    # Generate hash key for storage from original key
                    hash_key = hashlib.sha256(entry.key.encode()).hexdigest()
                    self.memory_cache[hash_key] = entry
                    loaded_count += 1

            # Load stats
            if "stats" in cache_data:
                self.stats.update(cache_data["stats"])

            self.stats["loads"] += 1
            logger.info(f"Cache loaded from {self.cache_file}: {loaded_count} entries")
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")

    def save(self) -> None:
        """Explicitly save cache to disk."""
        with self.lock:
            self._save_cache()

    def clear(self) -> int:
        """Clear all cache entries."""
        with self.lock:
            count = len(self.memory_cache)
            self.memory_cache.clear()
            self.stats["invalidations"] += count
            return count

    def set_ttl(self, cache_type: CacheType, ttl: float) -> None:
        """Set default TTL for a cache type."""
        self.default_ttl[cache_type] = ttl
        logger.debug(f"TTL for {cache_type.value} set to {ttl}s")


# Global cache instance
_cache_instance: IntelligentCache | None = None


def get_cache() -> IntelligentCache:
    """Get the global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = IntelligentCache()
    return _cache_instance


def initialize_cache(
    cache_file: str = "cache.json", max_memory_size: int = 1000
) -> IntelligentCache:
    """Initialize the global cache instance with custom settings."""
    global _cache_instance
    _cache_instance = IntelligentCache(cache_file, max_memory_size)
    return _cache_instance
