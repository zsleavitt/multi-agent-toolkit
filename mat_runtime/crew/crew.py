"""Crew orchestration class."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from mat_runtime.crew.context import create_context_store


def _find_repo_root(start_path: Path) -> Path:
    """
    Find the repository root by walking up from start_path.

    Looks for common repo markers: .git, CLAUDE.md, pyproject.toml, setup.py.
    Falls back to start_path if no marker found.
    """
    markers = {".git", "CLAUDE.md", "pyproject.toml", "setup.py", "ai-team.repo.json"}
    current = start_path.resolve()

    for _ in range(20):  # Limit search depth
        for marker in markers:
            if (current / marker).exists():
                return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    return start_path.resolve()
from mat_runtime.crew.definition import (
    AgentRef,
    CrewDefinition,
    load_crew_definition,
)
from mat_runtime.crew.hooks import HookRunner
from mat_runtime.crew.routing import (
    RoutingState,
    RoutingStrategy,
    create_routing_strategy,
)
from mat_runtime.crew.types import CrewTask, CrewResult
from mat_runtime.router import AgentRouter, MAT2Request, MAT2Response


# Error codes that are retryable (infrastructure failures)
RETRYABLE_ERRORS = {"timeout", "execution_error"}


class Crew:
    """
    Orchestrates task execution across a collection of agents.

    Loads a crew definition, resolves agent references, and routes
    tasks to agents with configurable strategies, constraints, and hooks.
    """

    def __init__(
        self,
        definition_path: str | Path | None = None,
        *,
        definition: CrewDefinition | None = None,
        repo_root: str | Path | None = None,
        router: AgentRouter | None = None,
    ):
        """
        Initialize a Crew from a definition file or in-memory definition.

        Args:
            definition_path: Path to the crew definition JSON file.
            definition: Pre-loaded crew definition (optional).
            repo_root: Repository root. Defaults to definition file's parent.
            router: AgentRouter instance. Created if not provided.

        Raises:
            ValueError: If any referenced agent is unknown, or neither
                definition_path nor definition is provided.
        """
        if definition is not None:
            self._definition = definition
        elif definition_path is not None:
            self._definition = load_crew_definition(definition_path)
        else:
            raise ValueError("Either definition_path or definition must be provided")

        if repo_root:
            self._repo_root = Path(repo_root).resolve()
        elif definition_path is not None:
            # Auto-detect repo root by walking up from definition file
            self._repo_root = _find_repo_root(Path(definition_path).parent)
        elif self._definition.source_path is not None:
            self._repo_root = _find_repo_root(self._definition.source_path.parent)
        else:
            self._repo_root = Path(".").resolve()

        # Initialize router and validate agents exist
        self._router = router or AgentRouter(repo_root=self._repo_root)
        self._validate_agents()

        # Initialize routing strategy
        agent_defs = {
            name: {"specialization": agent.specialization}
            for name, agent in self._router.agents.items()
        }
        self._strategy = create_routing_strategy(
            strategy=self._definition.routing.strategy,
            agent_definitions=agent_defs,
            match_on=self._definition.routing.match_on,
            fallback=self._definition.routing.fallback,
        )

        # Initialize context store
        self._context = create_context_store(
            store_type=self._definition.communication.shared_context_type,
            path=self._definition.communication.shared_context_path,
            ttl_ms=self._definition.communication.shared_context_ttl_ms,
        )

        # Initialize hooks
        self._hooks = HookRunner(
            config=self._definition.hooks,
            repo_root=self._repo_root,
        )

        # Initialize state
        self._routing_state = RoutingState()
        self._task_count = 0
        self._busy_agents: set[str] = set()
        self._started = False
        self._shutdown = False

        # Initialize semaphore for concurrency control
        max_concurrent = self._definition.constraints.max_concurrent_agents
        if max_concurrent:
            self._semaphore: asyncio.Semaphore | None = asyncio.Semaphore(max_concurrent)
        else:
            self._semaphore = None

    def _validate_agents(self) -> None:
        """Validate all referenced agents exist."""
        for agent_ref in self._definition.agents:
            if not self._router.find_agent(agent_ref.name):
                raise ValueError(
                    f"Unknown agent '{agent_ref.name}' in crew '{self._definition.name}'. "
                    f"Valid agents: {sorted(self._router.agents.keys())}"
                )

    @property
    def name(self) -> str:
        """Crew name."""
        return self._definition.name

    @property
    def definition(self) -> CrewDefinition:
        """Crew definition."""
        return self._definition

    @property
    def context(self) -> ContextStore:
        """Shared context store."""
        return self._context

    async def start(self) -> None:
        """
        Start the crew and run the on_start hook.

        Should be called before submitting tasks.
        """
        if self._started:
            return

        self._started = True
        await self._hooks.run("on_start", {"crew": self._definition.name})

    async def shutdown(self) -> None:
        """
        Shutdown the crew and run the on_finish hook.

        Should be called after all tasks are complete.
        """
        if self._shutdown:
            return

        self._shutdown = True
        await self._hooks.run(
            "on_finish",
            {
                "crew": self._definition.name,
                "total_tasks": self._task_count,
            },
        )

    async def submit(self, task: CrewTask) -> CrewResult:
        """
        Submit a task for execution.

        Selects an agent, executes with retry logic, and returns result.

        Args:
            task: The task to execute.

        Returns:
            CrewResult with execution outcome.
        """
        start_time = time.monotonic()
        constraints = self._definition.constraints

        # Acquire semaphore if configured
        if self._semaphore:
            await self._semaphore.acquire()

        try:
            # Check max_tasks constraint (inside semaphore to prevent race)
            if constraints.max_tasks and self._task_count >= constraints.max_tasks:
                await self._hooks.run(
                    "on_error",
                    {
                        "crew": self._definition.name,
                        "error": "max_tasks_exceeded",
                        "task_id": task.correlation_id,
                    },
                )
                return CrewResult(
                    ok=False,
                    agent_used="",
                    output=None,
                    correlation_id=task.correlation_id,
                    duration_ms=int((time.monotonic() - start_time) * 1000),
                    error={
                        "code": "max_tasks_exceeded",
                        "message": f"Crew reached max_tasks limit ({constraints.max_tasks})",
                    },
                )

            # Run on_task_assigned hook (inside semaphore)
            await self._hooks.run(
                "on_task_assigned",
                {"task_id": task.correlation_id},
            )

            # Select agent with prefer_idle pre-filter
            candidates = list(self._definition.agents)
            if self._definition.routing.prefer_idle and self._busy_agents:
                idle = [a for a in candidates if a.name not in self._busy_agents]
                if idle:
                    candidates = idle

            selected = self._strategy.select(candidates, task, self._routing_state)

            # Reserve task slot after selection to maintain round-robin order
            # Note: max_tasks check above + semaphore prevents race conditions
            self._task_count += 1
            self._routing_state.task_count = self._task_count

            # Execute with retry loop
            result = await self._execute_with_retry(selected, task)
            self._routing_state.agent_task_counts[selected.name] = (
                self._routing_state.agent_task_counts.get(selected.name, 0) + 1
            )
            self._routing_state.last_agent = selected.name

            # Run completion hook
            await self._hooks.run(
                "on_task_complete",
                {
                    "task_id": task.correlation_id,
                    "agent": selected.name,
                    "ok": result.ok,
                },
            )

            return result

        finally:
            if self._semaphore:
                self._semaphore.release()

    async def _execute_with_retry(
        self,
        agent_ref: AgentRef,
        task: CrewTask,
    ) -> CrewResult:
        """Execute task with retry logic for infrastructure failures."""
        start_time = time.monotonic()
        constraints = self._definition.constraints
        max_retries = constraints.max_retries
        backoff_ms = constraints.backoff_ms
        multiplier = constraints.backoff_multiplier

        attempts = 0
        retry_reasons: list[str] = []

        # Mark agent as busy
        self._busy_agents.add(agent_ref.name)

        try:
            while True:
                attempts += 1

                # Build MAT-2 request
                mat2_request = MAT2Request(
                    schema_version="1.2.0",
                    correlation_id=task.correlation_id,
                    idempotency_key=f"{task.correlation_id}-{attempts}",
                    op=task.op,
                    repo_root=str(self._repo_root),
                    instruction=self._build_instruction(task),
                    scope_paths=task.scope_paths,
                    timeout_ms=agent_ref.timeout_ms or task.timeout_ms,
                )

                # Invoke agent (in thread to avoid blocking event loop)
                response = await asyncio.to_thread(
                    self._router.invoke,
                    agent_ref.name,
                    mat2_request,
                )

                # Success
                if response.ok:
                    return CrewResult(
                        ok=True,
                        agent_used=agent_ref.name,
                        output=response.result,
                        correlation_id=task.correlation_id,
                        duration_ms=int((time.monotonic() - start_time) * 1000),
                        attempts=attempts,
                        retry_reasons=retry_reasons,
                    )

                # Check if error is retryable
                error_code = (response.error or {}).get("code", "unknown")
                is_retryable = error_code in RETRYABLE_ERRORS

                if not is_retryable or attempts > max_retries:
                    # Non-retryable or retries exhausted
                    await self._hooks.run(
                        "on_agent_failure",
                        {
                            "task_id": task.correlation_id,
                            "agent": agent_ref.name,
                            "error": error_code,
                            "attempts": attempts,
                        },
                    )

                    return CrewResult(
                        ok=False,
                        agent_used=agent_ref.name,
                        output=None,
                        correlation_id=task.correlation_id,
                        duration_ms=int((time.monotonic() - start_time) * 1000),
                        attempts=attempts,
                        retry_reasons=retry_reasons,
                        error=response.error,
                    )

                # Retryable - add to reasons and backoff
                retry_reasons.append(f"Attempt {attempts}: {error_code}")
                await asyncio.sleep(backoff_ms / 1000)
                backoff_ms = int(backoff_ms * multiplier)

        finally:
            self._busy_agents.discard(agent_ref.name)

    def _build_instruction(self, task: CrewTask) -> str:
        """Build the full instruction with shared_goal if configured."""
        parts = []
        if self._definition.shared_goal:
            parts.append(f"CREW GOAL: {self._definition.shared_goal}")
        parts.append(task.instruction)
        return "\n\n".join(parts)
