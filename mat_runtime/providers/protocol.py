"""MAT-53 — typed invocation surface for agent backends (CLI today, extensible later).

Swarm ``parallel_model`` mode and similar call sites depend on a stable
``invoke`` / ``invoke_with_file`` contract. Concrete implementations live in
``mat_runtime.adapters`` (subprocess CLIs per ADR 0002).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from mat_runtime.adapters.base import InvocationResult


@runtime_checkable
class AgentInvocationProvider(Protocol):
    """Anything that can run a prompt and return structured stdout/stderr."""

    def invoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> InvocationResult:
        """Run *prompt* (and optional *system_prompt*) and return a result envelope."""
        ...

    def invoke_with_file(
        self,
        prompt: str,
        system_prompt: str | None = None,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> InvocationResult:
        """Same as ``invoke`` but may spill long prompts to a temp file."""
        ...
