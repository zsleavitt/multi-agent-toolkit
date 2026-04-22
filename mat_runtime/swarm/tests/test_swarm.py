# mat_runtime/swarm/tests/test_swarm.py
"""Tests for Swarm dispatch and consensus."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mat_runtime.adapters import InvocationResult
from mat_runtime.swarm import Swarm, SwarmTask


def _write_definition(data: dict) -> Path:
    """Write a definition to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


def _make_invocation_result(ok: bool, stdout: str = "", stderr: str = "") -> InvocationResult:
    """Create an InvocationResult for testing."""
    return InvocationResult(
        ok=ok,
        stdout=stdout,
        stderr=stderr,
        return_code=0 if ok else 1,
        correlation_id="test-correlation",
        timeout_exceeded=False,
    )


class TestSwarmInit:
    """Tests for Swarm initialization."""

    def test_reject_unknown_candidate(self):
        """Reject swarm with unknown CLI adapter."""
        path = _write_definition({
            "name": "unknown-adapter",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "unknown_cli"],
            "consensus_strategy": "first-complete",
        })

        with pytest.raises(ValueError, match="Unknown CLI adapter 'unknown_cli'"):
            Swarm(definition_path=path)

        path.unlink()

    def test_valid_initialization(self):
        """Initialize swarm with valid candidates."""
        path = _write_definition({
            "name": "valid-swarm",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "first-complete",
        })

        swarm = Swarm(definition_path=path)

        assert swarm.name == "valid-swarm"
        assert swarm.definition.candidates == ["claude", "codex"]

        path.unlink()


