"""Shared utilities for model providers (MAT-53)."""

from __future__ import annotations

import os

from mat_runtime.providers.model import ProviderError


def require_api_key(api_key: str | None, env_var: str) -> str:
    """Return api_key or the env var value; raise ProviderError if neither is set."""
    if api_key:
        return api_key
    from_env = os.environ.get(env_var)
    if from_env:
        return from_env
    raise ProviderError(
        code="auth_error",
        message=f"{env_var} is not set",
    )
