# Hive Runtime Design (MAT-50)

**Date:** 2026-04-22  
**Status:** Approved  
**Author:** Claude + Zach  

## Overview

Implement the Python runtime for Hive — the top-level orchestrator that loads hive definitions, routes tasks across multiple Crews, manages cross-crew sessions/handoffs, and enforces hive-wide limits.

**Hierarchy:**
```
Hive (MAT-50) — this spec
├── Crew (MAT-42/43/44) — mat_runtime/crew/
└── Swarm (MAT-45/46/47) — mat_runtime/swarm/ (not in Hive v1)
```

## Goals

1. Load and validate hive definitions from `hives/*.json`
2. Route tasks to appropriate Crews via inter-crew routing strategies
3. Manage in-memory sessions with correlation_id threading and handoff context
4. Evaluate explicit handoff rules between crew stages
5. Enforce hive-wide limits (`max_tasks`, `max_concurrent_crews`, quotas)
6. Follow patterns established in `mat_runtime/crew/` and `mat_runtime/swarm/`

## Non-Goals

- Shared memory store across crews (MAT-51)
- Structured observability hooks and telemetry (MAT-52)
- Swarm-in-Hive dispatch (v2)
- Persistent session storage
- Dynamic crew discovery beyond `crews/{ref}.json`

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Module structure | Mirror `mat_runtime/crew/` | Consistency, proven patterns |
| Crew resolution | Reuse `CrewRegistry` | Single source of truth for crew definitions |
| Async API | `async def submit()` | Align with Crew runtime |
| Semantic validation | Shared `mat_runtime/hive/validation.py` | Avoid duplicating cycle detection in loader and script |
| Session store | In-memory dict on `HiveSession` | MAT-51 replaces with real store |
| Hooks | No-op `HookRunner` stub | Schema has no hook fields until MAT-52 |
| Handoff precedence | Explicit rules override `default_handoff` | Matches schema semantics |
| Pipeline stop | Break on failed stage when `default_handoff: on_success` | dev-pipeline stops after dev-crew failure |

## Module Structure

```
mat_runtime/hive/
  __init__.py           # Public exports
  definition.py         # HiveDefinition dataclass + load_hive_definition()
  types.py              # HiveTask, HiveResult, HiveSession, HandoffContext
  routing.py            # Inter-crew strategies + handoff evaluation
  hive.py               # Main Hive class with submit()
  registry.py           # HiveRegistry for hives/*.json discovery
  hooks.py              # No-op HookRunner (MAT-52 placeholder)
  validation.py         # Semantic validation shared with validate_hive.py
  tests/
    test_definition.py
    test_routing.py
    test_hive.py
```

## Types

### HiveTask

Task submitted to a Hive. Extends Crew task fields with optional `role` for capability routing.

### HiveResult

Aggregated outcome across one or more crew stages. `ok` reflects the final stage. Includes `agent_invocations` summed from crew attempt counts.

### HiveSession

In-memory session keyed by `correlation_id`. Tracks `completed_crews`, `stage_results`, and `shared_context` (previous crew outputs for handoff injection).

### HandoffContext

Bundle for handoff rule evaluation: source/target crew, `when` trigger, stage result, shared context.

## submit() Pipeline Flow

For `hives/dev-pipeline.json`:

1. Check `global_config.max_tasks` (inside crew semaphore)
2. Build execution order from routing strategy
3. For each crew in order:
   - Verify `depends_on` satisfied (successful completion)
   - If not first stage, evaluate handoff from previous crew
   - Acquire hive crew semaphore (`max_concurrent_crews`)
   - Resolve Crew via `CrewRegistry.get_crew(ref)`
   - Build `CrewTask` with `HIVE GOAL:` prefix and previous stage context
   - `await crew.submit(crew_task)`
   - Accumulate `CrewStageResult`, update session
   - Enforce `quotas.max_agent_invocations`
   - Stop pipeline on failure when `default_handoff: on_success`
4. Return `HiveResult` with all stages

## Routing Strategies

| Strategy | Behavior |
|----------|----------|
| `sequential` | Declaration order |
| `dependency` | Topological order from `depends_on` |
| `capability` | Crews matching `HiveTask.role` first, then remainder in declaration order |
| `manual` | Follow explicit `rules` chain; requires rules array |

## Handoff Evaluation

Rules match on `(from, to, when)`. Condition (`success`, `failure`, `any`) gates transition. When no rule matches, `default_handoff` applies:

| default_handoff | Behavior |
|-----------------|----------|
| `on_success` | Continue only if previous stage succeeded |
| `always` | Always continue to next crew in order |
| `never` | Never continue unless explicit rule matches |

## V1 Trade-offs

| Feature | v1 Status | Notes |
|---------|-----------|-------|
| Crew refs + depends_on | Fully enforced | Loader + runtime |
| inter_crew_routing rules | Fully enforced | Handoff between stages |
| global_config quotas | Enforced | max_tasks, max_agent_invocations |
| Hive timeout_ms | Basic elapsed check | Per-stage crew timeouts via CrewTask |
| shared_goal injection | Implemented | Prepended to crew instruction |
| Session shared_context | In-memory only | MAT-51 |
| Hooks | No-op stub | MAT-52 |
| Swarms in Hive | Not supported | v2 |

## CLI

```bash
python -m mat_runtime invoke-hive \
  --hive dev-pipeline \
  --instruction "Implement X" \
  --repo-root .
```

## See Also

- [Hive Schema Design](./2026-04-21-hive-schema-design.md)
- [Crew Runtime Design](./2026-04-21-crew-runtime-design.md)
- [Swarm Runtime Design](./2026-04-22-swarm-runtime-parallel-model.md)
- [MAT-50 Issue](https://github.com/zsleavitt/multi-agent-toolkit/issues/47)
