"""
Navigation Cache

Manages cached navigation snapshots for pagination.
Based on partsbox_mcp PaginationCache pattern.
"""

import uuid
from dataclasses import dataclass, field
from time import time
from typing import Any


@dataclass
class CacheEntry:
    """Cached navigation snapshot with TTL."""

    url: str
    snapshot_json: list[dict] | dict | Any
    created_at: float = field(default_factory=time)
    last_accessed: float = field(default_factory=time)
    ttl: int = 300  # 5 minutes default

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return time() - self.last_accessed > self.ttl

    def touch(self) -> None:
        """Update last access time."""
        self.last_accessed = time()


class NavigationCache:
    """Manages cached navigation snapshots for pagination."""

    def __init__(self, default_ttl: int = 300):
        """
        Initialize navigation cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 300 = 5 minutes)
        """
        self._cache: dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl

    def create(self, url: str, snapshot_json: Any, ttl: int | None = None) -> str:
        """
        Store snapshot and return cache key.

        Args:
            url: URL that was navigated to
            snapshot_json: Parsed ARIA snapshot as JSON
            ttl: Optional custom TTL in seconds

        Returns:
            Cache key for future retrieval
        """
        self._lazy_cleanup()
        key = f"nav_{uuid.uuid4().hex[:8]}"
        entry_ttl = ttl if ttl is not None else self._default_ttl
        self._cache[key] = CacheEntry(
            url=url, snapshot_json=snapshot_json, ttl=entry_ttl
        )
        return key

    def get(self, key: str) -> CacheEntry | None:
        """
        Retrieve cache entry.

        Args:
            key: Cache key from previous create() call

        Returns:
            CacheEntry if found and not expired, None otherwise
        """
        self._lazy_cleanup()

        entry = self._cache.get(key)
        if entry is None:
            return None

        if entry.is_expired:
            del self._cache[key]
            return None

        entry.touch()
        return entry

    def delete(self, key: str) -> bool:
        """
        Delete cache entry.

        Args:
            key: Cache key to delete

        Returns:
            True if entry was deleted, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def _lazy_cleanup(self) -> None:
        """Remove expired entries on each access."""
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired]
        for key in expired_keys:
            del self._cache[key]

    def __len__(self) -> int:
        """Return number of cached entries."""
        return len(self._cache)
