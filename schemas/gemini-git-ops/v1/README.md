# MAT-1 — Claude → Gemini git/CLI contracts (`v1`)

Versioned JSON Schemas for requests and responses between the **orchestrator (Claude Code)** and a **git executor** (e.g. Gemini CLI bridge). The orchestrator never runs git; it only emits JSON validated against `request.schema.json`.

## Schema identity (vendor-neutral)

- Schemas use **only** the standard `$schema` keyword plus **`#/$defs/...` fragment references** inside each file. There is **no** embedded `https://` document id and no dependency on any particular docs host (the old `gusto.github.io/...` style ids were removed).
- Shared field shapes for requests live in **`request.schema.json` → `$defs`**. Response-only shared shapes (**`error_code`**, **`git_error_details`**, etc.) live in **`response.schema.json` → `$defs`** (small intentional duplication so each file validates standalone).
- **`manifest.json`** is not a JSON Schema document; it uses a neutral **`bundle_id`** string (`gemini-git-ops@v1`), not a URL.

## Repo config (`config/schema-registry.json`)

| Field | Purpose |
|-------|---------|
| `schema_bundles["gemini-git-ops@v1"].root_relative` | Directory containing `manifest.json`, `request.schema.json`, `response.schema.json`, and `examples/`. |
| `published_document_base` | Reserved for an **optional** org-specific publish step (e.g. uploading to an internal static site). **Committed schemas do not read this file** — only tooling you add later would. |

Override the bundle directory without editing config:

```bash
export MAT_GEMINI_GIT_OPS_V1=/absolute/path/to/schemas/gemini-git-ops/v1
python scripts/validate_gemini_git_ops.py
```

## Files in this folder

| File | Purpose |
|------|---------|
| `manifest.json` | `bundle_id`, schema version, **allowlist** of `op` values (deny-by-default for implementers). |
| `request.schema.json` | Request envelope + `params` keyed by `op` + shared `$defs` for envelope fields. |
| `response.schema.json` | Success (`result`) or failure (`error`) envelope + `$defs` for errors and result shapes. |
| `examples/` | Valid / invalid fixtures for CI and manual testing. |

## Invoke from Claude Code

1. **MCP tool (recommended):** expose a single tool (e.g. `mat_git_op`) whose input matches `request.schema.json`. A small MCP server validates JSON, executes argv-mapped git under `repo_root`, returns a `response` object.
2. **Subprocess bridge:** write the request JSON to stdin of `mat-git-exec` (future binary); read JSON stdout. Same schemas; useful when MCP is unavailable.

In both cases the **executor** must:

- Reject `op` not in `manifest.json → allowed_operations`.
- Run **no shell** — spawn `git` with explicit argv only.
- Honor `idempotency_key` (return `replay: true` + prior `result` when safe).

## Result shapes per `op`

Executors should populate `result` consistently; recommended shapes live under `response.schema.json` → `$defs` (`result_status`, `result_worktree_add`, …). The top-level `result` property stays a JSON object for forward compatibility.

## Validate locally

```bash
cd /path/to/multi-agent-toolkit
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/validate_gemini_git_ops.py
```

## Portable `repo_root`

Requests always carry **`repo_root`** (absolute path). Orchestration code must not assume cwd; profile-driven paths and work-item adapters are **MAT-9** (`schemas/ai-team-repo-profile/v1/`).
