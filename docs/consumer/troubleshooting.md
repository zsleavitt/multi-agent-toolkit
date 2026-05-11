# Troubleshooting consumer setups

## `python lib/skills/...` fails with “No such file or directory”

**Cause:** `.cursorrules` still points at `lib/skills` relative to **your** app repo, but MAT lives under a submodule or another path.

**Fix:** Edit commands to the real path, e.g. `vendor/multi-agent-toolkit/lib/skills/...`, or set `PYTHONPATH` and invoke a small wrapper script in your repo.

## `ModuleNotFoundError: mat_runtime`

**Cause:** `PYTHONPATH` does not include the toolkit root, or the venv lacks an editable install.

**Fix:**

```bash
export PYTHONPATH="/path/to/multi-agent-toolkit:$PYTHONPATH"
# or
pip install -e /path/to/multi-agent-toolkit
```

## `mat_runtime list-agents` returns no agents

**Cause:** No `agents/` directory found when walking up from cwd, or empty directory.

**Fix:** Copy or maintain `agents/*.md` under your repo root (see [`docs/agent-definition-format.md`](../../docs/agent-definition-format.md)), or pass explicit paths if your integration supports it.

## Wrong CLI invoked for coder / reviewer

**Cause:** Missing or incorrect **MAT-16** file.

**Fix:** Add **`mat-config.json`** or **`.mat/config.json`** at the repo root. The router merges **`agents.<role>`** then **`agents.<agent-name>`** (per-agent wins), so you can override only `reviewer` or `coder` without touching `agents/*.md`. See **`mat-config.example.json`** and [`schemas/provider-config/v1/README.md`](../../schemas/provider-config/v1/README.md).

## `/ticket` does nothing or errors

**Causes:**

- `ai-team.repo.json` missing or `work_item_source.adapter` is `none`.
- MCP for Notion/Linear/Jira/GitHub not connected (orchestrator-only in typical setups).
- Skill output expects an MCP tool call your environment does not expose.

**Fix:** Validate `ai-team.repo.json` ([guide](ai-team-repo-profile.md)); configure MCP in Claude Code / Cursor; read `lib/skills/ticket/instructions.md`.

## JSON Schema validation errors on `ai-team.repo.json`

**Cause:** Typo in adapter name, forbidden absolute path in `path_overrides`, or wrong `schema_version`.

**Fix:** Compare against [`schemas/ai-team-repo-profile/v1/examples/valid/`](../../schemas/ai-team-repo-profile/v1/examples/valid/); read validator messages; use editor schema association (see [ai-team-repo-profile.md](ai-team-repo-profile.md#validate-your-file)).

## `mat_runtime smoke --strict` fails

**Cause:** A CLI referenced in `agents/` or provider config is not installed or not on `PATH`.

**Fix:** Install the missing tool, or relax to `python -m mat_runtime smoke` without `--strict` on machines that only run a subset of roles.

## Claude Code skills do not autocomplete

**Cause:** Plugin path wrong or `installed_plugins.json` entry stale.

**Fix:** Follow [`adapters/claude-code/README.md`](../../adapters/claude-code/README.md) verification steps; restart Claude Code.

## Cursor does not recognize `/develop`

**Cause:** `.cursorrules` not at project root, or Cursor needs reload.

**Fix:** Place file at workspace root; restart Cursor; check Cursor settings for rules file name and scope.
