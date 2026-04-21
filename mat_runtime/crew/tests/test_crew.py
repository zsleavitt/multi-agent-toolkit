"""Tests for Crew orchestration class."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mat_runtime.crew.crew import Crew, RETRYABLE_ERRORS
from mat_runtime.crew.types import CrewTask, CrewResult
from mat_runtime.config import AgentDefinition
from mat_runtime.router import MAT2Response


@pytest.fixture
def crew_definition(tmp_path: Path) -> Path:
    """Create a minimal crew definition file."""
    crew_file = tmp_path / "test-crew.json"
    crew_file.write_text(json.dumps({
        "schema_version": "1.0.0",
        "name": "test-crew",
        "agents": ["coder", "reviewer"],
        "routing": {
            "strategy": "round-robin",
        },
        "constraints": {
            "max_concurrent_agents": 2,
            "max_tasks": 10,
            "retry_policy": {
                "max_retries": 2,
                "backoff_ms": 10,
            },
        },
    }))
    return crew_file


@pytest.fixture
def mock_router() -> MagicMock:
    """Create a mock AgentRouter."""
    router = MagicMock()
    router.agents = {
        "coder": AgentDefinition(
            name="coder",
            description="Coder agent",
            role="worker",
            specialization={"languages": ["python"]},
        ),
        "reviewer": AgentDefinition(
            name="reviewer",
            description="Reviewer agent",
            role="worker",
            specialization={"domain": "security"},
        ),
    }
    router.find_agent.side_effect = lambda name: router.agents.get(name)
    return router


class TestCrewInit:
    """Tests for Crew initialization."""

    def test_init_loads_definition(
        self,
        crew_definition: Path,
        mock_router: MagicMock,
    ) -> None:
        crew = Crew(crew_definition, router=mock_router)
        assert crew.name == "test-crew"
        assert len(crew.definition.agents) == 2

    def test_init_validates_agents(
        self,
        tmp_path: Path,
        mock_router: MagicMock,
    ) -> None:
        """Raises if referenced agent doesn't exist."""
        crew_file = tmp_path / "bad-crew.json"
        crew_file.write_text(json.dumps({
            "schema_version": "1.0.0",
            "name": "bad-crew",
            "agents": ["nonexistent"],
        }))

        with pytest.raises(ValueError, match="Unknown agent 'nonexistent'"):
            Crew(crew_file, router=mock_router)


class TestCrewLifecycle:
    """Tests for crew lifecycle methods."""

    @pytest.mark.asyncio
    async def test_start_runs_hook(
        self,
        crew_definition: Path,
        mock_router: MagicMock,
    ) -> None:
        crew = Crew(crew_definition, router=mock_router)

        with patch.object(crew._hooks, "run", new_callable=AsyncMock) as mock_run:
            await crew.start()
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == "on_start"

    @pytest.mark.asyncio
    async def test_start_idempotent(
        self,
        crew_definition: Path,
        mock_router: MagicMock,
    ) -> None:
        crew = Crew(crew_definition, router=mock_router)

        with patch.object(crew._hooks, "run", new_callable=AsyncMock) as mock_run:
            await crew.start()
            await crew.start()  # Second call
            assert mock_run.call_count == 1  # Only called once

    @pytest.mark.asyncio
    async def test_shutdown_runs_hook(
        self,
        crew_definition: Path,
        mock_router: MagicMock,
    ) -> None:
        crew = Crew(crew_definition, router=mock_router)

        with patch.object(crew._hooks, "run", new_callable=AsyncMock) as mock_run:
            await crew.shutdown()
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == "on_finish"


