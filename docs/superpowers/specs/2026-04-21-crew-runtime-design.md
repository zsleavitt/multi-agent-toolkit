# Crew Runtime Design (MAT-43)

**Date:** 2026-04-21  
**Status:** Approved  
**Author:** Claude + Zach  

## Overview

This document specifies the Python runtime layer for Crew orchestration. The Crew runtime executes crew definitions from `schemas/crew/v1/crew.schema.json`, routing tasks to member agents via the existing `AgentRouter` infrastructure.

## Goals

1. Load and validate crew definitions from `crews/*.json`
2. Route tasks to agents using configurable strategies (round-robin, capability, priority, random)
3. Enforce constraints (concurrency, timeout, max_tasks, retries)
4. Run lifecycle hooks with per-hook timeouts (non-fatal failures)
5. Provide shared context storage for inter-agent state
6. Design for async, implement v1 as sync-compatible

## Non-Goals

- Persistent agent processes (CLI subprocess model)
- File-based context store (deferred to future ticket)
- Message passing modes direct/broadcast (require persistent agents)
- Crew composition API (MAT-44)
- Swarm integration (MAT-45+)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Execution model | Async-first, sync v1 | Semaphore, hooks, future Hive need async |
| Task submission | `crew.submit(task)` blocks, returns result | Simple, matches sync v1 |
| Agent invocation | `asyncio.to_thread(router.invoke)` | Don't block event loop |
| Concurrency | `asyncio.Semaphore(max_concurrent_agents)` | Enforces constraint cleanly |
| Retry logic | Infrastructure failures only | Semantic failures (agent_refused) not retriable |
| Hooks | Blocking with per-hook timeout, non-fatal | Pipeline can't hang, notifications can't kill work |
| Context store | Protocol + MemoryContextStore | file deferred, NullContextStore for "none" |
| Message passing | "none" only v1 | direct/broadcast need persistent agents |
| Routing strategies | All four implemented | Simple ones trivial, capability has fallback |

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

## Types

### CrewTask

```python
@dataclass
class CrewTask:
    instruction: str
    op: str = "codex.implement"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    required_capabilities: list[str] = field(default_factory=list)
    scope_paths: list[str] = field(default_factory=list)
    timeout_ms: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

### CrewResult

```python
@dataclass
class CrewResult:
    ok: bool
    agent_used: str
    output: Any  # TODO(MAT-41): type this once structured output contracts land
    correlation_id: str
    duration_ms: int
    attempts: int = 1
    retry_reasons: list[str] = field(default_factory=list)
    error: dict[str, Any] | None = None
```

## Definition Loading

`definition.py` is stateless — loads JSON, validates against schema, normalizes agents to `list[AgentRef]`. Agent reference resolution happens in `Crew.__init__`.

### Config Types (in definition.py)

```python
@dataclass
class AgentRef:
    name: str
    timeout_ms: int | None = None
    priority: int = 0
    required_capabilities: list[str] = field(default_factory=list)

@dataclass
class RoutingConfig:
    strategy: str = "round-robin"
    match_on: list[str] = field(default_factory=list)
    fallback: str = "round-robin"
    allow_reassignment: bool = False
    prefer_idle: bool = True

@dataclass
class ConstraintsConfig:
    max_concurrent_agents: int | None = None
    timeout_ms: int | None = None
    max_tasks: int | None = None
    max_retries: int = 0
    backoff_ms: int = 1000
    backoff_multiplier: float = 2.0

@dataclass
class HooksConfig:
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
    shared_context_type: str = "none"
    shared_context_path: str | None = None
    shared_context_ttl_ms: int = 0
    message_passing_mode: str = "none"
```

### Validation

- Schema validation uses registry lookup (not hardcoded path)
- Semantic hook path validation: reject absolute paths and `..` traversal
- Agents normalized to `list[AgentRef]` at parse time (no mixed types)

## Context Store

### Protocol (async-first)

```python
class ContextStore(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl_ms: int = 0) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def keys(self) -> list[str]: ...
```

### Implementations

- `NullContextStore` — no-op for "none" mode (Null Object pattern)
- `MemoryContextStore` — in-memory dict with lazy TTL expiry
- `FileContextStore` — raises `NotImplementedError` in v1

Factory always returns a `ContextStore`, never `None`.

## Hooks

### HookRunner

- Runs lifecycle hooks with per-hook configurable timeouts (default 30s)
- **Non-fatal failures**: hook errors emit events and log, never abort the crew
- Explicit existence check before subprocess (clear error message)
- Kill timed-out processes to prevent orphans

### Hook Semantics

| Hook | Trigger | Context |
|------|---------|---------|
| `on_start` | `crew.start()` called | crew name |
| `on_task_assigned` | Agent selected, inside semaphore | task_id |
| `on_task_complete` | Agent finished | task_id, agent, ok |
| `on_agent_failure` | Non-retryable failure or retries exhausted | task_id, agent, error |
| `on_finish` | `crew.shutdown()` called | crew name, total_tasks |
| `on_error` | Crew-level error (max_tasks exceeded) | crew name, error |

## Routing Strategies

### Protocol

```python
class RoutingStrategy(Protocol):
    def select(self, agents: list[AgentRef], task: CrewTask, state: RoutingState) -> AgentRef: ...
