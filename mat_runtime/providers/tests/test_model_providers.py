"""Unit tests for direct API model providers (MAT-53)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mat_runtime.providers.claude import ClaudeProvider
from mat_runtime.providers.errors import map_anthropic_error, map_gemini_error, map_openai_error
from mat_runtime.providers.factory import get_provider
from mat_runtime.providers.gemini import GeminiProvider
from mat_runtime.providers.model import ModelProvider, ProviderError
from mat_runtime.providers.openai_provider import OpenAIProvider


def _anthropic_success_response() -> SimpleNamespace:
    return SimpleNamespace(
        model="claude-sonnet-4-20250514",
        stop_reason="end_turn",
        content=[SimpleNamespace(text="hello from claude")],
        usage=SimpleNamespace(input_tokens=11, output_tokens=7),
    )


def _openai_success_response() -> SimpleNamespace:
    return SimpleNamespace(
        model="gpt-4o",
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content="hello from openai"),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
    )


def _gemini_success_response() -> SimpleNamespace:
    return SimpleNamespace(
        text="hello from gemini",
        usage_metadata=SimpleNamespace(prompt_token_count=9, candidates_token_count=4),
        candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="STOP"))],
    )


def test_claude_provider_success_from_mock() -> None:
    client = MagicMock()
    client.messages.create.return_value = _anthropic_success_response()
    provider = ClaudeProvider(client=client)

    result = provider.complete("hi", model="claude-sonnet-4-20250514", max_tokens=128)

    assert result.ok is True
    assert result.text == "hello from claude"
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert result.model == "claude-sonnet-4-20250514"
    assert result.stop_reason == "end_turn"
    assert result.error is None


def test_openai_provider_success_from_mock() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = _openai_success_response()
    provider = OpenAIProvider(client=client)

    result = provider.complete("hi", model="gpt-4o", max_tokens=64)

    assert result.ok is True
    assert result.text == "hello from openai"
    assert result.input_tokens == 5
    assert result.output_tokens == 3
    assert result.model == "gpt-4o"
    assert result.stop_reason == "stop"


def test_gemini_provider_success_from_mock() -> None:
    client = MagicMock()
    model = MagicMock()
    model.generate_content.return_value = _gemini_success_response()
    client.GenerativeModel.return_value = model
    provider = GeminiProvider(client=client)

    result = provider.complete("hi", model="gemini-2.0-flash", max_tokens=64)

    assert result.ok is True
    assert result.text == "hello from gemini"
    assert result.input_tokens == 9
    assert result.output_tokens == 4
    assert result.model == "gemini-2.0-flash"
    assert result.stop_reason == "STOP"


def test_map_anthropic_errors() -> None:
    anthropic = pytest.importorskip("anthropic")

    auth = map_anthropic_error(
        anthropic.AuthenticationError("bad key", response=MagicMock(), body=None)
    )
    assert auth.code == "auth_error"

    rate = map_anthropic_error(
        anthropic.RateLimitError(
            "slow down",
            response=MagicMock(headers={"retry-after": "2"}),
            body=None,
        )
    )
    assert rate.code == "rate_limit"
    assert rate.retryable is True
    assert rate.retry_after_ms == 2000

    timeout = map_anthropic_error(anthropic.APITimeoutError(request=MagicMock()))
    assert timeout.code == "timeout"
    assert timeout.retryable is True

    context = map_anthropic_error(
        anthropic.BadRequestError(
            "prompt exceeds maximum context length", response=MagicMock(), body=None
        )
    )
    assert context.code == "context_length"


def test_map_openai_errors() -> None:
    openai = pytest.importorskip("openai")

    auth = map_openai_error(
        openai.AuthenticationError("bad key", response=MagicMock(), body=None)
    )
    assert auth.code == "auth_error"

    rate = map_openai_error(
        openai.RateLimitError(
            "slow down",
            response=MagicMock(headers={"Retry-After": "3"}),
            body=None,
        )
    )
    assert rate.code == "rate_limit"
    assert rate.retryable is True
    assert rate.retry_after_ms == 3000

    timeout = map_openai_error(openai.APITimeoutError(request=MagicMock()))
    assert timeout.code == "timeout"

    context = map_openai_error(
        openai.BadRequestError(
            "maximum context length exceeded", response=MagicMock(), body=None
        )
    )
    assert context.code == "context_length"


def test_map_gemini_errors() -> None:
    google_exceptions = pytest.importorskip("google.api_core.exceptions")

    auth = map_gemini_error(google_exceptions.Unauthenticated("bad key"))
    assert auth.code == "auth_error"

    rate = map_gemini_error(google_exceptions.ResourceExhausted("quota exceeded"))
    assert rate.code == "rate_limit"
    assert rate.retryable is True

    timeout = map_gemini_error(google_exceptions.DeadlineExceeded("deadline"))
    assert timeout.code == "timeout"

    context = map_gemini_error(
        google_exceptions.InvalidArgument("input token limit exceeded")
    )
    assert context.code == "context_length"


def test_provider_api_errors_return_model_response() -> None:
    anthropic = pytest.importorskip("anthropic")

    client = MagicMock()
    client.messages.create.side_effect = anthropic.RateLimitError(
        "rate limited",
        response=MagicMock(headers={}),
        body=None,
    )
    provider = ClaudeProvider(client=client)

    result = provider.complete("hi", model="claude-sonnet-4-20250514", max_tokens=32)

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "rate_limit"
    assert result.error.retryable is True


def test_get_provider_resolution() -> None:
    client = MagicMock()
    provider = get_provider("claude", client=client)
    assert isinstance(provider, ClaudeProvider)
    assert isinstance(provider, ModelProvider)

    provider = get_provider("gpt-4o", client=client)
    assert isinstance(provider, OpenAIProvider)

    provider = get_provider("gemini", client=client)
    assert isinstance(provider, GeminiProvider)


def test_get_provider_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown model provider"):
        get_provider("unknown-vendor")


def test_missing_api_key_raises_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ProviderError) as exc:
        ClaudeProvider()
    assert exc.value.code == "auth_error"

    with pytest.raises(ProviderError) as exc:
        OpenAIProvider()
    assert exc.value.code == "auth_error"

    with pytest.raises(ProviderError) as exc:
        GeminiProvider()
    assert exc.value.code == "auth_error"


def test_get_provider_missing_key_raises_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderError) as exc:
        get_provider("claude")
    assert exc.value.code == "auth_error"


def test_providers_read_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("anthropic")
    pytest.importorskip("openai")
    pytest.importorskip("google.generativeai")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    with patch("anthropic.Anthropic") as anthropic_ctor:
        ClaudeProvider()
        anthropic_ctor.assert_called_once_with(api_key="test-anthropic-key")

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    with patch("openai.OpenAI") as openai_ctor:
        OpenAIProvider()
        openai_ctor.assert_called_once_with(api_key="test-openai-key")

    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    with patch("google.generativeai.configure") as configure:
        GeminiProvider()
        configure.assert_called_once_with(api_key="test-google-key")
