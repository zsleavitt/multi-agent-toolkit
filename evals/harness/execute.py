"""Execute a golden eval task against AgentRouter with mock adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

from evals.harness.agents import default_agents, default_provider_config
from evals.harness.loader import EvalTask
from evals.harness.mock_adapter import ScenarioMockAdapter
from mat_runtime.config import AgentDefinition
from mat_runtime.resilience import CircuitState
from mat_runtime.router import AgentRouter, MAT2Request, MAT2Response


@dataclass
class Trajectory:
    """Observed routing + resilience trajectory for scoring."""

    agent_name: str | None = None
    agent_cli: str | None = None
    agent_role: str | None = None
    allowed_mat_ops: list[str] = field(default_factory=list)
    op: str | None = None
    op_in_allowlist: bool | None = None
    attempts: int = 0
    circuit_state: str | None = None
    response: MAT2Response | None = None


@dataclass
class TaskExecution:
    task: EvalTask
    trajectory: Trajectory
    error: str | None = None


def _build_request(task: EvalTask) -> MAT2Request:
    mat2 = dict(task.request.get("mat2") or task.request)
    # Allow nesting under request.mat2; strip harness-only keys if flat.
    for key in ("agent_name", "use_invoke_op"):
        mat2.pop(key, None)
    defaults = {
        "schema_version": "1.2.0",
        "correlation_id": f"eval-{task.id}",
        "idempotency_key": f"eval-idem-{task.id}",
        "repo_root": "/tmp/eval-repo",
        "instruction": task.description or f"Eval task {task.id}",
    }
    for key, value in defaults.items():
        mat2.setdefault(key, value)
    return MAT2Request.from_dict(mat2)


def _resolve_agents(setup: dict[str, Any]) -> dict[str, AgentDefinition]:
    agents = default_agents()
    overrides = setup.get("agents")
    if isinstance(overrides, dict):
        for name, patch_fields in overrides.items():
            if name not in agents or not isinstance(patch_fields, dict):
                continue
            base = agents[name]
            agents[name] = AgentDefinition(
                name=base.name,
                description=patch_fields.get("description", base.description),
                role=patch_fields.get("role", base.role),
                cli=patch_fields.get("cli", base.cli),
                allowed_mat_ops=patch_fields.get(
                    "allowed_mat_ops", base.allowed_mat_ops
                ),
                system_prompt=patch_fields.get("system_prompt", base.system_prompt),
            )
    return agents


def execute_task(task: EvalTask) -> TaskExecution:
    """Run one golden task with a mock adapter; never touches live CLIs."""
    setup = task.setup
    agents = _resolve_agents(setup)
    provider = default_provider_config(
        defaults=setup.get("provider_defaults"),
        routing=setup.get("routing"),
    )
    mock = ScenarioMockAdapter(setup.get("mock"))

    router = AgentRouter(
        repo_root="/tmp/eval-repo",
        provider_config=provider,
        agents=agents,
    )

    pre_failures = int(setup.get("pre_failures") or 0)
    for _ in range(pre_failures):
        router._circuit_breaker.record_failure()

    req = _build_request(task)
    use_invoke_op = bool(task.request.get("use_invoke_op", False))
    agent_name = task.request.get("agent_name")

    traj = Trajectory(op=req.op)

    try:
        with patch(
            "mat_runtime.router.create_invocation_provider",
            return_value=mock,
        ):
            if use_invoke_op:
                chosen = router._find_agent_for_op(req.op)
                if chosen is not None:
                    traj.agent_name = chosen.name
                    traj.agent_cli = chosen.cli
                    traj.agent_role = chosen.role
                    traj.allowed_mat_ops = list(chosen.allowed_mat_ops or [])
                    traj.op_in_allowlist = req.op in (chosen.allowed_mat_ops or [])
                response = router.invoke_op(req)
            else:
                if not agent_name:
                    raise ValueError(
                        f"Task {task.id!r} needs request.agent_name "
                        "or request.use_invoke_op=true"
                    )
                agent = router.find_agent(str(agent_name))
                traj.agent_name = str(agent_name)
                if agent is not None:
                    traj.agent_cli = agent.cli
                    traj.agent_role = agent.role
                    traj.allowed_mat_ops = list(agent.allowed_mat_ops or [])
                    traj.op_in_allowlist = req.op in (agent.allowed_mat_ops or [])
                response = router.invoke(str(agent_name), req)
    except Exception as exc:  # noqa: BLE001 — surface as eval failure
        traj.attempts = mock.calls
        traj.circuit_state = router._circuit_breaker.state.value
        return TaskExecution(task=task, trajectory=traj, error=str(exc))

    traj.attempts = mock.calls
    traj.circuit_state = (
        router._circuit_breaker.state.value
        if isinstance(router._circuit_breaker.state, CircuitState)
        else str(router._circuit_breaker.state)
    )
    # After invoke_op, prefer agent recorded on successful routing.
    if use_invoke_op and traj.agent_name is None and response.ok:
        # Should not happen; keep trajectory as-is.
        pass
    traj.response = response
    return TaskExecution(task=task, trajectory=traj)
