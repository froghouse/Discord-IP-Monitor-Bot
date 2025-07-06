"""
Comprehensive tests for the intelligent cache system.

This module tests all aspects of the cache system including:
- Basic operations (get/set/delete)
- TTL and expiration handling
- LRU eviction policies
- Cache persistence
- Statistics and performance monitoring
- Thread safety and concurrency
- Cleanup and maintenance
"""

import asyncio
import concurrent.futures
import json
import pytest
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from ip_monitor.utils.cache import (
    CacheEntry,
    CacheType,
    IntelligentCache,
    get_cache,
    initialize_cache,
)


class TestCacheEntry:
    """Test the CacheEntry dataclass functionality."""

    def test_cache_entry_initialization(self):
        """Test CacheEntry initialization with proper defaults."""
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=1000.0,
            last_accessed=1000.0,
            access_count=1,
            ttl=300.0,
            cache_type=CacheType.IP_RESULT,
        )
        
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.created_at == 1000.0
        assert entry.last_accessed == 1000.0
        assert entry.access_count == 1
        assert entry.ttl == 300.0
        assert entry.cache_type == CacheType.IP_RESULT
        assert entry.metadata == {}

    def test_cache_entry_with_metadata(self):
        """Test CacheEntry initialization with metadata."""
        metadata = {"source": "test", "priority": "high"}
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=1000.0,
            last_accessed=1000.0,
            access_count=1,
            ttl=300.0,
            cache_type=CacheType.IP_RESULT,
            metadata=metadata,
        )
        
        assert entry.metadata == metadata

    def test_is_expired_not_expired(self):
        """Test is_expired returns False for non-expired entries."""
        current_time = time.time()
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=current_time,
            last_accessed=current_time,
            access_count=1,
            ttl=300.0,
            cache_type=CacheType.IP_RESULT,
        )
        
        assert not entry.is_expired()

    def test_is_expired_expired(self):
        """Test is_expired returns True for expired entries."""
        old_time = time.time() - 400  # 400 seconds ago
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=old_time,
            last_accessed=old_time,
            access_count=1,
            ttl=300.0,  # 5 minutes TTL
            cache_type=CacheType.IP_RESULT,
        )
        
        assert entry.is_expired()

    def test_is_stale_not_stale(self):
        """Test is_stale returns False for fresh entries."""
        current_time = time.time()
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=current_time,
            last_accessed=current_time,
            access_count=1,
            ttl=300.0,
            cache_type=CacheType.IP_RESULT,
        )
        
        assert not entry.is_stale()

    def test_is_stale_stale(self):
        """Test is_stale returns True for stale entries."""
        old_time = time.time() - 250  # 250 seconds ago, 80% of 300s TTL
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=old_time,
            last_accessed=old_time,
            access_count=1,
            ttl=300.0,
            cache_type=CacheType.IP_RESULT,
        )
        
        assert entry.is_stale()

    def test_is_stale_custom_threshold(self):
        """Test is_stale with custom threshold."""
        old_time = time.time() - 150  # 150 seconds ago
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=old_time,
            last_accessed=old_time,
            access_count=1,
            ttl=300.0,
            cache_type=CacheType.IP_RESULT,
        )
        
        # Should be stale at 0.4 threshold (120s), not stale at 0.6 (180s)
        assert entry.is_stale(stale_threshold=0.4)
        assert not entry.is_stale(stale_threshold=0.6)

    def test_touch_updates_access_info(self):
        """Test touch updates last_accessed time and access_count."""
        current_time = time.time()
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=current_time,
            last_accessed=current_time,
            access_count=1,
            ttl=300.0,
            cache_type=CacheType.IP_RESULT,
        )
        
        original_access_count = entry.access_count
        original_last_accessed = entry.last_accessed
        
        # Wait a tiny bit to ensure time difference
        time.sleep(0.001)
        entry.touch()
        
        assert entry.access_count == original_access_count + 1
        assert entry.last_accessed > original_last_accessed

    def test_to_dict_serialization(self):
        """Test cache entry serialization to dictionary."""
        metadata = {"source": "test"}
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=1000.0,
            last_accessed=1000.0,
            access_count=1,
            ttl=300.0,
            cache_type=CacheType.IP_RESULT,
            metadata=metadata,
        )
        
        result = entry.to_dict()
        expected = {
            "key": "test_key",
            "value": "test_value",
            "created_at": 1000.0,
            "last_accessed": 1000.0,
            "access_count": 1,
            "ttl": 300.0,
            "cache_type": "ip_result",
            "metadata": metadata,
        }
        
        assert result == expected

    def test_from_dict_deserialization(self):
        """Test cache entry deserialization from dictionary."""
        data = {
            "key": "test_key",
            "value": "test_value",
            "created_at": 1000.0,
            "last_accessed": 1000.0,
            "access_count": 1,
            "ttl": 300.0,
            "cache_type": "ip_result",
            "metadata": {"source": "test"},
        }
        
        entry = CacheEntry.from_dict(data)
        
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.created_at == 1000.0
        assert entry.last_accessed == 1000.0
        assert entry.access_count == 1
        assert entry.ttl == 300.0
        assert entry.cache_type == CacheType.IP_RESULT
        assert entry.metadata == {"source": "test"}

    def test_from_dict_without_metadata(self):
        """Test cache entry deserialization without metadata field."""
        data = {
            "key": "test_key",
            "value": "test_value",
            "created_at": 1000.0,
            "last_accessed": 1000.0,
            "access_count": 1,
            "ttl": 300.0,
            "cache_type": "ip_result",
        }
        
        entry = CacheEntry.from_dict(data)
        assert entry.metadata == {}


