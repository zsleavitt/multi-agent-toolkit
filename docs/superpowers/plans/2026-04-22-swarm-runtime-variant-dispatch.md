> **Note:** Planning document — implementation may differ from the steps described here. See mat_runtime/swarm/ for authoritative code.

# Swarm Runtime: Variant Dispatch Implementation Plan (MAT-47)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Swarm runtime to support `dispatch_mode: "variant"` for dispatching the same task to multiple agent variants in parallel.

**Architecture:** Extend the existing `Swarm` class to handle both dispatch modes. For `variant` mode, use `AgentRouter` to resolve and invoke agent variants instead of direct CLI adapters. The `return-all` consensus strategy collects all variant outputs without selecting a winner.

**Tech Stack:** Python 3.10+, asyncio, dataclasses, pytest

---

## File Structure

| File | Responsibility |
|------|----------------|
| `mat_runtime/swarm/definition.py` | Modify: Accept `dispatch_mode: "variant"` with `return-all` consensus validation |
| `mat_runtime/swarm/swarm.py` | Modify: Add variant dispatch path using AgentRouter, branch by dispatch_mode |
| `mat_runtime/swarm/types.py` | Modify: Add `variant_output` field to `CandidateResult` |
| `mat_runtime/swarm/tests/test_definition.py` | Add: Tests for variant mode definition loading |
| `mat_runtime/swarm/tests/test_swarm.py` | Add: Tests for variant initialization |
| `mat_runtime/swarm/tests/test_swarm_variant.py` | Create: Dedicated variant dispatch tests |
| `mat_runtime/swarm/tests/test_swarm_integration.py` | Create: Integration tests with real agent definitions |

---

### Task 1: Update definition.py to accept variant dispatch_mode

**Files:**
- Modify: `mat_runtime/swarm/definition.py:73-105`
- Modify: `mat_runtime/swarm/tests/test_definition.py`

- [ ] **Step 1: Write failing tests for variant mode acceptance**

Add to `mat_runtime/swarm/tests/test_definition.py`:

```python
class TestVariantDispatchMode:
    """Tests for dispatch_mode: variant."""

    def test_accept_variant_dispatch_mode(self):
        """Accept variant dispatch_mode with return-all consensus."""
        path = _write_definition({
            "schema_version": "1.0.0",
            "name": "variant-swarm",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "ruby-engineer"],
            "consensus_strategy": "return-all",
        })

        definition = load_swarm_definition(path)

        assert definition.dispatch_mode == "variant"
        assert definition.consensus_strategy == "return-all"
        assert definition.candidates == ["python-engineer", "ruby-engineer"]

        path.unlink()

    def test_reject_variant_with_first_complete(self):
        """Reject variant mode with first-complete consensus."""
        path = _write_definition({
            "schema_version": "1.0.0",
            "name": "bad-swarm",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "ruby-engineer"],
            "consensus_strategy": "first-complete",
        })

        with pytest.raises(ValueError, match="return-all"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_parallel_model_with_return_all(self):
        """Reject parallel_model mode with return-all consensus."""
        path = _write_definition({
            "schema_version": "1.0.0",
            "name": "bad-swarm",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "return-all",
        })

        with pytest.raises(ValueError, match="first-complete"):
            load_swarm_definition(path)

        path.unlink()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mat_runtime/swarm/tests/test_definition.py::TestVariantDispatchMode::test_accept_variant_dispatch_mode -v`
Expected: FAIL with "dispatch_mode 'variant' not supported"

- [ ] **Step 3: Update load_swarm_definition to accept variant mode**

Update `mat_runtime/swarm/definition.py` - replace the dispatch_mode validation section:

