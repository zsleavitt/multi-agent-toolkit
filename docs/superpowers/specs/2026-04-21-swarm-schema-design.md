# Swarm Schema Design (MAT-45)

**Date:** 2026-04-21  
**Status:** Approved  
**Author:** Claude + Zach  

## Overview

This document specifies the JSON Schema for "Swarm" — a parallel dispatch primitive that sends the same task to multiple candidates simultaneously, collects responses, and applies a consensus strategy to return a single result (or all results for `return-all`).

**Hierarchy:**
```
Hive (MAT-49)
├── Crew (MAT-42/43) — sequential task routing to individual agents
└── Swarm (MAT-45) — parallel dispatch, same task to N candidates
      └── Agent × N (MAT-2) — each candidate is a standard MAT-2 invocation
```

## Goals

1. Define declarative schema for Swarm definitions
2. Support two dispatch modes: `parallel_model` (multiple CLI adapters) and `variant` (multiple agent variants)
3. Provide consensus strategies appropriate to each mode
4. Align with existing MAT schema patterns (Crew, agent-definition)
5. Enable independent testing without Crew/Hive dependencies

## Non-Goals

- Runtime implementation (MAT-46, MAT-47, MAT-48)
- Synthesis consensus strategy — deferred to v2; requires meta-agent invocation, tracked in MAT-50
- Hive integration (MAT-49)
- Model-specific parameters (temperature, max_tokens) — candidates use CLI adapter defaults
- Direct API invocation — all candidates dispatched via MAT-2 through CLI adapters (ADR 0002)
- `fail_fast` cancellation flag — cancellation semantics on partial failure require runtime design (MAT-46) before schema can be finalized; deferred to v2

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Schema structure | Unified with conditional validation | Matches Crew pattern; avoids duplicate loaders |
| Dispatch modes | `parallel_model`, `variant` | Cover CLI adapter parallelism and agent specialization |
| Consensus strategies | Mode-restricted | `variant` outputs differ by design; `majority-vote` meaningless |
| Candidate semantics | Polymorphic by mode | CLI adapters vs agent names; explicit in description |
| File location | `swarms/` directory | Parallel to `crews/`; independently testable |
| Validation | Schema + Python belt-and-suspenders | Schema catches early; Python gives readable errors |

## Schema Structure

### File Locations

```
schemas/swarm/v1/
  swarm.schema.json      # The schema
  manifest.json          # Bundle metadata
  examples/
    model-comparison.json    # parallel_model example
    language-variants.json   # variant example
    invalid/
      README.md
      wrong-consensus.json
      majority-vote-two-candidates.json

swarms/
  README.md
  {swarm-name}.json      # Actual swarm definitions
```

### Core Identity

