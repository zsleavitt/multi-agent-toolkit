"""CLI adapters for invoking AI tools."""

from __future__ import annotations

from mat_runtime.adapters.base import CLIAdapter, InvocationResult
from mat_runtime.providers import AgentInvocationProvider
from mat_runtime.adapters.claude import ClaudeAdapter
from mat_runtime.adapters.codex import CodexAdapter
from mat_runtime.adapters.codex_review import CodexReviewAdapter
from mat_runtime.adapters.gemini import GeminiAdapter

__all__ = [
    "CLIAdapter",
    "InvocationResult",
    "ClaudeAdapter",
    "CodexAdapter",
    "CodexReviewAdapter",
    "GeminiAdapter",
]

ADAPTER_REGISTRY: dict[str, type["CLIAdapter"]] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "codex-review": CodexReviewAdapter,
    "gemini": GeminiAdapter,
}


def get_adapter(cli: str, **kwargs) -> AgentInvocationProvider:
    """Get adapter instance for a CLI tool."""
    if cli == "custom":
        return CLIAdapter(**kwargs)
    if cli not in ADAPTER_REGISTRY:
        raise ValueError(f"Unknown CLI tool: {cli}. Use 'custom' with explicit command.")
    # Empty list from provider config must not override adapter class defaults.
    if kwargs.get("flags") == []:
        kwargs.pop("flags", None)
    return ADAPTER_REGISTRY[cli](**kwargs)
