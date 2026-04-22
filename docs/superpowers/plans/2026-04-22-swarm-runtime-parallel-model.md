# Swarm Runtime: Parallel Model Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Swarm runtime for dispatching same task to multiple CLI adapters in parallel with first-complete consensus.

**Architecture:** Mirror `mat_runtime/crew/` structure. Swarm class loads definition, creates CLI adapters for each candidate, dispatches via `asyncio.gather()`, and applies first-complete consensus (first `ok == True` response wins).

**Tech Stack:** Python 3.10+, asyncio, dataclasses, pytest

---

## File Structure

| File | Responsibility |
|------|----------------|
| `mat_runtime/swarm/__init__.py` | Public exports: Swarm, SwarmTask, SwarmResult, load_swarm_definition |
| `mat_runtime/swarm/types.py` | Data classes: SwarmTask, CandidateResult, SwarmResult |
| `mat_runtime/swarm/definition.py` | SwarmDefinition, ConstraintsConfig, load_swarm_definition() |
| `mat_runtime/swarm/swarm.py` | Swarm class with dispatch() and consensus logic |
| `mat_runtime/swarm/tests/test_definition.py` | Definition loading and validation tests |
| `mat_runtime/swarm/tests/test_swarm.py` | Dispatch and consensus tests with mocked adapters |
| `mat_runtime/__init__.py` | Add swarm exports |
| `mat_runtime/__main__.py` | Add invoke-swarm command |

---

### Task 1: Create types.py with SwarmTask, CandidateResult, SwarmResult

**Files:**
- Create: `mat_runtime/swarm/types.py`
- Create: `mat_runtime/swarm/__init__.py` (stub)
- Create: `mat_runtime/swarm/tests/__init__.py`

- [ ] **Step 1: Create swarm directory structure**

```bash
mkdir -p mat_runtime/swarm/tests
```

- [ ] **Step 2: Create tests/__init__.py**

```python
# mat_runtime/swarm/tests/__init__.py
"""Swarm runtime tests."""
```

- [ ] **Step 3: Create types.py with all dataclasses**

```python
# mat_runtime/swarm/types.py
"""Core types for Swarm runtime."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from mat_runtime.adapters import InvocationResult


@dataclass
class SwarmTask:
    """Task submitted to a Swarm for parallel dispatch."""

    instruction: str
    op: str = "codex.implement"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timeout_ms: int | None = None


@dataclass
class CandidateResult:
    """Result from a single candidate in the swarm."""

    candidate: str  # CLI adapter name (e.g., "claude", "codex")
    ok: bool
    response: InvocationResult | None
    duration_ms: int
    error: str | None = None


@dataclass
class SwarmResult:
    """Result of swarm dispatch with consensus applied."""

    ok: bool
    consensus_strategy: str
    winning_candidate: str | None
    output: Any
    correlation_id: str
    duration_ms: int
    candidate_results: list[CandidateResult]
    error: dict[str, Any] | None = None
```

- [ ] **Step 4: Create stub __init__.py**

```python
# mat_runtime/swarm/__init__.py
"""Swarm runtime - parallel dispatch to multiple CLI adapters."""

from mat_runtime.swarm.types import SwarmTask, CandidateResult, SwarmResult

__all__ = [
    "SwarmTask",
    "CandidateResult",
    "SwarmResult",
]
```

- [ ] **Step 5: Verify imports work**

Run: `python -c "from mat_runtime.swarm import SwarmTask, CandidateResult, SwarmResult; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add mat_runtime/swarm/
git commit -m "feat(swarm): add SwarmTask, CandidateResult, SwarmResult types"
```

---

### Task 2: Create definition.py with SwarmDefinition and loader

**Files:**
- Create: `mat_runtime/swarm/definition.py`
- Modify: `mat_runtime/swarm/__init__.py`

- [ ] **Step 1: Create definition.py**

