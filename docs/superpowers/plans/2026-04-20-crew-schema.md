# Crew Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the MAT-42 Crew schema — a JSON Schema defining named agent collections with routing, constraints, hooks, and communication.

**Architecture:** Schema bundle in `schemas/crew/v1/` with crew.schema.json, manifest.json, and examples. Validation script validates both schema examples and actual crew definitions in `crews/`. Registry updated to include the new bundle.

**Tech Stack:** JSON Schema (draft 2020-12), Python (jsonschema, referencing), pytest

---

## File Structure

```
schemas/crew/v1/
  crew.schema.json           # Main schema (create)
  manifest.json              # Bundle metadata (create)
  examples/
    valid/
      dev-crew.json          # Valid example: full-featured dev crew
      minimal-crew.json      # Valid example: minimal crew
    invalid/
      missing-agents.json    # Invalid: missing required field
      invalid-strategy.json  # Invalid: bad routing strategy

crews/
  README.md                  # Documentation (create)

scripts/
  validate_crew.py           # Validation script (create)

config/
  schema-registry.json       # Update with crew bundle
```

---

### Task 1: Create Schema Directory Structure

**Files:**
- Create: `schemas/crew/v1/` directory
- Create: `schemas/crew/v1/examples/valid/` directory
- Create: `schemas/crew/v1/examples/invalid/` directory

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p schemas/crew/v1/examples/valid
mkdir -p schemas/crew/v1/examples/invalid
```

- [ ] **Step 2: Verify directories exist**

Run: `ls -la schemas/crew/v1/`
Expected: Shows `examples` directory

Run: `ls -la schemas/crew/v1/examples/`
Expected: Shows `valid` and `invalid` directories

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/
git commit -m "chore: create crew schema directory structure (MAT-42)"
```

---

### Task 2: Create Crew Schema - Core Identity

**Files:**
- Create: `schemas/crew/v1/crew.schema.json`

- [ ] **Step 1: Create schema with core identity fields**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mat.dev/schemas/crew/v1/crew.schema.json",
  "title": "Crew definition (MAT-42)",
  "description": "Schema for defining a named collection of agents with shared goals and routing configuration.",
  "type": "object",
  "additionalProperties": false,
  "required": ["name", "agents"],
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]*$",
      "description": "Unique crew identifier (lowercase alphanumeric with hyphens)"
    },
    "description": {
      "type": "string",
      "maxLength": 512,
      "description": "Human-readable description of the crew's purpose"
    },
    "shared_goal": {
      "type": "string",
      "maxLength": 2048,
      "description": "Goal text injected into each agent's context when dispatched"
    }
  }
}
```

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/crew/v1/crew.schema.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/crew.schema.json
git commit -m "feat(schema): add crew schema core identity fields (MAT-42)"
```

---

### Task 3: Add Agents Array to Schema

**Files:**
- Modify: `schemas/crew/v1/crew.schema.json`

- [ ] **Step 1: Add agents property to schema**

Add the following property to the `properties` object in `crew.schema.json`:

```json
    "agents": {
      "type": "array",
      "minItems": 1,
      "items": {
        "oneOf": [
          {
            "type": "string",
            "pattern": "^[a-z][a-z0-9-]*$",
            "description": "Agent name reference (must exist in agents/)"
          },
          {
            "type": "object",
            "required": ["name"],
            "additionalProperties": false,
            "properties": {
              "name": {
                "type": "string",
                "pattern": "^[a-z][a-z0-9-]*$",
                "description": "Agent name reference"
              },
              "timeout_ms": {
                "type": "integer",
                "minimum": 1000,
                "maximum": 3600000,
                "description": "Override default timeout for this agent in this crew"
              },
              "priority": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Routing priority (higher = preferred)"
              },
              "required_capabilities": {
                "type": "array",
                "items": { "type": "string" },
                "description": "Capabilities this agent must have for task routing"
              }
            }
          }
        ]
      },
      "description": "Member agents - by name or with per-crew overrides"
    }
```

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/crew/v1/crew.schema.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/crew.schema.json
git commit -m "feat(schema): add agents array with mixed mode support (MAT-42)"
```

---

### Task 4: Add Routing Configuration to Schema

**Files:**
- Modify: `schemas/crew/v1/crew.schema.json`

- [ ] **Step 1: Add routing property to schema**

Add the following property to the `properties` object:

```json
    "routing": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "strategy": {
          "type": "string",
          "enum": ["round-robin", "capability", "priority", "random"],
          "default": "round-robin",
          "description": "Primary routing strategy"
        },
        "match_on": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": ["tags", "domain", "languages", "frameworks"]
          },
          "description": "Agent specialization fields to match against (for capability strategy)"
        },
        "fallback": {
          "type": "string",
          "enum": ["round-robin", "random", "first-available", "error"],
          "default": "round-robin",
          "description": "Strategy when no capability match found"
        },
        "task_assignment": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "allow_reassignment": {
              "type": "boolean",
              "default": false,
              "description": "Allow tasks to be reassigned on agent failure"
            },
            "prefer_idle": {
              "type": "boolean",
              "default": true,
              "description": "Prefer agents not currently working on tasks"
            }
          }
        }
      }
    }