class TestIntelligentCacheOperations:
    """Test basic cache operations (get, set, delete)."""

    @pytest.fixture
    def cache(self):
        """Create a temporary cache instance for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        cache = IntelligentCache(cache_file=cache_file, max_memory_size=100)
        yield cache
        
        # Cleanup
        Path(cache_file).unlink(missing_ok=True)

    def test_set_and_get_basic(self, cache):
        """Test basic set and get operations."""
        cache.set("test_namespace", "test_id", "test_value")
        result = cache.get("test_namespace", "test_id")
        
        assert result == "test_value"

    def test_set_with_custom_ttl(self, cache):
        """Test set with custom TTL."""
        cache.set("test_namespace", "test_id", "test_value", ttl=600)
        
        # Get the entry directly to check TTL
        key = cache._generate_key("test_namespace", "test_id")
        entry = cache.memory_cache[key]
        
        assert entry.ttl == 600

    def test_set_with_metadata(self, cache):
        """Test set with metadata."""
        metadata = {"source": "test", "priority": "high"}
        cache.set("test_namespace", "test_id", "test_value", metadata=metadata)
        
        key = cache._generate_key("test_namespace", "test_id")
        entry = cache.memory_cache[key]
        
        assert entry.metadata == metadata

    def test_set_with_cache_type(self, cache):
        """Test set with specific cache type."""
        cache.set("test_namespace", "test_id", "test_value", cache_type=CacheType.DNS_LOOKUP)
        
        key = cache._generate_key("test_namespace", "test_id")
        entry = cache.memory_cache[key]
        
        assert entry.cache_type == CacheType.DNS_LOOKUP
        assert entry.ttl == cache.default_ttl[CacheType.DNS_LOOKUP]

    def test_get_nonexistent_key(self, cache):
        """Test get for non-existent key returns None."""
        result = cache.get("nonexistent_namespace", "nonexistent_id")
        assert result is None

    def test_get_updates_access_info(self, cache):
        """Test get updates access count and last accessed time."""
        cache.set("test_namespace", "test_id", "test_value")
        
        key = cache._generate_key("test_namespace", "test_id")
        entry = cache.memory_cache[key]
        original_access_count = entry.access_count
        original_last_accessed = entry.last_accessed
        
        time.sleep(0.001)  # Small delay to ensure time difference
        cache.get("test_namespace", "test_id")
        
        assert entry.access_count == original_access_count + 1
        assert entry.last_accessed > original_last_accessed

    def test_set_overwrites_existing(self, cache):
        """Test set overwrites existing entries."""
        cache.set("test_namespace", "test_id", "original_value")
        cache.set("test_namespace", "test_id", "new_value")
        
        result = cache.get("test_namespace", "test_id")
        assert result == "new_value"

    def test_different_cache_types(self, cache):
        """Test different cache types use appropriate TTL."""
        cache.set("test", "id1", "value1", cache_type=CacheType.IP_RESULT)
        cache.set("test", "id2", "value2", cache_type=CacheType.DNS_LOOKUP)
        
        key1 = cache._generate_key("test", "id1")
        key2 = cache._generate_key("test", "id2")
        
        entry1 = cache.memory_cache[key1]
        entry2 = cache.memory_cache[key2]
        
        assert entry1.ttl == cache.default_ttl[CacheType.IP_RESULT]
        assert entry2.ttl == cache.default_ttl[CacheType.DNS_LOOKUP]
        assert entry1.ttl != entry2.ttl

    def test_key_generation_uniqueness(self, cache):
        """Test that key generation creates unique keys for different namespaces."""
        cache.set("namespace1", "id", "value1")
        cache.set("namespace2", "id", "value2")
        
        result1 = cache.get("namespace1", "id")
        result2 = cache.get("namespace2", "id")
        
        assert result1 == "value1"
        assert result2 == "value2"

    def test_cache_hit_miss_statistics(self, cache):
        """Test cache hit and miss statistics are tracked correctly."""
        initial_hits = cache.stats["hits"]
        initial_misses = cache.stats["misses"]
        
        # Miss
        cache.get("nonexistent", "key")
        assert cache.stats["misses"] == initial_misses + 1
        
        # Set and hit
        cache.set("test", "key", "value")
        cache.get("test", "key")
        assert cache.stats["hits"] == initial_hits + 1


class TestCacheExpiration:
    """Test cache expiration and TTL handling."""

    @pytest.fixture
    def cache(self):
        """Create a temporary cache instance for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        cache = IntelligentCache(cache_file=cache_file, max_memory_size=100)
        yield cache
        
        # Cleanup
        Path(cache_file).unlink(missing_ok=True)

    def test_expired_entry_returns_none(self, cache):
        """Test that expired entries return None."""
        # Set entry with very short TTL
        cache.set("test", "key", "value", ttl=0.001)
        
        # Wait for expiration
        time.sleep(0.002)
        
        result = cache.get("test", "key")
        assert result is None

    def test_expired_entry_removed_from_cache(self, cache):
        """Test that expired entries are removed from memory cache."""
        cache.set("test", "key", "value", ttl=0.001)
        key = cache._generate_key("test", "key")
        
        # Entry should exist initially
        assert key in cache.memory_cache
        
        # Wait for expiration and try to get
        time.sleep(0.002)
        cache.get("test", "key")
        
        # Entry should be removed
        assert key not in cache.memory_cache

    def test_expired_entry_updates_statistics(self, cache):
        """Test that expired entries update miss and eviction statistics."""
        initial_misses = cache.stats["misses"]
        initial_evictions = cache.stats["evictions"]
        
        cache.set("test", "key", "value", ttl=0.001)
        time.sleep(0.002)
        cache.get("test", "key")
        
        assert cache.stats["misses"] == initial_misses + 1
        assert cache.stats["evictions"] == initial_evictions + 1

    def test_non_expired_entry_accessible(self, cache):
        """Test that non-expired entries remain accessible."""
        cache.set("test", "key", "value", ttl=60)  # 1 minute
        
        # Should be accessible immediately
        result = cache.get("test", "key")
        assert result == "value"

    def test_stale_entry_detection(self, cache):
        """Test detection of stale entries."""
        # Set entry with moderate TTL
        cache.set("test", "key", "value", ttl=1.0)
        
        # Wait for entry to become stale but not expired
        time.sleep(0.85)  # 85% of 1 second
        
        stale_entries = cache.get_stale_entries()
        assert len(stale_entries) == 1
        assert stale_entries[0].key == "test:key"

    def test_stale_entry_still_accessible(self, cache):
        """Test that stale entries are still accessible."""
        cache.set("test", "key", "value", ttl=1.0)
        
        # Wait for stale but not expired
        time.sleep(0.85)
        
        result = cache.get("test", "key")
        assert result == "value"

    def test_get_stale_entries_with_namespace_filter(self, cache):
        """Test getting stale entries with namespace filter."""
        cache.set("namespace1", "key1", "value1", ttl=1.0)
        cache.set("namespace2", "key2", "value2", ttl=1.0)
        
        time.sleep(0.85)
        
        # Get stale entries for specific namespace
        stale_entries = cache.get_stale_entries("namespace1")
        assert len(stale_entries) == 1
        assert stale_entries[0].key == "namespace1:key1"

    def test_evict_expired_cleans_multiple_entries(self, cache):
        """Test that _evict_expired cleans multiple expired entries."""
        # Set multiple entries with short TTL
        cache.set("test", "key1", "value1", ttl=0.001)
        cache.set("test", "key2", "value2", ttl=0.001)
        cache.set("test", "key3", "value3", ttl=60)  # This one shouldn't expire
        
        initial_count = len(cache.memory_cache)
        
        # Wait for expiration
        time.sleep(0.002)
        
        # Trigger cleanup
        cache._evict_expired()
        
        # Should have removed 2 expired entries
        assert len(cache.memory_cache) == initial_count - 2
        
        # Non-expired entry should remain
        assert cache.get("test", "key3") == "value3"

    def test_set_ttl_for_cache_type(self, cache):
        """Test setting custom TTL for cache types."""
        original_ttl = cache.default_ttl[CacheType.IP_RESULT]
        new_ttl = 1200
        
        cache.set_ttl(CacheType.IP_RESULT, new_ttl)
        
        assert cache.default_ttl[CacheType.IP_RESULT] == new_ttl
        assert cache.default_ttl[CacheType.IP_RESULT] != original_ttl
        
        # New entries should use new TTL
        cache.set("test", "key", "value", cache_type=CacheType.IP_RESULT)
        key = cache._generate_key("test", "key")
        entry = cache.memory_cache[key]
        
        assert entry.ttl == new_ttl


