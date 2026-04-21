# MAT-43 Crew Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Python runtime layer that executes Crew definitions, routing tasks to member agents via AgentRouter with configurable strategies, constraints, hooks, and shared context.

**Architecture:** Async-first design with sync v1 implementation. Crew loads definitions from `crews/*.json`, validates against schema, resolves agent references via AgentRouter. Task submission acquires semaphore, selects agent via RoutingStrategy, executes with retry loop using `asyncio.to_thread`, runs lifecycle hooks with per-hook timeouts.

**Tech Stack:** Python 3.11+, asyncio, dataclasses, typing.Protocol, pytest

**Spec:** `docs/superpowers/specs/2026-04-21-crew-runtime-design.md`

---

## File Structure

```
mat_runtime/crew/
  __init__.py          # exports: Crew, CrewTask, CrewResult, CrewDefinition
  types.py             # CrewTask, CrewResult dataclasses
  definition.py        # CrewDefinition loader, config dataclasses
  routing.py           # RoutingStrategy protocol + 4 implementations
  context.py           # ContextStore protocol + Memory/Null stores
  hooks.py             # HookRunner with per-hook timeouts
  crew.py              # Crew class - orchestration, retry, semaphore
  tests/
    __init__.py
    test_routing.py
    test_context.py
    test_hooks.py
    test_crew.py
```

---

### Task 1: Update MAT-42 Schema with Hook Timeout Fields

**Files:**
- Modify: `schemas/crew/v1/crew.schema.json:171-199`

- [ ] **Step 1: Add per-hook timeout fields to schema**

```json
"hooks": {
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "on_start": {
      "allOf": [{ "$ref": "#/$defs/repo_relative_path" }],
      "description": "Script to run when crew starts"
    },
    "on_start_timeout_ms": {
      "type": "integer",
      "minimum": 1000,
      "maximum": 300000,
      "default": 30000,
      "description": "Timeout for on_start hook (default 30s)"
    },
    "on_task_assigned": {
      "allOf": [{ "$ref": "#/$defs/repo_relative_path" }],
      "description": "Script to run when a task is assigned to an agent"
    },
    "on_task_assigned_timeout_ms": {
      "type": "integer",
      "minimum": 1000,
      "maximum": 300000,
      "default": 30000,
      "description": "Timeout for on_task_assigned hook (default 30s)"
    },
    "on_task_complete": {
      "allOf": [{ "$ref": "#/$defs/repo_relative_path" }],
      "description": "Script to run when an agent completes a task"
    },
    "on_task_complete_timeout_ms": {
      "type": "integer",
      "minimum": 1000,
      "maximum": 300000,
      "default": 30000,
      "description": "Timeout for on_task_complete hook (default 30s)"
    },
    "on_agent_failure": {
      "allOf": [{ "$ref": "#/$defs/repo_relative_path" }],
      "description": "Script to run when an agent fails"
    },
    "on_agent_failure_timeout_ms": {
      "type": "integer",
      "minimum": 1000,
      "maximum": 300000,
      "default": 30000,
      "description": "Timeout for on_agent_failure hook (default 30s)"
    },
    "on_finish": {
      "allOf": [{ "$ref": "#/$defs/repo_relative_path" }],
      "description": "Script to run when crew completes all work"
    },
    "on_finish_timeout_ms": {
      "type": "integer",
      "minimum": 1000,
      "maximum": 300000,
      "default": 30000,
      "description": "Timeout for on_finish hook (default 30s)"
    },
    "on_error": {
      "allOf": [{ "$ref": "#/$defs/repo_relative_path" }],
      "description": "Script to run on crew-level error (timeout, max_tasks exceeded)"
    },
    "on_error_timeout_ms": {
      "type": "integer",
      "minimum": 1000,
      "maximum": 300000,
      "default": 30000,
      "description": "Timeout for on_error hook (default 30s)"
    }
  }
}
```

- [ ] **Step 2: Validate schema still passes**

