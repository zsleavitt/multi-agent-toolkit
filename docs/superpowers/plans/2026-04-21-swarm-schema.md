# MAT-45 Swarm Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the JSON Schema for Swarm — a parallel dispatch primitive with two modes (parallel_model, variant) and mode-restricted consensus strategies.

**Architecture:** Single unified schema with conditional validation (if/then/else) to restrict consensus strategies per dispatch mode. Validation script tests both JSON Schema validation and Python semantic validation (belt-and-suspenders). Swarm definitions live in `swarms/` directory parallel to `crews/`.

**Tech Stack:** JSON Schema Draft 2020-12, Python 3.10+, jsonschema library, referencing library

---

## File Structure

```
schemas/swarm/v1/
  swarm.schema.json          # Create: Main schema
  manifest.json              # Create: Bundle metadata
  examples/
    model-comparison.json    # Create: parallel_model example
    language-variants.json   # Create: variant example
    invalid/
      README.md              # Create: Explains invalid examples
      wrong-consensus.json   # Create: variant + majority-vote (schema error)
      majority-vote-two-candidates.json  # Create: parallel_model + majority-vote + 2 candidates (Python error)

swarms/
  README.md                  # Create: Directory documentation

scripts/
  validate_swarm.py          # Create: Validation script

config/
  schema-registry.json       # Modify: Add swarm@v1 bundle

CLAUDE.md                    # Modify: Add validate_swarm.py command
```

---

### Task 1: Create swarm.schema.json

**Files:**
- Create: `schemas/swarm/v1/swarm.schema.json`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p schemas/swarm/v1/examples/invalid
```

- [ ] **Step 2: Create the schema file**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://mat.dev/schemas/swarm/v1/swarm.schema.json",
  "title": "Swarm definition (MAT-45)",
  "description": "Schema for defining parallel dispatch to multiple candidates with consensus strategies.",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "name", "dispatch_mode", "candidates", "consensus_strategy"],
  "properties": {
    "schema_version": { "$ref": "#/$defs/schema_version" },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 64,
      "pattern": "^[a-z][a-z0-9-]*$",
      "description": "Unique swarm identifier (lowercase alphanumeric with hyphens)"
    },
    "description": {
      "type": "string",
      "maxLength": 512,
      "description": "Human-readable description of the swarm's purpose"
    },
    "dispatch_mode": {
      "type": "string",
      "enum": ["parallel_model", "variant"],
      "description": "Dispatch mode: parallel_model (multiple CLI adapters) or variant (multiple agent variants)"
    },
    "candidates": {
      "type": "array",
      "minItems": 2,
      "maxItems": 10,
      "uniqueItems": true,
      "items": { "type": "string", "pattern": "^[a-z][a-z0-9-]*$" },
      "description": "For parallel_model: CLI adapter identifiers (claude, codex, gemini) registered in MAT-16. For variant: agent names from the agents/ directory."
    },
    "consensus_strategy": {
      "type": "string",
      "description": "Strategy for combining candidate responses. Valid values depend on dispatch_mode."
    },
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
  },
  "if": {
    "properties": { "dispatch_mode": { "const": "variant" } },
    "required": ["dispatch_mode"]
  },
  "then": {
    "properties": { "consensus_strategy": { "enum": ["return-all"] } }
  },
  "else": {
    "properties": { "consensus_strategy": { "enum": ["first-complete", "majority-vote"] } }
  },
  "$defs": {
    "schema_version": {
      "type": "string",
      "const": "1.0.0",
      "description": "Schema version. Bump when swarm definition shape changes."
    }
  }
}
```

- [ ] **Step 3: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/swarm/v1/swarm.schema.json'))"`
Expected: No output (success)

- [ ] **Step 4: Commit**

```bash
git add schemas/swarm/v1/swarm.schema.json
git commit -m "feat(swarm): add MAT-45 swarm.schema.json

Defines parallel dispatch primitive with:
- Two dispatch modes: parallel_model, variant
- Mode-restricted consensus via if/then/else validation
- Candidates array (2-10 unique items)"
```

