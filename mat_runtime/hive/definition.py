"""Hive definition loading and configuration types."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mat_runtime.hive.validation import semantic_validation
from mat_runtime.hive.memory import NamespacePermissions


@dataclass
class CrewEntry:
    """Reference to a crew within a hive."""

    ref: str
    depends_on: list[str] = field(default_factory=list)
    role: str | None = None


@dataclass
class QuotasConfig:
    """Hive-wide quota limits."""

    max_agent_invocations: int | None = None


@dataclass
class SharedMemoryConfig:
    """Hive-wide shared memory configuration."""

    type: str = "memory"
    path: str | None = None
    ttl_ms: int = 0
    permissions: dict[str, NamespacePermissions] = field(default_factory=dict)


@dataclass
class GlobalConfig:
    """Hive-wide resource limits."""

    max_concurrent_crews: int | None = None
    timeout_ms: int | None = None
    max_tasks: int | None = None
    quotas: QuotasConfig = field(default_factory=QuotasConfig)
    shared_memory: SharedMemoryConfig = field(default_factory=SharedMemoryConfig)


@dataclass
class RoutingRule:
    """Explicit inter-crew routing rule."""

    from_crew: str
    to_crew: str
    when: str
    condition: str | None = None


@dataclass
class InterCrewRoutingConfig:
    """Inter-crew routing configuration."""

    strategy: str = "sequential"
    default_handoff: str = "on_success"
    rules: list[RoutingRule] = field(default_factory=list)


@dataclass
class HiveDefinition:
    """Parsed hive definition."""

    name: str
    crews: list[CrewEntry]
    schema_version: str = "1.0.0"
    description: str | None = None
    shared_goal: str | None = None
    global_config: GlobalConfig = field(default_factory=GlobalConfig)
    inter_crew_routing: InterCrewRoutingConfig = field(
        default_factory=InterCrewRoutingConfig
    )
    source_path: Path | None = None


def _load_known_crew_refs(repo_root: Path) -> set[str]:
    crews_dir = repo_root / "crews"
    refs: set[str] = set()
    if not crews_dir.is_dir():
        return refs
    for path in crews_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            name = data.get("name")
            if isinstance(name, str) and name:
                refs.add(name)
        except (json.JSONDecodeError, OSError):
            continue
    return refs


def _parse_crews(crews_data: list[Any]) -> list[CrewEntry]:
    result: list[CrewEntry] = []
    for item in crews_data:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid crew entry: {item}")
        ref = item.get("ref")
        if not isinstance(ref, str) or not ref:
            raise ValueError("Each crew entry requires a non-empty 'ref'")
        result.append(
            CrewEntry(
                ref=ref,
                depends_on=list(item.get("depends_on") or []),
                role=item.get("role"),
            )
        )
    return result


def _parse_shared_memory(data: dict[str, Any] | None) -> SharedMemoryConfig:
    if not data:
        return SharedMemoryConfig()

    store_type = data.get("type", "memory")
    if store_type not in {"memory", "file"}:
        raise ValueError(
            f"global_config.shared_memory.type '{store_type}' not valid. "
            "Use one of: file, memory"
        )

    permissions: dict[str, NamespacePermissions] = {}
    raw_permissions = data.get("permissions") or {}
    if isinstance(raw_permissions, dict):
        for crew_name, config in raw_permissions.items():
            if not isinstance(crew_name, str) or not isinstance(config, dict):
                continue
            permissions[crew_name] = NamespacePermissions(
                read=bool(config.get("read", True)),
                write=bool(config.get("write", True)),
            )

    return SharedMemoryConfig(
        type=store_type,
        path=data.get("path"),
        ttl_ms=int(data.get("ttl_ms", 0) or 0),
        permissions=permissions,
    )


def _parse_global_config(data: dict[str, Any] | None) -> GlobalConfig:
    if not data:
        return GlobalConfig()

    quotas_data = data.get("quotas") or {}
    quotas = QuotasConfig(
        max_agent_invocations=quotas_data.get("max_agent_invocations"),
    )
    return GlobalConfig(
        max_concurrent_crews=data.get("max_concurrent_crews"),
        timeout_ms=data.get("timeout_ms"),
        max_tasks=data.get("max_tasks"),
        quotas=quotas,
        shared_memory=_parse_shared_memory(data.get("shared_memory")),
    )


def _parse_routing_rules(rules_data: list[Any] | None) -> list[RoutingRule]:
    if not rules_data:
        return []

    rules: list[RoutingRule] = []
    for item in rules_data:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid routing rule: {item}")
        rules.append(
            RoutingRule(
                from_crew=item["from"],
                to_crew=item["to"],
                when=item["when"],
                condition=item.get("condition"),
            )
        )
    return rules


def _parse_inter_crew_routing(
    data: dict[str, Any] | None,
) -> InterCrewRoutingConfig:
    if not data:
        return InterCrewRoutingConfig()

    strategy = data.get("strategy", "sequential")
    valid_strategies = {"sequential", "capability", "dependency", "manual"}
    if strategy not in valid_strategies:
        raise ValueError(
            f"inter_crew_routing.strategy '{strategy}' not valid. "
            f"Use one of: {', '.join(sorted(valid_strategies))}"
        )

    default_handoff = data.get("default_handoff", "on_success")
    valid_handoffs = {"on_success", "always", "never"}
    if default_handoff not in valid_handoffs:
        raise ValueError(
            f"inter_crew_routing.default_handoff '{default_handoff}' not valid. "
            f"Use one of: {', '.join(sorted(valid_handoffs))}"
        )

    rules = _parse_routing_rules(data.get("rules"))
    if strategy == "manual" and not rules:
        raise ValueError(
            "inter_crew_routing.strategy 'manual' requires at least one rule"
        )

    return InterCrewRoutingConfig(
        strategy=strategy,
        default_handoff=default_handoff,
        rules=rules,
    )


def load_hive_definition(
    path: Path | str,
    *,
    repo_root: Path | str | None = None,
    known_crews: set[str] | None = None,
) -> HiveDefinition:
    """
    Load and parse a hive definition from a JSON file.

    Args:
        path: Path to the hive definition JSON file.
        repo_root: Repository root for crew ref validation. Defaults to
            walking up from the definition file.
        known_crews: Optional set of valid crew names. When omitted, loads
            from ``crews/*.json`` under repo_root.

    Returns:
        Parsed HiveDefinition.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the definition is invalid.
        json.JSONDecodeError: If the file isn't valid JSON.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("Hive definition missing required field: name")

    crews = data.get("crews")
    if not isinstance(crews, list) or not crews:
        raise ValueError("Hive definition requires at least one crew entry")

    if repo_root is None:
        repo_root = path.parent
    repo_root = Path(repo_root).resolve()

    if known_crews is None:
        known_crews = _load_known_crew_refs(repo_root)

    semantic_validation(data, path, known_crews)

    return HiveDefinition(
        name=name,
        crews=_parse_crews(crews),
        schema_version=data.get("schema_version", "1.0.0"),
        description=data.get("description"),
        shared_goal=data.get("shared_goal"),
        global_config=_parse_global_config(data.get("global_config")),
        inter_crew_routing=_parse_inter_crew_routing(
            data.get("inter_crew_routing")
        ),
        source_path=path,
    )