Run: `python scripts/validate_crew.py`
Expected: All checks pass

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/crew.schema.json
git commit -m "feat(schema): add per-hook timeout fields to crew schema (MAT-43)"
```

---

### Task 2: Add agent_refused Error Code to AgentRouter

**Files:**
- Modify: `mat_runtime/router.py:248-260`
- Test: `mat_runtime/tests/test_router.py`

- [ ] **Step 1: Write failing test for agent_refused**

Add to `mat_runtime/tests/test_router.py`:

```python
def test_invoke_agent_refused_when_output_but_failure(
    sample_agents: dict[str, AgentDefinition],
    sample_provider_config: ProviderConfig,
) -> None:
    """Agent produces output but indicates failure = agent_refused."""
    router = AgentRouter(
        repo_root=Path("/tmp"),
        provider_config=sample_provider_config,
        agents=sample_agents,
    )

    # Mock adapter that returns non-zero with stdout (semantic failure)
    mock_result = InvocationResult(
        ok=False,
        return_code=1,
        stdout="I cannot perform this task because it violates safety guidelines.",
        stderr="",
        timeout_exceeded=False,
        duration_ms=500,
    )

    with patch.object(router, "_get_adapter") as mock_get:
        mock_adapter = MagicMock()
        mock_adapter.invoke.return_value = mock_result
        mock_get.return_value = mock_adapter

        response = router.invoke(
            "coder",
            MAT2Request(
                schema_version="1.2.0",
                correlation_id="test-123",
                idempotency_key="key-123",
                op="codex.implement",
                repo_root="/tmp",
                instruction="Do something unsafe",
            ),
        )

    assert not response.ok
    assert response.error is not None
    assert response.error["code"] == "agent_refused"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mat_runtime/tests/test_router.py::test_invoke_agent_refused_when_output_but_failure -v`
Expected: FAIL with AssertionError (code is "execution_error" not "agent_refused")

- [ ] **Step 3: Update router.py error code logic**

Replace lines 248-260 in `mat_runtime/router.py`:

```python
        # Build response
        if result.ok:
            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=True,
                result={
                    "output": result.stdout,
                    "files_modified": [],  # Would need to parse from output
                },
            )
        else:
            # Classify error: timeout vs semantic refusal vs infrastructure
            if result.timeout_exceeded:
                error_code = "timeout"
            elif result.stdout.strip():
                # Agent produced output but failed = semantic refusal
                error_code = "agent_refused"
            else:
                # No output = infrastructure failure
                error_code = "execution_error"

            return MAT2Response(
                schema_version=req.schema_version,
                correlation_id=req.correlation_id,
                idempotency_key=req.idempotency_key,
                ok=False,
                error={
                    "code": error_code,
                    "message": result.stderr or result.stdout or f"CLI returned code {result.return_code}",
                },
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest mat_runtime/tests/test_router.py::test_invoke_agent_refused_when_output_but_failure -v`
Expected: PASS

- [ ] **Step 5: Run all router tests**

Run: `pytest mat_runtime/tests/test_router.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add mat_runtime/router.py mat_runtime/tests/test_router.py
git commit -m "feat(router): add agent_refused error code for semantic failures (MAT-43)"
```

---

### Task 3: Create Package Structure and types.py

**Files:**
- Create: `mat_runtime/crew/__init__.py`
- Create: `mat_runtime/crew/types.py`
- Create: `mat_runtime/crew/tests/__init__.py`

- [ ] **Step 1: Create package directories**

```bash
mkdir -p mat_runtime/crew/tests
```

- [ ] **Step 2: Create types.py with CrewTask and CrewResult**

```python
"""Core types for Crew runtime."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CrewTask:
    """Task submitted to a Crew for execution."""

    instruction: str
    op: str = "codex.implement"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    required_capabilities: list[str] = field(default_factory=list)
    scope_paths: list[str] = field(default_factory=list)
    timeout_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrewResult:
    """Result of executing a CrewTask."""

    ok: bool
    agent_used: str
    output: Any
    correlation_id: str
    duration_ms: int
    attempts: int = 1
    retry_reasons: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
```

- [ ] **Step 3: Create crew/__init__.py**

```python
"""Crew runtime - orchestration layer for multi-agent task routing."""

from mat_runtime.crew.types import CrewTask, CrewResult

__all__ = [
    "CrewTask",
    "CrewResult",
]
```

- [ ] **Step 4: Create tests/__init__.py**

```python
"""Tests for Crew runtime."""
```

- [ ] **Step 5: Verify import works**

Run: `python -c "from mat_runtime.crew import CrewTask, CrewResult; print('OK')"`
Expected: OK

- [ ] **Step 6: Commit**

```bash
git add mat_runtime/crew/
git commit -m "feat(crew): add types.py with CrewTask and CrewResult (MAT-43)"
```

---

### Task 4: Implement definition.py (Config Dataclasses)

**Files:**
- Create: `mat_runtime/crew/definition.py`

- [ ] **Step 1: Create definition.py with config dataclasses**

```python
"""Crew definition loading and configuration types."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentRef:
    """Reference to an agent within a crew."""

    name: str
    timeout_ms: int | None = None
    priority: int = 0
    required_capabilities: list[str] = field(default_factory=list)


@dataclass
class RoutingConfig:
    """Routing configuration for a crew."""

    strategy: str = "round-robin"
    match_on: list[str] = field(default_factory=list)
    fallback: str = "round-robin"
    allow_reassignment: bool = False
    prefer_idle: bool = True


@dataclass
class ConstraintsConfig:
    """Constraints configuration for a crew."""

    max_concurrent_agents: int | None = None
    timeout_ms: int | None = None
    max_tasks: int | None = None
    max_retries: int = 0
    backoff_ms: int = 1000
    backoff_multiplier: float = 2.0


@dataclass
class HooksConfig:
    """Hooks configuration for a crew."""

    on_start: str | None = None
    on_start_timeout_ms: int = 30000
    on_task_assigned: str | None = None
    on_task_assigned_timeout_ms: int = 30000
    on_task_complete: str | None = None
    on_task_complete_timeout_ms: int = 30000
    on_agent_failure: str | None = None
    on_agent_failure_timeout_ms: int = 30000
    on_finish: str | None = None
    on_finish_timeout_ms: int = 30000
    on_error: str | None = None
    on_error_timeout_ms: int = 30000


@dataclass
class CommunicationConfig:
    """Communication configuration for a crew."""

    shared_context_type: str = "none"
    shared_context_path: str | None = None
    shared_context_ttl_ms: int = 0
    message_passing_mode: str = "none"


@dataclass
class CrewDefinition:
    """Parsed crew definition."""

    name: str
    agents: list[AgentRef]
    schema_version: str = "1.0.0"
    description: str | None = None
    shared_goal: str | None = None
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    constraints: ConstraintsConfig = field(default_factory=ConstraintsConfig)
    hooks: HooksConfig = field(default_factory=HooksConfig)
    communication: CommunicationConfig = field(default_factory=CommunicationConfig)
    source_path: Path | None = None


def _validate_hook_path(path: str) -> None:
    """Validate hook path is safe (no absolute, no traversal)."""
    if path.startswith("/") or path.startswith("\\"):
        raise ValueError(f"Hook path must be relative: {path}")
    if ".." in path:
        raise ValueError(f"Hook path cannot contain '..': {path}")


def _parse_agents(agents_data: list[Any]) -> list[AgentRef]:
    """Parse agents array into list of AgentRef."""
    result = []
    for item in agents_data:
        if isinstance(item, str):
            result.append(AgentRef(name=item))
        elif isinstance(item, dict):
            result.append(
                AgentRef(
                    name=item["name"],
                    timeout_ms=item.get("timeout_ms"),
                    priority=item.get("priority", 0),
                    required_capabilities=item.get("required_capabilities", []),
                )
            )
        else:
            raise ValueError(f"Invalid agent entry: {item}")
    return result


def _parse_routing(data: dict[str, Any] | None) -> RoutingConfig:
    """Parse routing configuration."""
    if not data:
        return RoutingConfig()

    task_assignment = data.get("task_assignment", {})
    return RoutingConfig(
        strategy=data.get("strategy", "round-robin"),
        match_on=data.get("match_on", []),
        fallback=data.get("fallback", "round-robin"),
        allow_reassignment=task_assignment.get("allow_reassignment", False),
        prefer_idle=task_assignment.get("prefer_idle", True),
    )


def _parse_constraints(data: dict[str, Any] | None) -> ConstraintsConfig:
    """Parse constraints configuration."""
    if not data:
        return ConstraintsConfig()

    retry_policy = data.get("retry_policy", {})
    return ConstraintsConfig(
        max_concurrent_agents=data.get("max_concurrent_agents"),
        timeout_ms=data.get("timeout_ms"),
        max_tasks=data.get("max_tasks"),
        max_retries=retry_policy.get("max_retries", 0),
        backoff_ms=retry_policy.get("backoff_ms", 1000),
        backoff_multiplier=retry_policy.get("backoff_multiplier", 2.0),
    )


def _parse_hooks(data: dict[str, Any] | None) -> HooksConfig:
    """Parse hooks configuration with semantic validation."""
    if not data:
        return HooksConfig()

    # Validate all hook paths
    for key in ["on_start", "on_task_assigned", "on_task_complete",
                "on_agent_failure", "on_finish", "on_error"]:
        if path := data.get(key):
            _validate_hook_path(path)

    return HooksConfig(
        on_start=data.get("on_start"),
        on_start_timeout_ms=data.get("on_start_timeout_ms", 30000),
        on_task_assigned=data.get("on_task_assigned"),
        on_task_assigned_timeout_ms=data.get("on_task_assigned_timeout_ms", 30000),
        on_task_complete=data.get("on_task_complete"),
        on_task_complete_timeout_ms=data.get("on_task_complete_timeout_ms", 30000),
        on_agent_failure=data.get("on_agent_failure"),
        on_agent_failure_timeout_ms=data.get("on_agent_failure_timeout_ms", 30000),
        on_finish=data.get("on_finish"),
        on_finish_timeout_ms=data.get("on_finish_timeout_ms", 30000),
        on_error=data.get("on_error"),
        on_error_timeout_ms=data.get("on_error_timeout_ms", 30000),
    )


def _parse_communication(data: dict[str, Any] | None) -> CommunicationConfig:
    """Parse communication configuration."""
    if not data:
        return CommunicationConfig()

    shared_context = data.get("shared_context", {})
    message_passing = data.get("message_passing", {})

    return CommunicationConfig(
        shared_context_type=shared_context.get("type", "none"),
        shared_context_path=shared_context.get("path"),
        shared_context_ttl_ms=shared_context.get("ttl_ms", 0),
        message_passing_mode=message_passing.get("mode", "none"),
    )


def load_crew_definition(path: Path | str) -> CrewDefinition:
    """
    Load and parse a crew definition from a JSON file.

    Args:
        path: Path to the crew definition JSON file.

    Returns:
        Parsed CrewDefinition.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the definition is invalid.
        json.JSONDecodeError: If the file isn't valid JSON.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))

    return CrewDefinition(
        name=data["name"],
        agents=_parse_agents(data["agents"]),
        schema_version=data.get("schema_version", "1.0.0"),
        description=data.get("description"),
        shared_goal=data.get("shared_goal"),
        routing=_parse_routing(data.get("routing")),
        constraints=_parse_constraints(data.get("constraints")),
        hooks=_parse_hooks(data.get("hooks")),
        communication=_parse_communication(data.get("communication")),
        source_path=path,
    )
```

- [ ] **Step 2: Update crew/__init__.py exports**

```python
"""Crew runtime - orchestration layer for multi-agent task routing."""

from mat_runtime.crew.types import CrewTask, CrewResult
from mat_runtime.crew.definition import (
    AgentRef,
    RoutingConfig,
    ConstraintsConfig,
    HooksConfig,
    CommunicationConfig,
    CrewDefinition,
    load_crew_definition,
)

__all__ = [
    "CrewTask",
    "CrewResult",
    "AgentRef",
    "RoutingConfig",
    "ConstraintsConfig",
    "HooksConfig",
    "CommunicationConfig",
    "CrewDefinition",
    "load_crew_definition",
]
```

- [ ] **Step 3: Verify import works**

Run: `python -c "from mat_runtime.crew import load_crew_definition; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add mat_runtime/crew/definition.py mat_runtime/crew/__init__.py
git commit -m "feat(crew): add definition.py with config dataclasses and loader (MAT-43)"
```

---

### Task 5: Add Tests for definition.py

**Files:**
- Create: `mat_runtime/crew/tests/test_definition.py`

- [ ] **Step 1: Write tests for definition loading**

```python
"""Tests for crew definition loading."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from mat_runtime.crew.definition import (
    AgentRef,
    CrewDefinition,
    load_crew_definition,
    _validate_hook_path,
)