class TestSwarmDispatch:
    """Tests for Swarm.dispatch()."""

    @pytest.fixture
    def swarm_path(self) -> Path:
        """Create a valid swarm definition."""
        path = _write_definition({
            "name": "test-swarm",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "first-complete",
        })
        yield path
        path.unlink()

    def test_first_complete_selects_fastest_success(self, swarm_path: Path):
        """First-complete consensus returns fastest successful response."""
        import time

        swarm = Swarm(definition_path=swarm_path)

        # Mock adapters - codex succeeds faster than claude
        mock_claude = MagicMock()
        mock_codex = MagicMock()

        def claude_invoke(**kwargs):
            time.sleep(0.05)  # Claude takes 50ms
            return _make_invocation_result(ok=True, stdout="claude output")

        def codex_invoke(**kwargs):
            # Codex returns immediately (faster)
            return _make_invocation_result(ok=True, stdout="codex output")

        mock_claude.invoke = claude_invoke
        mock_codex.invoke = codex_invoke

        swarm._adapters = {"claude": mock_claude, "codex": mock_codex}

        task = SwarmTask(instruction="test instruction")
        result = asyncio.run(swarm.dispatch(task))

        assert result.ok is True
        # Codex should win because it completed faster
        assert result.winning_candidate == "codex"
        assert result.output == "codex output"
        assert len(result.candidate_results) == 2

    def test_first_complete_skips_failures(self, swarm_path: Path):
        """First-complete skips failed candidates."""
        swarm = Swarm(definition_path=swarm_path)

        mock_claude = MagicMock()
        mock_codex = MagicMock()

        # Claude fails, codex succeeds
        mock_claude.invoke = lambda **kwargs: _make_invocation_result(
            ok=False, stderr="claude failed"
        )
        mock_codex.invoke = lambda **kwargs: _make_invocation_result(
            ok=True, stdout="codex success"
        )

        swarm._adapters = {"claude": mock_claude, "codex": mock_codex}

        task = SwarmTask(instruction="test")
        result = asyncio.run(swarm.dispatch(task))

        assert result.ok is True
        assert result.winning_candidate == "codex"
        assert result.output == "codex success"

    def test_all_fail_returns_aggregate_error(self, swarm_path: Path):
        """When all candidates fail, return aggregate error."""
        swarm = Swarm(definition_path=swarm_path)

        mock_claude = MagicMock()
        mock_codex = MagicMock()

        mock_claude.invoke = lambda **kwargs: _make_invocation_result(
            ok=False, stderr="claude error"
        )
        mock_codex.invoke = lambda **kwargs: _make_invocation_result(
            ok=False, stderr="codex error"
        )

        swarm._adapters = {"claude": mock_claude, "codex": mock_codex}

        task = SwarmTask(instruction="test")
        result = asyncio.run(swarm.dispatch(task))

        assert result.ok is False
        assert result.winning_candidate is None
        assert result.error is not None
        assert result.error["code"] == "all_candidates_failed"
        assert len(result.error["details"]) == 2

    def test_timing_metadata_collected(self, swarm_path: Path):
        """Verify timing metadata is collected for all candidates."""
        swarm = Swarm(definition_path=swarm_path)

        mock_claude = MagicMock()
        mock_codex = MagicMock()

        mock_claude.invoke = lambda **kwargs: _make_invocation_result(ok=True)
        mock_codex.invoke = lambda **kwargs: _make_invocation_result(ok=True)

        swarm._adapters = {"claude": mock_claude, "codex": mock_codex}

        task = SwarmTask(instruction="test")
        result = asyncio.run(swarm.dispatch(task))

        assert result.duration_ms >= 0
        for cr in result.candidate_results:
            assert cr.duration_ms >= 0

    def test_exception_in_candidate_returns_error_result(self, swarm_path: Path):
        """Exception in candidate invoke returns error CandidateResult."""
        swarm = Swarm(definition_path=swarm_path)

        mock_claude = MagicMock()
        mock_codex = MagicMock()

        mock_claude.invoke = MagicMock(side_effect=RuntimeError("connection failed"))
        mock_codex.invoke = lambda **kwargs: _make_invocation_result(ok=True, stdout="ok")

        swarm._adapters = {"claude": mock_claude, "codex": mock_codex}

        task = SwarmTask(instruction="test")
        result = asyncio.run(swarm.dispatch(task))

        # Should still succeed because codex succeeded
        assert result.ok is True
        assert result.winning_candidate == "codex"

        # Claude should have error in candidate_results
        claude_result = next(cr for cr in result.candidate_results if cr.candidate == "claude")
        assert claude_result.ok is False
        assert "connection failed" in claude_result.error

    def test_correlation_id_preserved(self, swarm_path: Path):
        """Correlation ID from task is preserved in result."""
        swarm = Swarm(definition_path=swarm_path)

        mock_claude = MagicMock()
        mock_codex = MagicMock()

        mock_claude.invoke = lambda **kwargs: _make_invocation_result(ok=True)
        mock_codex.invoke = lambda **kwargs: _make_invocation_result(ok=True)

        swarm._adapters = {"claude": mock_claude, "codex": mock_codex}

        task = SwarmTask(instruction="test", correlation_id="my-correlation-123")
        result = asyncio.run(swarm.dispatch(task))

        assert result.correlation_id == "my-correlation-123"


class TestCandidateResultVariant:
    """Tests for CandidateResult with variant mode output."""

    def test_candidate_result_stores_variant_output(self):
        """CandidateResult can store variant-specific output dict."""
        from mat_runtime.swarm.types import CandidateResult

        result = CandidateResult(
            candidate="python-engineer",
            ok=True,
            response=None,
            duration_ms=1500,
            variant_output={"files_modified": ["src/main.py"], "output": "Done"},
        )

        assert result.variant_output is not None
        assert result.variant_output["output"] == "Done"


