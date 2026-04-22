# Crew Schema Design (MAT-42)

**Date:** 2026-04-20  
**Status:** Approved  
**Author:** Claude + Zach  

## Overview

This document specifies the JSON Schema for "Crew" — a named collection of agents that work together toward a shared goal with configurable routing. Crews are a foundational building block for multi-agent orchestration in MAT.

## Goals

1. Define a declarative schema for Crew definitions
2. Support flexible agent routing (round-robin, capability-based, priority-based)
3. Enable inter-agent communication within a Crew
4. Provide lifecycle hooks for external integration
5. Align with existing MAT schema patterns

## Non-Goals

- Runtime implementation (covered by MAT-43)
- Crew composition API (covered by MAT-44)
- Swarm parallel dispatch (covered by MAT-45)
- Hive multi-crew orchestration (covered by MAT-49)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent references | Mixed (name + override objects) | Flexibility: simple cases stay simple |
| Routing strategies | All (tags, domain, priority, round-robin) | Maximum flexibility for different use cases |
| Shared goal | Documentation + context injection | Agents understand their mission |
| Lifecycle | Constraints + hook references | Full control without over-complexity |
| Communication | Shared context + message passing | Self-sufficient Crews |
| File format | JSON in `crews/` | Consistent with MAT patterns |
| Schema structure | Grouped (Approach B) | Organized, extensible, self-documenting |

## Schema Structure

### File Locations

```
schemas/crew/v1/
  crew.schema.json      # The schema
  manifest.json         # Bundle metadata
  examples/
    dev-crew.json       # Example: development crew
    review-crew.json    # Example: review-only crew

crews/
  {crew-name}.json      # Actual crew definitions
```

### Core Identity