```

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/crew/v1/crew.schema.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/crew.schema.json
git commit -m "feat(schema): add routing configuration to crew schema (MAT-42)"
```

---

### Task 5: Add Constraints to Schema

**Files:**
- Modify: `schemas/crew/v1/crew.schema.json`

- [ ] **Step 1: Add constraints property to schema**

Add the following property to the `properties` object:

```json
    "constraints": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "max_concurrent_agents": {
          "type": "integer",
          "minimum": 1,
          "maximum": 100,
          "description": "Maximum agents working simultaneously"
        },
        "timeout_ms": {
          "type": "integer",
          "minimum": 1000,
          "maximum": 86400000,
          "description": "Crew-level timeout (1s to 24h)"
        },
        "max_tasks": {
          "type": "integer",
          "minimum": 1,
          "description": "Maximum tasks before crew auto-terminates"
        },
        "retry_policy": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "max_retries": {
              "type": "integer",
              "minimum": 0,
              "maximum": 10,
              "default": 0,
              "description": "Retry attempts on agent task failure (not hooks)"
            },
            "backoff_ms": {
              "type": "integer",
              "minimum": 100,
              "maximum": 60000,
              "default": 1000,
              "description": "Initial backoff between retries"
            },
            "backoff_multiplier": {
              "type": "number",
              "minimum": 1,
              "maximum": 5,
              "default": 2,
              "description": "Exponential backoff multiplier"
            }
          }
        }
      }
    }
```

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/crew/v1/crew.schema.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/crew.schema.json
git commit -m "feat(schema): add constraints to crew schema (MAT-42)"
```

---

### Task 6: Add Hooks to Schema

**Files:**
- Modify: `schemas/crew/v1/crew.schema.json`

- [ ] **Step 1: Add hooks property to schema**

Add the following property to the `properties` object:

```json
    "hooks": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "on_start": {
          "type": "string",
          "description": "Script/command to run when crew starts (relative to repo root)"
        },
        "on_task_assigned": {
          "type": "string",
          "description": "Script to run when a task is assigned to an agent"
        },
        "on_task_complete": {
          "type": "string",
          "description": "Script to run when an agent completes a task"
        },
        "on_agent_failure": {
          "type": "string",
          "description": "Script to run when an agent fails"
        },
        "on_finish": {
          "type": "string",
          "description": "Script to run when crew completes all work"
        },
        "on_error": {
          "type": "string",
          "description": "Script to run on crew-level error (timeout, max_tasks exceeded)"
        }
      }
    }
```

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/crew/v1/crew.schema.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/crew.schema.json
git commit -m "feat(schema): add lifecycle hooks to crew schema (MAT-42)"
```

---

### Task 7: Add Communication to Schema

**Files:**
- Modify: `schemas/crew/v1/crew.schema.json`

- [ ] **Step 1: Add communication property to schema**

Add the following property to the `properties` object:

```json
    "communication": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "shared_context": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "type": {
              "type": "string",
              "enum": ["memory", "file", "none"],
              "default": "none",
              "description": "Context store type"
            },
            "path": {
              "type": "string",
              "description": "File path for 'file' type (relative to repo root)"
            },
            "ttl_ms": {
              "type": "integer",
              "minimum": 0,
              "description": "Time-to-live for context entries (0 = no expiry)"
            }
          },
          "if": {
            "properties": { "type": { "const": "file" } },
            "required": ["type"]
          },
          "then": {
            "required": ["path"]
          }
        },
        "message_passing": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "mode": {
              "type": "string",
              "enum": ["none", "broadcast", "direct"],
              "default": "none",
              "description": "How agents can send messages to each other"
            },
            "max_queue_size": {
              "type": "integer",
              "minimum": 1,
              "maximum": 1000,
              "default": 100,
              "description": "Maximum pending messages per agent"
            }
          }
        }
      }
    }
```

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/crew/v1/crew.schema.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/crew.schema.json
git commit -m "feat(schema): add communication config to crew schema (MAT-42)"
```

---

### Task 8: Create Manifest

**Files:**
- Create: `schemas/crew/v1/manifest.json`

- [ ] **Step 1: Create manifest file**

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

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/crew/v1/manifest.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/manifest.json
git commit -m "feat(schema): add crew schema manifest (MAT-42)"
```

---

### Task 9: Create Valid Example - Full Dev Crew

**Files:**
- Create: `schemas/crew/v1/examples/valid/dev-crew.json`