class TestCacheLRUEviction:
    """Test LRU eviction policy."""

    @pytest.fixture
    def small_cache(self):
        """Create a cache with small max size for testing eviction."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        cache = IntelligentCache(cache_file=cache_file, max_memory_size=3)
        yield cache
        
        # Cleanup
        Path(cache_file).unlink(missing_ok=True)

    def test_lru_eviction_triggered_when_full(self, small_cache):
        """Test that LRU eviction is triggered when cache is full."""
        # Fill cache to capacity
        small_cache.set("test", "key1", "value1")
        small_cache.set("test", "key2", "value2")
        small_cache.set("test", "key3", "value3")
        
        assert len(small_cache.memory_cache) == 3
        
        # Access key1 and key2 to make key3 LRU
        small_cache.get("test", "key1")
        small_cache.get("test", "key2")
        
        # Add one more entry - should trigger eviction
        small_cache.set("test", "key4", "value4")
        
        # Should still have 3 entries
        assert len(small_cache.memory_cache) == 3
        
        # key3 should be evicted (was LRU)
        assert small_cache.get("test", "key3") is None
        
        # Others should remain
        assert small_cache.get("test", "key1") == "value1"
        assert small_cache.get("test", "key2") == "value2"
        assert small_cache.get("test", "key4") == "value4"

    def test_lru_eviction_statistics(self, small_cache):
        """Test that LRU eviction updates statistics."""
        initial_evictions = small_cache.stats["evictions"]
        
        # Fill cache beyond capacity
        small_cache.set("test", "key1", "value1")
        small_cache.set("test", "key2", "value2")
        small_cache.set("test", "key3", "value3")
        small_cache.set("test", "key4", "value4")  # Should trigger eviction
        
        # Eviction count should increase
        assert small_cache.stats["evictions"] > initial_evictions

    def test_lru_eviction_percentage(self, small_cache):
        """Test that LRU eviction removes appropriate percentage."""
        # Create cache with larger capacity for testing percentage
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        cache = IntelligentCache(cache_file=cache_file, max_memory_size=10)
        
        try:
            # Fill cache to capacity
            for i in range(10):
                cache.set("test", f"key{i}", f"value{i}")
            
            # Add one more - should trigger eviction of ~10% (at least 1)
            cache.set("test", "key_new", "value_new")
            
            # Should have evicted at least 1 entry
            assert len(cache.memory_cache) <= 10
            
        finally:
            Path(cache_file).unlink(missing_ok=True)

    def test_lru_respects_access_patterns(self, small_cache):
        """Test that LRU eviction respects access patterns."""
        # Fill cache
        small_cache.set("test", "key1", "value1")
        small_cache.set("test", "key2", "value2")
        small_cache.set("test", "key3", "value3")
        
        # Access entries in specific order
        small_cache.get("test", "key1")  # Most recently used
        time.sleep(0.001)
        small_cache.get("test", "key3")  # Second most recently used
        # key2 is least recently used
        
        # Add new entry to trigger eviction
        small_cache.set("test", "key4", "value4")
        
        # key2 should be evicted (LRU)
        assert small_cache.get("test", "key2") is None
        
        # Others should remain
        assert small_cache.get("test", "key1") == "value1"
        assert small_cache.get("test", "key3") == "value3"
        assert small_cache.get("test", "key4") == "value4"

    def test_eviction_before_expiration_cleanup(self, small_cache):
        """Test that eviction happens after expiration cleanup."""
        # Set expired entry
        small_cache.set("test", "expired", "value", ttl=0.001)
        time.sleep(0.002)
        
        # Fill cache
        small_cache.set("test", "key1", "value1")
        small_cache.set("test", "key2", "value2")
        small_cache.set("test", "key3", "value3")
        
        # The expired entry should be cleaned up during set operations
        # Cache should have exactly 3 entries (not 4)
        assert len(small_cache.memory_cache) == 3
        
        # Expired entry should not be accessible
        assert small_cache.get("test", "expired") is None

    def test_no_eviction_when_under_limit(self, small_cache):
        """Test that no eviction occurs when under capacity."""
        initial_evictions = small_cache.stats["evictions"]
        
        # Add entries under capacity
        small_cache.set("test", "key1", "value1")
        small_cache.set("test", "key2", "value2")
        
        # Should not trigger eviction
        assert small_cache.stats["evictions"] == initial_evictions
        assert len(small_cache.memory_cache) == 2


class TestCachePersistence:
    """Test cache persistence (save/load from disk)."""

    @pytest.fixture
    def temp_cache_file(self):
        """Create a temporary cache file for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        yield cache_file
        
        # Cleanup
        Path(cache_file).unlink(missing_ok=True)

    def test_save_cache_to_disk(self, temp_cache_file):
        """Test saving cache to disk."""
        cache = IntelligentCache(cache_file=temp_cache_file)
        
        # Add some entries
        cache.set("test", "key1", "value1")
        cache.set("test", "key2", "value2")
        
        # Save cache
        cache.save()
        
        # Verify file was created and contains data
        assert Path(temp_cache_file).exists()
        
        with open(temp_cache_file) as f:
            data = json.load(f)
        
        assert "entries" in data
        assert "stats" in data
        assert "saved_at" in data
        assert len(data["entries"]) == 2

    def test_load_cache_from_disk(self, temp_cache_file):
        """Test loading cache from disk."""
        # Create cache and add entries
        cache1 = IntelligentCache(cache_file=temp_cache_file)
        cache1.set("test", "key1", "value1")
        cache1.set("test", "key2", "value2")
        cache1.save()
        
        # Create new cache instance - should load from disk
        cache2 = IntelligentCache(cache_file=temp_cache_file)
        
        # Data should be loaded
        assert cache2.get("test", "key1") == "value1"
        assert cache2.get("test", "key2") == "value2"
        assert len(cache2.memory_cache) == 2

    def test_load_cache_filters_expired_entries(self, temp_cache_file):
        """Test that loading cache filters out expired entries."""
        cache1 = IntelligentCache(cache_file=temp_cache_file)
        
        # Add entry with very short TTL
        cache1.set("test", "expired", "value", ttl=0.001)
        cache1.set("test", "valid", "value", ttl=3600)
        cache1.save()
        
        # Wait for expiration
        time.sleep(0.002)
        
        # Create new cache instance
        cache2 = IntelligentCache(cache_file=temp_cache_file)
        
        # Only non-expired entry should be loaded
        assert cache2.get("test", "expired") is None
        assert cache2.get("test", "valid") == "value"
        assert len(cache2.memory_cache) == 1

    def test_load_cache_updates_statistics(self, temp_cache_file):
        """Test that loading cache updates statistics."""
        cache1 = IntelligentCache(cache_file=temp_cache_file)
        cache1.set("test", "key", "value")
        cache1.save()
        
        # Create new cache instance
        cache2 = IntelligentCache(cache_file=temp_cache_file)
        
        # Loads counter should be incremented
        assert cache2.stats["loads"] > 0

    def test_load_nonexistent_cache_file(self, temp_cache_file):
        """Test loading cache when file doesn't exist."""
        # Remove file if it exists
        Path(temp_cache_file).unlink(missing_ok=True)
        
        # Create cache - should not fail
        cache = IntelligentCache(cache_file=temp_cache_file)
        
        # Should be empty
        assert len(cache.memory_cache) == 0

    def test_save_cache_error_handling(self, temp_cache_file):
        """Test cache save error handling."""
        cache = IntelligentCache(cache_file=temp_cache_file)
        cache.set("test", "key", "value")
        
        # Mock file operations to raise exception
        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with patch("logging.Logger.error") as mock_error:
                cache.save()
                
                # Should log error
                mock_error.assert_called_once()

    def test_load_cache_error_handling(self, temp_cache_file):
        """Test cache load error handling."""
        # Create invalid JSON file
        Path(temp_cache_file).write_text("invalid json")
        
        with patch("logging.Logger.error") as mock_error:
            cache = IntelligentCache(cache_file=temp_cache_file)
            
            # Should log error and continue
            mock_error.assert_called_once()
            assert len(cache.memory_cache) == 0

    def test_cache_data_format(self, temp_cache_file):
        """Test the format of saved cache data."""
        cache = IntelligentCache(cache_file=temp_cache_file)
        
        # Add entry with metadata
        metadata = {"source": "test", "priority": "high"}
        cache.set("test", "key", "value", metadata=metadata)
        cache.save()
        
        # Load and verify format
        with open(temp_cache_file) as f:
            data = json.load(f)
        
        assert "entries" in data
        assert "stats" in data
        assert "saved_at" in data
        
        entry_data = data["entries"][0]
        assert "key" in entry_data
        assert "value" in entry_data
        assert "created_at" in entry_data
        assert "last_accessed" in entry_data
        assert "access_count" in entry_data
        assert "ttl" in entry_data
        assert "cache_type" in entry_data
        assert "metadata" in entry_data
        
        assert entry_data["metadata"] == metadata

    def test_save_preserves_statistics(self, temp_cache_file):
        """Test that save operation preserves statistics."""
        cache1 = IntelligentCache(cache_file=temp_cache_file)
        
        # Generate some statistics
        cache1.set("test", "key1", "value1")
        cache1.get("test", "key1")  # Hit
        cache1.get("test", "nonexistent")  # Miss
        cache1.save()
        
        # Load in new instance
        cache2 = IntelligentCache(cache_file=temp_cache_file)
        
        # Statistics should be preserved
        assert cache2.stats["hits"] == cache1.stats["hits"]
        assert cache2.stats["misses"] == cache1.stats["misses"]


