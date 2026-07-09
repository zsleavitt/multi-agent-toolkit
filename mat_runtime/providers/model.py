"""Direct API model providers — unified request/response types (MAT-53)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol, runtime_checkable

ProviderErrorCode = Literal[
    "auth_error",
    "rate_limit",
    "timeout",
    "context_length",
    "unknown",
]


@dataclass
class ProviderError(Exception):
    """Normalized provider failure with retry guidance."""

    code: ProviderErrorCode
    message: str
    retryable: bool = False
    retry_after_ms: int | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass
class ModelResponse:
    """Result of a direct API completion call."""

    ok: bool
    text: str
    input_tokens: int | None
    output_tokens: int | None
    model: str
    stop_reason: str | None
    error: ProviderError | None = None


@runtime_checkable
class ModelProvider(Protocol):
    """Direct API completion surface (distinct from CLI ``AgentInvocationProvider``)."""

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        max_tokens: int,
        timeout_ms: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Run *prompt* against *model* and return a structured response."""
        ...