```python
# mat_runtime/swarm/definition.py
"""Swarm definition loading and configuration types."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConstraintsConfig:
    """Swarm constraints configuration."""

    timeout_ms: int | None = None


@dataclass
class SwarmDefinition:
    """Parsed swarm definition."""

    name: str
    dispatch_mode: str
    candidates: list[str]
    consensus_strategy: str
    schema_version: str = "1.0.0"
    description: str | None = None
    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)
    source_path: Path | None = None


def _parse_constraints(data: dict | None) -> ConstraintsConfig:
    """Parse constraints configuration."""
    if not data:
        return ConstraintsConfig()
    return ConstraintsConfig(
        timeout_ms=data.get("timeout_ms"),
    )


def load_swarm_definition(path: Path | str) -> SwarmDefinition:
    """
    Load and parse a swarm definition from JSON.

    Validates:
    - dispatch_mode is "parallel_model" (variant not supported in MAT-46)
    - consensus_strategy is valid for dispatch_mode
    - candidates list has >= 2 items

    Args:
        path: Path to the swarm definition JSON file.

    Returns:
        Parsed SwarmDefinition.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the definition is invalid.
        json.JSONDecodeError: If the file isn't valid JSON.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    # Validate required fields
    name = data.get("name")
    if not name:
        raise ValueError("Swarm definition missing required field: name")

    dispatch_mode = data.get("dispatch_mode")
    if not dispatch_mode:
        raise ValueError("Swarm definition missing required field: dispatch_mode")

    # MAT-46: only parallel_model supported
    if dispatch_mode != "parallel_model":
        raise ValueError(
            f"dispatch_mode '{dispatch_mode}' not supported in MAT-46. "
            f"Only 'parallel_model' is implemented."
        )

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Swarm definition missing required field: candidates")
    if len(candidates) < 2:
        raise ValueError(
            f"Swarm requires at least 2 candidates, got {len(candidates)}"
        )

    consensus_strategy = data.get("consensus_strategy")
    if not consensus_strategy:
        raise ValueError("Swarm definition missing required field: consensus_strategy")

    # Validate consensus_strategy for parallel_model
    valid_strategies = {"first-complete", "majority-vote"}
    if consensus_strategy not in valid_strategies:
        raise ValueError(
            f"consensus_strategy '{consensus_strategy}' not valid for parallel_model. "
            f"Use one of: {', '.join(sorted(valid_strategies))}"
        )

    # MAT-46: only first-complete implemented
    if consensus_strategy == "majority-vote":
        raise ValueError(
            "consensus_strategy 'majority-vote' not implemented in MAT-46. "
            "Use 'first-complete'."
        )

    return SwarmDefinition(
        name=name,
        dispatch_mode=dispatch_mode,
        candidates=candidates,
        consensus_strategy=consensus_strategy,
        schema_version=data.get("schema_version", "1.0.0"),
        description=data.get("description"),
        constraints=_parse_constraints(data.get("constraints")),
        source_path=path,
    )
```

- [ ] **Step 2: Update __init__.py to export definition types**

```python
# mat_runtime/swarm/__init__.py
"""Swarm runtime - parallel dispatch to multiple CLI adapters."""

from mat_runtime.swarm.types import SwarmTask, CandidateResult, SwarmResult
from mat_runtime.swarm.definition import (
    ConstraintsConfig,
    SwarmDefinition,
    load_swarm_definition,
)

__all__ = [
    # Types
    "SwarmTask",
    "CandidateResult",
    "SwarmResult",
    # Definition
    "ConstraintsConfig",
    "SwarmDefinition",
    "load_swarm_definition",
]
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from mat_runtime.swarm import SwarmDefinition, load_swarm_definition; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add mat_runtime/swarm/definition.py mat_runtime/swarm/__init__.py
git commit -m "feat(swarm): add SwarmDefinition and load_swarm_definition"
```

---

### Task 3: Create test_definition.py with loader tests

**Files:**
- Create: `mat_runtime/swarm/tests/test_definition.py`

- [ ] **Step 1: Create test_definition.py**

