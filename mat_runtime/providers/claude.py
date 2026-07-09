"""Anthropic API model provider (MAT-53)."""

from __future__ import annotations

import os
from typing import Any

from mat_runtime.providers.errors import map_anthropic_error
from mat_runtime.providers.model import ModelResponse, ProviderError


def _require_api_key(api_key: str | None, env_var: str) -> str:
    if api_key:
        return api_key
    from_env = os.environ.get(env_var)
    if from_env:
        return from_env
    raise ProviderError(
        code="auth_error",
        message=f"{env_var} is not set",
    )


class ClaudeProvider:
    """Direct Anthropic Messages API adapter."""

    def __init__(self, *, api_key: str | None = None, client: Any | None = None) -> None:
        if client is not None:
            self._client = client
            return
        key = _require_api_key(api_key, "ANTHROPIC_API_KEY")
        from anthropic import Anthropic

        self._client = Anthropic(api_key=key)

    def complete(
        self,
        prompt: str,
        *,
        model: str,
        max_tokens: int,
        timeout_ms: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        timeout_sec = timeout_ms / 1000.0 if timeout_ms is not None else None
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout_sec,
                **kwargs,
            )
        except ProviderError:
            raise
        except Exception as exc:
            err = map_anthropic_error(exc)
            return ModelResponse(
                ok=False,
                text="",
                input_tokens=None,
                output_tokens=None,
                model=model,
                stop_reason=None,
                error=err,
            )

        text = ""
        if response.content:
            block = response.content[0]
            text = getattr(block, "text", "") or ""

        usage = getattr(response, "usage", None)
        return ModelResponse(
            ok=True,
            text=text,
            input_tokens=getattr(usage, "input_tokens", None) if usage else None,
            output_tokens=getattr(usage, "output_tokens", None) if usage else None,
            model=response.model,
            stop_reason=response.stop_reason,
        )
