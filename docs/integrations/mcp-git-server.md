# MAT-1 MCP Git Server (MAT-101)

Exposes the deny-by-default MAT-1 git executor (`schemas/gemini-git-ops/v1/`) as
an [MCP](https://modelcontextprotocol.io/) server so any MCP client can call the
same allowlisted ops. The **manifest** remains the permission boundary — MCP
does not invent new git capabilities.

## Install

```bash
pip install '.[mcp]'
```

## Run (stdio)

```bash
python -m mat_runtime.mcp_git_server
# or
python scripts/run_mcp_git_server.py
```

Optional: `--manifest /path/to/manifest.json`, or set `MAT_GEMINI_GIT_OPS_V1` to
the `schemas/gemini-git-ops/v1` directory (same override as the schema validator).

## MAT-1 → MCP tool mapping

Each entry in `manifest.json` → `allowed_operations` becomes one MCP tool.
Dotted MAT-1 ops map to underscored tool names:

| MAT-1 `op` | MCP tool name |
|------------|---------------|
| `git.status` | `git_status` |
| `git.fetch` | `git_fetch` |
| `git.pull` | `git_pull` |
| `git.checkout_new_branch` | `git_checkout_new_branch` |
| `git.checkout_existing` | `git_checkout_existing` |
| `git.branch_list` | `git_branch_list` |
| `git.worktree_add` | `git_worktree_add` |
| `git.worktree_remove` | `git_worktree_remove` |
| `git.worktree_list` | `git_worktree_list` |
| `git.push` | `git_push` |
| `git.add` | `git_add` |
| `git.commit` | `git_commit` |
| `git.diff` | `git_diff` |

Tool arguments:

| Field | Required | Description |
|-------|----------|-------------|
| `repo_root` | yes | Absolute or `~`-relative repo path (same rules as MAT-1) |
| `params` | no | Op-specific object from `request.schema.json` `$defs` |
| `timeout_ms` | no | Wall-clock budget (MAT-11); default 60s |

Flat params (e.g. `message` on `git_commit`) are also accepted and folded into
`params`.

## Permission model

- **Source of truth:** `schemas/gemini-git-ops/v1/manifest.json` — read at
  startup; not duplicated in code.
- **Deny-by-default:** tools not on the allowlist return
  `{"ok": false, "error": "op_not_allowed"}` and never call `subprocess`.
- **No shell:** every op maps to an explicit `git …` argv list
  (`subprocess.run(..., shell=False)`).

## Relation to the MAT-1 JSON envelope

MAT-1 request/response schemas (`correlation_id`, `idempotency_key`,
`schema_version`, structured `result` / `error`) stay the internal wire format
for orchestrator ↔ executor JSON. The MCP surface is a thinner mapping: one tool
per allowlisted op, returning `{ok, stdout, stderr, argv, …}`. Clients that need
the full envelope can still emit MAT-1 JSON to a future bridge; this server
covers the MCP-native path described in the schema README.

## Example (conceptual)

```json
{
  "name": "git_status",
  "arguments": {
    "repo_root": "/path/to/repo",
    "params": {}
  }
}
```
