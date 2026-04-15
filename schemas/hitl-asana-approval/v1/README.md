# MAT-6 — HITL Asana approval triggers and callbacks (`v1`)

JSON Schemas for **human-in-the-loop** gates when the MAT-4 queue marks an item **`blocked_hitl`**. The orchestrator (or a companion tool) emits a **trigger** payload for automation to create or route an Asana approval task; after the human decides, the bridge delivers a **callback** so the orchestrator can update queue status and continue.

## Schema identity

- Uses **Draft 2020-12** with **only** `#/$defs/...` fragment references (same convention as MAT-1 / MAT-2 / MAT-4 / MAT-9).
- **`manifest.json`** indexes the bundle; it is not a JSON Schema instance.

## Repo config (`config/schema-registry.json`)

| Field | Purpose |
|-------|---------|
| `schema_bundles["hitl-asana-approval@v1"].root_relative` | Directory containing `manifest.json`, `trigger.schema.json`, `callback.schema.json`, and `examples/`. |

Override the bundle directory without editing config:

```bash
export MAT_HITL_ASANA_APPROVAL_V1=/absolute/path/to/schemas/hitl-asana-approval/v1
python scripts/validate_hitl_asana_approval.py
```

## Coordination with MAT-4

- Set **`queue.items[].status`** to **`blocked_hitl`** before emitting a trigger for that item.
- **`correlation_id`** (UUID) and **`queue_item_id`** SHOULD match **`queue.items[].correlation_id`** (when present) and **`queue.items[].id`** so artifacts and logs remain joinable.
- Optional **`orchestrator_state_path`** is a repo-relative path to the state document (same path rules as MAT-4 / MAT-9).

## Coordination with MAT-9

- Optional **`repo_profile_identity_id`** matches **`identity.id`** in `ai-team.repo.json` and **`repo_profile.identity_id`** in orchestrator state.

## Out of scope (by design)

- Asana OAuth tokens, webhook HMAC verification, and HTTP transport are **not** part of these schemas.
- Mapping **`decision`** to the next MAT-4 **`status`** value (`pending`, `failed`, `cancelled`, etc.) is **policy** for the orchestrator implementation.

## Validate locally

```bash
cd /path/to/multi-agent-toolkit
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/validate_hitl_asana_approval.py
```
