"""Cost + resilience controls for CLI/API invocations (MAT-98).

Pure-stdlib retry (bounded exponential backoff), in-process circuit breaker,
and token/cost budget enforcement. Wired around ``adapter.invoke()`` in
:class:`~mat_runtime.router.AgentRouter`.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

# Infrastructure failures are retryable; semantic refusals are not.
RETRYABLE_ERROR_CODES = frozenset({"execution_error", "timeout"})

ERROR_CIRCUIT_OPEN = "circuit_open"
ERROR_BUDGET_EXCEEDED = "budget_exceeded"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ResilienceConfig:
    """Retry + circuit-breaker settings (MAT-16 overlay / env / defaults)."""

    max_retries: int = 0
    backoff_ms: int = 500
    backoff_multiplier: float = 2.0
    breaker_failure_threshold: int = 5
    breaker_cooldown_ms: int = 30_000
    spend_rate_window_ms: int = 60_000
    spend_rate_token_limit: int | None = None

    @classmethod
    def from_overlay(
        cls,
        overlay: dict[str, Any] | None = None,
        defaults: dict[str, Any] | None = None,
        env: dict[str, str] | None = None,
    ) -> "ResilienceConfig":
        """Merge defaults → overlay → env (later wins)."""
        merged: dict[str, Any] = {}
        for source in (defaults or {}, overlay or {}):
            for key in (
                "max_retries",
                "backoff_ms",
                "backoff_multiplier",
            ):
                if key in source and source[key] is not None:
                    merged[key] = source[key]
            breaker = source.get("circuit_breaker")
            if isinstance(breaker, dict):
                if breaker.get("failure_threshold") is not None:
                    merged["breaker_failure_threshold"] = breaker["failure_threshold"]
                if breaker.get("cooldown_ms") is not None:
                    merged["breaker_cooldown_ms"] = breaker["cooldown_ms"]
                if breaker.get("spend_rate_window_ms") is not None:
                    merged["spend_rate_window_ms"] = breaker["spend_rate_window_ms"]
                if breaker.get("spend_rate_token_limit") is not None:
                    merged["spend_rate_token_limit"] = breaker["spend_rate_token_limit"]

        environ = env if env is not None else os.environ
        env_map = {
            "MAT_MAX_RETRIES": ("max_retries", int),
            "MAT_BACKOFF_MS": ("backoff_ms", int),
            "MAT_BACKOFF_MULTIPLIER": ("backoff_multiplier", float),
            "MAT_BREAKER_FAILURE_THRESHOLD": ("breaker_failure_threshold", int),
            "MAT_BREAKER_COOLDOWN_MS": ("breaker_cooldown_ms", int),
            "MAT_SPEND_RATE_WINDOW_MS": ("spend_rate_window_ms", int),
            "MAT_SPEND_RATE_TOKEN_LIMIT": ("spend_rate_token_limit", int),
        }
        for env_key, (field_name, caster) in env_map.items():
            raw = environ.get(env_key)
            if raw is not None and str(raw).strip() != "":
                merged[field_name] = caster(raw)

        base = cls()
        return cls(
            max_retries=int(merged.get("max_retries", base.max_retries)),
            backoff_ms=int(merged.get("backoff_ms", base.backoff_ms)),
            backoff_multiplier=float(
                merged.get("backoff_multiplier", base.backoff_multiplier)
            ),
            breaker_failure_threshold=int(
                merged.get(
                    "breaker_failure_threshold", base.breaker_failure_threshold
                )
            ),
            breaker_cooldown_ms=int(
                merged.get("breaker_cooldown_ms", base.breaker_cooldown_ms)
            ),
            spend_rate_window_ms=int(
                merged.get("spend_rate_window_ms", base.spend_rate_window_ms)
            ),
            spend_rate_token_limit=(
                int(merged["spend_rate_token_limit"])
                if merged.get("spend_rate_token_limit") is not None
                else base.spend_rate_token_limit
            ),
        )


@dataclass
class BudgetLimits:
    """Optional session/task caps and running totals."""

    session_token_budget: int | None = None
    session_cost_budget: float | None = None
    session_tokens_used: int = 0
    session_cost_used: float = 0.0
    task_token_budget: int | None = None
    task_cost_budget: float | None = None
    task_tokens_used: int = 0
    task_cost_used: float = 0.0
    queue_item_id: str | None = None

    def check(self) -> tuple[bool, str | None, str | None]:
        """Return ``(ok, scope, message)``; ``ok`` is False when a budget is exceeded."""
        if (
            self.session_token_budget is not None
            and self.session_tokens_used >= self.session_token_budget
        ):
            return (
                False,
                "session",
                f"Session token budget exceeded "
                f"({self.session_tokens_used} >= {self.session_token_budget})",
            )
        if (
            self.session_cost_budget is not None
            and self.session_cost_used >= self.session_cost_budget
        ):
            return (
                False,
                "session",
                f"Session cost budget exceeded "
                f"({self.session_cost_used} >= {self.session_cost_budget})",
            )
        if (
            self.task_token_budget is not None
            and self.task_tokens_used >= self.task_token_budget
        ):
            return (
                False,
                "task",
                f"Task token budget exceeded "
                f"({self.task_tokens_used} >= {self.task_token_budget})",
            )
        if (
            self.task_cost_budget is not None
            and self.task_cost_used >= self.task_cost_budget
        ):
            return (
                False,
                "task",
                f"Task cost budget exceeded "
                f"({self.task_cost_used} >= {self.task_cost_budget})",
            )
        return True, None, None

    def record(self, tokens: int = 0, cost: float = 0.0) -> None:
        """Accumulate usage after a successful or attempted invocation."""
        if tokens > 0:
            self.session_tokens_used += tokens
            self.task_tokens_used += tokens
        if cost > 0:
            self.session_cost_used += cost
            self.task_cost_used += cost


@dataclass
class CircuitBreaker:
    """In-process circuit breaker with consecutive-failure and spend-rate trips."""

    failure_threshold: int = 5
    cooldown_ms: int = 30_000
    spend_rate_window_ms: int = 60_000
    spend_rate_token_limit: int | None = None
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    opened_at_monotonic: float | None = None
    _spend_events: list[tuple[float, int]] = field(default_factory=list)
    _clock: Callable[[], float] = field(default=time.monotonic, repr=False)

    def allow(self) -> bool:
        """True when a call may proceed; False when the breaker is open (fail-fast)."""
        self._maybe_transition_to_half_open()
        if self.state is CircuitState.OPEN:
            return False
        return True

    def record_success(self, tokens: int = 0) -> None:
        """Close the breaker (or keep closed) after a successful call."""
        now = self._clock()
        if tokens > 0:
            self._record_spend(now, tokens)
            if self._spend_rate_exceeded(now):
                self._trip(now)
                return
        self.consecutive_failures = 0
        self.state = CircuitState.CLOSED
        self.opened_at_monotonic = None

    def record_failure(self) -> None:
        """Count an infrastructure failure; may open the breaker."""
        self.consecutive_failures += 1
        if self.state is CircuitState.HALF_OPEN:
            self._trip(self._clock())
            return
        if self.consecutive_failures >= self.failure_threshold:
            self._trip(self._clock())

    def _trip(self, now: float) -> None:
        self.state = CircuitState.OPEN
        self.opened_at_monotonic = now

    def _maybe_transition_to_half_open(self) -> None:
        if self.state is not CircuitState.OPEN:
            return
        if self.opened_at_monotonic is None:
            return
        elapsed_ms = (self._clock() - self.opened_at_monotonic) * 1000.0
        if elapsed_ms >= self.cooldown_ms:
            self.state = CircuitState.HALF_OPEN

    def _record_spend(self, now: float, tokens: int) -> None:
        self._spend_events.append((now, tokens))
        cutoff = now - (self.spend_rate_window_ms / 1000.0)
        self._spend_events = [(t, n) for t, n in self._spend_events if t >= cutoff]

    def _spend_rate_exceeded(self, now: float) -> bool:
        if self.spend_rate_token_limit is None:
            return False
        cutoff = now - (self.spend_rate_window_ms / 1000.0)
        total = sum(n for t, n in self._spend_events if t >= cutoff)
        return total > self.spend_rate_token_limit


@dataclass
class RetryOutcome:
    """Result of :func:`invoke_with_retry`."""

    result: Any
    attempts: int
    retry_reasons: list[str] = field(default_factory=list)
    circuit_open: bool = False
    budget_exceeded: bool = False
    budget_scope: str | None = None
    budget_message: str | None = None


def classify_invocation_error(
    *,
    ok: bool,
    timeout_exceeded: bool,
    stdout: str,
) -> str | None:
    """Map an :class:`~mat_runtime.adapters.base.InvocationResult` to a MAT error code."""
    if ok:
        return None
    if timeout_exceeded:
        return "timeout"
    if (stdout or "").strip():
        return "agent_refused"
    return "execution_error"


def invoke_with_retry(
    invoke_fn: Callable[..., Any],
    *,
    idempotency_key: str | None,
    config: ResilienceConfig,
    breaker: CircuitBreaker,
    budgets: BudgetLimits | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    classify_fn: Callable[..., str | None] | None = None,
    tokens_from_result: Callable[[Any], int] | None = None,
    cost_from_result: Callable[[Any], float] | None = None,
    **invoke_kwargs: Any,
) -> RetryOutcome:
    """Call ``invoke_fn`` with budget check, circuit breaker, and bounded retries.

    Retries only when ``idempotency_key`` is present and the failure is an
    infrastructure error (``execution_error`` / ``timeout``). Semantic refusals
    (``agent_refused``) are never retried.
    """
    sleep = sleep_fn or time.sleep
    classify = classify_fn or (
        lambda result: classify_invocation_error(
            ok=bool(getattr(result, "ok", False)),
            timeout_exceeded=bool(getattr(result, "timeout_exceeded", False)),
            stdout=str(getattr(result, "stdout", "") or ""),
        )
    )
    token_of = tokens_from_result or (lambda _r: 0)
    cost_of = cost_from_result or (lambda _r: 0.0)

    if budgets is not None:
        ok_budget, scope, message = budgets.check()
        if not ok_budget:
            return RetryOutcome(
                result=None,
                attempts=0,
                budget_exceeded=True,
                budget_scope=scope,
                budget_message=message,
            )

    if not breaker.allow():
        return RetryOutcome(result=None, attempts=0, circuit_open=True)

    # Retries require an idempotency key so callers can safely re-issue.
    max_attempts = 1 + (
        config.max_retries if idempotency_key else 0
    )
    backoff_ms = config.backoff_ms
    retry_reasons: list[str] = []
    last_result: Any = None

    for attempt in range(1, max_attempts + 1):
        if attempt > 1 and not breaker.allow():
            return RetryOutcome(
                result=last_result,
                attempts=attempt - 1,
                retry_reasons=retry_reasons,
                circuit_open=True,
            )

        last_result = invoke_fn(**invoke_kwargs)
        error_code = classify(last_result)
        tokens = int(token_of(last_result) or 0)
        cost = float(cost_of(last_result) or 0.0)

        if budgets is not None and (tokens or cost):
            budgets.record(tokens=tokens, cost=cost)

        if error_code is None:
            breaker.record_success(tokens=tokens)
            return RetryOutcome(
                result=last_result,
                attempts=attempt,
                retry_reasons=retry_reasons,
            )

        # Semantic refusal / non-retryable: count as success for breaker
        # (agent answered) only for agent_refused; infra failures trip the breaker.
        if error_code not in RETRYABLE_ERROR_CODES:
            if error_code == "agent_refused":
                breaker.record_success(tokens=tokens)
            else:
                breaker.record_failure()
            return RetryOutcome(
                result=last_result,
                attempts=attempt,
                retry_reasons=retry_reasons,
            )

        breaker.record_failure()
        if attempt >= max_attempts:
            return RetryOutcome(
                result=last_result,
                attempts=attempt,
                retry_reasons=retry_reasons,
            )

        retry_reasons.append(f"Attempt {attempt}: {error_code}")
        if backoff_ms > 0:
            sleep(backoff_ms / 1000.0)
        backoff_ms = int(backoff_ms * config.backoff_multiplier)


__all__ = [
    "RETRYABLE_ERROR_CODES",
    "ERROR_CIRCUIT_OPEN",
    "ERROR_BUDGET_EXCEEDED",
    "CircuitState",
    "ResilienceConfig",
    "BudgetLimits",
    "CircuitBreaker",
    "RetryOutcome",
    "classify_invocation_error",
    "invoke_with_retry",
]