- [ ] **Step 1: Create full-featured example**

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

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/crew/v1/examples/valid/dev-crew.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/examples/valid/dev-crew.json
git commit -m "feat(schema): add dev-crew valid example (MAT-42)"
```

---

### Task 10: Create Valid Example - Minimal Crew

**Files:**
- Create: `schemas/crew/v1/examples/valid/minimal-crew.json`

- [ ] **Step 1: Create minimal example**

```json
{
  "name": "minimal-crew",
  "agents": ["coder"]
}
```

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/crew/v1/examples/valid/minimal-crew.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add schemas/crew/v1/examples/valid/minimal-crew.json
git commit -m "feat(schema): add minimal-crew valid example (MAT-42)"
```

---

### Task 11: Create Invalid Example - Missing Agents

**Files:**
- Create: `schemas/crew/v1/examples/invalid/missing-agents.json`

- [ ] **Step 1: Create invalid example missing required field**

```json
{
  "name": "broken-crew",
  "description": "This crew is missing the required agents field"
}
```

- [ ] **Step 2: Commit**

```bash
git add schemas/crew/v1/examples/invalid/missing-agents.json
git commit -m "test(schema): add missing-agents invalid example (MAT-42)"
```

---

### Task 12: Create Invalid Example - Invalid Strategy

**Files:**
- Create: `schemas/crew/v1/examples/invalid/invalid-strategy.json`

- [ ] **Step 1: Create invalid example with bad enum value**

```json
{
  "name": "bad-routing-crew",
  "agents": ["coder"],
  "routing": {
    "strategy": "magic-routing"
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add schemas/crew/v1/examples/invalid/invalid-strategy.json
git commit -m "test(schema): add invalid-strategy invalid example (MAT-42)"
```

---

### Task 13: Create Validation Script

**Files:**
- Create: `scripts/validate_crew.py`

- [ ] **Step 1: Create validation script**

```python
#!/usr/bin/env python3
"""Validate MAT-42 Crew definition files."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_KEY = "crew@v1"
_ENV_BUNDLE_DIR = "MAT_CREW_V1"


def resolve_bundle_dir(root: Path) -> Path:
    env = os.environ.get(_ENV_BUNDLE_DIR)
    if env:
        return Path(env).expanduser().resolve()
    cfg_path = root / "config" / "schema-registry.json"
    if cfg_path.is_file():
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        bundle = (data.get("schema_bundles") or {}).get(_BUNDLE_KEY) or {}
        rel = bundle.get("root_relative")
        if isinstance(rel, str) and rel.strip():
            return (root / rel).resolve()
    return (root / "schemas" / "crew" / "v1").resolve()


V1 = resolve_bundle_dir(ROOT)
CREWS_DIR = ROOT / "crews"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_registry():
    try:
        from referencing import Registry
        from referencing.jsonschema import DRAFT202012
    except ImportError as e:
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    registry = Registry()
    schema_file = V1 / "crew.schema.json"
    uri = schema_file.as_uri()
    doc = _load_json(schema_file)
    registry = registry.with_resource(uri, DRAFT202012.create_resource(doc))
    return registry


def main() -> None:
    if not V1.is_dir():
        raise SystemExit(
            f"Bundle directory missing: {V1}\n"
            f"Set {_ENV_BUNDLE_DIR} or config/schema-registry.json → schema_bundles.{_BUNDLE_KEY}.root_relative"
        )

    schema = _load_json(V1 / "crew.schema.json")

    from jsonschema import Draft202012Validator

    registry = _build_registry()
    validator = Draft202012Validator(schema, registry=registry)

    # Validate valid examples
    valid_dir = V1 / "examples" / "valid"
    if valid_dir.is_dir():
        for path in sorted(valid_dir.glob("*.json")):
            instance = _load_json(path)
            validator.validate(instance)
            print(f"OK valid    {path.relative_to(ROOT)}")

    # Validate invalid examples (should fail)
    invalid_dir = V1 / "examples" / "invalid"
    if invalid_dir.is_dir():
        for path in sorted(invalid_dir.glob("*.json")):
            instance = _load_json(path)
            errs = sorted(validator.iter_errors(instance), key=lambda e: e.path)
            if not errs:
                raise SystemExit(f"Expected validation failure for {path}")
            print(f"OK invalid  {path.relative_to(ROOT)} ({errs[0].message})")

    # Validate actual crew definitions
    if CREWS_DIR.is_dir():
        seen_names: set[str] = set()
        for path in sorted(CREWS_DIR.glob("*.json")):
            instance = _load_json(path)
            errs = sorted(validator.iter_errors(instance), key=lambda e: e.path)
            if errs:
                raise SystemExit(
                    f"Invalid crew definition in {path}:\n  {errs[0].message}"
                )

            name = instance.get("name")
            if name in seen_names:
                raise SystemExit(f"Duplicate crew name '{name}' in {path}")
            seen_names.add(name)

            print(f"OK crew     {path.relative_to(ROOT)} (name={name})")
    else:
        print(f"No crews directory at {CREWS_DIR}; skipping crew file validation.")

    print(f"All MAT-42 crew definition checks passed (bundle: {V1}).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make script executable**

```bash
chmod +x scripts/validate_crew.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/validate_crew.py
git commit -m "feat(validation): add crew schema validation script (MAT-42)"
```

---

### Task 14: Test Validation Script

**Files:**
- Test: `scripts/validate_crew.py`

- [ ] **Step 1: Run validation script**

Run: `source .venv/bin/activate && python scripts/validate_crew.py`

Expected output:
```
OK valid    schemas/crew/v1/examples/valid/dev-crew.json
OK valid    schemas/crew/v1/examples/valid/minimal-crew.json
OK invalid  schemas/crew/v1/examples/invalid/invalid-strategy.json ('magic-routing' is not one of...)
OK invalid  schemas/crew/v1/examples/invalid/missing-agents.json ('agents' is a required property)
No crews directory at .../crews; skipping crew file validation.
All MAT-42 crew definition checks passed (bundle: .../schemas/crew/v1).
```

- [ ] **Step 2: Fix any validation errors**

If any errors occur, fix the schema or examples and re-run.

---

### Task 15: Create Crews Directory with README

**Files:**
- Create: `crews/README.md`

- [ ] **Step 1: Create crews directory and README**

```bash
mkdir -p crews
```

```markdown
# Crews

