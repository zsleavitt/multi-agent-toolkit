"""Tests for OpenTelemetry GenAI tracing (MAT-97).

Uses the OTel in-memory span exporter so span emission is asserted without any
external collector. Skipped entirely when the optional ``otel`` extra is absent.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("opentelemetry.sdk")

from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode  # noqa: E402

from mat_runtime import telemetry  # noqa: E402
from mat_runtime.adapters.base import InvocationResult  # noqa: E402
from mat_runtime.config import AgentDefinition, ProviderConfig  # noqa: E402
from mat_runtime.router import AgentRouter, MAT2Request  # noqa: E402


@pytest.fixture
def span_exporter():
    """Install an in-memory exporter as the runtime tracer provider."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    telemetry.set_tracer_provider(provider)
    try:
        yield exporter
    finally:
        telemetry.set_tracer_provider(None)
        provider.shutdown()


@pytest.fixture
def agents() -> dict[str, AgentDefinition]:
    return {
        "coder": AgentDefinition(
            name="coder",
            description="Code implementation agent",
            role="worker",
            cli="codex",
            allowed_mat_ops=["codex.implement"],
            system_prompt="You are a coder.",
        ),
        "reviewer": AgentDefinition(
            name="reviewer",
            description="Review agent",
            role="worker",
            cli="claude",
            allowed_mat_ops=["codex.review"],
            system_prompt="You are a reviewer.",
        ),
    }


@pytest.fixture
def request_() -> MAT2Request:
    return MAT2Request(
        schema_version="1.2.0",
        correlation_id="corr-1",
        idempotency_key="idem-1",
        op="codex.implement",
        repo_root="/tmp/repo",
        instruction="Implement a thing",
        timeout_ms=60_000,
    )


def _by_name(exporter: InMemorySpanExporter) -> dict[str, object]:
    return {span.name: span for span in exporter.get_finished_spans()}


class TestTokenUsageExtraction:
    def test_parses_nested_usage_object(self):
        out = '{"usage": {"input_tokens": 10, "output_tokens": 25}}'
        assert telemetry.extract_token_usage(out) == (10, 25)

    def test_parses_openai_style_keys(self):
        out = '{"usage": {"prompt_tokens": 3, "completion_tokens": 7}}'
        assert telemetry.extract_token_usage(out) == (3, 7)

    def test_top_level_keys(self):
        out = '{"input_tokens": 1, "output_tokens": 2}'
        assert telemetry.extract_token_usage(out) == (1, 2)

    def test_non_json_returns_none(self):
        assert telemetry.extract_token_usage("hello world") == (None, None)

    def test_empty_returns_none(self):
        assert telemetry.extract_token_usage("") == (None, None)
        assert telemetry.extract_token_usage(None) == (None, None)

    def test_booleans_are_ignored(self):
        out = '{"input_tokens": true, "output_tokens": 5}'
        assert telemetry.extract_token_usage(out) == (None, 5)


class TestCliMapping:
    def test_known_clis(self):
        assert telemetry.cli_to_gen_ai_system("claude") == "anthropic"
        assert telemetry.cli_to_gen_ai_system("codex") == "openai"
        assert telemetry.cli_to_gen_ai_system("codex-review") == "openai"
        assert telemetry.cli_to_gen_ai_system("gemini") == "gcp.gemini"

    def test_unknown_cli_passthrough(self):
        assert telemetry.cli_to_gen_ai_system("cursor") == "cursor"

    def test_none(self):
        assert telemetry.cli_to_gen_ai_system(None) is None


