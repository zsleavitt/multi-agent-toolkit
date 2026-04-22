# mat_runtime/swarm/tests/test_swarm_variant.py
"""Tests for Swarm variant dispatch mode."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mat_runtime.config import AgentDefinition
from mat_runtime.router import MAT2Response
from mat_runtime.swarm import Swarm, SwarmTask


def _write_definition(data: dict) -> Path:
    """Write a definition to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


class TestVariantValidation:
    """Tests for variant mode candidate validation."""

    def test_reject_base_agent_as_variant_candidate(self):
        """Reject swarm with base agent (no variant_of) as candidate."""
        path = _write_definition({
            "name": "bad-variant-swarm",
            "dispatch_mode": "variant",
            "candidates": ["coder", "python-engineer"],
            "consensus_strategy": "return-all",
        })

        # coder is a base agent (no variant_of), python-engineer is a variant
        mock_agents = {
            "coder": AgentDefinition(
                name="coder",
                description="Base coder agent",
                role="worker",
                cli="codex",
                # No variant_of - this is a base agent
            ),
            "python-engineer": AgentDefinition(
                name="python-engineer",
                description="Python specialist",
                role="worker",
                cli="codex",
                variant_of="coder",
            ),
        }

        with patch("mat_runtime.swarm.swarm.load_agent_definitions", return_value=mock_agents):
            with pytest.raises(ValueError, match="not a variant agent"):
                Swarm(definition_path=path)

        path.unlink()


class TestVariantDispatch:
    """Tests for variant mode dispatch."""

    @pytest.fixture
    def mock_agents(self) -> dict[str, AgentDefinition]:
        return {
            "python-engineer": AgentDefinition(
                name="python-engineer",
                description="Python specialist",
                role="worker",
                cli="codex",
                variant_of="coder",
            ),
            "ruby-engineer": AgentDefinition(
                name="ruby-engineer",
                description="Ruby specialist",
                role="worker",
                cli="codex",
                variant_of="coder",
            ),
        }

    @pytest.fixture
    def variant_swarm_path(self) -> Path:
        path = _write_definition({
            "name": "variant-test-swarm",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "ruby-engineer"],
            "consensus_strategy": "return-all",
        })
        try:
            yield path
        finally:
            if path.exists():
                path.unlink()

    def test_variant_dispatch_invokes_all_agents(
        self,
        variant_swarm_path: Path,
        mock_agents: dict[str, AgentDefinition],
    ):
        """Variant dispatch calls AgentRouter.invoke for each candidate."""
        mock_router = MagicMock()

        def mock_invoke(agent_name, request):
            return MAT2Response(
                schema_version="1.0.0",
                correlation_id=request.correlation_id,
                idempotency_key=request.idempotency_key,
                ok=True,
                result={"output": f"{agent_name} completed"},
            )

        mock_router.invoke = mock_invoke

        with patch("mat_runtime.swarm.swarm.load_agent_definitions", return_value=mock_agents):
            with patch("mat_runtime.swarm.swarm.AgentRouter", return_value=mock_router):
                swarm = Swarm(definition_path=variant_swarm_path)
                task = SwarmTask(instruction="implement feature X")
                result = asyncio.run(swarm.dispatch(task))

        assert result.ok is True
        assert result.consensus_strategy == "return-all"
        assert result.winning_candidate is None
        assert len(result.candidate_results) == 2
        assert "python-engineer" in result.output
        assert "ruby-engineer" in result.output

    def test_variant_dispatch_partial_failure(
        self,
        variant_swarm_path: Path,
        mock_agents: dict[str, AgentDefinition],
    ):
        """Return-all consensus succeeds if at least one variant succeeds."""
        mock_router = MagicMock()

        def mock_invoke(agent_name, request):
            if agent_name == "python-engineer":
                return MAT2Response(
                    schema_version="1.0.0",
                    correlation_id=request.correlation_id,
                    idempotency_key=request.idempotency_key,
                    ok=True,
                    result={"output": "python done"},
                )
            else:
                return MAT2Response(
                    schema_version="1.0.0",
                    correlation_id=request.correlation_id,
                    idempotency_key=request.idempotency_key,
                    ok=False,
                    error={"code": "timeout", "message": "Agent timed out"},
                )

        mock_router.invoke = mock_invoke

        with patch("mat_runtime.swarm.swarm.load_agent_definitions", return_value=mock_agents):
            with patch("mat_runtime.swarm.swarm.AgentRouter", return_value=mock_router):
                swarm = Swarm(definition_path=variant_swarm_path)
                task = SwarmTask(instruction="implement feature X")
                result = asyncio.run(swarm.dispatch(task))

        assert result.ok is True
        assert result.output["python-engineer"]["ok"] is True
        assert result.output["ruby-engineer"]["ok"] is False

    def test_variant_dispatch_all_fail(
        self,
        variant_swarm_path: Path,
        mock_agents: dict[str, AgentDefinition],
    ):
        """Return-all consensus fails if all variants fail."""
        mock_router = MagicMock()

        def mock_invoke(agent_name, request):
            return MAT2Response(
                schema_version="1.0.0",
                correlation_id=request.correlation_id,
                idempotency_key=request.idempotency_key,
                ok=False,
                error={"code": "execution_error", "message": f"{agent_name} failed"},
            )

        mock_router.invoke = mock_invoke

        with patch("mat_runtime.swarm.swarm.load_agent_definitions", return_value=mock_agents):
            with patch("mat_runtime.swarm.swarm.AgentRouter", return_value=mock_router):
                swarm = Swarm(definition_path=variant_swarm_path)
                task = SwarmTask(instruction="implement feature X")
                result = asyncio.run(swarm.dispatch(task))

        assert result.ok is False
        assert result.error["code"] == "all_variants_failed"

    def test_variant_dispatch_handles_exception(
        self,
        variant_swarm_path: Path,
        mock_agents: dict[str, AgentDefinition],
    ):
        """Variant dispatch gracefully handles exceptions from router."""
        mock_router = MagicMock()

        def mock_invoke(agent_name, request):
            if agent_name == "python-engineer":
                raise RuntimeError("Connection failed")
            return MAT2Response(
                schema_version="1.0.0",
                correlation_id=request.correlation_id,
                idempotency_key=request.idempotency_key,
                ok=True,
                result={"output": "ruby done"},
            )

        mock_router.invoke = mock_invoke

        with patch("mat_runtime.swarm.swarm.load_agent_definitions", return_value=mock_agents):
            with patch("mat_runtime.swarm.swarm.AgentRouter", return_value=mock_router):
                swarm = Swarm(definition_path=variant_swarm_path)
                task = SwarmTask(instruction="implement feature X")
                result = asyncio.run(swarm.dispatch(task))

        assert result.ok is True
        python_result = next(
            cr for cr in result.candidate_results if cr.candidate == "python-engineer"
        )
        assert python_result.ok is False
        assert python_result.error["code"] == "exception"
        assert "Connection failed" in python_result.error["message"]
