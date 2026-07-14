"""Invocation provider abstractions (MAT-53) and CLI/API bridge (MAT-58)."""

from mat_runtime.providers.bridge import (
    ModelProviderAdapter,
    create_invocation_provider,
    resolve_invocation_mode,
)
from mat_runtime.providers.factory import PROVIDER_REGISTRY, get_provider
from mat_runtime.providers.model import ModelProvider, ModelResponse, ProviderError
from mat_runtime.providers.protocol import AgentInvocationProvider

__all__ = [
    "AgentInvocationProvider",
    "ModelProvider",
    "ModelProviderAdapter",
    "ModelResponse",
    "PROVIDER_REGISTRY",
    "ProviderError",
    "create_invocation_provider",
    "get_provider",
    "resolve_invocation_mode",
]