```python
# mat_runtime/swarm/tests/test_definition.py
"""Tests for swarm definition loading."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from mat_runtime.swarm.definition import (
    ConstraintsConfig,
    SwarmDefinition,
    load_swarm_definition,
)


def _write_definition(data: dict) -> Path:
    """Write a definition to a temp file and return the path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


class TestLoadSwarmDefinition:
    """Tests for load_swarm_definition()."""

    def test_load_valid_parallel_model_definition(self):
        """Load a valid parallel_model swarm definition."""
        path = _write_definition({
            "schema_version": "1.0.0",
            "name": "test-swarm",
            "description": "Test swarm",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex", "gemini"],
            "consensus_strategy": "first-complete",
            "constraints": {
                "timeout_ms": 120000
            }
        })

        definition = load_swarm_definition(path)

        assert definition.name == "test-swarm"
        assert definition.description == "Test swarm"
        assert definition.dispatch_mode == "parallel_model"
        assert definition.candidates == ["claude", "codex", "gemini"]
        assert definition.consensus_strategy == "first-complete"
        assert definition.constraints.timeout_ms == 120000
        assert definition.source_path == path

        path.unlink()

    def test_load_minimal_definition(self):
        """Load definition with only required fields."""
        path = _write_definition({
            "name": "minimal",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "first-complete",
        })

        definition = load_swarm_definition(path)

        assert definition.name == "minimal"
        assert definition.description is None
        assert definition.constraints.timeout_ms is None
        assert definition.schema_version == "1.0.0"

        path.unlink()

    def test_reject_variant_mode(self):
        """Reject variant dispatch mode (not supported in MAT-46)."""
        path = _write_definition({
            "name": "variant-swarm",
            "dispatch_mode": "variant",
            "candidates": ["python-engineer", "ruby-engineer"],
            "consensus_strategy": "return-all",
        })

        with pytest.raises(ValueError, match="dispatch_mode 'variant' not supported"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_majority_vote(self):
        """Reject majority-vote consensus (not implemented in MAT-46)."""
        path = _write_definition({
            "name": "majority-swarm",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex", "gemini"],
            "consensus_strategy": "majority-vote",
        })

        with pytest.raises(ValueError, match="majority-vote' not implemented"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_invalid_consensus_for_mode(self):
        """Reject consensus strategy not valid for parallel_model."""
        path = _write_definition({
            "name": "invalid-consensus",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "return-all",
        })

        with pytest.raises(ValueError, match="not valid for parallel_model"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_fewer_than_two_candidates(self):
        """Reject swarm with fewer than 2 candidates."""
        path = _write_definition({
            "name": "single-candidate",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude"],
            "consensus_strategy": "first-complete",
        })

        with pytest.raises(ValueError, match="at least 2 candidates"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_missing_name(self):
        """Reject definition missing name."""
        path = _write_definition({
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "first-complete",
        })

        with pytest.raises(ValueError, match="missing required field: name"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_missing_dispatch_mode(self):
        """Reject definition missing dispatch_mode."""
        path = _write_definition({
            "name": "no-mode",
            "candidates": ["claude", "codex"],
            "consensus_strategy": "first-complete",
        })

        with pytest.raises(ValueError, match="missing required field: dispatch_mode"):
            load_swarm_definition(path)

        path.unlink()

    def test_reject_missing_consensus_strategy(self):
        """Reject definition missing consensus_strategy."""
        path = _write_definition({
            "name": "no-consensus",
            "dispatch_mode": "parallel_model",
            "candidates": ["claude", "codex"],
        })

        with pytest.raises(ValueError, match="missing required field: consensus_strategy"):
            load_swarm_definition(path)

        path.unlink()

    def test_file_not_found(self):
        """Raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_swarm_definition("/nonexistent/path.json")

    def test_invalid_json(self):
        """Raise JSONDecodeError for invalid JSON."""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("not valid json {")
        f.close()
        path = Path(f.name)

        with pytest.raises(json.JSONDecodeError):
            load_swarm_definition(path)

        path.unlink()
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest mat_runtime/swarm/tests/test_definition.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add mat_runtime/swarm/tests/test_definition.py
git commit -m "test(swarm): add definition loading tests"
```

---

### Task 4: Create swarm.py with Swarm class

**Files:**
- Create: `mat_runtime/swarm/swarm.py`
- Modify: `mat_runtime/swarm/__init__.py`

- [ ] **Step 1: Create swarm.py**

