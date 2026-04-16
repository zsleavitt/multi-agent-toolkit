"""CLI adapters for invoking AI tools."""

from mat_runtime.adapters.base import CLIAdapter, InvocationResult
from mat_runtime.adapters.claude import ClaudeAdapter
from mat_runtime.adapters.codex import CodexAdapter
from mat_runtime.adapters.gemini import GeminiAdapter

__all__ = [
    "CLIAdapter",
    "InvocationResult",
    "ClaudeAdapter",
    "CodexAdapter",
    "GeminiAdapter",
]

ADAPTER_REGISTRY: dict[str, type["CLIAdapter"]] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "gemini": GeminiAdapter,
}


def get_adapter(cli: str, **kwargs) -> "CLIAdapter":
    """Get adapter instance for a CLI tool."""
    if cli == "custom":
        return CLIAdapter(**kwargs)
    if cli not in ADAPTER_REGISTRY:
        raise ValueError(f"Unknown CLI tool: {cli}. Use 'custom' with explicit command.")
    return ADAPTER_REGISTRY[cli](**kwargs)
