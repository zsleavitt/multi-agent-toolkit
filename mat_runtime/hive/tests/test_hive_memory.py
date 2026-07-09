"""Tests for hive shared memory store."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

from mat_runtime.hive.memory import (
    GLOBAL_NAMESPACE,
    NamespacePermissions,
    create_hive_memory_store,
    crew_namespace,
)


class TestHiveMemoryStore:
    def test_namespace_isolation(self) -> None:
        store = create_hive_memory_store("memory")
        crew_a = store.scope_for("crew-a")
        crew_b = store.scope_for("crew-b")

        asyncio.run(crew_a.set("token", "alpha"))
        asyncio.run(crew_b.set("token", "beta"))

        assert asyncio.run(crew_a.get("token")) == "alpha"
        assert asyncio.run(crew_b.get("token")) == "beta"

    def test_global_namespace_shared_across_crews(self) -> None:
        store = create_hive_memory_store("memory")
        crew_a = store.scope_for("crew-a")
        crew_b = store.scope_for("crew-b")

        asyncio.run(crew_a.set_global("handoff", {"step": 1}))
        assert asyncio.run(crew_b.get_global("handoff")) == {"step": 1}
        assert asyncio.run(crew_b.get("handoff")) == {"step": 1}

    def test_permissions_block_global_write(self) -> None:
        store = create_hive_memory_store(
            "memory",
            permissions={
                "reader": NamespacePermissions(read=True, write=False),
            },
        )
        reader = store.scope_for("reader")

        with pytest.raises(PermissionError):
            asyncio.run(reader.set_global("blocked", "value"))

    def test_permissions_block_global_read(self) -> None:
        store = create_hive_memory_store(
            "memory",
            permissions={
                "blind": NamespacePermissions(read=False, write=True),
            },
        )
        writer = store.scope_for("writer")
        blind = store.scope_for("blind")

        asyncio.run(writer.set_global("secret", "value"))
        assert asyncio.run(blind.get_global("secret")) is None
        assert asyncio.run(blind.get("secret")) is None
        assert "global:secret" not in asyncio.run(blind.keys())

    def test_ttl_expiry(self) -> None:
        store = create_hive_memory_store("memory")
        scoped = store.scope_for("crew-a")

        asyncio.run(scoped.set_global("expires", "soon", ttl_ms=50))
        assert asyncio.run(scoped.get_global("expires")) == "soon"
        time.sleep(0.1)
        assert asyncio.run(scoped.get_global("expires")) is None

    def test_delete_and_keys(self) -> None:
        store = create_hive_memory_store("memory")
        scoped = store.scope_for("crew-a")

        asyncio.run(scoped.set("local", 1))
        asyncio.run(scoped.set_global("shared", 2))
        assert scoped.crew_name == "crew-a"
        assert sorted(asyncio.run(scoped.keys())) == ["global:shared", "local"]

        asyncio.run(scoped.delete("local"))
        asyncio.run(scoped.delete_global("shared"))
        assert asyncio.run(scoped.keys()) == []

    def test_low_level_namespace_api(self) -> None:
        store = create_hive_memory_store("memory")

        asyncio.run(store.set(crew_namespace("crew-a"), "key", "value"))
        assert asyncio.run(store.get(crew_namespace("crew-a"), "key")) == "value"
        assert asyncio.run(store.keys(crew_namespace("crew-a"))) == ["key"]
        asyncio.run(store.delete(crew_namespace("crew-a"), "key"))
        assert asyncio.run(store.get(GLOBAL_NAMESPACE, "key")) is None

    def test_file_backend_persists(self, tmp_path: Path) -> None:
        path = tmp_path / "hive-memory.json"
        store = create_hive_memory_store(
            "file",
            path=str(path),
            repo_root=tmp_path,
        )
        scoped = store.scope_for("crew-a")
        asyncio.run(scoped.set_global("persisted", "value"))

        reloaded = create_hive_memory_store(
            "file",
            path=str(path),
            repo_root=tmp_path,
        )
        assert (
            asyncio.run(reloaded.scope_for("crew-b").get_global("persisted"))
            == "value"
        )
        assert (
            json.loads(path.read_text(encoding="utf-8"))["global"]["persisted"][0]
            == "value"
        )

    def test_create_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown hive memory store type"):
            create_hive_memory_store("redis")

    def test_create_file_without_path_raises(self) -> None:
        with pytest.raises(ValueError, match="shared_memory.path is required"):
            create_hive_memory_store("file")