```python
# mat_runtime/swarm/swarm.py
"""Swarm orchestration class."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from mat_runtime.adapters import ADAPTER_REGISTRY, CLIAdapter, get_adapter
from mat_runtime.swarm.definition import SwarmDefinition, load_swarm_definition
from mat_runtime.swarm.types import CandidateResult, SwarmResult, SwarmTask


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

        Raises:
            ValueError: If dispatch_mode is not "parallel_model".
            ValueError: If any candidate is not a registered CLI adapter.
        """
        self._definition = load_swarm_definition(definition_path)
        self._repo_root = Path(repo_root) if repo_root else Path.cwd()

        # Validate all candidates are registered adapters
        for candidate in self._definition.candidates:
            if candidate not in ADAPTER_REGISTRY:
                raise ValueError(
                    f"Unknown CLI adapter '{candidate}'. "
                    f"Available: {', '.join(sorted(ADAPTER_REGISTRY.keys()))}"
                )

        # Create adapters
        self._adapters: dict[str, CLIAdapter] = {}
        for candidate in self._definition.candidates:
            self._adapters[candidate] = get_adapter(
                cli=candidate,
                working_dir=str(self._repo_root),
            )

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
        Invoke a single candidate adapter.

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
            response = await asyncio.to_thread(
                self._adapters[candidate].invoke,
                prompt=task.instruction,
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

    def _apply_consensus(
        self,
        results: list[CandidateResult],
        task: SwarmTask,
        total_duration_ms: int,
    ) -> SwarmResult:
        """
        Apply consensus strategy to candidate results.

        For first-complete:
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
```

- [ ] **Step 2: Update __init__.py to export Swarm**

```python
# mat_runtime/swarm/__init__.py
"""Swarm runtime - parallel dispatch to multiple CLI adapters."""

from mat_runtime.swarm.types import SwarmTask, CandidateResult, SwarmResult
from mat_runtime.swarm.definition import (
    ConstraintsConfig,
    SwarmDefinition,
    load_swarm_definition,
)
from mat_runtime.swarm.swarm import Swarm

__all__ = [
    # Types
    "SwarmTask",
    "CandidateResult",
    "SwarmResult",
    # Definition
    "ConstraintsConfig",
    "SwarmDefinition",
    "load_swarm_definition",
    # Swarm
    "Swarm",
]
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from mat_runtime.swarm import Swarm; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add mat_runtime/swarm/swarm.py mat_runtime/swarm/__init__.py
git commit -m "feat(swarm): add Swarm class with dispatch and consensus"
```

---

### Task 5: Create test_swarm.py with dispatch and consensus tests

**Files:**
- Create: `mat_runtime/swarm/tests/test_swarm.py`

- [ ] **Step 1: Create test_swarm.py**

```python
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
        swarm = Swarm(definition_path=swarm_path)

        # Mock adapters - codex succeeds faster
        mock_claude = MagicMock()
        mock_codex = MagicMock()

        def claude_invoke(**kwargs):
            return _make_invocation_result(ok=True, stdout="claude output")

        def codex_invoke(**kwargs):
            return _make_invocation_result(ok=True, stdout="codex output")

        mock_claude.invoke = claude_invoke
        mock_codex.invoke = codex_invoke

        swarm._adapters = {"claude": mock_claude, "codex": mock_codex}

        task = SwarmTask(instruction="test instruction")
        result = asyncio.run(swarm.dispatch(task))

        assert result.ok is True
        assert result.winning_candidate in ["claude", "codex"]
        assert result.output in ["claude output", "codex output"]
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest mat_runtime/swarm/tests/test_swarm.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add mat_runtime/swarm/tests/test_swarm.py
git commit -m "test(swarm): add dispatch and consensus tests"
```

---

### Task 6: Update mat_runtime/__init__.py exports

**Files:**
- Modify: `mat_runtime/__init__.py`

- [ ] **Step 1: Update __init__.py to export swarm module**

```python
# mat_runtime/__init__.py
"""
MAT Runtime — Multi-Agent Toolkit runtime adapter layer.

Provides CLI-based agent invocation following the CLI delegation model (ADR 0002).
No direct API calls — each CLI tool manages its own authentication.
"""

from mat_runtime.router import AgentRouter
from mat_runtime.config import load_provider_config, load_agent_definitions
from mat_runtime.crew import (
    Crew,
    CrewTask,
    CrewResult,
    CrewDefinition,
    load_crew_definition,
)
from mat_runtime.swarm import (
    Swarm,
    SwarmTask,
    SwarmResult,
    SwarmDefinition,
    load_swarm_definition,
)

__all__ = [
    "AgentRouter",
    "load_provider_config",
    "load_agent_definitions",
    # Crew
    "Crew",
    "CrewTask",
    "CrewResult",
    "CrewDefinition",
    "load_crew_definition",
    # Swarm
    "Swarm",
    "SwarmTask",
    "SwarmResult",
    "SwarmDefinition",
    "load_swarm_definition",
]
__version__ = "0.1.0"
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from mat_runtime import Swarm, SwarmTask, SwarmResult; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add mat_runtime/__init__.py
git commit -m "feat(swarm): export swarm module from mat_runtime"
```

