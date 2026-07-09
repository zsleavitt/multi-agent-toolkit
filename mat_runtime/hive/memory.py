"""Hive shared memory store for cross-crew context."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mat_runtime.crew.context import MemoryContextStore

GLOBAL_NAMESPACE = "global"


def crew_namespace(crew_name: str) -> str:
    """Return the namespace key for a crew."""
    return f"crew:{crew_name}"


@dataclass(frozen=True)
class NamespacePermissions:
    """Read/write permissions for the global namespace."""

    read: bool = True
    write: bool = True


class _MemoryBackend:
    """In-process namespace storage with lazy TTL expiry."""

    def __init__(self) -> None:
        self._namespaces: dict[str, MemoryContextStore] = {}
        self._lock = asyncio.Lock()

    def _namespace_store(self, namespace: str) -> MemoryContextStore:
        store = self._namespaces.get(namespace)
        if store is None:
            store = MemoryContextStore()
            self._namespaces[namespace] = store
        return store

    async def get(self, namespace: str, key: str) -> Any | None:
        async with self._lock:
            return await self._namespace_store(namespace).get(key)

    async def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl_ms: int = 0,
    ) -> None:
        async with self._lock:
            await self._namespace_store(namespace).set(key, value, ttl_ms=ttl_ms)

    async def delete(self, namespace: str, key: str) -> None:
        async with self._lock:
            await self._namespace_store(namespace).delete(key)

    async def keys(self, namespace: str) -> list[str]:
        async with self._lock:
            return await self._namespace_store(namespace).keys()

    async def snapshot(self) -> dict[str, dict[str, tuple[Any, int | None]]]:
        async with self._lock:
            data: dict[str, dict[str, tuple[Any, int | None]]] = {}
            for namespace, store in self._namespaces.items():
                data[namespace] = dict(store._data)
            return data


class _FileBackend(_MemoryBackend):
    """JSON file-backed namespace storage."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.is_file():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                raise ValueError(
                    f"Hive memory file is corrupt or unreadable ({self._path}): {e}"
                ) from e
            if isinstance(raw, dict):
                for namespace, entries in raw.items():
                    if not isinstance(namespace, str) or not isinstance(entries, dict):
                        continue
                    store = MemoryContextStore()
                    for key, entry in entries.items():
                        if (
                            isinstance(key, str)
                            and isinstance(entry, list)
                            and len(entry) == 2
                        ):
                            store._data[key] = (entry[0], entry[1])
                    self._namespaces[namespace] = store

    async def _persist(self) -> None:
        snapshot = await self.snapshot()
        serializable = {
            namespace: {
                key: [value, expiry]
                for key, (value, expiry) in entries.items()
            }
            for namespace, entries in snapshot.items()
        }
        self._path.write_text(
            json.dumps(serializable, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    async def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl_ms: int = 0,
    ) -> None:
        await super().set(namespace, key, value, ttl_ms=ttl_ms)
        await self._persist()

    async def delete(self, namespace: str, key: str) -> None:
        await super().delete(namespace, key)
        await self._persist()


class ScopedHiveMemoryView:
    """
    Crew-scoped view over a HiveMemoryStore.

    Implements the same async get/set/delete/keys API as crew context stores.
    Crew-private keys live in ``crew:<name>``; global keys are readable when
    permitted and writable via ``set_global`` / ``delete_global``.
    """

    def __init__(
        self,
        store: HiveMemoryStore,
        crew_name: str,
        permissions: NamespacePermissions,
    ) -> None:
        self._store = store
        self._crew_name = crew_name
        self._permissions = permissions

    @property
    def crew_name(self) -> str:
        return self._crew_name

    async def get(self, key: str) -> Any | None:
        # Check key presence via keys() rather than value truthiness — the crew
        # may have explicitly stored None, which must shadow the global namespace.
        crew_keys = await self._store.keys(crew_namespace(self._crew_name))
        if key in crew_keys:
            return await self._store.get(crew_namespace(self._crew_name), key)
        if self._permissions.read:
            return await self._store.get(GLOBAL_NAMESPACE, key)
        return None

    async def set(self, key: str, value: Any, ttl_ms: int = 0) -> None:
        await self._store.set(
            crew_namespace(self._crew_name),
            key,
            value,
            ttl_ms=ttl_ms,
        )

    async def delete(self, key: str) -> None:
        await self._store.delete(crew_namespace(self._crew_name), key)

    async def keys(self) -> list[str]:
        crew_keys = await self._store.keys(crew_namespace(self._crew_name))
        if not self._permissions.read:
            return sorted(crew_keys)

        global_keys = [
            f"global:{key}"
            for key in await self._store.keys(GLOBAL_NAMESPACE)
        ]
        return sorted(crew_keys + global_keys)

    async def get_global(self, key: str) -> Any | None:
        if not self._permissions.read:
            return None
        return await self._store.get(GLOBAL_NAMESPACE, key)

    async def set_global(self, key: str, value: Any, ttl_ms: int = 0) -> None:
        if not self._permissions.write:
            raise PermissionError(
                f"Crew '{self._crew_name}' cannot write to global hive memory"
            )
        await self._store.set(GLOBAL_NAMESPACE, key, value, ttl_ms=ttl_ms)

    async def delete_global(self, key: str) -> None:
        if not self._permissions.write:
            raise PermissionError(
                f"Crew '{self._crew_name}' cannot write to global hive memory"
            )
        await self._store.delete(GLOBAL_NAMESPACE, key)


class HiveMemoryStore:
    """Shared memory store with namespace isolation across crews."""

    def __init__(
        self,
        backend: _MemoryBackend,
        *,
        default_ttl_ms: int = 0,
        permissions: dict[str, NamespacePermissions] | None = None,
    ) -> None:
        self._backend = backend
        self._default_ttl_ms = default_ttl_ms
        self._permissions = permissions or {}

    async def get(self, namespace: str, key: str) -> Any | None:
        return await self._backend.get(namespace, key)

    async def set(
        self,
        namespace: str,
        key: str,
        value: Any,
        ttl_ms: int | None = None,
    ) -> None:
        effective_ttl = self._default_ttl_ms if ttl_ms is None else ttl_ms
        await self._backend.set(namespace, key, value, ttl_ms=effective_ttl)

    async def delete(self, namespace: str, key: str) -> None:
        await self._backend.delete(namespace, key)

    async def keys(self, namespace: str) -> list[str]:
        return await self._backend.keys(namespace)

    def scope_for(self, crew_name: str) -> ScopedHiveMemoryView:
        perms = self._permissions.get(crew_name, NamespacePermissions())
        return ScopedHiveMemoryView(self, crew_name, perms)


def create_hive_memory_store(
    store_type: str,
    *,
    path: str | None = None,
    ttl_ms: int = 0,
    permissions: dict[str, NamespacePermissions] | None = None,
    repo_root: Path | str | None = None,
) -> HiveMemoryStore:
    """
    Factory for hive memory stores.

    Args:
        store_type: One of ``memory`` or ``file``.
        path: Relative path for the file backend.
        ttl_ms: Default TTL for entries (0 = no expiry).
        permissions: Per-crew global namespace permissions.
        repo_root: Repository root for resolving file paths.

    Raises:
        ValueError: If store_type is unknown or file path is missing.
    """
    if store_type == "memory":
        backend: _MemoryBackend = _MemoryBackend()
    elif store_type == "file":
        if not path:
            raise ValueError("shared_memory.path is required for file backend")
        root = Path(repo_root or ".").resolve()
        backend = _FileBackend(root / path)
    else:
        raise ValueError(f"Unknown hive memory store type: {store_type}")

    return HiveMemoryStore(
        backend,
        default_ttl_ms=ttl_ms,
        permissions=permissions,
    )