class TestCacheStatistics:
    """Test cache statistics and performance monitoring."""

    @pytest.fixture
    def cache(self):
        """Create a temporary cache instance for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        cache = IntelligentCache(cache_file=cache_file, max_memory_size=100)
        yield cache
        
        # Cleanup
        Path(cache_file).unlink(missing_ok=True)

    def test_initial_statistics(self, cache):
        """Test initial cache statistics."""
        stats = cache.get_stats()
        
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["evictions"] == 0
        assert stats["invalidations"] == 0
        assert stats["refreshes"] == 0
        assert stats["saves"] == 0
        assert stats["loads"] >= 0  # May be > 0 due to cache loading
        assert stats["memory_entries"] == 0
        assert stats["hit_rate"] == 0
        assert stats["memory_usage_mb"] == 0

    def test_hit_rate_calculation(self, cache):
        """Test hit rate calculation."""
        # Add some entries
        cache.set("test", "key1", "value1")
        cache.set("test", "key2", "value2")
        
        # Generate hits and misses
        cache.get("test", "key1")  # Hit
        cache.get("test", "key2")  # Hit
        cache.get("test", "nonexistent")  # Miss
        
        stats = cache.get_stats()
        
        # Hit rate should be 2/3 = 0.667
        assert abs(stats["hit_rate"] - 0.6666666666666666) < 0.01
        assert stats["hits"] == 2
        assert stats["misses"] == 1

    def test_memory_entries_count(self, cache):
        """Test memory entries count."""
        stats = cache.get_stats()
        assert stats["memory_entries"] == 0
        
        # Add entries
        cache.set("test", "key1", "value1")
        cache.set("test", "key2", "value2")
        
        stats = cache.get_stats()
        assert stats["memory_entries"] == 2

    def test_eviction_statistics(self, cache):
        """Test eviction statistics tracking."""
        # Set entry that will expire
        cache.set("test", "expired", "value", ttl=0.001)
        time.sleep(0.002)
        
        initial_evictions = cache.stats["evictions"]
        
        # Access expired entry - should trigger eviction
        cache.get("test", "expired")
        
        assert cache.stats["evictions"] == initial_evictions + 1

    def test_invalidation_statistics(self, cache):
        """Test invalidation statistics tracking."""
        cache.set("test", "key1", "value1")
        cache.set("test", "key2", "value2")
        
        initial_invalidations = cache.stats["invalidations"]
        
        # Invalidate specific entry
        cache.invalidate("test", "key1")
        
        assert cache.stats["invalidations"] == initial_invalidations + 1

    def test_refresh_statistics(self, cache):
        """Test refresh statistics tracking."""
        cache.set("test", "key", "original_value")
        
        initial_refreshes = cache.stats["refreshes"]
        
        # Refresh entry
        cache.refresh_entry("test", "key", "new_value")
        
        assert cache.stats["refreshes"] == initial_refreshes + 1

    def test_save_statistics(self, cache):
        """Test save statistics tracking."""
        cache.set("test", "key", "value")
        
        initial_saves = cache.stats["saves"]
        
        # Save cache
        cache.save()
        
        assert cache.stats["saves"] == initial_saves + 1

    def test_memory_usage_estimation(self, cache):
        """Test memory usage estimation."""
        initial_stats = cache.get_stats()
        initial_usage = initial_stats["memory_usage_mb"]
        
        # Add entries
        for i in range(10):
            cache.set("test", f"key{i}", f"value{i}")
        
        stats = cache.get_stats()
        
        # Memory usage should increase
        assert stats["memory_usage_mb"] > initial_usage

    def test_statistics_with_zero_requests(self, cache):
        """Test statistics when no requests have been made."""
        stats = cache.get_stats()
        
        # Hit rate should be 0 when no requests
        assert stats["hit_rate"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_statistics_thread_safety(self, cache):
        """Test that statistics are thread-safe."""
        def worker():
            for i in range(10):
                cache.set(f"thread_{threading.current_thread().ident}", f"key{i}", f"value{i}")
                cache.get(f"thread_{threading.current_thread().ident}", f"key{i}")
        
        # Run multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        stats = cache.get_stats()
        
        # Should have processed all operations
        assert stats["hits"] == 50  # 10 hits per thread * 5 threads
        assert stats["memory_entries"] == 50  # 10 entries per thread * 5 threads


class TestCacheInvalidation:
    """Test cache invalidation functionality."""

    @pytest.fixture
    def cache(self):
        """Create a temporary cache instance for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        cache = IntelligentCache(cache_file=cache_file, max_memory_size=100)
        yield cache
        
        # Cleanup
        Path(cache_file).unlink(missing_ok=True)

    def test_invalidate_specific_entry(self, cache):
        """Test invalidating a specific cache entry."""
        cache.set("test", "key1", "value1")
        cache.set("test", "key2", "value2")
        
        # Invalidate specific entry
        result = cache.invalidate("test", "key1")
        
        assert result == 1  # One entry invalidated
        assert cache.get("test", "key1") is None
        assert cache.get("test", "key2") == "value2"

    def test_invalidate_nonexistent_entry(self, cache):
        """Test invalidating a non-existent entry."""
        result = cache.invalidate("nonexistent", "key")
        
        assert result == 0  # No entries invalidated

    def test_invalidate_entire_namespace(self, cache):
        """Test invalidating entire namespace."""
        cache.set("namespace1", "key1", "value1")
        cache.set("namespace1", "key2", "value2")
        cache.set("namespace2", "key1", "value3")
        
        # Invalidate entire namespace1
        result = cache.invalidate("namespace1")
        
        assert result == 2  # Two entries invalidated
        assert cache.get("namespace1", "key1") is None
        assert cache.get("namespace1", "key2") is None
        assert cache.get("namespace2", "key1") == "value3"  # Different namespace unaffected

    def test_invalidate_empty_namespace(self, cache):
        """Test invalidating empty namespace."""
        cache.set("other", "key", "value")
        
        result = cache.invalidate("empty_namespace")
        
        assert result == 0  # No entries invalidated
        assert cache.get("other", "key") == "value"  # Other entries unaffected

    def test_invalidate_updates_statistics(self, cache):
        """Test that invalidation updates statistics."""
        cache.set("test", "key1", "value1")
        cache.set("test", "key2", "value2")
        
        initial_invalidations = cache.stats["invalidations"]
        
        cache.invalidate("test", "key1")
        
        assert cache.stats["invalidations"] == initial_invalidations + 1

    def test_invalidate_namespace_updates_statistics(self, cache):
        """Test that namespace invalidation updates statistics correctly."""
        cache.set("test", "key1", "value1")
        cache.set("test", "key2", "value2")
        
        initial_invalidations = cache.stats["invalidations"]
        
        cache.invalidate("test")
        
        assert cache.stats["invalidations"] == initial_invalidations + 2

    def test_clear_all_entries(self, cache):
        """Test clearing all cache entries."""
        cache.set("namespace1", "key1", "value1")
        cache.set("namespace2", "key2", "value2")
        
        result = cache.clear()
        
        assert result == 2  # Two entries cleared
        assert len(cache.memory_cache) == 0
        assert cache.get("namespace1", "key1") is None
        assert cache.get("namespace2", "key2") is None

    def test_clear_empty_cache(self, cache):
        """Test clearing empty cache."""
        result = cache.clear()
        
        assert result == 0  # No entries to clear
        assert len(cache.memory_cache) == 0

    def test_clear_updates_statistics(self, cache):
        """Test that clear updates statistics."""
        cache.set("test", "key1", "value1")
        cache.set("test", "key2", "value2")
        
        initial_invalidations = cache.stats["invalidations"]
        
        cache.clear()
        
        assert cache.stats["invalidations"] == initial_invalidations + 2


