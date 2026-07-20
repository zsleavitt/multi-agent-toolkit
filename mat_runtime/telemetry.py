"""OpenTelemetry GenAI tracing for the MAT runtime (MAT-97).

This module owns *all* OpenTelemetry wiring so the rest of the runtime never
imports ``opentelemetry`` directly. Every OTel dependency is optional: if the
packages are not installed the helpers degrade to no-ops and the runtime behaves
exactly as before. Install them with the ``otel`` extra::

    pip install '.[otel]'

Design:
- ``configure_tracing()`` builds a ``TracerProvider`` with an OTLP exporter so
  any GenAI-aware backend (Langfuse, Phoenix, Datadog, …) can ingest the spans.
  It is idempotent and only activates when tracing is explicitly enabled via env
  (``MAT_OTEL_ENABLED`` or an ``OTEL_EXPORTER_OTLP_ENDPOINT``).
- ``start_span()`` is a context manager that yields a span (or ``None`` when
  OTel is unavailable) so call sites stay identical in both modes.
- Attribute helpers follow the OpenTelemetry **GenAI semantic conventions**.
  Those attributes are still marked *Development* stability upstream, so the
  version we target is pinned in :data:`GEN_AI_SEMCONV_VERSION` — expect churn
  and bump deliberately.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

# The GenAI semantic conventions are still "Development" stability upstream: the
# attribute names (gen_ai.*) and their values change between semconv releases.
# Pin the version we target here so a dependency bump is an explicit, reviewable
# change rather than a silent behavioral drift. Bump together with the
# opentelemetry-semantic-conventions dependency.
GEN_AI_SEMCONV_VERSION = "1.44.0"
SCHEMA_URL = f"https://opentelemetry.io/schemas/{GEN_AI_SEMCONV_VERSION}"

INSTRUMENTATION_NAME = "mat_runtime"
DEFAULT_SERVICE_NAME = "mat-runtime"

# --- GenAI semantic-convention attribute keys ---------------------------------
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_SYSTEM = "gen_ai.system"
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

# --- MAT-specific attribute keys (namespaced under mat.*) ----------------------
MAT_OP = "mat.op"
MAT_CORRELATION_ID = "mat.correlation_id"
MAT_IDEMPOTENCY_KEY = "mat.idempotency_key"
MAT_AGENT_NAME = "mat.agent.name"
MAT_AGENT_ROLE = "mat.agent.role"
MAT_AGENT_CLI = "mat.agent.cli"
MAT_REPO_ROOT = "mat.repo_root"
MAT_TIMEOUT_MS = "mat.request.timeout_ms"
MAT_DURATION_MS = "mat.duration_ms"
MAT_RETURN_CODE = "mat.return_code"
MAT_TIMEOUT_EXCEEDED = "mat.timeout_exceeded"
MAT_ERROR_CODE = "mat.error.code"

# Map MAT-16 ``cli`` bindings to GenAI ``gen_ai.system`` values.
_CLI_TO_GEN_AI_SYSTEM: dict[str, str] = {
    "claude": "anthropic",
    "codex": "openai",
    "codex-review": "openai",
    "gemini": "gcp.gemini",
}

try:  # OTel is an optional dependency (the ``otel`` extra).
    from opentelemetry import trace as _trace
    from opentelemetry.trace import SpanKind, Status, StatusCode

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    _OTEL_AVAILABLE = False
    SpanKind = None  # type: ignore[assignment]
    Status = None  # type: ignore[assignment]
    StatusCode = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing only
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Span, Tracer


# Test/host code can inject a provider (e.g. one wired to an in-memory exporter)
# without touching the global OTel provider, which can only be set once.
_tracer_provider: Any | None = None
_configured = False


def is_available() -> bool:
    """Return True if the OpenTelemetry API is importable."""
    return _OTEL_AVAILABLE


def cli_to_gen_ai_system(cli: str | None) -> str | None:
    """Map a MAT-16 ``cli`` binding to a ``gen_ai.system`` value."""
    if not cli:
        return None
    return _CLI_TO_GEN_AI_SYSTEM.get(cli, cli)


def set_tracer_provider(provider: Any | None) -> None:
    """Install a specific ``TracerProvider`` for the runtime to use.

    Passing an explicit provider avoids the global-provider-set-once limitation,
    which matters for tests that need a fresh in-memory exporter each run.
    """
    global _tracer_provider
    _tracer_provider = provider


def get_tracer() -> "Tracer | None":
    """Return the runtime tracer, or ``None`` when OTel is unavailable."""
    if not _OTEL_AVAILABLE:
        return None
    if _tracer_provider is not None:
        return _tracer_provider.get_tracer(
            INSTRUMENTATION_NAME,
            schema_url=SCHEMA_URL,
        )
    return _trace.get_tracer(INSTRUMENTATION_NAME, schema_url=SCHEMA_URL)


def configure_tracing(
    *,
    service_name: str | None = None,
    force: bool = False,
) -> bool:
    """Set up an OTLP-exporting ``TracerProvider`` when tracing is enabled.

    Tracing activates only when explicitly requested via environment so that
    normal CLI usage stays quiet and dependency-free:

    - ``MAT_OTEL_ENABLED`` is truthy (``1``/``true``/``yes``/``on``), or
    - ``OTEL_EXPORTER_OTLP_ENDPOINT`` (or the traces-specific variant) is set.

    The OTLP exporter reads its endpoint/headers/protocol from the standard
    ``OTEL_EXPORTER_OTLP_*`` environment variables. Returns True if a provider
    was configured.
    """
    global _configured
    if _configured and not force:
        return _tracer_provider is not None
    if not _OTEL_AVAILABLE:
        return False
    if not (force or _tracing_enabled()):
        return False

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:  # pragma: no cover - SDK/exporter extra not installed
        return False

    resource = Resource.create(
        {
            "service.name": service_name
            or os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME),
            "gen_ai.semconv.version": GEN_AI_SEMCONV_VERSION,
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    set_tracer_provider(provider)
    # Also register globally so any other OTel-aware code shares the provider.
    try:
        _trace.set_tracer_provider(provider)
    except Exception:  # pragma: no cover - already set elsewhere
        pass

    _configured = True
    return True


def _tracing_enabled() -> bool:
    flag = os.getenv("MAT_OTEL_ENABLED", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    return bool(
        os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    )


def _clean_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    """Drop ``None`` values (OTel rejects them) and keep JSON-safe scalars."""
    if not attributes:
        return {}
    return {k: v for k, v in attributes.items() if v is not None}


@contextmanager
def start_span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
    kind: Any | None = None,
) -> Iterator["Span | None"]:
    """Start a span as the current span, yielding ``None`` when OTel is absent.

    Exceptions propagate after being recorded and marking the span as errored,
    mirroring ``tracer.start_as_current_span`` semantics.
    """
    tracer = get_tracer()
    if tracer is None:
        yield None
        return

    span_kind = kind if kind is not None else SpanKind.CLIENT
    with tracer.start_as_current_span(
        name,
        kind=span_kind,
        attributes=_clean_attributes(attributes),
    ) as span:
        yield span


def set_attributes(span: "Span | None", attributes: dict[str, Any] | None) -> None:
    """Set multiple attributes on ``span`` (no-op if span is ``None``)."""
    if span is None:
        return
    for key, value in _clean_attributes(attributes).items():
        span.set_attribute(key, value)


def set_ok(span: "Span | None") -> None:
    """Mark ``span`` as successfully completed."""
    if span is None:
        return
    span.set_status(Status(StatusCode.OK))


def set_error(
    span: "Span | None",
    *,
    error_code: str,
    message: str | None = None,
) -> None:
    """Mark ``span`` as errored and record the MAT error code."""
    if span is None:
        return
    span.set_attribute(MAT_ERROR_CODE, error_code)
    span.set_status(Status(StatusCode.ERROR, message or error_code))


def extract_token_usage(text: str | None) -> tuple[int | None, int | None]:
    """Best-effort ``(input_tokens, output_tokens)`` from CLI stdout.

    Conservative on purpose: only parses stdout that is a single JSON object and
    only trusts well-known usage keys. Returns ``(None, None)`` otherwise so we
    never fabricate token counts a CLI did not actually surface.
    """
    if not text:
        return None, None
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return None, None
    try:
        data = json.loads(stripped)
    except ValueError:
        return None, None
    if not isinstance(data, dict):
        return None, None

    usage = data.get("usage")
    if not isinstance(usage, dict):
        usage = data  # some CLIs surface token counts at the top level

    def _pick(*keys: str) -> int | None:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return int(value)
        return None

    input_tokens = _pick("input_tokens", "prompt_tokens", "input")
    output_tokens = _pick("output_tokens", "completion_tokens", "output")
    return input_tokens, output_tokens


__all__ = [
    "GEN_AI_SEMCONV_VERSION",
    "SCHEMA_URL",
    "INSTRUMENTATION_NAME",
    "GEN_AI_OPERATION_NAME",
    "GEN_AI_SYSTEM",
    "GEN_AI_REQUEST_MODEL",
    "GEN_AI_RESPONSE_MODEL",
    "GEN_AI_USAGE_INPUT_TOKENS",
    "GEN_AI_USAGE_OUTPUT_TOKENS",
    "MAT_OP",
    "MAT_CORRELATION_ID",
    "MAT_IDEMPOTENCY_KEY",
    "MAT_AGENT_NAME",
    "MAT_AGENT_ROLE",
    "MAT_AGENT_CLI",
    "MAT_REPO_ROOT",
    "MAT_TIMEOUT_MS",
    "MAT_DURATION_MS",
    "MAT_RETURN_CODE",
    "MAT_TIMEOUT_EXCEEDED",
    "MAT_ERROR_CODE",
    "is_available",
    "cli_to_gen_ai_system",
    "get_tracer",
    "set_tracer_provider",
    "configure_tracing",
    "start_span",
    "set_attributes",
    "set_ok",
    "set_error",
    "extract_token_usage",
]
