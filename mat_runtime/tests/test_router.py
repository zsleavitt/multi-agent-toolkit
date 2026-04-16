"""Tests for AgentRouter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mat_runtime.adapters.base import InvocationResult
from mat_runtime.config import AgentDefinition, ProviderConfig
from mat_runtime.router import AgentRouter, MAT2Request, MAT2Response


@pytest.fixture
def sample_agents() -> dict[str, AgentDefinition]:
    """Sample agent definitions for testing."""
    return {
        "coder": AgentDefinition(
            name="coder",
            description="Code implementation agent",
            role="worker",
            cli="codex",
            allowed_mat_ops=["codex.implement", "codex.refactor"],
            system_prompt="You are a code implementation agent.",
        ),
        "reviewer": AgentDefinition(
            name="reviewer",
            description="Code review agent",
            role="worker",
            cli="claude",
            allowed_mat_ops=["codex.review"],
            system_prompt="You are a code review agent.",
        ),
        "orchestrator": AgentDefinition(
            name="orchestrator",
            description="Planning agent",
            role="orchestrator",
            cli="claude",
            allowed_mat_ops=[],
            system_prompt="You are an orchestrator.",
        ),
    }


@pytest.fixture
def sample_provider_config() -> ProviderConfig:
    """Sample provider configuration."""
    return ProviderConfig(
        schema_version="1.0.0",
        agents={
            "worker": {"cli": "codex", "timeout_ms": 60000},
            "orchestrator": {"cli": "claude"},
        },
        routing={"codex_ops": "worker"},
        defaults={"timeout_ms": 300000},
    )


@pytest.fixture
def sample_request() -> MAT2Request:
    """Sample MAT-2 request."""
    return MAT2Request(
        schema_version="1.2.0",
        correlation_id="test-correlation-id",
        idempotency_key="test-idempotency-key",
        op="codex.implement",
        repo_root="/tmp/test-repo",
        instruction="Implement a hello world function",
    )


class TestMAT2Request:
    """Tests for MAT2Request parsing."""

    def test_from_dict(self):
        data = {
            "schema_version": "1.2.0",
            "correlation_id": "abc123",
            "idempotency_key": "key123",
            "op": "codex.implement",
            "repo_root": "/tmp/repo",
            "instruction": "Do something",
        }
        req = MAT2Request.from_dict(data)
        assert req.op == "codex.implement"
        assert req.instruction == "Do something"

    def test_from_json(self):
        json_str = json.dumps({
            "schema_version": "1.2.0",
            "correlation_id": "abc123",
            "idempotency_key": "key123",
            "op": "codex.test",
            "repo_root": "/tmp/repo",
            "instruction": "Run tests",
        })
        req = MAT2Request.from_json(json_str)
        assert req.op == "codex.test"

    def test_from_file(self):
        data = {
            "schema_version": "1.2.0",
            "correlation_id": "abc123",
            "idempotency_key": "key123",
            "op": "codex.review",
            "repo_root": "/tmp/repo",
            "instruction": "Review code",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            req = MAT2Request.from_file(f.name)
        assert req.op == "codex.review"
        Path(f.name).unlink()


class TestMAT2Response:
    """Tests for MAT2Response serialization."""

    def test_success_response(self):
        resp = MAT2Response(
            schema_version="1.2.0",
            correlation_id="abc123",
            idempotency_key="key123",
            ok=True,
            result={"output": "Hello world"},
        )
        d = resp.to_dict()
        assert d["ok"] is True
        assert "result" in d
        assert "error" not in d

    def test_error_response(self):
        resp = MAT2Response(
            schema_version="1.2.0",
            correlation_id="abc123",
            idempotency_key="key123",
            ok=False,
            error={"code": "test_error", "message": "Something went wrong"},
        )
        d = resp.to_dict()
        assert d["ok"] is False
        assert "error" in d
        assert d["error"]["code"] == "test_error"


class TestAgentRouter:
    """Tests for AgentRouter."""

    def test_find_agent(self, sample_agents):
        router = AgentRouter(agents=sample_agents)
        agent = router.find_agent("coder")
        assert agent is not None
        assert agent.name == "coder"

    def test_find_agent_not_found(self, sample_agents):
        router = AgentRouter(agents=sample_agents)
        agent = router.find_agent("nonexistent")
        assert agent is None

    def test_find_agent_for_op_by_allowed_ops(self, sample_agents):
        router = AgentRouter(agents=sample_agents)
        agent = router._find_agent_for_op("codex.implement")
        assert agent is not None
        assert agent.name == "coder"

    def test_find_agent_for_op_review(self, sample_agents):
        router = AgentRouter(agents=sample_agents)
        agent = router._find_agent_for_op("codex.review")
        assert agent is not None
        assert agent.name == "reviewer"

    @patch("mat_runtime.router.get_adapter")
    def test_invoke_success(self, mock_get_adapter, sample_agents, sample_request):
        # Mock adapter
        mock_adapter = MagicMock()
        mock_adapter.invoke.return_value = InvocationResult(
            ok=True,
            stdout="Implementation complete",
            stderr="",
            return_code=0,
            correlation_id=sample_request.correlation_id,
        )
        mock_get_adapter.return_value = mock_adapter

        router = AgentRouter(agents=sample_agents)
        response = router.invoke("coder", sample_request)

        assert response.ok is True
        assert "output" in response.result

    @patch("mat_runtime.router.get_adapter")
    def test_invoke_agent_not_found(self, mock_get_adapter, sample_agents, sample_request):
        router = AgentRouter(agents=sample_agents)
        response = router.invoke("nonexistent", sample_request)

        assert response.ok is False
        assert response.error["code"] == "agent_not_found"

    @patch("mat_runtime.router.get_adapter")
    def test_invoke_operation_not_allowed(
        self, mock_get_adapter, sample_agents, sample_request
    ):
        # Try to invoke reviewer with implement operation
        sample_request.op = "codex.implement"
        router = AgentRouter(agents=sample_agents)
        response = router.invoke("reviewer", sample_request)

        assert response.ok is False
        assert response.error["code"] == "operation_not_allowed"

    @patch("mat_runtime.router.get_adapter")
    def test_invoke_timeout(self, mock_get_adapter, sample_agents, sample_request):
        mock_adapter = MagicMock()
        mock_adapter.invoke.return_value = InvocationResult(
            ok=False,
            stdout="",
            stderr="",
            return_code=-1,
            correlation_id=sample_request.correlation_id,
            timeout_exceeded=True,
        )
        mock_get_adapter.return_value = mock_adapter

        router = AgentRouter(agents=sample_agents)
        response = router.invoke("coder", sample_request)

        assert response.ok is False
        assert response.error["code"] == "timeout"

    @patch("mat_runtime.router.get_adapter")
    def test_invoke_op_routes_correctly(
        self, mock_get_adapter, sample_agents, sample_request
    ):
        mock_adapter = MagicMock()
        mock_adapter.invoke.return_value = InvocationResult(
            ok=True,
            stdout="Done",
            stderr="",
            return_code=0,
            correlation_id=sample_request.correlation_id,
        )
        mock_get_adapter.return_value = mock_adapter

        router = AgentRouter(agents=sample_agents)
        response = router.invoke_op(sample_request)

        assert response.ok is True
        # Should have routed to coder based on codex.implement
        mock_adapter.invoke.assert_called_once()


class TestConfigIntegration:
    """Integration tests for config loading."""

    def test_load_agents_from_directory(self, tmp_path):
        # Create a temporary agents directory
        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()

        # Create a test agent
        (agents_dir / "test-agent.md").write_text(
            """---
name: test-agent
description: A test agent
role: worker
cli: claude
allowed_mat_ops:
  - codex.implement
---

You are a test agent.
"""
        )

        router = AgentRouter(repo_root=tmp_path)
        assert "test-agent" in router.agents
        assert router.agents["test-agent"].cli == "claude"