```json
{
  "schema_version": "1.0.0",
  "name": "model-comparison",
  "description": "Compare Claude, Codex, and Gemini on implementation tasks"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | Yes | `"1.0.0"` for v1 |
| `name` | string | Yes | Unique identifier (lowercase, hyphens allowed) |
| `description` | string | No | Human-readable purpose |

### Dispatch Mode & Candidates

```json
{
  "dispatch_mode": "parallel_model",
  "candidates": ["claude", "codex", "gemini"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `dispatch_mode` | enum | Yes | `"parallel_model"` or `"variant"` |
| `candidates` | array | Yes | Min 2, max 10, unique items. See below for semantics. |

**Candidates schema:**
```json
"candidates": {
  "type": "array",
  "minItems": 2,
  "maxItems": 10,
  "uniqueItems": true,
  "items": { "type": "string", "pattern": "^[a-z][a-z0-9-]*$" },
  "description": "For parallel_model: CLI adapter identifiers (claude, codex, gemini) registered in MAT-16. For variant: agent names from the agents/ directory."
}
```

**Semantic validation (Python-side):**
- `parallel_model`: Runtime verifies each candidate exists in MAT-16 provider config
- `variant`: Runtime verifies each candidate exists in `agents/` directory

### Consensus Strategies

```json
{
  "consensus_strategy": "majority-vote"
}
```

**v1 Strategies:**

| Strategy | Valid Modes | Behavior |
|----------|-------------|----------|
| `first-complete` | `parallel_model` | Return first successful MAT-2 response |
| `majority-vote` | `parallel_model` | Return most common result among successful responses |
| `return-all` | `variant` | Return array of all successful responses |

**Note:** `consensus_strategy` is required in the top-level `required` array alongside `schema_version`, `name`, `dispatch_mode`, and `candidates`.

**Schema conditional validation:**
```json
"if": {
  "properties": { "dispatch_mode": { "const": "variant" } },
  "required": ["dispatch_mode"]
},
"then": {
  "properties": { "consensus_strategy": { "enum": ["return-all"] } }
},
"else": {
  "properties": { "consensus_strategy": { "enum": ["first-complete", "majority-vote"] } }
}
```

**Belt-and-suspenders Python validation:**
```python
if definition.dispatch_mode == "variant" and definition.consensus_strategy != "return-all":
    raise ValueError(
        f"consensus_strategy '{definition.consensus_strategy}' is not valid for "
        f"dispatch_mode 'variant'. Use 'return-all'."
    )

if definition.consensus_strategy == "majority-vote" and len(definition.candidates) < 3:
    raise ValueError(
        "majority-vote requires at least 3 candidates — with 2 candidates, "
        "any disagreement resolves to first-complete by tie-breaking. "
        "Use first-complete directly or add a third candidate."
    )
```

**majority-vote tie-breaking:** When two results have equal votes, return the one that completed first. Runtime detail, not in schema.

### Constraints

```json
{
  "constraints": {
    "timeout_ms": 120000
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `timeout_ms` | integer | — | Overall swarm timeout (1s–10min) |

**Schema:**
```json
"constraints": {
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "timeout_ms": {
      "type": "integer",
      "minimum": 1000,
      "maximum": 600000,
      "description": "Overall swarm timeout in milliseconds (1s–10min)"
    }
  }
}
```

## Complete Examples

### parallel_model (model-comparison.json)

```json
{
  "schema_version": "1.0.0",
  "name": "model-comparison",
  "description": "Compare Claude, Codex, and Gemini on implementation tasks",
  "dispatch_mode": "parallel_model",
  "candidates": ["claude", "codex", "gemini"],
  "consensus_strategy": "majority-vote",
  "constraints": {
    "timeout_ms": 120000
  }
}
```

### variant (language-variants.json)

```json
{
  "schema_version": "1.0.0",
  "name": "language-variants",
  "description": "Get Python, Ruby, and TypeScript implementations",
  "dispatch_mode": "variant",
  "candidates": ["python-engineer", "ruby-engineer", "frontend-engineer"],
  "consensus_strategy": "return-all",
  "constraints": {
    "timeout_ms": 180000
  }
}
```

### Invalid Examples

**invalid/wrong-consensus.json:**
```json
{
  "schema_version": "1.0.0",
  "name": "invalid-swarm",
  "dispatch_mode": "variant",
  "candidates": ["python-engineer", "ruby-engineer"],
  "consensus_strategy": "majority-vote"
}
```

**invalid/majority-vote-two-candidates.json:**
```json
{
  "schema_version": "1.0.0",
  "name": "invalid-majority",
  "dispatch_mode": "parallel_model",
  "candidates": ["claude", "codex"],
  "consensus_strategy": "majority-vote"
}
```

**invalid/README.md:**

| File | Reason | Caught by |
|------|--------|-----------|
| `wrong-consensus.json` | `majority-vote` not valid for `dispatch_mode: variant` | JSON Schema |
| `majority-vote-two-candidates.json` | `majority-vote` requires ≥3 candidates | Python validation |

## Manifest

```json
{
  "bundle_id": "swarm@v1",
  "title": "MAT Swarm Definition — bundle manifest",
  "description": "Machine-readable index for MAT-45. Defines the schema for Swarm parallel dispatch.",
  "schema_version": "1.0.0",
  "swarm_schema": "./swarm.schema.json",
  "notes": [
    "Swarm definitions are JSON files in the swarms/ directory (parallel to crews/).",
    "dispatch_mode determines candidate semantics: CLI adapters (parallel_model) or agent names (variant).",
    "candidates are dispatched as concurrent MAT-2 requests.",
    "consensus_strategy is constrained by dispatch_mode (schema-enforced + Python belt-and-suspenders).",
    "v1 does not include synthesis consensus — deferred to v2 (requires meta-agent invocation)."
  ]
}
```

## Integration Points

| Integration | Description |
|-------------|-------------|
| **MAT-2 (codex-code-exec)** | Each candidate dispatch is a standard MAT-2 request/response |
| **MAT-16 (provider-config)** | `parallel_model` candidates must exist as CLI adapters |
| **MAT-17 (agent-definition)** | `variant` candidates must exist in `agents/` directory |
| **MAT-49 (Hive)** | Hive routes tasks to Crew or Swarm; Swarm returns consensus result |

## V1 Trade-offs

1. **if/then/else consensus validation assumes exactly two dispatch modes** — adding a third mode in v2 requires revisiting the conditional; `else` branch is not "default", it's implicitly "parallel_model"

2. **`fail_fast` cancellation flag deferred** — cancellation semantics require runtime design (MAT-46) before schema can be finalized

3. **`synthesis` consensus strategy deferred** — requires meta-agent invocation, tracked in MAT-50

## Validation

Add validation script: `scripts/validate_swarm.py`

```bash
source .venv/bin/activate
python scripts/validate_swarm.py
```

The validation script must test both JSON Schema validation (catches `wrong-consensus.json`) and Python semantic validation (catches `majority-vote-two-candidates.json`).

## Implementation Tasks

1. Create `schemas/swarm/v1/swarm.schema.json`
2. Create `schemas/swarm/v1/manifest.json`
3. Create `schemas/swarm/v1/examples/model-comparison.json`
4. Create `schemas/swarm/v1/examples/language-variants.json`
5. Create `schemas/swarm/v1/examples/invalid/` with README and two invalid examples
6. Create `swarms/` directory with README
7. Add validation script `scripts/validate_swarm.py`
8. Update `config/schema-registry.json` — add swarm@v1 bundle
9. Update `CLAUDE.md` — add `validate_swarm.py` to validation commands

## References

- [MAT-45](https://github.com/zsleavitt/multi-agent-toolkit/issues/42) — This issue
- [MAT-46/47/48](https://github.com/zsleavitt/multi-agent-toolkit/issues/43) — Swarm runtime implementation
- [MAT-49](https://github.com/zsleavitt/multi-agent-toolkit/issues/46) — Hive (routes tasks to Crew or Swarm)
- [MAT-50](https://github.com/zsleavitt/multi-agent-toolkit/issues/47) — Synthesis consensus strategy (v2)
- [MAT-2](../../../schemas/codex-code-exec/v1/manifest.json) — Wire format (each candidate dispatch)
- [MAT-16](../../../schemas/provider-config/v1/manifest.json) — Provider config (parallel_model candidate validation)
- [MAT-17](../../../schemas/agent-definition/v1/manifest.json) — Agent definition schema (variant candidate validation)
- [ADR 0002](../../adr/0002-cli-delegation-no-api-keys.md) — CLI delegation (no direct API invocation)
