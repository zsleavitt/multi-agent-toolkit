"""Crew definition loading and configuration types."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentRef:
    """Reference to an agent within a crew."""

    name: str
    timeout_ms: int | None = None
    priority: int = 0
    required_capabilities: list[str] = field(default_factory=list)


@dataclass
class RoutingConfig:
    """Routing configuration for a crew."""

    strategy: str = "round-robin"
    match_on: list[str] = field(default_factory=list)
    fallback: str = "round-robin"
    allow_reassignment: bool = False
    prefer_idle: bool = True


@dataclass
class ConstraintsConfig:
    """Constraints configuration for a crew.

    Note: timeout_ms (crew-level timeout) is parsed but not enforced in v1.
    Enforcement is deferred to v2. Per-agent timeouts via AgentRef.timeout_ms
    are enforced.
    """

    max_concurrent_agents: int | None = None
    timeout_ms: int | None = None  # Not enforced in v1, deferred to v2
    max_tasks: int | None = None
    max_retries: int = 0
    backoff_ms: int = 1000
    backoff_multiplier: float = 2.0


@dataclass
class HooksConfig:
    """Hooks configuration for a crew."""

    on_start: str | None = None
    on_start_timeout_ms: int = 30000
    on_task_assigned: str | None = None
    on_task_assigned_timeout_ms: int = 30000
    on_task_complete: str | None = None
    on_task_complete_timeout_ms: int = 30000
    on_agent_failure: str | None = None
    on_agent_failure_timeout_ms: int = 30000
    on_finish: str | None = None
    on_finish_timeout_ms: int = 30000
    on_error: str | None = None
    on_error_timeout_ms: int = 30000


@dataclass
class CommunicationConfig:
    """Communication configuration for a crew."""

    shared_context_type: str = "none"
    shared_context_path: str | None = None
    shared_context_ttl_ms: int = 0
    message_passing_mode: str = "none"


@dataclass
class CrewDefinition:
    """Parsed crew definition."""

    name: str
    agents: list[AgentRef]
    schema_version: str = "1.0.0"
    description: str | None = None
    shared_goal: str | None = None
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)
    hooks: HooksConfig = field(default_factory=HooksConfig)
    communication: CommunicationConfig = field(default_factory=CommunicationConfig)
    source_path: Path | None = None


def _validate_hook_path(path: str) -> None:
    """Validate hook path is safe (no absolute, no traversal)."""
    if path.startswith("/") or path.startswith("\\"):
        raise ValueError(f"Hook path must be relative: {path}")
    if ".." in path:
        raise ValueError(f"Hook path cannot contain '..': {path}")


def _parse_agents(agents_data: list[Any]) -> list[AgentRef]:
    """Parse agents array into list of AgentRef."""
    result = []
    for item in agents_data:
        if isinstance(item, str):
            result.append(AgentRef(name=item))
        elif isinstance(item, dict):
            result.append(
                AgentRef(
                    name=item["name"],
                    timeout_ms=item.get("timeout_ms"),
                    priority=item.get("priority", 0),
                    required_capabilities=item.get("required_capabilities", []),
                )
            )
        else:
            raise ValueError(f"Invalid agent entry: {item}")
    return result


def _parse_routing(data: dict[str, Any] | None) -> RoutingConfig:
    """Parse routing configuration."""
    if not data:
        return RoutingConfig()

    task_assignment = data.get("task_assignment", {})
    return RoutingConfig(
        strategy=data.get("strategy", "round-robin"),
        match_on=data.get("match_on", []),
        fallback=data.get("fallback", "round-robin"),
        allow_reassignment=task_assignment.get("allow_reassignment", False),
        prefer_idle=task_assignment.get("prefer_idle", True),
    )


def _parse_constraints(data: dict[str, Any] | None) -> ConstraintsConfig:
    """Parse constraints configuration."""
    if not data:
        return ConstraintsConfig()

    retry_policy = data.get("retry_policy", {})
    return ConstraintsConfig(
        max_concurrent_agents=data.get("max_concurrent_agents"),
        timeout_ms=data.get("timeout_ms"),
        max_tasks=data.get("max_tasks"),
        max_retries=retry_policy.get("max_retries", 0),
        backoff_ms=retry_policy.get("backoff_ms", 1000),
        backoff_multiplier=retry_policy.get("backoff_multiplier", 2.0),
    )


def _parse_hooks(data: dict[str, Any] | None) -> HooksConfig:
    """Parse hooks configuration with semantic validation."""
    if not data:
        return HooksConfig()

    # Validate all hook paths
    for key in ["on_start", "on_task_assigned", "on_task_complete",
                "on_agent_failure", "on_finish", "on_error"]:
        if path := data.get(key):
            _validate_hook_path(path)

    return HooksConfig(
        on_start=data.get("on_start"),
        on_start_timeout_ms=data.get("on_start_timeout_ms", 30000),
        on_task_assigned=data.get("on_task_assigned"),
        on_task_assigned_timeout_ms=data.get("on_task_assigned_timeout_ms", 30000),
        on_task_complete=data.get("on_task_complete"),
        on_task_complete_timeout_ms=data.get("on_task_complete_timeout_ms", 30000),
        on_agent_failure=data.get("on_agent_failure"),
        on_agent_failure_timeout_ms=data.get("on_agent_failure_timeout_ms", 30000),
        on_finish=data.get("on_finish"),
        on_finish_timeout_ms=data.get("on_finish_timeout_ms", 30000),
        on_error=data.get("on_error"),
        on_error_timeout_ms=data.get("on_error_timeout_ms", 30000),
    )


def _parse_communication(data: dict[str, Any] | None) -> CommunicationConfig:
    """Parse communication configuration."""
    if not data:
        return CommunicationConfig()

    shared_context = data.get("shared_context", {})
    message_passing = data.get("message_passing", {})

    return CommunicationConfig(
        shared_context_type=shared_context.get("type", "none"),
        shared_context_path=shared_context.get("path"),
        shared_context_ttl_ms=shared_context.get("ttl_ms", 0),
        message_passing_mode=message_passing.get("mode", "none"),
    )


def load_crew_definition(path: Path | str) -> CrewDefinition:
    """
    Load and parse a crew definition from a JSON file.

    Args:
        path: Path to the crew definition JSON file.

    Returns:
        Parsed CrewDefinition.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the definition is invalid.
        json.JSONDecodeError: If the file isn't valid JSON.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    return CrewDefinition(
        name=data["name"],
        agents=_parse_agents(data["agents"]),
        schema_version=data.get("schema_version", "1.0.0"),
        description=data.get("description"),
        shared_goal=data.get("shared_goal"),
        routing=_parse_routing(data.get("routing")),
        constraints=_parse_constraints(data.get("constraints")),
        hooks=_parse_hooks(data.get("hooks")),
        communication=_parse_communication(data.get("communication")),
        source_path=path,
    )
