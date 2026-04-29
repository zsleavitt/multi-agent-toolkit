# mat_runtime/swarm/swarm.py
"""Swarm orchestration class."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from mat_runtime.adapters import ADAPTER_REGISTRY, get_adapter
from mat_runtime.providers import AgentInvocationProvider
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
        self._adapters: dict[str, AgentInvocationProvider] = {}
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

        # Validate all candidates are known agents AND are actual variants
        for candidate in self._definition.candidates:
            if candidate not in self._agents:
                available = ", ".join(sorted(self._agents.keys()))
                raise ValueError(
                    f"Unknown agent variant '{candidate}'. "
                    f"Available agents: {available if available else '(none found)'}"
                )
            agent_def = self._agents[candidate]
            if not agent_def.variant_of:
                raise ValueError(
                    f"Candidate '{candidate}' is not a variant agent (missing variant_of). "
                    f"dispatch_mode 'variant' requires all candidates to be agent variants. "
                    f"Found base agent. Use a variant like 'python-engineer' instead of 'coder'."
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
            invoke_kw: dict[str, Any] = {}
            model_hint = self._definition.model_matrix.get(candidate)
            if model_hint:
                invoke_kw["model"] = model_hint
            response = await asyncio.to_thread(
                self._adapters[candidate].invoke,
                prompt=prompt,
                timeout_ms=timeout,
                correlation_id=task.correlation_id,
                **invoke_kw,
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
            timeout_ms = (
                task.timeout_ms
                if task.timeout_ms is not None
                else self._definition.constraints.timeout_ms
            )
            timeout_s = (timeout_ms / 1000) if timeout_ms else None

            request = MAT2Request(
                schema_version="1.0.0",
                correlation_id=task.correlation_id,
                idempotency_key=task.correlation_id,
                op=task.op,
                repo_root=str(self._repo_root),
                instruction=task.instruction,
                timeout_ms=timeout_ms,
            )

            # Wrap with asyncio.wait_for to enforce hard timeout ceiling
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._router.invoke,
                    agent_name=candidate,
                    request=request,
                ),
                timeout=timeout_s,
            )

            return CandidateResult(
                candidate=candidate,
                ok=response.ok,
                response=None,
                duration_ms=int((time.monotonic() - start) * 1000),
                error=response.error if isinstance(response.error, dict) else {"message": str(response.error)} if response.error else None,
                variant_output=response.result if response.ok else None,
            )
        except asyncio.TimeoutError:
            return CandidateResult(
                candidate=candidate,
                ok=False,
                response=None,
                duration_ms=int((time.monotonic() - start) * 1000),
                error={"code": "timeout", "message": f"Candidate '{candidate}' exceeded timeout"},
                variant_output=None,
            )
        except Exception as e:
            return CandidateResult(
                candidate=candidate,
                ok=False,
                response=None,
                duration_ms=int((time.monotonic() - start) * 1000),
                error={"code": "exception", "message": str(e)},
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
        Apply return-all consensus (variant or parallel_model mode).

        Collects ALL outputs into a dict keyed by candidate name.
        - ok=True if ANY candidate succeeded
        - winning_candidate=None (no winner in return-all mode)
        - output is dict of all results: {candidate: {"ok": bool, "output": ..., "duration_ms": int}}

        For variant mode, output comes from variant_output.
        For parallel_model mode, output comes from response.stdout.
        """
        outputs: dict[str, Any] = {}
        any_ok = False
        is_variant_mode = self._definition.dispatch_mode == "variant"

        for result in results:
            if result.ok:
                any_ok = True
                # Extract output based on dispatch mode
                if is_variant_mode:
                    output_value = result.variant_output
                else:
                    # parallel_model: use response stdout
                    output_value = result.response.stdout if result.response else None
                outputs[result.candidate] = {
                    "ok": True,
                    "output": output_value,
                    "duration_ms": result.duration_ms,
                }
            else:
                outputs[result.candidate] = {
                    "ok": False,
                    "error": result.error,
                    "duration_ms": result.duration_ms,
                }

        error_code = "all_variants_failed" if is_variant_mode else "all_candidates_failed"
        error_message = "All agent variants failed" if is_variant_mode else "All candidates failed"

        return SwarmResult(
            ok=any_ok,
            consensus_strategy=self._definition.consensus_strategy,
            winning_candidate=None,
            output=outputs,
            correlation_id=task.correlation_id,
            duration_ms=total_duration_ms,
            candidate_results=results,
            error=None if any_ok else {
                "code": error_code,
                "message": error_message,
            },
        )