class TestCacheRefresh:
    """Test cache refresh functionality."""

    @pytest.fixture
    def cache(self):
        """Create a temporary cache instance for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        cache = IntelligentCache(cache_file=cache_file, max_memory_size=100)
        yield cache
        
        # Cleanup
        Path(cache_file).unlink(missing_ok=True)

    def test_refresh_existing_entry(self, cache):
        """Test refreshing an existing cache entry."""
        cache.set("test", "key", "original_value")
        
        result = cache.refresh_entry("test", "key", "new_value")
        
        assert result is True
        assert cache.get("test", "key") == "new_value"

    def test_refresh_nonexistent_entry(self, cache):
        """Test refreshing a non-existent entry."""
        result = cache.refresh_entry("test", "nonexistent", "value")
        
        assert result is False

    def test_refresh_extends_ttl(self, cache):
        """Test that refresh extends TTL when extend_ttl=True."""
        cache.set("test", "key", "original_value", ttl=3600)
        
        key = cache._generate_key("test", "key")
        entry = cache.memory_cache[key]
        original_created_at = entry.created_at
        
        # Wait a bit then refresh
        time.sleep(0.01)
        cache.refresh_entry("test", "key", "new_value", extend_ttl=True)
        
        # Created time should be updated
        assert entry.created_at > original_created_at

    def test_refresh_without_extending_ttl(self, cache):
        """Test that refresh doesn't extend TTL when extend_ttl=False."""
        cache.set("test", "key", "original_value", ttl=3600)
        
        key = cache._generate_key("test", "key")
        entry = cache.memory_cache[key]
        original_created_at = entry.created_at
        
        # Wait a bit then refresh
        time.sleep(0.01)
        cache.refresh_entry("test", "key", "new_value", extend_ttl=False)
        
        # Created time should NOT be updated
        assert entry.created_at == original_created_at

    def test_refresh_updates_access_info(self, cache):
        """Test that refresh updates access information."""
        cache.set("test", "key", "original_value")
        
        key = cache._generate_key("test", "key")
        entry = cache.memory_cache[key]
        original_access_count = entry.access_count
        original_last_accessed = entry.last_accessed
        
        # Wait a bit then refresh
        time.sleep(0.01)
        cache.refresh_entry("test", "key", "new_value")
        
        # Access info should be updated
        assert entry.access_count == original_access_count + 1
        assert entry.last_accessed > original_last_accessed

    def test_refresh_updates_statistics(self, cache):
        """Test that refresh updates statistics."""
        cache.set("test", "key", "original_value")
        
        initial_refreshes = cache.stats["refreshes"]
        
        cache.refresh_entry("test", "key", "new_value")
        
        assert cache.stats["refreshes"] == initial_refreshes + 1