class TestValidateHookPath:
    """Tests for hook path validation."""

    def test_relative_path_allowed(self) -> None:
        _validate_hook_path("scripts/hooks/on_start.sh")

    def test_absolute_path_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be relative"):
            _validate_hook_path("/etc/passwd")

    def test_windows_absolute_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be relative"):
            _validate_hook_path("\\Windows\\System32")

    def test_traversal_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot contain"):
            _validate_hook_path("../../../etc/passwd")

    def test_traversal_in_middle_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot contain"):
            _validate_hook_path("scripts/../../../etc/passwd")


class TestLoadCrewDefinition:
    """Tests for loading crew definitions."""

    def test_minimal_crew(self, tmp_path: Path) -> None:
        """Load a minimal valid crew definition."""
        crew_file = tmp_path / "minimal.json"
        crew_file.write_text(json.dumps({
            "schema_version": "1.0.0",
            "name": "test-crew",
            "agents": ["coder", "reviewer"],
        }))

        crew = load_crew_definition(crew_file)

        assert crew.name == "test-crew"
        assert len(crew.agents) == 2
        assert crew.agents[0].name == "coder"
        assert crew.agents[1].name == "reviewer"
        assert crew.routing.strategy == "round-robin"

    def test_agent_with_overrides(self, tmp_path: Path) -> None:
        """Load crew with agent override objects."""
        crew_file = tmp_path / "overrides.json"
        crew_file.write_text(json.dumps({
            "schema_version": "1.0.0",
            "name": "override-crew",
            "agents": [
                "coder",
                {
                    "name": "reviewer",
                    "timeout_ms": 60000,
                    "priority": 10,
                    "required_capabilities": ["security"],
                },
            ],
        }))

        crew = load_crew_definition(crew_file)

        assert crew.agents[0].name == "coder"
        assert crew.agents[0].timeout_ms is None
        assert crew.agents[1].name == "reviewer"
        assert crew.agents[1].timeout_ms == 60000
        assert crew.agents[1].priority == 10
        assert crew.agents[1].required_capabilities == ["security"]

    def test_full_crew(self, tmp_path: Path) -> None:
        """Load a fully-specified crew definition."""
        crew_file = tmp_path / "full.json"
        crew_file.write_text(json.dumps({
            "schema_version": "1.0.0",
            "name": "full-crew",
            "description": "A fully configured crew",
            "shared_goal": "Build the feature",
            "agents": ["coder"],
            "routing": {
                "strategy": "capability",
                "match_on": ["languages", "frameworks"],
                "fallback": "random",
                "task_assignment": {
                    "allow_reassignment": True,
                    "prefer_idle": False,
                },
            },
            "constraints": {
                "max_concurrent_agents": 2,
                "timeout_ms": 600000,
                "max_tasks": 100,
                "retry_policy": {
                    "max_retries": 3,
                    "backoff_ms": 2000,
                    "backoff_multiplier": 1.5,
                },
            },
            "hooks": {
                "on_start": "scripts/on_start.sh",
                "on_start_timeout_ms": 10000,
                "on_finish": "scripts/on_finish.sh",
            },
            "communication": {
                "shared_context": {
                    "type": "memory",
                    "ttl_ms": 60000,
                },
            },
        }))

        crew = load_crew_definition(crew_file)

        assert crew.description == "A fully configured crew"
        assert crew.shared_goal == "Build the feature"
        assert crew.routing.strategy == "capability"
        assert crew.routing.match_on == ["languages", "frameworks"]
        assert crew.routing.fallback == "random"
        assert crew.routing.allow_reassignment is True
        assert crew.routing.prefer_idle is False
        assert crew.constraints.max_concurrent_agents == 2
        assert crew.constraints.max_retries == 3
        assert crew.constraints.backoff_ms == 2000
        assert crew.hooks.on_start == "scripts/on_start.sh"
        assert crew.hooks.on_start_timeout_ms == 10000
        assert crew.communication.shared_context_type == "memory"

    def test_invalid_hook_path_rejected(self, tmp_path: Path) -> None:
        """Reject crew with unsafe hook paths."""
        crew_file = tmp_path / "bad-hooks.json"
        crew_file.write_text(json.dumps({
            "schema_version": "1.0.0",
            "name": "bad-crew",
            "agents": ["coder"],
            "hooks": {
                "on_start": "../../../etc/passwd",
            },
        }))

        with pytest.raises(ValueError, match="cannot contain"):
            load_crew_definition(crew_file)

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_crew_definition(tmp_path / "nonexistent.json")
```

- [ ] **Step 2: Run tests**

Run: `pytest mat_runtime/crew/tests/test_definition.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add mat_runtime/crew/tests/test_definition.py
git commit -m "test(crew): add tests for definition loading (MAT-43)"
```

---

### Task 6: Implement context.py (ContextStore Protocol)

**Files:**
- Create: `mat_runtime/crew/context.py`
- Create: `mat_runtime/crew/tests/test_context.py`

- [ ] **Step 1: Write failing test for MemoryContextStore**

Create `mat_runtime/crew/tests/test_context.py`:

```python
"""Tests for context stores."""