class TestReturnAllParallelModel:
    """Tests for return-all consensus with parallel_model dispatch."""

    @pytest.fixture
    def return_all_swarm_path(self) -> Path:
        """Create a return-all parallel_model swarm definition."""
        path = _write_definition({
            "name": "return-all-swarm",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "return-all",
        })
        yield path
        path.unlink()

    def test_return_all_collects_all_successes(self, return_all_swarm_path: Path):
        """Return-all collects outputs from all successful candidates."""
        swarm = Swarm(definition_path=return_all_swarm_path)

        mock_claude = MagicMock()
        mock_codex = MagicMock()

        mock_claude.invoke = lambda **kwargs: _make_invocation_result(
            ok=True, stdout="claude review output"
        )
        mock_codex.invoke = lambda **kwargs: _make_invocation_result(
            ok=True, stdout="codex review output"
        )

        swarm._adapters = {"claude": mock_claude, "codex": mock_codex}

        task = SwarmTask(instruction="review this code")
        result = asyncio.run(swarm.dispatch(task))

        assert result.ok is True
        assert result.consensus_strategy == "return-all"
        assert result.winning_candidate is None  # No winner in return-all
        assert "claude" in result.output
        assert "codex" in result.output
        assert result.output["claude"]["ok"] is True
        assert result.output["claude"]["output"] == "claude review output"
        assert result.output["codex"]["ok"] is True
        assert result.output["codex"]["output"] == "codex review output"

    def test_return_all_partial_success(self, return_all_swarm_path: Path):
        """Return-all succeeds if at least one candidate succeeds."""
        swarm = Swarm(definition_path=return_all_swarm_path)

        mock_claude = MagicMock()
        mock_codex = MagicMock()

        mock_claude.invoke = lambda **kwargs: _make_invocation_result(
            ok=True, stdout="claude success"
        )
        mock_codex.invoke = lambda **kwargs: _make_invocation_result(
            ok=False, stderr="codex failed"
        )

        swarm._adapters = {"claude": mock_claude, "codex": mock_codex}

        task = SwarmTask(instruction="review")
        result = asyncio.run(swarm.dispatch(task))

        assert result.ok is True
        assert result.output["claude"]["ok"] is True
        assert result.output["claude"]["output"] == "claude success"
        assert result.output["codex"]["ok"] is False
        assert "error" in result.output["codex"]

    def test_return_all_all_fail(self, return_all_swarm_path: Path):
        """Return-all fails only if all candidates fail."""
        swarm = Swarm(definition_path=return_all_swarm_path)

        mock_claude = MagicMock()
        mock_codex = MagicMock()

        mock_claude.invoke = lambda **kwargs: _make_invocation_result(
            ok=False, stderr="claude error"
        )
        mock_codex.invoke = lambda **kwargs: _make_invocation_result(
            ok=False, stderr="codex error"
        )

        swarm._adapters = {"claude": mock_claude, "codex": mock_codex}

        task = SwarmTask(instruction="review")
        result = asyncio.run(swarm.dispatch(task))

        assert result.ok is False
        assert result.error is not None
        assert result.error["code"] == "all_candidates_failed"
        assert result.output["claude"]["ok"] is False
        assert result.output["codex"]["ok"] is False


class TestSwarmVariantInit:
    """Tests for Swarm initialization with variant dispatch_mode."""

    def test_accept_variant_candidates_with_router(self):
        """Accept variant swarm when all candidates exist as agents."""
        from mat_runtime.config import AgentDefinition

        path = _write_definition({
            "name": "variant-swarm",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "ruby-engineer"],
            "consensus_strategy": "return-all",
        })

        mock_agents = {
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

        with patch("mat_runtime.swarm.swarm.load_agent_definitions", return_value=mock_agents):
            swarm = Swarm(definition_path=path)

        assert swarm.name == "variant-swarm"
        assert swarm.definition.dispatch_mode == "variant"
        assert swarm._router is not None
        assert "python-engineer" in swarm._agents
        assert "ruby-engineer" in swarm._agents

        path.unlink()

    def test_reject_unknown_variant_candidate(self):
        """Reject swarm with unknown agent variant."""
        from mat_runtime.config import AgentDefinition

        path = _write_definition({
            "name": "bad-variant-swarm",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "unknown-agent"],
            "consensus_strategy": "return-all",
        })

        mock_agents = {
            "python-engineer": AgentDefinition(
                name="python-engineer",
                description="Python specialist",
                role="worker",
                cli="codex",
                variant_of="coder",
            ),
        }

        with patch("mat_runtime.swarm.swarm.load_agent_definitions", return_value=mock_agents):
            with pytest.raises(ValueError, match="Unknown agent variant 'unknown-agent'"):
                Swarm(definition_path=path)

        path.unlink()