class TestCacheCleanup:
    """Test cache cleanup and maintenance."""

    @pytest.fixture
    def cache(self):
        """Create a temporary cache instance for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        cache = IntelligentCache(cache_file=cache_file, max_memory_size=100)
        yield cache
        
        # Cleanup
        Path(cache_file).unlink(missing_ok=True)

    def test_cleanup_removes_expired_entries(self, cache):
        """Test that cleanup removes expired entries."""
        # Add mix of expired and valid entries
        cache.set("test", "expired1", "value1", ttl=0.001)
        cache.set("test", "expired2", "value2", ttl=0.001)
        cache.set("test", "valid", "value3", ttl=3600)
        
        # Wait for expiration
        time.sleep(0.002)
        
        result = cache.cleanup()
        
        assert result["entries_cleaned"] == 2
        assert result["entries_remaining"] == 1
        assert cache.get("test", "valid") == "value3"
        assert cache.get("test", "expired1") is None
        assert cache.get("test", "expired2") is None

    def test_cleanup_with_no_expired_entries(self, cache):
        """Test cleanup when no entries are expired."""
        cache.set("test", "key1", "value1", ttl=3600)
        cache.set("test", "key2", "value2", ttl=3600)
        
        result = cache.cleanup()
        
        assert result["entries_cleaned"] == 0
        assert result["entries_remaining"] == 2

    def test_cleanup_empty_cache(self, cache):
        """Test cleanup on empty cache."""
        result = cache.cleanup()
        
        assert result["entries_cleaned"] == 0
        assert result["entries_remaining"] == 0

    def test_cleanup_saves_cache(self, cache):
        """Test that cleanup saves cache to disk."""
        cache.set("test", "key", "value")
        
        initial_saves = cache.stats["saves"]
        
        cache.cleanup()
        
        # Should have saved after cleanup
        assert cache.stats["saves"] == initial_saves + 1

    def test_cleanup_thread_safety(self, cache):
        """Test that cleanup is thread-safe."""
        # Add entries from multiple threads
        def add_entries():
            for i in range(10):
                cache.set(f"thread_{threading.current_thread().ident}", f"key{i}", f"value{i}")
        
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=add_entries)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Cleanup should work without issues
        result = cache.cleanup()
        
        assert result["entries_remaining"] == 30  # 10 entries * 3 threads


class TestCacheThreadSafety:
    """Test cache thread safety and concurrency."""

    @pytest.fixture
    def cache(self):
        """Create a temporary cache instance for testing."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        cache = IntelligentCache(cache_file=cache_file, max_memory_size=1000)
        yield cache
        
        # Cleanup
        Path(cache_file).unlink(missing_ok=True)

    def test_concurrent_set_operations(self, cache):
        """Test concurrent set operations."""
        def set_worker(thread_id):
            for i in range(50):
                cache.set(f"thread_{thread_id}", f"key{i}", f"value{i}")
        
        # Run multiple threads
        threads = []
        for thread_id in range(10):
            thread = threading.Thread(target=set_worker, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All entries should be present
        assert len(cache.memory_cache) == 500  # 50 entries * 10 threads

    def test_concurrent_get_operations(self, cache):
        """Test concurrent get operations."""
        # Pre-populate cache
        for i in range(100):
            cache.set("test", f"key{i}", f"value{i}")
        
        results = []
        def get_worker():
            local_results = []
            for i in range(100):
                result = cache.get("test", f"key{i}")
                local_results.append(result)
            results.extend(local_results)
        
        # Run multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=get_worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All gets should succeed
        assert len(results) == 1000  # 100 gets * 10 threads
        assert all(result is not None for result in results)

    def test_concurrent_mixed_operations(self, cache):
        """Test concurrent mixed operations (set, get, invalidate)."""
        def mixed_worker(thread_id):
            for i in range(20):
                # Set
                cache.set(f"thread_{thread_id}", f"key{i}", f"value{i}")
                # Get
                cache.get(f"thread_{thread_id}", f"key{i}")
                # Invalidate some entries
                if i % 5 == 0:
                    cache.invalidate(f"thread_{thread_id}", f"key{i}")
        
        # Run multiple threads
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=mixed_worker, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Cache should still be in consistent state
        stats = cache.get_stats()
        assert stats["hits"] > 0
        assert stats["invalidations"] > 0

    def test_concurrent_cleanup_operations(self, cache):
        """Test concurrent cleanup operations."""
        # Add entries with mix of TTLs
        for i in range(100):
            ttl = 0.001 if i % 2 == 0 else 3600  # Half will expire quickly
            cache.set("test", f"key{i}", f"value{i}", ttl=ttl)
        
        # Wait for half to expire
        time.sleep(0.002)
        
        def cleanup_worker():
            cache.cleanup()
        
        # Run multiple cleanup threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=cleanup_worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Should have cleaned up expired entries
        assert len(cache.memory_cache) == 50  # Only non-expired entries remain

    def test_concurrent_eviction_operations(self, cache):
        """Test concurrent operations that trigger eviction."""
        # Use small cache to trigger eviction
        small_cache = IntelligentCache(max_memory_size=100)
        
        def eviction_worker(thread_id):
            for i in range(50):
                small_cache.set(f"thread_{thread_id}", f"key{i}", f"value{i}")
        
        # Run multiple threads to trigger eviction
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=eviction_worker, args=(thread_id,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Cache should respect max size
        assert len(small_cache.memory_cache) <= 100
        assert small_cache.stats["evictions"] > 0

    def test_statistics_thread_safety(self, cache):
        """Test that statistics are properly updated in concurrent operations."""
        def stats_worker():
            for i in range(100):
                cache.set(f"test_{threading.current_thread().ident}", f"key{i}", f"value{i}")
                cache.get(f"test_{threading.current_thread().ident}", f"key{i}")
                cache.get(f"test_{threading.current_thread().ident}", f"nonexistent{i}")
        
        # Run multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=stats_worker)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        stats = cache.get_stats()
        
        # Statistics should be consistent
        assert stats["hits"] == 500  # 100 successful gets * 5 threads
        assert stats["misses"] == 500  # 100 failed gets * 5 threads
        assert stats["hit_rate"] == 0.5  # 50% hit rate


class TestCacheGlobalInstance:
    """Test global cache instance functionality."""

    def test_get_cache_returns_instance(self):
        """Test that get_cache returns a cache instance."""
        cache = get_cache()
        assert isinstance(cache, IntelligentCache)

    def test_get_cache_returns_same_instance(self):
        """Test that get_cache returns the same instance on multiple calls."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2

    def test_initialize_cache_creates_new_instance(self):
        """Test that initialize_cache creates a new instance."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        try:
            cache = initialize_cache(cache_file=cache_file, max_memory_size=500)
            assert isinstance(cache, IntelligentCache)
            assert cache.cache_file == Path(cache_file)
            assert cache.max_memory_size == 500
        finally:
            Path(cache_file).unlink(missing_ok=True)

    def test_initialize_cache_replaces_global_instance(self):
        """Test that initialize_cache replaces the global instance."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            cache_file = tmp_file.name
        
        try:
            # Get initial instance
            cache1 = get_cache()
            
            # Initialize with new settings
            cache2 = initialize_cache(cache_file=cache_file, max_memory_size=500)
            
            # get_cache should now return the new instance
            cache3 = get_cache()
            
            assert cache2 is cache3
            assert cache1 is not cache2
        finally:
            Path(cache_file).unlink(missing_ok=True)