This directory contains Crew definitions — JSON files that define named collections of agents with shared goals and routing configuration.

## File Format

Each crew is a JSON file following the schema at `schemas/crew/v1/crew.schema.json`.

## Example

```json
{
  "name": "dev-crew",
  "description": "Development team",
  "shared_goal": "Implement features with high quality",
  "agents": ["coder", "tester", "reviewer"],
  "routing": {
    "strategy": "capability",
    "match_on": ["tags", "languages"]
  }
}
```

## Validation

```bash
source .venv/bin/activate
python scripts/validate_crew.py
```

## See Also

- [Crew Schema Spec](../docs/superpowers/specs/2026-04-20-crew-schema-design.md)
- [MAT-42 Issue](https://github.com/zsleavitt/multi-agent-toolkit/issues/39)
- [MAT-43 Crew Runtime](https://github.com/zsleavitt/multi-agent-toolkit/issues/40)
```

- [ ] **Step 2: Commit**

```bash
git add crews/README.md
git commit -m "docs: add crews directory with README (MAT-42)"
```

---

### Task 16: Update Schema Registry

**Files:**
- Modify: `config/schema-registry.json`

- [ ] **Step 1: Add crew bundle to registry**

Add the following entry to `schema_bundles` in `config/schema-registry.json`:

```json
    "crew@v1": {
      "root_relative": "schemas/crew/v1",
      "published_document_base": null
    }
```

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('config/schema-registry.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add config/schema-registry.json
git commit -m "config: add crew bundle to schema registry (MAT-42)"
```

---

### Task 17: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add MAT-42 to contracts list**

Add the following line after the MAT-17 entry in the Contracts section:

```markdown
- **MAT-42** — `schemas/crew/v1/` — **Crew definition schema**: named agent collections with routing, constraints, hooks, and communication. Crews are defined in `crews/*.json`.
```

- [ ] **Step 2: Add validation command**

Add the following line to the Validation code block:

```bash
python scripts/validate_crew.py
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add MAT-42 crew schema to CLAUDE.md"
```

---

### Task 18: Run Full Validation Suite

**Files:**
- Test: All schema validation scripts

- [ ] **Step 1: Run all validations**

Run:
```bash
source .venv/bin/activate
python scripts/validate_crew.py
python scripts/validate_agent_definitions.py
```

Expected: Both pass without errors

- [ ] **Step 2: Verify no regressions**

Run: `git status`
Expected: Clean working directory (all changes committed)

---

## Self-Review Checklist

- [x] **Spec coverage:** All sections from spec have corresponding tasks
  - Core identity: Task 2
  - Agents: Task 3
  - Routing: Task 4
  - Constraints: Task 5
  - Hooks: Task 6
  - Communication: Task 7
  - Manifest: Task 8
  - Examples: Tasks 9-12
  - Validation: Tasks 13-14
  - crews/ directory: Task 15
  - Registry: Task 16
  - CLAUDE.md: Task 17

- [x] **Placeholder scan:** No TBD, TODO, or "implement later" markers

- [x] **Type consistency:** All property names match between tasks (e.g., `max_concurrent_agents`, `timeout_ms`, `backoff_multiplier`)
