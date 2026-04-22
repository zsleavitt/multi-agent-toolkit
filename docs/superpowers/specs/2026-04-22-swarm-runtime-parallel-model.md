# Swarm Runtime: Parallel Model Dispatch (MAT-46)

**Date:** 2026-04-22  
**Status:** Approved  
**Author:** Claude + Zach  

## Overview

Implement the Swarm runtime for `parallel_model` dispatch mode. This sends the same task to multiple CLI adapters (claude, codex, gemini) simultaneously and returns the first successful response.

## Goals

1. Load and validate swarm definitions from `swarms/*.json`
2. Dispatch same prompt to N CLI adapters concurrently
3. Implement `first-complete` consensus (first `ok == True` response)
4. Collect timing metadata for all candidates
5. Follow patterns established in `mat_runtime/crew/`

## Non-Goals

- `variant` dispatch mode (MAT-47)
- `majority-vote` consensus (MAT-48) — requires semantic comparison or test execution
- `synthesis` consensus (MAT-50) — requires meta-agent
- `fail_fast` cancellation (deferred to v2)
- Crew-level timeout enforcement (mirrors Crew v1 trade-off)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Module structure | Mirror `mat_runtime/crew/` | Consistency, proven patterns |
| Parallel dispatch | `asyncio.gather()` | Simple, wait-for-all semantics for v1 |
| First-complete definition | First `ok == True` | Returning fastest error isn't useful consensus |
| Error handling | Catch inside `_invoke_candidate` | Clean type safety in `_apply_consensus` |
| All candidates wait | Yes (no cancellation) | `fail_fast` deferred to v2 |

## Module Structure

```
mat_runtime/swarm/
  __init__.py           # Exports Swarm, SwarmTask, SwarmResult
  definition.py         # SwarmDefinition dataclass + load_swarm_definition()
  types.py              # SwarmTask, SwarmResult, CandidateResult
  swarm.py              # Main Swarm class with dispatch()
  tests/
    __init__.py
    test_definition.py  # Definition loading tests
    test_swarm.py       # Dispatch and consensus tests
```

## Types

### SwarmTask

```python
@dataclass
class SwarmTask:
    """Task submitted to a Swarm for parallel dispatch."""
    
    instruction: str
    op: str = "codex.implement"
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timeout_ms: int | None = None
```

### CandidateResult

```python
@dataclass
class CandidateResult:
    """Result from a single candidate in the swarm."""
    
    candidate: str          # CLI adapter name (e.g., "claude", "codex")
    ok: bool
    response: InvocationResult | None  # CLIAdapter.invoke() return type
    duration_ms: int
    error: str | None = None
```

### SwarmResult

```python
@dataclass
class SwarmResult:
    """Result of swarm dispatch with consensus applied."""
    
    ok: bool
    consensus_strategy: str
    winning_candidate: str | None
    output: Any
    correlation_id: str
    duration_ms: int
    candidate_results: list[CandidateResult]  # All results for observability
    error: dict[str, Any] | None = None
```

## Definition Loading

### SwarmDefinition

```python
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
```

### Loader

```python
def load_swarm_definition(path: Path | str) -> SwarmDefinition:
    """
    Load and parse a swarm definition from JSON.
    
    Validates:
    - dispatch_mode is "parallel_model" (variant not supported in MAT-46)
    - consensus_strategy is valid for dispatch_mode
    - candidates list has >= 2 items
    
    Raises:
        ValueError: If definition is invalid or uses unsupported mode.
    """
```

## Swarm Class

### Initialization

```python
class Swarm:
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
```

Validates:
- `dispatch_mode == "parallel_model"` (MAT-47 adds variant support)
- All candidates exist in `ADAPTER_REGISTRY`

### Dispatch

```python
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
```

### Internal Methods

