"""AgentRouter — routes MAT-2 requests to appropriate CLI agents."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mat_runtime import orchestrator_state, telemetry
from mat_runtime.adapters import InvocationResult
from mat_runtime.providers.bridge import create_invocation_provider
from mat_runtime.providers.model import ProviderError
from mat_runtime.providers.protocol import AgentInvocationProvider
from mat_runtime.config import (
    AgentDefinition,
    ProviderConfig,
    load_agent_definitions,
    load_provider_config,
)
from mat_runtime.resilience import (
    ERROR_BUDGET_EXCEEDED,
    ERROR_CIRCUIT_OPEN,
    BudgetLimits,
    CircuitBreaker,
    ResilienceConfig,
    invoke_with_retry,
)


@dataclass
class MAT2Request:
    """Parsed MAT-2 request."""

    schema_version: str
    correlation_id: str
    idempotency_key: str
    op: str
    repo_root: str
    instruction: str
    scope_paths: list[str] = field(default_factory=list)
    session: dict[str, Any] | None = None
    turn: dict[str, Any] | None = None
    timeout_ms: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MAT2Request":
        return cls(
            schema_version=data.get("schema_version", "1.0.0"),
            correlation_id=data.get("correlation_id", str(uuid.uuid4())),
            idempotency_key=data.get("idempotency_key", str(uuid.uuid4())),
            op=data["op"],
            repo_root=data["repo_root"],
            instruction=data["instruction"],
            scope_paths=data.get("scope_paths", []),
            session=data.get("session"),
            turn=data.get("turn"),
            timeout_ms=data.get("timeout_ms"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "MAT2Request":
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: Path | str) -> "MAT2Request":
        return cls.from_dict(json.loads(Path(path).read_text()))


@dataclass
class MAT2Response:
    """MAT-2 response."""

    schema_version: str
    correlation_id: str
    idempotency_key: str
    ok: bool
    replay: bool = False
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "idempotency_key": self.idempotency_key,
            "ok": self.ok,
            "replay": self.replay,
        }
        if self.ok:
            d["result"] = self.result or {}
        else:
            d["error"] = self.error or {"code": "unknown", "message": "Unknown error"}
        return d

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class AgentRouter:
    """
    Routes MAT-2 requests to the appropriate CLI agent.

    Combines MAT-16 provider config with agent definitions to:
    1. Determine which agent handles an operation
    2. Load the agent's system prompt
    3. Invoke the appropriate CLI tool
    4. Return a MAT-2 response
    """

    def __init__(
        self,
        repo_root: Path | str | None = None,
        provider_config: ProviderConfig | None = None,
        agents: dict[str, AgentDefinition] | None = None,
    ):
        """
        Initialize the router.

        Args:
            repo_root: Repository root path. Auto-detected if None.
            provider_config: MAT-16 config. Loaded from repo if None.
            agents: Agent definitions. Loaded from agents/ if None.
        """
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        self.provider_config = provider_config or load_provider_config(
            repo_root=self.repo_root
        )
        self.agents = agents or load_agent_definitions(repo_root=self.repo_root)
        self._adapters: dict[str, AgentInvocationProvider] = {}
        # MAT-98: in-process breaker shared across invocations on this router.
        defaults = self.provider_config.defaults if self.provider_config else {}
        cfg = ResilienceConfig.from_overlay(defaults=defaults)
        self._resilience_config = cfg
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=cfg.breaker_failure_threshold,
            cooldown_ms=cfg.breaker_cooldown_ms,
            spend_rate_window_ms=cfg.spend_rate_window_ms,
            spend_rate_token_limit=cfg.spend_rate_token_limit,
        )

    def _provider_overlay(self, agent: AgentDefinition) -> dict[str, Any]:
        """Merge MAT-16 ``agents`` entries: role defaults, then per-agent name wins."""
        merged: dict[str, Any] = {}
        if not self.provider_config:
            return merged
        agents_map = self.provider_config.agents
        role_cfg = agents_map.get(agent.role)
        if isinstance(role_cfg, dict):
            merged.update(role_cfg)
        name_cfg = agents_map.get(agent.name)
        if isinstance(name_cfg, dict):
            merged.update(name_cfg)
        return merged

    def _get_adapter(self, agent: AgentDefinition) -> AgentInvocationProvider:
        """Get or create invocation provider (CLI or direct API) for an agent."""
        if agent.name not in self._adapters:
            # Check provider config for CLI/API overrides (role, then agent name)
            cli = agent.cli or "codex"
            flags: list[str] = []
            timeout_ms = agent.timeout_ms or 300_000
            overlay: dict[str, Any] = {}
            defaults: dict[str, Any] = {}

            if self.provider_config:
                overlay = self._provider_overlay(agent)
                defaults = self.provider_config.defaults
                if overlay:
                    cli = overlay.get("cli", cli)
                    if "flags" in overlay:
                        flags = list(overlay.get("flags") or [])
                    timeout_ms = overlay.get(
                        "timeout_ms",
                        defaults.get("timeout_ms", timeout_ms),
                    )

            self._adapters[agent.name] = create_invocation_provider(
                cli=cli,
                overlay=overlay,
                defaults=defaults,
                flags=flags,
                working_dir=str(self.repo_root),
                timeout_ms=timeout_ms,
            )

        return self._adapters[agent.name]

    def find_agent_for_op(self, op: str) -> AgentDefinition | None:
        """Find an agent that can handle the given operation."""
        # First check explicit routing in provider config
        if self.provider_config and self.provider_config.routing:
            if op.startswith("codex."):
                role = self.provider_config.routing.get("codex_ops")
                if role:
                    # Find agent with this role
                    for agent in self.agents.values():
                        if agent.role == role:
                            return agent

        # Fall back to checking allowed_mat_ops in agent definitions
        for agent in self.agents.values():
            if op in agent.allowed_mat_ops:
                return agent

        # Default: find any worker agent
        for agent in self.agents.values():
            if agent.role == "worker":
                return agent

        return None

    def find_agent(self, name: str) -> AgentDefinition | None:
        """Find an agent by name."""
        return self.agents.get(name)

    def invoke(
        self,
        agent_name: str,
        request: MAT2Request | dict[str, Any] | str,
    ) -> MAT2Response:
        """
        Invoke an agent with a MAT-2 request.

        Args:
            agent_name: Name of the agent to invoke.
            request: MAT-2 request (dict, JSON string, or MAT2Request object).

        Returns:
            MAT-2 response.
        """
        # Parse request
        if isinstance(request, str):
            req = MAT2Request.from_json(request)
        elif isinstance(request, dict):
            req = MAT2Request.from_dict(request)
        else:
            req = request

        # Root span per MAT task; a child span per CLI invocation is created
        # around adapter.invoke() below. See mat_runtime/telemetry.py (MAT-97).
        with telemetry.start_span(
            f"invoke_agent {req.op}",
            attributes={
                telemetry.GEN_AI_OPERATION_NAME: "invoke_agent",
                telemetry.MAT_OP: req.op,
                telemetry.MAT_CORRELATION_ID: req.correlation_id,
                telemetry.MAT_IDEMPOTENCY_KEY: req.idempotency_key,
                telemetry.MAT_REPO_ROOT: req.repo_root,
                telemetry.MAT_TIMEOUT_MS: req.timeout_ms,
                telemetry.MAT_AGENT_NAME: agent_name,
            },
        ) as root_span:
            return self._invoke_with_span(agent_name, req, root_span)

    def _invoke_with_span(
        self,
        agent_name: str,
        req: MAT2Request,
        root_span: Any,
    ) -> MAT2Response:
        """Core invoke logic, executed inside the task root span."""
        # Find agent
        agent = self.find_agent(agent_name)
        if not agent:
            telemetry.set_error(root_span, error_code="agent_not_found")
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=False,
                error={
                    "code": "agent_not_found",
                    "message": f"Agent '{agent_name}' not found",
                },
            )

        telemetry.set_attributes(
            root_span,
            {
                telemetry.MAT_AGENT_ROLE: agent.role,
                telemetry.MAT_AGENT_CLI: agent.cli,
                telemetry.GEN_AI_SYSTEM: telemetry.cli_to_gen_ai_system(agent.cli),
            },
        )

        # Check if agent can handle this operation
        if agent.allowed_mat_ops and req.op not in agent.allowed_mat_ops:
            telemetry.set_error(root_span, error_code="operation_not_allowed")
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=False,
                error={
                    "code": "operation_not_allowed",
                    "message": f"Agent '{agent_name}' cannot handle operation '{req.op}'",
                },
            )

        # Get adapter and invoke
        try:
            adapter = self._get_adapter(agent)
        except (ProviderError, ValueError) as exc:
            telemetry.set_error(
                root_span, error_code="provider_init_error", message=str(exc)
            )
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=False,
                error={
                    "code": "provider_init_error",
                    "message": str(exc),
                },
            )

        # Resolve the request model for the CLI span (best-effort; MAT-16 overlay).
        overlay = self._provider_overlay(agent)
        request_model = overlay.get("model") if isinstance(overlay, dict) else None
        gen_ai_system = telemetry.cli_to_gen_ai_system(agent.cli)
        defaults = self.provider_config.defaults if self.provider_config else {}
        resilience_cfg = ResilienceConfig.from_overlay(
            overlay=overlay if isinstance(overlay, dict) else {},
            defaults=defaults,
        )
        # Keep breaker thresholds in sync with latest overlay without resetting state.
        self._circuit_breaker.failure_threshold = (
            resilience_cfg.breaker_failure_threshold
        )
        self._circuit_breaker.cooldown_ms = resilience_cfg.breaker_cooldown_ms
        self._circuit_breaker.spend_rate_window_ms = (
            resilience_cfg.spend_rate_window_ms
        )
        self._circuit_breaker.spend_rate_token_limit = (
            resilience_cfg.spend_rate_token_limit
        )

        budgets, state_path, state_doc = self._resolve_budgets(req)

        with telemetry.start_span(
            f"{agent.cli or 'cli'} invoke",
            attributes={
                telemetry.GEN_AI_OPERATION_NAME: "invoke_agent",
                telemetry.GEN_AI_SYSTEM: gen_ai_system,
                telemetry.GEN_AI_REQUEST_MODEL: request_model,
                telemetry.MAT_AGENT_NAME: agent.name,
                telemetry.MAT_AGENT_CLI: agent.cli,
                telemetry.MAT_CORRELATION_ID: req.correlation_id,
            },
        ) as cli_span:
            started = time.perf_counter()
            outcome = invoke_with_retry(
                adapter.invoke,
                idempotency_key=req.idempotency_key,
                config=resilience_cfg,
                breaker=self._circuit_breaker,
                budgets=budgets,
                tokens_from_result=lambda r: self._tokens_from_invocation(r),
                cost_from_result=lambda r: self._cost_from_invocation(r),
                prompt=req.instruction,
                system_prompt=agent.system_prompt,
                working_dir=req.repo_root,
                timeout_ms=req.timeout_ms,
                correlation_id=req.correlation_id,
            )

            if outcome.budget_exceeded:
                self._persist_budget_exceeded(
                    state_path,
                    state_doc,
                    budgets,
                    reason=outcome.budget_message or "Budget exceeded",
                    scope=outcome.budget_scope or "task",
                )
                telemetry.set_error(
                    cli_span,
                    error_code=ERROR_BUDGET_EXCEEDED,
                    message=outcome.budget_message,
                )
                response = MAT2Response(
                    schema_version=req.schema_version,
                    correlation_id=req.correlation_id,
                    idempotency_key=req.idempotency_key,
                    ok=False,
                    error={
                        "code": ERROR_BUDGET_EXCEEDED,
                        "message": outcome.budget_message
                        or "Token or cost budget exceeded",
                    },
                )
                telemetry.set_error(
                    root_span,
                    error_code=ERROR_BUDGET_EXCEEDED,
                    message=outcome.budget_message,
                )
                return response

            if outcome.circuit_open and outcome.result is None:
                telemetry.set_error(
                    cli_span,
                    error_code=ERROR_CIRCUIT_OPEN,
                    message="Circuit breaker is open",
                )
                response = MAT2Response(
                    schema_version=req.schema_version,
                    correlation_id=req.correlation_id,
                    idempotency_key=req.idempotency_key,
                    ok=False,
                    error={
                        "code": ERROR_CIRCUIT_OPEN,
                        "message": "Circuit breaker is open; failing fast",
                    },
                )
                telemetry.set_error(
                    root_span,
                    error_code=ERROR_CIRCUIT_OPEN,
                    message="Circuit breaker is open",
                )
                return response

            result = outcome.result
            if result is None:
                # Invariant: budget_exceeded and circuit_open paths returned above.
                # Treat an unexpected None as an infrastructure failure.
                telemetry.set_error(
                    cli_span, error_code="execution_error", message="No result from invocation"
                )
                telemetry.set_error(
                    root_span, error_code="execution_error", message="No result from invocation"
                )
                return MAT2Response(
                    schema_version=req.schema_version,
                    correlation_id=req.correlation_id,
                    idempotency_key=req.idempotency_key,
                    ok=False,
                    error={"code": "execution_error", "message": "No result from invocation"},
                )
            self._record_invocation_span(cli_span, result, started, request_model)
            self._persist_usage(state_path, state_doc, budgets)

        response = self._build_response(req, result)
        if response.ok:
            telemetry.set_ok(root_span)
        else:
            telemetry.set_error(
                root_span,
                error_code=(response.error or {}).get("code", "unknown"),
                message=(response.error or {}).get("message"),
            )
        return response

    def _resolve_budgets(
        self, req: MAT2Request
    ) -> tuple[BudgetLimits, Path | None, dict[str, Any] | None]:
        """Build budget limits from request session/turn and optional MAT-4 state."""
        budgets = BudgetLimits()
        session = req.session if isinstance(req.session, dict) else {}
        turn = req.turn if isinstance(req.turn, dict) else {}

        if session.get("token_budget") is not None:
            budgets.session_token_budget = int(session["token_budget"])
        if session.get("cost_budget") is not None:
            budgets.session_cost_budget = float(session["cost_budget"])
        if session.get("tokens_used") is not None:
            budgets.session_tokens_used = int(session["tokens_used"])
        if session.get("cost_used") is not None:
            budgets.session_cost_used = float(session["cost_used"])

        task_token = turn.get("token_budget", session.get("task_token_budget"))
        task_cost = turn.get("cost_budget", session.get("task_cost_budget"))
        if task_token is not None:
            budgets.task_token_budget = int(task_token)
        if task_cost is not None:
            budgets.task_cost_budget = float(task_cost)
        if turn.get("tokens_used") is not None:
            budgets.task_tokens_used = int(turn["tokens_used"])
        elif session.get("task_tokens_used") is not None:
            budgets.task_tokens_used = int(session["task_tokens_used"])
        if turn.get("cost_used") is not None:
            budgets.task_cost_used = float(turn["cost_used"])
        elif session.get("task_cost_used") is not None:
            budgets.task_cost_used = float(session["task_cost_used"])

        queue_item_id = session.get("queue_item_id") or turn.get("queue_item_id")
        if queue_item_id:
            budgets.queue_item_id = str(queue_item_id)

        state_path = orchestrator_state.find_state_path(req.repo_root or self.repo_root)
        state_doc: dict[str, Any] | None = None
        if state_path is not None:
            try:
                state_doc = orchestrator_state.load_state(state_path)
                from_state = orchestrator_state.budgets_from_state(
                    state_doc,
                    queue_item_id=budgets.queue_item_id,
                    correlation_id=req.correlation_id,
                )
                # State fills gaps; explicit request session/turn wins.
                for key, value in from_state.items():
                    if value is None:
                        continue
                    current = getattr(budgets, key, None)
                    if key.endswith("_used"):
                        # Prefer the higher watermark so we never under-count.
                        if current is None or current == 0:
                            setattr(budgets, key, value)
                        else:
                            setattr(budgets, key, max(current, value))
                    elif current is None:
                        setattr(budgets, key, value)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                state_doc = None
                state_path = None

        return budgets, state_path, state_doc

    @staticmethod
    def _tokens_from_invocation(result: InvocationResult | None) -> int:
        if result is None:
            return 0
        inp, out = telemetry.extract_token_usage(result.stdout)
        total = (inp or 0) + (out or 0)
        return total

    @staticmethod
    def _cost_from_invocation(result: InvocationResult | None) -> float:
        """Best-effort cost from stdout JSON ``usage.cost`` / ``cost`` when present."""
        if result is None or not result.stdout:
            return 0.0
        stripped = result.stdout.strip()
        if not (stripped.startswith("{") and stripped.endswith("}")):
            return 0.0
        try:
            data = json.loads(stripped)
        except ValueError:
            return 0.0
        if not isinstance(data, dict):
            return 0.0
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else data
        for key in ("cost", "total_cost", "cost_usd"):
            value = usage.get(key) if isinstance(usage, dict) else None
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        return 0.0

    @staticmethod
    def _persist_budget_exceeded(
        state_path: Path | None,
        state_doc: dict[str, Any] | None,
        budgets: BudgetLimits,
        *,
        reason: str,
        scope: str,
    ) -> None:
        if state_path is None or state_doc is None:
            return
        orchestrator_state.record_budget_exceeded_transition(
            state_doc,
            reason=reason,
            scope=scope,
            queue_item_id=budgets.queue_item_id,
        )
        try:
            orchestrator_state.save_state(state_path, state_doc)
        except OSError:
            pass

    @staticmethod
    def _persist_usage(
        state_path: Path | None,
        state_doc: dict[str, Any] | None,
        budgets: BudgetLimits,
    ) -> None:
        if state_path is None or state_doc is None:
            return
        orchestrator_state.sync_usage_counters(
            state_doc,
            session_tokens_used=budgets.session_tokens_used,
            session_cost_used=budgets.session_cost_used,
            queue_item_id=budgets.queue_item_id,
            task_tokens_used=budgets.task_tokens_used,
            task_cost_used=budgets.task_cost_used,
        )
        try:
            orchestrator_state.save_state(state_path, state_doc)
        except OSError:
            pass

    @staticmethod
    def _record_invocation_span(
        cli_span: Any,
        result: InvocationResult,
        started: float,
        request_model: str | None,
    ) -> None:
        """Populate a CLI-invocation span from the adapter result."""
        duration_ms = int((time.perf_counter() - started) * 1000)
        input_tokens, output_tokens = telemetry.extract_token_usage(result.stdout)
        telemetry.set_attributes(
            cli_span,
            {
                telemetry.MAT_DURATION_MS: duration_ms,
                telemetry.MAT_RETURN_CODE: result.return_code,
                telemetry.MAT_TIMEOUT_EXCEEDED: result.timeout_exceeded,
                telemetry.MAT_CORRELATION_ID: result.correlation_id,
                telemetry.GEN_AI_RESPONSE_MODEL: request_model,
                telemetry.GEN_AI_USAGE_INPUT_TOKENS: input_tokens,
                telemetry.GEN_AI_USAGE_OUTPUT_TOKENS: output_tokens,
            },
        )
        if result.ok:
            telemetry.set_ok(cli_span)
        elif result.timeout_exceeded:
            telemetry.set_error(
                cli_span, error_code="timeout", message=result.stderr or "timeout"
            )
        else:
            telemetry.set_error(
                cli_span,
                error_code="execution_error",
                message=result.stderr or f"CLI returned code {result.return_code}",
            )

    @staticmethod
    def _build_response(req: MAT2Request, result: InvocationResult) -> MAT2Response:
        """Translate an adapter :class:`InvocationResult` into a MAT-2 response."""
        if result.ok:
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=True,
                result={
                    "output": result.stdout,
                    "files_modified": [],  # Would need to parse from output
                },
            )

        if result.timeout_exceeded:
            error_code = "timeout"
        elif result.stdout.strip():
            # Agent produced output but failed = semantic refusal
            error_code = "agent_refused"
        else:
            # No output = infrastructure failure
            error_code = "execution_error"
        # Preserve refusal reason from stdout for agent_refused errors
        if error_code == "agent_refused":
            error_message = result.stdout.strip()
        else:
            error_message = result.stderr or f"CLI returned code {result.return_code}"
        return MAT2Response(
            schema_version=req.schema_version,
            correlation_id=req.correlation_id,
            idempotency_key=req.idempotency_key,
            ok=False,
            error={
                "code": error_code,
                "message": error_message,
            },
        )

    def invoke_op(self, request: MAT2Request | dict[str, Any] | str) -> MAT2Response:
        """
        Invoke the appropriate agent for a MAT-2 operation.

        Automatically routes to the right agent based on the operation.
        """
        # Parse request
        if isinstance(request, str):
            req = MAT2Request.from_json(request)
        elif isinstance(request, dict):
            req = MAT2Request.from_dict(request)
        else:
            req = request

        # Find agent for this operation
        agent = self.find_agent_for_op(req.op)
        if not agent:
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=False,
                error={
                    "code": "no_agent_for_op",
                    "message": f"No agent found to handle operation '{req.op}'",
                },
            )

        return self.invoke(agent.name, req)
