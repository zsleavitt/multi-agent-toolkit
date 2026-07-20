"""Tests for CLI ↔ API provider bridge (MAT-58)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mat_runtime.providers.bridge import (
    ModelProviderAdapter,
    create_invocation_provider,
    model_response_to_invocation_result,
    resolve_api_model,
    resolve_api_provider_name,
    resolve_invocation_mode,
)
from mat_runtime.providers.model import ModelResponse, ProviderError
from mat_runtime.providers.protocol import AgentInvocationProvider


def test_resolve_invocation_mode_defaults_to_cli() -> None:
    assert resolve_invocation_mode({}) == "cli"
    assert resolve_invocation_mode({}, {"invocation_mode": "cli"}) == "cli"


def test_resolve_invocation_mode_overlay_wins() -> None:
    assert resolve_invocation_mode(
        {"invocation_mode": "api"},
        {"invocation_mode": "cli"},
    ) == "api"


def test_resolve_invocation_mode_falls_back_to_defaults() -> None:
    assert resolve_invocation_mode({}, {"invocation_mode": "api"}) == "api"


def test_resolve_api_provider_name_from_cli() -> None:
    assert resolve_api_provider_name("claude", {}) == "claude"
    assert resolve_api_provider_name("codex", {}) == "openai"
    assert resolve_api_provider_name("gemini", {}) == "gemini"


def test_resolve_api_provider_name_explicit_override() -> None:
    assert resolve_api_provider_name("codex", {"provider": "anthropic"}) == "anthropic"


def test_resolve_api_provider_name_unknown_cli_raises() -> None:
    with pytest.raises(ValueError, match="Cannot map cli 'cursor'"):
        resolve_api_provider_name("cursor", {})


def test_resolve_api_model_explicit() -> None:
    assert resolve_api_model("openai", {"model": "gpt-4.1"}) == "gpt-4.1"


def test_resolve_api_model_default() -> None:
    assert resolve_api_model("openai", {}) == "gpt-4o"


def test_model_response_to_invocation_result_success() -> None:
    result = model_response_to_invocation_result(
        ModelResponse(
            ok=True,
            text="done",
            input_tokens=1,
            output_tokens=2,
            model="gpt-4o",
            stop_reason="stop",
        ),
        correlation_id="cid",
    )
    assert result.ok is True
    assert result.stdout == "done"
    assert result.correlation_id == "cid"


def test_model_response_to_invocation_result_timeout() -> None:
    result = model_response_to_invocation_result(
        ModelResponse(
            ok=False,
            text="",
            input_tokens=None,
            output_tokens=None,
            model="gpt-4o",
            stop_reason=None,
            error=ProviderError(code="timeout", message="timed out"),
        ),
        correlation_id="cid",
    )
    assert result.ok is False
    assert result.timeout_exceeded is True


def test_model_provider_adapter_invoke_success() -> None:
    provider = MagicMock()
    provider.complete.return_value = ModelResponse(
        ok=True,
        text="hello api",
        input_tokens=3,
        output_tokens=5,
        model="gpt-4o",
        stop_reason="stop",
    )
    adapter = ModelProviderAdapter(provider=provider, default_model="gpt-4o")

    result = adapter.invoke(
        prompt="do work",
        system_prompt="you are helpful",
        correlation_id="test-cid",
    )

    assert result.ok is True
    assert result.stdout == "hello api"
    provider.complete.assert_called_once()
    assert provider.complete.call_args.kwargs["model"] == "gpt-4o"
    assert "you are helpful" in provider.complete.call_args.args[0]
    assert "do work" in provider.complete.call_args.args[0]


def test_model_provider_adapter_invoke_model_override_from_kwargs() -> None:
    provider = MagicMock()
    provider.complete.return_value = ModelResponse(
        ok=True,
        text="ok",
        input_tokens=1,
        output_tokens=1,
        model="gpt-4.1",
        stop_reason="stop",
    )
    adapter = ModelProviderAdapter(provider=provider, default_model="gpt-4o")

    adapter.invoke(prompt="hi", model="gpt-4.1")

    assert provider.complete.call_args.kwargs["model"] == "gpt-4.1"


def test_model_provider_adapter_catches_provider_error() -> None:
    provider = MagicMock()
    provider.complete.side_effect = ProviderError(
        code="auth_error",
        message="missing key",
    )
    adapter = ModelProviderAdapter(provider=provider, default_model="gpt-4o")

    result = adapter.invoke(prompt="hi")

    assert result.ok is False
    assert "missing key" in result.stderr


def test_model_provider_adapter_satisfies_protocol() -> None:
    provider = MagicMock()
    adapter = ModelProviderAdapter(provider=provider, default_model="gpt-4o")
    assert isinstance(adapter, AgentInvocationProvider)


@patch("mat_runtime.adapters.get_adapter")
def test_create_invocation_provider_cli_mode(mock_get_adapter: MagicMock) -> None:
    mock_get_adapter.return_value = MagicMock(spec=AgentInvocationProvider)

    provider = create_invocation_provider(
        cli="codex",
        overlay={"invocation_mode": "cli", "flags": ["--x"]},
        defaults={},
        flags=["--x"],
        working_dir="/tmp",
        timeout_ms=60_000,
    )

    mock_get_adapter.assert_called_once_with(
        cli="codex",
        flags=["--x"],
        working_dir="/tmp",
        timeout_ms=60_000,
    )
    assert provider is mock_get_adapter.return_value


@patch("mat_runtime.providers.bridge.get_provider")
def test_create_invocation_provider_api_mode(mock_get_provider: MagicMock) -> None:
    mock_get_provider.return_value = MagicMock()

    provider = create_invocation_provider(
        cli="codex",
        overlay={
            "invocation_mode": "api",
            "model": "gpt-4o",
        },
        defaults={"max_tokens": 2048},
        flags=[],
        working_dir="/tmp",
        timeout_ms=90_000,
    )

    mock_get_provider.assert_called_once_with("openai")
    assert isinstance(provider, ModelProviderAdapter)
    assert provider.default_model == "gpt-4o"
    assert provider.max_tokens == 2048
    assert provider.timeout_ms == 90_000


def test_create_invocation_provider_api_mode_via_defaults() -> None:
    with patch("mat_runtime.providers.bridge.get_provider") as mock_get_provider:
        mock_get_provider.return_value = MagicMock()
        provider = create_invocation_provider(
            cli="claude",
            overlay={},
            defaults={"invocation_mode": "api"},
            flags=[],
            working_dir="/tmp",
            timeout_ms=30_000,
        )
    assert isinstance(provider, ModelProviderAdapter)
    mock_get_provider.assert_called_once_with("claude")


def test_model_provider_adapter_invoke_with_file(tmp_path) -> None:
    prompt_file = tmp_path / "task.md"
    prompt_file.write_text("file prompt body", encoding="utf-8")

    provider = MagicMock()
    provider.complete.return_value = ModelResponse(
        ok=True,
        text="from file",
        input_tokens=1,
        output_tokens=1,
        model="gpt-4o",
        stop_reason="stop",
    )
    adapter = ModelProviderAdapter(provider=provider, default_model="gpt-4o")

    result = adapter.invoke_with_file(
        prompt=f"@{prompt_file}", working_dir=str(tmp_path)
    )

    assert result.ok is True
    assert "file prompt body" in provider.complete.call_args.args[0]


def test_invoke_with_file_rejects_path_outside_working_dir(tmp_path) -> None:
    outside = tmp_path.parent / "secret.txt"
    outside.write_text("sensitive", encoding="utf-8")
    provider = MagicMock()
    adapter = ModelProviderAdapter(provider=provider, default_model="gpt-4o")
    subdir = tmp_path / "work"
    subdir.mkdir()

    result = adapter.invoke_with_file(
        prompt=f"@{outside}", working_dir=str(subdir)
    )

    assert result.ok is False
    assert "escapes working_dir" in result.stderr
    provider.complete.assert_not_called()


def test_invoke_with_file_no_working_dir_allows_any_path(tmp_path) -> None:
    prompt_file = tmp_path / "task.md"
    prompt_file.write_text("body", encoding="utf-8")
    provider = MagicMock()
    provider.complete.return_value = ModelResponse(
        ok=True,
        text="ok",
        input_tokens=1,
        output_tokens=1,
        model="gpt-4o",
        stop_reason="stop",
    )
    adapter = ModelProviderAdapter(provider=provider, default_model="gpt-4o")

    result = adapter.invoke_with_file(prompt=f"@{prompt_file}")

    assert result.ok is True
