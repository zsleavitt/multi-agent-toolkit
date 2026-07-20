"""CLI ↔ direct-API bridge (MAT-58).

Reads MAT-16 provider overlays and returns either a subprocess CLI adapter or a
``ModelProvider`` wrapper that satisfies ``AgentInvocationProvider``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mat_runtime.adapters.base import InvocationResult, model_from_kwargs
from mat_runtime.providers.factory import get_provider
from mat_runtime.providers.model import ModelProvider, ProviderError
from mat_runtime.providers.protocol import AgentInvocationProvider

# MAT-16 ``cli`` values → ``get_provider`` registry keys.
CLI_TO_PROVIDER: dict[str, str] = {
    "claude": "claude",
    "codex": "openai",
    "codex-review": "openai",
    "gemini": "gemini",
}

DEFAULT_MODELS: dict[str, str] = {
    "claude": "claude-sonnet-4-20250514",
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "gpt-4o": "gpt-4o",
    "gemini": "gemini-2.0-flash",
    "google": "gemini-2.0-flash",
}

DEFAULT_MAX_TOKENS = 4096


def resolve_invocation_mode(
    overlay: dict[str, Any],
    defaults: dict[str, Any] | None = None,
) -> str:
    """Return ``cli`` (default) or ``api`` from merged MAT-16 config."""
    mode = overlay.get("invocation_mode")
    if mode is None and defaults:
        mode = defaults.get("invocation_mode")
    if mode in ("cli", "api"):
        return mode
    return "cli"


def resolve_api_provider_name(cli: str, overlay: dict[str, Any]) -> str:
    """Map CLI binding to a ``get_provider`` name, with optional override."""
    explicit = overlay.get("provider")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().lower()
    mapped = CLI_TO_PROVIDER.get(cli)
    if mapped:
        return mapped
    raise ValueError(
        f"Cannot map cli '{cli}' to an API provider. "
        "Set 'provider' in mat-config when using invocation_mode 'api'."
    )


def resolve_api_model(provider_name: str, overlay: dict[str, Any]) -> str:
    """Resolve model id for API invocations."""
    model = overlay.get("model")
    if isinstance(model, str) and model.strip():
        return model.strip()
    default = DEFAULT_MODELS.get(provider_name.lower())
    if default:
        return default
    raise ValueError(
        f"No default model for provider '{provider_name}'. "
        "Set 'model' in mat-config when using invocation_mode 'api'."
    )


def _combine_prompt(prompt: str, system_prompt: str | None) -> str:
    if system_prompt:
        return f"{system_prompt}\n\n---\n\n{prompt}"
    return prompt


def model_response_to_invocation_result(
    response: Any,
    *,
    correlation_id: str,
) -> InvocationResult:
    """Convert ``ModelResponse`` to ``InvocationResult`` for router compatibility."""
    if response.ok:
        return InvocationResult(
            ok=True,
            stdout=response.text,
            stderr="",
            return_code=0,
            correlation_id=correlation_id,
        )

    err: ProviderError | None = response.error
    if err and err.code == "timeout":
        return InvocationResult(
            ok=False,
            stdout=response.text or "",
            stderr=err.message,
            return_code=-1,
            correlation_id=correlation_id,
            timeout_exceeded=True,
        )

    message = err.message if err else "API provider returned an error"
    return InvocationResult(
        ok=False,
        stdout=response.text or "",
        stderr=message,
        return_code=1,
        correlation_id=correlation_id,
    )


@dataclass
class ModelProviderAdapter:
    """Wraps a ``ModelProvider`` as an ``AgentInvocationProvider``."""

    provider: ModelProvider
    default_model: str
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout_ms: int = 300_000

    def invoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> InvocationResult:
        correlation_id = correlation_id or str(uuid.uuid4())
        model = model_from_kwargs(kwargs) or self.default_model
        full_prompt = _combine_prompt(prompt, system_prompt)
        effective_timeout = timeout_ms if timeout_ms is not None else self.timeout_ms

        try:
            response = self.provider.complete(
                full_prompt,
                model=model,
                max_tokens=self.max_tokens,
                timeout_ms=effective_timeout,
            )
        except ProviderError as exc:
            if exc.code == "timeout":
                return InvocationResult(
                    ok=False,
                    stdout="",
                    stderr=exc.message,
                    return_code=-1,
                    correlation_id=correlation_id,
                    timeout_exceeded=True,
                )
            return InvocationResult(
                ok=False,
                stdout="",
                stderr=exc.message,
                return_code=1,
                correlation_id=correlation_id,
            )

        return model_response_to_invocation_result(
            response, correlation_id=correlation_id
        )

    def invoke_with_file(
        self,
        prompt: str,
        system_prompt: str | None = None,
        working_dir: str | None = None,
        timeout_ms: int | None = None,
        correlation_id: str | None = None,
        **kwargs: Any,
    ) -> InvocationResult:
        """Read ``@path`` prompts from disk, then delegate to ``invoke``.

        When ``working_dir`` is provided, the resolved path must be within it.
        """
        if prompt.startswith("@"):
            path = Path(prompt[1:]).resolve()
            if working_dir is not None:
                root = Path(working_dir).resolve()
                if not path.is_relative_to(root):
                    return InvocationResult(
                        ok=False,
                        stdout="",
                        stderr=f"Prompt file path escapes working_dir: {path}",
                        return_code=1,
                        correlation_id=correlation_id or str(uuid.uuid4()),
                    )
            prompt = path.read_text(encoding="utf-8")
        return self.invoke(
            prompt=prompt,
            system_prompt=system_prompt,
            working_dir=working_dir,
            timeout_ms=timeout_ms,
            correlation_id=correlation_id,
            **kwargs,
        )


def create_invocation_provider(
    *,
    cli: str,
    overlay: dict[str, Any],
    defaults: dict[str, Any] | None,
    flags: list[str],
    working_dir: str,
    timeout_ms: int,
) -> AgentInvocationProvider:
    """Return CLI or API invocation backend based on MAT-16 overlay."""
    mode = resolve_invocation_mode(overlay, defaults)
    if mode == "cli":
        from mat_runtime.adapters import get_adapter

        return get_adapter(
            cli=cli,
            flags=flags,
            working_dir=working_dir,
            timeout_ms=timeout_ms,
        )

    provider_name = resolve_api_provider_name(cli, overlay)
    model = resolve_api_model(provider_name, overlay)
    max_tokens = overlay.get("max_tokens")
    if max_tokens is None and defaults:
        max_tokens = defaults.get("max_tokens")
    if not isinstance(max_tokens, int) or max_tokens < 1:
        max_tokens = DEFAULT_MAX_TOKENS

    provider = get_provider(provider_name)
    return ModelProviderAdapter(
        provider=provider,
        default_model=model,
        max_tokens=max_tokens,
        timeout_ms=timeout_ms,
    )
