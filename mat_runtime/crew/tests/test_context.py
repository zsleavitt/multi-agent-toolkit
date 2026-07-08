"""Tests for context stores."""

from __future__ import annotations

import asyncio
import time

import pytest

from mat_runtime.crew.context import (
    MemoryContextStore,
    NullContextStore,
    create_context_store,
)


class TestMemoryContextStore:
    """Tests for MemoryContextStore."""

    def test_get_set_basic(self) -> None:
        store = MemoryContextStore()
        asyncio.run(store.set("key1", {"value": 42}))
        result = asyncio.run(store.get("key1"))
        assert result == {"value": 42}

    def test_get_missing_returns_none(self) -> None:
        store = MemoryContextStore()
        result = asyncio.run(store.get("nonexistent"))
        assert result is None

    def test_delete(self) -> None:
        store = MemoryContextStore()
        asyncio.run(store.set("key1", "value"))
        asyncio.run(store.delete("key1"))
        result = asyncio.run(store.get("key1"))
        assert result is None

    def test_delete_nonexistent_no_error(self) -> None:
        store = MemoryContextStore()
        asyncio.run(store.delete("nonexistent"))  # Should not raise

    def test_keys(self) -> None:
        store = MemoryContextStore()
        asyncio.run(store.set("a", 1))
        asyncio.run(store.set("b", 2))
        asyncio.run(store.set("c", 3))
        keys = asyncio.run(store.keys())
        assert sorted(keys) == ["a", "b", "c"]

    def test_ttl_expiry(self) -> None:
        store = MemoryContextStore()
        asyncio.run(store.set("expires", "soon", ttl_ms=50))
        # Should exist immediately
        assert asyncio.run(store.get("expires")) == "soon"
        # Wait for expiry
        time.sleep(0.1)
        # Should be gone (lazy expiry on read)
        assert asyncio.run(store.get("expires")) is None

    def test_ttl_zero_no_expiry(self) -> None:
        store = MemoryContextStore()
        asyncio.run(store.set("forever", "value", ttl_ms=0))
        time.sleep(0.05)
        assert asyncio.run(store.get("forever")) == "value"


class TestNullContextStore:
    """Tests for NullContextStore (Null Object pattern)."""

    def test_get_always_none(self) -> None:
        store = NullContextStore()
        asyncio.run(store.set("key", "value"))
        result = asyncio.run(store.get("key"))
        assert result is None

    def test_keys_always_empty(self) -> None:
        store = NullContextStore()
        asyncio.run(store.set("key", "value"))
        keys = asyncio.run(store.keys())
        assert keys == []

    def test_delete_no_error(self) -> None:
        store = NullContextStore()
        asyncio.run(store.delete("key"))  # Should not raise


class TestCreateContextStore:
    """Tests for context store factory."""

    def test_create_none_returns_null(self) -> None:
        store = create_context_store("none")
        assert isinstance(store, NullContextStore)

    def test_create_memory_returns_memory(self) -> None:
        store = create_context_store("memory")
        assert isinstance(store, MemoryContextStore)

    def test_create_file_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            create_context_store("file", path="some/path")

    def test_create_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown context store type"):
            create_context_store("unknown")