from __future__ import annotations

import asyncio
import time

import pytest

from mat_runtime.crew.context import (
    ContextStore,
    MemoryContextStore,
    NullContextStore,
    create_context_store,
)


class TestMemoryContextStore:
    """Tests for MemoryContextStore."""

    @pytest.mark.asyncio
    async def test_get_set_basic(self) -> None:
        store = MemoryContextStore()
        await store.set("key1", {"value": 42})
        result = await store.get("key1")
        assert result == {"value": 42}

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self) -> None:
        store = MemoryContextStore()
        result = await store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        store = MemoryContextStore()
        await store.set("key1", "value")
        await store.delete("key1")
        result = await store.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_no_error(self) -> None:
        store = MemoryContextStore()
        await store.delete("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_keys(self) -> None:
        store = MemoryContextStore()
        await store.set("a", 1)
        await store.set("b", 2)
        await store.set("c", 3)
        keys = await store.keys()
        assert sorted(keys) == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_ttl_expiry(self) -> None:
        store = MemoryContextStore()
        await store.set("expires", "soon", ttl_ms=50)
        # Should exist immediately
        assert await store.get("expires") == "soon"
        # Wait for expiry
        await asyncio.sleep(0.1)
        # Should be gone (lazy expiry on read)
        assert await store.get("expires") is None

    @pytest.mark.asyncio
    async def test_ttl_zero_no_expiry(self) -> None:
        store = MemoryContextStore()
        await store.set("forever", "value", ttl_ms=0)
        await asyncio.sleep(0.05)
        assert await store.get("forever") == "value"


class TestNullContextStore:
    """Tests for NullContextStore (Null Object pattern)."""

    @pytest.mark.asyncio
    async def test_get_always_none(self) -> None:
        store = NullContextStore()
        await store.set("key", "value")
        result = await store.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_keys_always_empty(self) -> None:
        store = NullContextStore()
        await store.set("key", "value")
        keys = await store.keys()
        assert keys == []

    @pytest.mark.asyncio
    async def test_delete_no_error(self) -> None:
        store = NullContextStore()
        await store.delete("key")  # Should not raise


class TestCreateContextStore:
    """Tests for context store factory."""

    def test_create_none_returns_null(self) -> None:
        store = create_context_store("none")
        assert isinstance(store, NullContextStore)

    def test_create_memory_returns_memory(self) -> None:
        store = create_context_store("memory")
        assert isinstance(store, MemoryContextStore)

    def test_create_file_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            create_context_store("file", path="some/path")

    def test_create_unknown_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown context store type"):
            create_context_store("unknown")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mat_runtime/crew/tests/test_context.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement context.py**

```python
"""Context stores for inter-agent state sharing."""

from __future__ import annotations

import time
from typing import Any, Protocol


class ContextStore(Protocol):
    """Protocol for context storage backends."""

    async def get(self, key: str) -> Any | None:
        """Get a value by key. Returns None if not found or expired."""
        ...

    async def set(self, key: str, value: Any, ttl_ms: int = 0) -> None:
        """Set a value with optional TTL (0 = no expiry)."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a key. No error if key doesn't exist."""
        ...

    async def keys(self) -> list[str]:
        """List all non-expired keys."""
        ...


class NullContextStore:
    """
    No-op context store for 'none' mode.

    Implements the Null Object pattern - all operations succeed
    but nothing is stored.
    """

    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl_ms: int = 0) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass

    async def keys(self) -> list[str]:
        return []


class MemoryContextStore:
    """
    In-memory context store with lazy TTL expiry.

    Values are stored with their expiry timestamp. Expired values
    are removed lazily when accessed via get() or keys().
    """

    def __init__(self) -> None:
        # Store: key -> (value, expiry_time_ms or None)
        self._data: dict[str, tuple[Any, int | None]] = {}

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _is_expired(self, expiry: int | None) -> bool:
        if expiry is None:
            return False
        return self._now_ms() > expiry

    async def get(self, key: str) -> Any | None:
        entry = self._data.get(key)
        if entry is None:
            return None

        value, expiry = entry
        if self._is_expired(expiry):
            del self._data[key]
            return None

        return value

    async def set(self, key: str, value: Any, ttl_ms: int = 0) -> None:
        if ttl_ms > 0:
            expiry = self._now_ms() + ttl_ms
        else:
            expiry = None
        self._data[key] = (value, expiry)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def keys(self) -> list[str]:
        # Clean expired keys during enumeration
        valid_keys = []
        expired_keys = []

        for key, (_, expiry) in self._data.items():
            if self._is_expired(expiry):
                expired_keys.append(key)
            else:
                valid_keys.append(key)

        for key in expired_keys:
            del self._data[key]

        return valid_keys


def create_context_store(
    store_type: str,
    path: str | None = None,
    ttl_ms: int = 0,
) -> ContextStore:
    """
    Factory function to create a context store.

    Args:
        store_type: One of 'none', 'memory', 'file'.
        path: File path for 'file' type (required if type is 'file').
        ttl_ms: Default TTL for entries (not currently used by factory).

    Returns:
        ContextStore instance.

    Raises:
        ValueError: If store_type is unknown.
        NotImplementedError: If 'file' type is requested (v2 feature).
    """
    if store_type == "none":
        return NullContextStore()
    elif store_type == "memory":
        return MemoryContextStore()
    elif store_type == "file":
        raise NotImplementedError("FileContextStore is deferred to v2")
    else:
        raise ValueError(f"Unknown context store type: {store_type}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest mat_runtime/crew/tests/test_context.py -v`
Expected: All tests pass

- [ ] **Step 5: Update crew/__init__.py exports**

Add to `mat_runtime/crew/__init__.py`:

```python
from mat_runtime.crew.context import (
    ContextStore,
    MemoryContextStore,
    NullContextStore,
    create_context_store,
)

# Update __all__
__all__ = [
    # ... existing exports ...
    "ContextStore",
    "MemoryContextStore",
    "NullContextStore",
    "create_context_store",
]
```

- [ ] **Step 6: Commit**

```bash
git add mat_runtime/crew/context.py mat_runtime/crew/tests/test_context.py mat_runtime/crew/__init__.py
git commit -m "feat(crew): add context.py with MemoryContextStore and NullContextStore (MAT-43)"
```

---

### Task 7: Implement hooks.py (HookRunner)

**Files:**
- Create: `mat_runtime/crew/hooks.py`
- Create: `mat_runtime/crew/tests/test_hooks.py`

- [ ] **Step 1: Write failing test for HookRunner**

Create `mat_runtime/crew/tests/test_hooks.py`:

```python
"""Tests for HookRunner."""

from __future__ import annotations

import asyncio
import stat
import tempfile
from pathlib import Path

import pytest

from mat_runtime.crew.hooks import HookRunner
from mat_runtime.crew.definition import HooksConfig


@pytest.fixture
def hooks_dir(tmp_path: Path) -> Path:
    """Create a temp directory with executable hook scripts."""
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    return scripts


def create_script(path: Path, content: str, exit_code: int = 0) -> None:
    """Create an executable script."""
    script = f"""#!/bin/bash
{content}
exit {exit_code}
"""
    path.write_text(script)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


class TestHookRunner:
    """Tests for HookRunner."""

    @pytest.mark.asyncio
    async def test_run_existing_hook(self, hooks_dir: Path) -> None:
        """Run a hook that exists and succeeds."""
        script = hooks_dir / "on_start.sh"
        create_script(script, "echo 'started'")

        config = HooksConfig(
            on_start="scripts/on_start.sh",
            on_start_timeout_ms=5000,
        )
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = await runner.run("on_start", {"crew": "test-crew"})

        assert result.ok
        assert result.hook_name == "on_start"

    @pytest.mark.asyncio
    async def test_run_nonexistent_hook_no_error(self, hooks_dir: Path) -> None:
        """Running a hook that's not configured is a no-op."""
        config = HooksConfig()  # No hooks configured
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = await runner.run("on_start", {})

        assert result.ok
        assert result.skipped

    @pytest.mark.asyncio
    async def test_run_missing_script_non_fatal(self, hooks_dir: Path) -> None:
        """Missing script file is non-fatal, returns error result."""
        config = HooksConfig(on_start="scripts/missing.sh")
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = await runner.run("on_start", {})

        assert not result.ok
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_timeout_kills_process(self, hooks_dir: Path) -> None:
        """Hook that exceeds timeout is killed."""
        script = hooks_dir / "slow.sh"
        create_script(script, "sleep 10")

        config = HooksConfig(
            on_start="scripts/slow.sh",
            on_start_timeout_ms=100,  # 100ms timeout
        )
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = await runner.run("on_start", {})

        assert not result.ok
        assert result.timeout_exceeded

    @pytest.mark.asyncio
    async def test_hook_failure_non_fatal(self, hooks_dir: Path) -> None:
        """Hook that exits non-zero is non-fatal."""
        script = hooks_dir / "failing.sh"
        create_script(script, "echo 'oops'", exit_code=1)

        config = HooksConfig(on_start="scripts/failing.sh")
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = await runner.run("on_start", {})

        assert not result.ok
        assert result.return_code == 1

    @pytest.mark.asyncio
    async def test_context_passed_as_env(self, hooks_dir: Path) -> None:
        """Context dict is passed as environment variables."""
        script = hooks_dir / "env_check.sh"
        create_script(script, 'echo "CREW=$MAT_CREW"')

        config = HooksConfig(on_start="scripts/env_check.sh")
        runner = HookRunner(config, repo_root=hooks_dir.parent)

        result = await runner.run("on_start", {"crew": "my-crew"})

        assert result.ok
        assert "CREW=my-crew" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mat_runtime/crew/tests/test_hooks.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement hooks.py**

```python
"""Hook runner for crew lifecycle events."""

from __future__ import annotations

import asyncio
import os
import signal
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mat_runtime.crew.definition import HooksConfig


@dataclass
class HookResult:
    """Result of running a hook."""

    ok: bool
    hook_name: str
    skipped: bool = False
    timeout_exceeded: bool = False
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str = ""
    duration_ms: int = 0


class HookRunner:
    """
    Runs lifecycle hooks with per-hook timeouts.

    Hook failures are non-fatal - they emit results but don't
    abort the crew operation.
    """

    def __init__(self, config: HooksConfig, repo_root: Path | str):
        self._config = config
        self._repo_root = Path(repo_root)

    def _get_hook_path(self, hook_name: str) -> str | None:
        """Get the configured path for a hook."""
        return getattr(self._config, hook_name, None)

    def _get_hook_timeout(self, hook_name: str) -> int:
        """Get the configured timeout for a hook in ms."""
        timeout_attr = f"{hook_name}_timeout_ms"
        return getattr(self._config, timeout_attr, 30000)

    async def run(self, hook_name: str, context: dict[str, Any]) -> HookResult:
        """
        Run a lifecycle hook.

        Args:
            hook_name: Name of the hook (e.g., 'on_start', 'on_task_complete').
            context: Context dict to pass as environment variables.

        Returns:
            HookResult indicating success/failure. Failures are non-fatal.
        """
        import time

        start_time = time.monotonic()

        # Check if hook is configured
        hook_path = self._get_hook_path(hook_name)
        if not hook_path:
            return HookResult(
                ok=True,
                hook_name=hook_name,
                skipped=True,
            )

        # Resolve full path
        full_path = self._repo_root / hook_path

        # Check if script exists
        if not full_path.exists():
            return HookResult(
                ok=False,
                hook_name=hook_name,
                error=f"Hook script not found: {full_path}",
                duration_ms=int((time.monotonic() - start_time) * 1000),
            )

        # Build environment with MAT_ prefix for context
        env = os.environ.copy()
        for key, value in context.items():
            env_key = f"MAT_{key.upper()}"
            env[env_key] = str(value)

        # Get timeout
        timeout_ms = self._get_hook_timeout(hook_name)
        timeout_sec = timeout_ms / 1000

        try:
            proc = await asyncio.create_subprocess_exec(
                str(full_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._repo_root),
                env=env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_sec,
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")

                duration_ms = int((time.monotonic() - start_time) * 1000)

                return HookResult(
                    ok=proc.returncode == 0,
                    hook_name=hook_name,
                    return_code=proc.returncode,
                    stdout=stdout,
                    stderr=stderr,
                    duration_ms=duration_ms,
                )

            except asyncio.TimeoutError:
                # Kill the process
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass  # Already terminated

                duration_ms = int((time.monotonic() - start_time) * 1000)

                return HookResult(
                    ok=False,
                    hook_name=hook_name,
                    timeout_exceeded=True,
                    error=f"Hook timed out after {timeout_ms}ms",
                    duration_ms=duration_ms,
                )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return HookResult(
                ok=False,
                hook_name=hook_name,
                error=str(e),
                duration_ms=duration_ms,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest mat_runtime/crew/tests/test_hooks.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add mat_runtime/crew/hooks.py mat_runtime/crew/tests/test_hooks.py
git commit -m "feat(crew): add hooks.py with HookRunner and per-hook timeouts (MAT-43)"
```

---

### Task 8: Implement routing.py (RoutingStrategy Protocol)

**Files:**
- Create: `mat_runtime/crew/routing.py`
- Create: `mat_runtime/crew/tests/test_routing.py`

- [ ] **Step 1: Write failing tests for routing strategies**

Create `mat_runtime/crew/tests/test_routing.py`:

```python
"""Tests for routing strategies."""

from __future__ import annotations

import pytest

from mat_runtime.crew.definition import AgentRef
from mat_runtime.crew.routing import (
    RoutingState,
    RoundRobinStrategy,
    PriorityStrategy,
    RandomStrategy,
    CapabilityStrategy,
    create_routing_strategy,
)
from mat_runtime.crew.types import CrewTask


@pytest.fixture
def agents() -> list[AgentRef]:
    """Sample agents for testing."""
    return [
        AgentRef(name="coder", priority=5),
        AgentRef(name="reviewer", priority=10),
        AgentRef(name="tester", priority=3),
    ]


@pytest.fixture
def agent_definitions() -> dict[str, dict]:
    """Mock agent definitions with specializations."""
    return {
        "coder": {
            "specialization": {
                "languages": ["python", "typescript"],
                "frameworks": ["django", "react"],
            }
        },
        "reviewer": {
            "specialization": {
                "languages": ["python"],
                "domain": "security",
            }
        },
        "tester": {
            "specialization": {
                "languages": ["python"],
                "tags": ["testing", "qa"],
            }
        },
    }


class TestRoundRobinStrategy:
    """Tests for round-robin routing."""

    def test_cycles_through_agents(self, agents: list[AgentRef]) -> None:
        strategy = RoundRobinStrategy()
        state = RoutingState()
        task = CrewTask(instruction="test")

        # First call: coder (index 0)
        result = strategy.select(agents, task, state)
        assert result.name == "coder"

        # Simulate state update
        state.task_count = 1

        # Second call: reviewer (index 1)
        result = strategy.select(agents, task, state)
        assert result.name == "reviewer"

        state.task_count = 2

        # Third call: tester (index 2)
        result = strategy.select(agents, task, state)
        assert result.name == "tester"

        state.task_count = 3

        # Fourth call: back to coder (index 0)
        result = strategy.select(agents, task, state)
        assert result.name == "coder"


class TestPriorityStrategy:
    """Tests for priority-based routing."""

    def test_selects_highest_priority(self, agents: list[AgentRef]) -> None:
        strategy = PriorityStrategy()
        state = RoutingState()
        task = CrewTask(instruction="test")

        result = strategy.select(agents, task, state)
        assert result.name == "reviewer"  # Priority 10

    def test_consistent_on_tie(self) -> None:
        """When priorities tie, selection is deterministic."""
        agents = [
            AgentRef(name="a", priority=5),
            AgentRef(name="b", priority=5),
        ]
        strategy = PriorityStrategy()
        state = RoutingState()
        task = CrewTask(instruction="test")

        # Should consistently return the same agent
        results = [strategy.select(agents, task, state) for _ in range(5)]
        assert all(r.name == results[0].name for r in results)


class TestRandomStrategy:
    """Tests for random routing."""

    def test_returns_valid_agent(self, agents: list[AgentRef]) -> None:
        strategy = RandomStrategy()
        state = RoutingState()
        task = CrewTask(instruction="test")

        for _ in range(10):
            result = strategy.select(agents, task, state)
            assert result in agents


class TestCapabilityStrategy:
    """Tests for capability-based routing."""

    def test_matches_language(
        self,
        agents: list[AgentRef],
        agent_definitions: dict[str, dict],
    ) -> None:
        strategy = CapabilityStrategy(
            agent_definitions=agent_definitions,
            match_on=["languages"],
            fallback="round-robin",
        )
        state = RoutingState()
        task = CrewTask(
            instruction="test",
            required_capabilities=["typescript"],
        )

        result = strategy.select(agents, task, state)
        assert result.name == "coder"  # Only coder has typescript

    def test_fallback_when_no_match(
        self,
        agents: list[AgentRef],
        agent_definitions: dict[str, dict],
    ) -> None:
        strategy = CapabilityStrategy(
            agent_definitions=agent_definitions,
            match_on=["languages"],
            fallback="round-robin",
        )
        state = RoutingState()
        task = CrewTask(
            instruction="test",
            required_capabilities=["rust"],  # No one has rust
        )

        # Should fall back to round-robin (first agent)
        result = strategy.select(agents, task, state)
        assert result.name == "coder"

    def test_fallback_when_no_capabilities(
        self,
        agents: list[AgentRef],
        agent_definitions: dict[str, dict],
    ) -> None:
        strategy = CapabilityStrategy(
            agent_definitions=agent_definitions,
            match_on=["languages"],
            fallback="priority",
        )
        state = RoutingState()
        task = CrewTask(instruction="test")  # No required_capabilities

        # Should fall back to priority (reviewer has highest)
        result = strategy.select(agents, task, state)
        assert result.name == "reviewer"


class TestCreateRoutingStrategy:
    """Tests for strategy factory."""

    def test_create_round_robin(self) -> None:
        strategy = create_routing_strategy("round-robin")
        assert isinstance(strategy, RoundRobinStrategy)

    def test_create_priority(self) -> None:
        strategy = create_routing_strategy("priority")
        assert isinstance(strategy, PriorityStrategy)

    def test_create_random(self) -> None:
        strategy = create_routing_strategy("random")
        assert isinstance(strategy, RandomStrategy)

    def test_create_capability(self) -> None:
        strategy = create_routing_strategy(
            "capability",
            agent_definitions={},
            match_on=["languages"],
            fallback="round-robin",
        )
        assert isinstance(strategy, CapabilityStrategy)

    def test_unknown_strategy_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown routing strategy"):
            create_routing_strategy("unknown")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest mat_runtime/crew/tests/test_routing.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement routing.py**

```python
"""Routing strategies for task assignment."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Protocol

from mat_runtime.crew.definition import AgentRef
from mat_runtime.crew.types import CrewTask


@dataclass
class RoutingState:
    """
    Read-only state passed to routing strategies.

    Strategies read this but never mutate it. The Crew class
    maintains and updates this state.
    """

    task_count: int = 0
    agent_task_counts: dict[str, int] = field(default_factory=dict)
    last_agent: str | None = None


class RoutingStrategy(Protocol):
    """Protocol for routing strategy implementations."""

    def select(
        self,
        agents: list[AgentRef],
        task: CrewTask,
        state: RoutingState,
    ) -> AgentRef:
        """
        Select an agent for a task.

        Args:
            agents: Available agents to choose from.
            task: The task to be assigned.
            state: Current routing state (read-only).

        Returns:
            The selected agent.
        """
        ...


class RoundRobinStrategy:
    """Cycles through agents in order."""

    def select(
        self,
        agents: list[AgentRef],
        task: CrewTask,
        state: RoutingState,
    ) -> AgentRef:
        index = state.task_count % len(agents)
        return agents[index]


class PriorityStrategy:
    """Selects agent with highest priority."""

    def select(
        self,
        agents: list[AgentRef],
        task: CrewTask,
        state: RoutingState,
    ) -> AgentRef:
        return max(agents, key=lambda a: a.priority)


class RandomStrategy:
    """Selects a random agent."""

    def select(
        self,
        agents: list[AgentRef],
        task: CrewTask,
        state: RoutingState,
    ) -> AgentRef:
        return random.choice(agents)


class CapabilityStrategy:
    """
    Matches task required_capabilities against agent specializations.

    Falls back to a secondary strategy when no match is found or
    when the task has no required_capabilities.
    """

    def __init__(
        self,
        agent_definitions: dict[str, Any],
        match_on: list[str],
        fallback: str = "round-robin",
    ):
        self._agent_defs = agent_definitions
        self._match_on = match_on
        self._fallback = self._create_fallback(fallback)

    def _create_fallback(self, strategy_name: str) -> RoutingStrategy:
        """Create the fallback strategy."""
        if strategy_name == "round-robin":
            return RoundRobinStrategy()
        elif strategy_name == "priority":
            return PriorityStrategy()
        elif strategy_name == "random":
            return RandomStrategy()
        else:
            return RoundRobinStrategy()

    def _get_agent_capabilities(self, agent_name: str) -> set[str]:
        """Extract all capability values from agent specialization."""
        agent_def = self._agent_defs.get(agent_name, {})
        spec = agent_def.get("specialization", {})

        capabilities: set[str] = set()
        for field in self._match_on:
            value = spec.get(field)
            if isinstance(value, list):
                capabilities.update(value)
            elif isinstance(value, str):
                capabilities.add(value)

        return capabilities

    def _score_agent(self, agent: AgentRef, required: set[str]) -> int:
        """Score an agent by how many required capabilities it has."""
        capabilities = self._get_agent_capabilities(agent.name)
        return len(capabilities & required)

    def select(
        self,
        agents: list[AgentRef],
        task: CrewTask,
        state: RoutingState,
    ) -> AgentRef:
        # No required capabilities -> use fallback
        if not task.required_capabilities:
            return self._fallback.select(agents, task, state)

        required = set(task.required_capabilities)

        # Score all agents
        scored = [(agent, self._score_agent(agent, required)) for agent in agents]

        # Find best match
        best_score = max(score for _, score in scored)

        if best_score == 0:
            # No matches -> use fallback
            return self._fallback.select(agents, task, state)

        # Return first agent with best score
        for agent, score in scored:
            if score == best_score:
                return agent

        # Should never reach here
        return self._fallback.select(agents, task, state)


def create_routing_strategy(
    strategy: str,
    agent_definitions: dict[str, Any] | None = None,
    match_on: list[str] | None = None,
    fallback: str = "round-robin",
) -> RoutingStrategy:
    """
    Factory function to create a routing strategy.

    Args:
        strategy: Strategy name ('round-robin', 'priority', 'random', 'capability').
        agent_definitions: Agent definitions (required for capability strategy).
        match_on: Fields to match on (required for capability strategy).
        fallback: Fallback strategy for capability routing.

    Returns:
        RoutingStrategy instance.

    Raises:
        ValueError: If strategy is unknown.
    """
    if strategy == "round-robin":
        return RoundRobinStrategy()
    elif strategy == "priority":
        return PriorityStrategy()
    elif strategy == "random":
        return RandomStrategy()
    elif strategy == "capability":
        return CapabilityStrategy(
            agent_definitions=agent_definitions or {},
            match_on=match_on or [],
            fallback=fallback,
        )
    else:
        raise ValueError(f"Unknown routing strategy: {strategy}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest mat_runtime/crew/tests/test_routing.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add mat_runtime/crew/routing.py mat_runtime/crew/tests/test_routing.py
git commit -m "feat(crew): add routing.py with 4 routing strategies (MAT-43)"
```

---

### Task 9: Implement crew.py (Crew Class) - Part 1: Core Structure

**Files:**
- Create: `mat_runtime/crew/crew.py`

- [ ] **Step 1: Create crew.py with initialization and lifecycle**

```python
"""Crew orchestration class."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mat_runtime.crew.context import ContextStore, create_context_store
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
        definition_path: str | Path,
        repo_root: str | Path | None = None,
        router: AgentRouter | None = None,
    ):
        """
        Initialize a Crew from a definition file.

        Args:
            definition_path: Path to the crew definition JSON file.
            repo_root: Repository root. Defaults to definition file's parent.
            router: AgentRouter instance. Created if not provided.

        Raises:
            ValueError: If any referenced agent is unknown.
        """
        self._definition = load_crew_definition(definition_path)
        self._repo_root = Path(repo_root) if repo_root else Path(definition_path).parent

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

        # Check max_tasks constraint
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

        # Acquire semaphore if configured
        if self._semaphore:
            await self._semaphore.acquire()

        try:
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

            # Execute with retry loop
            result = await self._execute_with_retry(selected, task)

            # Update state
            self._task_count += 1
            self._routing_state.task_count = self._task_count
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
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from mat_runtime.crew.crew import Crew; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add mat_runtime/crew/crew.py
git commit -m "feat(crew): add crew.py with Crew class orchestration (MAT-43)"
```

---

### Task 10: Add Tests for Crew Class

**Files:**
- Create: `mat_runtime/crew/tests/test_crew.py`

- [ ] **Step 1: Write tests for Crew class**

```python
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
        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0

        async def slow_invoke(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.05)
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest mat_runtime/crew/tests/test_crew.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add mat_runtime/crew/tests/test_crew.py
git commit -m "test(crew): add tests for Crew orchestration class (MAT-43)"
```

---

### Task 11: Update Package Exports

**Files:**
- Modify: `mat_runtime/crew/__init__.py`
- Modify: `mat_runtime/__init__.py`

- [ ] **Step 1: Update crew/__init__.py with all exports**

```python
"""Crew runtime - orchestration layer for multi-agent task routing."""

from mat_runtime.crew.types import CrewTask, CrewResult
from mat_runtime.crew.definition import (
    AgentRef,
    RoutingConfig,
    ConstraintsConfig,
    HooksConfig,
    CommunicationConfig,
    CrewDefinition,
    load_crew_definition,
)
from mat_runtime.crew.context import (
    ContextStore,
    MemoryContextStore,
    NullContextStore,
    create_context_store,
)
from mat_runtime.crew.hooks import HookRunner, HookResult
from mat_runtime.crew.routing import (
    RoutingState,
    RoutingStrategy,
    RoundRobinStrategy,
    PriorityStrategy,
    RandomStrategy,
    CapabilityStrategy,
    create_routing_strategy,
)
from mat_runtime.crew.crew import Crew

__all__ = [
    # Types
    "CrewTask",
    "CrewResult",
    # Definition
    "AgentRef",
    "RoutingConfig",
    "ConstraintsConfig",
    "HooksConfig",
    "CommunicationConfig",
    "CrewDefinition",
    "load_crew_definition",
    # Context
    "ContextStore",
    "MemoryContextStore",
    "NullContextStore",
    "create_context_store",
    # Hooks
    "HookRunner",
    "HookResult",
    # Routing
    "RoutingState",
    "RoutingStrategy",
    "RoundRobinStrategy",
    "PriorityStrategy",
    "RandomStrategy",
    "CapabilityStrategy",
    "create_routing_strategy",
    # Crew
    "Crew",
]
```

- [ ] **Step 2: Update mat_runtime/__init__.py**

Add to existing `mat_runtime/__init__.py`:

```python
from mat_runtime.crew import (
    Crew,
    CrewTask,
    CrewResult,
    CrewDefinition,
    load_crew_definition,
)

# Update __all__ to include crew exports
__all__ = [
    # ... existing exports ...
    "Crew",
    "CrewTask",
    "CrewResult",
    "CrewDefinition",
    "load_crew_definition",
]
```

- [ ] **Step 3: Verify imports work**

Run: `python -c "from mat_runtime import Crew, CrewTask, CrewResult; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add mat_runtime/crew/__init__.py mat_runtime/__init__.py
git commit -m "feat(crew): update package exports for Crew runtime (MAT-43)"
```

---

### Task 12: Update __main__.py with invoke-crew Command

**Files:**
- Modify: `mat_runtime/__main__.py`

- [ ] **Step 1: Add async support and invoke-crew command**

Add to `mat_runtime/__main__.py`:

```python
import asyncio

# Add after existing imports
from mat_runtime.crew import Crew, CrewTask


async def cmd_invoke_crew_async(args: argparse.Namespace) -> int:
    """Handle the invoke-crew command (async implementation)."""
    crew = Crew(
        definition_path=args.crew,
        repo_root=args.repo_root,
    )

    await crew.start()

    try:
        task = CrewTask(
            instruction=args.instruction,
            op=args.op,
            scope_paths=args.scope_paths or [],
            timeout_ms=args.timeout_ms,
        )

        result = await crew.submit(task)

        # Output result
        output = {
            "ok": result.ok,
            "agent_used": result.agent_used,
            "correlation_id": result.correlation_id,
            "duration_ms": result.duration_ms,
            "attempts": result.attempts,
        }
        if result.ok:
            output["output"] = result.output
        else:
            output["error"] = result.error
            if result.retry_reasons:
                output["retry_reasons"] = result.retry_reasons

        print(json.dumps(output, indent=2 if args.pretty else None))
        return 0 if result.ok else 1

    finally:
        await crew.shutdown()


def cmd_invoke_crew(args: argparse.Namespace) -> int:
    """Handle the invoke-crew command."""
    return asyncio.run(cmd_invoke_crew_async(args))


# Add to main() after existing subparsers:

    # invoke-crew command
    invoke_crew_parser = subparsers.add_parser(
        "invoke-crew", help="Submit a task to a crew"
    )
    invoke_crew_parser.add_argument(
        "--crew",
        "-c",
        type=Path,
        required=True,
        help="Path to crew definition JSON file",
    )
    invoke_crew_parser.add_argument(
        "--instruction",
        "-i",
        required=True,
        help="Task instruction",
    )
    invoke_crew_parser.add_argument(
        "--op",
        "-o",
        default="codex.implement",
        help="Operation (default: codex.implement)",
    )
    invoke_crew_parser.add_argument(
        "--scope-paths",
        "-s",
        nargs="*",
        help="Scope paths",
    )
    invoke_crew_parser.add_argument(
        "--timeout-ms",
        "-t",
        type=int,
        help="Task timeout in milliseconds",
    )
    invoke_crew_parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        default=True,
        help="Pretty-print JSON output (default: true)",
    )
    invoke_crew_parser.set_defaults(func=cmd_invoke_crew)
```

- [ ] **Step 2: Verify command is registered**

Run: `python -m mat_runtime invoke-crew --help`
Expected: Shows help for invoke-crew command

- [ ] **Step 3: Commit**

```bash
git add mat_runtime/__main__.py
git commit -m "feat(cli): add invoke-crew command to mat_runtime CLI (MAT-43)"
```

---

### Task 13: Run All Tests and Final Validation

**Files:**
- All test files

- [ ] **Step 1: Run all crew tests**

Run: `pytest mat_runtime/crew/tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Run all mat_runtime tests**

Run: `pytest mat_runtime/tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Run crew schema validation**

Run: `python scripts/validate_crew.py`
Expected: All checks pass

- [ ] **Step 4: Verify end-to-end import**

Run:
```bash
python -c "
from mat_runtime import Crew, CrewTask, CrewResult
from mat_runtime.crew import (
    load_crew_definition,
    create_routing_strategy,
    create_context_store,
    HookRunner,
)
print('All imports OK')
"
```
Expected: All imports OK

- [ ] **Step 5: Create final commit**

```bash
git add -A
git commit -m "feat(crew): complete MAT-43 Crew runtime implementation

- Add per-hook timeout fields to crew schema
- Add agent_refused error code to AgentRouter
- Implement types.py with CrewTask and CrewResult
- Implement definition.py with config dataclasses and loader
- Implement context.py with MemoryContextStore and NullContextStore
- Implement hooks.py with HookRunner and per-hook timeouts
- Implement routing.py with 4 routing strategies
- Implement crew.py with Crew orchestration class
- Add comprehensive tests for all modules
- Update CLI with invoke-crew command

Closes MAT-43"
```

---

## Summary

This plan implements the MAT-43 Crew Runtime in 13 tasks:

1. Schema update (hook timeouts)
2. AgentRouter change (agent_refused)
3. Package structure + types.py
4. definition.py (config + loader)
5. Tests for definition.py
6. context.py (ContextStore)
7. hooks.py (HookRunner)
8. routing.py (4 strategies)
9. crew.py (Crew class)
10. Tests for Crew class
11. Package exports
12. CLI command
13. Final validation

Each task follows TDD with failing test first, implementation, then passing tests.