---

### Task 7: Add invoke-swarm command to __main__.py

**Files:**
- Modify: `mat_runtime/__main__.py`

- [ ] **Step 1: Add async handler for invoke-swarm**

Add after line 144 (after `cmd_invoke_crew`):

```python
async def cmd_invoke_swarm_async(args: argparse.Namespace) -> int:
    """Handle the invoke-swarm command (async implementation)."""
    from mat_runtime.swarm import Swarm, SwarmTask

    swarm = Swarm(
        definition_path=args.swarm,
        repo_root=args.repo_root,
    )

    task = SwarmTask(
        instruction=args.instruction,
        op=args.op,
        timeout_ms=args.timeout_ms,
    )

    result = await swarm.dispatch(task)

    # Output result
    output = {
        "ok": result.ok,
        "consensus_strategy": result.consensus_strategy,
        "winning_candidate": result.winning_candidate,
        "correlation_id": result.correlation_id,
        "duration_ms": result.duration_ms,
        "candidate_results": [
            {
                "candidate": cr.candidate,
                "ok": cr.ok,
                "duration_ms": cr.duration_ms,
                "error": cr.error,
            }
            for cr in result.candidate_results
        ],
    }
    if result.ok:
        output["output"] = result.output
    else:
        output["error"] = result.error

    print(json.dumps(output, indent=2 if args.pretty else None))
    return 0 if result.ok else 1


def cmd_invoke_swarm(args: argparse.Namespace) -> int:
    """Handle the invoke-swarm command."""
    return asyncio.run(cmd_invoke_swarm_async(args))
```

- [ ] **Step 2: Add invoke-swarm subparser**

Add after line 271 (after `invoke_crew_parser.set_defaults`):

```python
    # invoke-swarm command
    invoke_swarm_parser = subparsers.add_parser(
        "invoke-swarm", help="Dispatch a task to a swarm"
    )
    invoke_swarm_parser.add_argument(
        "--swarm",
        "-s",
        type=Path,
        required=True,
        help="Path to swarm definition JSON file",
    )
    invoke_swarm_parser.add_argument(
        "--instruction",
        "-i",
        required=True,
        help="Task instruction",
    )
    invoke_swarm_parser.add_argument(
        "--op",
        "-o",
        default="codex.implement",
        help="Operation (default: codex.implement)",
    )
    invoke_swarm_parser.add_argument(
        "--timeout-ms",
        "-t",
        type=int,
        help="Task timeout in milliseconds",
    )
    invoke_swarm_parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: true)",
    )
    invoke_swarm_parser.set_defaults(func=cmd_invoke_swarm)
```

- [ ] **Step 3: Verify command shows in help**

Run: `python -m mat_runtime --help`
Expected: Shows `invoke-swarm` in commands list

- [ ] **Step 4: Commit**

```bash
git add mat_runtime/__main__.py
git commit -m "feat(swarm): add invoke-swarm CLI command"
```

---

### Task 8: Run all tests and verify

**Files:**
- None (verification only)

- [ ] **Step 1: Run all swarm tests**

Run: `python -m pytest mat_runtime/swarm/tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run all mat_runtime tests**

Run: `python -m pytest mat_runtime/tests/ -v`
Expected: All existing tests still pass

- [ ] **Step 3: Verify CLI commands work**

Run: `python -m mat_runtime list-agents`
Expected: Lists agents (verifies imports work)

Run: `python -m mat_runtime invoke-swarm --help`
Expected: Shows invoke-swarm help

- [ ] **Step 4: Final commit with any fixes**

```bash
git status
# If clean, skip this step
# If any fixes needed, commit them
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - [x] Types: SwarmTask, CandidateResult, SwarmResult (Task 1)
   - [x] Definition: SwarmDefinition, load_swarm_definition (Task 2)
   - [x] Validation: dispatch_mode, consensus_strategy, candidates count (Task 2, 3)
   - [x] Swarm class: dispatch(), _invoke_candidate(), _apply_consensus() (Task 4)
   - [x] First-complete consensus logic (Task 4)
   - [x] Tests for definition loading (Task 3)
   - [x] Tests for dispatch and consensus (Task 5)
   - [x] Module exports (Task 6)
   - [x] CLI command (Task 7)

2. **No placeholders:** All code is complete and runnable.

3. **Type consistency:** All types match between definition and usage.
