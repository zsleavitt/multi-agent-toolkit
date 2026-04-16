"""AgentRouter — routes MAT-2 requests to appropriate CLI agents."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mat_runtime.adapters import get_adapter, CLIAdapter, InvocationResult
from mat_runtime.config import (
    AgentDefinition,
    ProviderConfig,
    load_agent_definitions,
    load_provider_config,
)


@dataclass
class MAT2Request:
    """Parsed MAT-2 request."""

    schema_version: str
    correlation_id: str
    idempotency_key: str
    op: str
    repo_root: str
    instruction: str
    scope_paths: list[str] = field(default_factory=list)
    session: dict[str, Any] | None = None
    turn: dict[str, Any] | None = None
    timeout_ms: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MAT2Request":
        return cls(
            schema_version=data.get("schema_version", "1.0.0"),
            correlation_id=data.get("correlation_id", str(uuid.uuid4())),
            idempotency_key=data.get("idempotency_key", str(uuid.uuid4())),
            op=data["op"],
            repo_root=data["repo_root"],
            instruction=data["instruction"],
            scope_paths=data.get("scope_paths", []),
            session=data.get("session"),
            turn=data.get("turn"),
            timeout_ms=data.get("timeout_ms"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "MAT2Request":
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: Path | str) -> "MAT2Request":
        return cls.from_dict(json.loads(Path(path).read_text()))


@dataclass
class MAT2Response:
    """MAT-2 response."""

    schema_version: str
    correlation_id: str
    idempotency_key: str
    ok: bool
    replay: bool = False
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "ok": self.ok,
            "replay": self.replay,
        }
        if self.ok:
            d["result"] = self.result or {}
        else:
            d["error"] = self.error or {"code": "unknown", "message": "Unknown error"}
        return d

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class AgentRouter:
    """
    Routes MAT-2 requests to the appropriate CLI agent.

    Combines MAT-16 provider config with agent definitions to:
    1. Determine which agent handles an operation
    2. Load the agent's system prompt
    3. Invoke the appropriate CLI tool
    4. Return a MAT-2 response
    """

    def __init__(
        self,
        repo_root: Path | str | None = None,
        provider_config: ProviderConfig | None = None,
        agents: dict[str, AgentDefinition] | None = None,
    ):
        """
        Initialize the router.

        Args:
            repo_root: Repository root path. Auto-detected if None.
            provider_config: MAT-16 config. Loaded from repo if None.
            agents: Agent definitions. Loaded from agents/ if None.
        """
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        self.provider_config = provider_config or load_provider_config(
            repo_root=self.repo_root
        )
        self.agents = agents or load_agent_definitions(repo_root=self.repo_root)
        self._adapters: dict[str, CLIAdapter] = {}

    def _get_adapter(self, agent: AgentDefinition) -> CLIAdapter:
        """Get or create CLI adapter for an agent."""
        if agent.name not in self._adapters:
            # Check provider config for CLI overrides
            cli = agent.cli
            flags: list[str] = []
            timeout_ms = agent.timeout_ms or 300_000

            if self.provider_config:
                # Look up by role in provider config
                role_config = self.provider_config.agents.get(agent.role, {})
                if role_config:
                    cli = role_config.get("cli", cli)
                    flags = role_config.get("flags", [])
                    timeout_ms = role_config.get(
                        "timeout_ms",
                        self.provider_config.defaults.get("timeout_ms", timeout_ms),
                    )

            self._adapters[agent.name] = get_adapter(
                cli=cli,
                flags=flags,
                working_dir=str(self.repo_root),
                timeout_ms=timeout_ms,
            )

        return self._adapters[agent.name]

    def _find_agent_for_op(self, op: str) -> AgentDefinition | None:
        """Find an agent that can handle the given operation."""
        # First check explicit routing in provider config
        if self.provider_config and self.provider_config.routing:
            if op.startswith("codex."):
                role = self.provider_config.routing.get("codex_ops")
                if role:
                    # Find agent with this role
                    for agent in self.agents.values():
                        if agent.role == role:
                            return agent

        # Fall back to checking allowed_mat_ops in agent definitions
        for agent in self.agents.values():
            if op in agent.allowed_mat_ops:
                return agent

        # Default: find any worker agent
        for agent in self.agents.values():
            if agent.role == "worker":
                return agent

        return None

    def find_agent(self, name: str) -> AgentDefinition | None:
        """Find an agent by name."""
        return self.agents.get(name)

    def invoke(
        self,
        agent_name: str,
        request: MAT2Request | dict[str, Any] | str,
    ) -> MAT2Response:
        """
        Invoke an agent with a MAT-2 request.

        Args:
            agent_name: Name of the agent to invoke.
            request: MAT-2 request (dict, JSON string, or MAT2Request object).

        Returns:
            MAT-2 response.
        """
        # Parse request
        if isinstance(request, str):
            req = MAT2Request.from_json(request)
        elif isinstance(request, dict):
            req = MAT2Request.from_dict(request)
        else:
            req = request

        # Find agent
        agent = self.find_agent(agent_name)
        if not agent:
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=False,
                error={
                    "code": "agent_not_found",
                    "message": f"Agent '{agent_name}' not found",
                },
            )

        # Check if agent can handle this operation
        if agent.allowed_mat_ops and req.op not in agent.allowed_mat_ops:
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=False,
                error={
                    "code": "operation_not_allowed",
                    "message": f"Agent '{agent_name}' cannot handle operation '{req.op}'",
                },
            )

        # Get adapter and invoke
        adapter = self._get_adapter(agent)
        result = adapter.invoke(
            prompt=req.instruction,
            system_prompt=agent.system_prompt,
            working_dir=req.repo_root,
            timeout_ms=req.timeout_ms,
            correlation_id=req.correlation_id,
        )

        # Build response
        if result.ok:
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=True,
                result={
                    "output": result.stdout,
                    "files_modified": [],  # Would need to parse from output
                },
            )
        else:
            error_code = "timeout" if result.timeout_exceeded else "execution_error"
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=False,
                error={
                    "code": error_code,
                    "message": result.stderr or f"CLI returned code {result.return_code}",
                },
            )

    def invoke_op(self, request: MAT2Request | dict[str, Any] | str) -> MAT2Response:
        """
        Invoke the appropriate agent for a MAT-2 operation.

        Automatically routes to the right agent based on the operation.
        """
        # Parse request
        if isinstance(request, str):
            req = MAT2Request.from_json(request)
        elif isinstance(request, dict):
            req = MAT2Request.from_dict(request)
        else:
            req = request

        # Find agent for this operation
        agent = self._find_agent_for_op(req.op)
        if not agent:
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=False,
                error={
                    "code": "no_agent_for_op",
                    "message": f"No agent found to handle operation '{req.op}'",
                },
            )

        return self.invoke(agent.name, req)
