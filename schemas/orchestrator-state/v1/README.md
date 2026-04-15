# MAT-4 / MAT-10 — Orchestrator persisted state (`v1`)

JSON Schema for a **single durable state document** (`orchestrator.state.json` or `ai-team.state.json`): **work queue**, **artifact index**, and **session checkpoints**. Paths are **repo-relative from repo root** (same rules as MAT-9); pair with **`repo.path_overrides.artifacts_dir`** and **`agent_state_dir`** in the portable repo profile for conventional layout.

**MAT-10** adds optional **orchestrator session** and **fluency** metadata on checkpoints so the primary orchestrator session (main Claude Code) can record planning/review phases for correlation with fluency tooling (for example **`/ai-fluency-insights`** via `claude-introspection`). Use document **`schema_version`** `1.1.0` when emitting these fields; documents without them may remain **`1.0.0`**.

## Schema identity

- Uses **Draft 2020-12** with **only** `#/$defs/...` fragment references (same convention as MAT-1 / MAT-2 / MAT-9).
- **`manifest.json`** indexes the bundle; it is not a JSON Schema instance.

## Repo config (`config/schema-registry.json`)

| Field | Purpose |
|-------|---------|
| `schema_bundles["orchestrator-state@v1"].root_relative` | Directory containing `manifest.json`, `orchestrator-state.schema.json`, and `examples/`. |

Override the bundle directory without editing config:

```bash
export MAT_ORCHESTRATOR_STATE_V1=/absolute/path/to/schemas/orchestrator-state/v1
python scripts/validate_orchestrator_state.py
```

## Coordination with MAT-9

- **`repo_profile.identity_id`** (optional) should match **`identity.id`** in `ai-team.repo.json`.
- **`artifacts.items[].path`** and **`checkpoints.items[].path`** use the same **`repo_relative_path`** constraints as MAT-9 (no leading `/`, no `http(s):`, no leading `../`).
- Recommended prefixes: artifacts under **`repo.path_overrides.artifacts_dir`**, checkpoints under **`repo.path_overrides.agent_state_dir`** when those keys are set.

## Queue and external work items

- **`queue.items[].work_item`** is optional; when present, **`adapter`** uses the same discriminant names as MAT-9 **`work_item_source.adapter`** (`none`, `linear`, `jira`, `github_issues`, `file`).
- **`queue.items[].status`** is a fixed lifecycle enum for orchestration (`pending` … `cancelled`).
- Use **`blocked_hitl`** when a human gate is required; pair outbound payloads with **MAT-6** `schemas/hitl-asana-approval/v1/trigger.schema.json` and resume via **`callback.schema.json`** (same **`correlation_id`** / **`queue_item_id`**).

## Checkpoints and MAT-2

- **`checkpoints.items[].session`** (optional) mirrors MAT-2 request **`session`**: `session_id` + monotonic **`turn`**, so tooling can relate a checkpoint file to a Codex-style session.

## Orchestrator session and fluency (MAT-10)

- **`orchestrator_session`** (optional, top-level) identifies the **primary orchestrator** run (e.g. main Claude Code). It is **not** the same object as **`checkpoints.items[].session`**, which links a checkpoint to a **MAT-2** worker session.
- **`checkpoints.items[].fluency`** (optional) records **`capture_phase`** (`planning`, `review`, `routing`, `synthesis`, `other`) and optional **`insights_surface`** (string label such as `/ai-fluency-insights`, not a URL) plus an optional **`correlation_id`** for introspection exports. Prefer **planning** and **review** in the main orchestrator session when fluency scores should reflect high-signal work.

## Validate locally

```bash
cd /path/to/multi-agent-toolkit
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/validate_orchestrator_state.py
```
