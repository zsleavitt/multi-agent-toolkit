# mat_runtime/swarm/swarm.py
"""Swarm orchestration class."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from mat_runtime.adapters import ADAPTER_REGISTRY, CLIAdapter, get_adapter
from mat_runtime.config import AgentDefinition, load_agent_definitions
from mat_runtime.router import AgentRouter, MAT2Request
from mat_runtime.swarm.definition import SwarmDefinition, load_swarm_definition
from mat_runtime.swarm.types import CandidateResult, SwarmResult, SwarmTask


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


class Swarm:
    """
    Dispatches tasks to multiple CLI adapters in parallel.

    Loads a swarm definition, creates adapters for each candidate,
    and applies consensus strategy to results.
    """

    def __init__(
        self,
        definition_path: str | Path,
        repo_root: str | Path | None = None,
    ):
        """
        Initialize Swarm from definition file.

        Args:
            definition_path: Path to swarm definition JSON.
            repo_root: Repository root for CLI invocations.
                Defaults to definition file's parent (auto-detects repo root).

        Raises:
            ValueError: If any candidate is not valid for the dispatch mode.
                - parallel_model: candidates must be registered CLI adapters.
                - variant: candidates must be known agent definitions.
        """
        self._definition = load_swarm_definition(definition_path)
        if repo_root:
            self._repo_root = Path(repo_root).resolve()
        else:
            # Auto-detect repo root by walking up from definition file
            self._repo_root = _find_repo_root(Path(definition_path).parent)

        # Initialize based on dispatch mode
        self._adapters: dict[str, CLIAdapter] = {}
        self._agents: dict[str, AgentDefinition] = {}
        self._router: AgentRouter | None = None

        if self._definition.dispatch_mode == "parallel_model":
            self._init_parallel_model()
        elif self._definition.dispatch_mode == "variant":
            self._init_variant()

    def _init_parallel_model(self) -> None:
        """Initialize for parallel_model dispatch mode."""
        # Validate all candidates are registered adapters
        for candidate in self._definition.candidates:
            if candidate not in ADAPTER_REGISTRY:
                raise ValueError(
                    f"Unknown CLI adapter '{candidate}'. "
                    f"Available: {', '.join(sorted(ADAPTER_REGISTRY.keys()))}"
                )

        # Create adapters
        for candidate in self._definition.candidates:
            self._adapters[candidate] = get_adapter(
                cli=candidate,
                working_dir=str(self._repo_root),
            )

    def _init_variant(self) -> None:
        """Initialize for variant dispatch mode."""
        self._agents = load_agent_definitions(repo_root=self._repo_root)

        # Validate all candidates are known agents
        for candidate in self._definition.candidates:
            if candidate not in self._agents:
                available = ", ".join(sorted(self._agents.keys()))
                raise ValueError(
                    f"Unknown agent variant '{candidate}'. "
                    f"Available agents: {available if available else '(none found)'}"
                )

        self._router = AgentRouter(repo_root=self._repo_root, agents=self._agents)

    @property
    def name(self) -> str:
        """Swarm name."""
        return self._definition.name

    @property
    def definition(self) -> SwarmDefinition:
        """Swarm definition."""
        return self._definition

    async def dispatch(self, task: SwarmTask) -> SwarmResult:
        """
        Dispatch task to all candidates in parallel.

        Sends the same instruction to all CLI adapters concurrently,
        waits for all to complete, and applies consensus strategy.

        Args:
            task: The task to dispatch.

        Returns:
            SwarmResult with consensus output and all candidate results.
        """
        start_time = time.monotonic()

        # Dispatch to all candidates
        coros = [
            self._invoke_candidate(candidate, task)
            for candidate in self._definition.candidates
        ]
        results = await asyncio.gather(*coros, return_exceptions=True)

        # Convert any exceptions to CandidateResult (safety net)
        candidate_results: list[CandidateResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                candidate_results.append(
                    CandidateResult(
                        candidate=self._definition.candidates[i],
                        ok=False,
                        response=None,
                        duration_ms=0,
                        error=str(result),
                    )
                )
            else:
                candidate_results.append(result)

        total_duration_ms = int((time.monotonic() - start_time) * 1000)
        return self._apply_consensus(candidate_results, task, total_duration_ms)

    async def _invoke_candidate(
        self,
        candidate: str,
        task: SwarmTask,
    ) -> CandidateResult:
        """
        Invoke a single candidate.

        Routes to appropriate method based on dispatch_mode.
        Never raises - catches all exceptions and returns CandidateResult
        with ok=False and error message.
        """
        if self._definition.dispatch_mode == "parallel_model":
            return await self._invoke_adapter(candidate, task)
        else:
            return await self._invoke_variant(candidate, task)

    async def _invoke_adapter(
        self,
        candidate: str,
        task: SwarmTask,
    ) -> CandidateResult:
        """
        Invoke a CLI adapter candidate (parallel_model mode).

        Never raises - catches all exceptions and returns CandidateResult
        with ok=False and error message.
        """
        start = time.monotonic()
        try:
            timeout = (
                task.timeout_ms
                if task.timeout_ms is not None
                else self._definition.constraints.timeout_ms
            )
            # Include op in prompt for operation-aware dispatch
            prompt = f"[op: {task.op}]\n\n{task.instruction}"
            response = await asyncio.to_thread(
                self._adapters[candidate].invoke,
                prompt=prompt,
                timeout_ms=timeout,
                correlation_id=task.correlation_id,
            )
            return CandidateResult(
                candidate=candidate,
                ok=response.ok,
                response=response,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            return CandidateResult(
                candidate=candidate,
                ok=False,
                response=None,
                duration_ms=int((time.monotonic() - start) * 1000),
                error=str(e),
            )

    async def _invoke_variant(
        self,
        candidate: str,
        task: SwarmTask,
    ) -> CandidateResult:
        """
        Invoke an agent variant candidate (variant mode).

        Never raises - catches all exceptions and returns CandidateResult
        with ok=False and error message.
        """
        start = time.monotonic()
        try:
            timeout = (
                task.timeout_ms
                if task.timeout_ms is not None
                else self._definition.constraints.timeout_ms
            )

            request = MAT2Request(
                schema_version="1.0.0",
                correlation_id=task.correlation_id,
                idempotency_key=task.correlation_id,
                op=task.op,
                repo_root=str(self._repo_root),
                instruction=task.instruction,
                timeout_ms=timeout,
            )

            response = await asyncio.to_thread(
                self._router.invoke,
                agent_name=candidate,
                request=request,
            )

            return CandidateResult(
                candidate=candidate,
                ok=response.ok,
                response=None,
                duration_ms=int((time.monotonic() - start) * 1000),
                error=response.error.get("message") if response.error else None,
                variant_output=response.result if response.ok else None,
            )
        except Exception as e:
            return CandidateResult(
                candidate=candidate,
                ok=False,
                response=None,
                duration_ms=int((time.monotonic() - start) * 1000),
                error=str(e),
                variant_output=None,
            )

    def _apply_consensus(
        self,
        results: list[CandidateResult],
        task: SwarmTask,
        total_duration_ms: int,
    ) -> SwarmResult:
        """
        Apply consensus strategy to candidate results.

        Routes to appropriate method based on consensus_strategy.
        """
        if self._definition.consensus_strategy == "return-all":
            return self._apply_return_all_consensus(results, task, total_duration_ms)
        else:
            return self._apply_first_complete_consensus(results, task, total_duration_ms)

    def _apply_first_complete_consensus(
        self,
        results: list[CandidateResult],
        task: SwarmTask,
        total_duration_ms: int,
    ) -> SwarmResult:
        """
        Apply first-complete consensus (parallel_model mode).

        - Sort by duration_ms (completion order)
        - Return first where ok == True
        - If all failed, aggregate errors
        """
        # Sort by completion time
        sorted_results = sorted(results, key=lambda r: r.duration_ms)

        # Find first success
        for result in sorted_results:
            if result.ok:
                return SwarmResult(
                    ok=True,
                    consensus_strategy=self._definition.consensus_strategy,
                    winning_candidate=result.candidate,
                    output=result.response.stdout if result.response else None,
                    correlation_id=task.correlation_id,
                    duration_ms=total_duration_ms,
                    candidate_results=results,
                )

        # All failed - aggregate errors
        errors = []
        for result in results:
            if result.error:
                errors.append(f"{result.candidate}: {result.error}")
            elif result.response:
                errors.append(f"{result.candidate}: {result.response.stderr}")
            else:
                errors.append(f"{result.candidate}: unknown error")

        return SwarmResult(
            ok=False,
            consensus_strategy=self._definition.consensus_strategy,
            winning_candidate=None,
            output=None,
            correlation_id=task.correlation_id,
            duration_ms=total_duration_ms,
            candidate_results=results,
            error={
                "code": "all_candidates_failed",
                "message": "All candidates failed",
                "details": errors,
            },
        )

    def _apply_return_all_consensus(
        self,
        results: list[CandidateResult],
        task: SwarmTask,
        total_duration_ms: int,
    ) -> SwarmResult:
        """
        Apply return-all consensus (variant mode).

        Collects ALL variant outputs into a dict keyed by candidate name.
        - ok=True if ANY candidate succeeded
        - winning_candidate=None (no winner in return-all mode)
        - output is dict of all results: {candidate: {"ok": bool, "output": ..., "duration_ms": int}}
        """
        outputs: dict[str, Any] = {}
        any_ok = False

        for result in results:
            if result.ok:
                any_ok = True
                outputs[result.candidate] = {
                    "ok": True,
                    "output": result.variant_output,
                    "duration_ms": result.duration_ms,
                }
            else:
                outputs[result.candidate] = {
                    "ok": False,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                }

        return SwarmResult(
            ok=any_ok,
            consensus_strategy=self._definition.consensus_strategy,
            winning_candidate=None,
            output=outputs,
            correlation_id=task.correlation_id,
            duration_ms=total_duration_ms,
            candidate_results=results,
            error=None if any_ok else {
                "code": "all_variants_failed",
                "message": "All agent variants failed",
            },
        )
