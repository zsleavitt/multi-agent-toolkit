"""Hive orchestration class."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from mat_runtime.crew.registry import CrewRegistry
from mat_runtime.crew.types import CrewTask
from mat_runtime.hive.definition import HiveDefinition, load_hive_definition
from mat_runtime.hive.hooks import HookRunner
from mat_runtime.hive.memory import create_hive_memory_store
from mat_runtime.hive.routing import (
    create_routing_strategy,
    dependencies_satisfied,
    evaluate_handoff,
    get_crew_entry,
)
from mat_runtime.hive.types import (
    CrewStageResult,
    HiveResult,
    HiveSession,
    HiveTask,
)


def _find_repo_root(start_path: Path) -> Path:
    """Find repository root by walking up from start_path."""
    markers = {".git", "CLAUDE.md", "pyproject.toml", "setup.py", "ai-team.repo.json"}
    current = start_path.resolve()

    for _ in range(20):
        for marker in markers:
            if (current / marker).exists():
                return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    return start_path.resolve()


class Hive:
    """
    Top-level orchestrator managing multiple Crews with inter-crew routing.

    Loads a hive definition, resolves crew references via CrewRegistry,
    and routes tasks across crews with session tracking and global limits.
    """

    def __init__(
        self,
        definition_path: str | Path | None = None,
        *,
        definition: HiveDefinition | None = None,
        repo_root: str | Path | None = None,
        crew_registry: CrewRegistry | None = None,
    ):
        if definition is not None:
            self._definition = definition
        elif definition_path is not None:
            path = Path(definition_path)
            root = repo_root or _find_repo_root(path.parent)
            self._definition = load_hive_definition(path, repo_root=root)
        else:
            raise ValueError("Either definition_path or definition must be provided")

        if repo_root:
            self._repo_root = Path(repo_root).resolve()
        elif definition_path is not None:
            self._repo_root = _find_repo_root(Path(definition_path).parent)
        elif self._definition.source_path is not None:
            self._repo_root = _find_repo_root(self._definition.source_path.parent)
        else:
            self._repo_root = Path(".").resolve()

        self._crew_registry = crew_registry or CrewRegistry(repo_root=self._repo_root)
        self._validate_crew_refs()

        self._strategy = create_routing_strategy(
            self._definition.inter_crew_routing.strategy
        )
        self._hooks = HookRunner()
        self._task_count = 0
        self._task_count_lock = asyncio.Lock()
        self._started = False
        self._shutdown = False

        max_concurrent = self._definition.global_config.max_concurrent_crews
        if max_concurrent:
            self._semaphore: asyncio.Semaphore | None = asyncio.Semaphore(
                max_concurrent
            )
        else:
            self._semaphore = None

        shared_memory = self._definition.global_config.shared_memory
        self._memory_store = create_hive_memory_store(
            shared_memory.type,
            path=shared_memory.path,
            ttl_ms=shared_memory.ttl_ms,
            permissions=shared_memory.permissions,
            repo_root=self._repo_root,
        )

    def _validate_crew_refs(self) -> None:
        for entry in self._definition.crews:
            try:
                self._crew_registry.get_definition(entry.ref)
            except ValueError as exc:
                raise ValueError(
                    f"Unknown crew ref '{entry.ref}' in hive "
                    f"'{self._definition.name}'. {exc}"
                ) from exc

    @property
    def name(self) -> str:
        return self._definition.name

    @property
    def definition(self) -> HiveDefinition:
        return self._definition

    async def start(self) -> None:
        """Start the hive and run the on_start hook."""
        if self._started:
            return
        self._started = True
        await self._hooks.run("on_start", {"hive": self._definition.name})

    async def shutdown(self) -> None:
        """Shutdown the hive and run the on_finish hook."""
        if self._shutdown:
            return
        self._shutdown = True
        await self._hooks.run(
            "on_finish",
            {
                "hive": self._definition.name,
                "total_tasks": self._task_count,
            },
        )

    async def submit(self, task: HiveTask) -> HiveResult:
        """
        Submit a task for multi-crew execution.

        Routes the task through crews according to the configured strategy,
        evaluates handoff rules between stages, and returns aggregated results.
        """
        start_time = time.monotonic()
        config = self._definition.global_config
        routing = self._definition.inter_crew_routing

        if self._semaphore:
            await self._semaphore.acquire()

        try:
            async with self._task_count_lock:
                if config.max_tasks and self._task_count >= config.max_tasks:
                    await self._hooks.run(
                        "on_error",
                        {
                            "hive": self._definition.name,
                            "error": "max_tasks_exceeded",
                            "task_id": task.correlation_id,
                        },
                    )
                    return self._error_result(
                        task,
                        start_time,
                        [],
                        code="max_tasks_exceeded",
                        message=(
                            f"Hive reached max_tasks limit ({config.max_tasks})"
                        ),
                    )
                self._task_count += 1
            await self._hooks.run(
                "on_task_assigned",
                {"task_id": task.correlation_id, "hive": self._definition.name},
            )

            session = HiveSession(
                correlation_id=task.correlation_id,
                hive_name=self._definition.name,
                hive_memory_store=self._memory_store,
            )
            execution_order = self._strategy.get_execution_order(
                self._definition,
                task,
            )
            if not execution_order:
                return self._error_result(
                    task,
                    start_time,
                    [],
                    code="no_execution_path",
                    message="No crew execution path for this task",
                )

            stages: list[CrewStageResult] = []
            agent_invocations = 0
            completed_successfully: set[str] = set()
            final_crew: str | None = None

            for index, crew_ref in enumerate(execution_order):
                if self._hive_timeout_exceeded(start_time, config.timeout_ms):
                    return self._error_result(
                        task,
                        start_time,
                        stages,
                        code="hive_timeout",
                        message="Hive-level timeout exceeded",
                        agent_invocations=agent_invocations,
                        final_crew=final_crew,
                    )

                entry = get_crew_entry(self._definition, crew_ref)
                if not dependencies_satisfied(entry, completed_successfully):
                    break

                if index > 0:
                    previous_ref = execution_order[index - 1]
                    previous_result = stages[-1].crew_result
                    if not evaluate_handoff(
                        previous_ref,
                        crew_ref,
                        previous_result,
                        routing,
                    ):
                        break

                stage_result = await self._run_crew_stage(
                    crew_ref,
                    task,
                    session,
                )
                stages.append(stage_result)
                session.stage_results.append(stage_result)
                session.completed_crews.add(crew_ref)
                agent_invocations += stage_result.crew_result.attempts
                final_crew = crew_ref

                if stage_result.crew_result.output is not None:
                    session.shared_context[f"{crew_ref}_output"] = (
                        stage_result.crew_result.output
                    )

                if stage_result.ok:
                    completed_successfully.add(crew_ref)

                if config.quotas.max_agent_invocations is not None:
                    if agent_invocations > config.quotas.max_agent_invocations:
                        await self._hooks.run(
                            "on_error",
                            {
                                "hive": self._definition.name,
                                "error": "max_agent_invocations_exceeded",
                                "task_id": task.correlation_id,
                            },
                        )
                        return self._error_result(
                            task,
                            start_time,
                            stages,
                            code="max_agent_invocations_exceeded",
                            message=(
                                "Hive exceeded max_agent_invocations quota "
                                f"({config.quotas.max_agent_invocations})"
                            ),
                            agent_invocations=agent_invocations,
                            final_crew=final_crew,
                        )

                await self._hooks.run(
                    "on_task_complete",
                    {
                        "task_id": task.correlation_id,
                        "crew": crew_ref,
                        "ok": stage_result.ok,
                    },
                )

                if not stage_result.ok and routing.default_handoff == "on_success":
                    break

            ok = bool(stages) and stages[-1].ok
            return HiveResult(
                ok=ok,
                correlation_id=task.correlation_id,
                stages=stages,
                final_crew=final_crew,
                total_duration_ms=int((time.monotonic() - start_time) * 1000),
                agent_invocations=agent_invocations,
            )

        finally:
            if self._semaphore:
                self._semaphore.release()

    async def _run_crew_stage(
        self,
        crew_ref: str,
        task: HiveTask,
        session: HiveSession,
    ) -> CrewStageResult:
        from mat_runtime.crew.types import CrewResult

        stage_start = time.monotonic()
        crew = self._crew_registry.get_crew(crew_ref)
        await crew.start()
        try:
            crew_task = self._build_crew_task(task, session, crew_ref)
            try:
                result = await crew.submit(crew_task)
            except Exception as exc:
                result = CrewResult(
                    ok=False,
                    agent_used="",
                    output=None,
                    correlation_id=task.correlation_id,
                    duration_ms=int((time.monotonic() - stage_start) * 1000),
                    error={"code": "crew_exception", "message": str(exc)},
                )
        finally:
            await crew.shutdown()

        return CrewStageResult(
            crew_ref=crew_ref,
            ok=result.ok,
            crew_result=result,
            duration_ms=int((time.monotonic() - stage_start) * 1000),
        )

    def _build_crew_task(
        self,
        task: HiveTask,
        session: HiveSession,
        crew_ref: str,
    ) -> CrewTask:
        parts: list[str] = []
        if self._definition.shared_goal:
            parts.append(f"HIVE GOAL: {self._definition.shared_goal}")

        if session.stage_results:
            previous = session.stage_results[-1]
            parts.append(
                f"Previous crew '{previous.crew_ref}' completed with "
                f"ok={previous.ok}."
            )
            output_key = f"{previous.crew_ref}_output"
            if output_key in session.shared_context:
                parts.append(
                    f"Previous output: {session.shared_context[output_key]}"
                )

        parts.append(task.instruction)

        metadata = {**task.metadata, "hive": self._definition.name}
        if session.hive_memory_store is not None:
            metadata["hive_memory"] = session.hive_memory_store.scope_for(crew_ref)

        return CrewTask(
            instruction="\n\n".join(parts),
            op=task.op,
            correlation_id=task.correlation_id,
            required_capabilities=list(task.required_capabilities),
            scope_paths=list(task.scope_paths),
            timeout_ms=task.timeout_ms,
            metadata=metadata,
        )

    @staticmethod
    def _hive_timeout_exceeded(start_time: float, timeout_ms: int | None) -> bool:
        if timeout_ms is None:
            return False
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        return elapsed_ms > timeout_ms

    @staticmethod
    def _error_result(
        task: HiveTask,
        start_time: float,
        stages: list[CrewStageResult],
        *,
        code: str,
        message: str,
        agent_invocations: int = 0,
        final_crew: str | None = None,
    ) -> HiveResult:
        return HiveResult(
            ok=False,
            correlation_id=task.correlation_id,
            stages=stages,
            final_crew=final_crew,
            total_duration_ms=int((time.monotonic() - start_time) * 1000),
            agent_invocations=agent_invocations,
            error={"code": code, "message": message},
        )
