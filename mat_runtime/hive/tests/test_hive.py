"""Tests for Hive orchestration."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mat_runtime.crew.types import CrewResult, CrewTask
from mat_runtime.hive.definition import (
    CrewEntry,
    GlobalConfig,
    HiveDefinition,
    InterCrewRoutingConfig,
    QuotasConfig,
    RoutingRule,
)
from mat_runtime.hive.events import Event, EventBus, EventType
from mat_runtime.hive.hive import Hive
from mat_runtime.hive.types import HiveTask


def _pipeline_definition(
    *,
    max_tasks: int | None = None,
    max_agent_invocations: int | None = None,
) -> HiveDefinition:
    return HiveDefinition(
        name="dev-pipeline",
        shared_goal="Ship with review",
        crews=[
            CrewEntry(ref="dev-crew"),
            CrewEntry(ref="review-crew", depends_on=["dev-crew"], role="review"),
        ],
        global_config=GlobalConfig(
            max_tasks=max_tasks,
            quotas=QuotasConfig(max_agent_invocations=max_agent_invocations),
        ),
        inter_crew_routing=InterCrewRoutingConfig(
            strategy="sequential",
            default_handoff="on_success",
            rules=[
                RoutingRule(
                    from_crew="dev-crew",
                    to_crew="review-crew",
                    when="task_complete",
                    condition="success",
                )
            ],
        ),
    )


def _crew_result(ok: bool, *, attempts: int = 1) -> CrewResult:
    return CrewResult(
        ok=ok,
        agent_used="coder" if ok else "coder",
        output="output" if ok else None,
        correlation_id="test-correlation",
        duration_ms=10,
        attempts=attempts,
        error=None if ok else {"code": "failed"},
    )


@pytest.fixture
def mock_crew_registry() -> MagicMock:
    registry = MagicMock()
    registry.get_definition.return_value = MagicMock()
    return registry


def _mock_crew(submit_results: list[CrewResult]) -> MagicMock:
    crew = MagicMock()
    crew.start = AsyncMock()
    crew.shutdown = AsyncMock()
    responses = list(submit_results)

    async def _submit(task: CrewTask) -> CrewResult:
        if not responses:
            raise AssertionError("Unexpected crew.submit call")
        return responses.pop(0)

    crew.submit = AsyncMock(side_effect=_submit)
    return crew


class TestHiveSubmit:
    def test_dev_pipeline_handoff_on_success(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        asyncio.run(self._test_dev_pipeline_handoff_on_success(mock_crew_registry))

    async def _test_dev_pipeline_handoff_on_success(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        dev_crew = _mock_crew([_crew_result(True)])
        review_crew = _mock_crew([_crew_result(True)])

        def get_crew(name: str) -> MagicMock:
            return dev_crew if name == "dev-crew" else review_crew

        mock_crew_registry.get_crew.side_effect = get_crew

        hive = Hive(
            definition=_pipeline_definition(),
            repo_root="/tmp",
            crew_registry=mock_crew_registry,
        )
        await hive.start()

        try:
            result = await hive.submit(HiveTask(instruction="Implement feature"))
        finally:
            await hive.shutdown()

        assert result.ok is True
        assert len(result.stages) == 2
        assert result.stages[0].crew_ref == "dev-crew"
        assert result.stages[1].crew_ref == "review-crew"
        assert result.final_crew == "review-crew"
        assert result.agent_invocations == 2
        dev_crew.submit.assert_called_once()
        review_crew.submit.assert_called_once()

    def test_pipeline_stops_on_dev_failure(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        asyncio.run(self._test_pipeline_stops_on_dev_failure(mock_crew_registry))

    async def _test_pipeline_stops_on_dev_failure(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        dev_crew = _mock_crew([_crew_result(False)])
        review_crew = _mock_crew([_crew_result(True)])
        mock_crew_registry.get_crew.side_effect = lambda name: (
            dev_crew if name == "dev-crew" else review_crew
        )

        hive = Hive(
            definition=_pipeline_definition(),
            repo_root="/tmp",
            crew_registry=mock_crew_registry,
        )
        await hive.start()

        try:
            result = await hive.submit(HiveTask(instruction="Implement feature"))
        finally:
            await hive.shutdown()

        assert result.ok is False
        assert len(result.stages) == 1
        assert result.stages[0].crew_ref == "dev-crew"
        review_crew.submit.assert_not_called()

    def test_max_tasks_enforced(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        asyncio.run(self._test_max_tasks_enforced(mock_crew_registry))

    async def _test_max_tasks_enforced(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        dev_crew = _mock_crew([_crew_result(True)])
        review_crew = _mock_crew([_crew_result(True)])
        mock_crew_registry.get_crew.side_effect = lambda name: (
            dev_crew if name == "dev-crew" else review_crew
        )

        hive = Hive(
            definition=_pipeline_definition(max_tasks=1),
            repo_root="/tmp",
            crew_registry=mock_crew_registry,
        )
        await hive.start()

        try:
            first = await hive.submit(HiveTask(instruction="first"))
            second = await hive.submit(HiveTask(instruction="second"))
        finally:
            await hive.shutdown()

        assert first.ok is True
        assert len(first.stages) == 2
        assert second.ok is False
        assert second.error is not None
        assert second.error["code"] == "max_tasks_exceeded"

    def test_quota_enforced(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        asyncio.run(self._test_quota_enforced(mock_crew_registry))

    async def _test_quota_enforced(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        dev_crew = _mock_crew([_crew_result(True, attempts=2)])
        mock_crew_registry.get_crew.return_value = dev_crew

        hive = Hive(
            definition=_pipeline_definition(max_agent_invocations=1),
            repo_root="/tmp",
            crew_registry=mock_crew_registry,
        )
        await hive.start()

        try:
            result = await hive.submit(HiveTask(instruction="task"))
        finally:
            await hive.shutdown()

        assert result.ok is False
        assert result.error is not None
        assert result.error["code"] == "max_agent_invocations_exceeded"

    def test_shared_goal_injected_into_crew_task(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        asyncio.run(
            self._test_shared_goal_injected_into_crew_task(mock_crew_registry)
        )

    async def _test_shared_goal_injected_into_crew_task(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        captured: list[CrewTask] = []
        dev_crew = _mock_crew([_crew_result(True)])
        review_crew = _mock_crew([_crew_result(True)])

        async def capture_submit(task: CrewTask) -> CrewResult:
            captured.append(task)
            return _crew_result(True)

        dev_crew.submit = AsyncMock(side_effect=capture_submit)
        review_crew.submit = AsyncMock(side_effect=capture_submit)
        mock_crew_registry.get_crew.side_effect = lambda name: (
            dev_crew if name == "dev-crew" else review_crew
        )

        hive = Hive(
            definition=_pipeline_definition(),
            repo_root="/tmp",
            crew_registry=mock_crew_registry,
        )
        await hive.start()
        try:
            await hive.submit(HiveTask(instruction="Do work"))
        finally:
            await hive.shutdown()

        assert "HIVE GOAL: Ship with review" in captured[0].instruction
        assert "Do work" in captured[0].instruction

    def test_start_and_shutdown_hooks_called(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        asyncio.run(
            self._test_start_and_shutdown_hooks_called(mock_crew_registry)
        )

    async def _test_start_and_shutdown_hooks_called(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        dev_crew = _mock_crew([_crew_result(True)])
        review_crew = _mock_crew([_crew_result(True)])
        mock_crew_registry.get_crew.side_effect = lambda name: (
            dev_crew if name == "dev-crew" else review_crew
        )

        hive = Hive(
            definition=_pipeline_definition(),
            repo_root="/tmp",
            crew_registry=mock_crew_registry,
        )

        with patch.object(hive._hooks, "run", new_callable=AsyncMock) as mock_run:
            await hive.start()
            await hive.submit(HiveTask(instruction="task"))
            await hive.shutdown()

            hook_names = [call.args[0] for call in mock_run.call_args_list]
            assert "on_start" in hook_names
            assert "on_task_assigned" in hook_names
            assert "on_task_complete" in hook_names
            assert "on_finish" in hook_names

    def test_emits_crew_events_to_event_bus(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        asyncio.run(self._test_emits_crew_events_to_event_bus(mock_crew_registry))

    async def _test_emits_crew_events_to_event_bus(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        dev_crew = _mock_crew([_crew_result(True)])
        review_crew = _mock_crew([_crew_result(True)])
        mock_crew_registry.get_crew.side_effect = lambda name: (
            dev_crew if name == "dev-crew" else review_crew
        )

        events: list[Event] = []
        bus = EventBus()

        class _Recorder:
            def handle(self, event: Event) -> None:
                events.append(event)

        bus.subscribe(_Recorder())

        hive = Hive(
            definition=_pipeline_definition(),
            repo_root="/tmp",
            crew_registry=mock_crew_registry,
            event_bus=bus,
        )
        await hive.start()
        try:
            await hive.submit(HiveTask(instruction="Implement feature"))
        finally:
            await hive.shutdown()

        started = [e for e in events if e.event_type == EventType.CREW_STARTED]
        completed = [e for e in events if e.event_type == EventType.CREW_COMPLETED]

        assert [e.crew for e in started] == ["dev-crew", "review-crew"]
        assert [e.crew for e in completed] == ["dev-crew", "review-crew"]
        assert all(e.outcome["ok"] is True for e in completed)
        assert all(e.duration_ms is not None for e in completed)

    def test_no_crew_started_event_when_start_raises(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        asyncio.run(
            self._test_no_crew_started_event_when_start_raises(mock_crew_registry)
        )

    async def _test_no_crew_started_event_when_start_raises(
        self,
        mock_crew_registry: MagicMock,
    ) -> None:
        failing_crew = MagicMock()
        failing_crew.start = AsyncMock(side_effect=RuntimeError("startup failed"))
        failing_crew.shutdown = AsyncMock()
        mock_crew_registry.get_crew.return_value = failing_crew

        events: list[Event] = []
        bus = EventBus()

        class _Recorder:
            def handle(self, event: Event) -> None:
                events.append(event)

        bus.subscribe(_Recorder())

        hive = Hive(
            definition=_pipeline_definition(),
            repo_root="/tmp",
            crew_registry=mock_crew_registry,
            event_bus=bus,
        )
        await hive.start()
        try:
            with pytest.raises(Exception):
                await hive.submit(HiveTask(instruction="Implement feature"))
        finally:
            await hive.shutdown()

        # crew.start() raised before CREW_STARTED was emitted — no events at all.
        assert events == []