```python
    # Validate dispatch_mode
    valid_modes = {"parallel_model", "variant"}
    if dispatch_mode not in valid_modes:
        raise ValueError(
            f"dispatch_mode '{dispatch_mode}' not valid. "
            f"Use one of: {', '.join(sorted(valid_modes))}"
        )

    # ... candidates validation ...

    # Validate consensus_strategy based on dispatch_mode
    if dispatch_mode == "parallel_model":
        valid_strategies = {"first-complete", "majority-vote"}
        if consensus_strategy not in valid_strategies:
            raise ValueError(
                f"consensus_strategy '{consensus_strategy}' not valid for parallel_model. "
                f"Use one of: {', '.join(sorted(valid_strategies))}"
            )
        # MAT-46: only first-complete implemented
        if consensus_strategy == "majority-vote":
            raise ValueError(
                "consensus_strategy 'majority-vote' not implemented. "
                "Use 'first-complete'."
            )
    elif dispatch_mode == "variant":
        valid_strategies = {"return-all"}
        if consensus_strategy not in valid_strategies:
            raise ValueError(
                f"consensus_strategy '{consensus_strategy}' not valid for variant mode. "
                f"Use one of: {', '.join(sorted(valid_strategies))}"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest mat_runtime/swarm/tests/test_definition.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add mat_runtime/swarm/definition.py mat_runtime/swarm/tests/test_definition.py
git commit -m "feat(swarm): accept dispatch_mode variant with return-all consensus"
```

---

### Task 2: Add variant_output field to CandidateResult

**Files:**
- Modify: `mat_runtime/swarm/types.py`

- [ ] **Step 1: Write failing test for variant_output field**

Add to `mat_runtime/swarm/tests/test_swarm.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mat_runtime/swarm/tests/test_swarm.py::TestCandidateResultVariant -v`
Expected: FAIL with "unexpected keyword argument 'variant_output'"

- [ ] **Step 3: Add variant_output field to CandidateResult**

Update `mat_runtime/swarm/types.py`:

```python
@dataclass
class CandidateResult:
    """Result from a single candidate in the swarm.

    For parallel_model mode: response contains InvocationResult from CLI adapter.
    For variant mode: variant_output contains the MAT2Response result dict.
    """

    candidate: str  # CLI adapter name or agent variant name
    ok: bool
    response: InvocationResult | None  # Used in parallel_model mode
    duration_ms: int
    error: str | None = None
    variant_output: dict[str, Any] | None = None  # Used in variant mode
```

Add `from typing import Any` to imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest mat_runtime/swarm/tests/test_swarm.py::TestCandidateResultVariant -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mat_runtime/swarm/types.py mat_runtime/swarm/tests/test_swarm.py
git commit -m "feat(swarm): add variant_output field to CandidateResult"
```

---

### Task 3: Add AgentRouter injection to Swarm __init__

**Files:**
- Modify: `mat_runtime/swarm/swarm.py`
- Add tests to: `mat_runtime/swarm/tests/test_swarm.py`

- [ ] **Step 1: Write failing test for Swarm variant mode initialization**

Add to `mat_runtime/swarm/tests/test_swarm.py`:

```python
from unittest.mock import patch
from mat_runtime.config import AgentDefinition