---

### Task 2: Create manifest.json

**Files:**
- Create: `schemas/swarm/v1/manifest.json`

- [ ] **Step 1: Create the manifest file**

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

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('schemas/swarm/v1/manifest.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add schemas/swarm/v1/manifest.json
git commit -m "feat(swarm): add MAT-45 manifest.json"
```

---

### Task 3: Create valid examples

**Files:**
- Create: `schemas/swarm/v1/examples/model-comparison.json`
- Create: `schemas/swarm/v1/examples/language-variants.json`

- [ ] **Step 1: Create model-comparison.json (parallel_model example)**

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

- [ ] **Step 2: Create language-variants.json (variant example)**

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

- [ ] **Step 3: Verify both files are valid JSON**

Run: `python3 -c "import json; [json.load(open(f)) for f in ['schemas/swarm/v1/examples/model-comparison.json', 'schemas/swarm/v1/examples/language-variants.json']]"`
Expected: No output (success)

- [ ] **Step 4: Commit**

```bash
git add schemas/swarm/v1/examples/model-comparison.json schemas/swarm/v1/examples/language-variants.json
git commit -m "feat(swarm): add valid example swarm definitions"
```

---

### Task 4: Create invalid examples

**Files:**
- Create: `schemas/swarm/v1/examples/invalid/README.md`
- Create: `schemas/swarm/v1/examples/invalid/wrong-consensus.json`
- Create: `schemas/swarm/v1/examples/invalid/majority-vote-two-candidates.json`

- [ ] **Step 1: Create wrong-consensus.json**

```json
{
  "schema_version": "1.0.0",
  "name": "invalid-swarm",
  "dispatch_mode": "variant",
  "candidates": ["python-engineer", "ruby-engineer"],
  "consensus_strategy": "majority-vote"
}
```

- [ ] **Step 2: Create majority-vote-two-candidates.json**

```json
{
  "schema_version": "1.0.0",
  "name": "invalid-majority",
  "dispatch_mode": "parallel_model",
  "candidates": ["claude", "codex"],
  "consensus_strategy": "majority-vote"
}
```

- [ ] **Step 3: Create README.md**

```markdown
# Invalid Swarm Examples

These files intentionally fail validation. Used by `scripts/validate_swarm.py` tests.

| File | Reason | Caught by |
|------|--------|-----------|
| `wrong-consensus.json` | `majority-vote` not valid for `dispatch_mode: variant` | JSON Schema |
| `majority-vote-two-candidates.json` | `majority-vote` requires ≥3 candidates | Python validation |
```

- [ ] **Step 4: Commit**

```bash
git add schemas/swarm/v1/examples/invalid/
git commit -m "feat(swarm): add invalid examples for validation testing"
```

---

### Task 5: Create swarms/ directory with README

**Files:**
- Create: `swarms/README.md`

- [ ] **Step 1: Create swarms directory**

```bash
mkdir -p swarms
```

- [ ] **Step 2: Create README.md**

```markdown
# Swarms

This directory contains Swarm definitions — JSON files that define parallel dispatch to multiple candidates with consensus strategies.

## File Format

Each swarm is a JSON file following the schema at `schemas/swarm/v1/swarm.schema.json`.

## Example

```json
{
  "schema_version": "1.0.0",
  "name": "model-comparison",
  "description": "Compare multiple models on implementation tasks",
  "dispatch_mode": "parallel_model",
  "candidates": ["claude", "codex", "gemini"],
  "consensus_strategy": "majority-vote"
}
```

## Dispatch Modes

- **parallel_model**: Send same task to multiple CLI adapters (claude, codex, gemini)
- **variant**: Send same task to multiple agent variants (python-engineer, ruby-engineer)

## Consensus Strategies

| Strategy | Valid Modes | Behavior |
|----------|-------------|----------|
| `first-complete` | parallel_model | Return first successful response |
| `majority-vote` | parallel_model | Return most common result (requires ≥3 candidates) |
| `return-all` | variant | Return array of all responses |

## Validation

```bash
source .venv/bin/activate
python scripts/validate_swarm.py
```

## See Also

- [Swarm Schema Spec](../docs/superpowers/specs/2026-04-21-swarm-schema-design.md)
- [MAT-45 Issue](https://github.com/zsleavitt/multi-agent-toolkit/issues/42)
```

- [ ] **Step 3: Commit**

```bash
git add swarms/
git commit -m "feat(swarm): add swarms/ directory with README"
```

---

### Task 6: Create validate_swarm.py

**Files:**
- Create: `scripts/validate_swarm.py`

- [ ] **Step 1: Create the validation script**

```python
#!/usr/bin/env python3
"""Validate MAT-45 Swarm definition files."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BUNDLE_KEY = "swarm@v1"
_ENV_BUNDLE_DIR = "MAT_SWARM_V1"


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
    return (root / "schemas" / "swarm" / "v1").resolve()


V1 = resolve_bundle_dir(ROOT)
SWARMS_DIR = ROOT / "swarms"
AGENTS_DIR = ROOT / "agents"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_agent_names() -> set[str]:
    """Load all valid agent names from agents/*.md frontmatter."""
    import re
    import yaml
    names: set[str] = set()
    if not AGENTS_DIR.is_dir():
        return names

    for pattern in ["*.md", "variants/*.md"]:
        for path in AGENTS_DIR.glob(pattern):
            if path.name.lower() in ("readme.md", "index.md"):
                continue

            content = path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue
            end = content.find("\n---", 3)
            if end == -1:
                continue
            try:
                frontmatter = yaml.safe_load(content[4:end])
                if isinstance(frontmatter, dict) and "name" in frontmatter:
                    name = frontmatter["name"]
                    if isinstance(name, str) and re.match(r"^[a-z][a-z0-9-]*$", name):
                        names.add(name)
            except yaml.YAMLError:
                continue
    return names


def _semantic_validation(instance: dict, path: Path, known_agents: set[str]) -> None:
    """Run Python-side semantic validation (belt-and-suspenders)."""
    dispatch_mode = instance.get("dispatch_mode")
    consensus_strategy = instance.get("consensus_strategy")
    candidates = instance.get("candidates", [])

    # Check consensus strategy validity per mode
    if dispatch_mode == "variant" and consensus_strategy != "return-all":
        raise ValueError(
            f"consensus_strategy '{consensus_strategy}' is not valid for "
            f"dispatch_mode 'variant'. Use 'return-all'. ({path})"
        )

    # Check majority-vote requires >= 3 candidates
    if consensus_strategy == "majority-vote" and len(candidates) < 3:
        raise ValueError(
            f"majority-vote requires at least 3 candidates — with {len(candidates)} candidates, "
            f"any disagreement resolves to first-complete by tie-breaking. "
            f"Use first-complete directly or add a third candidate. ({path})"
        )

    # Check variant candidates exist in agents/ directory
    if dispatch_mode == "variant" and known_agents:
        for candidate in candidates:
            if candidate not in known_agents:
                raise ValueError(
                    f"Unknown agent '{candidate}' in {path}. "
                    f"For dispatch_mode 'variant', candidates must exist in agents/. "
                    f"Valid agents: {sorted(known_agents)}"
                )


def _build_registry():
    try:
        from referencing import Registry
        from referencing.jsonschema import DRAFT202012
    except ImportError as e:
        raise SystemExit(
            "Missing deps. Run: pip install -r requirements-dev.txt\n" + str(e)
        ) from e

    registry = Registry()
    schema_file = V1 / "swarm.schema.json"
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

    schema = _load_json(V1 / "swarm.schema.json")

    from jsonschema import Draft202012Validator

    registry = _build_registry()
    validator = Draft202012Validator(schema, registry=registry)

    # Load known agent names for semantic validation
    known_agents = _load_agent_names()
    if known_agents:
        print(f"Loaded {len(known_agents)} agent names from {AGENTS_DIR}")
    else:
        print(f"Warning: No agents found in {AGENTS_DIR}; skipping agent reference validation")

    # Validate valid examples
    examples_dir = V1 / "examples"
    for path in sorted(examples_dir.glob("*.json")):
        instance = _load_json(path)
        validator.validate(instance)
        _semantic_validation(instance, path, known_agents)
        print(f"OK valid    {path.relative_to(ROOT)}")

    # Validate invalid examples
    invalid_dir = V1 / "examples" / "invalid"
    if invalid_dir.is_dir():
        for path in sorted(invalid_dir.glob("*.json")):
            instance = _load_json(path)

            # Check if schema catches it
            schema_errors = list(validator.iter_errors(instance))
            if schema_errors:
                print(f"OK invalid  {path.relative_to(ROOT)} (schema: {schema_errors[0].message})")
                continue

            # Check if Python semantic validation catches it
            try:
                _semantic_validation(instance, path, known_agents)
                raise SystemExit(f"Expected validation failure for {path}")
            except ValueError as e:
                print(f"OK invalid  {path.relative_to(ROOT)} (python: {e})")

    # Validate actual swarm definitions
    if SWARMS_DIR.is_dir():
        seen_names: set[str] = set()
        for path in sorted(SWARMS_DIR.glob("*.json")):
            instance = _load_json(path)
            errs = sorted(validator.iter_errors(instance), key=lambda e: e.path)
            if errs:
                raise SystemExit(
                    f"Invalid swarm definition in {path}:\n  {errs[0].message}"
                )

            # Semantic validation
            _semantic_validation(instance, path, known_agents)

            name = instance.get("name")
            if name in seen_names:
                raise SystemExit(f"Duplicate swarm name '{name}' in {path}")
            seen_names.add(name)

            print(f"OK swarm    {path.relative_to(ROOT)} (name={name})")
    else:
        print(f"No swarms directory at {SWARMS_DIR}; skipping swarm file validation.")

    print(f"All MAT-45 swarm definition checks passed (bundle: {V1}).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/validate_swarm.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/validate_swarm.py
git commit -m "feat(swarm): add validate_swarm.py with schema + semantic validation"
```

---

### Task 7: Update schema-registry.json

**Files:**
- Modify: `config/schema-registry.json`

- [ ] **Step 1: Add swarm@v1 bundle**

Add the following entry to the `schema_bundles` object:

```json
    "swarm@v1": {
      "root_relative": "schemas/swarm/v1",
      "published_document_base": null
    }
```

The full file should look like:

```json
{
  "documentation": "schema_bundles.*.root_relative: where this repo keeps MAT JSON Schema bundles on disk. published_document_base: optional URL prefix for a separate publish/mirror pipeline (not read by schemas in git — they use only fragment $ref). MAT_GEMINI_GIT_OPS_V1, MAT_CODEX_CODE_EXEC_V1, MAT_AI_TEAM_REPO_PROFILE_V1, MAT_ORCHESTRATOR_STATE_V1, MAT_HITL_ASANA_APPROVAL_V1, MAT_PROVIDER_CONFIG_V1, MAT_AGENT_DEFINITION_V1, and MAT_SWARM_V1 env vars override root_relative for validators and CI.",
  "schema_bundles": {
    "gemini-git-ops@v1": {
      "root_relative": "schemas/gemini-git-ops/v1",
      "published_document_base": null
    },
    "codex-code-exec@v1": {
      "root_relative": "schemas/codex-code-exec/v1",
      "published_document_base": null
    },
    "ai-team-repo-profile@v1": {
      "root_relative": "schemas/ai-team-repo-profile/v1",
      "published_document_base": null
    },
    "orchestrator-state@v1": {
      "root_relative": "schemas/orchestrator-state/v1",
      "published_document_base": null
    },
    "hitl-asana-approval@v1": {
      "root_relative": "schemas/hitl-asana-approval/v1",
      "published_document_base": null
    },
    "provider-config@v1": {
      "root_relative": "schemas/provider-config/v1",
      "published_document_base": null
    },
    "agent-definition@v1": {
      "root_relative": "schemas/agent-definition/v1",
      "published_document_base": null
    },
    "crew@v1": {
      "root_relative": "schemas/crew/v1",
      "published_document_base": null
    },
    "swarm@v1": {
      "root_relative": "schemas/swarm/v1",
      "published_document_base": null
    }
  }
}
```

- [ ] **Step 2: Verify JSON is valid**

Run: `python3 -c "import json; json.load(open('config/schema-registry.json'))"`
Expected: No output (success)

- [ ] **Step 3: Commit**

```bash
git add config/schema-registry.json
git commit -m "feat(swarm): register swarm@v1 bundle in schema-registry"
```

---

### Task 8: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add MAT-45 to Contracts section**

Find the line:
```
- **MAT-42** — `schemas/crew/v1/` — **Crew definition schema**: named agent collections with routing, constraints, hooks, and communication. Crews are defined in `crews/*.json`.
```

Add after it:
```
- **MAT-45** — `schemas/swarm/v1/` — **Swarm definition schema**: parallel dispatch to multiple candidates with consensus strategies. Swarms are defined in `swarms/*.json`.
```

- [ ] **Step 2: Add validate_swarm.py to validation commands**

Find the validation code block and add `python scripts/validate_swarm.py` after `python scripts/validate_crew.py`:

```bash
source .venv/bin/activate
python scripts/validate_gemini_git_ops.py
python scripts/validate_codex_code_exec.py
python scripts/validate_ai_team_repo_profile.py
python scripts/validate_orchestrator_state.py
python scripts/validate_hitl_asana_approval.py
python scripts/validate_provider_config.py
python scripts/validate_agent_definitions.py
python scripts/validate_crew.py
python scripts/validate_swarm.py
python scripts/validate_gumloop_examples.py
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add MAT-45 swarm schema to CLAUDE.md"
```

---

### Task 9: Run full validation

**Files:**
- None (verification only)

- [ ] **Step 1: Activate virtual environment**

```bash
source .venv/bin/activate
```

- [ ] **Step 2: Run swarm validation**

Run: `python scripts/validate_swarm.py`
Expected output:
```
Loaded N agent names from /path/to/agents
OK valid    schemas/swarm/v1/examples/language-variants.json
OK valid    schemas/swarm/v1/examples/model-comparison.json
OK invalid  schemas/swarm/v1/examples/invalid/majority-vote-two-candidates.json (python: ...)
OK invalid  schemas/swarm/v1/examples/invalid/wrong-consensus.json (schema: ...)
No swarms directory at /path/to/swarms; skipping swarm file validation.
All MAT-45 swarm definition checks passed (bundle: ...).
```

- [ ] **Step 3: Run all validation scripts to ensure no regressions**

Run: `python scripts/validate_crew.py && python scripts/validate_swarm.py`
Expected: Both pass

- [ ] **Step 4: Final commit (if any fixes needed)**

```bash
git status
# If clean, no action needed
# If changes, commit with appropriate message
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Task 1: `schemas/swarm/v1/swarm.schema.json` — conditional if/then/else validation
- [x] Task 2: `schemas/swarm/v1/manifest.json` — bundle metadata
- [x] Task 3: Valid examples (model-comparison.json, language-variants.json)
- [x] Task 4: Invalid examples with README explaining each
- [x] Task 5: `swarms/` directory with README
- [x] Task 6: `scripts/validate_swarm.py` — schema + Python semantic validation
- [x] Task 7: `config/schema-registry.json` — swarm@v1 bundle
- [x] Task 8: `CLAUDE.md` — validate_swarm.py command
- [x] Task 9: Full validation run

**Placeholder scan:** None found. All code blocks are complete.

**Type consistency:** 
- `dispatch_mode` enum: `["parallel_model", "variant"]` — consistent throughout
- `consensus_strategy` values: `first-complete`, `majority-vote`, `return-all` — consistent throughout
- `candidates` pattern: `^[a-z][a-z0-9-]*$` — matches agent name pattern
