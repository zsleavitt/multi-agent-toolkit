# MAT-2 — Claude → Codex code execution contracts (`v1`)

Versioned JSON Schemas for requests and responses between the **orchestrator (Claude Code)** and a **code-execution worker** (e.g. OpenAI Codex in a sandbox). This bundle covers **scoped implementation, tests, refactors, diagnosis, and review** — not repo-wide git (see **MAT-1** / **MAT-12**).

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

## Timeout (MAT-14)

- Optional **`timeout_ms`** on the request: integer milliseconds **1**–**86400000**; executor may clamp. Omitted means executor default.
- Use **`schema_version`** **1.1.0** when emitting **`timeout_ms`**; documents without it may remain **1.0.0**.
- **`TIMEOUT`** in `response.schema.json` → `error.code` covers budget exhaustion (already defined for MAT-2).

## Diagnose and review (MAT-13)

- **`codex.diagnose`** — read-oriented root-cause analysis. Params: required **`instruction`**; optional **`scope_paths`**, **`evidence`** (strings), **`readonly_paths`**. Recommended success shape: **`result_diagnose`** (`summary`, optional **`hypothesis`**, **`likely_causes`**, **`recommended_next_steps`**, **`session`**).
- **`codex.review`** — structured code review. Params: required **`instruction`** and **`scope_paths`** (≥1 path); optional **`acceptance_criteria`**, **`minimum_severity`** (`info`, `suggestion`, `issue`, or `blocker`). Recommended success shape: **`result_review`** (`summary`, **`findings`** array of **`review_finding`**: required **`severity`**, **`path`**, **`message`**; optional **`line`**, **`end_line`**, **`category`**, **`code_snippet`**).
- Use request/response **`schema_version`** **1.2.0** when emitting **`codex.diagnose`** or **`codex.review`** so executors can rely on MAT-13 shapes (older **1.0.0** / **1.1.0** documents remain valid for other ops).

## Validate locally

```bash
cd /path/to/multi-agent-toolkit
source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/validate_codex_code_exec.py
```

## Portable `repo_root`

Same as MAT-1: requests carry **`repo_root`** (absolute path). Combined with **MAT-9** repo profiles, paths stay explicit rather than implicit cwd.

### Path validation (MAT-23)

The schema enforces that `repo_root` starts with:
- `/` (Unix/macOS/Linux absolute)
- `~` or `~user` (Unix home-relative, e.g. `~/projects/webapp` or `~first.last/projects`)
- A drive letter followed by `:\` or `:/` (Windows, e.g. `C:\Projects` or `D:/repos`)

**Executors MUST additionally:**
1. Expand `~` paths to the appropriate home directory
2. Verify the path exists on the filesystem
3. Reject paths containing `/../` traversal sequences
4. Ensure the resolved path is within allowed boundaries

## Scope boundaries

This bundle covers **code execution and analysis** ops: implement, test, refactor, diagnose, review. **MAT-12 (done):** `git add`, `git commit`, and `git diff` are **MAT-1** wire ops only (allowlisted `git` argv on the executor). MAT-2 does not carry git staging, commits, or diff requests — orchestrators emit MAT-1 JSON for those after Codex (or other workers) finish editing.
