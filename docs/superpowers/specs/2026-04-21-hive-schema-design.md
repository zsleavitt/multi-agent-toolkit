# Hive Schema Design (MAT-49)

**Date:** 2026-04-21  
**Status:** Approved  
**Author:** Claude + Zach  

## Overview

This document specifies the JSON Schema for "Hive" — the top-level orchestrator that manages multiple named Crews with inter-crew routing, dependency sequencing, and hive-wide resource limits.

**Hierarchy:**
```
Hive (MAT-49) — this issue
├── Crew (MAT-42/43/44) — sequential task routing to agents
└── Swarm (MAT-45/46/47) — parallel dispatch, consensus
      └── Agent × N (MAT-2) — each candidate is a standard MAT-2 invocation
```

## Goals

1. Define declarative schema for Hive definitions
2. Support crew references with dependency sequencing (`depends_on`)
3. Provide inter-crew routing strategies and explicit handoff rules
4. Enforce hive-wide resource limits and quotas in schema
5. Align with existing MAT schema patterns (Crew, Swarm)
6. Enable independent validation without Hive runtime

## Non-Goals

- Runtime implementation (MAT-50)
- Shared memory across crews (MAT-51)
- Observability hooks and telemetry (MAT-52)
- Swarm membership in Hive v1 — deferred; Hive v1 manages Crews only
- Dynamic crew discovery at runtime — refs must resolve to `crews/{ref}.json`

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Schema structure | Grouped (like Crew) | Organized sections: identity, crews, global_config, inter_crew_routing |
| Crew references | `ref` string matching `crews/{ref}.json` | Consistent with agent refs in Crew schema |
| Sequencing | `depends_on` on crew entries | Explicit DAG; runtime uses topological order |
| Routing strategies | `sequential`, `capability`, `dependency`, `manual` | Cover common orchestration patterns |
| File location | `hives/` directory | Parallel to `crews/` and `swarms/` |
| Validation | Schema + Python belt-and-suspenders | Schema catches early; Python gives readable errors for refs and cycles |
| Swarms in Hive | Deferred to v2 | v1 focuses on Crew orchestration; Swarm integration needs runtime design |

## Schema Structure

### File Locations

```
schemas/hive/v1/
  hive.schema.json      # The schema
  manifest.json         # Bundle metadata
  examples/
    valid/
      dev-pipeline.json
      minimal-hive.json
    invalid/
      circular-depends-on.json
      missing-crews.json

hives/
  README.md
  {hive-name}.json      # Actual hive definitions
```

### Core Identity

```json
{
  "schema_version": "1.0.0",
  "name": "dev-pipeline",
  "description": "Implement then review using dev and review crews",
  "shared_goal": "Ship features with TDD and security review"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | `"1.0.0"` for v1 |
| `name` | string | Yes | Unique hive identifier (lowercase, hyphens) |
| `description` | string | No | Human-readable purpose |
| `shared_goal` | string | No | Goal text injected into crew context when dispatched |

### Crews

```json
{
  "crews": [
    { "ref": "dev-crew" },
    {
      "ref": "review-crew",
      "depends_on": ["dev-crew"],
      "role": "review"
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `crews` | array | Yes | At least one crew reference |
| `crews[].ref` | string | Yes | Crew name; must exist as `crews/{ref}.json` |
| `crews[].depends_on` | array | No | Crew refs that must complete before this crew starts |
| `crews[].role` | string | No | Optional label for routing rules (e.g. `"review"`) |

### Global Config

```json
{
  "global_config": {
    "max_concurrent_crews": 2,
    "timeout_ms": 3600000,
    "max_tasks": 50,
    "quotas": {
      "max_agent_invocations": 200
    }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `max_concurrent_crews` | integer | Maximum crews running simultaneously (1–100) |
| `timeout_ms` | integer | Hive-level timeout (1s–24h) |
| `max_tasks` | integer | Maximum tasks before hive auto-terminates |
| `quotas.max_agent_invocations` | integer | Cap on total MAT-2 invocations across all crews |

### Inter-Crew Routing

```json
{
  "inter_crew_routing": {
    "strategy": "sequential",
    "default_handoff": "on_success",
    "rules": [
      {
        "from": "dev-crew",
        "to": "review-crew",
        "when": "task_complete",
        "condition": "success"
      }
    ]
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strategy` | enum | `sequential` | `sequential`, `capability`, `dependency`, `manual` |
| `default_handoff` | enum | `on_success` | `on_success`, `always`, `never` |
| `rules` | array | — | Explicit routing rules (required for `manual`) |
| `rules[].from` | string | Yes | Source crew ref |
| `rules[].to` | string | Yes | Target crew ref |
| `rules[].when` | enum | Yes | `task_complete`, `crew_complete`, `error` |
| `rules[].condition` | enum | No | `success`, `failure`, `any` |

**Routing strategies:**

| Strategy | Behavior |
|----------|----------|
| `sequential` | Process crews in declaration order, respecting `depends_on` |
| `capability` | Route tasks to crews by `role` label (runtime) |
| `dependency` | Follow `depends_on` graph only; ignore declaration order |
| `manual` | Use explicit `rules` only |

## Integration Points

### Crew (MAT-42/43/44)

- Hive references crews by `ref`; each ref must resolve to `crews/{ref}.json`
- `CrewRegistry` loads crew definitions; Hive runtime (MAT-50) will use the same registry
- Crew-level routing, constraints, and hooks remain in crew definitions — Hive does not override them in v1

### Swarm (MAT-45)

- Not included in Hive v1 schema
- Future v2 may add optional `swarms[]` for parallel review within a hive stage

### Validation (`scripts/validate_hive.py`)

1. JSON Schema validation (Draft 2020-12)
2. Semantic checks:
   - Each `crews[].ref` exists as `crews/{ref}.json`
   - No duplicate crew refs within a hive
   - `depends_on` entries reference crew refs in the hive
   - No circular dependencies (topological sort)
   - `inter_crew_routing.rules[].from` / `.to` reference crew refs in the hive
   - Filename matches `name` for `hives/*.json`

## V1 Trade-offs

| Feature | v1 Status | Notes |
|---------|-----------|-------|
| Crew refs + depends_on | Parsed + validated | Runtime executes sequencing in MAT-50 |
| inter_crew_routing rules | Parsed + validated | Handoff execution deferred to MAT-50 |
| global_config quotas | Parsed | Enforcement deferred to MAT-50 |
| capability routing strategy | Schema only | Requires runtime task classification |
| Swarms in Hive | Not in schema | Deferred to v2 |
| Hooks | Not in schema | Deferred to MAT-52 (observability) |
| shared_goal injection | Documented | Runtime behavior in MAT-50 |

## See Also

- [Crew Schema Design](./2026-04-20-crew-schema-design.md)
- [Swarm Schema Design](./2026-04-21-swarm-schema-design.md)
- [MAT-49 Issue](https://github.com/zsleavitt/multi-agent-toolkit/issues/46)
- [MAT-50 Hive Runtime](https://github.com/zsleavitt/multi-agent-toolkit/issues/47)