```

Strategies are stateless — they read `RoutingState` but never mutate it.

### Implementations

| Strategy | Logic |
|----------|-------|
| `round-robin` | `agents[task_count % len(agents)]` |
| `priority` | `max(agents, key=lambda a: a.priority)` |
| `random` | `random.choice(agents)` |
| `capability` | Score agents by specialization match, fallback if no match |

### Capability Routing

- Requires `agent_definitions` injected at construction (Protocol-compatible)
- Scores against `agent.specialization` fields specified in `match_on`
- No `required_capabilities` on task → falls back to fallback strategy
- No match found → falls back to fallback strategy

### prefer_idle Handling

Pre-filter in `Crew.submit()` before calling strategy:

```python
# prefer_idle is best-effort for concurrent submissions — semaphore limits actual concurrency
candidates = self._definition.agents
if routing_config.prefer_idle and self._busy_agents:
    idle = [a for a in candidates if a.name not in self._busy_agents]
    candidates = idle if idle else candidates
```

## Retry Logic

### Retryable vs Non-Retryable

| Error Code | Retryable | Reason |
|------------|-----------|--------|
| `timeout` | Yes | Infrastructure: model overload, network blip |
| `execution_error` | Yes | Process crash, no output |
| `agent_refused` | No | Semantic: agent understood and said no |

### AgentRouter Change

Add `agent_refused` error code when agent produces output but fails:

```python
if result.timeout_exceeded:
    error_code = "timeout"
elif result.return_code < 0:
    error_code = "execution_error"
elif result.stdout.strip():
    error_code = "agent_refused"  # semantic failure
else:
    error_code = "execution_error"  # infrastructure
```

### Backoff

Exponential backoff: `backoff_ms *= backoff_multiplier` after each retry.

## Crew Class

### Initialization

```python
class Crew:
    def __init__(self, definition_path: str | Path, repo_root: str | Path | None = None):
        # Load definition
        # Resolve agent references (ValueError if unknown)
        # Initialize: AgentRouter, RoutingStrategy, ContextStore, HookRunner
        # Create semaphore for max_concurrent_agents
```

### Lifecycle

```python
await crew.start()      # on_start hook
result = await crew.submit(task)  # per-task orchestration
await crew.shutdown()   # on_finish hook
```

### submit() Flow

1. Check `max_tasks` constraint
2. Acquire semaphore
3. Run `on_task_assigned` hook
4. Select agent (with prefer_idle pre-filter)
5. Execute with retry loop (`asyncio.to_thread` for blocking invoke)
6. Update routing state
7. Release semaphore
8. Run `on_task_complete` hook
9. Return `CrewResult`

### Concurrency

```python
async with self._semaphore:
    await self._hooks.run("on_task_assigned", ...)
    result = await self._execute_with_retry(...)
```

## Schema Update (MAT-42)

Add per-hook timeout fields to `schemas/crew/v1/crew.schema.json`:

```json
"hooks": {
  "properties": {
    "on_start": { "allOf": [{ "$ref": "#/$defs/repo_relative_path" }] },
    "on_start_timeout_ms": { "type": "integer", "minimum": 1000, "default": 30000 },
    // ... same for all 6 hooks
  }
},
"$defs": {
  "repo_relative_path": {
    "type": "string",
    "minLength": 1,
    "pattern": "^[^/]",
    "description": "Path relative to repo root. Semantic traversal check in load_crew_definition."
  }
}
```

Backwards-compatible: new optional fields with defaults.

## V1 Trade-offs (Documented)

1. **task_count redundancy**: `self._task_count` mirrors `routing_state.task_count` — consolidate in v2
2. **prefer_idle race condition**: Best-effort for concurrent submissions — semaphore is the real concurrency guard

## Testing

### test_routing.py
- All 4 strategies with mock agents
- Capability fallback behavior
- RoutingState read-only contract

### test_context.py
- MemoryContextStore get/set/delete
- TTL expiry (lazy on read)
- NullContextStore no-ops

### test_hooks.py
- Timeout enforcement
- Non-fatal failure handling
- Missing script detection
- Process cleanup on timeout

### test_crew.py
- submit() happy path
- Semaphore concurrency limit
- Retry loop with backoff
- Hook invocation order

## Implementation Tasks

1. Update MAT-42 schema with hook timeout fields
2. Add `agent_refused` error code to `AgentRouter.invoke()`
3. Create `mat_runtime/crew/` package structure
4. Implement `types.py` (CrewTask, CrewResult)
5. Implement `definition.py` (loader, config classes)
6. Implement `context.py` (protocol, Memory, Null stores)
7. Implement `hooks.py` (HookRunner)
8. Implement `routing.py` (protocol, 4 strategies)
9. Implement `crew.py` (Crew class)
10. Add tests for each module
11. Update `mat_runtime/__init__.py` exports
12. Add validation script or integrate with existing

## References

- [MAT-43](https://github.com/zsleavitt/multi-agent-toolkit/issues/40) — This issue
- [MAT-42](https://github.com/zsleavitt/multi-agent-toolkit/issues/39) — Crew schema
- [MAT-44](https://github.com/zsleavitt/multi-agent-toolkit/issues/41) — Crew composition API
- [MAT-41](https://github.com/zsleavitt/multi-agent-toolkit/issues/38) — Structured output contracts