class TestCrewSubmit:
    """Tests for task submission."""

    @pytest.mark.asyncio
    async def test_submit_success(
        self,
        crew_definition: Path,
        mock_router: MagicMock,
    ) -> None:
        mock_router.invoke.return_value = MAT2Response(
            schema_version="1.2.0",
            correlation_id="test-123",
            idempotency_key="key-123",
            ok=True,
            result={"output": "done"},
        )

        crew = Crew(crew_definition, router=mock_router)
        task = CrewTask(instruction="implement feature", correlation_id="test-123")

        with patch.object(crew._hooks, "run", new_callable=AsyncMock):
            result = await crew.submit(task)

        assert result.ok
        assert result.agent_used == "coder"  # First in round-robin
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_submit_max_tasks_exceeded(
        self,
        crew_definition: Path,
        mock_router: MagicMock,
    ) -> None:
        crew = Crew(crew_definition, router=mock_router)
        crew._task_count = 10  # At the limit

        with patch.object(crew._hooks, "run", new_callable=AsyncMock) as mock_run:
            result = await crew.submit(CrewTask(instruction="test"))

        assert not result.ok
        assert result.error["code"] == "max_tasks_exceeded"
        # on_error hook should have been called
        mock_run.assert_called()
        assert any(call[0][0] == "on_error" for call in mock_run.call_args_list)

    @pytest.mark.asyncio
    async def test_submit_retries_on_timeout(
        self,
        crew_definition: Path,
        mock_router: MagicMock,
    ) -> None:
        # First two calls timeout, third succeeds
        mock_router.invoke.side_effect = [
            MAT2Response(
                schema_version="1.2.0",
                correlation_id="test",
                idempotency_key="key",
                ok=False,
                error={"code": "timeout", "message": "timed out"},
            ),
            MAT2Response(
                schema_version="1.2.0",
                correlation_id="test",
                idempotency_key="key",
                ok=False,
                error={"code": "timeout", "message": "timed out"},
            ),
            MAT2Response(
                schema_version="1.2.0",
                correlation_id="test",
                idempotency_key="key",
                ok=True,
                result={"output": "done"},
            ),
        ]

        crew = Crew(crew_definition, router=mock_router)

        with patch.object(crew._hooks, "run", new_callable=AsyncMock):
            result = await crew.submit(CrewTask(instruction="test"))

        assert result.ok
        assert result.attempts == 3
        assert len(result.retry_reasons) == 2

    @pytest.mark.asyncio
    async def test_submit_no_retry_on_agent_refused(
        self,
        crew_definition: Path,
        mock_router: MagicMock,
    ) -> None:
        mock_router.invoke.return_value = MAT2Response(
            schema_version="1.2.0",
            correlation_id="test",
            idempotency_key="key",
            ok=False,
            error={"code": "agent_refused", "message": "cannot do this"},
        )

        crew = Crew(crew_definition, router=mock_router)

        with patch.object(crew._hooks, "run", new_callable=AsyncMock):
            result = await crew.submit(CrewTask(instruction="test"))

        assert not result.ok
        assert result.attempts == 1  # No retries
        assert result.error["code"] == "agent_refused"


class TestCrewConcurrency:
    """Tests for concurrency control."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(
        self,
        crew_definition: Path,
        mock_router: MagicMock,
    ) -> None:
        import threading
        import time as sync_time

        # Track concurrent executions (thread-safe)
        lock = threading.Lock()
        concurrent_count = 0
        max_concurrent = 0

        def slow_invoke(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            with lock:
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
            sync_time.sleep(0.05)
            with lock:
                concurrent_count -= 1
            return MAT2Response(
                schema_version="1.2.0",
                correlation_id="test",
                idempotency_key="key",
                ok=True,
                result={"output": "done"},
            )

        mock_router.invoke.side_effect = slow_invoke

        crew = Crew(crew_definition, router=mock_router)

        with patch.object(crew._hooks, "run", new_callable=AsyncMock):
            # Submit 5 tasks concurrently
            tasks = [
                crew.submit(CrewTask(instruction=f"task-{i}"))
                for i in range(5)
            ]
            await asyncio.gather(*tasks)

        # max_concurrent_agents is 2 in fixture
        assert max_concurrent <= 2