class TestSwarmVariantInit:
    """Tests for Swarm initialization with variant dispatch_mode."""

    def test_accept_variant_candidates_with_router(self):
        """Accept variant swarm when all candidates exist as agents."""
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

        path.unlink()

    def test_reject_unknown_variant_candidate(self):
        """Reject swarm with unknown agent variant."""
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
            ),
        }

        with patch("mat_runtime.swarm.swarm.load_agent_definitions", return_value=mock_agents):
            with pytest.raises(ValueError, match="Unknown agent variant 'unknown-agent'"):
                Swarm(definition_path=path)

        path.unlink()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mat_runtime/swarm/tests/test_swarm.py::TestSwarmVariantInit -v`
Expected: FAIL (variant mode not yet handled)

- [ ] **Step 3: Update Swarm.__init__ to handle variant mode**

Update `mat_runtime/swarm/swarm.py`:

1. Add imports:
```python
from mat_runtime.config import AgentDefinition, load_agent_definitions
from mat_runtime.router import AgentRouter, MAT2Request
```

2. Update `__init__` method to branch by dispatch_mode:
```python
    def __init__(
        self,
        definition_path: str | Path,
        repo_root: str | Path | None = None,
    ):
        self._definition = load_swarm_definition(definition_path)
        if repo_root:
            self._repo_root = Path(repo_root).resolve()
        else:
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
        for candidate in self._definition.candidates:
            if candidate not in ADAPTER_REGISTRY:
                raise ValueError(
                    f"Unknown CLI adapter '{candidate}'. "
                    f"Available: {', '.join(sorted(ADAPTER_REGISTRY.keys()))}"
                )
        for candidate in self._definition.candidates:
            self._adapters[candidate] = get_adapter(
                cli=candidate,
                working_dir=str(self._repo_root),
            )

    def _init_variant(self) -> None:
        """Initialize for variant dispatch mode."""
        self._agents = load_agent_definitions(repo_root=self._repo_root)
        for candidate in self._definition.candidates:
            if candidate not in self._agents:
                available = ", ".join(sorted(self._agents.keys()))
                raise ValueError(
                    f"Unknown agent variant '{candidate}'. "
                    f"Available agents: {available if available else '(none found)'}"
                )
        self._router = AgentRouter(repo_root=self._repo_root, agents=self._agents)
```

- [ ] **Step 4: Run tests to verify initialization passes**

Run: `pytest mat_runtime/swarm/tests/test_swarm.py::TestSwarmVariantInit -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add mat_runtime/swarm/swarm.py mat_runtime/swarm/tests/test_swarm.py
git commit -m "feat(swarm): add variant dispatch mode initialization"
```

---

### Task 4: Implement variant dispatch and return-all consensus

**Files:**
- Modify: `mat_runtime/swarm/swarm.py`
- Create: `mat_runtime/swarm/tests/test_swarm_variant.py`

- [ ] **Step 1: Create test file for variant dispatch**

Create `mat_runtime/swarm/tests/test_swarm_variant.py`:

```python
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
        yield path
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
        assert "Connection failed" in python_result.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest mat_runtime/swarm/tests/test_swarm_variant.py -v`
Expected: FAIL (dispatch methods not implemented)

- [ ] **Step 3: Implement _invoke_candidate branching and _invoke_variant**

Update `mat_runtime/swarm/swarm.py` - update `_invoke_candidate` to branch:

```python
    async def _invoke_candidate(
        self,
        candidate: str,
        task: SwarmTask,
    ) -> CandidateResult:
        """
        Invoke a single candidate.
        Routes to appropriate method based on dispatch_mode.
        """
        if self._definition.dispatch_mode == "parallel_model":
            return await self._invoke_adapter(candidate, task)
        else:
            return await self._invoke_variant(candidate, task)
```

Rename existing `_invoke_candidate` to `_invoke_adapter`, then add `_invoke_variant`:

```python
    async def _invoke_variant(
        self,
        candidate: str,
        task: SwarmTask,
    ) -> CandidateResult:
        """Invoke an agent variant candidate (variant mode)."""
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
```

- [ ] **Step 4: Implement _apply_return_all_consensus**

Update `_apply_consensus` to branch:

```python
    def _apply_consensus(
        self,
        results: list[CandidateResult],
        task: SwarmTask,
        total_duration_ms: int,
    ) -> SwarmResult:
        if self._definition.consensus_strategy == "return-all":
            return self._apply_return_all_consensus(results, task, total_duration_ms)
        else:
            return self._apply_first_complete_consensus(results, task, total_duration_ms)
