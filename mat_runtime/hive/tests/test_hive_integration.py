"""End-to-end integration tests: Hive → Crew → Swarm dispatch chain."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mat_runtime.adapters import InvocationResult
from mat_runtime.config import AgentDefinition
from mat_runtime.crew.registry import CrewRegistry
from mat_runtime.hive.hive import Hive
from mat_runtime.hive.types import HiveTask
from mat_runtime.router import AgentRouter, MAT2Request, MAT2Response
from mat_runtime.swarm import Swarm, SwarmTask


def _make_invocation_result(
    ok: bool,
    stdout: str = "",
    stderr: str = "",
    *,
    timeout_exceeded: bool = False,
) -> InvocationResult:
    return InvocationResult(
        ok=ok,
        stdout=stdout,
        stderr=stderr,
        return_code=0 if ok else 1,
        correlation_id="test-correlation",
        timeout_exceeded=timeout_exceeded,
    )


class SwarmBackedRouter(AgentRouter):
    """
    AgentRouter extension that resolves designated agents through Swarm.dispatch().

    Production glue for crew→swarm routing is not yet in mat_runtime; this bridge
    lets integration tests exercise real Hive and Crew code against real Swarm
    dispatch with mocked CLI adapters.
    """

    def __init__(
        self,
        repo_root: Path | str,
        *,
        agents: dict[str, AgentDefinition],
        swarm_agents: dict[str, Path],
        adapter_factory: Callable[[Swarm], dict[str, MagicMock]] | None = None,
    ):
        super().__init__(repo_root=repo_root, agents=agents)
        self._swarm_agents = swarm_agents
        self._adapter_factory = adapter_factory
        self._swarms: dict[str, Swarm] = {}

    def _get_swarm(self, agent_name: str) -> Swarm:
        if agent_name not in self._swarms:
            swarm_path = self._swarm_agents[agent_name]
            swarm = Swarm(definition_path=swarm_path, repo_root=self.repo_root)
            if self._adapter_factory is not None:
                # _adapters is the internal adapter registry; patched here as a
                # test seam since no public injection API exists yet.
                swarm._adapters = self._adapter_factory(swarm)
            self._swarms[agent_name] = swarm
        return self._swarms[agent_name]

    @staticmethod
    def _mat2_from_swarm(req: MAT2Request, swarm_result) -> MAT2Response:
        if swarm_result.ok:
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=True,
                result={
                    "output": swarm_result.output,
                    "winning_candidate": swarm_result.winning_candidate,
                    "swarm_result": {
                        "consensus_strategy": swarm_result.consensus_strategy,
                        "duration_ms": swarm_result.duration_ms,
                        "candidate_count": len(swarm_result.candidate_results),
                    },
                },
            )

        error = swarm_result.error or {
            "code": "swarm_failed",
            "message": "Swarm dispatch failed",
        }
        return MAT2Response(
            schema_version=req.schema_version,
            correlation_id=req.correlation_id,
            idempotency_key=req.idempotency_key,
            ok=False,
            error=error,
        )

    def invoke(
        self,
        agent_name: str,
        request: MAT2Request | dict | str,
    ) -> MAT2Response:
        # Crew dispatches invoke() via asyncio.to_thread(), so this always runs
        # in a worker thread — asyncio.run() is safe here (no running event loop
        # in the thread).
        if isinstance(request, str):
            req = MAT2Request.from_json(request)
        elif isinstance(request, dict):
            req = MAT2Request.from_dict(request)
        else:
            req = request

        if agent_name not in self._swarm_agents:
            return super().invoke(agent_name, request)

        agent = self.find_agent(agent_name)
        if agent is None:
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

        swarm = self._get_swarm(agent_name)
        task = SwarmTask(
            instruction=req.instruction,
            op=req.op,
            correlation_id=req.correlation_id,
            timeout_ms=req.timeout_ms,
        )
        swarm_result = asyncio.run(swarm.dispatch(task))
        return self._mat2_from_swarm(req, swarm_result)


@pytest.fixture
def integration_env(tmp_path: Path) -> dict:
    """Minimal hive/crew/swarm layout with a swarm-backed crew agent."""
    crews_dir = tmp_path / "crews"
    swarms_dir = tmp_path / "swarms"
    hives_dir = tmp_path / "hives"
    crews_dir.mkdir()
    swarms_dir.mkdir()
    hives_dir.mkdir()

    swarm_path = swarms_dir / "test-swarm.json"
    swarm_path.write_text(
        json.dumps(
            {
                "schema_version": "1.1.0",
                "name": "test-swarm",
                "dispatch_mode": "parallel_model",
                "candidates": ["claude", "codex"],
                "consensus_strategy": "first-complete",
                "constraints": {"timeout_ms": 5000},
            }
        )
    )

    crew_path = crews_dir / "swarm-crew.json"
    crew_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "name": "swarm-crew",
                "agents": ["swarm-worker"],
                "routing": {"strategy": "round-robin"},
                "constraints": {
                    "retry_policy": {
                        "max_retries": 0,
                        "backoff_ms": 1,
                    },
                },
            }
        )
    )

    hive_path = hives_dir / "integration-hive.json"
    hive_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "name": "integration-hive",
                "shared_goal": "Exercise hive crew swarm chain",
                "crews": [{"ref": "swarm-crew"}],
                "global_config": {
                    "timeout_ms": 30000,
                },
                "inter_crew_routing": {
                    "strategy": "sequential",
                    "default_handoff": "on_success",
                },
            }
        )
    )

    agents = {
        "swarm-worker": AgentDefinition(
            name="swarm-worker",
            description="Dispatches through a swarm definition",
            role="worker",
            cli="codex",
        ),
    }

    return {
        "repo_root": tmp_path,
        "hive_path": hive_path,
        "swarm_path": swarm_path,
        "agents": agents,
    }


def _build_hive(
    env: dict,
    adapter_factory: Callable[[Swarm], dict[str, MagicMock]],
    *,
    hive_timeout_ms: int | None = None,
) -> Hive:
    router = SwarmBackedRouter(
        repo_root=env["repo_root"],
        agents=env["agents"],
        swarm_agents={"swarm-worker": env["swarm_path"]},
        adapter_factory=adapter_factory,
    )
    registry = CrewRegistry(
        repo_root=env["repo_root"],
        crews_dir=env["repo_root"] / "crews",
        router=router,
    )
    hive = Hive(
        definition_path=env["hive_path"],
        repo_root=env["repo_root"],
        crew_registry=registry,
    )
    if hive_timeout_ms is not None:
        # _definition.global_config is patched here as a test seam; no public
        # API for overriding timeout post-construction exists yet.
        hive._definition.global_config.timeout_ms = hive_timeout_ms
    return hive


def _fast_codex_adapters(_swarm: Swarm) -> dict[str, MagicMock]:
    mock_claude = MagicMock()
    mock_codex = MagicMock()

    def claude_invoke(**kwargs):
        time.sleep(0.05)
        return _make_invocation_result(ok=True, stdout="claude output")

    def codex_invoke(**kwargs):
        return _make_invocation_result(ok=True, stdout="codex output")

    mock_claude.invoke = claude_invoke
    mock_codex.invoke = codex_invoke
    return {"claude": mock_claude, "codex": mock_codex}


def _failing_adapters(_swarm: Swarm) -> dict[str, MagicMock]:
    mock_claude = MagicMock()
    mock_codex = MagicMock()
    mock_claude.invoke = lambda **kwargs: _make_invocation_result(
        ok=False, stderr="claude failed"
    )
    mock_codex.invoke = lambda **kwargs: _make_invocation_result(
        ok=False, stderr="codex failed"
    )
    return {"claude": mock_claude, "codex": mock_codex}


def _timeout_adapters(_swarm: Swarm) -> dict[str, MagicMock]:
    mock_claude = MagicMock()
    mock_codex = MagicMock()
    mock_claude.invoke = lambda **kwargs: _make_invocation_result(
        ok=False,
        stderr="timed out",
        timeout_exceeded=True,
    )
    mock_codex.invoke = lambda **kwargs: _make_invocation_result(
        ok=False,
        stderr="timed out",
        timeout_exceeded=True,
    )
    return {"claude": mock_claude, "codex": mock_codex}


class TestHiveCrewSwarmIntegration:
    """Full-stack dispatch: Hive.submit → Crew.submit → Swarm.dispatch."""

    def test_happy_path_swarm_result_propagates(
        self,
        integration_env: dict,
    ) -> None:
        hive = _build_hive(integration_env, _fast_codex_adapters)
        correlation_id = "integration-happy-path"

        asyncio.run(hive.start())
        try:
            result = asyncio.run(
                hive.submit(
                    HiveTask(
                        instruction="Implement the feature",
                        correlation_id=correlation_id,
                    )
                )
            )
        finally:
            asyncio.run(hive.shutdown())

        assert result.ok is True
        assert result.correlation_id == correlation_id
        assert len(result.stages) == 1
        assert result.final_crew == "swarm-crew"

        stage = result.stages[0]
        assert stage.crew_ref == "swarm-crew"
        assert stage.ok is True

        crew_result = stage.crew_result
        assert crew_result.ok is True
        assert crew_result.agent_used == "swarm-worker"
        assert crew_result.correlation_id == correlation_id
        assert crew_result.output["output"] == "codex output"
        assert crew_result.output["winning_candidate"] == "codex"
        assert crew_result.output["swarm_result"]["consensus_strategy"] == "first-complete"
        assert crew_result.output["swarm_result"]["candidate_count"] == 2
        assert result.agent_invocations == 1

    def test_crew_failure_propagates_to_hive(
        self,
        integration_env: dict,
    ) -> None:
        hive = _build_hive(integration_env, _failing_adapters)

        asyncio.run(hive.start())
        try:
            result = asyncio.run(hive.submit(HiveTask(instruction="This will fail")))
        finally:
            asyncio.run(hive.shutdown())

        assert result.ok is False
        assert len(result.stages) == 1

        stage = result.stages[0]
        assert stage.ok is False
        assert stage.crew_result.ok is False
        assert stage.crew_result.error is not None
        assert stage.crew_result.error["code"] == "all_candidates_failed"
        assert stage.crew_result.output is None

    def test_adapter_timeout_failure_propagates_to_hive(
        self,
        integration_env: dict,
    ) -> None:
        # Validates that adapter-level failures (timeout_exceeded=True) propagate
        # through swarm → crew → hive as all_candidates_failed. Note: crew-level
        # timeout enforcement is deferred to v2; HiveTask.timeout_ms flows to
        # adapters but is not enforced by the crew or hive layers.
        hive = _build_hive(integration_env, _timeout_adapters)

        asyncio.run(hive.start())
        try:
            result = asyncio.run(
                hive.submit(
                    HiveTask(
                        instruction="Should hit adapter timeouts",
                        timeout_ms=1,
                    )
                )
            )
        finally:
            asyncio.run(hive.shutdown())

        assert result.ok is False
        assert len(result.stages) == 1
        assert result.stages[0].ok is False
        assert result.stages[0].crew_result.error is not None
        assert result.stages[0].crew_result.error["code"] == "all_candidates_failed"

    def test_hive_timeout_before_stage(
        self,
        integration_env: dict,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Hive-level timeout_ms is enforced before starting a crew stage."""
        hive = _build_hive(
            integration_env,
            _fast_codex_adapters,
            hive_timeout_ms=1,
        )
        monkeypatch.setattr(
            Hive,
            "_hive_timeout_exceeded",
            staticmethod(lambda _start, _timeout: True),
        )

        asyncio.run(hive.start())
        try:
            result = asyncio.run(
                hive.submit(HiveTask(instruction="Should time out immediately"))
            )
        finally:
            asyncio.run(hive.shutdown())

        assert result.ok is False
        assert result.error is not None
        assert result.error["code"] == "hive_timeout"
        assert result.stages == []


