# MAT-17 — Agent definition schema (`v1`)

Versioned JSON Schema for validating **agent definition frontmatter**. Agent definitions are Markdown files with YAML frontmatter that describe an agent's identity, capabilities, and system prompt.

See **`docs/agent-definition-format.md`** for the full specification.

## Schema identity (vendor-neutral)

- Same rules as other MAT bundles: **fragment `$ref` only** inside the schema file.
- **`manifest.json`** uses `bundle_id` `agent-definition@v1`.

## Repo config (`config/schema-registry.json`)

| Field | Purpose |
|-------|---------|
| `schema_bundles["agent-definition@v1"].root_relative` | Directory for this bundle. |
| `MAT_AGENT_DEFINITION_V1` | Env override for validators (absolute path to this `v1` folder). |

## Files in this folder

| File | Purpose |
|------|---------|
| `manifest.json` | Bundle metadata and notes. |
| `agent-frontmatter.schema.json` | Schema for validating frontmatter. |
| `examples/` | Valid / invalid frontmatter fixtures for CI. |

## Agent definition format

Agent definitions live in `agents/*.md`:

```markdown
---
name: coder
description: Implements code changes
role: worker
cli: codex
allowed_mat_ops:
  - codex.implement
  - codex.test
tools:
  - read
  - write
  - bash
---

You are a code implementation agent...
```

## Frontmatter fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Unique agent identifier |
| `description` | string | Yes | Human-readable description |
| `role` | enum | Yes | `orchestrator`, `worker`, or `executor` |
| `cli` | enum | Yes | CLI tool binding |
| `allowed_mat_ops` | string[] | No | MAT-2 operations allowed |
| `tools` | string[] | No | Tools the agent can use |
| `timeout_ms` | integer | No | Default timeout |
| `temperature` | number | No | Default temperature |

## Core agents

| Agent | Role | CLI | Purpose |
|-------|------|-----|---------|
| `orchestrator` | orchestrator | claude | Plan, route, synthesize |
| `coder` | worker | codex | Implement code |
| `researcher` | executor | gemini | Gather information |
| `reviewer` | worker | claude | Code review |
| `tester` | worker | codex | Write and run tests |

## Validate locally

```bash
cd /path/to/multi-agent-toolkit
source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/validate_agent_definitions.py
```

The validator checks:
1. Example frontmatter JSON files against schema
2. Actual `agents/*.md` files for valid frontmatter
3. Name uniqueness across all agents
