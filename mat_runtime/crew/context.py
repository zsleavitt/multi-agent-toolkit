"""Context stores for inter-agent state sharing."""

from __future__ import annotations

import time
from typing import Any, Protocol


class ContextStore(Protocol):
    """Protocol for context storage backends."""

    async def get(self, key: str) -> Any | None:
        """Get a value by key. Returns None if not found or expired."""
        ...

    async def set(self, key: str, value: Any, ttl_ms: int = 0) -> None:
        """Set a value with optional TTL (0 = no expiry)."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a key. No error if key doesn't exist."""
        ...

    async def keys(self) -> list[str]:
        """List all non-expired keys."""
        ...


class NullContextStore:
    """
    No-op context store for 'none' mode.

    Implements the Null Object pattern - all operations succeed
    but nothing is stored.
    """

    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl_ms: int = 0) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass

    async def keys(self) -> list[str]:
        return []


class MemoryContextStore:
    """
    In-memory context store with lazy TTL expiry.

    Values are stored with their expiry timestamp. Expired values
    are removed lazily when accessed via get() or keys().
    """

    def __init__(self) -> None:
        # Store: key -> (value, expiry_time_ms or None)
        self._data: dict[str, tuple[Any, int | None]] = {}

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _is_expired(self, expiry: int | None) -> bool:
        if expiry is None:
            return False
        return self._now_ms() > expiry

    async def get(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None:
            return None

        value, expiry = entry
        if self._is_expired(expiry):
            del self._data[key]
            return None

        return value

    async def set(self, key: str, value: Any, ttl_ms: int = 0) -> None:
        if ttl_ms > 0:
            expiry = self._now_ms() + ttl_ms
        else:
            expiry = None
        self._data[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def keys(self) -> list[str]:
        # Clean expired keys during enumeration
        valid_keys = []
        expired_keys = []

        for key, (_, expiry) in self._data.items():
            if self._is_expired(expiry):
                expired_keys.append(key)
            else:
                valid_keys.append(key)

        for key in expired_keys:
            del self._data[key]

        return valid_keys


def create_context_store(
    store_type: str,
    path: str | None = None,
    ttl_ms: int = 0,
) -> ContextStore:
    """
    Factory function to create a context store.

    Args:
        store_type: One of 'none', 'memory', 'file'.
        path: File path for 'file' type (required if type is 'file').
        ttl_ms: Default TTL for entries (not currently used by factory).

    Returns:
        ContextStore instance.

    Raises:
        ValueError: If store_type is unknown.
        NotImplementedError: If 'file' type is requested (v2 feature).
    """
    if store_type == "none":
        return NullContextStore()
    elif store_type == "memory":
        return MemoryContextStore()
    elif store_type == "file":
        raise NotImplementedError("FileContextStore is deferred to v2")
    else:
        raise ValueError(f"Unknown context store type: {store_type}")