class TestConfigureTracing:
    def test_disabled_without_env(self, monkeypatch):
        monkeypatch.delenv("MAT_OTEL_ENABLED", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
        monkeypatch.setattr(telemetry, "_configured", False)
        assert telemetry.configure_tracing() is False

    def test_enabled_via_flag(self, monkeypatch):
        monkeypatch.setenv("MAT_OTEL_ENABLED", "1")
        monkeypatch.setattr(telemetry, "_configured", False)
        monkeypatch.setattr(telemetry, "_tracer_provider", None)
        provider = None
        try:
            assert telemetry.configure_tracing() is True
            assert telemetry.get_tracer() is not None
            provider = telemetry._tracer_provider
        finally:
            # Shut down the OTLP BatchSpanProcessor so its background export
            # thread does not linger and spam connection errors after the test.
            if provider is not None:
                provider.shutdown()
            telemetry.set_tracer_provider(None)  # also resets _configured


class TestRouterSpans:
    @patch("mat_runtime.router.create_invocation_provider")
    def test_success_emits_root_and_cli_spans(
        self, mock_provider, span_exporter, agents, request_
    ):
        adapter = MagicMock()
        adapter.invoke.return_value = InvocationResult(
            ok=True,
            stdout='{"usage": {"input_tokens": 11, "output_tokens": 22}}',
            stderr="",
            return_code=0,
            correlation_id="corr-1",
        )
        mock_provider.return_value = adapter

        router = AgentRouter(agents=agents)
        response = router.invoke("coder", request_)
        assert response.ok is True

        spans = _by_name(span_exporter)
        assert "invoke_agent codex.implement" in spans
        assert "codex invoke" in spans

        root = spans["invoke_agent codex.implement"]
        cli = spans["codex invoke"]

        # Root span attributes from the MAT-2 request.
        assert root.attributes[telemetry.MAT_OP] == "codex.implement"
        assert root.attributes[telemetry.MAT_CORRELATION_ID] == "corr-1"
        assert root.attributes[telemetry.MAT_AGENT_NAME] == "coder"
        assert root.attributes[telemetry.MAT_TIMEOUT_MS] == 60_000
        assert root.status.status_code == StatusCode.OK

        # CLI span carries GenAI attributes + token usage.
        assert cli.attributes[telemetry.GEN_AI_SYSTEM] == "openai"
        assert cli.attributes[telemetry.GEN_AI_USAGE_INPUT_TOKENS] == 11
        assert cli.attributes[telemetry.GEN_AI_USAGE_OUTPUT_TOKENS] == 22
        assert cli.attributes[telemetry.MAT_RETURN_CODE] == 0
        assert cli.status.status_code == StatusCode.OK

        # Child span is nested under the root task span.
        assert cli.parent is not None
        assert cli.parent.span_id == root.context.span_id

    @patch("mat_runtime.router.create_invocation_provider")
    def test_request_model_from_overlay(
        self, mock_provider, span_exporter, agents, request_
    ):
        adapter = MagicMock()
        adapter.invoke.return_value = InvocationResult(
            ok=True, stdout="done", stderr="", return_code=0, correlation_id="corr-1"
        )
        mock_provider.return_value = adapter

        cfg = ProviderConfig(
            schema_version="1.0.0",
            agents={"worker": {"cli": "codex", "model": "gpt-4o"}},
            routing={},
            defaults={},
        )
        router = AgentRouter(agents=agents, provider_config=cfg)
        router.invoke("coder", request_)

        cli = _by_name(span_exporter)["codex invoke"]
        assert cli.attributes[telemetry.GEN_AI_REQUEST_MODEL] == "gpt-4o"

    @patch("mat_runtime.router.create_invocation_provider")
    def test_timeout_sets_error_status(
        self, mock_provider, span_exporter, agents, request_
    ):
        adapter = MagicMock()
        adapter.invoke.return_value = InvocationResult(
            ok=False,
            stdout="",
            stderr="",
            return_code=-1,
            correlation_id="corr-1",
            timeout_exceeded=True,
        )
        mock_provider.return_value = adapter

        router = AgentRouter(agents=agents)
        response = router.invoke("coder", request_)
        assert response.ok is False

        spans = _by_name(span_exporter)
        root = spans["invoke_agent codex.implement"]
        cli = spans["codex invoke"]
        assert cli.status.status_code == StatusCode.ERROR
        assert cli.attributes[telemetry.MAT_TIMEOUT_EXCEEDED] is True
        assert cli.attributes[telemetry.MAT_ERROR_CODE] == "timeout"
        assert root.status.status_code == StatusCode.ERROR
        assert root.attributes[telemetry.MAT_ERROR_CODE] == "timeout"

    @patch("mat_runtime.router.create_invocation_provider")
    def test_agent_not_found_marks_root_error_no_cli_span(
        self, mock_provider, span_exporter, agents, request_
    ):
        router = AgentRouter(agents=agents)
        response = router.invoke("ghost", request_)
        assert response.ok is False

        spans = _by_name(span_exporter)
        assert "codex invoke" not in spans
        root = spans["invoke_agent codex.implement"]
        assert root.status.status_code == StatusCode.ERROR
        assert root.attributes[telemetry.MAT_ERROR_CODE] == "agent_not_found"

    @patch("mat_runtime.router.create_invocation_provider")
    def test_operation_not_allowed_marks_root_error(
        self, mock_provider, span_exporter, agents, request_
    ):
        request_.op = "codex.implement"
        router = AgentRouter(agents=agents)
        response = router.invoke("reviewer", request_)
        assert response.ok is False

        root = _by_name(span_exporter)["invoke_agent codex.implement"]
        assert root.status.status_code == StatusCode.ERROR
        assert root.attributes[telemetry.MAT_ERROR_CODE] == "operation_not_allowed"


class TestTracingDisabledFallback:
    """When no provider is installed, spans are silently dropped."""

    @patch("mat_runtime.router.create_invocation_provider")
    def test_invoke_works_without_provider(self, mock_provider, agents, request_):
        telemetry.set_tracer_provider(None)
        adapter = MagicMock()
        adapter.invoke.return_value = InvocationResult(
            ok=True, stdout="ok", stderr="", return_code=0, correlation_id="corr-1"
        )
        mock_provider.return_value = adapter

        router = AgentRouter(agents=agents)
        response = router.invoke("coder", request_)
        assert response.ok is True