```python
async def _invoke_candidate(
    self,
    candidate: str,
    task: SwarmTask,
) -> CandidateResult:
    """
    Invoke a single candidate adapter.
    
    Never raises — catches all exceptions and returns CandidateResult
    with ok=False and error message. This ensures _apply_consensus
    always receives list[CandidateResult] without type checking.
    """
    start = time.monotonic()
    try:
        timeout = task.timeout_ms if task.timeout_ms is not None else self._definition.constraints.timeout_ms
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
```

## Consensus: first-complete

**Definition:** Return the first response where `InvocationResult.ok == True`.

**Algorithm:**
1. Sort `candidate_results` by `duration_ms` ascending
2. Find first result where `ok == True`
3. If found: return success with that candidate's output
4. If none: return failure with aggregated error info

**Edge cases:**
- All candidates fail: Return `ok=False` with error listing all failures
- All candidates timeout: Same as all fail (timeout is `ok=False`)

## V1 Trade-offs

1. **`asyncio.gather()` vs `asyncio.as_completed()`** — v1 uses `gather()` which waits for all candidates before returning. This is correct for v1 (no `fail_fast`). The v2 upgrade path when `fail_fast` ships: replace `gather()` with `as_completed()` to get real arrival order and cancel remaining tasks on first success. The timing-sort approach won't survive that refactor cleanly — will need task cancellation via `asyncio.Task.cancel()`.

2. **No variant mode** — `dispatch_mode: "variant"` raises `ValueError`. MAT-47 adds support.

3. **No majority-vote** — Consensus strategy `majority-vote` is not implemented. Real majority-vote for code requires test execution or meta-agent comparison — both are MAT-48 territory.

4. **Swarm-level timeout not enforced** — `constraints.timeout_ms` is parsed but not enforced as an overall deadline. Per-candidate timeouts via the CLI adapter are enforced. Mirrors Crew v1 trade-off.

## Integration Points

| Integration | Description |
|-------------|-------------|
| `mat_runtime/adapters/` | Uses `ADAPTER_REGISTRY`, `get_adapter()`, and `InvocationResult` for CLI invocation |
| `schemas/swarm/v1/` | Definition files validated against swarm schema |
| MAT-47 | Will add `variant` mode support to same module |
| MAT-48 | Will add `majority-vote` and `synthesis` consensus |

## Testing Strategy

### Unit Tests

**test_definition.py:**
- Load valid parallel_model definition
- Reject variant mode (not supported in MAT-46)
- Reject invalid consensus for mode
- Reject < 2 candidates

**test_swarm.py:**
- Mock adapters returning success/failure
- Verify first-complete selects fastest success
- Verify all-fail returns aggregate error
- Verify timing metadata collected for all candidates
- Verify unknown candidate raises on init

### Integration Test (optional)

If CLI tools available, test with real `claude` adapter against a simple prompt.

## Implementation Tasks

1. Create `mat_runtime/swarm/__init__.py`
2. Create `mat_runtime/swarm/types.py` — SwarmTask, CandidateResult, SwarmResult
3. Create `mat_runtime/swarm/definition.py` — SwarmDefinition + loader
4. Create `mat_runtime/swarm/swarm.py` — Swarm class
5. Create `mat_runtime/swarm/tests/__init__.py`
6. Create `mat_runtime/swarm/tests/test_definition.py`
7. Create `mat_runtime/swarm/tests/test_swarm.py`
8. Update `mat_runtime/__init__.py` to export swarm module
9. Update `mat_runtime/__main__.py` — add `invoke-swarm` command with async entry point

## References

- [MAT-46](https://github.com/zsleavitt/multi-agent-toolkit/issues/43) — This issue
- [MAT-45](../../../schemas/swarm/v1/manifest.json) — Swarm schema
- [MAT-47](https://github.com/zsleavitt/multi-agent-toolkit/issues/44) — Variant dispatch (next)
- [MAT-48](https://github.com/zsleavitt/multi-agent-toolkit/issues/45) — Consensus layer
- [Crew runtime](../../../mat_runtime/crew/) — Pattern reference
