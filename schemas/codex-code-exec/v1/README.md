# MAT-2 — Claude → Codex code execution contracts (`v1`)

Versioned JSON Schemas for requests and responses between the **orchestrator (Claude Code)** and a **code-execution worker** (e.g. OpenAI Codex in a sandbox). This bundle covers **scoped implementation, tests, and refactors** — not repo-wide git (see **MAT-1** / **MAT-12**).

## Schema identity (vendor-neutral)

- Same rules as MAT-1: **fragment `$ref` only** inside each schema file; **`manifest.json`** uses `bundle_id` `codex-code-exec@v1`.
- Shared request envelope `$defs` live in **`request.schema.json`**. Shared error codes and optional documented result shapes live in **`response.schema.json` → `$defs`** (top-level `result` stays open for forward compatibility, like MAT-1).

## Repo config (`config/schema-registry.json`)

| Field | Purpose |
|-------|---------|
| `schema_bundles["codex-code-exec@v1"].root_relative` | Directory for this bundle. |
| `MAT_CODEX_CODE_EXEC_V1` | Env override for validators (absolute path to this `v1` folder). |

## Files in this folder

| File | Purpose |
|------|---------|
| `manifest.json` | Allowlisted `op` values (deny-by-default). |
| `request.schema.json` | Envelope + `params` per `op` + optional `session` (multi-turn). |
| `response.schema.json` | Success (`result`) or failure (`error`) envelope. |
| `examples/` | Valid / invalid fixtures for CI. |

## Session semantics

- **`session`** on the request is optional. When present, **`session_id`** and **`turn`** are required; clients should use monotonic **`turn`** per `session_id` for idempotent resume (executor may return `SESSION_TURN_MISMATCH`).
- On success, workers may return a **`result.session`** object (`session_id`, **`next_turn`**, **`terminal`**) so the orchestrator knows how to continue. Shapes are documented under `response.schema.json` → `$defs/result_session`.

## Validate locally

```bash
cd /path/to/multi-agent-toolkit
source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/validate_codex_code_exec.py
```

## Portable `repo_root`

Same as MAT-1: requests carry **`repo_root`** (absolute path). Combined with future **MAT-9** repo profiles, paths stay explicit rather than implicit cwd.