```

Rename existing implementation to `_apply_first_complete_consensus`, add:

```python
    def _apply_return_all_consensus(
        self,
        results: list[CandidateResult],
        task: SwarmTask,
        total_duration_ms: int,
    ) -> SwarmResult:
        """Apply return-all consensus (variant mode)."""
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
```

- [ ] **Step 5: Run all variant tests**

Run: `pytest mat_runtime/swarm/tests/test_swarm_variant.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add mat_runtime/swarm/swarm.py mat_runtime/swarm/tests/test_swarm_variant.py
git commit -m "feat(swarm): implement variant dispatch with return-all consensus"
```

---

### Task 5: Verify existing parallel_model tests still pass

**Files:**
- Test: `mat_runtime/swarm/tests/test_swarm.py`
- Test: `mat_runtime/swarm/tests/test_definition.py`

- [ ] **Step 1: Run all swarm tests**

Run: `pytest mat_runtime/swarm/tests/ -v`
Expected: All tests PASS (both modes)

- [ ] **Step 2: Commit any fixes if needed**

```bash
git add mat_runtime/swarm/
git commit -m "fix(swarm): ensure parallel_model tests pass with variant support"
```

---

### Task 6: Add integration test with real agent definitions

**Files:**
- Create: `mat_runtime/swarm/tests/test_swarm_integration.py`

- [ ] **Step 1: Write integration test**

Create `mat_runtime/swarm/tests/test_swarm_integration.py`:

```python
"""Integration tests for Swarm with real agent definitions."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from mat_runtime.swarm import Swarm


def _write_definition(data: dict) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


class TestSwarmIntegration:
    """Integration tests with real agent definitions."""

    @pytest.fixture
    def repo_root(self) -> Path:
        current = Path(__file__).resolve()
        while current.parent != current:
            if (current / "agents").is_dir():
                return current
            current = current.parent
        pytest.skip("Could not find repo root with agents/ directory")

    def test_swarm_loads_real_variant_agents(self, repo_root: Path):
        """Swarm can load real variant agent definitions."""
        path = _write_definition({
            "name": "real-variants",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "ruby-engineer"],
            "consensus_strategy": "return-all",
        })

        try:
            swarm = Swarm(definition_path=path, repo_root=repo_root)

            assert swarm.name == "real-variants"
            assert swarm.definition.dispatch_mode == "variant"
            assert "python-engineer" in swarm._agents
            assert "ruby-engineer" in swarm._agents
        finally:
            path.unlink()

    def test_swarm_rejects_nonexistent_variant(self, repo_root: Path):
        """Swarm rejects variants that don't exist in agents/."""
        path = _write_definition({
            "name": "bad-variants",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "nonexistent-agent"],
            "consensus_strategy": "return-all",
        })

        try:
            with pytest.raises(ValueError, match="Unknown agent variant"):
                Swarm(definition_path=path, repo_root=repo_root)
        finally:
            path.unlink()
```

- [ ] **Step 2: Run integration test**

Run: `pytest mat_runtime/swarm/tests/test_swarm_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add mat_runtime/swarm/tests/test_swarm_integration.py
git commit -m "test(swarm): add integration tests with real agent definitions"
```

---

### Task 7: Run full test suite and final verification

**Files:**
- All swarm tests

- [ ] **Step 1: Run full swarm test suite**

Run: `pytest mat_runtime/swarm/tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Run full mat_runtime test suite**

Run: `pytest mat_runtime/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 3: Verify imports work**

Run: `python3 -c "from mat_runtime import Swarm, SwarmTask, SwarmResult, CandidateResult; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat(swarm): complete MAT-47 variant dispatch implementation"
```

---

## Summary

This plan extends the existing Swarm runtime to support `dispatch_mode: "variant"`:

1. **definition.py** - Accept `variant` mode with `return-all` consensus
2. **types.py** - Add `variant_output` field to `CandidateResult`
3. **swarm.py** - Branch initialization and dispatch by mode, use `AgentRouter` for variants
4. **Tests** - Unit tests for variant mode, integration tests with real agent files

The implementation follows existing patterns and maintains backward compatibility with `parallel_model` mode.

## References

- [MAT-47](https://github.com/zsleavitt/multi-agent-toolkit/issues/44) - This issue
- [MAT-46](https://github.com/zsleavitt/multi-agent-toolkit/issues/43) - Parallel model dispatch (completed)
- [MAT-40](https://github.com/zsleavitt/multi-agent-toolkit/issues/37) - Agent variant schema
- [Swarm schema](../../../schemas/swarm/v1/swarm.schema.json) - Definition schema
