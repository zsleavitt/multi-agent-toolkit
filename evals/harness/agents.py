"""Default agent definitions and provider config for eval runs."""

from __future__ import annotations

from typing import Any

from mat_runtime.config import AgentDefinition, ProviderConfig


def default_agents() -> dict[str, AgentDefinition]:
    """Mirrors production agent shapes used by routing/allowlist scenarios."""
    return {
        "coder": AgentDefinition(
            name="coder",
            description="Code implementation agent",
            role="worker",
            cli="codex",
            allowed_mat_ops=["codex.implement", "codex.refactor", "codex.diagnose"],
            system_prompt="You are a code implementation agent.",
        ),
        "reviewer": AgentDefinition(
            name="reviewer",
            description="Code review agent",
            role="worker",
            cli="claude",
            allowed_mat_ops=["codex.review"],
            system_prompt="You are a code review agent.",
        ),
        "tester": AgentDefinition(
            name="tester",
            description="Testing agent",
            role="worker",
            cli="codex",
            allowed_mat_ops=["codex.test", "codex.implement"],
            system_prompt="You are a testing agent.",
        ),
        "security": AgentDefinition(
            name="security",
            description="Security analysis agent",
            role="worker",
            cli="claude",
            allowed_mat_ops=["codex.review", "codex.diagnose"],
            system_prompt="You are a security analysis agent.",
        ),
        "researcher": AgentDefinition(
            name="researcher",
            description="Research agent",
            role="executor",
            cli="gemini",
            allowed_mat_ops=["codex.research"],
            system_prompt="You are a research agent.",
        ),
        "orchestrator": AgentDefinition(
            name="orchestrator",
            description="Planning agent",
            role="orchestrator",
            cli="claude",
            allowed_mat_ops=[],
            system_prompt="You are an orchestrator.",
        ),
    }


def default_provider_config(
    defaults: dict[str, Any] | None = None,
    routing: dict[str, str] | None = None,
) -> ProviderConfig:
    """Provider config with zero backoff so evals stay fast and deterministic."""
    merged_defaults: dict[str, Any] = {
        "max_retries": 0,
        "backoff_ms": 0,
        "backoff_multiplier": 2.0,
        "timeout_ms": 60_000,
        "circuit_breaker": {
            "failure_threshold": 5,
            "cooldown_ms": 60_000,
        },
    }
    if defaults:
        cb = merged_defaults.get("circuit_breaker", {})
        incoming_cb = defaults.get("circuit_breaker")
        merged_defaults.update(
            {k: v for k, v in defaults.items() if k != "circuit_breaker"}
        )
        if isinstance(incoming_cb, dict):
            merged_defaults["circuit_breaker"] = {**cb, **incoming_cb}
    return ProviderConfig(
        schema_version="1.0.0",
        agents={
            "worker": {"cli": "codex"},
            "orchestrator": {"cli": "claude"},
            "executor": {"cli": "gemini"},
        },
        routing=(
            {"codex_ops": "worker"} if routing is None else dict(routing)
        ),
        defaults=merged_defaults,
    )
