# OpenTelemetry GenAI Tracing (MAT-97)

The MAT runtime emits [OpenTelemetry](https://opentelemetry.io/) spans following
the [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
for every task dispatch. This gives end-to-end tracing across the orchestrator →
router → CLI boundary that any GenAI-aware backend (Langfuse, Phoenix, Datadog,
Grafana Tempo, …) can ingest over OTLP.

Tracing is **optional and off by default**: with the extra uninstalled or the
enable flag unset, the runtime behaves exactly as before (the tracing helpers
degrade to no-ops).

## Span model

`AgentRouter.invoke` emits two nested spans per task:

- **Root span** — one per MAT task (`invoke_agent <op>`). Carries the request
  metadata (op, correlation id, idempotency key, repo root, timeout, agent).
- **Child span** — one per CLI invocation (`<cli> invoke`), wrapping the
  `adapter.invoke()` call. Carries the GenAI attributes, latency, return code,
  error status, and token usage when the CLI surfaces it.

```
invoke_agent codex.implement            (root, StatusCode.OK)
└── codex invoke                         (child, StatusCode.OK)
```

## Attributes

### GenAI semantic conventions (`gen_ai.*`)

| Attribute | Where | Notes |
|-----------|-------|-------|
| `gen_ai.operation.name` | root + child | `invoke_agent` |
| `gen_ai.system` | root + child | mapped from the agent `cli` (`claude`→`anthropic`, `codex`→`openai`, `gemini`→`gcp.gemini`) |
| `gen_ai.request.model` | child | from the MAT-16 overlay `model`, when configured |
| `gen_ai.response.model` | child | best-effort; mirrors the request model |
| `gen_ai.usage.input_tokens` | child | when surfaced by the CLI stdout (JSON `usage`) |
| `gen_ai.usage.output_tokens` | child | when surfaced by the CLI stdout (JSON `usage`) |

> **SemConv stability.** The GenAI conventions are still *Development* stability
> upstream — attribute names and values change between releases. The version we
> target is pinned in `GEN_AI_SEMCONV_VERSION` in
> [`mat_runtime/telemetry.py`](../../mat_runtime/telemetry.py) and set as the
> span `schema_url`. Bump it deliberately alongside the
> `opentelemetry-semantic-conventions` dependency.

### MAT-specific attributes (`mat.*`)

`mat.op`, `mat.correlation_id`, `mat.idempotency_key`, `mat.agent.name`,
`mat.agent.role`, `mat.agent.cli`, `mat.repo_root`, `mat.request.timeout_ms`,
`mat.duration_ms`, `mat.return_code`, `mat.timeout_exceeded`, and `mat.error.code`
(set on failure, alongside `StatusCode.ERROR`).

## Enabling tracing

1. Install the optional dependencies:

```bash
pip install '.[otel]'
```

2. Enable tracing and point the OTLP exporter at your collector. Tracing turns on
   when `MAT_OTEL_ENABLED` is truthy **or** an OTLP endpoint is set:

```bash
export MAT_OTEL_ENABLED=1
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_SERVICE_NAME=mat-runtime   # optional (defaults to "mat-runtime")

python -m mat_runtime invoke --agent coder \
  --op codex.implement \
  --instruction "Add a hello() function to util.py"
```

The exporter reads all standard `OTEL_EXPORTER_OTLP_*` variables (endpoint,
headers, protocol, timeout). Spans are batched and exported over gRPC OTLP.

## Example trace

A successful `codex.implement` dispatch produces the following spans. Child span
shown as exported JSON (abridged):

```json
{
  "name": "codex invoke",
  "kind": "SpanKind.CLIENT",
  "status": { "status_code": "OK" },
  "parent_id": "aabbccddeeff1122",
  "attributes": {
    "gen_ai.operation.name": "invoke_agent",
    "gen_ai.system": "openai",
    "gen_ai.request.model": "gpt-4o",
    "gen_ai.usage.input_tokens": 11,
    "gen_ai.usage.output_tokens": 22,
    "mat.agent.name": "coder",
    "mat.agent.cli": "codex",
    "mat.correlation_id": "corr-1",
    "mat.duration_ms": 842,
    "mat.return_code": 0,
    "mat.timeout_exceeded": false
  }
}
```

Root span attributes for the same task:

```json
{
  "name": "invoke_agent codex.implement",
  "status": { "status_code": "OK" },
  "attributes": {
    "gen_ai.operation.name": "invoke_agent",
    "gen_ai.system": "openai",
    "mat.op": "codex.implement",
    "mat.correlation_id": "corr-1",
    "mat.idempotency_key": "idem-1",
    "mat.repo_root": "/path/to/repo",
    "mat.request.timeout_ms": 60000,
    "mat.agent.name": "coder",
    "mat.agent.role": "worker",
    "mat.agent.cli": "codex"
  }
}
```

On failure (timeout, refusal, or infrastructure error) the child and root spans
are marked `StatusCode.ERROR` with `mat.error.code` set to the MAT error code
(`timeout`, `agent_refused`, `execution_error`, `agent_not_found`,
`operation_not_allowed`, or `provider_init_error`).

## Relationship to the Hive event bus (MAT-52)

OTel spans **complement** the in-process
[`EventBus`](../../mat_runtime/hive/events.py) rather than replacing it. The
event bus delivers structured Crew/Swarm lifecycle events to in-process
observers (logging, webhooks); OTel spans provide distributed, backend-agnostic
tracing of the per-task CLI invocation path. Use both: the event bus for
orchestration-level observability, OTel for cross-service trace correlation.
