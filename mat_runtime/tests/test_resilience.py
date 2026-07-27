"""Tests for MAT-98 cost + resilience controls."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from mat_runtime.adapters.base import InvocationResult
from mat_runtime.config import AgentDefinition, ProviderConfig
from mat_runtime import orchestrator_state
from mat_runtime.resilience import (
    ERROR_BUDGET_EXCEEDED,
    ERROR_CIRCUIT_OPEN,
    BudgetLimits,
    CircuitBreaker,
    CircuitState,
    ResilienceConfig,
    invoke_with_retry,
)
from mat_runtime.router import AgentRouter, MAT2Request


@pytest.fixture
def sample_agents() -> dict[str, AgentDefinition]:
    return {
        "coder": AgentDefinition(
            name="coder",
            description="Code implementation agent",
            role="worker",
            cli="codex",
            allowed_mat_ops=["codex.implement"],
            system_prompt="You are a code implementation agent.",
        ),
    }


@pytest.fixture
def sample_request() -> MAT2Request:
    return MAT2Request(
        schema_version="1.2.0",
        correlation_id="test-correlation-id",
        idempotency_key="test-idempotency-key",
        op="codex.implement",
        repo_root="/tmp/test-repo",
        instruction="Implement a hello world function",
    )


def _fail_result(correlation_id: str = "c") -> InvocationResult:
    return InvocationResult(
        ok=False,
        stdout="",
        stderr="Connection refused",
        return_code=1,
        correlation_id=correlation_id,
        timeout_exceeded=False,
    )


def _ok_result(correlation_id: str = "c", stdout: str = "done") -> InvocationResult:
    return InvocationResult(
        ok=True,
        stdout=stdout,
        stderr="",
        return_code=0,
        correlation_id=correlation_id,
    )


class TestCircuitBreaker:
    def test_closed_to_open_after_threshold(self):
        clock = {"t": 0.0}

        def now() -> float:
            return clock["t"]

        breaker = CircuitBreaker(
            failure_threshold=3,
            cooldown_ms=10_000,
            _clock=now,
        )
        assert breaker.state is CircuitState.CLOSED
        assert breaker.allow() is True

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state is CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.state is CircuitState.OPEN
        assert breaker.allow() is False

    def test_open_to_half_open_after_cooldown_then_closed_on_success(self):
        clock = {"t": 0.0}

        def now() -> float:
            return clock["t"]

        breaker = CircuitBreaker(
            failure_threshold=2,
            cooldown_ms=5_000,
            _clock=now,
        )
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state is CircuitState.OPEN

        clock["t"] = 4.0
        assert breaker.allow() is False
        assert breaker.state is CircuitState.OPEN

        clock["t"] = 5.0
        assert breaker.allow() is True
        assert breaker.state is CircuitState.HALF_OPEN

        breaker.record_success()
        assert breaker.state is CircuitState.CLOSED
        assert breaker.consecutive_failures == 0

    def test_half_open_failure_reopens(self):
        clock = {"t": 0.0}

        def now() -> float:
            return clock["t"]

        breaker = CircuitBreaker(
            failure_threshold=1,
            cooldown_ms=1_000,
            _clock=now,
        )
        breaker.record_failure()
        assert breaker.state is CircuitState.OPEN
        clock["t"] = 2.0
        assert breaker.allow() is True
        assert breaker.state is CircuitState.HALF_OPEN
        breaker.record_failure()
        assert breaker.state is CircuitState.OPEN

    def test_spend_rate_spike_trips_breaker(self):
        clock = {"t": 0.0}

        def now() -> float:
            return clock["t"]

        breaker = CircuitBreaker(
            failure_threshold=99,
            spend_rate_window_ms=60_000,
            spend_rate_token_limit=100,
            _clock=now,
        )
        breaker.record_success(tokens=60)
        assert breaker.state is CircuitState.CLOSED
        breaker.record_success(tokens=50)
        assert breaker.state is CircuitState.OPEN
        assert breaker.allow() is False


class TestBudgetLimits:
    def test_session_token_budget_exceeded(self):
        budgets = BudgetLimits(
            session_token_budget=100,
            session_tokens_used=100,
        )
        ok, scope, message = budgets.check()
        assert ok is False
        assert scope == "session"
        assert "token" in (message or "")

    def test_task_cost_budget_exceeded(self):
        budgets = BudgetLimits(
            task_cost_budget=1.5,
            task_cost_used=1.5,
        )
        ok, scope, message = budgets.check()
        assert ok is False
        assert scope == "task"
        assert "cost" in (message or "")

    def test_within_budget(self):
        budgets = BudgetLimits(
            session_token_budget=1000,
            session_tokens_used=10,
            task_cost_budget=5.0,
            task_cost_used=0.1,
        )
        ok, scope, message = budgets.check()
        assert ok is True
        assert scope is None
        assert message is None


class TestInvokeWithRetry:
    def test_retries_execution_error_then_succeeds(self):
        calls = {"n": 0}
        sleeps: list[float] = []

        def invoke(**_kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                return _fail_result()
            return _ok_result()

        cfg = ResilienceConfig(max_retries=3, backoff_ms=10, backoff_multiplier=2.0)
        breaker = CircuitBreaker(failure_threshold=10)
        outcome = invoke_with_retry(
            invoke,
            idempotency_key="idem-1",
            config=cfg,
            breaker=breaker,
            sleep_fn=lambda s: sleeps.append(s),
        )
        assert outcome.result.ok is True
        assert outcome.attempts == 3
        assert len(outcome.retry_reasons) == 2
        assert sleeps == [0.01, 0.02]
        assert breaker.state is CircuitState.CLOSED

    def test_no_retry_without_idempotency_key(self):
        calls = {"n": 0}

        def invoke(**_kwargs):
            calls["n"] += 1
            return _fail_result()

        cfg = ResilienceConfig(max_retries=5, backoff_ms=1)
        outcome = invoke_with_retry(
            invoke,
            idempotency_key=None,
            config=cfg,
            breaker=CircuitBreaker(failure_threshold=10),
            sleep_fn=lambda _s: None,
        )
        assert outcome.result.ok is False
        assert outcome.attempts == 1
        assert calls["n"] == 1

    def test_no_retry_on_agent_refused(self):
        calls = {"n": 0}

        def invoke(**_kwargs):
            calls["n"] += 1
            return InvocationResult(
                ok=False,
                stdout="I refuse this request.",
                stderr="",
                return_code=1,
                correlation_id="c",
            )

        cfg = ResilienceConfig(max_retries=5, backoff_ms=1)
        outcome = invoke_with_retry(
            invoke,
            idempotency_key="idem-1",
            config=cfg,
            breaker=CircuitBreaker(failure_threshold=10),
            sleep_fn=lambda _s: None,
        )
        assert outcome.attempts == 1
        assert calls["n"] == 1
        assert outcome.result.stdout.startswith("I refuse")

    def test_retries_timeout_failures(self):
        calls = {"n": 0}

        def invoke(**_kwargs):
            calls["n"] += 1
            return InvocationResult(
                ok=False,
                stdout="",
                stderr="",
                return_code=-1,
                correlation_id="c",
                timeout_exceeded=True,
            )

        cfg = ResilienceConfig(max_retries=2, backoff_ms=0)
        outcome = invoke_with_retry(
            invoke,
            idempotency_key="idem-1",
            config=cfg,
            breaker=CircuitBreaker(failure_threshold=10),
            sleep_fn=lambda _s: None,
        )
        assert outcome.attempts == 3
        assert calls["n"] == 3
        assert outcome.result.timeout_exceeded is True

    def test_circuit_open_fail_fast(self):
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.record_failure()
        assert breaker.state is CircuitState.OPEN

        outcome = invoke_with_retry(
            lambda **_k: _ok_result(),
            idempotency_key="idem-1",
            config=ResilienceConfig(max_retries=2),
            breaker=breaker,
            sleep_fn=lambda _s: None,
        )
        assert outcome.circuit_open is True
        assert outcome.attempts == 0
        assert outcome.result is None

    def test_budget_exceeded_before_invoke(self):
        called = {"n": 0}

        def invoke(**_kwargs):
            called["n"] += 1
            return _ok_result()

        budgets = BudgetLimits(session_token_budget=10, session_tokens_used=10)
        outcome = invoke_with_retry(
            invoke,
            idempotency_key="idem-1",
            config=ResilienceConfig(max_retries=2),
            breaker=CircuitBreaker(failure_threshold=10),
            budgets=budgets,
            sleep_fn=lambda _s: None,
        )
        assert outcome.budget_exceeded is True
        assert outcome.budget_scope == "session"
        assert called["n"] == 0


class TestOrchestratorStateBudgets:
    def test_record_budget_exceeded_transition(self):
        state = {
            "schema_version": "1.1.0",
            "queue": {
                "items": [
                    {"id": "q-1", "status": "running", "title": "t"},
                ]
            },
            "artifacts": {"items": []},
            "checkpoints": {"items": []},
            "meta": {},
        }
        orchestrator_state.record_budget_exceeded_transition(
            state,
            reason="Session token budget exceeded",
            scope="session",
            queue_item_id="q-1",
            at="2026-07-26T12:00:00Z",
        )
        assert state["queue"]["items"][0]["status"] == "budget_exceeded"
        assert state["schema_version"] == "1.2.0"
        transitions = state["meta"]["transitions"]
        assert len(transitions) == 1
        assert transitions[0]["to"] == "budget_exceeded"
        assert transitions[0]["from"] == "running"
        assert transitions[0]["scope"] == "session"

    def test_budgets_from_state(self):
        state = {
            "orchestrator_session": {
                "session_id": "s1",
                "token_budget": 1000,
                "tokens_used": 50,
            },
            "queue": {
                "items": [
                    {
                        "id": "q-1",
                        "status": "running",
                        "token_budget": 200,
                        "cost_budget": 1.0,
                        "correlation_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
                    }
                ]
            },
        }
        fields = orchestrator_state.budgets_from_state(
            state, correlation_id="a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"
        )
        assert fields["session_token_budget"] == 1000
        assert fields["session_tokens_used"] == 50
        assert fields["task_token_budget"] == 200
        assert fields["task_cost_budget"] == 1.0
        assert fields["queue_item_id"] == "q-1"


class TestRouterResilience:
    @patch("mat_runtime.router.create_invocation_provider")
    def test_router_retries_execution_error(
        self, mock_create, sample_agents, sample_request
    ):
        mock_adapter = MagicMock()
        mock_adapter.invoke.side_effect = [
            _fail_result(sample_request.correlation_id),
            _ok_result(sample_request.correlation_id, "recovered"),
        ]
        mock_create.return_value = mock_adapter

        cfg = ProviderConfig(
            schema_version="1.0.0",
            agents={"worker": {"cli": "codex"}},
            defaults={
                "max_retries": 2,
                "backoff_ms": 0,
                "circuit_breaker": {"failure_threshold": 10},
            },
        )
        router = AgentRouter(agents=sample_agents, provider_config=cfg)
        response = router.invoke("coder", sample_request)
        assert response.ok is True
        assert mock_adapter.invoke.call_count == 2

    @patch("mat_runtime.router.create_invocation_provider")
    def test_router_budget_exceeded_and_state_transition(
        self, mock_create, sample_agents, sample_request, tmp_path
    ):
        mock_adapter = MagicMock()
        mock_create.return_value = mock_adapter

        state = {
            "schema_version": "1.2.0",
            "orchestrator_session": {
                "session_id": "s1",
                "token_budget": 10,
                "tokens_used": 10,
            },
            "queue": {
                "items": [
                    {
                        "id": "q-1",
                        "status": "running",
                        "title": "work",
                        "correlation_id": sample_request.correlation_id,
                    }
                ]
            },
            "artifacts": {"items": []},
            "checkpoints": {"items": []},
            "meta": {},
        }
        state_path = tmp_path / "orchestrator.state.json"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        sample_request.repo_root = str(tmp_path)
        sample_request.session = {"queue_item_id": "q-1"}

        router = AgentRouter(agents=sample_agents)
        response = router.invoke("coder", sample_request)

        assert response.ok is False
        assert response.error["code"] == ERROR_BUDGET_EXCEEDED
        mock_adapter.invoke.assert_not_called()

        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["queue"]["items"][0]["status"] == "budget_exceeded"
        assert saved["meta"]["transitions"][0]["to"] == "budget_exceeded"

    @patch("mat_runtime.router.create_invocation_provider")
    def test_router_circuit_open(
        self, mock_create, sample_agents, sample_request
    ):
        mock_adapter = MagicMock()
        mock_adapter.invoke.return_value = _fail_result(
            sample_request.correlation_id
        )
        mock_create.return_value = mock_adapter

        cfg = ProviderConfig(
            schema_version="1.0.0",
            agents={"worker": {"cli": "codex"}},
            defaults={
                "max_retries": 0,
                "circuit_breaker": {
                    "failure_threshold": 2,
                    "cooldown_ms": 60_000,
                },
            },
        )
        router = AgentRouter(agents=sample_agents, provider_config=cfg)

        r1 = router.invoke("coder", sample_request)
        assert r1.ok is False
        assert r1.error["code"] == "execution_error"

        r2 = router.invoke("coder", sample_request)
        assert r2.ok is False
        assert r2.error["code"] == "execution_error"

        r3 = router.invoke("coder", sample_request)
        assert r3.ok is False
        assert r3.error["code"] == ERROR_CIRCUIT_OPEN
        assert mock_adapter.invoke.call_count == 2

    def test_resilience_config_from_env(self):
        cfg = ResilienceConfig.from_overlay(
            defaults={},
            overlay={},
            env={
                "MAT_MAX_RETRIES": "3",
                "MAT_BREAKER_FAILURE_THRESHOLD": "7",
                "MAT_SPEND_RATE_TOKEN_LIMIT": "999",
            },
        )
        assert cfg.max_retries == 3
        assert cfg.breaker_failure_threshold == 7
        assert cfg.spend_rate_token_limit == 999
