"""Factory for direct API model providers (MAT-53)."""

from __future__ import annotations

from typing import Any

from mat_runtime.providers.claude import ClaudeProvider
from mat_runtime.providers.gemini import GeminiProvider
from mat_runtime.providers.model import ModelProvider
from mat_runtime.providers.openai_provider import OpenAIProvider

PROVIDER_REGISTRY: dict[str, type[ClaudeProvider] | type[OpenAIProvider] | type[GeminiProvider]] = {
    "claude": ClaudeProvider,
    "anthropic": ClaudeProvider,
    "openai": OpenAIProvider,
    "gpt-4o": OpenAIProvider,
    "gemini": GeminiProvider,
    "google": GeminiProvider,
}


def get_provider(name: str, **config: Any) -> ModelProvider:
    """Return a configured ``ModelProvider`` for *name*."""
    key = name.strip().lower()
    if key not in PROVIDER_REGISTRY:
        known = ", ".join(sorted(PROVIDER_REGISTRY))
        raise ValueError(f"Unknown model provider: {name}. Known providers: {known}")
    return PROVIDER_REGISTRY[key](**config)