class TestHiveSharedMemoryIntegration:
    """Cross-crew shared memory flows through Hive.submit."""

    def test_stage_two_reads_value_written_in_stage_one(
        self,
        tmp_path: Path,
    ) -> None:
        asyncio.run(self._test_stage_two_reads_value_written_in_stage_one(tmp_path))

    async def _test_stage_two_reads_value_written_in_stage_one(
        self,
        tmp_path: Path,
    ) -> None:
        from mat_runtime.crew.types import CrewResult, CrewTask
        from mat_runtime.hive.definition import (
            CrewEntry,
            GlobalConfig,
            HiveDefinition,
            InterCrewRoutingConfig,
            SharedMemoryConfig,
        )
        from mat_runtime.hive.hive import Hive
        from mat_runtime.hive.types import HiveTask

        definition = HiveDefinition(
            name="memory-hive",
            crews=[
                CrewEntry(ref="crew-a"),
                CrewEntry(ref="crew-b", depends_on=["crew-a"]),
            ],
            global_config=GlobalConfig(
                shared_memory=SharedMemoryConfig(type="memory"),
            ),
            inter_crew_routing=InterCrewRoutingConfig(
                strategy="sequential",
                default_handoff="on_success",
            ),
        )

        registry = MagicMock()
        registry.get_definition.return_value = MagicMock()

        async def crew_a_submit(task: CrewTask) -> CrewResult:
            memory = task.metadata["hive_memory"]
            await memory.set_global("handoff", "from-crew-a")
            return CrewResult(
                ok=True,
                agent_used="agent-a",
                output={"status": "done"},
                correlation_id=task.correlation_id,
                duration_ms=1,
            )

        async def crew_b_submit(task: CrewTask) -> CrewResult:
            memory = task.metadata["hive_memory"]
            value = await memory.get_global("handoff")
            assert value == "from-crew-a"
            return CrewResult(
                ok=True,
                agent_used="agent-b",
                output={"read": value},
                correlation_id=task.correlation_id,
                duration_ms=1,
            )

        crew_a = MagicMock()
        crew_a.start = AsyncMock()
        crew_a.shutdown = AsyncMock()
        crew_a.submit = AsyncMock(side_effect=crew_a_submit)

        crew_b = MagicMock()
        crew_b.start = AsyncMock()
        crew_b.shutdown = AsyncMock()
        crew_b.submit = AsyncMock(side_effect=crew_b_submit)

        registry.get_crew.side_effect = lambda name: (
            crew_a if name == "crew-a" else crew_b
        )

        hive = Hive(
            definition=definition,
            repo_root=tmp_path,
            crew_registry=registry,
        )
        await hive.start()
        try:
            result = await hive.submit(HiveTask(instruction="Share memory"))
        finally:
            await hive.shutdown()

        assert result.ok is True
        assert len(result.stages) == 2
        assert result.stages[1].crew_result.output == {"read": "from-crew-a"}
        crew_a.submit.assert_called_once()
        crew_b.submit.assert_called_once()
        assert "hive_memory" in crew_a.submit.call_args.args[0].metadata
        assert "hive_memory" in crew_b.submit.call_args.args[0].metadata
