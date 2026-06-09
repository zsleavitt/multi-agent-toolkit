"""Crew discovery and runtime membership management."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from mat_runtime.crew.crew import Crew
from mat_runtime.crew.definition import (
    AgentRef,
    CommunicationConfig,
    ConstraintsConfig,
    CrewDefinition,
    HooksConfig,
    RoutingConfig,
    load_crew_definition,
)
from mat_runtime.router import AgentRouter


def _agent_ref_to_json(agent: AgentRef) -> str | dict:
    """Serialize an AgentRef to its JSON representation."""
    if (
        agent.timeout_ms is None
        and agent.priority == 0
        and not agent.required_capabilities
    ):
        return agent.name

    data: dict = {"name": agent.name}
    if agent.timeout_ms is not None:
        data["timeout_ms"] = agent.timeout_ms
    if agent.priority != 0:
        data["priority"] = agent.priority
    if agent.required_capabilities:
        data["required_capabilities"] = list(agent.required_capabilities)
    return data


def _routing_to_json(routing: RoutingConfig) -> dict:
    data: dict = {"strategy": routing.strategy}
    if routing.match_on:
        data["match_on"] = list(routing.match_on)
    if routing.fallback != "round-robin":
        data["fallback"] = routing.fallback
    if routing.allow_reassignment or not routing.prefer_idle:
        data["task_assignment"] = {
            "allow_reassignment": routing.allow_reassignment,
            "prefer_idle": routing.prefer_idle,
        }
    return data


def _constraints_to_json(constraints: ConstraintsConfig) -> dict:
    data: dict = {}
    if constraints.max_concurrent_agents is not None:
        data["max_concurrent_agents"] = constraints.max_concurrent_agents
    if constraints.timeout_ms is not None:
        data["timeout_ms"] = constraints.timeout_ms
    if constraints.max_tasks is not None:
        data["max_tasks"] = constraints.max_tasks
    if (
        constraints.max_retries != 0
        or constraints.backoff_ms != 1000
        or constraints.backoff_multiplier != 2.0
    ):
        retry: dict = {}
        if constraints.max_retries != 0:
            retry["max_retries"] = constraints.max_retries
        if constraints.backoff_ms != 1000:
            retry["backoff_ms"] = constraints.backoff_ms
        if constraints.backoff_multiplier != 2.0:
            retry["backoff_multiplier"] = constraints.backoff_multiplier
        data["retry_policy"] = retry
    return data


def _hooks_to_json(hooks: HooksConfig) -> dict:
    data: dict = {}
    hook_fields = [
        ("on_start", "on_start_timeout_ms"),
        ("on_task_assigned", "on_task_assigned_timeout_ms"),
        ("on_task_complete", "on_task_complete_timeout_ms"),
        ("on_agent_failure", "on_agent_failure_timeout_ms"),
        ("on_finish", "on_finish_timeout_ms"),
        ("on_error", "on_error_timeout_ms"),
    ]
    for path_key, timeout_key in hook_fields:
        path = getattr(hooks, path_key)
        timeout = getattr(hooks, timeout_key)
        if path:
            data[path_key] = path
        if path and timeout != 30000:
            data[timeout_key] = timeout
    return data


def _communication_to_json(communication: CommunicationConfig) -> dict:
    data: dict = {}
    shared: dict = {}
    if communication.shared_context_type != "none":
        shared["type"] = communication.shared_context_type
    if communication.shared_context_path:
        shared["path"] = communication.shared_context_path
    if communication.shared_context_ttl_ms:
        shared["ttl_ms"] = communication.shared_context_ttl_ms
    if shared:
        data["shared_context"] = shared

    if communication.message_passing_mode != "none":
        data["message_passing"] = {"mode": communication.message_passing_mode}
    return data


def definition_to_dict(definition: CrewDefinition) -> dict:
    """Convert a CrewDefinition to a JSON-serializable dict."""
    data: dict = {
        "schema_version": definition.schema_version,
        "name": definition.name,
        "agents": [_agent_ref_to_json(agent) for agent in definition.agents],
    }
    if definition.description:
        data["description"] = definition.description
    if definition.shared_goal:
        data["shared_goal"] = definition.shared_goal

    data["routing"] = _routing_to_json(definition.routing)

    constraints = _constraints_to_json(definition.constraints)
    if constraints:
        data["constraints"] = constraints

    hooks = _hooks_to_json(definition.hooks)
    if hooks:
        data["hooks"] = hooks

    communication = _communication_to_json(definition.communication)
    if communication:
        data["communication"] = communication

    return data


class CrewRegistry:
    """
    Discover crew definitions from disk and manage runtime membership.

    Runtime mutations update in-memory definitions only. Call ``save()`` to
    persist changes back to ``crews/{name}.json``.

    Note: This class is not thread-safe. Concurrent calls to ``add_agent``,
    ``remove_agent``, or ``save`` from multiple threads may cause race conditions.
    Use external synchronization if concurrent access is required.
    """

    def __init__(
        self,
        repo_root: Path | str,
        crews_dir: Path | str | None = None,
        router: AgentRouter | None = None,
    ):
        self._repo_root = Path(repo_root).resolve()
        self._crews_dir = (
            Path(crews_dir).resolve()
            if crews_dir is not None
            else (self._repo_root / "crews").resolve()
        )
        self._router = router or AgentRouter(repo_root=self._repo_root)
        self._definitions: dict[str, CrewDefinition] = {}
        self._crews: dict[str, Crew] = {}
        self._discover_crews()

    def _discover_crews(self) -> None:
        """Scan crews/*.json and index definitions by name."""
        self._definitions.clear()
        self._crews.clear()

        if not self._crews_dir.is_dir():
            return

        for path in sorted(self._crews_dir.glob("*.json")):
            definition = load_crew_definition(path)
            expected_name = path.stem
            if definition.name != expected_name:
                raise ValueError(
                    f"Crew filename '{path.name}' does not match name "
                    f"'{definition.name}'"
                )
            self._validate_agents(definition)
            self._definitions[definition.name] = definition

    def _validate_agents(self, definition: CrewDefinition) -> None:
        for agent_ref in definition.agents:
            if not self._router.find_agent(agent_ref.name):
                raise ValueError(
                    f"Unknown agent '{agent_ref.name}' in crew "
                    f"'{definition.name}'. "
                    f"Valid agents: {sorted(self._router.agents.keys())}"
                )

    def _require_crew(self, crew_name: str) -> CrewDefinition:
        definition = self._definitions.get(crew_name)
        if definition is None:
            raise ValueError(f"Unknown crew: {crew_name}")
        return definition

    def _normalize_agent(self, agent: str | AgentRef) -> AgentRef:
        ref = agent if isinstance(agent, AgentRef) else AgentRef(name=agent)
        if not self._router.find_agent(ref.name):
            raise ValueError(
                f"Unknown agent '{ref.name}'. "
                f"Valid agents: {sorted(self._router.agents.keys())}"
            )
        return ref

    def _invalidate_crew(self, crew_name: str) -> None:
        self._crews.pop(crew_name, None)

    def list_crews(self) -> list[str]:
        """Return sorted crew names discovered from disk."""
        return sorted(self._definitions.keys())

    def list_members(self, crew_name: str) -> list[str]:
        """Return agent names for a crew."""
        definition = self._require_crew(crew_name)
        return [agent.name for agent in definition.agents]

    def get_definition(self, crew_name: str) -> CrewDefinition:
        """Return the in-memory crew definition."""
        return self._require_crew(crew_name)

    def get_crew(self, crew_name: str) -> Crew:
        """Return a lazy Crew instance for the named crew."""
        definition = self._require_crew(crew_name)
        if crew_name not in self._crews:
            source_path = definition.source_path or (
                self._crews_dir / f"{crew_name}.json"
            )
            self._crews[crew_name] = Crew(
                definition_path=source_path,
                definition=definition,
                repo_root=self._repo_root,
                router=self._router,
            )
        return self._crews[crew_name]

    def add_agent(self, crew_name: str, agent: str | AgentRef) -> None:
        """Add an agent to a crew at runtime."""
        definition = self._require_crew(crew_name)
        ref = self._normalize_agent(agent)

        if any(existing.name == ref.name for existing in definition.agents):
            raise ValueError(
                f"Agent '{ref.name}' is already a member of crew '{crew_name}'"
            )

        definition.agents.append(ref)
        self._invalidate_crew(crew_name)

    def remove_agent(self, crew_name: str, agent_name: str) -> None:
        """Remove an agent from a crew at runtime."""
        definition = self._require_crew(crew_name)

        if len(definition.agents) <= 1:
            raise ValueError(
                f"Cannot remove last agent from crew '{crew_name}'"
            )

        original_len = len(definition.agents)
        definition.agents = [
            agent for agent in definition.agents if agent.name != agent_name
        ]
        if len(definition.agents) == original_len:
            raise ValueError(
                f"Agent '{agent_name}' is not a member of crew '{crew_name}'"
            )

        self._invalidate_crew(crew_name)

    def save(self, crew_name: str) -> None:
        """Persist the in-memory crew definition to crews/{name}.json."""
        definition = self._require_crew(crew_name)
        target = self._crews_dir / f"{crew_name}.json"
        payload = json.dumps(definition_to_dict(definition), indent=2) + "\n"

        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{crew_name}.",
            suffix=".json.tmp",
        )
        os.close(fd)
        tmp = Path(tmp_path)
        try:
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(target)
            definition.source_path = target
        finally:
            if tmp.exists():
                tmp.unlink()
