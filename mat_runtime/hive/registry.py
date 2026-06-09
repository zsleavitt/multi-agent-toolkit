"""Hive discovery and runtime membership management."""

from __future__ import annotations

from pathlib import Path

from mat_runtime.crew.registry import CrewRegistry
from mat_runtime.hive.definition import HiveDefinition, load_hive_definition
from mat_runtime.hive.hive import Hive


class HiveRegistry:
    """
    Discover hive definitions from disk and manage lazy Hive instances.

    Mirrors CrewRegistry: scans ``hives/*.json`` and indexes by name.
    """

    def __init__(
        self,
        repo_root: Path | str,
        hives_dir: Path | str | None = None,
        crew_registry: CrewRegistry | None = None,
    ):
        self._repo_root = Path(repo_root).resolve()
        self._hives_dir = (
            Path(hives_dir).resolve()
            if hives_dir is not None
            else (self._repo_root / "hives").resolve()
        )
        self._crew_registry = crew_registry or CrewRegistry(
            repo_root=self._repo_root
        )
        self._definitions: dict[str, HiveDefinition] = {}
        self._hives: dict[str, Hive] = {}
        self._discover_hives()

    def _discover_hives(self) -> None:
        self._definitions.clear()
        self._hives.clear()

        if not self._hives_dir.is_dir():
            return

        for path in sorted(self._hives_dir.glob("*.json")):
            definition = load_hive_definition(
                path,
                repo_root=self._repo_root,
            )
            expected_name = path.stem
            if definition.name != expected_name:
                raise ValueError(
                    f"Hive filename '{path.name}' does not match name "
                    f"'{definition.name}'"
                )
            self._definitions[definition.name] = definition

    def list_hives(self) -> list[str]:
        """Return sorted hive names discovered from disk."""
        return sorted(self._definitions.keys())

    def get_definition(self, hive_name: str) -> HiveDefinition:
        definition = self._definitions.get(hive_name)
        if definition is None:
            raise ValueError(f"Unknown hive: {hive_name}")
        return definition

    def get_hive(self, hive_name: str) -> Hive:
        """Return a lazy Hive instance for the named hive."""
        definition = self.get_definition(hive_name)
        if hive_name not in self._hives:
            source_path = definition.source_path or (
                self._hives_dir / f"{hive_name}.json"
            )
            self._hives[hive_name] = Hive(
                definition_path=source_path,
                definition=definition,
                repo_root=self._repo_root,
                crew_registry=self._crew_registry,
            )
        return self._hives[hive_name]