```json
{
  "name": "dev-crew",
  "description": "Full-stack development team",
  "shared_goal": "Implement features following TDD with comprehensive test coverage"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique identifier (lowercase, hyphens allowed) |
| `description` | string | No | Human-readable purpose |
| `shared_goal` | string | No | Injected into agent context when dispatched |

### Agents

Mixed mode: simple name references or objects with overrides.

```json
{
  "agents": [
    "coder",
    "tester",
    {
      "name": "reviewer",
      "timeout_ms": 120000,
      "priority": 50
    }
  ]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agents` | array | Yes | List of agent references |
| `agents[].name` | string | Yes (if object) | Agent name (must exist in `agents/`) |
| `agents[].timeout_ms` | integer | No | Override timeout for this agent |
| `agents[].priority` | integer | No | Routing priority (0-100, higher preferred) |
| `agents[].required_capabilities` | array | No | Capabilities for task routing |

### Routing

```json
{
  "routing": {
    "strategy": "capability",
    "match_on": ["tags", "domain", "languages"],
    "fallback": "round-robin",
    "task_assignment": {
      "allow_reassignment": true,
      "prefer_idle": true
    }
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strategy` | enum | `round-robin` | `round-robin`, `capability`, `priority`, `random` |
| `match_on` | array | — | Specialization fields: `tags`, `domain`, `languages`, `frameworks` |
| `fallback` | enum | `round-robin` | Strategy when no match: `round-robin`, `random`, `first-available`, `error` |
| `task_assignment.allow_reassignment` | boolean | `false` | Reassign on agent failure |
| `task_assignment.prefer_idle` | boolean | `true` | Prefer agents not working |

### Constraints

```json
{
  "constraints": {
    "max_concurrent_agents": 3,
    "timeout_ms": 300000,
    "max_tasks": 100,
    "retry_policy": {
      "max_retries": 2,
      "backoff_ms": 1000,
      "backoff_multiplier": 2
    }
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_concurrent_agents` | integer | — | Max agents working simultaneously |
| `timeout_ms` | integer | — | Crew-level timeout (1s to 24h) |
| `max_tasks` | integer | — | Circuit breaker: max tasks before termination |
| `retry_policy.max_retries` | integer | `0` | Retry attempts on agent task failure (not hooks) |
| `retry_policy.backoff_ms` | integer | `1000` | Initial backoff delay |
| `retry_policy.backoff_multiplier` | number | `2` | Exponential backoff multiplier |

### Hooks

```json
{
  "hooks": {
    "on_start": "hooks/crew-start.sh",
    "on_task_assigned": "hooks/task-assigned.sh",
    "on_task_complete": "hooks/task-complete.sh",
    "on_agent_failure": "hooks/agent-failed.sh",
    "on_finish": "hooks/crew-finish.sh",
    "on_error": "hooks/crew-error.sh"
  }
}
```

All hooks are optional string paths relative to repo root. Runtime passes context (task ID, agent name, status) as environment variables or arguments.

| Hook | Trigger |
|------|---------|
| `on_start` | Crew begins execution |
| `on_task_assigned` | Task assigned to agent |
| `on_task_complete` | Agent completes task |
| `on_agent_failure` | Agent fails |
| `on_finish` | Crew completes all work |
| `on_error` | Crew-level error (timeout, max_tasks) |

### Communication

```json
{
  "communication": {
    "shared_context": {
      "type": "memory",
      "ttl_ms": 300000
    },
    "message_passing": {
      "mode": "direct",
      "max_queue_size": 100
    }
  }
}
```

**Shared Context:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | enum | `none` | `memory`, `file`, `none` |
| `path` | string | — | Required if type is `file` |
| `ttl_ms` | integer | `0` | Entry expiry (0 = never) |

**Message Passing:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mode` | enum | `none` | `none`, `broadcast`, `direct` |
| `max_queue_size` | integer | `100` | Max pending messages per agent |

## Complete Example

```json
{
  "name": "dev-crew",
  "description": "Full-stack development team with TDD focus",
  "shared_goal": "Implement features using test-driven development with high code quality",
  
  "agents": [
    "coder",
    "tester",
    {
      "name": "reviewer",
      "timeout_ms": 120000,
      "priority": 50
    }
  ],
  
  "routing": {
    "strategy": "capability",
    "match_on": ["tags", "languages"],
    "fallback": "round-robin",
    "task_assignment": {
      "allow_reassignment": true,
      "prefer_idle": true
    }
  },
  
  "constraints": {
    "max_concurrent_agents": 2,
    "timeout_ms": 600000,
    "retry_policy": {
      "max_retries": 2,
      "backoff_ms": 2000
    }
  },
  
  "hooks": {
    "on_task_complete": "hooks/notify-progress.sh",
    "on_finish": "hooks/crew-complete.sh"
  },
  
  "communication": {
    "shared_context": {
      "type": "memory",
      "ttl_ms": 300000
    },
    "message_passing": {
      "mode": "direct"
    }
  }
}
```

## Manifest

```json
{
  "bundle_id": "crew@v1",
  "title": "MAT Crew Definition — bundle manifest",
  "description": "Machine-readable index for MAT-42. Defines the schema for Crew definitions.",
  "schema_version": "1.0.0",
  "crew_schema": "./crew.schema.json",
  "notes": [
    "Crew definitions are JSON files in the crews/ directory.",
    "Agents are referenced by name (must exist in agents/) or with override objects.",
    "shared_goal is injected into agent context when dispatched by this Crew.",
    "routing.match_on references agent specialization fields from agent-frontmatter schema.",
    "hooks are relative paths to scripts invoked by the Crew runtime (MAT-43).",
    "communication.shared_context enables state sharing between agents."
  ]
}
```

## Integration Points

### With Agent Definitions (MAT-17)

The `routing.match_on` field references the `specialization` object in agent frontmatter:

```yaml
# agents/coder-frontend.md
---
name: coder-frontend
variant_of: coder
specialization:
  domain: frontend
  languages: [typescript, javascript]
  frameworks: [react, nextjs]
  tags: [ui, components, styling]
---
```

When routing strategy is `capability`, the Crew matches task requirements against these fields.

### With Crew Runtime (MAT-43)

The runtime reads Crew definitions and:
1. Initializes agents from the `agents` list
2. Applies routing strategy for task assignment
3. Enforces constraints (concurrency, timeouts, retries)
4. Invokes hooks at lifecycle events
5. Manages shared context and message queues

### With Swarm (MAT-45)

A Crew can dispatch tasks to a Swarm for parallel model execution. The Swarm returns a consensus result that the Crew treats as task output.

### With Hive (MAT-49)

A Hive manages multiple Crews. Inter-Crew routing and shared memory are Hive responsibilities, not Crew responsibilities.

## Validation

Add validation script: `scripts/validate_crew.py`

```bash
source .venv/bin/activate
python scripts/validate_crew.py
```

## Implementation Tasks

1. Create `schemas/crew/v1/crew.schema.json`
2. Create `schemas/crew/v1/manifest.json`
3. Create example files in `schemas/crew/v1/examples/`
4. Create `crews/` directory with README
5. Add validation script `scripts/validate_crew.py`
6. Update `config/schema-registry.json`
7. Update CLAUDE.md with crew validation command

## V1 Runtime Trade-offs

The following schema fields are parsed but not fully enforced in the v1 runtime (MAT-43):

1. **`allow_reassignment` parsed but not enforced** — Reassignment on failure requires agent selection logic in the retry loop; currently retries the same agent. Deferred to v2.

2. **`communication.message_passing.mode` parsed but not enforced** — `direct`/`broadcast` modes require persistent agent processes (Non-Goal for v1). The field is accepted for schema validity but has no runtime effect.

3. **`constraints.timeout_ms` parsed but not enforced** — Crew-level timeout enforcement deferred to v2. Per-agent timeouts via `AgentRef.timeout_ms` are enforced.

4. **`shared_context.type = "file"` removed from schema** — File-backed context storage deferred to v2; only `memory` and `none` are supported.

## References

- [MAT-42](https://github.com/zsleavitt/multi-agent-toolkit/issues/39) — This issue
- [MAT-43](https://github.com/zsleavitt/multi-agent-toolkit/issues/40) — Crew runtime
- [MAT-17](../../../schemas/agent-definition/v1/manifest.json) — Agent definition schema
- [CrewAI](https://github.com/crewaiinc/crewai) — Reference implementation research
